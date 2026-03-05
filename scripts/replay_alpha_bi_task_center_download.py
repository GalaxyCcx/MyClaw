#!/usr/bin/env python3
"""
回放 Alpha BI 任务中心下载 Job。
完整流程：Alpha 数据页 -> 悬浮下载图标 -> 原始数据 -> 前往任务中心 -> 轮询 -> 下载。
（直接访问任务中心 URL 无效，必须通过上述跳转）
"""
from __future__ import annotations

import json
import sys

import requests

DEFAULT_BASE = "http://127.0.0.1:8000"


def main() -> int:
    base = DEFAULT_BASE
    url = f"{base}/api/browser/jobs/alpha-bi/task-center-download"
    payload = {
        "wait_after_navigate_ms": 25000,
    }
    try:
        resp = requests.post(url, json=payload, timeout=300)
    except Exception as exc:
        print(f"[ERROR] request failed: {exc}")
        return 1
    if resp.status_code != 200:
        print(f"[ERROR] HTTP {resp.status_code}")
        print(resp.text)
        return 2

    data = resp.json()
    actions_log = data.get("actions_log") or []
    dl_actions = [a for a in actions_log if a.get("action") in ("download_from_link", "click", "click_trusted") and "locator" in str(a.get("payload", {}))]
    # 找出每个 click 前最近的 locate，用于定位是哪个 locator 命中了错误元素
    locate_before_click = []
    for i, a in enumerate(actions_log):
        if a.get("action") in ("click", "click_trusted") and a.get("payload", {}).get("locator", {}).get("handle"):
            for j in range(i - 1, max(-1, i - 30), -1):
                prev = actions_log[j]
                if prev.get("action") == "locate":
                    loc_pl = prev.get("payload") or {}
                    loc = loc_pl.get("locator") or {}
                    el = (prev.get("result") or {}).get("payload") or {}
                    el_el = el.get("element") or {}
                    locate_before_click.append({
                        "locator": loc,
                        "element_cls": el_el.get("cls"),
                        "element_tag": el_el.get("tag"),
                        "element_text": el_el.get("text"),
                    })
                    break
    out = {
        "ok": data.get("ok"),
        "message": data.get("message"),
        "stage": data.get("stage"),
        "actions_count": len(actions_log),
        "poll_details": data.get("poll_details"),
        "snapshot_preview": data.get("snapshot_preview"),
        "download_related_actions": dl_actions[-5:],
        "locate_before_click": locate_before_click[-10:],
        "last_download_result": next((a.get("result") for a in reversed(actions_log) if a.get("action") == "download_from_link" and a.get("result", {}).get("payload", {}).get("ok")), None),
    }
    with open("D:/MyClaw/task_center_download_result.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("ok", out.get("ok"), "stage", out.get("stage"), "poll_count", len(out.get("poll_details") or []))
    return 0 if bool(data.get("ok")) else 3


if __name__ == "__main__":
    sys.exit(main())
