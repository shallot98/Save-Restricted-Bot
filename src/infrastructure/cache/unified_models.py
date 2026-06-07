"""Models used by UnifiedCache."""

import threading
import time
from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class CacheEntry:
    """Cache entry with expiration and metadata."""

    value: Any
    expires_at: float
    created_at: float
    access_count: int = 0

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at


class CacheStats:
    """Cache statistics tracker."""

    def __init__(self):
        self._hits = 0
        self._misses = 0
        self._sets = 0
        self._deletes = 0
        self._lock = threading.Lock()

    def record_hit(self) -> None:
        with self._lock:
            self._hits += 1

    def record_miss(self) -> None:
        with self._lock:
            self._misses += 1

    def record_set(self) -> None:
        with self._lock:
            self._sets += 1

    def record_delete(self) -> None:
        with self._lock:
            self._deletes += 1

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hits": self._hits,
            "misses": self._misses,
            "sets": self._sets,
            "deletes": self._deletes,
            "hit_rate": round(self.hit_rate * 100, 2),
        }

    def reset(self) -> None:
        with self._lock:
            self._hits = 0
            self._misses = 0
            self._sets = 0
            self._deletes = 0
