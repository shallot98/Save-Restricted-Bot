"""
Unified Cache Implementation
============================

Unified cache implementation based on TTLCache with event support.
"""

import time
import logging
import threading
import fnmatch
from typing import TypeVar, Optional, Dict, Any, Callable, List

from .interface import CacheInterface, CacheEventListener, InvalidationStrategy
from .unified_models import CacheEntry, CacheStats
from .unified_options import UnifiedCacheOptions, unified_cache_options

logger = logging.getLogger(__name__)

T = TypeVar('T')


class UnifiedCache(CacheInterface[T]):
    """
    Unified cache implementation

    Thread-safe in-memory cache with:
    - TTL support
    - LRU eviction
    - Event-based invalidation
    - Statistics tracking
    """

    def __init__(
        self,
        options: UnifiedCacheOptions | float | None = None,
        *legacy_args: Any,
        default_ttl: Optional[float] = None,
        max_size: Optional[int] = None,
        cleanup_interval: Optional[float] = None,
        invalidation_strategy: Optional[InvalidationStrategy] = None,
        name: Optional[str] = None,
    ) -> None:
        """
        Initialize unified cache

        Args:
            default_ttl: Default time-to-live in seconds
            max_size: Maximum cache size
            cleanup_interval: Cleanup interval in seconds
            invalidation_strategy: Cache invalidation strategy
            name: Cache instance name (for logging)
        """
        options = unified_cache_options(
            options,
            legacy_args,
            default_ttl=default_ttl,
            max_size=max_size,
            cleanup_interval=cleanup_interval,
            invalidation_strategy=invalidation_strategy,
            name=name,
        )
        self._cache: Dict[str, CacheEntry] = {}
        self._default_ttl = options.default_ttl
        self._max_size = options.max_size
        self._lock = threading.RLock()
        self._last_cleanup = time.time()
        self._cleanup_interval = options.cleanup_interval
        self._invalidation_strategy = options.invalidation_strategy
        self._name = options.name
        self._stats = CacheStats()
        self._listeners: List[CacheEventListener] = []

        logger.info(
            f"UnifiedCache '{options.name}' initialized: "
            f"ttl={options.default_ttl}s, max_size={options.max_size}, "
            f"strategy={options.invalidation_strategy.value}"
        )

    def get(self, key: str) -> Optional[T]:
        """Get value from cache"""
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._stats.record_miss()
                return None
            if entry.is_expired:
                del self._cache[key]
                self._stats.record_miss()
                return None
            entry.access_count += 1
            self._stats.record_hit()
            return entry.value

    def set(self, key: str, value: T, ttl: Optional[float] = None) -> None:
        """Set value in cache"""
        with self._lock:
            self._maybe_cleanup()

            if len(self._cache) >= self._max_size:
                self._evict_lru()

            now = time.time()
            expires_at = now + (ttl or self._default_ttl)
            self._cache[key] = CacheEntry(
                value=value,
                expires_at=expires_at,
                created_at=now
            )
            self._stats.record_set()

        # Notify listeners
        self._notify_set(key, value)

    def delete(self, key: str) -> bool:
        """Delete value from cache"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                self._stats.record_delete()
                self._notify_delete(key)
                return True
            return False

    def clear(self) -> None:
        """Clear all cached values"""
        with self._lock:
            self._cache.clear()
            self._notify_clear()
            logger.info(f"Cache '{self._name}' cleared")

    def get_or_set(
        self,
        key: str,
        factory: Callable[[], T],
        ttl: Optional[float] = None
    ) -> T:
        """Get value from cache or compute and cache it"""
        # First try without lock for performance
        value = self.get(key)
        if value is not None:
            return value

        # Double-check with lock
        with self._lock:
            value = self.get(key)
            if value is not None:
                return value

            # Compute and cache
            value = factory()
            self.set(key, value, ttl)
            return value

    def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return False
            if entry.is_expired:
                del self._cache[key]
                return False
            return True

    def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern (supports * wildcard)"""
        with self._lock:
            keys_to_delete = [
                key for key in self._cache.keys()
                if fnmatch.fnmatch(key, pattern)
            ]
            for key in keys_to_delete:
                del self._cache[key]
                self._notify_delete(key)

            if keys_to_delete:
                logger.debug(
                    f"Cache '{self._name}': deleted {len(keys_to_delete)} "
                    f"keys matching '{pattern}'"
                )
            return len(keys_to_delete)

    def delete_prefix(self, prefix: str) -> int:
        """Delete all keys with given prefix"""
        return self.delete_pattern(f"{prefix}*")

    @property
    def size(self) -> int:
        """Get current cache size"""
        return len(self._cache)

    def stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._lock:
            expired_count = sum(1 for e in self._cache.values() if e.is_expired)
            return {
                "name": self._name,
                "size": len(self._cache),
                "max_size": self._max_size,
                "expired_count": expired_count,
                "default_ttl": self._default_ttl,
                "invalidation_strategy": self._invalidation_strategy.value,
                **self._stats.to_dict()
            }

    def reset_stats(self) -> None:
        """Reset statistics"""
        self._stats.reset()

    # Event listener management

    def add_listener(self, listener: CacheEventListener) -> None:
        """Add event listener"""
        self._listeners.append(listener)

    def remove_listener(self, listener: CacheEventListener) -> None:
        """Remove event listener"""
        if listener in self._listeners:
            self._listeners.remove(listener)

    def _notify_set(self, key: str, value: Any) -> None:
        """Notify listeners of set event"""
        for listener in self._listeners:
            try:
                listener.on_set(key, value)
            except Exception as e:
                logger.error(f"Listener error on set: {e}")

    def _notify_delete(self, key: str) -> None:
        """Notify listeners of delete event"""
        for listener in self._listeners:
            try:
                listener.on_delete(key)
            except Exception as e:
                logger.error(f"Listener error on delete: {e}")

    def _notify_clear(self) -> None:
        """Notify listeners of clear event"""
        for listener in self._listeners:
            try:
                listener.on_clear()
            except Exception as e:
                logger.error(f"Listener error on clear: {e}")

    # Internal methods

    def _maybe_cleanup(self) -> None:
        """Cleanup expired entries if interval has passed"""
        now = time.time()
        if now - self._last_cleanup > self._cleanup_interval:
            self._cleanup_expired()
            self._last_cleanup = now

    def _cleanup_expired(self) -> None:
        """Remove all expired entries"""
        expired_keys = [
            key for key, entry in self._cache.items()
            if entry.is_expired
        ]
        for key in expired_keys:
            del self._cache[key]

        if expired_keys:
            logger.debug(
                f"Cache '{self._name}': cleaned up {len(expired_keys)} expired entries"
            )

    def _evict_lru(self) -> None:
        """Evict least recently used entry when cache is full"""
        if not self._cache:
            return

        # Find entry with lowest access count (LRU approximation)
        lru_key = min(
            self._cache.keys(),
            key=lambda k: (self._cache[k].access_count, self._cache[k].created_at)
        )
        del self._cache[lru_key]
        logger.debug(f"Cache '{self._name}': evicted LRU key '{lru_key}'")


from .unified_factory import get_unified_cache


__all__ = [
    "UnifiedCache",
    "CacheEntry",
    "CacheStats",
    "get_unified_cache",
]
