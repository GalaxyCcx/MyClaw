#!/usr/bin/env python3
"""
手动打开下拉后测试 get_dropdown_options 和点击选项。

用法：1) 在浏览器中打开 Alpha BI 页面  2) 手动点击任意下拉展开  3) 运行此脚本
"""
from __future__ import annotations

import json
import sys
import requests

def main() -> int:
    url = "http://127.0.0.1:8000/api/browser/actions/execute"
    payload = {
        "steps": [
            {"action": "get_dropdown_options", "payload": {}},
            {"action": "wait", "payload": {"ms": 500}},
        ],
    }
    try:
        resp = requests.post(url, json=payload, timeout=30)
    except Exception as exc:
        print(f"[ERROR] {exc}")
        return 1
    if resp.status_code != 200:
        print(f"[ERROR] HTTP {resp.status_code}")
        return 2
    data = resp.json()
    logs = data.get("actions_log") or []
    for log in logs:
        if log.get("action") == "get_dropdown_options":
            res = log.get("result", {})
            pl = res.get("payload", res) or {}
            opts = pl.get("options", [])
            dbg = pl.get("_debug")
            print("options count:", len(opts))
            if dbg:
                print("_debug:", json.dumps(dbg, ensure_ascii=False, indent=2)[:500])
            for i, o in enumerate(opts[:15]):
                print(f"  [{i}] {o.get('text')} (handle={o.get('handle')})")
            if len(opts) > 15:
                print("  ...")
            target = "蔬菜组" if "蔬菜组" in [o.get("text") for o in opts] else (opts[0].get("text") if opts else None)
            if target and target in [o.get("text") for o in opts]:
                idx = next(i for i, o in enumerate(opts) if o.get("text") == target)
                handle = opts[idx].get("handle")
                if handle:
                    print("\nTrying to click", target, "...")
                    r2 = requests.post(url, json={
                        "steps": [
                            {"action": "click", "payload": {"locator": {"handle": handle}}},
                        ],
                    }, timeout=15)
                    print("click result:", r2.json().get("ok"))
            return 0 if opts else 3
    return 3

if __name__ == "__main__":
    sys.exit(main())
