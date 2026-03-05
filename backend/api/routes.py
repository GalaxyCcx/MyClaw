from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from config.mcp_config import list_mcps, set_mcp_enabled
from browser_gateway import get_browser_gateway_manager
from browser_gateway.protocol import GatewayMessageType
from agent.engine import run_agent, PROMPTS_DIR, _build_system_prompt, MODEL_CONTEXT_LIMITS, DEFAULT_CONTEXT_LIMIT
from agent.auto_compactor import compact_history
from agent.context_budget import load_context_policy, compute_thresholds, estimate_messages_tokens
from agent.init_jobs import init_collector
from agent.overflow_recovery import is_context_overflow
from agent.history_pruner import prune_history
from agent.skill_loader import get_skill_loader
from tools import get_all_tools
from api.alpha_bi_core_metrics_job import (
    month_range_ymd as _core_month_range_ymd,
    text_hash as _core_text_hash,
    extract_snapshot_text_and_elements as _core_extract_snapshot_text_and_elements,
    find_query_ref as _core_find_query_ref,
)
from api.alpha_bi_select_dropdown_job import match_dropdown_option as _match_dropdown_option

logger = logging.getLogger(__name__)

router = APIRouter()

MEMORY_DIR = Path(__file__).resolve().parent.parent / "memory" / "conversations"
DEPRECATED_BROWSER_SKILLS: set[str] = set()


def _browser_transport() -> str:
    return (os.getenv("BROWSER_TRANSPORT", "legacy_mcp") or "legacy_mcp").strip().lower()


def _filter_runtime_skills(skills):
    if _browser_transport() == "native_extension":
        return [s for s in skills if getattr(s, "name", "") not in DEPRECATED_BROWSER_SKILLS]
    return skills


def _extract_user_friendly_error(exc: BaseException) -> str:
    """Extract short, user-friendly message from exception."""
    msg = str(exc).lower()
    if "502" in msg or "bad gateway" in msg:
        return "浏览器 bridge 连接异常。请在扩展中点击「断开」后重新「Connect」，或重启 Chrome。"
    if "failed to connect" in msg or "无法连接" in msg:
        return "无法连接浏览器 bridge。请确认扩展已点击 Connect，或尝试断开后重新连接。"
    if "context" in msg or "overflow" in msg or "token" in msg:
        return "上下文已满，请简化任务或开启新对话后重试。"
    first_line = str(exc).split("\n")[0].strip()
    return first_line[:120] + ("..." if len(first_line) > 120 else "")


def _is_tool_error_content(content: str) -> bool:
    raw = str(content or "").strip()
    if not raw:
        return False
    # Skill 文档/参考文档读取成功时会以该前缀返回，不应误判失败。
    if raw.startswith("=== Skill '"):
        return False
    text = raw.lower()
    if not text:
        return False
    return (
        text.startswith("错误")
        or text.startswith("error")
        or text.startswith("failed")
        or "timeout" in text
        or "element not found" in text
        or "stale" in text
    )


def _govern_history_before_run(
    history: list,
    user_content: str,
    model_name: str,
    context_limit: int,
):
    policy = load_context_policy()
    thresholds = compute_thresholds(
        context_limit=context_limit,
        reserve_tokens=policy.reserve_tokens,
        soft_threshold=policy.soft_threshold_tokens,
    )
    probe_messages = list(history) + [{"role": "user", "content": user_content}]
    probe_tokens = estimate_messages_tokens(probe_messages, model_name=model_name)

    events: list[dict] = []
    governed_history = list(history)

    if probe_tokens > thresholds["preflight_limit"]:
        pruned_history, prune_stats = prune_history(
            governed_history,
            target_tokens=thresholds["target_tokens"],
            preserve_recent_turns=policy.preserve_recent_turns,
            model_name=model_name,
            max_tool_result_chars=policy.max_tool_result_chars,
        )
        pruned_probe = estimate_messages_tokens(pruned_history + [{"role": "user", "content": user_content}], model_name=model_name)
        if pruned_history != governed_history:
            events.append({
                "type": "context_pruned",
                "data": {
                    "before_tokens": prune_stats.get("before_tokens", probe_tokens),
                    "after_tokens": pruned_probe,
                    "dropped_messages": prune_stats.get("dropped_messages", 0),
                    "truncated_messages": prune_stats.get("truncated_messages", 0),
                },
            })
        governed_history = pruned_history
        probe_tokens = pruned_probe

    if probe_tokens > thresholds["preflight_limit"]:
        compacted_history, compact_stats = compact_history(
            governed_history,
            preserve_recent_turns=policy.preserve_recent_turns,
            model_name=model_name,
        )
        compacted_probe = estimate_messages_tokens(compacted_history + [{"role": "user", "content": user_content}], model_name=model_name)
        if compacted_history != governed_history:
            events.append({
                "type": "context_compacted",
                "data": {
                    "before_tokens": compact_stats.get("before_tokens", probe_tokens),
                    "after_tokens": compacted_probe,
                    "summary_chars": compact_stats.get("summary_chars", 0),
                    "compacted_turns": compact_stats.get("compacted_turns", 0),
                },
            })
        governed_history = compacted_history

    return governed_history, events, policy


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
            status = "失败" if _is_tool_error_content(content) else "成功"
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
    tools = get_all_tools()
    builtin = [
        {"name": t.name, "description": t.description, "source": "builtin"}
        for t in tools
    ]
    return {"tools": builtin}


@router.get("/api/skills")
async def list_skills():
    loader = get_skill_loader()
    runtime_skills = _filter_runtime_skills(loader.loaded_skills)
    return {
        "skills": [
            {
                "name": s.name,
                "description": s.description,
                "status": s.status,
                "metadata": s.metadata,
                "scripts": s.scripts,
            }
            for s in runtime_skills
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


class BrowserActionStepRequest(BaseModel):
    action: str
    payload: dict = {}


class BrowserActionsExecuteRequest(BaseModel):
    url: str | None = None
    wait_after_navigate_ms: int = 800
    timeout_seconds: int = 30
    stop_on_error: bool = True
    steps: list[BrowserActionStepRequest]


class AlphaBiDateFilterJobRequest(BaseModel):
    url: str | None = None
    current_start: str
    current_end: str
    compare_start: str
    compare_end: str
    wait_after_navigate_ms: int = 1500


class AlphaBiCoreMetricsQueryRequest(BaseModel):
    url: str | None = None
    year: int | None = None
    wait_after_navigate_ms: int = 25000
    max_attempts: int = 3
    post_query_wait_ms: int = 1800


class AlphaBiDownloadJobRequest(BaseModel):
    url: str | None = None
    table_keyword: str = "✔ [贡献拆解1]-商品分类"
    file_keyword: str | None = None
    wait_after_navigate_ms: int = 25000
    timeout_seconds: int = 180
    poll_interval_ms: int = 1200
    # 默认单次触发，避免重复创建离线下载任务
    single_trigger_only: bool = True
    # 在单次触发后，追加点击“前往任务中心”
    goto_center_after_trigger: bool = False


class AlphaBiProblemLocatorDownloadRequest(BaseModel):
    """表下载：悬浮-原始数据-跳转任务中心-下载。与旧 download job 隔离。"""
    url: str | None = None
    wait_after_navigate_ms: int = 25000
    download_icon_index: int = 1  # 全局 index（当无 within_text 时）
    within_text: str | None = None  # 区块锚定，如 "贡献拆解1"、"过程拆解2"，优先于 index
    tab_text: str | None = None  # 可选：下载前先点 Tab，如 "转化归因"
    tab_within: str | None = None  # 可选：Tab 所在区块，如 "四、趋势分析"


class AlphaBiTaskCenterDownloadRequest(BaseModel):
    """任务中心下载：直接访问 URL 无效，统一走 Alpha 数据页完整流程。"""
    url: str = "https://alpha-bi.ddxq.mobi/mine-data/index"
    wait_after_navigate_ms: int = 8000
    max_poll: int = 15
    poll_interval_ms: int = 5000


class AlphaBiDownloadPresetRequest(BaseModel):
    target_id: str = "problem_breakdown_2_order_user"
    url: str | None = None
    file_keyword: str | None = None
    wait_after_navigate_ms: int = 25000
    timeout_seconds: int = 120
    poll_interval_ms: int = 1200
    # 预置任务默认走单次触发模式（不做后续跳转/轮询）
    single_trigger_only: bool = True
    # 开启后走“任务中心跳转 + 下载完成”全流程
    full_flow: bool = False
    # 在单次触发链路上追加“前往任务中心”点击（不做下载完成轮询）
    goto_center_after_trigger: bool = False


class AlphaBiSnapshotRequest(BaseModel):
    """Alpha BI 页面 snapshot：navigate（可选）→ wait → snapshot，用于提取表名/Tab 等。"""

    url: str | None = None
    wait_after_navigate_ms: int = 25000
    mode: str = "full"  # full | summary


class AlphaBiLocateTableRequest(BaseModel):
    """locate-table：navigate（可选）→ snapshot → 校验 table_keyword 是否出现在 snapshot.text。"""

    table_keyword: str
    url: str | None = None
    wait_after_navigate_ms: int = 25000


class AlphaBiSelectDropdownRequest(BaseModel):
    """单选下拉选择：点击展开 → 读选项 → 匹配并点击目标。"""

    url: str | None = None
    wait_after_navigate_ms: int = 3000
    trigger_locator: dict  # 如 {"selector": ".ant-select", "within": {"text": "二、问题定位"}}
    target_value: str  # 目标选项文本（支持包含匹配）
    verify_selector: str | None = None  # 可选：校验用区块
    skip_click: bool = False  # True 时跳过点击触发器，直接 get_dropdown_options（用于下拉已手动打开）


class AlphaBiSelectMultiDropdownRequest(BaseModel):
    """多选下拉：点击展开 → 逐项点击目标选项 → 关闭。"""

    url: str | None = None
    wait_after_navigate_ms: int = 3000
    trigger_locator: dict
    target_values: list[str]  # 目标选项列表


class AlphaBiSelectCheckboxGroupRequest(BaseModel):
    """复选组：在 within 区块内，按 option_texts 逐项点击勾选。"""

    url: str | None = None
    wait_after_navigate_ms: int = 3000
    within_text: str  # 区块锚定，如 "二、问题定位"
    option_texts: list[str]  # 要勾选的选项文本


class AlphaBiFullFilterQueryRequest(BaseModel):
    """完整路径：定位表 → 填所有筛选项 → 点查询。二、问题定位 区块。"""

    url: str | None = None
    wait_after_navigate_ms: int = 8000
    table_keyword: str = "贡献拆解1"  # 可选校验
    category_value: str = "蔬菜组"  # 品类组
    dimension_value: str = "商品分类"  # 聚合维度
    post_query_wait_ms: int = 2000


class AlphaBiClickTabRequest(BaseModel):
    """Tab 点击：locate 匹配 tab_text → click。"""

    url: str | None = None
    wait_after_navigate_ms: int = 8000
    tab_text: str  # 目标 Tab 文案，如 "经营结果(主站)"
    within_text: str | None = None  # 可选区块锚定


async def _browser_action_or_http_error(action: str, payload: dict | None = None, timeout: float = 30.0) -> dict:
    result = await get_browser_gateway_manager().send_command(
        action=action,
        payload=payload or {},
        timeout=timeout,
    )
    if result.get("type") == "error":
        raise HTTPException(
            status_code=400,
            detail={
                "action": action,
                "message": result.get("message", "browser action failed"),
                "code": result.get("code", "execution_failed"),
                "raw": result,
            },
        )
    return result


def _extract_alpha_bi_date_ranges(snapshot_text: str) -> dict[str, str]:
    text = str(snapshot_text or "")
    # 期望形态（innerText）：当期 \n YYYY-MM-DD \n ~ \n YYYY-MM-DD \n 对比期 \n YYYY-MM-DD \n ~ \n YYYY-MM-DD
    pattern = re.compile(
        r"当期\s*\n\s*(\d{4}-\d{2}-\d{2})\s*\n\s*~\s*\n\s*(\d{4}-\d{2}-\d{2})\s*\n\s*对比期\s*\n\s*(\d{4}-\d{2}-\d{2})\s*\n\s*~\s*\n\s*(\d{4}-\d{2}-\d{2})",
        re.MULTILINE,
    )
    m = pattern.search(text)
    if m:
        return {
            "current_start": m.group(1),
            "current_end": m.group(2),
            "compare_start": m.group(3),
            "compare_end": m.group(4),
        }

    # 兼容乱码/文案变化：仅按日期+波浪线模式抓前两个区间。
    generic = re.compile(
        r"(\d{4}-\d{2}-\d{2})\s*\n\s*~\s*\n\s*(\d{4}-\d{2}-\d{2}).{0,200}?(\d{4}-\d{2}-\d{2})\s*\n\s*~\s*\n\s*(\d{4}-\d{2}-\d{2})",
        re.MULTILINE | re.DOTALL,
    )
    g = generic.search(text)
    if not g:
        return {}
    return {
        "current_start": g.group(1),
        "current_end": g.group(2),
        "compare_start": g.group(3),
        "compare_end": g.group(4),
    }


def _extract_expected_from_after_values(after_values: list[str], expected: dict[str, str]) -> dict[str, str]:
    if len(after_values) < 4:
        return {}
    candidate = {
        "current_start": str(after_values[0] or ""),
        "current_end": str(after_values[1] or ""),
        "compare_start": str(after_values[2] or ""),
        "compare_end": str(after_values[3] or ""),
    }
    if all(candidate.get(k) == v for k, v in expected.items()):
        return candidate
    return {}


def _month_range_ymd(year: int, month: int) -> tuple[str, str]:
    return _core_month_range_ymd(year, month)


def _text_hash(v: str) -> str:
    return _core_text_hash(v)


def _extract_snapshot_text_and_elements(snapshot_res: dict) -> tuple[str, list[dict]]:
    return _core_extract_snapshot_text_and_elements(snapshot_res)


def _find_query_ref(elements: list[dict]) -> str:
    return _core_find_query_ref(elements)


async def _click_query_button(
    query_ref: str,
    timeout: float = 20.0,
) -> tuple[bool, str, dict]:
    manager = get_browser_gateway_manager()
    if query_ref:
        click_by_ref = await manager.send_command(
            action="click",
            payload={"ref": query_ref},
            timeout=timeout,
        )
        if click_by_ref.get("type") != "error":
            return True, "click_ref", click_by_ref

    # 兜底：避免 text 点击（Alpha BI 已封禁），用按钮 selector 列表尝试。
    fallback_selectors = [
        "button.ant-btn-primary",
        ".ant-form button.ant-btn",
        "button[type='button']",
    ]
    for sel in fallback_selectors:
        click_res = await manager.send_command(
            action="click",
            payload={"selector": sel},
            timeout=timeout,
        )
        if click_res.get("type") != "error":
            return True, f"click_selector:{sel}", click_res
    return False, "click_failed", {}


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


@router.get("/api/mcp")
async def list_mcp():
    """List all known MCPs with enabled state."""
    if _browser_transport() == "native_extension":
        return {"mcps": []}
    return {"mcps": list_mcps()}


class MCPEnabledUpdate(BaseModel):
    enabled: bool


@router.patch("/api/mcp/{mcp_id}/enabled")
async def update_mcp_enabled(mcp_id: str, body: MCPEnabledUpdate):
    """Toggle MCP enabled state."""
    if _browser_transport() == "native_extension":
        raise HTTPException(status_code=400, detail="legacy MCP controls disabled in native_extension mode")
    mcps = {m["id"] for m in list_mcps()}
    if mcp_id not in mcps:
        raise HTTPException(status_code=404, detail=f"MCP '{mcp_id}' not found")
    set_mcp_enabled(mcp_id, body.enabled)
    return {"id": mcp_id, "enabled": body.enabled}


@router.get("/api/mcp/browser/status")
async def mcp_browser_status():
    """Diagnostic: check Browser MCP extension connection and tool loading."""
    if _browser_transport() == "native_extension":
        manager = get_browser_gateway_manager()
        status = await manager.status()
        browser_tool_count = len([t for t in get_all_tools() if getattr(t, "name", "").startswith("browser_")])
        return {
            "enabled": True,
            "transport": "native_extension",
            "tools_loaded": True,
            "tool_count": browser_tool_count,
            "mcp_process_ready": False,
            "extension_connected": bool(status.get("connected")),
            "session_id": status.get("active_client_id", ""),
            "last_success_at": "",
            "last_error_type": "",
            "last_error_message": "",
            "probe_error": "" if status.get("connected") else "native extension not connected",
            "message": "OK" if status.get("connected") else "DEGRADED",
            "channel_status": status,
        }

    from config.mcp_config import is_mcp_enabled

    enabled = is_mcp_enabled("browser-mcp")
    tools_loaded = False
    tool_count = 0
    mcp_process_ready = False
    extension_connected = False
    session_id = ""
    last_success_at = ""
    last_error_type = ""
    last_error_message = ""
    probe_error = ""
    msg = ""
    if enabled:
        try:
            from mcp_client import (
                BrowserMCPClient,
                get_browser_mcp_runtime_status,
                get_browser_mcp_tools,
                is_extension_not_connected_error,
            )

            runtime_status = get_browser_mcp_runtime_status()
            mcp_process_ready = bool(runtime_status.get("mcp_process_ready"))
            session_id = str(runtime_status.get("session_id") or "")
            last_success_at = str(runtime_status.get("last_success_at") or "")
            last_error_type = str(runtime_status.get("last_error_type") or "")
            last_error_message = str(runtime_status.get("last_error_message") or "")

            tools = get_browser_mcp_tools()
            tools_loaded = True
            tool_count = len(tools)
            msg = "OK"

            extension_connected, probe_error = BrowserMCPClient().probe_extension_connection()
            if probe_error and not is_extension_not_connected_error(probe_error):
                msg = "DEGRADED"

            runtime_status = get_browser_mcp_runtime_status()
            mcp_process_ready = bool(runtime_status.get("mcp_process_ready"))
            session_id = str(runtime_status.get("session_id") or session_id)
            last_success_at = str(runtime_status.get("last_success_at") or last_success_at)
            last_error_type = str(runtime_status.get("last_error_type") or last_error_type)
            last_error_message = str(runtime_status.get("last_error_message") or last_error_message)
        except Exception as e:
            msg = str(e)
    return {
        "enabled": enabled,
        "tools_loaded": tools_loaded,
        "tool_count": tool_count,
        "server_command": os.getenv("BROWSER_MCP_COMMAND", "npx"),
        "server_args": os.getenv("BROWSER_MCP_ARGS", "-y @browsermcp/mcp@latest"),
        "mcp_process_ready": mcp_process_ready,
        "extension_connected": extension_connected,
        "session_id": session_id,
        "last_success_at": last_success_at,
        "last_error_type": last_error_type,
        "last_error_message": last_error_message,
        "probe_error": probe_error,
        "message": msg,
    }


@router.get("/api/browser/channel")
async def browser_channel():
    return {
        "transport": _browser_transport(),
        "legacy_mcp_available": _browser_transport() == "legacy_mcp",
    }


@router.get("/api/browser/channel/status")
async def browser_channel_status():
    transport = _browser_transport()
    if transport == "native_extension":
        status = await get_browser_gateway_manager().status()
        return {"transport": transport, "status": status}
    return {"transport": transport, "status": {"connected": False, "message": "legacy_mcp mode"}}


@router.post("/api/browser/actions/execute")
async def execute_browser_actions(req: BrowserActionsExecuteRequest):
    transport = _browser_transport()
    if transport != "native_extension":
        raise HTTPException(status_code=400, detail="actions execution requires BROWSER_TRANSPORT=native_extension")

    status = await get_browser_gateway_manager().status()
    if not status.get("connected"):
        raise HTTPException(status_code=400, detail="native extension not connected")

    if not req.steps:
        raise HTTPException(status_code=400, detail="steps cannot be empty")

    actions_log: list[dict] = []
    if req.url:
        nav = await _browser_action_or_http_error("navigate", {"url": req.url}, timeout=30.0)
        actions_log.append({"action": "navigate", "result": nav})
        wait_ms = max(0, int(req.wait_after_navigate_ms))
        if wait_ms > 0:
            wait_timeout = max(8.0, (wait_ms / 1000.0) + 5.0)
            wait_res = await _browser_action_or_http_error("wait", {"ms": wait_ms}, timeout=wait_timeout)
            actions_log.append({"action": "wait", "result": wait_res})

    ok = True
    timeout = max(5, int(req.timeout_seconds))
    for i, step in enumerate(req.steps):
        action = str(step.action or "").strip()
        payload = step.payload if isinstance(step.payload, dict) else {}
        res = await get_browser_gateway_manager().send_command(
            action=action,
            payload=payload,
            timeout=timeout,
        )
        actions_log.append({"index": i, "action": action, "result": res})
        if res.get("type") == "error":
            ok = False
            if req.stop_on_error:
                break

    return {
        "ok": ok,
        "actions_log": actions_log,
    }


@router.post("/api/browser/jobs/alpha-bi/snapshot")
async def run_alpha_bi_snapshot_job(req: AlphaBiSnapshotRequest):
    """
    Alpha BI 页面 snapshot：navigate（可选）→ wait → snapshot。
    用于提取表名清单、Tab 位置等，供 extract_alpha_bi_tables 脚本调用。
    """
    from api.alpha_bi_problem_locator_download_job import DEFAULT_ALPHA_BI_URL

    transport = _browser_transport()
    if transport != "native_extension":
        raise HTTPException(
            status_code=400,
            detail="alpha-bi snapshot job requires BROWSER_TRANSPORT=native_extension",
        )
    status = await get_browser_gateway_manager().status()
    if not status.get("connected"):
        raise HTTPException(status_code=400, detail="native extension not connected")

    target_url = req.url or DEFAULT_ALPHA_BI_URL
    wait_ms = max(0, int(req.wait_after_navigate_ms))
    mode = str(req.mode or "full").strip() or "full"
    manager = get_browser_gateway_manager()
    actions_log: list[dict] = []

    nav = await _browser_action_or_http_error("navigate", {"url": target_url}, timeout=30.0)
    actions_log.append({"action": "navigate", "result": nav})
    if wait_ms > 0:
        wait_timeout = max(10.0, (wait_ms / 1000.0) + 8.0)
        wait_res = await _browser_action_or_http_error("wait", {"ms": wait_ms}, timeout=wait_timeout)
        actions_log.append({"action": "wait", "result": wait_res})

    snap_res = await manager.send_command(
        action="snapshot",
        payload={"mode": mode},
        timeout=25.0,
    )
    actions_log.append({"action": "snapshot", "result": snap_res})

    text = ""
    elements: list[dict] = []
    if snap_res.get("type") != "error":
        text, elements = _extract_snapshot_text_and_elements(snap_res)

    return {
        "ok": snap_res.get("type") != "error",
        "snapshot_text": text,
        "snapshot_elements": elements,
        "actions_log": actions_log,
    }


@router.post("/api/browser/jobs/alpha-bi/locate-table")
async def run_alpha_bi_locate_table_job(req: AlphaBiLocateTableRequest):
    """
    locate-table：navigate（可选）→ snapshot → 校验 table_keyword 是否出现在 snapshot.text。
    返回 ok, found, block_hint, actions_log。
    """
    from api.alpha_bi_problem_locator_download_job import DEFAULT_ALPHA_BI_URL

    transport = _browser_transport()
    if transport != "native_extension":
        raise HTTPException(
            status_code=400,
            detail="locate-table job requires BROWSER_TRANSPORT=native_extension",
        )
    status = await get_browser_gateway_manager().status()
    if not status.get("connected"):
        raise HTTPException(status_code=400, detail="native extension not connected")

    target_url = req.url or DEFAULT_ALPHA_BI_URL
    wait_ms = max(0, int(req.wait_after_navigate_ms))
    keyword = str(req.table_keyword or "").strip()
    if not keyword:
        raise HTTPException(status_code=400, detail="table_keyword is required")

    manager = get_browser_gateway_manager()
    actions_log: list[dict] = []

    nav = await _browser_action_or_http_error("navigate", {"url": target_url}, timeout=30.0)
    actions_log.append({"action": "navigate", "result": nav})
    if wait_ms > 0:
        wait_timeout = max(10.0, (wait_ms / 1000.0) + 8.0)
        wait_res = await _browser_action_or_http_error("wait", {"ms": wait_ms}, timeout=wait_timeout)
        actions_log.append({"action": "wait", "result": wait_res})

    snap_res = await manager.send_command(
        action="snapshot",
        payload={"mode": "full"},
        timeout=25.0,
    )
    actions_log.append({"action": "snapshot", "result": snap_res})

    found = False
    block_hint: str | None = None
    if snap_res.get("type") != "error":
        text, _ = _extract_snapshot_text_and_elements(snap_res)
        found = keyword in text
        if found:
            kw_pos = text.find(keyword)
            blocks = ("一、核心指标", "二、问题定位", "三、归因分析V1", "归因分析V2", "毛利趋势")
            for block in reversed(blocks):
                pos = text.find(block)
                if 0 <= pos <= kw_pos:
                    block_hint = block
                    break
            # 精确定位表头组件，避免 text 包含匹配命中 #app 根节点导致“看似成功但未滚动”
            m = re.search(r"\[([^\]]+)\]", keyword)
            simple_name = m.group(1) if m else keyword
            locators = [
                {"selector": "div.comp-header-component", "text": keyword, "exact": True},
                {"selector": "div.comp-header-component", "text": simple_name, "exact": False},
                {"selector": "div,span,h1,h2,h3,h4", "text": keyword, "exact": True},
            ]
            for loc in locators:
                scroll_res = await manager.send_command(
                    "scroll_into_view",
                    {"locator": loc, "block": "start"},
                    12.0,
                )
                ok_scroll = scroll_res.get("type") != "error" and (scroll_res.get("payload") or {}).get("ok")
                if ok_scroll:
                    actions_log.append({"action": "scroll_to_table", "locator": loc, "result": "ok"})
                    break

    return {
        "ok": snap_res.get("type") != "error",
        "found": found,
        "block_hint": block_hint,
        "actions_log": actions_log,
    }


@router.post("/api/browser/jobs/alpha-bi/date-filter")
async def run_alpha_bi_date_filter_job(req: AlphaBiDateFilterJobRequest):
    transport = _browser_transport()
    if transport != "native_extension":
        raise HTTPException(status_code=400, detail="date-filter job requires BROWSER_TRANSPORT=native_extension")

    status = await get_browser_gateway_manager().status()
    if not status.get("connected"):
        raise HTTPException(status_code=400, detail="native extension not connected")

    actions_log: list[dict] = []
    if req.url:
        nav = await _browser_action_or_http_error("navigate", {"url": req.url}, timeout=30.0)
        actions_log.append({"action": "navigate", "result": nav})
        wait_ms = max(0, int(req.wait_after_navigate_ms))
        wait_timeout = max(10.0, (wait_ms / 1000.0) + 8.0)
        wait_res = await _browser_action_or_http_error("wait", {"ms": wait_ms}, timeout=wait_timeout)
        actions_log.append({"action": "wait", "result": wait_res})

    expected = {
        "current_start": req.current_start,
        "current_end": req.current_end,
        "compare_start": req.compare_start,
        "compare_end": req.compare_end,
    }

    # 优先走页面专用原子动作；若扩展未热更新导致动作不可用，自动降级为通用 run_plan。
    direct_res = await get_browser_gateway_manager().send_command(
        action="alpha_bi_set_date_ranges",
        payload={
            "current_start": req.current_start,
            "current_end": req.current_end,
            "compare_start": req.compare_start,
            "compare_end": req.compare_end,
        },
        timeout=55.0,
    )
    actions_log.append({"action": "alpha_bi_set_date_ranges", "result": direct_res})

    direct_payload = direct_res.get("payload") if isinstance(direct_res, dict) else {}
    if not isinstance(direct_payload, dict):
        direct_payload = {}

    dates_after = {}
    verified = False
    if direct_res.get("type") != "error" and bool(direct_payload.get("ok")):
        # 先验证扩展返回的输入值（来自页面 DOM），避免 snapshot 文本抽取不到日期时误判失败。
        after_values = [str(x or "") for x in (direct_payload.get("after") or [])]
        by_after = _extract_expected_from_after_values(after_values, expected)
        if by_after:
            dates_after = by_after
            verified = True

        post_direct_snapshot = await get_browser_gateway_manager().send_command(
            action="snapshot",
            payload={"mode": "summary"},
            timeout=20.0,
        )
        actions_log.append({"action": "snapshot_after_direct", "result": post_direct_snapshot})
        if post_direct_snapshot.get("type") != "error":
            snap = ((post_direct_snapshot.get("payload") or {}).get("snapshot") or {})
            by_text = _extract_alpha_bi_date_ranges(str(snap.get("text") or ""))
            if by_text:
                dates_after = by_text
                verified = all(dates_after.get(k) == v for k, v in expected.items())

    if not verified:
        # 先做一次 full snapshot，尽可能让扩展锁定包含真实控件的 frame。
        pre_fb_snapshot = await get_browser_gateway_manager().send_command(
            action="snapshot",
            payload={"mode": "full"},
            timeout=25.0,
        )
        actions_log.append({"action": "snapshot_before_fallback", "result": pre_fb_snapshot})

        fb_start_refs: list[str] = []
        if pre_fb_snapshot.get("type") != "error":
            snap = ((pre_fb_snapshot.get("payload") or {}).get("snapshot") or {})
            fb_elements = snap.get("elements") or []
            for item in fb_elements:
                if not isinstance(item, dict):
                    continue
                label = str(item.get("label") or "")
                ref = str(item.get("ref") or "")
                tag = str(item.get("tag") or "")
                if tag == "input" and ref and ("开始日期" in label or re.match(r"^\d{4}-\d{2}-\d{2}$", label)):
                    fb_start_refs.append(ref)

        # 优先用选择框流程：点击输入框打开日期选择器，再点击日历单元格，而非直接改文本
        fallback_plans = [
            {
                "name": "label-text-open",
                "steps": [
                    {"action": "click", "payload": {"text": "当期"}},
                    {"action": "wait", "payload": {"ms": 350}},
                    {"action": "click", "payload": {"selector": ".ant-picker-header-prev-btn"}},
                    {"action": "wait", "payload": {"ms": 150}},
                    {"action": "click", "payload": {"selector": f"[title='{req.current_start}']"}},
                    {"action": "wait", "payload": {"ms": 150}},
                    {"action": "click", "payload": {"selector": f"[title='{req.current_end}']"}},
                    {"action": "wait", "payload": {"ms": 350}},
                    {"action": "click", "payload": {"text": "对比期"}},
                    {"action": "wait", "payload": {"ms": 350}},
                    {"action": "click", "payload": {"selector": f"[title='{req.compare_start}']"}},
                    {"action": "wait", "payload": {"ms": 150}},
                    {"action": "click", "payload": {"selector": f"[title='{req.compare_end}']"}},
                    {"action": "wait", "payload": {"ms": 350}},
                    {"action": "snapshot", "payload": {"mode": "summary"}},
                ],
            },
            {
                "name": "ant-picker-input",
                "steps": [
                    {"action": "click", "payload": {"selector": ".ant-picker-input input"}},
                    {"action": "wait", "payload": {"ms": 350}},
                    {"action": "click", "payload": {"selector": ".ant-picker-header-prev-btn"}},
                    {"action": "wait", "payload": {"ms": 150}},
                    {"action": "click", "payload": {"selector": f"[title='{req.current_start}']"}},
                    {"action": "wait", "payload": {"ms": 150}},
                    {"action": "click", "payload": {"selector": f"[title='{req.current_end}']"}},
                    {"action": "wait", "payload": {"ms": 350}},
                    {"action": "click", "payload": {"selector": ".ant-picker-range:nth-of-type(2) .ant-picker-input input"}},
                    {"action": "wait", "payload": {"ms": 350}},
                    {"action": "click", "payload": {"selector": f"[title='{req.compare_start}']"}},
                    {"action": "wait", "payload": {"ms": 150}},
                    {"action": "click", "payload": {"selector": f"[title='{req.compare_end}']"}},
                    {"action": "wait", "payload": {"ms": 350}},
                    {"action": "snapshot", "payload": {"mode": "summary"}},
                ],
            },
            {
                "name": "by_snapshot_refs",
                "steps": (
                    [
                        {"action": "click", "payload": {"ref": fb_start_refs[0]}},
                        {"action": "wait", "payload": {"ms": 180}},
                        {"action": "click", "payload": {"selector": f"[title='{req.current_start}']"}},
                        {"action": "wait", "payload": {"ms": 120}},
                        {"action": "click", "payload": {"selector": f"[title='{req.current_end}']"}},
                        {"action": "wait", "payload": {"ms": 260}},
                        {"action": "click", "payload": {"ref": fb_start_refs[1] if len(fb_start_refs) > 1 else fb_start_refs[0]}},
                        {"action": "wait", "payload": {"ms": 180}},
                        {"action": "click", "payload": {"selector": f"[title='{req.compare_start}']"}},
                        {"action": "wait", "payload": {"ms": 120}},
                        {"action": "click", "payload": {"selector": f"[title='{req.compare_end}']"}},
                        {"action": "wait", "payload": {"ms": 320}},
                        {"action": "snapshot", "payload": {"mode": "summary"}},
                    ]
                    if fb_start_refs
                    else []
                ),
            },
            {
                "name": "type_calendar_inputs_last_resort",
                "steps": [
                    {"action": "type", "payload": {"locator": {"selector": "input.ant-calendar-range-picker-input", "index": 0}, "text": req.current_start, "clear": True}},
                    {"action": "type", "payload": {"locator": {"selector": "input.ant-calendar-range-picker-input", "index": 1}, "text": req.current_end, "clear": True}},
                    {"action": "type", "payload": {"locator": {"selector": "input.ant-calendar-range-picker-input", "index": 2}, "text": req.compare_start, "clear": True}},
                    {"action": "type", "payload": {"locator": {"selector": "input.ant-calendar-range-picker-input", "index": 3}, "text": req.compare_end, "clear": True}},
                    {"action": "wait", "payload": {"ms": 200}},
                    {"action": "snapshot", "payload": {"mode": "summary"}},
                ],
            },
        ]

        manager = get_browser_gateway_manager()
        for plan in fallback_plans:
            if not plan["steps"]:
                continue
            step_logs: list[dict] = []
            plan_ok = True
            for idx, step in enumerate(plan["steps"]):
                action = str(step.get("action") or "").strip()
                payload = step.get("payload") if isinstance(step.get("payload"), dict) else {}
                if not action:
                    continue
                step_timeout = 20.0 if action in {"snapshot", "wait_for"} else 12.0
                step_res = await manager.send_command(
                    action=action,
                    payload=payload,
                    timeout=step_timeout,
                )
                step_logs.append({"index": idx, "action": action, "payload": payload, "result": step_res})
                if step_res.get("type") == "error":
                    plan_ok = False
                    break

            actions_log.append(
                {
                    "action": "atomic_fallback_plan",
                    "strategy": plan["name"],
                    "result": {"ok": plan_ok, "steps": step_logs},
                }
            )
            if not plan_ok:
                continue

            # v2 snapshot 文本经常不包含输入 value；先尝试文本提取，再做输入框 value 断言。
            for step in reversed(step_logs):
                payload = step.get("result", {}).get("payload") if isinstance(step.get("result"), dict) else {}
                snap = payload.get("snapshot") if isinstance(payload, dict) else None
                if isinstance(snap, dict):
                    dates_after = _extract_alpha_bi_date_ranges(str(snap.get("text") or ""))
                    break

            if bool(dates_after) and all(dates_after.get(k) == v for k, v in expected.items()):
                verified = True
                break

            assert_targets = [
                ("current_start", {"selector": "input.ant-calendar-range-picker-input", "index": 0}),
                ("current_end", {"selector": "input.ant-calendar-range-picker-input", "index": 1}),
                ("compare_start", {"selector": "input.ant-calendar-range-picker-input", "index": 2}),
                ("compare_end", {"selector": "input.ant-calendar-range-picker-input", "index": 3}),
            ]
            assert_values: dict[str, str] = {}
            assert_ok = True
            for key, locator in assert_targets:
                ar = await manager.send_command(
                    action="assert",
                    payload={"locator": locator, "expect_value": expected[key]},
                    timeout=10.0,
                )
                actions_log.append(
                    {
                        "action": "assert_date_input",
                        "strategy": plan["name"],
                        "key": key,
                        "locator": locator,
                        "result": ar,
                    }
                )
                if ar.get("type") == "error":
                    assert_ok = False
                    break
                actual = ((ar.get("payload") or {}).get("actual") or {})
                assert_values[key] = str(actual.get("value") or "")
            if assert_ok and all(assert_values.get(k) == v for k, v in expected.items()):
                dates_after = assert_values
                verified = True
                break

    return {
        "ok": verified,
        "expected": expected,
        "dates_after": dates_after,
        "message": "verified" if verified else str(direct_payload.get("message") or "date values not fully matched"),
        "actions_log": actions_log,
    }


@router.post("/api/browser/jobs/alpha-bi/select-dropdown")
async def run_alpha_bi_select_dropdown_job(req: AlphaBiSelectDropdownRequest):
    """
    单选下拉选择：点击展开 → get_dropdown_options → 匹配并点击目标选项。
    """
    transport = _browser_transport()
    if transport != "native_extension":
        raise HTTPException(status_code=400, detail="select-dropdown job requires BROWSER_TRANSPORT=native_extension")

    status = await get_browser_gateway_manager().status()
    if not status.get("connected"):
        raise HTTPException(status_code=400, detail="native extension not connected")

    manager = get_browser_gateway_manager()
    actions_log: list[dict] = []

    if req.url:
        nav = await _browser_action_or_http_error("navigate", {"url": req.url}, timeout=30.0)
        actions_log.append({"action": "navigate", "result": nav})
        wait_ms = max(0, int(req.wait_after_navigate_ms))
        wait_timeout = max(10.0, (wait_ms / 1000.0) + 8.0)
        wait_res = await _browser_action_or_http_error("wait", {"ms": wait_ms}, timeout=wait_timeout)
        actions_log.append({"action": "wait", "result": wait_res})

    click_payload = {"locator": req.trigger_locator}
    if req.skip_click:
        click_res = {"type": "result", "payload": {"ok": True, "message": "skipped"}}
    else:
        # 优先 click_trusted（Debugger API 模拟真实点击），更易触发 Ant Design 下拉
        click_res = await manager.send_command("click_trusted", click_payload, timeout=20.0)
        if click_res.get("type") == "error":
            click_res = await manager.send_command("click", click_payload, timeout=15.0)
        if click_res.get("type") == "error":
            fallback_locators = [
                {"selector": ".ant-select", "within": {"text": "二、问题定位"}, "index": 0},
                {"selector": ".ant-select", "within": {"text": "一、核心指标"}, "index": 0},
                {"selector": ".ant-select-selector", "index": 0},
                {"selector": ".ant-select", "index": 0},
            ]
            for loc in fallback_locators:
                if loc == req.trigger_locator:
                    continue
                click_res = await manager.send_command("click", {"locator": loc}, timeout=15.0)
                actions_log.append({"action": "click_trigger_fallback", "locator": loc, "result": click_res})
                if click_res.get("type") != "error":
                    break
    actions_log.append({"action": "click_trigger", "result": click_res})
    if click_res.get("type") == "error":
        return {
            "ok": False,
            "error": "click_trigger_failed",
            "message": click_res.get("message", "failed to click dropdown trigger"),
            "actions_log": actions_log,
        }

    wait_after_click = await manager.send_command("wait", {"ms": 2500}, timeout=10.0)
    actions_log.append({"action": "wait_after_click", "result": wait_after_click})

    opts_res = await manager.send_command("get_dropdown_options", {"target_text": req.target_value}, timeout=12.0)
    actions_log.append({"action": "get_dropdown_options", "result": opts_res})
    if opts_res.get("type") == "error":
        for retry in range(2):
            await manager.send_command("wait", {"ms": 500}, timeout=5.0)
            opts_res = await manager.send_command("get_dropdown_options", {"target_text": req.target_value}, timeout=12.0)
            actions_log.append({"action": "get_dropdown_options_retry", "retry": retry + 1, "result": opts_res})
            if opts_res.get("type") != "error":
                break
    if opts_res.get("type") == "error":
        # 兜底 A：snapshot 后从文本校验选项是否存在，再 locate+click（用户反馈手动展开时 snapshot 可获取）
        await manager.send_command("wait", {"ms": 300}, timeout=5.0)
        snap_res = await manager.send_command("snapshot", {"mode": "full"}, timeout=20.0)
        actions_log.append({"action": "fallback_snapshot", "result": snap_res})
        snap_ok = snap_res.get("type") != "error"
        snap_text = ""
        if snap_ok:
            snap_pl = snap_res.get("payload") or {}
            snap_obj = snap_pl.get("snapshot") if isinstance(snap_pl.get("snapshot"), dict) else snap_pl
            snap_text = str(snap_obj.get("text") or "")
        if snap_ok and req.target_value in snap_text:
            within = (req.trigger_locator or {}).get("within") or {}
            fallback_locators = [{"text": req.target_value, "within": within}] if within else []
            fallback_locators.append({"text": req.target_value})
            for fallback_locator in fallback_locators:
                loc_res = await manager.send_command("locate", {"locator": fallback_locator}, timeout=12.0)
                actions_log.append({"action": "fallback_locate_option", "locator": fallback_locator, "result": loc_res})
                if loc_res.get("type") != "error":
                    pl = loc_res.get("payload") or {}
                    if pl.get("ok"):
                        handle = (pl.get("element") or {}).get("handle")
                        if handle:
                            click_opt_res = await manager.send_command("click", {"locator": {"handle": handle}}, timeout=15.0)
                            actions_log.append({"action": "fallback_click_option", "result": click_opt_res})
                            if click_opt_res.get("type") != "error":
                                return {"ok": True, "matched_option": {"text": req.target_value, "handle": handle}, "actions_log": actions_log}
        pl = opts_res.get("payload") or {}
        return {
            "ok": False,
            "error": "get_dropdown_options_failed",
            "message": opts_res.get("message", "failed to get dropdown options"),
            "actions_log": actions_log,
            "debug_counts": pl.get("_debug_counts"),
        }

    pl = opts_res.get("payload") or {}
    options = pl.get("options") if isinstance(pl.get("options"), list) else []
    matched = _match_dropdown_option(options, req.target_value)
    if not matched:
        return {
            "ok": False,
            "error": "option_not_found",
            "target_value": req.target_value,
            "options": options,
            "actions_log": actions_log,
        }

    handle = matched.get("handle")
    if not handle:
        return {
            "ok": False,
            "error": "option_no_handle",
            "matched_option": matched,
            "actions_log": actions_log,
        }

    click_opt_res = await manager.send_command(
        "click",
        {"locator": {"handle": handle}},
        timeout=15.0,
    )
    actions_log.append({"action": "click_option", "result": click_opt_res})
    if click_opt_res.get("type") == "error":
        return {
            "ok": False,
            "error": "click_option_failed",
            "matched_option": matched,
            "message": click_opt_res.get("message", "failed to click option"),
            "actions_log": actions_log,
        }

    wait_200 = await manager.send_command("wait", {"ms": 200}, timeout=8.0)
    actions_log.append({"action": "wait_after_option", "result": wait_200})
    snap_res = await manager.send_command("snapshot", {}, timeout=15.0)
    actions_log.append({"action": "snapshot_after", "result": snap_res})

    return {
        "ok": True,
        "matched_option": matched,
        "actions_log": actions_log,
    }


@router.post("/api/browser/jobs/alpha-bi/select-multi-dropdown")
async def run_alpha_bi_select_multi_dropdown_job(req: AlphaBiSelectMultiDropdownRequest):
    """
    多选下拉：点击展开 → 逐项 get_dropdown_options + click → 完成。
    若页面存在大区、城市等多选字段时使用。
    """
    transport = _browser_transport()
    if transport != "native_extension":
        raise HTTPException(status_code=400, detail="select-multi-dropdown requires BROWSER_TRANSPORT=native_extension")
    status = await get_browser_gateway_manager().status()
    if not status.get("connected"):
        raise HTTPException(status_code=400, detail="native extension not connected")

    manager = get_browser_gateway_manager()
    actions_log: list[dict] = []

    if req.url:
        nav = await _browser_action_or_http_error("navigate", {"url": req.url}, timeout=30.0)
        actions_log.append({"action": "navigate", "result": nav})
        wait_ms = max(0, int(req.wait_after_navigate_ms))
        wait_timeout = max(10.0, (wait_ms / 1000.0) + 8.0)
        wait_res = await _browser_action_or_http_error("wait", {"ms": wait_ms}, timeout=wait_timeout)
        actions_log.append({"action": "wait", "result": wait_res})

    click_res = await manager.send_command("click", {"locator": req.trigger_locator}, timeout=15.0)
    actions_log.append({"action": "click_trigger", "result": click_res})
    if click_res.get("type") == "error":
        return {"ok": False, "error": "click_trigger_failed", "actions_log": actions_log}

    await manager.send_command("wait", {"ms": 800}, timeout=5.0)
    matched_count = 0
    for val in (req.target_values or []):
        opts_res = await manager.send_command("get_dropdown_options", {"target_text": val}, timeout=12.0)
        actions_log.append({"action": "get_dropdown_options", "target": val, "result": opts_res})
        if opts_res.get("type") == "error":
            continue
        pl = opts_res.get("payload") or {}
        options = pl.get("options") or []
        matched = _match_dropdown_option(options, val)
        if matched and matched.get("handle"):
            click_opt = await manager.send_command("click", {"locator": {"handle": matched["handle"]}}, timeout=15.0)
            actions_log.append({"action": "click_option", "target": val, "result": click_opt})
            if click_opt.get("type") != "error":
                matched_count += 1
            await manager.send_command("wait", {"ms": 200}, timeout=5.0)

    return {
        "ok": matched_count > 0,
        "matched_count": matched_count,
        "target_count": len(req.target_values or []),
        "actions_log": actions_log,
    }


@router.post("/api/browser/jobs/alpha-bi/select-checkbox-group")
async def run_alpha_bi_select_checkbox_group_job(req: AlphaBiSelectCheckboxGroupRequest):
    """
    复选组：在 within_text 区块内，按 option_texts 逐项 locate + click 勾选。
    适用于 ant-checkbox-group（采一/采二/采三等）。
    """
    from api.alpha_bi_problem_locator_download_job import DEFAULT_ALPHA_BI_URL

    transport = _browser_transport()
    if transport != "native_extension":
        raise HTTPException(status_code=400, detail="select-checkbox-group requires BROWSER_TRANSPORT=native_extension")
    status = await get_browser_gateway_manager().status()
    if not status.get("connected"):
        raise HTTPException(status_code=400, detail="native extension not connected")

    manager = get_browser_gateway_manager()
    actions_log: list[dict] = []
    target_url = req.url or DEFAULT_ALPHA_BI_URL
    within_text = str(req.within_text or "").strip()
    option_texts = [str(t).strip() for t in (req.option_texts or []) if str(t).strip()]

    if not within_text:
        raise HTTPException(status_code=400, detail="within_text is required")
    if not option_texts:
        return {"ok": True, "clicked_count": 0, "actions_log": actions_log}

    nav = await _browser_action_or_http_error("navigate", {"url": target_url}, timeout=30.0)
    actions_log.append({"action": "navigate", "result": nav})
    wait_ms = max(0, int(req.wait_after_navigate_ms))
    if wait_ms > 0:
        wait_timeout = max(10.0, (wait_ms / 1000.0) + 8.0)
        wait_res = await _browser_action_or_http_error("wait", {"ms": wait_ms}, timeout=wait_timeout)
        actions_log.append({"action": "wait", "result": wait_res})

    clicked_count = 0
    for opt in option_texts:
        locator = {"text": opt, "within": {"text": within_text}}
        loc_res = await manager.send_command("locate", {"locator": locator}, timeout=12.0)
        actions_log.append({"action": "locate", "option": opt, "result": loc_res})
        if loc_res.get("type") == "error":
            continue
        pl = loc_res.get("payload") or {}
        if not pl.get("ok"):
            continue
        el = pl.get("element") or {}
        handle = el.get("handle")
        if not handle:
            continue
        click_res = await manager.send_command("click", {"locator": {"handle": handle}}, timeout=15.0)
        actions_log.append({"action": "click", "option": opt, "result": click_res})
        if click_res.get("type") != "error":
            clicked_count += 1
        await manager.send_command("wait", {"ms": 200}, timeout=5.0)

    return {
        "ok": clicked_count > 0,
        "clicked_count": clicked_count,
        "target_count": len(option_texts),
        "actions_log": actions_log,
    }


@router.post("/api/browser/jobs/alpha-bi/full-filter-query")
async def run_alpha_bi_full_filter_query_job(req: AlphaBiFullFilterQueryRequest):
    """
    完整路径：定位表 → 填日期 → 填品类组 → 填聚合维度 → 点查询。
    针对 二、问题定位 区块，至少一张表走通。
    """
    from api.alpha_bi_problem_locator_download_job import DEFAULT_ALPHA_BI_URL
    from datetime import datetime

    transport = _browser_transport()
    if transport != "native_extension":
        raise HTTPException(status_code=400, detail="full-filter-query requires BROWSER_TRANSPORT=native_extension")
    status = await get_browser_gateway_manager().status()
    if not status.get("connected"):
        raise HTTPException(status_code=400, detail="native extension not connected")

    target_url = req.url or DEFAULT_ALPHA_BI_URL
    year = datetime.now().year
    current_start, current_end = _core_month_range_ymd(year, 1)
    compare_start, compare_end = _core_month_range_ymd(year, 2)
    wait_ms = max(8000, int(req.wait_after_navigate_ms))
    actions_log: list[dict] = []

    # 1) 日期筛选
    df_req = AlphaBiDateFilterJobRequest(
        url=target_url,
        current_start=current_start,
        current_end=current_end,
        compare_start=compare_start,
        compare_end=compare_end,
        wait_after_navigate_ms=wait_ms,
    )
    df_res = await run_alpha_bi_date_filter_job(df_req)
    actions_log.append({"stage": "date_filter", "result": df_res})
    if not df_res.get("ok"):
        return {"ok": False, "failure_stage": "date_filter", "actions_log": actions_log}

    await get_browser_gateway_manager().send_command("wait", {"ms": 500}, timeout=5.0)

    # 2) 品类组
    cat_req = AlphaBiSelectDropdownRequest(
        url=None,
        trigger_locator={"selector": ".ant-select", "within": {"text": "二、问题定位"}, "index": 0},
        target_value=req.category_value,
    )
    cat_res = await run_alpha_bi_select_dropdown_job(cat_req)
    actions_log.append({"stage": "select_category", "result": cat_res})
    if not cat_res.get("ok"):
        return {"ok": False, "failure_stage": "select_category", "actions_log": actions_log}

    await get_browser_gateway_manager().send_command("wait", {"ms": 500}, timeout=5.0)

    # 3) 聚合维度
    dim_req = AlphaBiSelectDropdownRequest(
        url=None,
        trigger_locator={"selector": ".ant-select", "within": {"text": "二、问题定位"}, "index": 1},
        target_value=req.dimension_value,
    )
    dim_res = await run_alpha_bi_select_dropdown_job(dim_req)
    actions_log.append({"stage": "select_dimension", "result": dim_res})
    if not dim_res.get("ok"):
        return {"ok": False, "failure_stage": "select_dimension", "actions_log": actions_log}

    await get_browser_gateway_manager().send_command("wait", {"ms": 500}, timeout=5.0)

    # 4) 点击查询（区块内）
    manager = get_browser_gateway_manager()
    query_locator = {"text": "查询", "within": {"text": "二、问题定位"}}
    loc_res = await manager.send_command("locate", {"locator": query_locator}, timeout=12.0)
    actions_log.append({"stage": "locate_query", "result": loc_res})
    if loc_res.get("type") == "error":
        # 兜底：用 find_query_ref
        snap_res = await manager.send_command("snapshot", {"mode": "full"}, timeout=20.0)
        _, elements = _extract_snapshot_text_and_elements(snap_res)
        query_ref = _find_query_ref(elements)
        if query_ref:
            click_res = await manager.send_command(
                "click",
                {"locator": {"selector": f'[data-myclaw-ref="{query_ref}"]'}},
                timeout=15.0,
            )
        else:
            click_res = await manager.send_command("click", {"locator": query_locator}, timeout=15.0)
    else:
        pl = loc_res.get("payload") or {}
        handle = (pl.get("element") or {}).get("handle") if pl.get("ok") else None
        if handle:
            click_res = await manager.send_command("click", {"locator": {"handle": handle}}, timeout=15.0)
        else:
            click_res = await manager.send_command("click", {"locator": query_locator}, timeout=15.0)
    actions_log.append({"stage": "click_query", "result": click_res})
    if click_res.get("type") == "error":
        return {"ok": False, "failure_stage": "click_query", "actions_log": actions_log}

    wait_after = max(1500, int(req.post_query_wait_ms))
    await manager.send_command("wait", {"ms": wait_after}, timeout=max(10.0, wait_after / 1000.0 + 8.0))

    return {
        "ok": True,
        "message": "full filter query completed",
        "actions_log": actions_log,
    }


@router.post("/api/browser/jobs/alpha-bi/click-tab")
async def run_alpha_bi_click_tab_job(req: AlphaBiClickTabRequest):
    """
    Tab 点击：navigate（可选）→ locate tab_text（可选 within）→ click。
    """
    from api.alpha_bi_problem_locator_download_job import DEFAULT_ALPHA_BI_URL

    transport = _browser_transport()
    if transport != "native_extension":
        raise HTTPException(status_code=400, detail="click-tab requires BROWSER_TRANSPORT=native_extension")
    status = await get_browser_gateway_manager().status()
    if not status.get("connected"):
        raise HTTPException(status_code=400, detail="native extension not connected")

    tab_text = str(req.tab_text or "").strip()
    if not tab_text:
        raise HTTPException(status_code=400, detail="tab_text is required")

    manager = get_browser_gateway_manager()
    actions_log: list[dict] = []
    target_url = req.url or DEFAULT_ALPHA_BI_URL

    if req.url:
        nav = await _browser_action_or_http_error("navigate", {"url": target_url}, timeout=30.0)
        actions_log.append({"action": "navigate", "result": nav})
        wait_ms = max(0, int(req.wait_after_navigate_ms))
        if wait_ms > 0:
            wait_timeout = max(10.0, (wait_ms / 1000.0) + 8.0)
            wait_res = await _browser_action_or_http_error("wait", {"ms": wait_ms}, timeout=wait_timeout)
            actions_log.append({"action": "wait", "result": wait_res})

    locator = {"text": tab_text}
    if req.within_text:
        locator["within"] = {"text": req.within_text}

    loc_res = await manager.send_command("locate", {"locator": locator}, timeout=12.0)
    actions_log.append({"action": "locate", "result": loc_res})
    if loc_res.get("type") == "error":
        return {"ok": False, "error": "tab_not_found", "tab_text": tab_text, "actions_log": actions_log}
    pl = loc_res.get("payload") or {}
    if not pl.get("ok"):
        return {"ok": False, "error": "tab_not_found", "tab_text": tab_text, "actions_log": actions_log}
    handle = (pl.get("element") or {}).get("handle")
    if not handle:
        return {"ok": False, "error": "tab_no_handle", "tab_text": tab_text, "actions_log": actions_log}

    click_res = await manager.send_command("click", {"locator": {"handle": handle}}, timeout=15.0)
    actions_log.append({"action": "click", "result": click_res})
    if click_res.get("type") == "error":
        return {"ok": False, "error": "click_failed", "tab_text": tab_text, "actions_log": actions_log}

    return {"ok": True, "tab_text": tab_text, "actions_log": actions_log}


@router.post("/api/browser/jobs/alpha-bi/core-metrics-date-query")
async def run_alpha_bi_core_metrics_date_query_job(req: AlphaBiCoreMetricsQueryRequest):
    transport = _browser_transport()
    if transport != "native_extension":
        raise HTTPException(status_code=400, detail="core-metrics-date-query job requires BROWSER_TRANSPORT=native_extension")

    status = await get_browser_gateway_manager().status()
    if not status.get("connected"):
        raise HTTPException(status_code=400, detail="native extension not connected")

    target_url = req.url or (
        "https://alpha-bi.ddxq.mobi/report?"
        "pathIds=279b4f5efc6d446886b3662773c25b3c,cc4baf96c7344900918887be30cf56de"
        "&dashboardId=d127af3f0bb3457287f5093bdea78846"
        "&externalSpaceId=fccdafe6147b461d94425137c51ffe2e"
        "&appId=36620ff9365540a2b6a36531a5dcef6b"
        "&iframeType=app&orgId=1&spaceId=fccdafe6147b461d94425137c51ffe2e"
    )
    year = int(req.year or datetime.now().year)
    current_start, current_end = _month_range_ymd(year, 1)
    compare_start, compare_end = _month_range_ymd(year, 2)
    expected = {
        "current_start": current_start,
        "current_end": current_end,
        "compare_start": compare_start,
        "compare_end": compare_end,
    }

    max_attempts = max(1, min(5, int(req.max_attempts or 3)))
    base_wait = max(800, int(req.post_query_wait_ms or 1800))
    attempts: list[dict] = []
    actions_log: list[dict] = []
    failure_stage = ""

    for i in range(max_attempts):
        attempt_no = i + 1
        attempt_log: dict = {"attempt": attempt_no}
        # 自修复策略：逐轮增加查询后等待；第三轮开始重新导航。
        query_wait_ms = base_wait + i * 1200
        if i >= 2:
            nav = await _browser_action_or_http_error("navigate", {"url": target_url}, timeout=30.0)
            actions_log.append({"action": "navigate_reopen", "attempt": attempt_no, "result": nav})
            settle_ms = max(1500, int(req.wait_after_navigate_ms))
            wait_timeout = max(10.0, settle_ms / 1000.0 + 8.0)
            wait_res = await _browser_action_or_http_error("wait", {"ms": settle_ms}, timeout=wait_timeout)
            actions_log.append({"action": "wait_reopen", "attempt": attempt_no, "result": wait_res})

        # 1) 先做日期筛选动作（复用现有 date-filter job，保证“设置+校验”稳定）。
        df_req = AlphaBiDateFilterJobRequest(
            url=target_url if i == 0 else None,
            current_start=current_start,
            current_end=current_end,
            compare_start=compare_start,
            compare_end=compare_end,
            wait_after_navigate_ms=max(1200, int(req.wait_after_navigate_ms)),
        )
        df_res = await run_alpha_bi_date_filter_job(df_req)
        actions_log.append({"action": "core_metrics_date_filter", "attempt": attempt_no, "result": df_res})
        attempt_log["date_filter_ok"] = bool(df_res.get("ok"))
        attempt_log["dates_after"] = df_res.get("dates_after") if isinstance(df_res, dict) else {}
        if not bool(df_res.get("ok")):
            failure_stage = "set_date_ranges"
            attempts.append(attempt_log)
            continue

        # 2) 定位并点击查询按钮（ref 优先，selector 兜底）。
        snap_before_query = await get_browser_gateway_manager().send_command(
            action="snapshot",
            payload={"mode": "full"},
            timeout=25.0,
        )
        actions_log.append({"action": "snapshot_before_query", "attempt": attempt_no, "result": snap_before_query})
        before_text, before_elements = _extract_snapshot_text_and_elements(snap_before_query)
        before_hash = _text_hash(before_text)
        query_ref = _find_query_ref(before_elements)
        click_ok, click_method, click_res = await _click_query_button(query_ref=query_ref, timeout=20.0)
        actions_log.append(
            {
                "action": "click_query",
                "attempt": attempt_no,
                "query_ref": query_ref,
                "method": click_method,
                "result": click_res,
            }
        )
        attempt_log["query_ref"] = query_ref
        attempt_log["query_click_method"] = click_method
        attempt_log["query_clicked"] = click_ok
        if not click_ok:
            failure_stage = "click_query"
            attempts.append(attempt_log)
            continue

        wait_after_query = await get_browser_gateway_manager().send_command(
            action="wait",
            payload={"ms": query_wait_ms},
            timeout=max(10.0, query_wait_ms / 1000.0 + 8.0),
        )
        actions_log.append({"action": "wait_after_query", "attempt": attempt_no, "result": wait_after_query})

        # 3) 采集证据：查询后 snapshot 文本哈希变化（或明显 loading 信号变化）。
        snap_after_query = await get_browser_gateway_manager().send_command(
            action="snapshot",
            payload={"mode": "summary"},
            timeout=20.0,
        )
        actions_log.append({"action": "snapshot_after_query", "attempt": attempt_no, "result": snap_after_query})
        after_text, _after_elements = _extract_snapshot_text_and_elements(snap_after_query)
        after_hash = _text_hash(after_text)
        loading_signal = ("加载中" in before_text) != ("加载中" in after_text)
        text_changed = before_hash != after_hash
        evidence = {
            "before_text_hash": before_hash,
            "after_text_hash": after_hash,
            "text_changed": text_changed,
            "loading_signal_changed": loading_signal,
            "query_wait_ms": query_wait_ms,
        }
        attempt_log["evidence"] = evidence
        attempts.append(attempt_log)

        if text_changed or loading_signal:
            return {
                "ok": True,
                "message": "verified",
                "expected": expected,
                "actual": df_res.get("dates_after") if isinstance(df_res, dict) else {},
                "query_clicked": True,
                "evidence": evidence,
                "attempts": attempts,
                "failure_stage": "",
                "actions_log": actions_log,
            }

        # 日期正确且查询已点击时，即使 snapshot 文本未明显变化也视为成功（BI 数据可能异步刷新）
        dates_ok = all(
            (df_res.get("dates_after") or {}).get(k) == v for k, v in expected.items()
        )
        if click_ok and dates_ok:
            return {
                "ok": True,
                "message": "verified (dates+query)",
                "expected": expected,
                "actual": df_res.get("dates_after") if isinstance(df_res, dict) else {},
                "query_clicked": True,
                "evidence": evidence,
                "attempts": attempts,
                "failure_stage": "",
                "actions_log": actions_log,
            }

        failure_stage = "verify_evidence"

    return {
        "ok": False,
        "message": "core metrics date query not verified",
        "expected": expected,
        "actual": attempts[-1].get("dates_after", {}) if attempts else {},
        "query_clicked": bool(attempts[-1].get("query_clicked")) if attempts else False,
        "evidence": attempts[-1].get("evidence", {}) if attempts else {},
        "attempts": attempts,
        "failure_stage": failure_stage or "unknown",
        "actions_log": actions_log,
    }


@router.post("/api/browser/jobs/alpha-bi/download")
async def run_alpha_bi_download_job(req: AlphaBiDownloadJobRequest):
    transport = _browser_transport()
    if transport != "native_extension":
        raise HTTPException(status_code=400, detail="download job requires BROWSER_TRANSPORT=native_extension")

    status = await get_browser_gateway_manager().status()
    if not status.get("connected"):
        raise HTTPException(status_code=400, detail="native extension not connected")

    actions_log: list[dict] = []
    if req.url:
        nav = await _browser_action_or_http_error("navigate", {"url": req.url}, timeout=30.0)
        actions_log.append({"action": "navigate", "result": nav})
        wait_ms = max(0, int(req.wait_after_navigate_ms))
        wait_timeout = max(10.0, (wait_ms / 1000.0) + 8.0)
        wait_res = await _browser_action_or_http_error("wait", {"ms": wait_ms}, timeout=wait_timeout)
        actions_log.append({"action": "wait", "result": wait_res})

    timeout_seconds = max(10, int(req.timeout_seconds))
    poll_interval_ms = max(300, int(req.poll_interval_ms))
    payload = {
        "table_keyword": str(req.table_keyword or "").strip(),
        "file_keyword": str(req.file_keyword or "").strip(),
        "timeout_ms": timeout_seconds * 1000,
        "poll_interval_ms": poll_interval_ms,
        "single_trigger_only": bool(req.single_trigger_only),
        "goto_center_after_trigger": bool(req.goto_center_after_trigger),
        # 任务中心链路优先打通时，下载类型允许兜底点击任一项
        "allow_any_download_type": bool(req.goto_center_after_trigger),
    }
    dl_res = await get_browser_gateway_manager().send_command(
        action="alpha_bi_download_table",
        payload=payload,
        timeout=timeout_seconds + 20.0,
    )
    actions_log.append({"action": "alpha_bi_download_table", "result": dl_res})

    if bool(req.goto_center_after_trigger):
        goto_res = await get_browser_gateway_manager().send_command(
            action="alpha_bi_goto_task_center",
            payload={},
            timeout=35.0,
        )
        actions_log.append({"action": "alpha_bi_goto_task_center", "result": goto_res})
        goto_payload = goto_res.get("payload") if isinstance(goto_res.get("payload"), dict) else {}
        if not isinstance(goto_payload, dict):
            goto_payload = {}
        goto_msg = str(goto_res.get("message") or "goto center not verified")
        if "unsupported action in content script: alpha_bi_goto_task_center" in goto_msg:
            goto_msg = (
                "浏览器扩展尚未加载 alpha_bi_goto_task_center 新动作。"
                "请在扩展管理页 Reload `myclaw-browser-agent`，并对目标页面执行 Ctrl+F5 后重试。"
            )
        goto_clicked = bool(goto_payload.get("goto_center_clicked"))
        before_url = str(goto_payload.get("before_url") or "")
        after_url = str(goto_payload.get("after_url") or "")
        goto_method = str(goto_payload.get("goto_method") or "")
        return {
            "ok": goto_clicked,
            "message": "goto center verified" if goto_clicked else goto_msg,
            "failure_reason": "" if goto_clicked else "goto_not_verified",
            "trigger_count": int((dl_res.get("payload") or {}).get("trigger_count") or 0) if isinstance(dl_res.get("payload"), dict) else 0,
            "menu_target": str((dl_res.get("payload") or {}).get("menu_target") or "raw_only") if isinstance(dl_res.get("payload"), dict) else "raw_only",
            "table_keyword": req.table_keyword,
            "file_keyword": req.file_keyword or "",
            "single_trigger_only": bool(req.single_trigger_only),
            "goto": {
                "goto_center_clicked": goto_clicked,
                "before_url": before_url,
                "after_url": after_url,
                "goto_method": goto_method,
            },
            "result": {
                "download": dl_res.get("payload") if isinstance(dl_res.get("payload"), dict) else {},
                "goto": goto_payload,
            },
            "actions_log": actions_log,
        }

    def _derive_single_fields(out_payload: dict, single_only: bool) -> tuple[str, int, str]:
        if not single_only:
            return "", 0, ""
        menu_target = str(out_payload.get("menu_target") or "raw_only")
        trigger_count_raw = out_payload.get("trigger_count")
        if isinstance(trigger_count_raw, (int, float)):
            trigger_count = int(trigger_count_raw)
        else:
            ui = out_payload.get("ui") if isinstance(out_payload.get("ui"), dict) else {}
            trigger_count = 1 if bool(ui.get("export_clicked")) else 0
        failure_reason = str(out_payload.get("failure_reason") or "").strip()
        if failure_reason:
            return failure_reason, trigger_count, menu_target
        raw_msg = str(out_payload.get("message") or "").lower()
        if "suppressed" in raw_msg or "dedupe" in raw_msg:
            return "dedupe_suppressed", trigger_count, menu_target
        ui = out_payload.get("ui") if isinstance(out_payload.get("ui"), dict) else {}
        debug = ui.get("debug") if isinstance(ui.get("debug"), dict) else {}
        matched_blocks = int(debug.get("matched_blocks") or 0) if isinstance(debug.get("matched_blocks"), (int, float)) else 0
        menu_clicked = bool(debug.get("menu_clicked"))
        if matched_blocks <= 0:
            failure_reason = "target_not_found"
        elif trigger_count <= 0:
            failure_reason = "trigger_not_found"
        elif not menu_clicked:
            failure_reason = "menu_not_found_raw"
        else:
            failure_reason = ""
        return failure_reason, trigger_count, menu_target

    # 注意：为防止重复下载触发，禁止在服务端做二次下载重试。
    # 任何跳转补偿仅通过独立动作 alpha_bi_goto_task_center 完成。

    if dl_res.get("type") == "error":
        err_payload = dl_res.get("payload") if isinstance(dl_res.get("payload"), dict) else {}
        err_msg = str(dl_res.get("message") or "alpha_bi_download_table failed")
        failure_reason, trigger_count, menu_target = _derive_single_fields(err_payload, bool(req.single_trigger_only))
        if "unsupported action in content script: alpha_bi_download_table" in err_msg:
            err_msg = (
                "浏览器扩展尚未加载 alpha_bi_download_table 新动作。"
                "请在扩展管理页 Reload `myclaw-browser-agent`，并对目标页面执行 Ctrl+F5 后重试。"
            )
        return {
            "ok": False,
            "message": err_msg,
            "failure_reason": failure_reason,
            "trigger_count": trigger_count,
            "menu_target": menu_target,
            "table_keyword": req.table_keyword,
            "file_keyword": req.file_keyword or "",
            "result": err_payload,
            "actions_log": actions_log,
        }

    out = dl_res.get("payload") if isinstance(dl_res.get("payload"), dict) else {}
    if not isinstance(out, dict):
        out = {}
    failure_reason, trigger_count, menu_target = _derive_single_fields(out, bool(req.single_trigger_only))
    return {
        "ok": bool(out.get("ok")),
        "message": str(out.get("message") or ("verified" if out.get("ok") else "download failed")),
        "failure_reason": failure_reason,
        "trigger_count": trigger_count,
        "menu_target": menu_target,
        "table_keyword": req.table_keyword,
        "file_keyword": req.file_keyword or "",
        "single_trigger_only": bool(req.single_trigger_only),
        "result": out,
        "actions_log": actions_log,
    }


@router.post("/api/browser/jobs/alpha-bi/download-preset")
async def run_alpha_bi_download_preset_job(req: AlphaBiDownloadPresetRequest):
    default_alpha_bi_url = (
        "https://alpha-bi.ddxq.mobi/report?"
        "pathIds=279b4f5efc6d446886b3662773c25b3c,cc4baf96c7344900918887be30cf56de"
        "&dashboardId=d127af3f0bb3457287f5093bdea78846"
        "&externalSpaceId=fccdafe6147b461d94425137c51ffe2e"
        "&appId=36620ff9365540a2b6a36531a5dcef6b"
        "&iframeType=app&orgId=1&spaceId=fccdafe6147b461d94425137c51ffe2e"
    )
    table_by_target = {
        "problem_breakdown_1_category": "✔ [贡献拆解1]-商品分类",
        "problem_breakdown_2_order_user": "✔ [过程拆解2]-补充订单&用户",
    }
    table_keyword = table_by_target.get(str(req.target_id or "").strip())
    if not table_keyword:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "unsupported target_id",
                "supported_target_ids": sorted(table_by_target.keys()),
            },
        )
    single_trigger_only = bool(req.single_trigger_only)
    goto_center_after_trigger = bool(req.goto_center_after_trigger)
    if bool(req.full_flow):
        # full_flow 模式强制关闭单次模式，允许后续“前往任务中心 + 下载完成”链路执行。
        single_trigger_only = False
        goto_center_after_trigger = False

    job_req = AlphaBiDownloadJobRequest(
        url=req.url or default_alpha_bi_url,
        table_keyword=table_keyword,
        file_keyword=req.file_keyword,
        wait_after_navigate_ms=req.wait_after_navigate_ms,
        timeout_seconds=req.timeout_seconds,
        poll_interval_ms=req.poll_interval_ms,
        single_trigger_only=single_trigger_only,
        goto_center_after_trigger=goto_center_after_trigger,
    )
    result = await run_alpha_bi_download_job(job_req)
    if isinstance(result, dict):
        result["target_id"] = req.target_id
        result["full_flow"] = bool(req.full_flow)
    return result


@router.post("/api/browser/jobs/alpha-bi/task-center-download")
async def run_alpha_bi_task_center_download_job(req: AlphaBiTaskCenterDownloadRequest):
    """
    任务中心下载：直接访问任务中心 URL 无效，必须从 Alpha 数据页「悬浮-原始数据-前往任务中心」跳转。
    本接口统一走完整流程 download-problem-locator。
    """
    locator_req = AlphaBiProblemLocatorDownloadRequest(
        url=None,
        wait_after_navigate_ms=max(2000, int(req.wait_after_navigate_ms or 8000)),
        download_icon_index=1,
    )
    result = await run_alpha_bi_problem_locator_download_job(locator_req)
    if isinstance(result, dict):
        result["via"] = "task-center-download->download-problem-locator"
    return result


class AlphaBiLocateDownloadIconRequest(BaseModel):
    url: str | None = None
    tab_text: str | None = None
    tab_within: str | None = None
    within_text: str | None = None
    within_index: int = 0  # within 块内第几个下载图标，过程拆解2 用 1


@router.post("/api/browser/jobs/alpha-bi/locate-download-icon")
async def alpha_bi_locate_download_icon(req: AlphaBiLocateDownloadIconRequest):
    """
    测试定位下载图标：navigate → 可选点 Tab → locate .anticon-download（可选 within）。
    用于验证 within 是否命中正确区块，返回 element.text 等。
    """
    from api.alpha_bi_problem_locator_download_job import DEFAULT_ALPHA_BI_URL

    transport = _browser_transport()
    if transport != "native_extension":
        raise HTTPException(status_code=400, detail="requires BROWSER_TRANSPORT=native_extension")
    status = await get_browser_gateway_manager().status()
    if not status.get("connected"):
        raise HTTPException(status_code=400, detail="native extension not connected")

    target_url = req.url or DEFAULT_ALPHA_BI_URL
    manager = get_browser_gateway_manager()
    actions_log: list[dict] = []

    nav = await manager.send_command("navigate", {"url": target_url}, 30.0)
    actions_log.append({"action": "navigate", "result": nav})
    await manager.send_command("wait", {"ms": 12000}, 15.0)

    if req.tab_text:
        tab_loc = {"text": req.tab_text}
        if req.tab_within:
            tab_loc["within"] = {"text": req.tab_within}
        tab_res = await manager.send_command("locate", {"locator": tab_loc}, 12.0)
        actions_log.append({"action": "locate_tab", "result": tab_res})
        pl = tab_res.get("payload") or {}
        if pl.get("ok") and (pl.get("element") or {}).get("handle"):
            await manager.send_command("click", {"locator": {"handle": pl["element"]["handle"]}}, 12.0)
            await manager.send_command("wait", {"ms": 1500}, 5.0)

    locators = []
    idx = max(0, int(req.within_index))
    if req.within_text:
        locators = [
            {"selector": ".anticon-download", "within": {"text": req.within_text}, "index": idx},
            {"selector": "[class*='download']", "within": {"text": req.within_text}, "index": idx},
        ]
    else:
        locators = [
            {"selector": ".anticon-download", "index": 0},
            {"selector": ".anticon-download", "index": 1},
        ]

    results = []
    for loc in locators:
        res = await manager.send_command("locate", {"locator": loc}, 12.0)
        ok = res.get("type") != "error" and (res.get("payload") or {}).get("ok")
        el = (res.get("payload") or {}).get("element") or {} if ok else {}
        results.append({
            "locator": loc,
            "found": ok,
            "element_text": el.get("text", "")[:80] if ok else None,
            "element_cls": el.get("cls", "")[:80] if ok else None,
        })
        if ok:
            await manager.send_command(
                "scroll_into_view", {"locator": loc, "block": "start"}, 10.0
            )
            actions_log.append({"action": "scroll_into_view", "result": "ok"})
            break

    return {"ok": any(r["found"] for r in results), "results": results, "actions_log": actions_log}


@router.post("/api/browser/jobs/alpha-bi/locate-refresh-debug")
async def alpha_bi_locate_refresh_debug():
    """
    调试接口：在任务中心页面尝试各种刷新按钮选择器，返回哪些能定位到元素。
    使用前请确保：1) 扩展已连接 2) 当前标签页已打开任务中心页面。
    """
    transport = _browser_transport()
    if transport != "native_extension":
        raise HTTPException(
            status_code=400,
            detail="requires BROWSER_TRANSPORT=native_extension",
        )
    status = await get_browser_gateway_manager().status()
    if not status.get("connected"):
        raise HTTPException(status_code=400, detail="native extension not connected")

    manager = get_browser_gateway_manager()
    ref_locs = [
        {"text": "刷新"},
        {"text": "刷新", "deep": True},
        {"selector": "[class*='iconify']"},
        {"selector": "[class*='iconify--mdi']"},
        {"selector": "button:has([class*='iconify'])", "index": 0},
        {"selector": "button:has([class*='iconify'])", "index": 1},
        {"selector": "[class*='reload']"},
        {"selector": "[class*='reload']", "deep": True},
        {"selector": "[class*='refresh']"},
        {"selector": "[class*='sync']"},
        {"selector": "[title='刷新']"},
        {"selector": "[aria-label*='刷新']"},
        {"selector": ".anticon-reload"},
        {"selector": "button.ant-btn-icon-only", "index": 0},
        {"selector": "button.ant-btn-icon-only", "index": 1},
        {"selector": ".ant-pro-table-list-toolbar button", "index": 0},
        {"selector": ".ant-pro-table-list-toolbar button", "index": 1},
    ]
    results = []
    for loc in ref_locs:
        try:
            res = await manager.send_command(action="locate", payload={"locator": loc}, timeout=12.0)
            ok = res.get("type") != "error" and (res.get("payload") or {}).get("ok")
            el = (res.get("payload") or {}).get("element") or {} if ok else {}
            results.append({
                "locator": loc,
                "found": ok,
                "element": {"tag": el.get("tag"), "cls": el.get("cls"), "text": el.get("text")} if ok else None,
            })
        except Exception as e:
            results.append({"locator": loc, "found": False, "error": str(e)})
    snap = await manager.send_command(action="snapshot", payload={}, timeout=15.0)
    snap_text = ""
    if snap.get("type") != "error":
        snap_text = str(((snap.get("payload") or {}).get("snapshot") or {}).get("text", ""))[:500]
    return {
        "found_count": sum(1 for r in results if r.get("found")),
        "results": results,
        "snapshot_preview": snap_text,
    }


@router.post("/api/browser/jobs/alpha-bi/download-problem-locator")
async def run_alpha_bi_problem_locator_download_job(req: AlphaBiProblemLocatorDownloadRequest):
    """
    ▌二、问题定位 表下载：悬浮下载图标 -> 点击原始数据 -> 点击跳转至任务中心 -> 在任务中心点击下载。
    使用 v2 原子动作，与旧 download job 完全隔离。
    """
    from api.alpha_bi_problem_locator_download_job import (
        DEFAULT_ALPHA_BI_URL,
        DOWNLOAD_ICON_INDEX,
        GOTO_CENTER_TEXTS,
    )

    transport = _browser_transport()
    if transport != "native_extension":
        raise HTTPException(
            status_code=400,
            detail="download-problem-locator job requires BROWSER_TRANSPORT=native_extension",
        )

    status = await get_browser_gateway_manager().status()
    if not status.get("connected"):
        raise HTTPException(status_code=400, detail="native extension not connected")

    target_url = req.url or DEFAULT_ALPHA_BI_URL
    icon_index = max(0, int(req.download_icon_index or DOWNLOAD_ICON_INDEX))
    within_text = (req.within_text or "").strip()
    wait_ms = max(2000, int(req.wait_after_navigate_ms))
    manager = get_browser_gateway_manager()
    actions_log: list[dict] = []

    async def run_step(action: str, payload: dict, timeout: float = 15.0) -> dict:
        res = await manager.send_command(action=action, payload=payload, timeout=timeout)
        actions_log.append({"action": action, "payload": payload, "result": res})
        return res

    # 1) 导航
    nav = await run_step("navigate", {"url": target_url}, 30.0)
    if nav.get("type") == "error":
        return {
            "ok": False,
            "message": str(nav.get("message") or "navigate failed"),
            "stage": "navigate",
            "actions_log": actions_log,
        }
    await run_step("wait", {"ms": wait_ms}, max(10.0, wait_ms / 1000.0 + 8.0))

    # 1.5) 若需先点 Tab（如 转化归因 tab 下的图）
    tab_text = (req.tab_text or "").strip()
    tab_within = (req.tab_within or "").strip()
    if tab_text:
        tab_locator = {"text": tab_text}
        if tab_within:
            tab_locator["within"] = {"text": tab_within}
        tab_res = await run_step("locate", {"locator": tab_locator}, 12.0)
        if tab_res.get("type") != "error":
            pl = tab_res.get("payload") or {}
            handle = (pl.get("element") or {}).get("handle")
            if handle:
                await run_step("click", {"locator": {"handle": handle}}, 12.0)
                await run_step("wait", {"ms": 1500}, 5.0)

    # 2) 悬浮下载图标：优先用 within_text 按区块定位，否则用全局 index
    if within_text:
        # 先滚动到区块内，确保下载图标可见（趋势分析等可能 below the fold）
        scroll_loc = {"selector": "div", "within": {"text": within_text}, "index": 0}
        await run_step("scroll_into_view", {"locator": scroll_loc}, 10.0)
        await run_step("wait", {"ms": 500}, 3.0)
        hover_selectors = [
            {"selector": ".anticon-download", "within": {"text": within_text}, "index": 0},
            {"selector": "[class*='download']", "within": {"text": within_text}, "index": 0},
            {"selector": ".ant-dropdown-trigger", "within": {"text": within_text}, "index": 0},
        ]
    else:
        hover_selectors = [
            {"selector": ".anticon-download", "index": icon_index},
            {"selector": "[class*='download']", "index": icon_index},
            {"selector": ".ant-dropdown-trigger", "index": icon_index + 1},
        ]
    hover_ok = False
    for loc in hover_selectors:
        r = await run_step("hover", {"locator": loc}, 12.0)
        if r.get("type") != "error":
            hover_ok = True
            break
    if not hover_ok:
        return {
            "ok": False,
            "message": "hover on download icon failed",
            "stage": "hover",
            "actions_log": actions_log,
        }

    await run_step("wait", {"ms": 600}, 8.0)

    # 3) 点击「原始数据」（悬浮后出现的下拉菜单项，优先用菜单项 selector 精确定位）
    click_raw = await run_step(
        "click",
        {"locator": {"selector": ".ant-dropdown-menu-item", "text": "原始数据"}},
        12.0,
    )
    if click_raw.get("type") == "error":
        click_raw = await run_step("click", {"text": "原始数据", "index": 1}, 12.0)
    if click_raw.get("type") == "error":
        click_raw = await run_step("click", {"text": "原始数据"}, 12.0)
    if click_raw.get("type") == "error":
        return {
            "ok": False,
            "message": "click 原始数据 failed",
            "stage": "click_raw",
            "actions_log": actions_log,
        }

    await run_step("wait", {"ms": 3000}, 10.0)

    # 4) 等待弹窗出现后，点击「前往任务中心>>」
    await run_step(
        "wait_for",
        {"locator": {"text": "前往任务中心"}, "state": "visible", "timeout_ms": 8000},
        12.0,
    )

    async def _try_goto_click() -> bool:
        for loc in [
            {"selector": "button.ant-btn-primary", "text": "前往任务中心"},
            {"selector": ".ant-modal button.ant-btn-primary"},
            {"selector": ".ant-modal-footer button.ant-btn-primary"},
            {"selector": "button.ant-btn-primary", "index": 1},
            {"selector": "button.ant-btn-primary"},
        ]:
            r = await run_step("click", {"locator": loc}, 12.0)
            if r.get("type") != "error":
                return True
        for txt in GOTO_CENTER_TEXTS:
            r = await run_step("click", {"locator": {"text": txt, "role": "button"}}, 12.0)
            if r.get("type") != "error":
                return True
        for txt in GOTO_CENTER_TEXTS:
            r = await run_step("click", {"text": txt}, 12.0)
            if r.get("type") != "error":
                return True
        return False

    snap_pre_goto = await run_step("snapshot", {}, 20.0)
    pre_goto_text = ""
    if snap_pre_goto.get("type") != "error":
        pl = snap_pre_goto.get("payload") or {}
        pre_goto_text = str((pl.get("snapshot") or {}).get("text") or "")[:2000]

    goto_click_ok = await _try_goto_click()
    if not goto_click_ok:
        return {
            "ok": False,
            "message": "click 跳转至任务中心 failed",
            "stage": "click_goto",
            "pre_goto_snapshot_preview": pre_goto_text[:1500] if pre_goto_text else "",
            "actions_log": actions_log,
        }

    await run_step("wait", {"ms": 3500}, 12.0)

    # 4c) snapshot + get_url 验证是否已进入任务中心，失败则重试一次
    def _in_task_center(url: str, text: str) -> bool:
        u = (url or "").lower()
        t = (text or "").replace(" ", "")
        # URL 或快照文本包含任务中心特征
        return (
            "task" in u or "download" in u or "任务" in u
            or "下载中心" in t or "任务中心" in t or "下载管理" in t
            or "等待中" in t or "进行中" in t or "已成功" in t  # 任务状态，说明已在任务中心
        )

    async def _verify_goto() -> tuple[bool, str, str]:
        snap = await run_step("snapshot", {}, 20.0)
        url_res = await run_step("get_url", {}, 10.0)
        url = ""
        text = ""
        if url_res.get("type") != "error":
            url = str((url_res.get("payload") or {}).get("url") or "")
        if snap.get("type") != "error":
            pl = snap.get("payload") or {}
            text = str((pl.get("snapshot") or {}).get("text") or "")[:3000]
        return _in_task_center(url, text), url, text

    verified, after_goto_url, after_goto_text = await _verify_goto()
    if not verified:
        await run_step("wait", {"ms": 2000}, 8.0)
        await _try_goto_click()
        await run_step("wait", {"ms": 4000}, 12.0)
        verified, after_goto_url, after_goto_text = await _verify_goto()

    if not verified:
        return {
            "ok": False,
            "message": "goto not verified: still not in task center",
            "stage": "verify_goto",
            "after_goto_url": after_goto_url[:200],
            "after_goto_snapshot_preview": after_goto_text[:1500],
            "actions_log": actions_log,
        }

    # 5) 保持当前页（点击「前往任务中心>>」已正确跳转，直接访问 URL 无效），等待任务就绪后下载
    await run_step("wait", {"ms": 3000}, 10.0)

    max_poll = 12
    poll_interval_ms = 5000
    dl_click_ok = False
    poll_details: list[dict] = []

    for poll_i in range(max_poll):
        snap = await run_step("snapshot", {}, 20.0)
        snap_text = ""
        if snap.get("type") != "error":
            pl = snap.get("payload") or {}
            snap_text = str((pl.get("snapshot") or {}).get("text") or "")[:4000]

        has_wait = "等待中" in snap_text
        has_progress = "进行中" in snap_text
        has_ok = "已成功" in snap_text
        has_dl = "下载" in snap_text
        first_wait = snap_text.find("等待中")
        first_progress = snap_text.find("进行中")
        first_ok = snap_text.find("已成功")
        # 文本中最早出现的状态即第一条任务的状态
        poses = []
        if first_wait >= 0:
            poses.append(("wait", first_wait))
        if first_progress >= 0:
            poses.append(("progress", first_progress))
        if first_ok >= 0:
            poses.append(("ok", first_ok))
        if not poses:
            first_row_ready = False
            first_row_waiting = False
        else:
            first_status = min(poses, key=lambda x: x[1])[0]
            first_row_ready = first_status == "ok" and has_dl
            first_row_waiting = first_status in ("wait", "progress")
        task_ready = first_row_ready
        poll_details.append({
            "poll": poll_i + 1,
            "has_等待中": has_wait,
            "has_进行中": has_progress,
            "has_已成功": has_ok,
            "has_下载": has_dl,
            "first_row_ready": first_row_ready,
            "first_row_waiting": first_row_waiting,
            "task_ready": task_ready,
            "text_preview": snap_text[:400],
        })

        if task_ready:
            for loc in [
                {"selector": ".ant-table-tbody tr:first-child td span.member-table__btn", "text": "下载"},
                {"selector": ".ant-table-tbody tr:first-child td a, .ant-table-tbody tr:first-child td span", "text": "下载"},
                {"selector": ".ant-table-tbody tr:first-child td a", "text": "下载"},
                {"selector": ".ant-table-tbody td span.member-table__btn", "text": "下载", "index": 0},
                {"selector": ".ant-table-tbody td a", "text": "下载", "index": 0},
                {"selector": ".ant-table-tbody td span, .ant-table-tbody td a", "text": "下载", "index": 0},
                {"selector": ".ant-table a", "text": "下载", "index": 0},
                {"selector": "a[href]", "text": "下载", "index": 0},
                {"selector": "span.member-table__btn", "text": "下载", "index": 0},
                {"text": "下载", "exact": True, "selector": "a", "index": 0},
                {"text": "下载", "index": 0, "selector": "a"},
            ]:
                dl_res = await run_step("download_from_link", {"locator": loc}, 12.0)
                if dl_res.get("type") != "error":
                    dl_click_ok = True
                    break
            if not dl_click_ok:
                for loc in [
                    {"selector": ".ant-table-tbody tr:first-child td span.member-table__btn", "text": "下载"},
                    {"selector": ".ant-table-tbody tr:first-child td span, .ant-table-tbody tr:first-child td a", "text": "下载"},
                    {"selector": ".ant-table-tbody td span.member-table__btn", "text": "下载", "index": 0},
                    {"selector": "span.member-table__btn", "text": "下载", "index": 0},
                    {"selector": "span", "text": "下载", "exact": True, "index": 0},
                ]:
                    tc_res = await run_step("click_trusted", {"locator": loc}, 15.0)
                    if tc_res.get("type") != "error":
                        dl_click_ok = True
                        break
                if not dl_click_ok:
                    for loc in [
                        {"selector": ".ant-table-tbody tr:first-child td *", "text": "下载", "exact": True},
                        {"selector": ".ant-table-tbody td *", "text": "下载", "exact": True, "index": 0},
                        {"selector": ".ant-table td a, .ant-table td span, .ant-table td button", "text": "下载", "index": 0},
                        {"selector": "button", "text": "下载", "index": 0},
                        {"text": "下载", "exact": True, "selector": "a, span, button", "index": 0},
                        {"text": "下载", "index": 0, "selector": "a, span, button"},
                    ]:
                        dl_click = await run_step("click", {"locator": loc}, 12.0)
                        if dl_click.get("type") != "error":
                            pl = dl_click.get("payload") or {}
                            el = pl.get("element") or {}
                            if "spin" not in str(el.get("cls", "")).lower() and "loading" not in str(el.get("cls", "")).lower():
                                dl_click_ok = True
                                break
            if not dl_click_ok:
                return {
                    "ok": False,
                    "message": "download/click 下载 failed",
                    "stage": "click_download",
                    "poll_details": poll_details,
                    "snapshot_preview": snap_text[:1500],
                    "actions_log": actions_log,
                }
            break

        # 仅用 reload_page（frame 级 location.reload），不点击刷新按钮，避免误点 logo
        reload_ok = False
        rp = await run_step("reload_page", {}, 8.0)
        if rp.get("type") != "error" and (rp.get("payload") or {}).get("ok"):
            reload_ok = True
        poll_details[-1]["reload_ok"] = reload_ok

        await run_step("wait", {"ms": poll_interval_ms}, max(10.0, poll_interval_ms / 1000.0 + 5.0))

    if not dl_click_ok:
        snap_fail = await run_step("snapshot", {}, 20.0)
        fail_text = ""
        if snap_fail.get("type") != "error":
            pl = snap_fail.get("payload") or {}
            fail_text = str((pl.get("snapshot") or {}).get("text") or "")[:2000]
        return {
            "ok": False,
            "message": "task not ready after polling (still 等待中/进行中 or 下载 not found)",
            "stage": "wait_task_ready",
            "poll_count": max_poll,
            "poll_details": poll_details,
            "snapshot_preview": fail_text[:1500],
            "actions_log": actions_log,
        }

    await run_step("wait", {"ms": 2000}, 8.0)

    snap_final = await run_step("snapshot", {}, 20.0)
    final_text = ""
    if snap_final.get("type") != "error":
        pl = snap_final.get("payload") or {}
        final_text = str((pl.get("snapshot") or {}).get("text") or "")[:2000]

    return {
        "ok": True,
        "message": "verified",
        "stage": "done",
        "poll_details": poll_details,
        "final_snapshot_preview": final_text[:800],
        "actions_log": actions_log,
    }


@router.post("/api/skills/reload")
async def reload_skills():
    loader = get_skill_loader()
    loader.discover()
    return {
        "message": f"重新发现完成，共 {len(loader.loaded_skills)} 个 Skill",
        "skills": [s.name for s in loader.loaded_skills],
    }


def _ensure_json_serializable(obj):
    """Ensure object is JSON-serializable (Path, etc. -> str)."""
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, dict):
        return {str(k): _ensure_json_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_ensure_json_serializable(v) for v in obj]
    return obj


# --- WebSocket ---

@router.websocket("/ws/chat")
async def chat_ws(websocket: WebSocket):
    try:
        await websocket.accept()
    except Exception as e:
        logger.error("WebSocket accept failed: %s", e, exc_info=True)
        return

    history: list = []
    session_id = uuid.uuid4().hex[:12]
    turn_num = 0
    created_at = datetime.now(timezone.utc).isoformat()
    ws_connected_at = datetime.now(timezone.utc)
    last_activity_at = ws_connected_at
    current_turn_task: asyncio.Task | None = None
    model_name = os.getenv("LLM_MODEL", "qwen-plus")
    context_limit = MODEL_CONTEXT_LIMITS.get(model_name, DEFAULT_CONTEXT_LIMIT)

    async def _send_event(event_type: str, data: dict, step: int = 0):
        await websocket.send_json({
            "type": event_type,
            "step": step,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data,
        })

    async def _process_turn(user_content: str, turn_id: int):
        nonlocal history

        await _send_event("graph_reset", {})
        await _send_event("user_input", {"content": user_content})

        async def on_event(event: dict):
            await websocket.send_json(event)

        try:
            governed_history, governance_events, _ = _govern_history_before_run(
                history=history,
                user_content=user_content,
                model_name=model_name,
                context_limit=context_limit,
            )
            for evt in governance_events:
                await _send_event(evt["type"], evt["data"])

            round_messages = await run_agent(user_content, on_event, history=governed_history, turn_num=turn_id)
            history = list(governed_history)
            history.append({"role": "user", "content": user_content})
            history.extend(round_messages)

            try:
                _save_turn(session_id, turn_id, user_content, round_messages, created_at)
            except Exception as e:
                logger.warning("Failed to save conversation turn: %s", e)
            return

        except asyncio.CancelledError:
            history.append({"role": "user", "content": user_content})
            history.append({"role": "assistant", "content": "本轮任务已按用户请求手动停止。"})
            await _send_event("agent_stopped", {"reason": "manual_stop", "turn": turn_id})
            return

        except Exception as run_err:
            policy = load_context_policy()
            if is_context_overflow(run_err) and policy.max_retry_on_overflow > 0:
                retry_history, compact_stats = compact_history(
                    history,
                    preserve_recent_turns=policy.preserve_recent_turns,
                    model_name=model_name,
                )
                await _send_event("context_compacted", {
                    "before_tokens": compact_stats.get("before_tokens", 0),
                    "after_tokens": compact_stats.get("after_tokens", 0),
                    "summary_chars": compact_stats.get("summary_chars", 0),
                    "compacted_turns": compact_stats.get("compacted_turns", 0),
                })
                try:
                    round_messages = await run_agent(user_content, on_event, history=retry_history, turn_num=turn_id)
                    history = list(retry_history)
                    history.append({"role": "user", "content": user_content})
                    history.extend(round_messages)
                    await _send_event("overflow_recovered", {"retry_count": 1, "success": True, "reason": "context_overflow"})
                    try:
                        _save_turn(session_id, turn_id, user_content, round_messages, created_at)
                    except Exception as e:
                        logger.warning("Failed to save conversation turn after retry: %s", e)
                    return
                except Exception:
                    await _send_event("overflow_recovered", {"retry_count": 1, "success": False, "reason": "context_overflow"})

            tb = traceback.format_exc()
            logger.error("Agent error: %s", tb)
            detail = _extract_user_friendly_error(run_err)
            await _send_event("error", {"message": "Agent 执行出错", "detail": detail}, step=-1)
            return

    try:
        loader = get_skill_loader()
        builtin_tools_info = [
            {"name": str(t.name), "source": "builtin"} for t in get_all_tools()
        ]
        skills_info = [
            {"name": str(s.name), "description": str(s.description), "scripts": list(s.scripts)}
            for s in _filter_runtime_skills(loader.loaded_skills)
        ]
        assembled_prompt = _build_system_prompt()
        payload = {
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
                "browser_transport": _browser_transport(),
            },
        }
        payload = _ensure_json_serializable(payload)
        json.dumps(payload)
        await websocket.send_json(payload)
    except Exception as e:
        logger.error("init_status build/send failed: %s", e, exc_info=True)
        try:
            await websocket.send_json({
                "type": "init_status",
                "step": 0,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "jobs": init_collector.to_dict_list(),
                    "tools": [],
                    "skills": [],
                    "system_prompt": "",
                    "model_name": os.getenv("LLM_MODEL", "qwen-plus"),
                    "context_limit": DEFAULT_CONTEXT_LIMIT,
                    "browser_transport": _browser_transport(),
                    "_init_error": str(e)[:200],
                },
            })
        except Exception as send_err:
            logger.error("Failed to send fallback init_status: %s", send_err, exc_info=True)

    try:
        while True:
            if current_turn_task and current_turn_task.done():
                try:
                    current_turn_task.result()
                except Exception:
                    logger.exception("Background turn task failed (session=%s)", session_id)
                current_turn_task = None

            raw = await websocket.receive_text()
            last_activity_at = datetime.now(timezone.utc)

            msg_type = "user_input"
            user_content = ""
            try:
                msg = json.loads(raw)
                msg_type = str(msg.get("type", "user_input"))
                if msg_type == "user_input":
                    user_content = str(msg.get("data", {}).get("content", "") or "")
            except (json.JSONDecodeError, AttributeError):
                user_content = raw.strip()

            if msg_type == "stop":
                if current_turn_task and not current_turn_task.done():
                    current_turn_task.cancel()
                    try:
                        await current_turn_task
                    except asyncio.CancelledError:
                        pass
                    except Exception:
                        logger.exception("Failed to stop running turn (session=%s)", session_id)
                    current_turn_task = None
                else:
                    await _send_event("agent_stopped", {"reason": "idle", "turn": turn_num})
                continue

            if msg_type != "user_input":
                continue

            if not user_content:
                continue

            if current_turn_task and not current_turn_task.done():
                await _send_event("error", {
                    "message": "当前任务仍在执行，请先停止或等待完成",
                    "detail": "busy",
                }, step=-1)
                continue

            turn_num += 1
            current_turn_task = asyncio.create_task(_process_turn(user_content, turn_num))

    except WebSocketDisconnect as e:
        if current_turn_task and not current_turn_task.done():
            current_turn_task.cancel()
            try:
                await current_turn_task
            except Exception:
                pass
        now = datetime.now(timezone.utc)
        alive_seconds = round((now - ws_connected_at).total_seconds(), 1)
        idle_seconds = round((now - last_activity_at).total_seconds(), 1)
        logger.info(
            "WebSocket client disconnected (session=%s, turns=%d, code=%s, reason=%s, alive_seconds=%s, idle_seconds=%s)",
            session_id,
            turn_num,
            getattr(e, "code", "unknown"),
            getattr(e, "reason", "") or "",
            alive_seconds,
            idle_seconds,
        )
    except Exception:
        if current_turn_task and not current_turn_task.done():
            current_turn_task.cancel()
            try:
                await current_turn_task
            except Exception:
                pass
        logger.exception(
            "WebSocket chat loop crashed (session=%s, turns=%d)",
            session_id,
            turn_num,
        )


@router.websocket("/ws/browser-gateway")
async def browser_gateway_ws(websocket: WebSocket):
    await websocket.accept()
    manager = get_browser_gateway_manager()
    client_id = ""
    try:
        hello_raw = await websocket.receive_text()
        hello = json.loads(hello_raw)
        if str(hello.get("type", "")) != GatewayMessageType.HELLO.value:
            await websocket.send_json({"type": "error", "message": "first message must be hello"})
            await websocket.close(code=1003)
            return
        client_id = str(hello.get("client_id") or uuid.uuid4().hex[:12])
        await manager.register(websocket, client_id=client_id, meta=hello.get("meta") or {})
        await websocket.send_json(
            {
                "type": "ack",
                "id": hello.get("id", ""),
                "message": "registered",
                "client_id": client_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            await manager.handle_message(client_id=client_id, message=msg)
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("browser gateway websocket crashed (client=%s)", client_id)
    finally:
        if client_id:
            await manager.unregister(client_id)
