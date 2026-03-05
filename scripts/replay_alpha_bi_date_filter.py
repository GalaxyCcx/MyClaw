#!/usr/bin/env python3
"""
回放 Alpha BI date-filter Job：设置当期/对比期日期范围。

前置：后端已启动，BROWSER_TRANSPORT=native_extension，v2 扩展已连接。
"""
from __future__ import annotations

import calendar
import json
import sys
from datetime import datetime

import requests

DEFAULT_BASE = "http://127.0.0.1:8000"


def main() -> int:
    base = DEFAULT_BASE
    now = datetime.now()
    # 当月 1 号 ~ 当月最后一天
    start = f"{now.year:04d}-{now.month:02d}-01"
    end_day = calendar.monthrange(now.year, now.month)[1]
    end = f"{now.year:04d}-{now.month:02d}-{end_day:02d}"
    # 对比期：上月同期
    prev_month = now.month - 1 if now.month > 1 else 12
    prev_year = now.year if now.month > 1 else now.year - 1
    compare_start = f"{prev_year:04d}-{prev_month:02d}-01"
    compare_end_day = calendar.monthrange(prev_year, prev_month)[1]
    compare_end = f"{prev_year:04d}-{prev_month:02d}-{compare_end_day:02d}"

    api_url = f"{base}/api/browser/jobs/alpha-bi/date-filter"
    alpha_bi_url = (
        "https://alpha-bi.ddxq.mobi/report?"
        "pathIds=279b4f5efc6d446886b3662773c25b3c,cc4baf96c7344900918887be30cf56de"
        "&dashboardId=d127af3f0bb3457287f5093bdea78846"
        "&externalSpaceId=fccdafe6147b461d94425137c51ffe2e"
        "&appId=36620ff9365540a2b6a36531a5dcef6b"
        "&iframeType=app&orgId=1&spaceId=fccdafe6147b461d94425137c51ffe2e"
    )
    payload = {
        "url": alpha_bi_url,
        "current_start": start,
        "current_end": end,
        "compare_start": compare_start,
        "compare_end": compare_end,
        "wait_after_navigate_ms": 25000,
    }
    try:
        resp = requests.post(api_url, json=payload, timeout=120)
    except Exception as exc:
        print(f"[ERROR] {exc}")
        return 1
    if resp.status_code != 200:
        print(f"[ERROR] HTTP {resp.status_code}\n{resp.text}")
        return 2
    data = resp.json()
    ok = data.get("ok")
    dates = data.get("dates_after") or {}
    print(json.dumps({"ok": ok, "dates_after": dates}, ensure_ascii=False, indent=2))
    return 0 if ok else 3


if __name__ == "__main__":
    sys.exit(main())
