"""Integration tests for Browser MCP. Require Browser MCP extension + Connect."""

from __future__ import annotations

import os
import unittest


def _browser_mcp_available() -> bool:
    """Check if Browser MCP is reachable (extension connected)."""
    try:
        from mcp_client import BrowserMCPClient

        client = BrowserMCPClient()
        ok, _ = client.probe_extension_connection()
        return ok
    except Exception:
        return False


@unittest.skipUnless(
    os.getenv("BROWSER_MCP_INTEGRATION_TEST") == "1",
    "Set BROWSER_MCP_INTEGRATION_TEST=1 and Connect extension to enable",
)
class TestBrowserMCPIntegration(unittest.TestCase):
    """Integration tests - run only when Browser MCP extension is connected."""

    def test_list_tools_returns_non_empty(self):
        from mcp_client import BrowserMCPClient

        client = BrowserMCPClient()
        tools = client.list_tools()
        self.assertIsInstance(tools, list)
        self.assertGreater(len(tools), 0)
        names = [t.get("name") for t in tools]
        self.assertIn("browser_navigate", names)

    def test_browser_navigate_can_be_called(self):
        from mcp_client import BrowserMCPClient

        if not _browser_mcp_available():
            self.skipTest("Browser MCP not available")
        client = BrowserMCPClient()
        result = client.call_tool("browser_navigate", {"url": "https://example.com"})
        self.assertIsInstance(result, str)

    def test_get_browser_mcp_tools_returns_langchain_tools(self):
        from mcp_client import get_browser_mcp_tools

        if not _browser_mcp_available():
            self.skipTest("Browser MCP not available")
        tools = get_browser_mcp_tools()
        self.assertGreater(len(tools), 0)
        from langchain_core.tools import BaseTool

        for t in tools:
            self.assertIsInstance(t, BaseTool)
            self.assertTrue(hasattr(t, "name"))
            self.assertTrue(hasattr(t, "invoke") or hasattr(t, "run"))


class TestToolLoading(unittest.TestCase):
    """Test tool loading logic (no Browser MCP required)."""

    def test_builtin_tools_always_include_core(self):
        """Core tools like read_file are always present."""
        from tools import BUILTIN_TOOLS

        names = [getattr(t, "name", str(t)) for t in BUILTIN_TOOLS]
        self.assertIn("read_file", names)
        self.assertIn("web_fetch", names)
