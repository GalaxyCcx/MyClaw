from __future__ import annotations

import os
import unittest
from unittest.mock import patch

try:
    from tools import get_all_tools
except ModuleNotFoundError:
    get_all_tools = None


@unittest.skipIf(get_all_tools is None, "optional runtime deps missing for tools package")
class TestBrowserTransportSwitch(unittest.TestCase):
    @patch("tools._load_native_browser_tools")
    @patch("tools._load_browser_mcp_tools")
    def test_native_extension_path(self, mock_load_mcp, mock_load_native):
        mock_load_native.return_value = []
        mock_load_mcp.return_value = []
        with patch.dict(os.environ, {"BROWSER_TRANSPORT": "native_extension"}, clear=False):
            get_all_tools()
        mock_load_native.assert_called_once()
        mock_load_mcp.assert_not_called()

    @patch("tools._load_native_browser_tools")
    @patch("tools._load_browser_mcp_tools")
    def test_legacy_path(self, mock_load_mcp, mock_load_native):
        mock_load_native.return_value = []
        mock_load_mcp.return_value = []
        with patch.dict(os.environ, {"BROWSER_TRANSPORT": "legacy_mcp"}, clear=False):
            get_all_tools()
        mock_load_mcp.assert_called_once()
        mock_load_native.assert_not_called()


if __name__ == "__main__":
    unittest.main()

