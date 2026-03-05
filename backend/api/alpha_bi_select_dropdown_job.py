"""Alpha BI 单选下拉选择 Job 辅助逻辑。"""

from __future__ import annotations


def match_dropdown_option(options: list[dict], target_value: str) -> dict | None:
    """从 options 中匹配目标选项：优先精确匹配，其次包含匹配。"""
    target = str(target_value or "").strip()
    if not target:
        return None
    target_norm = target.replace(" ", "")
    exact_match = None
    contains_match = None
    for opt in options:
        if not isinstance(opt, dict):
            continue
        text = str(opt.get("text") or "").strip()
        text_norm = text.replace(" ", "")
        if text_norm == target_norm:
            exact_match = opt
            break
        if target_norm in text_norm:
            contains_match = opt
    return exact_match or contains_match
