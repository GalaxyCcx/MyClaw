#!/usr/bin/env python3
"""
Alpha BI 报表：定位「贡献拆解1-商品分类」表，点击下载-原始数据，并跳转至任务中心。

前置条件：
1. 后端服务已启动（start.bat 或 uvicorn）
2. BROWSER_TRANSPORT=native_extension
3. 已安装 myclaw-browser-agent 扩展（非 v2，需支持 alpha_bi_download_table）
4. 扩展已连接 WebSocket（/ws/browser-gateway），浏览器标签页已打开或脚本会导航到报表页

用法：
    python scripts/alpha_bi_download_and_goto_task_center.py
    python scripts/alpha_bi_download_and_goto_task_center.py --no-goto  # 仅下载，不跳转任务中心
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 确保 backend 在 path 中
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

import requests

REPORT_URL = (
    "https://alpha-bi.ddxq.mobi/report?"
    "pathIds=279b4f5efc6d446886b3662773c25b3c,cc4baf96c734900918887be30cf56de"
    "&dashboardId=d127af3f0bb3455b87f5093bdea78846"
    "&externalSpaceId=fccdafe6147b461d94425137c51ffe2e"
    "&appId=36620ff9365540a2b6a36531a5dcef6b"
    "&iframeType=app&orgId=1&spaceId=fccdafe6147b461d94425137c51ffe2e"
)

# 表头关键词：▌二、问题定位-✔ [贡献拆解1]-商品分类
TABLE_KEYWORD = "✔ [贡献拆解1]-商品分类"
FILE_KEYWORD = "原始数据"
DEFAULT_BASE = "http://127.0.0.1:8000"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Alpha BI：下载「贡献拆解1-商品分类」原始数据并跳转任务中心"
    )
    parser.add_argument(
        "--base",
        default=DEFAULT_BASE,
        help=f"后端 API 地址 (默认 {DEFAULT_BASE})",
    )
    parser.add_argument(
        "--url",
        default=REPORT_URL,
        help="报表页面 URL（默认使用预置链接）",
    )
    parser.add_argument(
        "--table",
        default=TABLE_KEYWORD,
        help="表头关键词，默认匹配「贡献拆解1-商品分类」",
    )
    parser.add_argument(
        "--file",
        default=FILE_KEYWORD,
        help="下载类型关键词，默认「原始数据」",
    )
    parser.add_argument(
        "--no-goto",
        action="store_true",
        help="仅触发下载，不点击跳转任务中心",
    )
    parser.add_argument(
        "--wait-ms",
        type=int,
        default=25000,
        help="导航后等待毫秒 (默认 25000)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=240,
        help="请求超时秒数 (默认 240)",
    )
    args = parser.parse_args()

    payload = {
        "url": args.url,
        "table_keyword": args.table,
        "file_keyword": args.file,
        "wait_after_navigate_ms": args.wait_ms,
        "timeout_seconds": 180,
        "single_trigger_only": True,
        "goto_center_after_trigger": not args.no_goto,
    }

    endpoint = f"{args.base.rstrip('/')}/api/browser/jobs/alpha-bi/download"
    print(f"[INFO] POST {endpoint}")
    print(f"[INFO] 表: {args.table}, 下载类型: {args.file}, 跳转任务中心: {not args.no_goto}")

    try:
        # connect 5s, read args.timeout
        resp = requests.post(
            endpoint, json=payload, timeout=(5, args.timeout)
        )
    except requests.exceptions.ConnectionError as e:
        print(f"[ERROR] 无法连接后端: {e}")
        return 1
    except requests.exceptions.Timeout as e:
        print(f"[ERROR] 请求超时: {e}")
        return 2

    if resp.status_code != 200:
        print(f"[ERROR] HTTP {resp.status_code}")
        try:
            print(resp.json())
        except Exception:
            print(resp.text)
        return 3

    data = resp.json()
    ok = bool(data.get("ok"))
    msg = data.get("message", "")

    out = {
        "ok": ok,
        "message": msg,
        "failure_reason": data.get("failure_reason", ""),
        "trigger_count": data.get("trigger_count", 0),
        "menu_target": data.get("menu_target", ""),
    }
    if data.get("goto"):
        out["goto"] = data["goto"]

    print(json.dumps(out, ensure_ascii=False, indent=2))

    if ok:
        print("\n[OK] 下载已触发，已跳转至任务中心。")
    else:
        print(f"\n[FAIL] {msg}")

    return 0 if ok else 4


if __name__ == "__main__":
    sys.exit(main())
