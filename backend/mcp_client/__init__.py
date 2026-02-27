"""MCP client for mcp-chrome bridge integration."""

from mcp_client.chrome_client import MCPChromeClient
from mcp_client.langchain_bridge import get_mcp_chrome_tools

__all__ = ["MCPChromeClient", "get_mcp_chrome_tools"]
