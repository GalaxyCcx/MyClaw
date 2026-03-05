#!/usr/bin/env python3
"""调试 Alpha BI 下拉：点击后 snapshot 看页面内容。"""
from __future__ import annotations

import requests

URL = "https://alpha-bi.ddxq.mobi/report?pathIds=279b4f5efc6d446886b3662773c25b3c,cc4baf96c7344900918887be30cf56de&dashboardId=d127af3f0bb3457287f5093bdea78846&externalSpaceId=fccdafe6147b461d94425137c51ffe2e&appId=36620ff9365540a2b6a36531a5dcef6b&iframeType=app&orgId=1&spaceId=fccdafe6147b461d94425137c51ffe2e"

def main():
    r = requests.post("http://127.0.0.1:8000/api/browser/actions/execute", json={
        "url": URL,
        "wait_after_navigate_ms": 12000,
        "steps": [
            {"action": "click", "payload": {"locator": {"selector": ".ant-select", "text": "合计", "index": 0}}},
            {"action": "wait", "payload": {"ms": 2500}},
            {"action": "snapshot", "payload": {}},
        ],
    }, timeout=90)
    d = r.json()
    for log in d.get("actions_log", []):
        act = log.get("action")
        res = log.get("result", {})
        if act == "snapshot" and res.get("type") != "error":
            pl = res.get("payload", res) or {}
            snap = pl.get("snapshot", pl)
            txt = (snap.get("text") or "")[:1500] if isinstance(snap, dict) else str(snap)[:1500]
            with open("debug_snapshot.txt", "w", encoding="utf-8") as f:
                f.write(txt)
            print("Snapshot saved to debug_snapshot.txt, len=", len(txt))
            print("Contains 全品类:", "全品类" in txt)
            print("=== Contains 品类组 ===", "品类组" in txt)
    return 0

if __name__ == "__main__":
    exit(main())
