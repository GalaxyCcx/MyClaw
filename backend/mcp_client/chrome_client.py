"""MCP Chrome client - connects to mcp-chrome-bridge via minimal HTTP (POST-only)."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_URL = "http://127.0.0.1:12306/mcp"
DEFAULT_TIMEOUT = 60.0

_BACKEND_DIR = Path(__file__).resolve().parent.parent


def _get_config() -> tuple[str, float]:
    url = os.getenv("MCP_CHROME_URL", DEFAULT_URL)
    timeout = float(os.getenv("MCP_CHROME_TIMEOUT", str(DEFAULT_TIMEOUT)))
    return url, timeout


def _check_bridge_reachable(url: str, timeout: float = 5.0) -> tuple[bool, str]:
    """Quick HTTP check if bridge port is reachable. Returns (reachable, message)."""
    try:
        import httpx
        from urllib.parse import urlparse
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(f"{base}/ping")
            return True, f"HTTP {resp.status_code}"
    except Exception as e:
        err = str(e).lower()
        if "refused" in err or "10061" in err or "connect" in err:
            return False, "端口不可达，请确认扩展已点击 Connect 且端口 12306 未被占用"
        return False, str(e)


def _use_legacy_sdk() -> bool:
    """Use Python MCP SDK (streamable HTTP / stdio) instead of minimal HTTP client."""
    return os.getenv("MCP_CHROME_USE_SDK", "").lower() in ("true", "1", "yes")


def _run_legacy_list_tools(url: str, timeout: float) -> list[dict]:
    """Legacy: run list_tools via Python MCP SDK."""
    import asyncio
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    async def _do():
        async with streamable_http_client(url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await asyncio.wait_for(session.initialize(), timeout=timeout)
                result = await asyncio.wait_for(session.list_tools(), timeout=timeout)
                return [
                    {"name": getattr(t, "name", ""), "description": getattr(t, "description", "") or "", "inputSchema": getattr(t, "inputSchema", {}) or {}}
                    for t in (getattr(result, "tools", []) or [])
                ]

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is not None and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, _do())
            return future.result()
    return asyncio.run(_do())


def _run_legacy_call_tool(url: str, timeout: float, name: str, arguments: dict) -> str:
    """Legacy: run call_tool via Python MCP SDK."""
    import asyncio
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    async def _do():
        async with streamable_http_client(url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await asyncio.wait_for(session.initialize(), timeout=timeout)
                result = await asyncio.wait_for(session.call_tool(name, arguments), timeout=timeout)
                content = getattr(result, "content", None) or []
                parts = []
                for block in content:
                    if hasattr(block, "type"):
                        if block.type == "text" and hasattr(block, "text"):
                            parts.append(block.text)
                        elif block.type == "image":
                            parts.append("[图片已省略]")
                return "\n".join(parts) if parts else "(无返回内容)"

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is not None and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, _do())
            return future.result()
    return asyncio.run(_do())


class MCPChromeClient:
    """
    Synchronous client for mcp-chrome-bridge.
    Uses minimal HTTP (POST-only) by default to avoid SDK 500/TaskGroup issues.
    Set MCP_CHROME_USE_SDK=true to fall back to Python MCP SDK.
    """

    def __init__(
        self,
        url: str | None = None,
        timeout: float | None = None,
    ):
        self._url = url or _get_config()[0]
        self._timeout = timeout if timeout is not None else _get_config()[1]
        self._http_client = None

    def _get_http_client(self):
        if self._http_client is None:
            from mcp_client.http_client import MCPHttpClient
            self._http_client = MCPHttpClient(self._url, self._timeout)
        return self._http_client

    def list_tools(self) -> list[dict[str, Any]]:
        """List available tools from mcp-chrome."""
        if not _use_legacy_sdk():
            reachable, msg = _check_bridge_reachable(self._url, timeout=min(5.0, self._timeout))
            if not reachable:
                raise ConnectionError(f"无法连接 mcp-chrome-bridge ({self._url})。{msg}")

            try:
                return self._get_http_client().list_tools()
            except Exception as e:
                logger.warning("MCP Chrome list_tools failed: %s", e)
                raise ConnectionError(
                    f"无法连接 mcp-chrome-bridge ({self._url})。{e} — "
                    "若扩展已显示连接，请尝试断开后重新点击 Connect，或重启 Chrome。"
                ) from e

        # Legacy SDK path
        try:
            return _run_legacy_list_tools(self._url, self._timeout)
        except Exception as e:
            logger.warning("MCP Chrome list_tools (SDK) failed: %s", e)
            raise ConnectionError(
                f"无法连接 mcp-chrome-bridge ({self._url})。{e} — "
                "可尝试设置 MCP_CHROME_USE_SDK=false 使用轻量 HTTP 客户端。"
            ) from e

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> str:
        """Call an MCP tool by name. Retries once on connection failure."""
        if not _use_legacy_sdk():
            last_err = None
            for attempt in range(2):
                try:
                    return self._get_http_client().call_tool(name, arguments or {})
                except Exception as e:
                    last_err = e
                    if attempt == 0:
                        logger.info("MCP Chrome call_tool %s attempt 1 failed, retrying: %s", name, e)
                        time.sleep(1.0)
                    else:
                        logger.warning("MCP Chrome call_tool %s failed: %s", name, e)
            raise RuntimeError(
                f"调用浏览器工具 {name} 失败: {last_err}。"
                "若扩展已显示连接，请尝试断开后重新点击 Connect，或重启 Chrome。"
            ) from last_err

        # Legacy SDK path
        last_err = None
        for attempt in range(2):
            try:
                return _run_legacy_call_tool(self._url, self._timeout, name, arguments or {})
            except Exception as e:
                last_err = e
                if attempt == 0:
                    logger.info("MCP Chrome call_tool %s (SDK) attempt 1 failed, retrying: %s", name, e)
                    time.sleep(1.0)
        raise RuntimeError(
            f"调用浏览器工具 {name} 失败: {last_err}。"
            "可尝试设置 MCP_CHROME_USE_SDK=false 使用轻量 HTTP 客户端。"
        ) from last_err
