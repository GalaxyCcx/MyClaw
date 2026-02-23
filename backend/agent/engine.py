from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from langchain.agents import create_agent

from agent.llm import get_llm
from agent.skill_loader import get_skill_loader
from agent.tool_registry import get_all_tools

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

DEFAULT_SYSTEM_PROMPT = """你是 MyClaw，一个通用 AI 助手。

你可以使用提供的工具来完成用户的任务。

执行原则：
1. 仅处理用户最新一条消息的需求，不要重复处理历史已完成的任务
2. 每一步选择最合适的工具
3. 使用 python_executor 时，请将完整代码写在一次调用中，不要拆成多次调用
4. 工具调用获得结果后，直接用文字总结回复用户，不要重复调用相同工具
5. 如果工具执行失败，最多重试一次，然后给出解释
6. 最终给出清晰、完整的回答"""

TOKEN_DELAY = 0.02

MODEL_CONTEXT_LIMITS: dict[str, int] = {
    "qwen-plus": 131072,
    "qwen-turbo": 1048576,
    "qwen-max": 32768,
    "qwen3.5-plus": 1048576,
}
DEFAULT_CONTEXT_LIMIT = 131072


def _extract_token_usage(ai_msg) -> dict[str, int] | None:
    """Extract token usage from a LangChain AIMessage if available."""
    usage = getattr(ai_msg, "usage_metadata", None)
    if usage and isinstance(usage, dict):
        return {
            "prompt_tokens": usage.get("input_tokens", 0),
            "completion_tokens": usage.get("output_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        }
    resp_meta = getattr(ai_msg, "response_metadata", None)
    if resp_meta and isinstance(resp_meta, dict):
        tu = resp_meta.get("token_usage") or resp_meta.get("usage") or {}
        if tu:
            return {
                "prompt_tokens": tu.get("prompt_tokens", 0),
                "completion_tokens": tu.get("completion_tokens", 0),
                "total_tokens": tu.get("total_tokens", tu.get("prompt_tokens", 0) + tu.get("completion_tokens", 0)),
            }
    return None


def load_system_prompt() -> str:
    path = PROMPTS_DIR / "system.md"
    if path.exists():
        content = path.read_text(encoding="utf-8").strip()
        if content:
            logger.info("Loaded system prompt from %s", path)
            return content
    logger.warning("System prompt file not found or empty, using default")
    return DEFAULT_SYSTEM_PROMPT


def _build_system_prompt() -> str:
    base = load_system_prompt()
    today = datetime.now().strftime("%Y-%m-%d %A")
    base = f"当前日期：{today}\n\n{base}"
    loader = get_skill_loader()
    skills = loader.loaded_skills
    if skills:
        lines = ["", "", "<available_skills>"]
        for s in skills:
            scripts_note = f' scripts="{", ".join(s.scripts)}"' if s.scripts else ""
            lines.append(f'<skill name="{s.name}"{scripts_note}>{s.description}</skill>')
        lines.append("</available_skills>")
        base += "\n".join(lines)
    return base


def _make_event(event_type: str, data: dict[str, Any], step: int = 0) -> dict:
    return {
        "type": event_type,
        "step": step,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }


def _serialize_message(msg) -> dict:
    """Serialize a LangChain message (or plain dict) to a JSON-safe dict."""
    if isinstance(msg, dict):
        return msg
    d: dict[str, Any] = {"role": getattr(msg, "type", "unknown")}
    content = getattr(msg, "content", "")
    if content:
        d["content"] = content
    tool_calls = getattr(msg, "tool_calls", None)
    if tool_calls:
        d["tool_calls"] = [
            {"id": tc.get("id", ""), "name": tc.get("name", ""), "args": tc.get("args", {})}
            for tc in tool_calls
        ]
    name = getattr(msg, "name", None)
    if name:
        d["name"] = name
    tool_call_id = getattr(msg, "tool_call_id", None)
    if tool_call_id:
        d["tool_call_id"] = tool_call_id
    return d


def build_agent():
    llm = get_llm()
    tools = get_all_tools()
    max_steps = int(os.getenv("AGENT_MAX_STEPS", "40"))
    system_prompt = _build_system_prompt()
    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=system_prompt,
        name="myclaw_agent",
    )
    return agent, max_steps


async def _stream_text(content: str, step: int, on_event: Callable):
    for char in content:
        await on_event(_make_event("llm_token", {"token": char}, step=step))
        await asyncio.sleep(TOKEN_DELAY)


async def run_agent(
    user_input: str,
    on_event: Callable,
    history: list | None = None,
    turn_num: int = 1,
) -> list:
    agent, max_steps = build_agent()

    messages = []
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_input})

    inputs = {"messages": messages}
    config = {"recursion_limit": max_steps * 4 + 10}

    round_messages: list = []
    step = 0

    async for event in agent.astream(inputs, config=config, stream_mode="updates"):
        for node_name, node_output in event.items():
            if node_name == "model":
                step += 1
                node_start = time.perf_counter()
                msgs = node_output.get("messages", [])
                if not msgs:
                    continue
                ai_msg = msgs[-1]
                round_messages.append(ai_msg)

                all_msgs = [_serialize_message(m) for m in messages] + [_serialize_message(m) for m in round_messages[:-1]]
                await on_event(_make_event("node_enter", {
                    "node_type": "llm",
                    "node_id": f"llm_t{turn_num}_{step}",
                    "step": step,
                    "messages_snapshot": all_msgs,
                }, step=step))

                tool_calls = getattr(ai_msg, "tool_calls", None)
                has_tool_calls = bool(tool_calls)

                if tool_calls:
                    for tc in tool_calls:
                        await on_event(_make_event(
                            "tool_call",
                            {
                                "tool_call_id": tc.get("id", ""),
                                "name": tc.get("name", ""),
                                "arguments": tc.get("args", {}),
                            },
                            step=step,
                        ))
                else:
                    content = getattr(ai_msg, "content", "")
                    if content:
                        await _stream_text(content, step, on_event)
                        await on_event(_make_event(
                            "final_answer",
                            {"content": content},
                            step=step,
                        ))

                duration_ms = round((time.perf_counter() - node_start) * 1000, 1)
                token_usage = _extract_token_usage(ai_msg)
                await on_event(_make_event("node_exit", {
                    "node_type": "llm",
                    "node_id": f"llm_t{turn_num}_{step}",
                    "step": step,
                    "has_tool_calls": has_tool_calls,
                    "duration_ms": duration_ms,
                    **({"token_usage": token_usage} if token_usage else {}),
                }, step=step))

            elif node_name == "tools":
                tool_msgs = node_output.get("messages", [])
                for tm in tool_msgs:
                    round_messages.append(tm)
                    content = getattr(tm, "content", "")
                    name = getattr(tm, "name", "")
                    tool_call_id = getattr(tm, "tool_call_id", "")
                    status = "error" if content.startswith("错误") else "success"

                    tool_start = time.perf_counter()
                    await on_event(_make_event("node_enter", {
                        "node_type": "tool",
                        "node_id": f"tool_{name}_t{turn_num}_{step}",
                        "step": step,
                        "tool_name": name,
                    }, step=step))

                    await on_event(_make_event(
                        "tool_result",
                        {
                            "tool_call_id": tool_call_id,
                            "name": name,
                            "status": status,
                            "content": content,
                        },
                        step=step,
                    ))

                    tool_duration = round((time.perf_counter() - tool_start) * 1000, 1)
                    await on_event(_make_event("node_exit", {
                        "node_type": "tool",
                        "node_id": f"tool_{name}_t{turn_num}_{step}",
                        "step": step,
                        "status": status,
                        "duration_ms": tool_duration,
                    }, step=step))

    return round_messages
