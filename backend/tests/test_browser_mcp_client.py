"""Unit tests for Browser MCP client."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from mcp_client.browser_mcp_client import (
    BrowserMCPClient,
    _classify_error,
    is_extension_not_connected_error,
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


class TestErrorClassification(unittest.TestCase):
    def test_extension_not_connected_markers(self):
        self.assertTrue(is_extension_not_connected_error("No connection to browser extension"))
        self.assertEqual(_classify_error("No tab connected"), "extension_not_connected")

    def test_runtime_missing(self):
        self.assertEqual(_classify_error("npx not found"), "runtime_missing")

    def test_timeout(self):
        self.assertEqual(_classify_error("operation timed out"), "timeout")


class TestBrowserMCPClient(unittest.TestCase):
    @patch("mcp_client.browser_mcp_client._get_shared_session")
    def test_list_tools_connection_error(self, mock_get_session):
        mock_session = MagicMock()
        mock_session.list_tools.side_effect = ConnectionError("No tab connected")
        mock_get_session.return_value = mock_session
        client = BrowserMCPClient()
        with self.assertRaises(ConnectionError):
            client.list_tools()
        self.assertTrue(mock_session.reset.called)

    @patch("mcp_client.browser_mcp_client._get_shared_session")
    def test_call_tool_connection_error(self, mock_get_session):
        mock_session = MagicMock()
        mock_session.call_tool.side_effect = RuntimeError("No tab connected")
        mock_get_session.return_value = mock_session
        client = BrowserMCPClient()
        with self.assertRaises(RuntimeError):
            client.call_tool("browser_navigate", {"url": "https://example.com"})
        self.assertTrue(mock_session.reset.called)

    @patch("mcp_client.browser_mcp_client._get_shared_session")
    def test_list_tools_success(self, mock_get_session):
        mock_session = MagicMock()
        mock_session.list_tools.return_value = [
            {"name": "browser_navigate", "description": "Navigate", "inputSchema": {}},
        ]
        mock_get_session.return_value = mock_session
        client = BrowserMCPClient()
        tools = client.list_tools()
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0]["name"], "browser_navigate")

    @patch("mcp_client.browser_mcp_client._get_shared_session")
    def test_call_tool_success(self, mock_get_session):
        mock_session = MagicMock()
        mock_session.call_tool.return_value = "Navigated successfully"
        mock_get_session.return_value = mock_session
        client = BrowserMCPClient()
        result = client.call_tool("browser_navigate", {"url": "https://example.com"})
        self.assertEqual(result, "Navigated successfully")

    @patch("mcp_client.browser_mcp_client._get_shared_session")
    def test_probe_extension_connection_false(self, mock_get_session):
        mock_session = MagicMock()
        mock_session.call_tool.return_value = (
            "Error: No connection to browser extension. Connect a tab first."
        )
        mock_get_session.return_value = mock_session
        ok, detail = BrowserMCPClient().probe_extension_connection()
        self.assertFalse(ok)
        self.assertIn("No connection", detail)


class TestRunAsync(unittest.TestCase):
    def test_run_async_no_loop(self):
        async def simple():
            return 42

        self.assertEqual(_run_async(simple()), 42)


if __name__ == "__main__":
    unittest.main()
