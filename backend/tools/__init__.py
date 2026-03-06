import logging

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

def _load_native_browser_tools() -> list:
    from browser_gateway import get_native_browser_tools

    try:
        return get_native_browser_tools()
    except Exception as e:
        logger.warning("Native browser tools unavailable: %s", e)
        return []


def get_all_tools() -> list:
    """Return all tools (base + V3 native extension tools)."""
    browser_tools = _load_native_browser_tools()
    return list(BASE_TOOLS) + browser_tools


def get_browser_channel_init_status():
    """
    Check browser native channel status for init job.
    Returns JobResult for display in Graph panel.
    """
    from agent.init_jobs import JobResult

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
        "native extension 未连接。请加载 extensions/myclaw-browser-agent-v3 并保持后端运行。",
        0.0,
    )


# For backward compatibility - used by routes; returns current snapshot
BUILTIN_TOOLS = BASE_TOOLS
