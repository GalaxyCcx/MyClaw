from tools import get_all_tools as _get_tools


def get_all_tools():
    """返回所有可用工具（内置 + 已启用的 MCP）。"""
    return _get_tools()
