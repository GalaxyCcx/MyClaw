#!/usr/bin/env python3
"""
回放 Alpha BI 复选组 Job。

前置：后端已启动，BROWSER_TRANSPORT=native_extension，v2 扩展已连接。
若页面存在 ant-checkbox-group（如采一/采二/采三），则能勾选；否则 clicked_count=0。
"""
from __future__ import annotations

import json
import sys

import requests

DEFAULT_BASE = "http://127.0.0.1:8000"
DEFAULT_URL = (
    "https://alpha-bi.ddxq.mobi/report?"
    "pathIds=279b4f5efc6d446886b3662773c25b3c,cc4baf96c7344900918887be30cf56de"
    "&dashboardId=d127af3f0bb3457287f5093bdea78846"
    "&externalSpaceId=fccdafe6147b461d94425137c51ffe2e"
    "&appId=36620ff9365540a2b6a36531a5dcef6b"
    "&iframeType=app&orgId=1&spaceId=fccdafe6147b461d94425137c51ffe2e"
)


def main() -> int:
    base = DEFAULT_BASE
    url = f"{base}/api/browser/jobs/alpha-bi/select-checkbox-group"
    payload = {
        "url": DEFAULT_URL,
        "wait_after_navigate_ms": 8000,
        "within_text": "二、问题定位",
        "option_texts": ["采一", "采二", "采三"],
    }
    try:
        resp = requests.post(url, json=payload, timeout=90)
    except Exception as exc:
        print(f"[ERROR] request failed: {exc}")
        return 1
    if resp.status_code != 200:
        print(f"[ERROR] HTTP {resp.status_code}")
        print(resp.text)
        return 2

    data = resp.json()
    out = {
        "ok": data.get("ok"),
        "clicked_count": data.get("clicked_count"),
        "target_count": data.get("target_count"),
        "actions_count": len(data.get("actions_log") or []),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    # 若页面无复选组，clicked_count=0 属预期，仍返回 0（job 执行成功）
    return 0 if data.get("clicked_count") is not None else 3


if __name__ == "__main__":
    sys.exit(main())
