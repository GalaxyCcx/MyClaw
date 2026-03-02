import logging
import time

from tools.read_file import read_file
from tools.write_file import write_file
from tools.web_fetch import web_fetch
from tools.web_search import web_search
from tools.python_executor import python_executor
from tools.shell_executor import shell_executor
from tools.read_skill_doc import read_skill_doc, read_skill_reference

logger = logging.getLogger(__name__)

BASE_TOOLS = [
    read_file,
    write_file,
    web_fetch,
    web_search,
    python_executor,
    shell_executor,
    read_skill_doc,
    read_skill_reference,
]

BROWSER_MCP_LOAD_RETRIES = 3
BROWSER_MCP_LOAD_DELAY = 1.5


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


def get_all_tools() -> list:
    """Return all tools (base + Browser MCP when enabled). Dynamic per call."""
    return list(BASE_TOOLS) + _load_browser_mcp_tools()


def get_browser_mcp_init_status():
    """
    Check Browser MCP connection status for init job.
    Returns JobResult for display in Graph panel.
    """
    from agent.init_jobs import JobResult

    from config.mcp_config import is_mcp_enabled

    if not is_mcp_enabled("browser-mcp"):
        return JobResult("check_browser_mcp", "success", "Browser MCP disabled (not enabled)", 0.0)

    last_err = None
    for attempt in range(1, BROWSER_MCP_LOAD_RETRIES + 1):
        try:
            from mcp_client import get_browser_mcp_tools

            tools = get_browser_mcp_tools()
            if tools:
                names = [t.name for t in tools]
                return JobResult(
                    "check_browser_mcp",
                    "success",
                    f"{len(tools)} tools: {', '.join(names[:5])}{'...' if len(names) > 5 else ''}",
                    0.0,
                )
            break
        except Exception as e:
            last_err = e
            if attempt < BROWSER_MCP_LOAD_RETRIES:
                time.sleep(BROWSER_MCP_LOAD_DELAY)

    err_msg = str(last_err) if last_err else "unknown"
    return JobResult(
        "check_browser_mcp",
        "warning",
        f"扩展未连接。{err_msg[:100]} — 请在 Browser MCP 扩展中点击 Connect",
        0.0,
    )


# For backward compatibility - used by routes; returns current snapshot
BUILTIN_TOOLS = BASE_TOOLS
