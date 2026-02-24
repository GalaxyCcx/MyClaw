from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any


@dataclass
class ContextPolicy:
    reserve_tokens: int
    soft_threshold_tokens: int
    preserve_recent_turns: int
    max_retry_on_overflow: int
    max_tool_result_chars: int


def load_context_policy() -> ContextPolicy:
    return ContextPolicy(
        reserve_tokens=max(1000, int(os.getenv("CTX_RESERVE_TOKENS", "20000"))),
        soft_threshold_tokens=max(0, int(os.getenv("CTX_SOFT_THRESHOLD_TOKENS", "4000"))),
        preserve_recent_turns=max(1, int(os.getenv("CTX_PRESERVE_RECENT_TURNS", "4"))),
        max_retry_on_overflow=max(0, int(os.getenv("CTX_MAX_RETRY_ON_OVERFLOW", "1"))),
        max_tool_result_chars=max(500, int(os.getenv("CTX_MAX_TOOL_RESULT_CHARS", "4000"))),
    )


def _estimate_text_tokens(text: str) -> int:
    if not text:
        return 0
    # Heuristic: 1 token ~= 4 chars for mixed zh/en payloads.
    return max(1, len(text) // 4)


def _extract_message_text(msg: Any) -> str:
    if isinstance(msg, dict):
        content = str(msg.get("content", "") or "")
        tool_calls = msg.get("tool_calls")
        if tool_calls:
            try:
                content += "\n" + json.dumps(tool_calls, ensure_ascii=False)
            except Exception:
                content += "\n" + str(tool_calls)
        return content

    content = str(getattr(msg, "content", "") or "")
    tool_calls = getattr(msg, "tool_calls", None)
    if tool_calls:
        try:
            content += "\n" + json.dumps(tool_calls, ensure_ascii=False)
        except Exception:
            content += "\n" + str(tool_calls)
    return content


def estimate_messages_tokens(messages: list[Any], model_name: str | None = None) -> int:
    del model_name  # Reserved for future model-specific estimation.
    total = 0
    for msg in messages:
        text = _extract_message_text(msg)
        total += _estimate_text_tokens(text) + 10  # per-message overhead
    return total + 50  # request envelope overhead


def compute_thresholds(context_limit: int, reserve_tokens: int, soft_threshold: int) -> dict[str, int]:
    safe_context_limit = max(1024, context_limit)
    safe_reserve = min(max(512, reserve_tokens), safe_context_limit - 256)
    preflight_limit = max(256, safe_context_limit - safe_reserve - max(0, soft_threshold))
    target_tokens = max(128, safe_context_limit - safe_reserve)
    return {
        "context_limit": safe_context_limit,
        "reserve_tokens": safe_reserve,
        "soft_threshold_tokens": max(0, soft_threshold),
        "preflight_limit": preflight_limit,
        "target_tokens": target_tokens,
    }
