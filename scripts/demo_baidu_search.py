from __future__ import annotations

import json
import sys
from typing import Any

import requests


def run() -> int:
    base = "http://127.0.0.1:8000"
    url = f"{base}/api/browser/actions/execute"
    payload: dict[str, Any] = {
        "url": "https://www.baidu.com",
        "wait_after_navigate_ms": 1200,
        "timeout_seconds": 25,
        "stop_on_error": True,
        "steps": [
            {"action": "navigate", "payload": {"url": "https://www.baidu.com/s?wd=%E5%A5%A5%E7%89%B9%E6%9B%BC"}},
            {"action": "wait", "payload": {"ms": 1500}},
        ],
    }

    try:
        resp = requests.post(url, json=payload, timeout=60)
    except Exception as exc:
        print(f"[ERROR] 请求失败: {exc}")
        return 1

    if resp.status_code != 200:
        print(f"[ERROR] HTTP {resp.status_code}")
        print(resp.text)
        return 1

    data = resp.json()
    print(json.dumps({"ok": data.get("ok"), "steps": len(data.get("actions_log", []))}, ensure_ascii=False))
    if not data.get("ok"):
        print(json.dumps(data, ensure_ascii=False))
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(run())
