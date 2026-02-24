from __future__ import annotations

from typing import Any

from agent.context_budget import estimate_messages_tokens


def _message_role(msg: Any) -> str:
    if isinstance(msg, dict):
        return str(msg.get("role", "") or "")
    return str(getattr(msg, "type", "") or "")


def _message_content(msg: Any) -> str:
    if isinstance(msg, dict):
        return str(msg.get("content", "") or "")
    return str(getattr(msg, "content", "") or "")


def _split_turns(history: list[Any]) -> list[list[Any]]:
    turns: list[list[Any]] = []
    current: list[Any] = []
    for msg in history:
        role = _message_role(msg)
        if role == "user" and current:
            turns.append(current)
            current = [msg]
        else:
            current.append(msg)
    if current:
        turns.append(current)
    return turns


def _summarize_turn(turn: list[Any], idx: int) -> str:
    user_text = ""
    answer_text = ""
    tool_count = 0
    for msg in turn:
        role = _message_role(msg)
        content = _message_content(msg).strip()
        if role == "user" and content and not user_text:
            user_text = content[:180]
        elif role in ("ai", "assistant") and content:
            answer_text = content[:220]
        elif role == "tool":
            tool_count += 1
    if not user_text:
        user_text = "(无用户文本)"
    if not answer_text:
        answer_text = "(无最终回答文本)"
    return f"- Turn {idx}: 用户={user_text} | 工具调用={tool_count} | 结论={answer_text}"


def compact_history(
    history: list[Any],
    preserve_recent_turns: int,
    model_name: str | None = None,
) -> tuple[list[Any], dict[str, int]]:
    if not history:
        return history, {"compacted_turns": 0, "dropped_messages": 0, "summary_chars": 0, "before_tokens": 0, "after_tokens": 0}

    before_tokens = estimate_messages_tokens(history, model_name=model_name)
    turns = _split_turns(history)
    preserve_recent_turns = max(1, preserve_recent_turns)
    if len(turns) <= preserve_recent_turns:
        return history, {"compacted_turns": 0, "dropped_messages": 0, "summary_chars": 0, "before_tokens": before_tokens, "after_tokens": before_tokens}

    old_turns = turns[:-preserve_recent_turns]
    recent_turns = turns[-preserve_recent_turns:]
    summary_lines = [
        "[Context Compact Summary]",
        "以下是被压缩历史轮次的结构化摘要，请基于它继续任务：",
    ]
    for i, turn in enumerate(old_turns, start=1):
        summary_lines.append(_summarize_turn(turn, i))
    summary_text = "\n".join(summary_lines)
    summary_message = {"role": "system", "content": summary_text}

    compacted = [summary_message]
    for turn in recent_turns:
        compacted.extend(turn)

    after_tokens = estimate_messages_tokens(compacted, model_name=model_name)
    dropped_messages = max(0, len(history) - len(compacted))
    return compacted, {
        "compacted_turns": len(old_turns),
        "dropped_messages": dropped_messages,
        "summary_chars": len(summary_text),
        "before_tokens": before_tokens,
        "after_tokens": after_tokens,
    }
