"""Unit tests for Browser MCP client."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from mcp_client.browser_mcp_client import (
    BrowserMCPClient,
    _shorten_error,
    _run_async,
)


class TestShortenError(unittest.TestCase):
    def test_no_tab_connected(self):
        self.assertIn("Connect", _shorten_error(Exception("No tab connected")))

    def test_timeout(self):
        self.assertIn("超时", _shorten_error(Exception("Operation timed out")))

    def test_npx_not_found(self):
        self.assertIn("npx", _shorten_error(Exception("npx not found")))

    def test_generic_truncates(self):
        long_msg = "x" * 300
        self.assertLessEqual(len(_shorten_error(Exception(long_msg))), 202)


class TestBrowserMCPClient(unittest.TestCase):
    @patch("mcp_client.browser_mcp_client._run_async")
    def test_list_tools_connection_error(self, mock_run):
        mock_run.side_effect = ConnectionError("No tab connected")
        client = BrowserMCPClient()
        with self.assertRaises(ConnectionError):
            client.list_tools()

    @patch("mcp_client.browser_mcp_client._run_async")
    def test_call_tool_connection_error(self, mock_run):
        mock_run.side_effect = RuntimeError("No tab connected")
        client = BrowserMCPClient()
        with self.assertRaises(RuntimeError):
            client.call_tool("browser_navigate", {"url": "https://example.com"})

    @patch("mcp_client.browser_mcp_client._run_async")
    def test_list_tools_success(self, mock_run):
        mock_run.return_value = [
            {"name": "browser_navigate", "description": "Navigate", "inputSchema": {}},
        ]
        client = BrowserMCPClient()
        tools = client.list_tools()
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0]["name"], "browser_navigate")

    @patch("mcp_client.browser_mcp_client._run_async")
    def test_call_tool_success(self, mock_run):
        mock_run.return_value = "Navigated successfully"
        client = BrowserMCPClient()
        result = client.call_tool("browser_navigate", {"url": "https://example.com"})
        self.assertEqual(result, "Navigated successfully")


class TestRunAsync(unittest.TestCase):
    def test_run_async_no_loop(self):
        async def simple():
            return 42

        self.assertEqual(_run_async(simple()), 42)


if __name__ == "__main__":
    unittest.main()
