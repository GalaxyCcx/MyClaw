"""Bridge Browser MCP tools to LangChain tools."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from langchain_core.tools import StructuredTool
from pydantic import create_model

from mcp_client.browser_mcp_client import BrowserMCPClient

logger = logging.getLogger(__name__)

# Core Browser MCP tools (subset to control token usage)
CORE_TOOL_NAMES = {
    "browser_navigate",
    "browser_click",
    "browser_type",
    "browser_snapshot",
    "browser_screenshot",
    "browser_hover",
    "browser_wait",
    "browser_go_back",
    "browser_go_forward",
    "browser_press_key",
    "browser_select_option",
}

# Heavy tools: per-tool max chars before truncate+save
HEAVY_TOOL_MAX_CHARS = {
    "browser_snapshot": 3500,
}

TOOL_OUTPUTS_DIR = Path(__file__).resolve().parent.parent / "memory" / "tool_outputs"


def _truncate_and_save_tool_result(name: str, raw: str) -> str:
    """Truncate tool result and save full content to memory/tool_outputs for agent to read_file."""
    max_chars = HEAVY_TOOL_MAX_CHARS.get(
        name,
        int(os.getenv("CTX_MAX_TOOL_RESULT_CHARS", "4000")),
    )
    if len(raw) <= max_chars:
        return raw

    TOOL_OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = name.replace("browser_", "").replace("_", "-")
    fname = f"{safe_name}_{ts}_{uuid4().hex[:8]}.txt"
    file_path = TOOL_OUTPUTS_DIR / fname
    try:
        file_path.write_text(raw, encoding="utf-8")
    except Exception as e:
        logger.warning("Failed to save truncated tool output to %s: %s", file_path, e)
        return raw[:max_chars] + f"\n\n...[已截断 {len(raw) - max_chars} 字符]"

    rel_path = f"backend/memory/tool_outputs/{fname}"
    return (
        raw[:max_chars]
        + f"\n\n...[已截断 {len(raw) - max_chars} 字符] 完整内容已保存至 {rel_path}，可用 read_file(path) 查看。"
    )


def _json_schema_type_to_python(prop: dict) -> type:
    """Map JSON Schema type to Python type."""
    t = prop.get("type", "string")
    if t == "integer":
        return int
    if t == "number":
        return float
    if t == "boolean":
        return bool
    if t == "array":
        return list
    if t == "object":
        return dict
    return str


def _create_args_model(name: str, schema: dict) -> type | None:
    """Create a Pydantic model from JSON Schema for tool arguments."""
    props = schema.get("properties", {})
    if not props:
        return None

    required = set(schema.get("required", []))
    fields = {}
    for k, v in props.items():
        py_type = _json_schema_type_to_python(v)
        if k in required:
            fields[k] = (py_type, ...)
        else:
            default = v.get("default")
            fields[k] = (py_type, default)

    safe_name = "".join(c if c.isalnum() else "_" for c in name)
    return create_model(f"MCP_{safe_name}Args", **fields)


def mcp_tool_to_langchain(mcp_tool: dict[str, Any], client: BrowserMCPClient) -> StructuredTool:
    """Convert an MCP tool definition to a LangChain StructuredTool."""
    name = mcp_tool.get("name", "")
    description = mcp_tool.get("description", "") or f"Browser MCP tool: {name}"
    schema = mcp_tool.get("inputSchema", {})

    args_model = None
    try:
        args_model = _create_args_model(name, schema)
    except Exception as e:
        logger.warning("Failed to create args model for %s: %s, using generic", name, e)

    def _invoke(**kwargs) -> str:
        raw = client.call_tool(name, kwargs)
        return _truncate_and_save_tool_result(name, raw)

    return StructuredTool(
        name=name,
        description=description,
        args_schema=args_model,
        func=_invoke,
    )


def get_browser_mcp_tools(
    client: BrowserMCPClient | None = None,
    tool_filter: set[str] | None = None,
) -> list[StructuredTool]:
    """
    Fetch tools from Browser MCP and convert to LangChain tools.
    If tool_filter is provided, only include those tools.
    """
    client = client or BrowserMCPClient()
    tool_filter = tool_filter or CORE_TOOL_NAMES

    tools_def = client.list_tools()
    result = []
    for t in tools_def:
        name = t.get("name", "")
        if name and (not tool_filter or name in tool_filter):
            try:
                result.append(mcp_tool_to_langchain(t, client))
            except Exception as e:
                logger.warning("Skip tool %s: %s", name, e)
    return result
