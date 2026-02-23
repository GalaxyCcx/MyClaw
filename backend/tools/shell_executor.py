import os
import subprocess
import sys
from pathlib import Path

from langchain_core.tools import tool

DANGEROUS_PATTERNS = [
    "rm -rf /",
    "rm -rf /*",
    "mkfs",
    "format c:",
    "format d:",
    ":(){:|:&};:",
    "dd if=/dev/zero",
    "shutdown",
    "reboot",
]


def _get_venv_env() -> dict:
    """Return env dict with venv's Scripts/bin directory prepended to PATH."""
    env = os.environ.copy()
    venv_dir = Path(sys.executable).resolve().parent
    current_path = env.get("PATH", "")
    env["PATH"] = f"{venv_dir}{os.pathsep}{current_path}"
    return env


@tool
def shell_executor(command: str) -> str:
    """执行一条 shell 命令并返回输出。禁止执行高危命令。"""
    MAX_CHARS = int(os.getenv("SHELL_EXECUTOR_MAX_CHARS", "50000"))
    TIMEOUT = int(os.getenv("SHELL_EXECUTOR_TIMEOUT", "60"))

    cmd_lower = command.lower().strip()
    for pattern in DANGEROUS_PATTERNS:
        if pattern in cmd_lower:
            return f"错误：禁止执行危险命令 - 包含 '{pattern}'"

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            env=_get_venv_env(),
        )
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += ("\n" if output else "") + result.stderr
        output += f"\n\n[退出码: {result.returncode}]"
        if len(output) > MAX_CHARS:
            output = output[:MAX_CHARS] + f"\n\n... [输出已截断，仅显示前 {MAX_CHARS} 字符]"
        return output
    except subprocess.TimeoutExpired:
        return f"错误：命令执行超时（{TIMEOUT} 秒）"
    except Exception as e:
        return f"错误：命令执行失败 - {e}"
