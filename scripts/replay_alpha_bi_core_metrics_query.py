from __future__ import annotations

import json
import sys
from datetime import datetime

import requests


def main() -> int:
    base = "http://127.0.0.1:8000"
    url = f"{base}/api/browser/jobs/alpha-bi/core-metrics-date-query"
    payload = {
        "year": datetime.now().year,
        "max_attempts": 3,
        "post_query_wait_ms": 1800,
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
        "failure_stage": data.get("failure_stage"),
        "query_clicked": data.get("query_clicked"),
        "expected": data.get("expected"),
        "actual": data.get("actual"),
        "evidence": data.get("evidence"),
        "attempt_count": len(data.get("attempts") or []),
    }
    print(json.dumps(out, ensure_ascii=False))
    return 0 if bool(data.get("ok")) else 3


if __name__ == "__main__":
    sys.exit(main())
