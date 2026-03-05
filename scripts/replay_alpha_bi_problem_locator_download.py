#!/usr/bin/env python3
"""
回放 Alpha BI「▌二、问题定位」表下载 Job。

前置：后端已启动，BROWSER_TRANSPORT=native_extension，v2 扩展已连接，浏览器已打开目标页或脚本会导航。
"""
from __future__ import annotations

import json
import sys

import requests

DEFAULT_BASE = "http://127.0.0.1:8000"


def main() -> int:
    base = DEFAULT_BASE
    url = f"{base}/api/browser/jobs/alpha-bi/download-problem-locator"
    payload = {
        "wait_after_navigate_ms": 25000,
        "download_icon_index": 1,
    }
    try:
        resp = requests.post(url, json=payload, timeout=240)
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
        "message": data.get("message"),
        "stage": data.get("stage"),
        "actions_count": len(data.get("actions_log") or []),
        "poll_details": data.get("poll_details"),
        "snapshot_preview": data.get("snapshot_preview"),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if bool(data.get("ok")) else 3


if __name__ == "__main__":
    sys.exit(main())
