from __future__ import annotations

import unittest
from unittest.mock import patch

from browser_gateway.tools import get_native_browser_tools


class TestBrowserGatewayTools(unittest.TestCase):
    @patch("browser_gateway.tools._dispatch")
    def test_contract_command_result(self, mock_dispatch):
        mock_dispatch.return_value = "ok"
        tools = {t.name: t for t in get_native_browser_tools()}

        self.assertIn("browser_navigate", tools)
        self.assertIn("browser_wait", tools)
        self.assertIn("browser_vision_capture_marked", tools)
        self.assertIn("browser_vision_click_label", tools)
        self.assertIn("browser_vision_type_label", tools)
        self.assertIn("browser_run_actions", tools)

        result = tools["browser_navigate"].invoke({"url": "https://example.com"})
        self.assertEqual(result, "ok")
        mock_dispatch.assert_called()

        tools["browser_vision_click_label"].invoke({"label": "a1"})
        self.assertTrue(mock_dispatch.called)


if __name__ == "__main__":
    unittest.main()

