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

MCP_CHROME_LOAD_RETRIES = 3
MCP_CHROME_LOAD_DELAY = 1.5


def _load_mcp_chrome_tools() -> list:
    """Load MCP Chrome tools if enabled and bridge is available. Retries on connection failure."""
    from config.mcp_config import is_mcp_enabled

    if not is_mcp_enabled("mcp-chrome"):
        return []
    last_err = None
    for attempt in range(1, MCP_CHROME_LOAD_RETRIES + 1):
        try:
            from mcp_client import get_mcp_chrome_tools

            tools = get_mcp_chrome_tools()
            if tools:
                logger.info("Loaded %d MCP Chrome tools", len(tools))
                return tools
            break
        except Exception as e:
            last_err = e
            if attempt < MCP_CHROME_LOAD_RETRIES:
                logger.info(
                    "MCP Chrome tools load attempt %d/%d failed, retrying in %.1fs: %s",
                    attempt,
                    MCP_CHROME_LOAD_RETRIES,
                    MCP_CHROME_LOAD_DELAY,
                    e,
                )
                time.sleep(MCP_CHROME_LOAD_DELAY)
            else:
                logger.warning(
                    "MCP Chrome tools not available after %d attempts (bridge may not be running): %s",
                    MCP_CHROME_LOAD_RETRIES,
                    last_err,
                    exc_info=False,
                )
    return []


def get_all_tools() -> list:
    """Return all tools (base + MCP when enabled). Dynamic per call."""
    return list(BASE_TOOLS) + _load_mcp_chrome_tools()


def get_mcp_chrome_init_status():
    """
    Check MCP Chrome connection status for init job.
    Returns JobResult for display in Graph panel.
    """
    from agent.init_jobs import JobResult

    from config.mcp_config import is_mcp_enabled

    if not is_mcp_enabled("mcp-chrome"):
        return JobResult("check_mcp_chrome", "success", "MCP Chrome disabled (not enabled)", 0.0)

    last_err = None
    for attempt in range(1, MCP_CHROME_LOAD_RETRIES + 1):
        try:
            from mcp_client import get_mcp_chrome_tools

            tools = get_mcp_chrome_tools()
            if tools:
                names = [t.name for t in tools]
                return JobResult(
                    "check_mcp_chrome",
                    "success",
                    f"{len(tools)} tools: {', '.join(names[:5])}{'...' if len(names) > 5 else ''}",
                    0.0,
                )
            break
        except Exception as e:
            last_err = e
            if attempt < MCP_CHROME_LOAD_RETRIES:
                time.sleep(MCP_CHROME_LOAD_DELAY)

    err_msg = str(last_err) if last_err else "unknown"
    return JobResult(
        "check_mcp_chrome",
        "warning",
        f"Bridge not reachable (port 12306). {err_msg} — 请先在 Chrome 扩展中点击 Connect",
        0.0,
    )


# For backward compatibility - used by routes; returns current snapshot
BUILTIN_TOOLS = BASE_TOOLS
