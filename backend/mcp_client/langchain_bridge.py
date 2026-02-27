"""Bridge MCP Chrome tools to LangChain tools."""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import create_model

from mcp_client.chrome_client import MCPChromeClient

logger = logging.getLogger(__name__)

# Core tools for enterprise scenarios (subset to control token usage)
CORE_TOOL_NAMES = {
    "get_windows_and_tabs",
    "chrome_navigate",
    "chrome_switch_tab",
    "chrome_get_web_content",
    "chrome_get_interactive_elements",
    "chrome_click_element",
    "chrome_fill_or_select",
    "chrome_screenshot",
    "chrome_keyboard",
}


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


def mcp_tool_to_langchain(mcp_tool: dict[str, Any], client: MCPChromeClient) -> StructuredTool:
    """Convert an MCP tool definition to a LangChain StructuredTool."""
    name = mcp_tool.get("name", "")
    description = mcp_tool.get("description", "") or f"MCP Chrome tool: {name}"
    schema = mcp_tool.get("inputSchema", {})

    args_model = None
    try:
        args_model = _create_args_model(name, schema)
    except Exception as e:
        logger.warning("Failed to create args model for %s: %s, using generic", name, e)

    def _invoke(**kwargs) -> str:
        return client.call_tool(name, kwargs)

    return StructuredTool(
        name=name,
        description=description,
        args_schema=args_model,
        func=_invoke,
    )


def get_mcp_chrome_tools(
    client: MCPChromeClient | None = None,
    tool_filter: set[str] | None = None,
) -> list[StructuredTool]:
    """
    Fetch tools from mcp-chrome and convert to LangChain tools.
    If tool_filter is provided, only include those tools.
    """
    client = client or MCPChromeClient()
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
