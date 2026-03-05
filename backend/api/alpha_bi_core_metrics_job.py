from __future__ import annotations

import calendar
import hashlib
import re


def month_range_ymd(year: int, month: int) -> tuple[str, str]:
    last_day = calendar.monthrange(year, month)[1]
    start = f"{year:04d}-{month:02d}-01"
    end = f"{year:04d}-{month:02d}-{last_day:02d}"
    return start, end


def text_hash(v: str) -> str:
    return hashlib.sha1(str(v or "").encode("utf-8")).hexdigest()[:16]


def extract_snapshot_text_and_elements(snapshot_res: dict) -> tuple[str, list[dict]]:
    payload = snapshot_res.get("payload") if isinstance(snapshot_res, dict) else {}
    if not isinstance(payload, dict):
        payload = {}
    snap = payload.get("snapshot") if isinstance(payload.get("snapshot"), dict) else {}
    text = str(snap.get("text") or "")
    elements = snap.get("elements") if isinstance(snap.get("elements"), list) else []
    out_elements: list[dict] = []
    for item in elements:
        if isinstance(item, dict):
            out_elements.append(item)
    return text, out_elements


def find_query_ref(elements: list[dict]) -> str:
    best_ref = ""
    best_score = -1
    for item in elements:
        ref = str(item.get("ref") or "").strip()
        if not ref:
            continue
        tag = str(item.get("tag") or "").lower()
        role = str(item.get("role") or "").lower()
        label = str(item.get("label") or "")
        label_norm = re.sub(r"\s+", "", label)
        score = 0
        if "查询" in label_norm:
            score += 100
        if "query" in label_norm.lower():
            score += 60
        if tag == "button":
            score += 20
        if role == "button":
            score += 20
        if score > best_score:
            best_score = score
            best_ref = ref
    return best_ref
