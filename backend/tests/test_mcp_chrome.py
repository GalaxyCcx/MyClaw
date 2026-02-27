"""Unit tests for MCP Chrome client and LangChain bridge."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from mcp_client.chrome_client import MCPChromeClient, _parse_tool_result
from mcp_client.langchain_bridge import (
    CORE_TOOL_NAMES,
    _create_args_model,
    _json_schema_type_to_python,
    mcp_tool_to_langchain,
)


class TestParseToolResult(unittest.TestCase):
    def test_parse_text_content(self):
        class TextBlock:
            type = "text"
            text = "hello world"

        result = MagicMock()
        result.content = [TextBlock()]
        self.assertEqual(_parse_tool_result(result), "hello world")

    def test_parse_image_content_omitted(self):
        class ImageBlock:
            type = "image"
            data = b"fake"

        result = MagicMock()
        result.content = [ImageBlock()]
        self.assertIn("图片", _parse_tool_result(result))

    def test_parse_empty_content(self):
        result = MagicMock()
        result.content = []
        self.assertEqual(_parse_tool_result(result), "(无返回内容)")


class TestJsonSchemaTypeMapping(unittest.TestCase):
    def test_string_type(self):
        self.assertEqual(_json_schema_type_to_python({"type": "string"}), str)

    def test_integer_type(self):
        self.assertEqual(_json_schema_type_to_python({"type": "integer"}), int)

    def test_number_type(self):
        self.assertEqual(_json_schema_type_to_python({"type": "number"}), float)

    def test_boolean_type(self):
        self.assertEqual(_json_schema_type_to_python({"type": "boolean"}), bool)

    def test_array_type(self):
        self.assertEqual(_json_schema_type_to_python({"type": "array"}), list)

    def test_object_type(self):
        self.assertEqual(_json_schema_type_to_python({"type": "object"}), dict)

    def test_missing_type_defaults_to_str(self):
        self.assertEqual(_json_schema_type_to_python({}), str)


class TestCreateArgsModel(unittest.TestCase):
    def test_creates_model_with_required_field(self):
        schema = {
            "properties": {"url": {"type": "string", "description": "URL"}},
            "required": ["url"],
        }
        model = _create_args_model("test", schema)
        self.assertIsNotNone(model)
        self.assertIn("url", model.model_fields)

    def test_creates_model_with_optional_field(self):
        schema = {
            "properties": {"optional": {"type": "string"}},
        }
        model = _create_args_model("test", schema)
        self.assertIsNotNone(model)
        self.assertIn("optional", model.model_fields)

    def test_returns_none_for_empty_properties(self):
        schema = {"properties": {}}
        self.assertIsNone(_create_args_model("test", schema))


class TestMCPChromeClient(unittest.TestCase):
    def test_list_tools_connection_error(self):
        client = MCPChromeClient(url="http://127.0.0.1:19999/mcp")
        with self.assertRaises((ConnectionError, OSError, Exception)):
            client.list_tools()

    def test_call_tool_connection_error(self):
        client = MCPChromeClient(url="http://127.0.0.1:19999/mcp")
        with self.assertRaises((ConnectionError, OSError, RuntimeError, Exception)):
            client.call_tool("chrome_navigate", {"url": "https://example.com"})


class TestMCPToolToLangChain(unittest.TestCase):
    def test_converts_tool_with_schema(self):
        client = MagicMock()
        client.call_tool = MagicMock(return_value="ok")
        mcp_tool = {
            "name": "chrome_navigate",
            "description": "Navigate to URL",
            "inputSchema": {
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
        }
        tool = mcp_tool_to_langchain(mcp_tool, client)
        self.assertEqual(tool.name, "chrome_navigate")
        self.assertIn("Navigate", tool.description)
        result = tool.invoke({"url": "https://example.com"})
        self.assertEqual(result, "ok")
        client.call_tool.assert_called_once_with("chrome_navigate", {"url": "https://example.com"})

    def test_converts_tool_without_schema(self):
        client = MagicMock()
        client.call_tool = MagicMock(return_value="done")
        mcp_tool = {
            "name": "get_windows_and_tabs",
            "description": "List tabs",
            "inputSchema": {"properties": {}},
        }
        tool = mcp_tool_to_langchain(mcp_tool, client)
        self.assertEqual(tool.name, "get_windows_and_tabs")
        result = tool.invoke({})
        self.assertEqual(result, "done")


class TestCoreToolNames(unittest.TestCase):
    def test_core_tools_include_expected(self):
        expected = {
            "chrome_navigate",
            "chrome_get_web_content",
            "chrome_click_element",
            "chrome_fill_or_select",
        }
        self.assertTrue(expected.issubset(CORE_TOOL_NAMES))


if __name__ == "__main__":
    unittest.main()
