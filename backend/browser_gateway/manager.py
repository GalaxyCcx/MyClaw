from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket

from browser_gateway.protocol import (
    GatewayErrorCode,
    GatewayMessageType,
    PendingCommand,
    SUPPORTED_ACTIONS,
    build_command,
    build_error,
    utc_now_iso,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ClientState:
    client_id: str
    websocket: WebSocket
    connected_at: float
    last_seen_at: float
    meta: dict[str, Any] = field(default_factory=dict)


class BrowserGatewayManager:
    """Manage native browser extension websocket sessions and command routing."""

    def __init__(self) -> None:
        self._clients: dict[str, ClientState] = {}
        self._pending: dict[str, asyncio.Future] = {}
        self._pending_meta: dict[str, PendingCommand] = {}
        self._lock = asyncio.Lock()
        self._active_client_id: str = ""
        self._recent_errors: deque[dict[str, Any]] = deque(maxlen=50)

    async def register(self, websocket: WebSocket, client_id: str, meta: dict[str, Any] | None = None) -> None:
        now = time.time()
        state = ClientState(
            client_id=client_id,
            websocket=websocket,
            connected_at=now,
            last_seen_at=now,
            meta=meta or {},
        )
        async with self._lock:
            self._clients[client_id] = state
            self._active_client_id = client_id
        logger.info("Browser gateway client registered: %s", client_id)

    async def unregister(self, client_id: str) -> None:
        async with self._lock:
            self._clients.pop(client_id, None)
            if self._active_client_id == client_id:
                self._active_client_id = next(iter(self._clients.keys()), "")
        logger.info("Browser gateway client unregistered: %s", client_id)

    async def heartbeat(self, client_id: str, meta: dict[str, Any] | None = None) -> None:
        async with self._lock:
            state = self._clients.get(client_id)
            if state is None:
                return
            state.last_seen_at = time.time()
            if meta:
                state.meta.update(meta)
            self._active_client_id = client_id

    async def send_command(
        self,
        action: str,
        payload: dict[str, Any] | None = None,
        timeout: float = 30.0,
        client_id: str | None = None,
    ) -> dict[str, Any]:
        if action not in SUPPORTED_ACTIONS:
            return build_error(
                command_id=None,
                code=GatewayErrorCode.UNSUPPORTED_ACTION,
                message=f"unsupported action: {action}",
                retriable=False,
            )

        async with self._lock:
            target_client_id = client_id or self._active_client_id
            if not target_client_id or target_client_id not in self._clients:
                return build_error(
                    command_id=None,
                    code=GatewayErrorCode.NO_CLIENT,
                    message="native extension not connected",
                    retriable=True,
                )
            ws = self._clients[target_client_id].websocket

        command_id = uuid.uuid4().hex[:12]
        cmd = build_command(command_id, action, payload)
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending[command_id] = fut
        self._pending_meta[command_id] = PendingCommand(
            command_id=command_id,
            action=action,
            started_at=time.time(),
        )
        try:
            await ws.send_json(cmd)
            return await asyncio.wait_for(fut, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending.pop(command_id, None)
            self._pending_meta.pop(command_id, None)
            err = build_error(
                command_id=command_id,
                code=GatewayErrorCode.TIMEOUT,
                message=f"action timeout: {action}",
                retriable=True,
            )
            self._recent_errors.append(err)
            return err
        except Exception as exc:
            self._pending.pop(command_id, None)
            self._pending_meta.pop(command_id, None)
            err = build_error(
                command_id=command_id,
                code=GatewayErrorCode.EXECUTION_FAILED,
                message=f"failed to dispatch action={action}: {exc}",
                retriable=True,
            )
            self._recent_errors.append(err)
            return err

    async def handle_message(self, client_id: str, message: dict[str, Any]) -> None:
        msg_type = str(message.get("type", ""))
        msg_id = str(message.get("id", ""))
        if msg_type == GatewayMessageType.HEARTBEAT.value:
            await self.heartbeat(client_id, message.get("meta") or {})
            return

        if msg_type in {GatewayMessageType.RESULT.value, GatewayMessageType.ERROR.value}:
            fut = self._pending.get(msg_id)
            self._pending.pop(msg_id, None)
            self._pending_meta.pop(msg_id, None)
            if fut and not fut.done():
                fut.set_result(message)
            if msg_type == GatewayMessageType.ERROR.value:
                self._recent_errors.append(message)
            return

        # ACK/PROGRESS are accepted but not required to drive state.
        if msg_type in {GatewayMessageType.ACK.value, GatewayMessageType.PROGRESS.value}:
            await self.heartbeat(client_id)
            return

    async def status(self) -> dict[str, Any]:
        async with self._lock:
            clients = list(self._clients.values())
            active = self._active_client_id
        now = time.time()
        return {
            "connected": bool(clients),
            "client_count": len(clients),
            "active_client_id": active,
            "clients": [
                {
                    "client_id": c.client_id,
                    "connected_at": utc_now_iso(),
                    "last_seen_seconds": round(max(0.0, now - c.last_seen_at), 3),
                    "meta": c.meta,
                }
                for c in clients
            ],
            "pending_count": len(self._pending),
            "recent_errors": list(self._recent_errors),
        }

    def status_snapshot(self) -> dict[str, Any]:
        """Best-effort sync snapshot for places where await is unavailable."""
        now = time.time()
        clients = list(self._clients.values())
        return {
            "connected": bool(clients),
            "client_count": len(clients),
            "active_client_id": self._active_client_id,
            "clients": [
                {
                    "client_id": c.client_id,
                    "connected_at": utc_now_iso(),
                    "last_seen_seconds": round(max(0.0, now - c.last_seen_at), 3),
                    "meta": c.meta,
                }
                for c in clients
            ],
            "pending_count": len(self._pending),
            "recent_errors": list(self._recent_errors),
        }


_MANAGER: BrowserGatewayManager | None = None


def get_browser_gateway_manager() -> BrowserGatewayManager:
    global _MANAGER
    if _MANAGER is None:
        _MANAGER = BrowserGatewayManager()
    return _MANAGER

