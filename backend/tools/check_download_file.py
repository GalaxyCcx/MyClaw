from __future__ import annotations

import json
import os
import time
from pathlib import Path

from langchain_core.tools import tool


def _default_download_dir() -> Path:
    user_profile = os.getenv("USERPROFILE")
    if user_profile:
        return Path(user_profile) / "Downloads"
    return Path.home() / "Downloads"


@tool
def check_download_file(
    keyword: str,
    download_dir: str = "",
    timeout_seconds: int = 45,
    poll_interval_seconds: float = 2.0,
    modified_within_seconds: int = 600,
) -> str:
    """
    检查本地下载目录是否出现包含关键字的新文件（用于校验浏览器下载是否真正落盘）。
    返回 JSON 字符串：found、path、size_bytes、modified_at、checked_dir、matched_files。
    """
    keyword = (keyword or "").strip()
    if not keyword:
        return json.dumps({"error": "keyword 不能为空"}, ensure_ascii=False)

    base_dir = Path(download_dir).expanduser() if download_dir else _default_download_dir()
    if not base_dir.exists() or not base_dir.is_dir():
        return json.dumps(
            {"error": "下载目录不存在或不可访问", "checked_dir": str(base_dir)},
            ensure_ascii=False,
        )

    timeout_seconds = max(1, int(timeout_seconds))
    poll_interval_seconds = max(0.2, float(poll_interval_seconds))
    modified_within_seconds = max(1, int(modified_within_seconds))
    start = time.time()
    cutoff = start - modified_within_seconds

    while True:
        candidates: list[Path] = []
        for p in base_dir.iterdir():
            if not p.is_file():
                continue
            name = p.name.lower()
            if keyword.lower() not in name:
                continue
            stat = p.stat()
            if stat.st_mtime < cutoff:
                continue
            # 跳过 Chrome 临时下载文件
            if name.endswith(".crdownload") or name.endswith(".tmp"):
                continue
            candidates.append(p)

        candidates.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        if candidates:
            hit = candidates[0]
            st = hit.stat()
            return json.dumps(
                {
                    "found": True,
                    "path": str(hit),
                    "size_bytes": st.st_size,
                    "modified_at": st.st_mtime,
                    "checked_dir": str(base_dir),
                    "matched_files": [str(x) for x in candidates[:10]],
                },
                ensure_ascii=False,
            )

        if time.time() - start >= timeout_seconds:
            return json.dumps(
                {
                    "found": False,
                    "checked_dir": str(base_dir),
                    "keyword": keyword,
                    "timeout_seconds": timeout_seconds,
                    "message": "超时未发现目标下载文件",
                },
                ensure_ascii=False,
            )

        time.sleep(poll_interval_seconds)
