from __future__ import annotations

import unittest
from unittest.mock import patch

from browser_gateway.tools import (
    _should_block_single_step_in_alpha_bi,
    get_native_browser_tools,
)


class TestBrowserGatewayTools(unittest.TestCase):
    @patch("browser_gateway.tools._dispatch")
    def test_contract_command_result(self, mock_dispatch):
        mock_dispatch.return_value = "ok"
        tools = {t.name: t for t in get_native_browser_tools()}

        self.assertIn("browser_navigate", tools)
        self.assertIn("browser_click", tools)
        self.assertIn("browser_type", tools)
        self.assertIn("browser_run_plan", tools)
        self.assertIn("browser_snapshot", tools)

        result = tools["browser_navigate"].invoke({"url": "https://example.com"})
        self.assertEqual(result, "ok")
        mock_dispatch.assert_called()

        tools["browser_run_plan"].invoke({
            "steps": [
                {"action": "wait", "payload": {"ms": 10}},
                {"action": "snapshot", "payload": {"mode": "summary"}},
            ],
            "stop_on_error": True,
        })
        self.assertTrue(mock_dispatch.called)

    @patch("browser_gateway.tools._active_url_from_status_snapshot")
    def test_alpha_bi_single_step_gate(self, mock_active_url):
        mock_active_url.return_value = "https://alpha-bi.ddxq.mobi/report?foo=bar"
        self.assertTrue(_should_block_single_step_in_alpha_bi("click", {}))
        self.assertTrue(_should_block_single_step_in_alpha_bi("type", {}))
        self.assertFalse(_should_block_single_step_in_alpha_bi("run_plan", {}))
        self.assertFalse(_should_block_single_step_in_alpha_bi("click", {"force_single_step": True}))


if __name__ == "__main__":
    unittest.main()

