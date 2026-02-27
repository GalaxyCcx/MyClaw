"""Integration tests for MCP Chrome. Require mcp-chrome-bridge + extension to be running."""

from __future__ import annotations

import os
import unittest


def _bridge_available() -> bool:
    """Check if mcp-chrome-bridge is reachable."""
    try:
        from mcp_client import MCPChromeClient

        client = MCPChromeClient()
        client.list_tools()
        return True
    except Exception:
        return False


@unittest.skipUnless(
    os.getenv("MCP_CHROME_INTEGRATION_TEST") == "1",
    "Set MCP_CHROME_INTEGRATION_TEST=1 and run bridge to enable",
)
class TestMCPChromeIntegration(unittest.TestCase):
    """Integration tests - run only when bridge is available."""

    def test_list_tools_returns_non_empty(self):
        from mcp_client import MCPChromeClient

        client = MCPChromeClient()
        tools = client.list_tools()
        self.assertIsInstance(tools, list)
        self.assertGreater(len(tools), 0)
        names = [t.get("name") for t in tools]
        self.assertIn("chrome_navigate", names)

    def test_chrome_navigate_can_be_called(self):
        from mcp_client import MCPChromeClient

        if not _bridge_available():
            self.skipTest("Bridge not available")
        client = MCPChromeClient()
        result = client.call_tool("chrome_navigate", {"url": "https://example.com"})
        self.assertIsInstance(result, str)

    def test_get_mcp_chrome_tools_returns_langchain_tools(self):
        from mcp_client import get_mcp_chrome_tools

        if not _bridge_available():
            self.skipTest("Bridge not available")
        tools = get_mcp_chrome_tools()
        self.assertGreater(len(tools), 0)
        from langchain_core.tools import BaseTool

        for t in tools:
            self.assertIsInstance(t, BaseTool)
            self.assertTrue(hasattr(t, "name"))
            self.assertTrue(hasattr(t, "invoke") or hasattr(t, "run"))


class TestMCPChromeToolLoading(unittest.TestCase):
    """Test tool loading logic (no bridge required)."""

    def test_builtin_tools_always_include_core(self):
        """Core tools like read_file are always present."""
        from tools import BUILTIN_TOOLS

        names = [getattr(t, "name", str(t)) for t in BUILTIN_TOOLS]
        self.assertIn("read_file", names)
        self.assertIn("web_fetch", names)
