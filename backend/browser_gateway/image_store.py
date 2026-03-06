from __future__ import annotations

import threading
import time
import uuid
from collections import OrderedDict


class BrowserImageStore:
    """In-memory cache for browser screenshots returned by tools."""

    def __init__(self, max_items: int = 80, ttl_seconds: int = 1800) -> None:
        self._max_items = max(1, int(max_items))
        self._ttl_seconds = max(60, int(ttl_seconds))
        self._lock = threading.Lock()
        self._items: OrderedDict[str, tuple[float, str]] = OrderedDict()

    def put(self, data_url: str) -> str:
        image_id = uuid.uuid4().hex[:16]
        now = time.time()
        with self._lock:
            self._items[image_id] = (now, data_url)
            self._items.move_to_end(image_id)
            self._evict_locked(now)
        return image_id

    def get(self, image_id: str) -> str | None:
        now = time.time()
        with self._lock:
            item = self._items.get(image_id)
            if item is None:
                return None
            created_at, data_url = item
            if now - created_at > self._ttl_seconds:
                self._items.pop(image_id, None)
                return None
            self._items.move_to_end(image_id)
            return data_url

    def _evict_locked(self, now: float) -> None:
        expired = [k for k, (ts, _v) in self._items.items() if now - ts > self._ttl_seconds]
        for k in expired:
            self._items.pop(k, None)
        while len(self._items) > self._max_items:
            self._items.popitem(last=False)


_STORE = BrowserImageStore()


def put_browser_image(data_url: str) -> str:
    return _STORE.put(data_url)


def get_browser_image(image_id: str) -> str | None:
    return _STORE.get(image_id)

