from __future__ import annotations

import base64
import logging
import os
import re
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    import oss2  # type: ignore
except Exception:  # pragma: no cover - optional dependency runtime guard
    oss2 = None


_DATA_URL_RE = re.compile(r"^data:(image/[a-zA-Z0-9.+-]+);base64,(.+)$", re.DOTALL)
_MIME_EXT = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/webp": "webp",
    "image/gif": "gif",
}


def _oss_config() -> dict[str, str]:
    return {
        "endpoint": os.getenv("OSS_ENDPOINT", "").strip(),
        "bucket": os.getenv("OSS_BUCKET", "").strip(),
        "access_key_id": os.getenv("OSS_ACCESS_KEY_ID", "").strip(),
        "access_key_secret": os.getenv("OSS_ACCESS_KEY_SECRET", "").strip(),
        "prefix": os.getenv("OSS_PREFIX", "tmp/vision/").strip() or "tmp/vision/",
    }


def _parse_data_url(data_url: str) -> tuple[str, bytes] | None:
    m = _DATA_URL_RE.match(data_url)
    if not m:
        return None
    mime = m.group(1).lower()
    raw_b64 = m.group(2)
    try:
        blob = base64.b64decode(raw_b64, validate=False)
    except Exception:
        return None
    return mime, blob


def _build_object_key(prefix: str, image_id: str, mime: str) -> str:
    safe_prefix = prefix.strip("/")
    ext = _MIME_EXT.get(mime, "bin")
    now = datetime.utcnow().strftime("%Y%m%d/%H%M%S")
    if safe_prefix:
        return f"{safe_prefix}/{now}_{image_id}.{ext}"
    return f"{now}_{image_id}.{ext}"


def upload_data_url_and_sign(image_id: str, data_url: str) -> str | None:
    """Upload a data URL image to OSS and return signed GET URL."""
    if oss2 is None:
        return None

    cfg = _oss_config()
    if not all([cfg["endpoint"], cfg["bucket"], cfg["access_key_id"], cfg["access_key_secret"]]):
        return None

    parsed = _parse_data_url(data_url)
    if not parsed:
        return None
    mime, blob = parsed

    try:
        auth = oss2.Auth(cfg["access_key_id"], cfg["access_key_secret"])
        bucket = oss2.Bucket(auth, cfg["endpoint"], cfg["bucket"])
        key = _build_object_key(cfg["prefix"], image_id, mime)
        headers = {"Content-Type": mime}
        bucket.put_object(key, blob, headers=headers)

        expires = max(30, int(os.getenv("OSS_SIGN_EXPIRES_SECONDS", "300")))
        signed = bucket.sign_url("GET", key, expires)
        return str(signed)
    except Exception as e:
        logger.warning("OSS upload/sign failed: %s", e)
        return None

