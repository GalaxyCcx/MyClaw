from __future__ import annotations

import asyncio
import concurrent.futures
import json
import os
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from browser_gateway.image_store import put_browser_image
from browser_gateway.manager import get_browser_gateway_manager
from browser_gateway.oss_store import upload_data_url_and_sign
from browser_gateway.protocol import SUPPORTED_ACTIONS


def _gateway_timeout() -> float:
    return float(os.getenv("BROWSER_GATEWAY_TIMEOUT", "30"))


def _format_gateway_result(result: dict[str, Any]) -> Any:
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

        # Store screenshot out-of-band and expose official multimodal blocks to model:
        # [{"type":"text","text":"..."}, {"type":"image_url","image_url":{"url":"..."}}]
        # URL source:
        # - OSS signed URL (preferred when OSS is configured)
        # - fallback: backend public URL or data URL (no external upload required)
        data_url = payload.get("data_url")
        if isinstance(data_url, str) and data_url:
            image_id = put_browser_image(data_url)
            compact = {"screenshot_id": image_id, "chars": len(data_url)}
            marks = payload.get("marks")
            if isinstance(marks, list):
                compact["marks_count"] = len(marks)
            page = payload.get("page")
            if isinstance(page, dict):
                compact["page"] = {"url": page.get("url", "")}
            meta = payload.get("meta")
            if isinstance(meta, dict):
                compact["meta"] = meta
            text_part = _to_compact_json(compact, max_len=1200)
            send_image = os.getenv("BROWSER_VISION_SEND_IMAGE_TO_LLM", "1").strip().lower() in ("1", "true", "yes")
            mark_limit = max(20, int(os.getenv("BROWSER_VISION_MARKS_TO_LLM_LIMIT", "260")))
            marks_compact: list[dict[str, Any]] = []
            if isinstance(marks, list):
                for m in marks[:mark_limit]:
                    if not isinstance(m, dict):
                        continue
                    txt = str(m.get("text", "") or "")
                    if len(txt) > 80:
                        txt = txt[:80] + "..."
                    marks_compact.append(
                        {
                            "label": m.get("label", ""),
                            "text": txt,
                            "x": m.get("x", 0),
                            "y": m.get("y", 0),
                            "width": m.get("width", 0),
                            "height": m.get("height", 0),
                            "tag": m.get("tag", ""),
                            "role": m.get("role", ""),
                        }
                    )
            llm_json = {
                "summary": compact,
                "marks_total": len(marks) if isinstance(marks, list) else 0,
                "marks_limit": mark_limit,
                "marks": marks_compact,
            }
            if not send_image:
                return _to_compact_json(llm_json, max_len=48000)
            image_url = ""
            image_source = "none"
            prefer_oss = os.getenv("BROWSER_VISION_IMAGE_SOURCE", "oss").strip().lower() == "oss"
            if prefer_oss:
                signed = upload_data_url_and_sign(image_id=image_id, data_url=data_url)
                if signed:
                    image_url = signed
                    image_source = "oss"
            if not image_url:
                public_base = os.getenv("BROWSER_VISION_IMAGE_PUBLIC_BASE_URL", "").strip().rstrip("/")
                if public_base:
                    image_url = f"{public_base}/api/browser/images/{image_id}"
                    image_source = "backend_public"
                else:
                    image_url = data_url
                    image_source = "data_url"
            return [
                {"type": "text", "text": _to_compact_json({**llm_json, "image_source": image_source}, max_len=48000)},
                {"type": "image_url", "image_url": {"url": image_url, "detail": "low"}},
            ]

        snapshot = payload.get("snapshot")
        if isinstance(snapshot, dict):
            return _format_snapshot(snapshot)

        # Return compact JSON for normal action payloads.
        return _to_compact_json(payload)
    return json.dumps(result, ensure_ascii=False)


def _is_retriable_error(result: dict[str, Any]) -> bool:
    return result.get("type") == "error" and bool(result.get("retriable"))


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


class VisionCaptureMarkedArgs(BaseModel):
    max_marks: int = Field(default=1200, description="最多返回标注数量（默认最细模式）")
    dense: bool = Field(default=True, description="是否开启高密度标注模式（默认开启）")
    wait_stable: bool = Field(default=True, description="截图前是否等待稳定")
    stable_timeout_ms: int = Field(default=3000, description="稳定检测超时（毫秒）")
    stable_interval_ms: int = Field(default=250, description="稳定检测轮询间隔（毫秒）")
    stable_rounds: int = Field(default=2, description="稳定判定需连续满足轮数")
    stable_min_wait_ms: int = Field(default=0, description="稳定前最少附加等待（毫秒）")
    mark_render_timeout_ms: int = Field(default=800, description="标注渲染等待超时（毫秒）")
    mark_render_interval_ms: int = Field(default=120, description="标注渲染轮询间隔（毫秒）")
    mark_render_min_wait_ms: int = Field(default=180, description="标注渲染最少附加等待（毫秒）")


class VisionClickLabelArgs(BaseModel):
    label: str = Field(..., description="目标标注编号，如 a1")


class VisionTypeLabelArgs(BaseModel):
    label: str = Field(..., description="目标标注编号，如 a2")
    text: str = Field(..., description="输入文本")
    clear: bool = Field(default=True, description="是否先清空")
    press_enter: bool = Field(default=False, description="输入后是否回车")


class VisionScrollByArgs(BaseModel):
    dy: int = Field(..., description="滚动像素（正数向下，负数向上）")


class VisionWaitStableArgs(BaseModel):
    timeout_ms: int = Field(default=3000, description="稳定检测超时（毫秒）")
    interval_ms: int = Field(default=250, description="稳定检测轮询间隔（毫秒）")
    settle_rounds: int = Field(default=2, description="稳定判定需连续满足轮数")
    min_wait_ms: int = Field(default=0, description="稳定前最少附加等待（毫秒）")


class BrowserActionStepArgs(BaseModel):
    action: str = Field(..., description="V3 扩展动作名")
    payload: dict[str, Any] = Field(default_factory=dict, description="步骤参数")


class BrowserRunActionsArgs(BaseModel):
    steps: list[BrowserActionStepArgs] = Field(..., description="按顺序执行的动作步骤列表")
    stop_on_error: bool = Field(default=True, description="任一步失败时是否立即停止")


DISABLED_MODEL_ACTIONS = {"wait"}


def _vision_capture_payload(kwargs: dict[str, Any]) -> dict[str, Any]:
    defaults = {
        "max_marks": 1200,
        "dense": True,
        "wait_stable": True,
        "stable_timeout_ms": 3000,
        "stable_interval_ms": 250,
        "stable_rounds": 2,
        "stable_min_wait_ms": 0,
        "mark_render_timeout_ms": 800,
        "mark_render_interval_ms": 120,
        "mark_render_min_wait_ms": 180,
    }
    out = dict(defaults)
    for k, v in (kwargs or {}).items():
        if v is not None:
            out[k] = v
    return out


def _dispatch(action: str, payload: dict[str, Any]) -> str:
    if action in DISABLED_MODEL_ACTIONS:
        return "错误: 动作 `wait` 已禁用，请直接执行下一步或使用 vision_wait_stable。"

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


def _dispatch_steps(steps: list[Any], stop_on_error: bool = True) -> str:
    actions_log: list[dict[str, Any]] = []
    ok = True
    for idx, step in enumerate(steps or []):
        if isinstance(step, dict):
            action = str(step.get("action") or "").strip()
            payload = step.get("payload")
        else:
            action = str(getattr(step, "action", "")).strip()
            payload = getattr(step, "payload", {})
        if not action:
            actions_log.append(
                {
                    "index": idx,
                    "action": "",
                    "result": {
                        "type": "error",
                        "message": "missing action",
                        "retriable": False,
                    },
                }
            )
            ok = False
            if stop_on_error:
                break
            continue
        if action not in SUPPORTED_ACTIONS:
            actions_log.append(
                {
                    "index": idx,
                    "action": action,
                    "result": {
                        "type": "error",
                        "message": f"unsupported action: {action}",
                        "retriable": False,
                    },
                }
            )
            ok = False
            if stop_on_error:
                break
            continue
        if action in DISABLED_MODEL_ACTIONS:
            actions_log.append(
                {
                    "index": idx,
                    "action": action,
                    "result": {
                        "type": "error",
                        "message": "action `wait` is disabled for model tools",
                        "retriable": False,
                    },
                }
            )
            ok = False
            if stop_on_error:
                break
            continue
        manager = get_browser_gateway_manager()
        coro = manager.send_command(
            action=action,
            payload=payload if isinstance(payload, dict) else {},
            timeout=_gateway_timeout(),
        )
        try:
            asyncio.get_running_loop()
            with concurrent.futures.ThreadPoolExecutor() as pool:
                result = pool.submit(asyncio.run, coro).result(timeout=_gateway_timeout() + 5)
        except RuntimeError:
            result = asyncio.run(coro)
        actions_log.append({"index": idx, "action": action, "result": result})
        if result.get("type") == "error":
            ok = False
            if stop_on_error:
                break
    return _to_compact_json({"ok": ok, "steps": actions_log}, max_len=5000)


def get_native_browser_tools() -> list[StructuredTool]:
    return [
        StructuredTool.from_function(
            name="browser_navigate",
            description="在当前浏览器标签页导航到目标 URL（V3 扩展）。",
            func=lambda url: _dispatch("navigate", {"url": url}),
            args_schema=NavigateArgs,
        ),
        StructuredTool.from_function(
            name="browser_get_url",
            description="获取当前标签页 URL（V3 扩展）。",
            func=lambda: _dispatch("get_url", {}),
        ),
        StructuredTool.from_function(
            name="browser_screenshot",
            description="截图当前可见区域（V3 扩展）。",
            func=lambda: _dispatch("screenshot", {}),
        ),
        StructuredTool.from_function(
            name="browser_go_back",
            description="浏览器后退（V3 扩展）。",
            func=lambda: _dispatch("go_back", {}),
        ),
        StructuredTool.from_function(
            name="browser_go_forward",
            description="浏览器前进（V3 扩展）。",
            func=lambda: _dispatch("go_forward", {}),
        ),
        StructuredTool.from_function(
            name="browser_vision_capture_marked",
            description="截图并返回标注元素（SoM，含 marks JSON）。",
            func=lambda **kwargs: _dispatch("vision_capture_marked", _vision_capture_payload(kwargs)),
            args_schema=VisionCaptureMarkedArgs,
        ),
        StructuredTool.from_function(
            name="browser_vision_click_label",
            description="按标注编号点击元素（如 a1）。",
            func=lambda label: _dispatch("vision_click_label", {"label": label}),
            args_schema=VisionClickLabelArgs,
        ),
        StructuredTool.from_function(
            name="browser_vision_type_label",
            description="按标注编号输入文本（如 a2）。",
            func=lambda label, text, clear=True, press_enter=False: _dispatch(
                "vision_type_label",
                {"label": label, "text": text, "clear": clear, "press_enter": press_enter},
            ),
            args_schema=VisionTypeLabelArgs,
        ),
        StructuredTool.from_function(
            name="browser_vision_clear_marks",
            description="清理当前页面的标注覆盖层。",
            func=lambda: _dispatch("vision_clear_marks", {}),
        ),
        StructuredTool.from_function(
            name="browser_vision_scroll_by",
            description="按像素滚动当前页面。",
            func=lambda dy: _dispatch("vision_scroll_by", {"dy": dy}),
            args_schema=VisionScrollByArgs,
        ),
        StructuredTool.from_function(
            name="browser_vision_wait_stable",
            description="等待页面稳定后再继续。",
            func=lambda timeout_ms=3000, interval_ms=250, settle_rounds=2, min_wait_ms=0: _dispatch(
                "vision_wait_stable",
                {
                    "timeout_ms": timeout_ms,
                    "interval_ms": interval_ms,
                    "settle_rounds": settle_rounds,
                    "min_wait_ms": min_wait_ms,
                },
            ),
            args_schema=VisionWaitStableArgs,
        ),
        StructuredTool.from_function(
            name="browser_run_actions",
            description="按顺序执行一组 V3 扩展动作（tool call 批量下发）。",
            func=lambda steps, stop_on_error=True: _dispatch_steps(steps=steps, stop_on_error=stop_on_error),
            args_schema=BrowserRunActionsArgs,
        ),
    ]

