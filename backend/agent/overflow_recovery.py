from __future__ import annotations


OVERFLOW_KEYWORDS = [
    "context length",
    "maximum context",
    "context window",
    "token limit",
    "too many tokens",
    "prompt is too long",
    "maximum tokens",
    "overflow",
    "上下文",
    "超出",
    "超过",
    "token 过多",
]


def is_context_overflow(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(k in text for k in OVERFLOW_KEYWORDS)
