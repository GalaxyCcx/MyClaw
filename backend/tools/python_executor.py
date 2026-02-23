import os
import subprocess
import sys

from langchain_core.tools import tool


@tool
def python_executor(code: str) -> str:
    """在子进程中执行 Python 代码片段并返回标准输出和标准错误。请将完整代码写在一次调用中，包含所有 print 语句来输出结果。不要分多次调用。"""
    MAX_CHARS = int(os.getenv("PYTHON_EXECUTOR_MAX_CHARS", "50000"))
    TIMEOUT = int(os.getenv("PYTHON_EXECUTOR_TIMEOUT", "180"))
    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
        )
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += ("\n" if output else "") + result.stderr
        if not output:
            output = "(无输出)"
        if len(output) > MAX_CHARS:
            output = output[:MAX_CHARS] + f"\n\n... [输出已截断，仅显示前 {MAX_CHARS} 字符]"
        return output
    except subprocess.TimeoutExpired:
        return f"错误：代码执行超时（{TIMEOUT} 秒）"
    except Exception as e:
        return f"错误：代码执行失败 - {e}"
