#!/usr/bin/env python3
"""
回放 Alpha BI select-dropdown：品类组（二、问题定位 区块）。

前置：后端已启动，BROWSER_TRANSPORT=native_extension，v2 扩展已连接。
"""
from __future__ import annotations

import json
import sys

import requests

DEFAULT_BASE = "http://127.0.0.1:8000"
ALPHA_BI_URL = (
    "https://alpha-bi.ddxq.mobi/report?"
    "pathIds=279b4f5efc6d446886b3662773c25b3c,cc4baf96c7344900918887be30cf56de"
    "&dashboardId=d127af3f0bb3457287f5093bdea78846"
    "&externalSpaceId=fccdafe6147b461d94425137c51ffe2e"
    "&appId=36620ff9365540a2b6a36531a5dcef6b"
    "&iframeType=app&orgId=1&spaceId=fccdafe6147b461d94425137c51ffe2e"
)


def main() -> int:
    base = DEFAULT_BASE
    url = f"{base}/api/browser/jobs/alpha-bi/select-dropdown"
    payload = {
        "url": ALPHA_BI_URL,
        "wait_after_navigate_ms": 12000,
        "trigger_locator": {"selector": ".ant-select", "within": {"text": "二、问题定位"}, "index": 0},
        "target_value": "蔬菜组",
    }
    try:
        resp = requests.post(url, json=payload, timeout=90)
    except Exception as exc:
        print(f"[ERROR] {exc}")
        return 1
    if resp.status_code != 200:
        print(f"[ERROR] HTTP {resp.status_code}\n{resp.text}")
        return 2
    data = resp.json()
    print(json.dumps({"ok": data.get("ok"), "error": data.get("error"), "matched_option": data.get("matched_option")}, ensure_ascii=False, indent=2))
    return 0 if data.get("ok") else 3


if __name__ == "__main__":
    sys.exit(main())
