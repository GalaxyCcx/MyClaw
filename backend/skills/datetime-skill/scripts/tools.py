"""DateTime Skill - CLI executable tools.

Usage:
    python tools.py get_current_time [--timezone=Asia/Shanghai]
    python tools.py calculate_date_diff --date1=2024-01-01 --date2=2024-12-31
"""
import sys
from datetime import datetime
from zoneinfo import ZoneInfo


def get_current_time(timezone="Asia/Shanghai"):
    try:
        tz = ZoneInfo(timezone)
        now = datetime.now(tz)
        return now.strftime("%Y-%m-%d %H:%M:%S %Z (UTC%z)")
    except Exception as e:
        return f"Error: {e}"


def calculate_date_diff(date1, date2):
    try:
        d1 = datetime.strptime(date1, "%Y-%m-%d")
        d2 = datetime.strptime(date2, "%Y-%m-%d")
        diff = abs((d2 - d1).days)
        return f"{date1} 和 {date2} 之间相差 {diff} 天"
    except ValueError as e:
        return f"Error: 日期格式不正确，请使用 YYYY-MM-DD — {e}"


COMMANDS = {
    "get_current_time": get_current_time,
    "calculate_date_diff": calculate_date_diff,
}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tools.py <command> [--key=value ...]")
        print(f"Available commands: {', '.join(COMMANDS)}")
        sys.exit(1)

    command = sys.argv[1]
    kwargs = {}
    for arg in sys.argv[2:]:
        if arg.startswith("--") and "=" in arg:
            key, value = arg[2:].split("=", 1)
            kwargs[key] = value

    if command not in COMMANDS:
        print(f"Unknown command: {command}. Available: {', '.join(COMMANDS)}")
        sys.exit(1)

    result = COMMANDS[command](**kwargs)
    print(result)
