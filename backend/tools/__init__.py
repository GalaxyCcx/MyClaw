import logging
import os
import time

from tools.read_file import read_file
from tools.write_file import write_file
from tools.web_fetch import web_fetch
from tools.web_search import web_search
from tools.python_executor import python_executor
from tools.shell_executor import shell_executor
from tools.check_download_file import check_download_file
from tools.read_skill_doc import read_skill_doc, read_skill_reference

logger = logging.getLogger(__name__)

BASE_TOOLS = [
    read_file,
    write_file,
    web_fetch,
    web_search,
    python_executor,
    shell_executor,
    check_download_file,
    read_skill_doc,
    read_skill_reference,
]

BROWSER_MCP_LOAD_RETRIES = 3
BROWSER_MCP_LOAD_DELAY = 1.5


def _browser_transport() -> str:
    return (os.getenv("BROWSER_TRANSPORT", "legacy_mcp") or "legacy_mcp").strip().lower()


def _load_browser_mcp_tools() -> list:
    """Load Browser MCP tools if enabled. Retries on connection failure."""
    from config.mcp_config import is_mcp_enabled

    if not is_mcp_enabled("browser-mcp"):
        return []
    last_err = None
    for attempt in range(1, BROWSER_MCP_LOAD_RETRIES + 1):
        try:
            from mcp_client import get_browser_mcp_tools

            tools = get_browser_mcp_tools()
            if tools:
                logger.info("Loaded %d Browser MCP tools", len(tools))
                return tools
            break
        except Exception as e:
            last_err = e
            if attempt < BROWSER_MCP_LOAD_RETRIES:
                logger.info(
                    "Browser MCP tools load attempt %d/%d failed, retrying in %.1fs: %s",
                    attempt,
                    BROWSER_MCP_LOAD_RETRIES,
                    BROWSER_MCP_LOAD_DELAY,
                    e,
                )
                time.sleep(BROWSER_MCP_LOAD_DELAY)
            else:
                logger.warning(
                    "Browser MCP tools not available after %d attempts (extension may not be connected): %s",
                    BROWSER_MCP_LOAD_RETRIES,
                    last_err,
                    exc_info=False,
                )
    return []


def _load_native_browser_tools() -> list:
    from browser_gateway import get_native_browser_tools

    try:
        return get_native_browser_tools()
    except Exception as e:
        logger.warning("Native browser tools unavailable: %s", e)
        return []


def get_all_tools() -> list:
    """Return all tools (base + selected browser transport). Dynamic per call."""
    transport = _browser_transport()
    if transport == "native_extension":
        browser_tools = _load_native_browser_tools()
    else:
        browser_tools = _load_browser_mcp_tools()
    return list(BASE_TOOLS) + browser_tools


def get_browser_mcp_init_status():
    """
    Check Browser MCP connection status for init job.
    Returns JobResult for display in Graph panel.
    """
    from agent.init_jobs import JobResult

    from config.mcp_config import is_mcp_enabled

    transport = _browser_transport()

    if transport == "native_extension":
        from browser_gateway import get_browser_gateway_manager

        try:
            status = get_browser_gateway_manager().status_snapshot()
        except Exception as e:
            return JobResult("check_browser_channel", "warning", f"Native browser channel check failed: {e}", 0.0)

        if status.get("connected"):
            return JobResult(
                "check_browser_channel",
                "success",
                f"native extension connected: clients={status.get('client_count', 0)} active={status.get('active_client_id', '')}",
                0.0,
            )
        return JobResult(
            "check_browser_channel",
            "warning",
            "native extension 未连接。请加载 extensions/myclaw-browser-agent 并保持后端运行。",
            0.0,
        )

    if not is_mcp_enabled("browser-mcp"):
        return JobResult("check_browser_mcp", "success", "Browser MCP disabled (not enabled)", 0.0)

    last_err = None
    for attempt in range(1, BROWSER_MCP_LOAD_RETRIES + 1):
        try:
            from mcp_client import BrowserMCPClient, get_browser_mcp_tools

            tools = get_browser_mcp_tools()
            names = [t.name for t in tools]
            connected, detail = BrowserMCPClient().probe_extension_connection()
            if connected:
                return JobResult(
                    "check_browser_mcp",
                    "success",
                    f"{len(tools)} tools, extension connected: {', '.join(names[:5])}{'...' if len(names) > 5 else ''}",
                    0.0,
                )
            return JobResult(
                "check_browser_mcp",
                "warning",
                f"扩展未连接。{detail[:100]} — 请在目标标签页点击 Browser MCP 的 Connect",
                0.0,
            )
        except Exception as e:
            last_err = e
            if attempt < BROWSER_MCP_LOAD_RETRIES:
                time.sleep(BROWSER_MCP_LOAD_DELAY)

    err_msg = str(last_err) if last_err else "unknown"
    return JobResult(
        "check_browser_mcp",
        "warning",
        f"Browser MCP 不可用。{err_msg[:100]} — 请检查 Node.js/npx 与本地端口占用",
        0.0,
    )


# For backward compatibility - used by routes; returns current snapshot
BUILTIN_TOOLS = BASE_TOOLS
