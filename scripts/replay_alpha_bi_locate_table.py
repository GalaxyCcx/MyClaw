#!/usr/bin/env python3
"""
回放 Alpha BI locate-table Job：逐表测试，每张表 ok=true, found=true。

前置：后端已启动，BROWSER_TRANSPORT=native_extension，v2 扩展已连接。
按清单 docs/alpha-bi-test-checklist.md 执行。
"""
from __future__ import annotations

import json
import sys
import io

if sys.stdout.encoding and "utf" not in sys.stdout.encoding.lower():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from pathlib import Path

import requests

DEFAULT_BASE = "http://127.0.0.1:8000"


def main() -> int:
    base = DEFAULT_BASE
    tables_json = Path(__file__).resolve().parent.parent / "backend" / "memory" / "alpha_bi_tables.json"
    tables = []
    if tables_json.exists():
        data = json.loads(tables_json.read_text(encoding="utf-8"))
        tables = [t["name"] for t in data.get("tables", [])]
    if not tables:
        tables = ["✔ [贡献拆解1]-商品分类", "✔ [过程拆解2]-补充订单&用户"]

    url = f"{base}/api/browser/jobs/alpha-bi/locate-table"
    all_ok = True
    for table in tables:
        try:
            resp = requests.post(url, json={"table_keyword": table, "wait_after_navigate_ms": 25000}, timeout=90)
        except Exception as exc:
            print(f"[ERROR] {table}: {exc}")
            all_ok = False
            continue
        if resp.status_code != 200:
            print(f"[ERROR] {table}: HTTP {resp.status_code}")
            all_ok = False
            continue
        data = resp.json()
        ok = data.get("ok")
        found = data.get("found")
        block = data.get("block_hint")
        if ok and found:
            print(f"[OK] {table} -> block={block}")
        else:
            print(f"[FAIL] {table} ok={ok} found={found}")
            all_ok = False

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
