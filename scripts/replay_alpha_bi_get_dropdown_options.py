#!/usr/bin/env python3
"""
测试扩展 get_dropdown_options 动作。

前置：后端已启动，BROWSER_TRANSPORT=native_extension，v2 扩展已连接。
流程：navigate -> 可选 click 下拉 -> wait -> get_dropdown_options -> 打印 options。
"""
from __future__ import annotations

import json
import sys

import requests

DEFAULT_BASE = "http://127.0.0.1:8000"


def main() -> int:
    base = DEFAULT_BASE
    # 使用 execute 接口：先 navigate，再 click 下拉，再 get_dropdown_options
    url = f"{base}/api/browser/actions/execute"
    payload = {
        "url": "https://alpha-bi.ddxq.mobi/report?pathIds=279b4f5efc6d446886b3662773c25b3c,cc4baf96c7344900918887be30cf56de&dashboardId=d127af3f0bb3457287f5093bdea78846&externalSpaceId=fccdafe6147b461d94425137c51ffe2e&appId=36620ff9365540a2b6a36531a5dcef6b&iframeType=app&orgId=1&spaceId=fccdafe6147b461d94425137c51ffe2e",
        "wait_after_navigate_ms": 12000,
        "steps": [
            {"action": "click", "payload": {"locator": {"selector": ".ant-select-selector", "index": 0}}},
            {"action": "wait", "payload": {"ms": 2000}},
            {"action": "get_dropdown_options", "payload": {}},
        ],
    }
    try:
        resp = requests.post(url, json=payload, timeout=60)
    except Exception as exc:
        print(f"[ERROR] request failed: {exc}")
        return 1
    if resp.status_code != 200:
        print(f"[ERROR] HTTP {resp.status_code}")
        print(resp.text)
        return 2

    data = resp.json()
    ok = data.get("ok")
    logs = data.get("actions_log") or []  # 兼容旧字段名

    for i, log in enumerate(logs):
        action = log.get("action", "")
        res = log.get("result", {})
        pl = (res.get("payload", res) if isinstance(res, dict) else res) or {}
        print(f"--- Step {i}: {action} ---")
        if action == "get_dropdown_options":
            opts = (pl or {}).get("options", [])
            print(f"options count: {len(opts)}")
            for j, o in enumerate(opts[:10]):
                print(f"  [{j}] handle={o.get('handle')} text={o.get('text')}")
            if len(opts) > 10:
                print(f"  ... and {len(opts) - 10} more")
            dbg = (pl or {}).get("_debug")
            if dbg:
                print("_debug:", dbg)
            if len(opts) == 0:
                raw = log.get("result") or {}
                p = raw.get("payload") or raw
                print("result type:", raw.get("type"), "| error:", p.get("error_code"), p.get("message"))
                print("payload keys:", list(p.keys()) if isinstance(p, dict) else "N/A")
        print()

    print(json.dumps({"ok": ok, "steps_count": len(logs)}, ensure_ascii=False, indent=2))
    return 0 if ok else 3


if __name__ == "__main__":
    sys.exit(main())
