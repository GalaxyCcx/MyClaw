from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EventType(str, Enum):
    USER_INPUT = "user_input"
    LLM_TOKEN = "llm_token"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    FINAL_ANSWER = "final_answer"
    ERROR = "error"
    INIT_STATUS = "init_status"
    GRAPH_RESET = "graph_reset"
    NODE_ENTER = "node_enter"
    NODE_EXIT = "node_exit"
    CONTEXT_PRUNED = "context_pruned"
    CONTEXT_COMPACTED = "context_compacted"
    OVERFLOW_RECOVERED = "overflow_recovered"


class UserInputData(BaseModel):
    content: str


class LLMTokenData(BaseModel):
    token: str


class ToolCallData(BaseModel):
    tool_call_id: str
    name: str
    arguments: dict[str, Any]


class ToolResultData(BaseModel):
    tool_call_id: str
    name: str
    status: str  # "success" | "error"
    content: str


class FinalAnswerData(BaseModel):
    content: str


class ErrorData(BaseModel):
    message: str
    detail: str = ""


class AgentEvent(BaseModel):
    type: EventType
    step: int = 0
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    data: dict[str, Any]


class ClientMessage(BaseModel):
    type: str
    data: UserInputData
