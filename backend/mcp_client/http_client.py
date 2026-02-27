"""
Minimal MCP HTTP client - bypasses Python MCP SDK's streamable_http_client
which has known 500/TaskGroup issues with mcp-chrome-bridge.

Uses simple POST requests only (no GET/SSE) to avoid protocol mismatches.
Bridge expects: POST /mcp with initialize -> response has Mcp-Session-Id header.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

import httpx

logger = logging.getLogger(__name__)

PROTOCOL_VERSION = "2024-11-05"  # Use stable version for compatibility


def _parse_response_body(resp: httpx.Response) -> dict:
    """Parse response: either JSON or SSE (text/event-stream) format."""
    content_type = (resp.headers.get("content-type") or "").lower()
    text = resp.text or ""
    if "text/event-stream" in content_type:
        # Parse SSE: "data: {...}\n\n" -> extract JSON
        for line in text.splitlines():
            if line.startswith("data:"):
                json_str = line[5:].strip()
                if json_str:
                    try:
                        return json.loads(json_str)
                    except json.JSONDecodeError:
                        continue
        return {}
    try:
        return resp.json()
    except Exception:
        return {}


def _post_json(url: str, body: dict, session_id: str | None, timeout: float) -> tuple[dict, str | None]:
    """POST JSON-RPC request, return (response_body, new_session_id from headers)."""
    headers = {
        "Accept": "application/json, text/event-stream",  # Per MCP streamable HTTP spec
        "Content-Type": "application/json",
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id

    with httpx.Client(timeout=timeout) as client:
        resp = client.post(url, json=body, headers=headers)
        resp.raise_for_status()
        # Headers are case-insensitive; bridge may send mcp-session-id or Mcp-Session-Id
        sid = resp.headers.get("mcp-session-id") or resp.headers.get("Mcp-Session-Id")
        data = _parse_response_body(resp)
        return data, sid


def mcp_initialize(url: str, timeout: float) -> str:
    """Initialize MCP session, return session ID from response header."""
    body = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "initialize",
        "params": {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "myclaw", "version": "0.2.0"},
        },
    }
    data, session_id = _post_json(url, body, None, timeout)
    if "error" in data:
        raise RuntimeError(f"MCP initialize failed: {data['error']}")
    if "result" in data:
        # Bridge sets Mcp-Session-Id in response header; fallback to result.sessionId
        return session_id or data["result"].get("sessionId", "") or ""
    raise RuntimeError(f"Unexpected MCP response: {data}")


def mcp_list_tools(url: str, session_id: str, timeout: float) -> list[dict]:
    """List tools from MCP server."""
    body = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "tools/list",
        "params": {},
    }
    data, _ = _post_json(url, body, session_id, timeout)
    if "result" in data:
        tools = data["result"].get("tools", [])
        return [{"name": t.get("name", ""), "description": t.get("description", ""), "inputSchema": t.get("inputSchema", {})} for t in tools]
    if "error" in data:
        raise RuntimeError(f"MCP tools/list failed: {data['error']}")
    raise RuntimeError(f"Unexpected MCP response: {data}")


def mcp_call_tool(url: str, session_id: str, name: str, arguments: dict, timeout: float) -> str:
    """Call MCP tool, return text content."""
    body = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments or {}},
    }
    data, _ = _post_json(url, body, session_id, timeout)
    if "result" in data:
        content = data["result"].get("content", [])
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, dict) and block.get("type") == "image":
                parts.append("[图片已省略]")
        text = "\n".join(parts) if parts else "(无返回内容)"
        if "Failed to connect to MCP server" in text or "无法连接" in text:
            text += "\n\n[排查建议] 扩展显示已连接但工具调用失败时：在扩展中点击「断开」后重新点击「Connect」；或重启 Chrome 后再试。"
        return text
    if "error" in data:
        err = data["error"]
        msg = err.get("message", str(err))
        raise RuntimeError(f"MCP tools/call failed: {msg}")
    raise RuntimeError(f"Unexpected MCP response: {data}")


class MCPHttpClient:
    """
    Session-aware MCP HTTP client. Uses POST-only, no SSE.
    Re-initializes on 404 (session expired).
    """

    def __init__(self, url: str, timeout: float):
        self._url = url
        self._timeout = timeout
        self._session_id: str | None = None

    def _ensure_session(self) -> str:
        if self._session_id:
            return self._session_id
        self._session_id = mcp_initialize(self._url, self._timeout)
        if not self._session_id:
            raise RuntimeError("MCP initialize did not return session ID")
        return self._session_id

    def list_tools(self) -> list[dict]:
        try:
            sid = self._ensure_session()
            return mcp_list_tools(self._url, sid, self._timeout)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                self._session_id = None
                sid = self._ensure_session()
                return mcp_list_tools(self._url, sid, self._timeout)
            raise

    def call_tool(self, name: str, arguments: dict | None = None) -> str:
        try:
            sid = self._ensure_session()
            return mcp_call_tool(self._url, sid, name, arguments or {}, self._timeout)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                self._session_id = None
                sid = self._ensure_session()
                return mcp_call_tool(self._url, sid, name, arguments or {}, self._timeout)
            raise
