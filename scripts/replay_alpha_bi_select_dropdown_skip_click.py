#!/usr/bin/env python3
"""
下拉已手动打开时，跳过点击直接执行 get_dropdown_options + 点击选项。
用法：1) 打开 Alpha BI 页面  2) 手动点击「二、问题定位」下的品类组展开  3) 运行此脚本
"""
from __future__ import annotations

import json
import sys
import requests

def main() -> int:
    url = "http://127.0.0.1:8000/api/browser/jobs/alpha-bi/select-dropdown"
    payload = {
        "trigger_locator": {"selector": ".ant-select", "within": {"text": "二、问题定位"}, "index": 0},
        "target_value": "蔬菜组",
        "skip_click": True,
    }
    try:
        resp = requests.post(url, json=payload, timeout=60)
    except Exception as exc:
        print(f"[ERROR] {exc}")
        return 1
    if resp.status_code != 200:
        print(f"[ERROR] HTTP {resp.status_code}")
        return 2
    d = resp.json()
    print(json.dumps({"ok": d.get("ok"), "error": d.get("error"), "matched_option": d.get("matched_option")}, ensure_ascii=False, indent=2))
    return 0 if bool(d.get("ok")) else 3

if __name__ == "__main__":
    sys.exit(main())
