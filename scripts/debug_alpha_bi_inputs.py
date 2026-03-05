from __future__ import annotations

import requests


def main() -> int:
    base = "http://127.0.0.1:8000/api/browser/actions/execute"
    url = (
        "https://alpha-bi.ddxq.mobi/report?"
        "pathIds=279b4f5efc6d446886b3662773c25b3c,cc4baf96c7344900918887be30cf56de"
        "&dashboardId=d127af3f0bb3457287f5093bdea78846"
        "&externalSpaceId=fccdafe6147b461d94425137c51ffe2e"
        "&appId=36620ff9365540a2b6a36531a5dcef6b"
        "&iframeType=app&orgId=1&spaceId=fccdafe6147b461d94425137c51ffe2e"
    )
    steps: list[dict] = [
        {"action": "navigate", "payload": {"url": url}},
        {"action": "wait", "payload": {"ms": 25000}},
    ]
    for i in range(40):
        steps.append({"action": "locate", "payload": {"selector": "input", "index": i}})
        steps.append({"action": "assert", "payload": {"selector": "input", "index": i}})

    resp = requests.post(
        base,
        json={"timeout_seconds": 35, "stop_on_error": False, "steps": steps},
        timeout=300,
    )
    data = resp.json()
    print("ok=", data.get("ok"), " steps=", len(data.get("actions_log") or []))
    logs = data.get("actions_log") or []
    for i in range(40):
        locate_row = logs[2 + i * 2]
        assert_row = logs[3 + i * 2]
        locate_res = locate_row.get("result") or {}
        if locate_res.get("type") == "error":
            continue
        element = ((locate_res.get("payload") or {}).get("element") or {})
        assert_res = assert_row.get("result") or {}
        actual = ((assert_res.get("payload") or {}).get("actual") or {})
        print(
            {
                "index": i,
                "id": element.get("id"),
                "cls": str(element.get("cls") or "")[:100],
                "text": str(element.get("text") or "")[:30],
                "value": actual.get("value"),
            }
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
