import os
from pathlib import Path

from langchain_core.tools import tool

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@tool
def write_file(path: str, content: str) -> str:
    """将内容写入指定路径的文件。如果目录不存在会自动创建。相对路径基于项目根目录。"""
    try:
        p = Path(path)
        if p.is_absolute():
            resolved = p
        else:
            resolved = PROJECT_ROOT / path
        resolved = resolved.resolve()
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding="utf-8")
        size = resolved.stat().st_size
        return f"写入成功：{resolved}（{size} 字节）"
    except PermissionError:
        return f"错误：权限不足，无法写入文件 - {path}"
    except Exception as e:
        return f"错误：写入文件失败 - {e}"
