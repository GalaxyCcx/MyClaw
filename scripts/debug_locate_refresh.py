#!/usr/bin/env python3
"""
调试刷新按钮定位：在任务中心页面尝试各种选择器，返回哪些能定位到元素。
使用前请确保：1) 扩展已连接 2) 当前标签页已打开任务中心页面。
"""
from __future__ import annotations

import json
import sys

import requests

DEFAULT_BASE = "http://127.0.0.1:8000"


def main() -> int:
    url = f"{DEFAULT_BASE}/api/browser/jobs/alpha-bi/locate-refresh-debug"
    try:
        resp = requests.post(url, timeout=30)
    except Exception as exc:
        print(f"[ERROR] {exc}")
        return 1
    if resp.status_code != 200:
        print(f"[ERROR] HTTP {resp.status_code}")
        print(resp.text)
        return 2
    data = resp.json()
    found = data.get("found_count", 0)
    print(f"找到 {found} 个匹配的刷新按钮选择器")
    for r in data.get("results", []):
        status = "✓" if r.get("found") else "✗"
        loc = r.get("locator", {})
        el = r.get("element") or {}
        print(f"  {status} {loc}")
        if r.get("found") and el:
            print(f"      -> tag={el.get('tag')} cls={el.get('cls')} text={el.get('text')}")
    print("\nsnapshot_preview:", (data.get("snapshot_preview") or "")[:300])
    return 0


if __name__ == "__main__":
    sys.exit(main())
