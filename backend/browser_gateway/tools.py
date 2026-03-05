from __future__ import annotations

import asyncio
import concurrent.futures
import json
import os
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from browser_gateway.manager import get_browser_gateway_manager


def _gateway_timeout() -> float:
    return float(os.getenv("BROWSER_GATEWAY_TIMEOUT", "30"))


ALPHA_BI_HOST_KEYWORD = "alpha-bi.ddxq.mobi/report"
ALPHA_BI_SINGLE_STEP_BLOCKED_ACTIONS = {
    "click",
    "type",
    "select_option",
    "hover",
    "press_key",
}


def _format_gateway_result(result: dict[str, Any]) -> str:
    if result.get("type") == "error":
        return f"错误: {result.get('message', 'unknown error')}"
    payload = result.get("payload")
    if isinstance(payload, dict):
        if isinstance(payload.get("steps"), list):
            steps = payload.get("steps") or []
            failed = [s for s in steps if isinstance(s, dict) and not bool(s.get("ok", False))]
            compact = {
                "ok": payload.get("ok", True),
                "message": payload.get("message", ""),
                "steps_total": len(steps),
                "steps_failed": len(failed),
                "failed_preview": failed[:3],
            }
            return _to_compact_json(compact, max_len=2000)

        # Never surface screenshot base64 to the model context.
        data_url = payload.get("data_url")
        if isinstance(data_url, str) and data_url:
            return f"screenshot captured (data_url omitted, chars={len(data_url)})"

        snapshot = payload.get("snapshot")
        if isinstance(snapshot, dict):
            return _format_snapshot(snapshot)

        # Return compact JSON for normal action payloads.
        return _to_compact_json(payload)
    return json.dumps(result, ensure_ascii=False)


def _is_retriable_error(result: dict[str, Any]) -> bool:
    return result.get("type") == "error" and bool(result.get("retriable"))


def _active_url_from_status_snapshot() -> str:
    try:
        status = get_browser_gateway_manager().status_snapshot()
        clients = status.get("clients") or []
        if not isinstance(clients, list):
            return ""
        active_client_id = str(status.get("active_client_id") or "")
        if active_client_id:
            for client in clients:
                if str(client.get("client_id") or "") == active_client_id:
                    meta = client.get("meta") or {}
                    return str(meta.get("active_url") or "")
        if clients:
            meta = clients[0].get("meta") or {}
            return str(meta.get("active_url") or "")
    except Exception:
        return ""
    return ""


def _should_block_single_step_in_alpha_bi(action: str, payload: dict[str, Any]) -> bool:
    if action not in ALPHA_BI_SINGLE_STEP_BLOCKED_ACTIONS:
        return False
    # allow escape hatch for diagnostics/manual fallback
    if bool(payload.get("force_single_step")):
        return False
    active_url = _active_url_from_status_snapshot()
    return ALPHA_BI_HOST_KEYWORD in active_url


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _to_compact_json(obj: Any, max_len: int = 1600) -> str:
    raw = json.dumps(obj, ensure_ascii=False)
    return _truncate(raw, max_len=max_len)


def _format_snapshot(snapshot: dict[str, Any]) -> str:
    text = str(snapshot.get("text") or "")
    elements = snapshot.get("elements")
    compact: dict[str, Any] = {
        "title": snapshot.get("title", ""),
        "url": snapshot.get("url", ""),
        "text": _truncate(text, 1200),
    }
    if isinstance(elements, list):
        compact["elements"] = elements[:40]
        compact["elements_count"] = int(snapshot.get("elements_count") or len(elements))
    return _to_compact_json(compact, max_len=4000)


class NavigateArgs(BaseModel):
    url: str = Field(..., description="目标URL")


class ClickArgs(BaseModel):
    ref: str | None = Field(default=None, description="snapshot 返回的元素引用ID")
    selector: str | None = Field(default=None, description="CSS选择器")
    text: str | None = Field(default=None, description="按可见文本匹配")


class TypeArgs(BaseModel):
    ref: str | None = Field(default=None, description="snapshot 返回的元素引用ID")
    selector: str | None = Field(default=None, description="CSS选择器")
    target_text: str | None = Field(default=None, description="按可见文本匹配输入目标（仅定位，不是输入值）")
    text: str = Field(..., description="输入文本")
    clear: bool = Field(default=True, description="是否先清空输入框")


class WaitArgs(BaseModel):
    ms: int = Field(default=1000, description="等待毫秒数")


class PressKeyArgs(BaseModel):
    key: str = Field(..., description="键值，如 Enter, Escape")


class SnapshotArgs(BaseModel):
    mode: str = Field(default="summary", description="summary|full")


class DownloadStatusArgs(BaseModel):
    keyword: str | None = Field(default=None, description="文件名关键字")


class SelectOptionArgs(BaseModel):
    ref: str | None = Field(default=None, description="snapshot 返回的元素引用ID")
    selector: str | None = Field(default=None, description="select元素选择器")
    value: str = Field(..., description="option值")


class PlanStepArgs(BaseModel):
    action: str = Field(..., description="步骤动作，如 click/type/wait/snapshot/select_option/press_key/navigate")
    payload: dict[str, Any] = Field(default_factory=dict, description="步骤参数")


class RunPlanArgs(BaseModel):
    steps: list[PlanStepArgs] = Field(..., description="按顺序执行的动作步骤列表")
    stop_on_error: bool = Field(default=True, description="任一步失败时是否立即停止")


def _dispatch(action: str, payload: dict[str, Any]) -> str:
    if _should_block_single_step_in_alpha_bi(action, payload):
        return (
            "错误: Alpha BI 页面已启用批量执行门控。"
            f"动作 `{action}` 需通过 browser_run_plan 执行；"
            "如需临时调试可传 force_single_step=true。"
        )

    manager = get_browser_gateway_manager()
    coro = manager.send_command(
        action=action,
        payload=payload,
        timeout=_gateway_timeout(),
    )
    try:
        asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            result = pool.submit(asyncio.run, coro).result(timeout=_gateway_timeout() + 5)
    except RuntimeError:
        result = asyncio.run(coro)
    # One retry for common transient failures (disconnect, timeout, stale target).
    if _is_retriable_error(result):
        retry_coro = manager.send_command(
            action=action,
            payload=payload,
            timeout=_gateway_timeout(),
        )
        try:
            asyncio.get_running_loop()
            with concurrent.futures.ThreadPoolExecutor() as pool:
                result = pool.submit(asyncio.run, retry_coro).result(timeout=_gateway_timeout() + 5)
        except RuntimeError:
            result = asyncio.run(retry_coro)
    return _format_gateway_result(result)


def get_native_browser_tools() -> list[StructuredTool]:
    return [
        StructuredTool.from_function(
            name="browser_navigate",
            description="在当前浏览器标签页导航到目标 URL（native extension）。",
            func=lambda url: _dispatch("navigate", {"url": url}),
            args_schema=NavigateArgs,
        ),
        StructuredTool.from_function(
            name="browser_click",
            description="点击页面元素（native extension，优先使用 ref 精确定位）。",
            func=lambda ref=None, selector=None, text=None: _dispatch(
                "click",
                {"ref": ref, "selector": selector, "text": text},
            ),
            args_schema=ClickArgs,
        ),
        StructuredTool.from_function(
            name="browser_type",
            description="在输入框输入文本（native extension，优先使用 ref，自动校验写入值）。",
            func=lambda ref=None, selector=None, target_text=None, text="", clear=True: _dispatch(
                "type",
                {"ref": ref, "selector": selector, "target_text": target_text, "text": text, "clear": clear},
            ),
            args_schema=TypeArgs,
        ),
        StructuredTool.from_function(
            name="browser_wait",
            description="等待指定时间（native extension）。",
            func=lambda ms=1000: _dispatch("wait", {"ms": ms}),
            args_schema=WaitArgs,
        ),
        StructuredTool.from_function(
            name="browser_press_key",
            description="发送键盘按键（native extension）。",
            func=lambda key: _dispatch("press_key", {"key": key}),
            args_schema=PressKeyArgs,
        ),
        StructuredTool.from_function(
            name="browser_hover",
            description="鼠标悬停元素（native extension，优先使用 ref 精确定位）。",
            func=lambda ref=None, selector=None, text=None: _dispatch(
                "hover",
                {"ref": ref, "selector": selector, "text": text},
            ),
            args_schema=ClickArgs,
        ),
        StructuredTool.from_function(
            name="browser_select_option",
            description="选择下拉选项（native extension，优先使用 ref，自动校验结果）。",
            func=lambda value, ref=None, selector=None: _dispatch(
                "select_option",
                {"ref": ref, "selector": selector, "value": value},
            ),
            args_schema=SelectOptionArgs,
        ),
        StructuredTool.from_function(
            name="browser_run_plan",
            description="批量执行浏览器步骤（native extension）。用于一次性执行多步操作，减少往返开销。",
            func=lambda steps, stop_on_error=True: _dispatch(
                "run_plan",
                {
                    "steps": [
                        {
                            "action": (s.get("action", "") if isinstance(s, dict) else getattr(s, "action", "")),
                            "payload": (s.get("payload", {}) if isinstance(s, dict) else getattr(s, "payload", {})),
                        }
                        for s in (steps or [])
                    ],
                    "stop_on_error": stop_on_error,
                },
            ),
            args_schema=RunPlanArgs,
        ),
        StructuredTool.from_function(
            name="browser_go_back",
            description="浏览器后退（native extension）。",
            func=lambda: _dispatch("go_back", {}),
        ),
        StructuredTool.from_function(
            name="browser_go_forward",
            description="浏览器前进（native extension）。",
            func=lambda: _dispatch("go_forward", {}),
        ),
        StructuredTool.from_function(
            name="browser_screenshot",
            description="截图当前可见区域（native extension）。",
            func=lambda: _dispatch("screenshot", {}),
        ),
        StructuredTool.from_function(
            name="browser_snapshot",
            description="获取页面快照信息（native extension，包含可交互元素 ref 列表）。",
            func=lambda mode="summary": _dispatch("snapshot", {"mode": mode}),
            args_schema=SnapshotArgs,
        ),
        StructuredTool.from_function(
            name="browser_download_status",
            description="查询下载状态（native extension）。",
            func=lambda keyword=None: _dispatch("download_status", {"keyword": keyword}),
            args_schema=DownloadStatusArgs,
        ),
    ]

