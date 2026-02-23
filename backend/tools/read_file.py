import os
from pathlib import Path

from langchain_core.tools import tool

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@tool
def read_file(path: str) -> str:
    """读取指定路径的本地文件内容并返回文本。支持绝对路径和相对路径。相对路径会依次从项目根目录和当前目录查找。"""
    MAX_CHARS = 50_000
    try:
        p = Path(path)
        if p.is_absolute():
            resolved = p
        else:
            candidate_project = PROJECT_ROOT / path
            candidate_cwd = Path.cwd() / path
            if candidate_project.exists():
                resolved = candidate_project
            elif candidate_cwd.exists():
                resolved = candidate_cwd
            else:
                return f"错误：文件不存在 - 已查找:\n  1) {candidate_project}\n  2) {candidate_cwd}"

        resolved = resolved.resolve()
        if not resolved.exists():
            return f"错误：文件不存在 - {resolved}"
        if not resolved.is_file():
            return f"错误：路径不是文件 - {resolved}"
        with open(resolved, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(MAX_CHARS + 1)
        if len(content) > MAX_CHARS:
            content = content[:MAX_CHARS] + f"\n\n... [文件内容已截断，仅显示前 {MAX_CHARS} 字符]"
        return content
    except PermissionError:
        return f"错误：权限不足，无法读取文件 - {path}"
    except Exception as e:
        return f"错误：读取文件失败 - {e}"
