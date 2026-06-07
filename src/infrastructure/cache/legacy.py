"""Legacy in-memory TTL cache implementations."""

import logging
import threading
import time
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, Dict, Generic, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class CacheEntry(Generic[T]):
    """Cache entry with expiration."""

    value: T
    expires_at: float

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at


class TTLCache(Generic[T]):
    """Thread-safe in-memory cache with TTL support."""

    def __init__(
        self,
        default_ttl: float = 60.0,
        max_size: int = 1000,
        cleanup_interval: float = 60.0,
    ) -> None:
        self._cache: Dict[str, CacheEntry[T]] = {}
        self._default_ttl = default_ttl
        self._max_size = max_size
        self._lock = threading.RLock()
        self._last_cleanup = time.time()
        self._cleanup_interval = cleanup_interval

    def get(self, key: str) -> Optional[T]:
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            if entry.is_expired:
                del self._cache[key]
                return None
            return entry.value

    def set(self, key: str, value: T, ttl: Optional[float] = None) -> None:
        with self._lock:
            self._maybe_cleanup()
            if len(self._cache) >= self._max_size:
                self._evict_oldest()

            expires_at = time.time() + (ttl or self._default_ttl)
            self._cache[key] = CacheEntry(value=value, expires_at=expires_at)

    def delete(self, key: str) -> bool:
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    def get_or_set(self, key: str, factory: Callable[[], T], ttl: Optional[float] = None) -> T:
        value = self.get(key)
        if value is not None:
            return value

        value = factory()
        self.set(key, value, ttl)
        return value

    def _maybe_cleanup(self) -> None:
        now = time.time()
        if now - self._last_cleanup > self._cleanup_interval:
            self._cleanup_expired()
            self._last_cleanup = now

    def _cleanup_expired(self) -> None:
        expired_keys = [key for key, entry in self._cache.items() if entry.is_expired]
        for key in expired_keys:
            del self._cache[key]

    def _evict_oldest(self) -> None:
        if not self._cache:
            return

        oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k].expires_at)
        del self._cache[oldest_key]

    @property
    def size(self) -> int:
        return len(self._cache)

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            expired_count = sum(1 for e in self._cache.values() if e.is_expired)
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "expired_count": expired_count,
                "default_ttl": self._default_ttl,
            }


_global_cache: Optional[TTLCache] = None
_cache_lock = threading.Lock()


def get_cache(default_ttl: float = 300.0, max_size: int = 10000) -> TTLCache:
    """Get global legacy TTL cache singleton."""
    global _global_cache
    if _global_cache is None:
        with _cache_lock:
            if _global_cache is None:
                _global_cache = TTLCache(default_ttl=default_ttl, max_size=max_size)
                logger.info(f"Global cache initialized: ttl={default_ttl}s, max_size={max_size}")
    return _global_cache


def cached(ttl: float = 300.0, key_prefix: str = "") -> Callable:
    """Legacy caching decorator."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = _build_cache_key(CacheKeyRequest(key_prefix, func, args, kwargs))
            cache = get_cache()
            cached_value = cache.get(cache_key)

            if cached_value is not None:
                logger.debug(f"Cache hit: {cache_key}")
                return cached_value

            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl)
            logger.debug(f"Cache set: {cache_key}")
            return result

        return wrapper

    return decorator


@dataclass(frozen=True)
class CacheKeyRequest:
    key_prefix: str
    func: Callable
    args: tuple
    kwargs: dict


def _build_cache_key(request: CacheKeyRequest) -> str:
    key_parts = [request.key_prefix, request.func.__name__]
    if request.args:
        key_parts.append(str(request.args))
    if request.kwargs:
        key_parts.append(str(sorted(request.kwargs.items())))
    return ":".join(filter(None, key_parts))


class PeerCache(TTLCache[Dict[str, Any]]):
    """Specialized cache for Telegram peer information."""

    def __init__(self) -> None:
        super().__init__(
            default_ttl=3600.0,
            max_size=1000,
            cleanup_interval=300.0,
        )

    def get_peer(self, peer_id: str) -> Optional[Dict[str, Any]]:
        return self.get(f"peer:{peer_id}")

    def set_peer(self, peer_id: str, peer_info: Dict[str, Any]) -> None:
        self.set(f"peer:{peer_id}", peer_info)

    def invalidate_peer(self, peer_id: str) -> bool:
        return self.delete(f"peer:{peer_id}")


class MessageCache(TTLCache[Any]):
    """Short TTL cache to prevent duplicate message processing."""

    def __init__(self) -> None:
        super().__init__(
            default_ttl=60.0,
            max_size=5000,
            cleanup_interval=30.0,
        )

    def is_duplicate(self, message_id: str) -> bool:
        return self.get(f"msg:{message_id}") is not None

    def mark_processed(self, message_id: str) -> None:
        self.set(f"msg:{message_id}", True)
