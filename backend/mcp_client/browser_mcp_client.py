"""Browser MCP client - connects via stdio to npx @browsermcp/mcp."""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import os
import time
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = float(os.getenv("BROWSER_MCP_TIMEOUT", "60"))
DEBUG = os.getenv("BROWSER_MCP_DEBUG", "").lower() in ("true", "1", "yes")


def _shorten_error(err: Exception) -> str:
    """Shorten error message for user-facing display."""
    s = str(err).lower()
    if "no tab" in s or "not connected" in s or "connect" in s:
        return "扩展未连接。请在 Browser MCP 扩展中点击 Connect，连接当前要操作的标签页。"
    if "timeout" in s or "timed out" in s:
        return "操作超时。请确认扩展已 Connect，或增加 BROWSER_MCP_TIMEOUT。"
    if "npx" in s or "not found" in s or "enoent" in s:
        return "未找到 npx。请安装 Node.js 并确保 npx 在 PATH 中。"
    return str(err)[:200]


def _get_server_params() -> StdioServerParameters:
    """Build stdio server parameters for @browsermcp/mcp."""
    return StdioServerParameters(
        command="npx",
        args=["-y", "@browsermcp/mcp@latest"],
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
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with concurrent.futures.ThreadPoolExecutor() as pool:
        future = pool.submit(asyncio.run, coro)
        return future.result()


class BrowserMCPClient:
    """
    Synchronous client for Browser MCP.
    Spawns npx @browsermcp/mcp as subprocess, communicates via stdio.
    """

    def __init__(self, timeout: float | None = None):
        self._timeout = timeout if timeout is not None else DEFAULT_TIMEOUT

    def list_tools(self) -> list[dict[str, Any]]:
        """List available tools from Browser MCP."""
        last_err = None
        for attempt in range(2):
            try:
                return _run_async(_list_tools_async(self._timeout))
            except Exception as e:
                last_err = e
                logger.warning("Browser MCP list_tools attempt %d failed: %s", attempt + 1, e)
                if attempt == 0:
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
                return _run_async(_call_tool_async(name, arguments or {}, self._timeout))
            except Exception as e:
                last_err = e
                if attempt == 0:
                    logger.info("Browser MCP call_tool %s attempt 1 failed, retrying: %s", name, e)
                    time.sleep(1.0)
                else:
                    logger.warning("Browser MCP call_tool %s failed: %s", name, e)
        raise RuntimeError(
            f"调用浏览器工具 {name} 失败: {_shorten_error(last_err)}"
        ) from last_err
