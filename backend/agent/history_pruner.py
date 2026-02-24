from __future__ import annotations

from typing import Any

from agent.context_budget import estimate_messages_tokens


def _message_role(msg: Any) -> str:
    if isinstance(msg, dict):
        return str(msg.get("role", "") or "")
    return str(getattr(msg, "type", "") or "")


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


def _truncate_old_tool_messages(messages: list[Any], max_tool_result_chars: int) -> tuple[list[Any], int]:
    truncated = 0
    updated: list[Any] = []
    for msg in messages:
        role = _message_role(msg)
        if role != "tool":
            updated.append(msg)
            continue

        if isinstance(msg, dict):
            content = str(msg.get("content", "") or "")
        else:
            content = str(getattr(msg, "content", "") or "")
        if len(content) <= max_tool_result_chars:
            updated.append(msg)
            continue

        truncated += 1
        short_content = (
            content[:max_tool_result_chars]
            + f"\n\n... [context_pruner truncated {len(content) - max_tool_result_chars} chars]"
        )
        if isinstance(msg, dict):
            cloned = dict(msg)
            cloned["content"] = short_content
            updated.append(cloned)
        else:
            try:
                cloned = msg.model_copy(deep=True)
                cloned.content = short_content
                updated.append(cloned)
            except Exception:
                updated.append(msg)
    return updated, truncated


def prune_history(
    history: list[Any],
    target_tokens: int,
    preserve_recent_turns: int,
    model_name: str | None = None,
    max_tool_result_chars: int = 4000,
) -> tuple[list[Any], dict[str, int]]:
    if not history:
        return history, {"dropped_messages": 0, "truncated_messages": 0, "before_tokens": 0, "after_tokens": 0}

    before_tokens = estimate_messages_tokens(history, model_name=model_name)
    if before_tokens <= target_tokens:
        return history, {"dropped_messages": 0, "truncated_messages": 0, "before_tokens": before_tokens, "after_tokens": before_tokens}

    turns = _split_turns(history)
    preserve_recent_turns = max(1, preserve_recent_turns)

    if len(turns) <= preserve_recent_turns:
        return history, {"dropped_messages": 0, "truncated_messages": 0, "before_tokens": before_tokens, "after_tokens": before_tokens}

    keep_tail = turns[-preserve_recent_turns:]
    keep_head = turns[:-preserve_recent_turns]

    flattened_tail = [msg for turn in keep_tail for msg in turn]
    flattened_head = [msg for turn in keep_head for msg in turn]
    truncated_head, truncated_messages = _truncate_old_tool_messages(flattened_head, max_tool_result_chars=max_tool_result_chars)
    candidate = truncated_head + flattened_tail

    # If still too large, drop oldest complete turns.
    dropped_messages = 0
    if estimate_messages_tokens(candidate, model_name=model_name) > target_tokens:
        remaining_head = keep_head
        while remaining_head:
            oldest = remaining_head[0]
            remaining_head = remaining_head[1:]
            dropped_messages += len(oldest)
            merged_head = [msg for turn in remaining_head for msg in turn]
            merged_head, _ = _truncate_old_tool_messages(merged_head, max_tool_result_chars=max_tool_result_chars)
            candidate = merged_head + flattened_tail
            if estimate_messages_tokens(candidate, model_name=model_name) <= target_tokens:
                break

    after_tokens = estimate_messages_tokens(candidate, model_name=model_name)
    if dropped_messages == 0:
        dropped_messages = max(0, len(history) - len(candidate))
    return candidate, {
        "dropped_messages": dropped_messages,
        "truncated_messages": truncated_messages,
        "before_tokens": before_tokens,
        "after_tokens": after_tokens,
    }
