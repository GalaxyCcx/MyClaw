"""Unit tests for Browser MCP LangChain bridge."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from mcp_client.langchain_bridge import (
    CORE_TOOL_NAMES,
    _create_args_model,
    _json_schema_type_to_python,
    get_browser_mcp_tools,
    mcp_tool_to_langchain,
)


class TestJsonSchemaTypeMapping(unittest.TestCase):
    def test_string_type(self):
        self.assertEqual(_json_schema_type_to_python({"type": "string"}), str)

    def test_integer_type(self):
        self.assertEqual(_json_schema_type_to_python({"type": "integer"}), int)


class TestCreateArgsModel(unittest.TestCase):
    def test_creates_model_with_required_field(self):
        schema = {
            "properties": {"url": {"type": "string", "description": "URL"}},
            "required": ["url"],
        }
        model = _create_args_model("browser_navigate", schema)
        self.assertIsNotNone(model)
        self.assertIn("url", model.model_fields)


class TestMCPToolToLangChain(unittest.TestCase):
    def test_converts_tool_with_schema(self):
        client = MagicMock()
        client.call_tool = MagicMock(return_value="ok")
        mcp_tool = {
            "name": "browser_navigate",
            "description": "Navigate to URL",
            "inputSchema": {
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
        }
        tool = mcp_tool_to_langchain(mcp_tool, client)
        self.assertEqual(tool.name, "browser_navigate")
        self.assertIn("Navigate", tool.description)
        result = tool.invoke({"url": "https://example.com"})
        self.assertEqual(result, "ok")
        client.call_tool.assert_called_once_with("browser_navigate", {"url": "https://example.com"})


class TestCoreToolNames(unittest.TestCase):
    def test_core_tools_include_expected(self):
        expected = {
            "browser_navigate",
            "browser_click",
            "browser_snapshot",
            "browser_screenshot",
        }
        self.assertTrue(expected.issubset(CORE_TOOL_NAMES))


class TestGetBrowserMCPTools(unittest.TestCase):
    @unittest.mock.patch("mcp_client.langchain_bridge.BrowserMCPClient")
    def test_returns_langchain_tools(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.list_tools.return_value = [
            {"name": "browser_navigate", "description": "Navigate", "inputSchema": {"properties": {"url": {"type": "string"}}, "required": ["url"]}},
        ]
        mock_client_class.return_value = mock_client

        tools = get_browser_mcp_tools(client=mock_client)
        self.assertGreater(len(tools), 0)
        self.assertEqual(tools[0].name, "browser_navigate")


if __name__ == "__main__":
    unittest.main()
