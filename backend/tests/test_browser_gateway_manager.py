from __future__ import annotations

import asyncio
import unittest

from browser_gateway.manager import BrowserGatewayManager


class DummyWebSocket:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_json(self, data):
        self.sent.append(data)


class TestBrowserGatewayManager(unittest.IsolatedAsyncioTestCase):
    async def test_send_command_without_client(self):
        manager = BrowserGatewayManager()
        result = await manager.send_command("navigate", {"url": "https://example.com"}, timeout=0.1)
        self.assertEqual(result["type"], "error")
        self.assertEqual(result["code"], "no_client")

    async def test_send_command_with_result(self):
        manager = BrowserGatewayManager()
        ws = DummyWebSocket()
        await manager.register(ws, "c1", {})

        async def _reply():
            await asyncio.sleep(0.01)
            sent = ws.sent[0]
            await manager.handle_message(
                "c1",
                {"type": "result", "id": sent["id"], "payload": {"ok": True, "message": "done"}},
            )

        task = asyncio.create_task(_reply())
        result = await manager.send_command("wait", {"ms": 1}, timeout=1.0)
        await task
        self.assertEqual(result["type"], "result")
        self.assertEqual(result["payload"]["message"], "done")

    async def test_timeout(self):
        manager = BrowserGatewayManager()
        ws = DummyWebSocket()
        await manager.register(ws, "c1", {})
        result = await manager.send_command("snapshot", {"mode": "summary"}, timeout=0.01)
        self.assertEqual(result["type"], "error")
        self.assertEqual(result["code"], "timeout")


if __name__ == "__main__":
    unittest.main()

