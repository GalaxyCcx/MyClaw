from __future__ import annotations

import json
import logging
import re
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from agent.engine import run_agent, PROMPTS_DIR, _build_system_prompt, MODEL_CONTEXT_LIMITS, DEFAULT_CONTEXT_LIMIT
from agent.init_jobs import init_collector
from agent.skill_loader import get_skill_loader
from tools import BUILTIN_TOOLS

logger = logging.getLogger(__name__)

router = APIRouter()

MEMORY_DIR = Path(__file__).resolve().parent.parent / "memory" / "conversations"


def _save_turn(session_id: str, turn_num: int, user_content: str,
               round_messages: list, created_at: str):
    """Append a conversation turn to the session markdown file."""
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    file_path = MEMORY_DIR / f"conv_{session_id}.md"

    if turn_num == 1:
        header = f"""---
session_id: {session_id}
created_at: {created_at}
turns: {turn_num}
---

# 对话记录

"""
        file_path.write_text(header, encoding="utf-8")

    now_str = datetime.now(timezone.utc).strftime("%H:%M:%S")
    lines = [f"\n## Turn {turn_num}\n"]
    lines.append(f"### 用户 ({now_str})\n")
    lines.append(f"{user_content}\n")

    for msg in round_messages:
        tool_calls = getattr(msg, "tool_calls", None)
        content = getattr(msg, "content", "")
        role = getattr(msg, "type", "")

        if role == "ai" and tool_calls:
            for tc in tool_calls:
                lines.append(f"\n### Agent 工具调用\n")
                lines.append(f"**工具**: `{tc.get('name', '')}`\n")
                args_str = json.dumps(tc.get("args", {}), ensure_ascii=False)
                lines.append(f"**参数**: `{args_str}`\n")
        elif role == "tool":
            name = getattr(msg, "name", "")
            status = "失败" if content.startswith("错误") else "成功"
            lines.append(f"\n### 工具结果\n")
            lines.append(f"**工具**: `{name}` | **状态**: {status}\n")
            lines.append(f"```\n{content[:2000]}\n```\n")
        elif role == "ai" and content:
            lines.append(f"\n### Agent 最终回答\n")
            lines.append(f"{content}\n")

    lines.append("\n---\n")

    with open(file_path, "a", encoding="utf-8") as f:
        f.writelines(lines)

    _update_frontmatter_turns(file_path, turn_num)


def _update_frontmatter_turns(file_path: Path, turns: int):
    text = file_path.read_text(encoding="utf-8")
    text = re.sub(r"(?m)^turns:\s*\d+", f"turns: {turns}", text)
    file_path.write_text(text, encoding="utf-8")


# --- HTTP API ---

@router.get("/api/tools")
async def list_tools():
    builtin = [
        {"name": t.name, "description": t.description, "source": "builtin"}
        for t in BUILTIN_TOOLS
    ]
    return {"tools": builtin}


@router.get("/api/skills")
async def list_skills():
    loader = get_skill_loader()
    return {
        "skills": [
            {
                "name": s.name,
                "description": s.description,
                "status": s.status,
                "metadata": s.metadata,
                "scripts": s.scripts,
            }
            for s in loader.loaded_skills
        ]
    }


@router.get("/api/skills/{name}/doc")
async def get_skill_doc(name: str):
    loader = get_skill_loader()
    doc = loader.get_skill_doc(name)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")
    return {"name": name, "doc": doc}


@router.get("/api/skills/{name}/reference/{ref_path:path}")
async def get_skill_reference(name: str, ref_path: str):
    loader = get_skill_loader()
    content = loader.get_skill_reference(name, ref_path)
    if content is None:
        raise HTTPException(status_code=404, detail=f"Reference not found: {name}/{ref_path}")
    return {"name": name, "path": ref_path, "content": content}


class PromptUpdateRequest(BaseModel):
    content: str


@router.get("/api/prompts/system")
async def get_system_prompt():
    path = PROMPTS_DIR / "system.md"
    if path.exists():
        content = path.read_text(encoding="utf-8")
        updated_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
    else:
        content = ""
        updated_at = None
    return {"content": content, "path": "prompts/system.md", "updated_at": updated_at}


@router.put("/api/prompts/system")
async def update_system_prompt(req: PromptUpdateRequest):
    path = PROMPTS_DIR / "system.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(req.content, encoding="utf-8")
    return {"message": "System prompt 已更新", "path": "prompts/system.md"}


@router.get("/api/conversations")
async def list_conversations():
    if not MEMORY_DIR.exists():
        return {"conversations": []}
    conversations = []
    for f in sorted(MEMORY_DIR.glob("conv_*.md"), reverse=True):
        text = f.read_text(encoding="utf-8")
        fm_match = re.search(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
        if fm_match:
            import yaml
            fm = yaml.safe_load(fm_match.group(1)) or {}
            conversations.append({
                "session_id": fm.get("session_id", ""),
                "created_at": fm.get("created_at", ""),
                "turns": fm.get("turns", 0),
            })
    return {"conversations": conversations}


@router.get("/api/conversations/{session_id}")
async def get_conversation(session_id: str):
    file_path = MEMORY_DIR / f"conv_{session_id}.md"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"session_id": session_id, "content": file_path.read_text(encoding="utf-8")}


@router.post("/api/skills/reload")
async def reload_skills():
    loader = get_skill_loader()
    loader.discover()
    return {
        "message": f"重新发现完成，共 {len(loader.loaded_skills)} 个 Skill",
        "skills": [s.name for s in loader.loaded_skills],
    }


# --- WebSocket ---

@router.websocket("/ws/chat")
async def chat_ws(websocket: WebSocket):
    await websocket.accept()
    history: list = []
    session_id = uuid.uuid4().hex[:12]
    turn_num = 0
    created_at = datetime.now(timezone.utc).isoformat()

    loader = get_skill_loader()
    builtin_tools_info = [
        {"name": t.name, "source": "builtin"} for t in BUILTIN_TOOLS
    ]
    skills_info = [
        {"name": s.name, "description": s.description, "scripts": s.scripts}
        for s in loader.loaded_skills
    ]
    assembled_prompt = _build_system_prompt()
    import os
    model_name = os.getenv("LLM_MODEL", "qwen-plus")
    context_limit = MODEL_CONTEXT_LIMITS.get(model_name, DEFAULT_CONTEXT_LIMIT)
    await websocket.send_json({
        "type": "init_status",
        "step": 0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": {
            "jobs": init_collector.to_dict_list(),
            "tools": builtin_tools_info,
            "skills": skills_info,
            "system_prompt": assembled_prompt,
            "model_name": model_name,
            "context_limit": context_limit,
        },
    })

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
                user_content = msg.get("data", {}).get("content", "")
            except (json.JSONDecodeError, AttributeError):
                user_content = raw.strip()

            if not user_content:
                continue

            turn_num += 1

            await websocket.send_json({
                "type": "graph_reset",
                "step": 0,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {},
            })

            await websocket.send_json({
                "type": "user_input",
                "step": 0,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {"content": user_content},
            })

            async def on_event(event: dict):
                await websocket.send_json(event)

            try:
                round_messages = await run_agent(user_content, on_event, history=history, turn_num=turn_num)
                history.append({"role": "user", "content": user_content})
                history.extend(round_messages)

                try:
                    _save_turn(session_id, turn_num, user_content, round_messages, created_at)
                except Exception as e:
                    logger.warning("Failed to save conversation turn: %s", e)

            except Exception:
                tb = traceback.format_exc()
                logger.error("Agent error: %s", tb)
                await websocket.send_json({
                    "type": "error",
                    "step": -1,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "data": {"message": "Agent 执行出错", "detail": tb[-500:]},
                })

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected (session=%s, turns=%d)", session_id, turn_num)
