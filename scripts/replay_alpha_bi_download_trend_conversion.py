#!/usr/bin/env python3
"""
触发 趋势分析 > 转化归因 tab > 图1/图2 的下载。

前置：后端已启动，BROWSER_TRANSPORT=native_extension，v2 扩展已连接。
"""
from __future__ import annotations

import json
import sys

import requests

# Windows 控制台 gbk 兼容
if sys.stdout.encoding and "gbk" in sys.stdout.encoding.lower():
    sys.stdout.reconfigure(encoding="utf-8")

BASE = "http://127.0.0.1:8000"
ALPHA_URL = (
    "https://alpha-bi.ddxq.mobi/report?"
    "pathIds=279b4f5efc6d446886b3662773c25b3c,cc4baf96c7344900918887be30cf56de"
    "&dashboardId=d127af3f0bb3457287f5093bdea78846"
    "&externalSpaceId=fccdafe6147b461d94425137c51ffe2e"
    "&appId=36620ff9365540a2b6a36531a5dcef6b"
    "&iframeType=app&orgId=1&spaceId=fccdafe6147b461d94425137c51ffe2e"
)


def main() -> int:
    # 一次请求：navigate + 点转化归因 tab + 下载
    # 用 四、趋势分析 做 within，确保命中趋势区块而非贡献拆解
    for within in ["四、趋势分析", "图1", "图2", "转化归因"]:
        r = requests.post(
            f"{BASE}/api/browser/jobs/alpha-bi/download-problem-locator",
            json={
                "url": ALPHA_URL,
                "wait_after_navigate_ms": 15000,
                "tab_text": "转化归因",
                "tab_within": "四、趋势分析",
                "within_text": within,
            },
            timeout=240,
        )
        dl_res = r.json()
        print(f"within_text={within}:", json.dumps(dl_res, ensure_ascii=True, indent=2))
        if dl_res.get("ok"):
            return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
