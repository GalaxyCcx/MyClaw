"""Browser MCP client - connects via stdio to npx @browsermcp/mcp."""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import os
import shlex
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = float(os.getenv("BROWSER_MCP_TIMEOUT", "60"))
DEBUG = os.getenv("BROWSER_MCP_DEBUG", "").lower() in ("true", "1", "yes")

EXTENSION_NOT_CONNECTED_MARKERS = (
    "no tab",
    "not connected",
    "no connection to browser extension",
    "must first connect a tab",
)

_SHARED_SESSION: "_PersistentBrowserMCPSession | None" = None
_SHARED_LOCK = threading.Lock()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_extension_not_connected_error(text: str) -> bool:
    s = (text or "").lower()
    return any(marker in s for marker in EXTENSION_NOT_CONNECTED_MARKERS)


def _classify_error(text: str) -> str:
    s = (text or "").lower()
    if is_extension_not_connected_error(s):
        return "extension_not_connected"
    if "timeout" in s or "timed out" in s:
        return "timeout"
    if "npx" in s or "enoent" in s or "not found" in s:
        return "runtime_missing"
    if "failed to kill process on port" in s or "maximum call stack size exceeded" in s:
        return "mcp_process_error"
    return "unknown"


def _shorten_error(err: Exception) -> str:
    """Shorten error message for user-facing display."""
    s = str(err)
    s_lower = s.lower()
    if is_extension_not_connected_error(s_lower):
        return "扩展未连接。请在 Browser MCP 扩展中点击 Connect，连接当前要操作的标签页。"
    if "timeout" in s_lower or "timed out" in s_lower:
        return "操作超时。请确认扩展已 Connect，或增加 BROWSER_MCP_TIMEOUT。"
    if "npx" in s_lower or "not found" in s_lower or "enoent" in s_lower:
        return "未找到 Browser MCP 启动命令（如 npx）。请检查 BROWSER_MCP_COMMAND/BROWSER_MCP_ARGS 配置与 PATH。"
    if "failed to kill process on port" in s_lower or "maximum call stack size exceeded" in s_lower:
        return "Browser MCP 子进程异常。请关闭占用端口的进程后重试，必要时重启 Chrome 与后端服务。"
    return s[:200]


def _get_server_params() -> StdioServerParameters:
    """Build stdio server parameters for Browser MCP server process."""
    command = os.getenv("BROWSER_MCP_COMMAND", "npx").strip() or "npx"
    args_json = (os.getenv("BROWSER_MCP_ARGS_JSON", "") or "").strip()
    args_text = (os.getenv("BROWSER_MCP_ARGS", "-y @browsermcp/mcp@latest") or "").strip()

    args: list[str]
    if args_json:
        try:
            import json
            parsed = json.loads(args_json)
            if isinstance(parsed, list) and all(isinstance(x, str) for x in parsed):
                args = parsed
            else:
                raise ValueError("BROWSER_MCP_ARGS_JSON must be a JSON string array")
        except Exception as e:
            logger.warning("Invalid BROWSER_MCP_ARGS_JSON, fallback to text args: %s", e)
            args = shlex.split(args_text, posix=(os.name != "nt"))
    else:
        args = shlex.split(args_text, posix=(os.name != "nt"))

    logger.info("Browser MCP server command: %s %s", command, " ".join(args))
    return StdioServerParameters(
        command=command,
        args=args,
        env=None,
    )


async def _list_tools_async(timeout: float) -> list[dict[str, Any]]:
    """List tools from Browser MCP (async)."""
    params = _get_server_params()
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await asyncio.wait_for(session.initialize(), timeout=timeout)
            result = await asyncio.wait_for(session.list_tools(), timeout=timeout)
            tools = getattr(result, "tools", []) or []
            return [
                {
                    "name": getattr(t, "name", ""),
                    "description": getattr(t, "description", "") or "",
                    "inputSchema": getattr(t, "inputSchema", {}) or {},
                }
                for t in tools
            ]


async def _call_tool_async(name: str, arguments: dict[str, Any], timeout: float) -> str:
    """Call a Browser MCP tool (async)."""
    params = _get_server_params()
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await asyncio.wait_for(session.initialize(), timeout=timeout)
            result = await asyncio.wait_for(
                session.call_tool(name, arguments or {}),
                timeout=timeout,
            )
            content = getattr(result, "content", None) or []
            parts = []
            for block in content:
                if hasattr(block, "type"):
                    if block.type == "text" and hasattr(block, "text"):
                        parts.append(block.text)
                    elif block.type == "image":
                        parts.append("[图片已省略]")
            return "\n".join(parts) if parts else "(无返回内容)"


def _run_async(coro):
    """Run async coroutine from sync context, handling existing event loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with concurrent.futures.ThreadPoolExecutor() as pool:
        future = pool.submit(asyncio.run, coro)
        return future.result()


class _PersistentBrowserMCPSession:
    """Maintain a shared Browser MCP session to avoid process/session drift."""

    def __init__(self, timeout: float):
        self._timeout = timeout
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._guard = threading.RLock()
        self._stdio_cm = None
        self._session_cm = None
        self._session: ClientSession | None = None
        self._session_id = ""
        self._last_success_at = ""
        self._last_error_type = ""
        self._last_error_message = ""
        self._mcp_process_ready = False
        self._start_loop()

    def _start_loop(self) -> None:
        if self._thread and self._thread.is_alive() and self._loop:
            return
        ready = threading.Event()

        def _runner():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._loop = loop
            ready.set()
            loop.run_forever()

        self._thread = threading.Thread(
            target=_runner,
            name="browser-mcp-session-loop",
            daemon=True,
        )
        self._thread.start()
        ready.wait(timeout=2.0)
        if not self._loop:
            raise RuntimeError("Browser MCP session loop failed to start")

    def _record_success(self) -> None:
        self._mcp_process_ready = True
        self._last_success_at = _utc_now_iso()
        self._last_error_type = ""
        self._last_error_message = ""

    def _record_error(self, err: Exception) -> None:
        msg = str(err)
        self._last_error_type = _classify_error(msg)
        self._last_error_message = msg[:200]
        self._mcp_process_ready = False

    def runtime_status(self) -> dict[str, Any]:
        with self._guard:
            return {
                "mcp_process_ready": self._mcp_process_ready,
                "session_id": self._session_id,
                "last_success_at": self._last_success_at,
                "last_error_type": self._last_error_type,
                "last_error_message": self._last_error_message,
            }

    def _run(self, coro):
        if not self._loop:
            self._start_loop()
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=self._timeout + 5)

    async def _ensure_session(self) -> None:
        if self._session is not None:
            return
        params = _get_server_params()
        self._stdio_cm = stdio_client(params)
        read_stream, write_stream = await asyncio.wait_for(
            self._stdio_cm.__aenter__(),
            timeout=self._timeout,
        )
        self._session_cm = ClientSession(read_stream, write_stream)
        self._session = await asyncio.wait_for(
            self._session_cm.__aenter__(),
            timeout=self._timeout,
        )
        await asyncio.wait_for(self._session.initialize(), timeout=self._timeout)
        self._session_id = uuid.uuid4().hex[:12]
        self._record_success()

    async def _reset_session_async(self) -> None:
        session_cm = self._session_cm
        stdio_cm = self._stdio_cm
        self._session = None
        self._session_cm = None
        self._stdio_cm = None
        self._session_id = ""
        if session_cm is not None:
            try:
                await session_cm.__aexit__(None, None, None)
            except Exception:
                logger.debug("Ignore session close error", exc_info=DEBUG)
        if stdio_cm is not None:
            try:
                await stdio_cm.__aexit__(None, None, None)
            except Exception:
                logger.debug("Ignore stdio close error", exc_info=DEBUG)

    async def _list_tools_async(self) -> list[dict[str, Any]]:
        await self._ensure_session()
        assert self._session is not None
        result = await asyncio.wait_for(self._session.list_tools(), timeout=self._timeout)
        tools = getattr(result, "tools", []) or []
        self._record_success()
        return [
            {
                "name": getattr(t, "name", ""),
                "description": getattr(t, "description", "") or "",
                "inputSchema": getattr(t, "inputSchema", {}) or {},
            }
            for t in tools
        ]

    async def _call_tool_async(self, name: str, arguments: dict[str, Any]) -> str:
        await self._ensure_session()
        assert self._session is not None
        result = await asyncio.wait_for(
            self._session.call_tool(name, arguments or {}),
            timeout=self._timeout,
        )
        content = getattr(result, "content", None) or []
        parts = []
        for block in content:
            if hasattr(block, "type"):
                if block.type == "text" and hasattr(block, "text"):
                    parts.append(block.text)
                elif block.type == "image":
                    parts.append("[图片已省略]")
        self._record_success()
        return "\n".join(parts) if parts else "(无返回内容)"

    def list_tools(self) -> list[dict[str, Any]]:
        with self._guard:
            try:
                return self._run(self._list_tools_async())
            except Exception as err:
                self._record_error(err)
                self._run(self._reset_session_async())
                raise

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> str:
        with self._guard:
            try:
                return self._run(self._call_tool_async(name, arguments or {}))
            except Exception as err:
                self._record_error(err)
                self._run(self._reset_session_async())
                raise

    def reset(self) -> None:
        with self._guard:
            try:
                self._run(self._reset_session_async())
            except Exception:
                logger.debug("Ignore reset error", exc_info=DEBUG)


def _get_shared_session(timeout: float) -> _PersistentBrowserMCPSession:
    global _SHARED_SESSION
    with _SHARED_LOCK:
        if _SHARED_SESSION is None:
            _SHARED_SESSION = _PersistentBrowserMCPSession(timeout=timeout)
        return _SHARED_SESSION


def get_browser_mcp_runtime_status() -> dict[str, Any]:
    session = _get_shared_session(DEFAULT_TIMEOUT)
    return session.runtime_status()


class BrowserMCPClient:
    """
    Synchronous client for Browser MCP.
    Spawns npx @browsermcp/mcp as subprocess, communicates via stdio.
    """

    def __init__(self, timeout: float | None = None):
        self._timeout = timeout if timeout is not None else DEFAULT_TIMEOUT
        self._session = _get_shared_session(self._timeout)

    def list_tools(self) -> list[dict[str, Any]]:
        """List available tools from Browser MCP."""
        last_err = None
        for attempt in range(2):
            try:
                return self._session.list_tools()
            except Exception as e:
                last_err = e
                logger.warning("Browser MCP list_tools attempt %d failed: %s", attempt + 1, e)
                if attempt == 0:
                    self._session.reset()
                    time.sleep(1.0)
        raise ConnectionError(
            f"无法连接 Browser MCP。{_shorten_error(last_err)} — "
            "请确认已安装 Browser MCP 扩展并在目标标签页点击 Connect。"
        ) from last_err

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> str:
        """Call an MCP tool by name. Retries once on failure."""
        last_err = None
        for attempt in range(2):
            try:
                return self._session.call_tool(name, arguments or {})
            except Exception as e:
                last_err = e
                if attempt == 0:
                    logger.info("Browser MCP call_tool %s attempt 1 failed, retrying: %s", name, e)
                    self._session.reset()
                    time.sleep(1.0)
                else:
                    logger.warning("Browser MCP call_tool %s failed: %s", name, e)
        raise RuntimeError(
            f"调用浏览器工具 {name} 失败: {_shorten_error(last_err)}"
        ) from last_err

    def probe_extension_connection(self) -> tuple[bool, str]:
        """Probe extension connectivity via lightweight tool call."""
        try:
            result = self.call_tool("browser_snapshot", {})
            if is_extension_not_connected_error(result):
                return False, result[:200]
            return True, ""
        except Exception as e:
            msg = str(e)
            return False, msg[:200]
