from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class GatewayMessageType(str, Enum):
    HELLO = "hello"
    COMMAND = "command"
    ACK = "ack"
    PROGRESS = "progress"
    RESULT = "result"
    ERROR = "error"
    HEARTBEAT = "heartbeat"


class GatewayErrorCode(str, Enum):
    NO_CLIENT = "no_client"
    TIMEOUT = "timeout"
    BAD_MESSAGE = "bad_message"
    EXECUTION_FAILED = "execution_failed"
    UNSUPPORTED_ACTION = "unsupported_action"


# V3 extension action set only.
SUPPORTED_ACTIONS: set[str] = {
    "navigate",
    "go_back",
    "go_forward",
    "wait",
    "get_url",
    "screenshot",
    "vision_capture_marked",
    "vision_click_label",
    "vision_type_label",
    "vision_clear_marks",
    "vision_scroll_by",
    "vision_wait_stable",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_command(command_id: str, action: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "type": GatewayMessageType.COMMAND.value,
        "id": command_id,
        "action": action,
        "payload": payload or {},
        "timestamp": utc_now_iso(),
    }


def build_error(
    command_id: str | None,
    code: GatewayErrorCode,
    message: str,
    retriable: bool = False,
) -> dict[str, Any]:
    return {
        "type": GatewayMessageType.ERROR.value,
        "id": command_id or "",
        "code": code.value,
        "message": message,
        "retriable": retriable,
        "timestamp": utc_now_iso(),
    }


@dataclass(slots=True)
class PendingCommand:
    command_id: str
    action: str
    started_at: float

