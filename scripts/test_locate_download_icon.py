#!/usr/bin/env python3
"""
测试 趋势分析 > 转化归因 tab 下 下载图标的定位。
先测通定位，再测下载。
"""
from __future__ import annotations

import json
import sys

import requests

BASE = "http://127.0.0.1:8000"


def main() -> int:
    # 1) within 四、趋势分析
    print("=== 1. within 四、趋势分析 ===")
    r = requests.post(
        f"{BASE}/api/browser/jobs/alpha-bi/locate-download-icon",
        json={"within_text": "四、趋势分析"},
        timeout=90,
    )
    if r.status_code != 200:
        print("HTTP", r.status_code, r.text[:300])
        return 1
    d = r.json()
    print("ok:", d.get("ok"))
    for r0 in d.get("results", []):
        print("  found:", r0.get("found"), "| text:", r0.get("element_text"), "| cls:", r0.get("element_cls"))

    # 2) 先点 tab 再 within
    print("\n=== 2. tab 转化归因 + within 四、趋势分析 ===")
    r = requests.post(
        f"{BASE}/api/browser/jobs/alpha-bi/locate-download-icon",
        json={
            "tab_text": "转化归因",
            "tab_within": "四、趋势分析",
            "within_text": "四、趋势分析",
        },
        timeout=90,
    )
    if r.status_code != 200:
        print("HTTP", r.status_code, r.text[:300])
        return 2
    d = r.json()
    print("ok:", d.get("ok"))
    for r0 in d.get("results", []):
        print("  found:", r0.get("found"), "| text:", r0.get("element_text"), "| cls:", r0.get("element_cls"))

    # 3) 无 within 对比（应命中贡献拆解）
    print("\n=== 3. 无 within 对比（index 0） ===")
    r = requests.post(
        f"{BASE}/api/browser/jobs/alpha-bi/locate-download-icon",
        json={},
        timeout=90,
    )
    if r.status_code != 200:
        print("HTTP", r.status_code)
        return 3
    d = r.json()
    print("ok:", d.get("ok"))
    for r0 in d.get("results", []):
        print("  found:", r0.get("found"), "| text:", r0.get("element_text"), "| cls:", r0.get("element_cls"))

    return 0


if __name__ == "__main__":
    sys.exit(main())
