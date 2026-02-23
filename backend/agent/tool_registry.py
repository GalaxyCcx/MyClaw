from tools import BUILTIN_TOOLS


def get_all_tools():
    """返回所有可用工具（仅内置工具，skill 通过脚本执行器调用）。"""
    return list(BUILTIN_TOOLS)
