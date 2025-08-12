from __future__ import annotations
import time
from typing import Any, Dict, Tuple

class TTLCache:
    def __init__(self, ttl: int = 10):
        self.ttl = ttl
        self._store: Dict[str, Tuple[float, Any]] = {}

    def get(self, key: str):
        now = time.time()
        v = self._store.get(key)
        if not v:
            return None
        ts, data = v
        if now - ts > self.ttl:
            self._store.pop(key, None)
            return None
        return data

    def set(self, key: str, value: Any):
        self._store[key] = (time.time(), value)

default_cache = TTLCache(ttl=10)
