from __future__ import annotations

import unittest

from browser_gateway.protocol import (
    GatewayErrorCode,
    SUPPORTED_ACTIONS,
    build_command,
    build_error,
)


class TestBrowserGatewayProtocol(unittest.TestCase):
    def test_build_command(self):
        cmd = build_command("abc123", "navigate", {"url": "https://example.com"})
        self.assertEqual(cmd["type"], "command")
        self.assertEqual(cmd["id"], "abc123")
        self.assertEqual(cmd["action"], "navigate")
        self.assertIn("timestamp", cmd)

    def test_build_error(self):
        err = build_error("x1", GatewayErrorCode.TIMEOUT, "timeout", retriable=True)
        self.assertEqual(err["type"], "error")
        self.assertEqual(err["id"], "x1")
        self.assertEqual(err["code"], "timeout")
        self.assertTrue(err["retriable"])

    def test_supported_actions_contains_core(self):
        for action in ("navigate", "click", "type", "run_plan", "snapshot", "wait", "press_key", "alpha_bi_download_table"):
            self.assertIn(action, SUPPORTED_ACTIONS)


if __name__ == "__main__":
    unittest.main()

