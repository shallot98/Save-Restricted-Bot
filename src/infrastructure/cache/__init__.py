"""
Cache Infrastructure
====================

In-memory caching implementations with thread-safety and TTL support.

Usage:
    from src.infrastructure.cache import get_cache, TTLCache, cached

    # Direct cache usage
    cache = get_cache()
    cache.set("key", "value", ttl=60)
    value = cache.get("key")

    # Decorator usage
    @cached(ttl=300, key_prefix="user")
    def get_user(user_id):
        return fetch_user_from_db(user_id)
"""

import time
import logging
import threading
from typing import TypeVar, Generic, Optional, Dict, Any, Callable
from dataclasses import dataclass
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class CacheEntry(Generic[T]):
    """Cache entry with expiration"""

    value: T
    expires_at: float

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at


class TTLCache(Generic[T]):
    """
    Time-to-live cache implementation

    Thread-safe in-memory cache with automatic expiration.
    """

    def __init__(
        self,
        default_ttl: float = 60.0,
        max_size: int = 1000,
        cleanup_interval: float = 60.0
    ) -> None:
        """
        Initialize cache

        Args:
            default_ttl: Default time-to-live in seconds
            max_size: Maximum cache size
            cleanup_interval: Cleanup interval in seconds
        """
        self._cache: Dict[str, CacheEntry[T]] = {}
        self._default_ttl = default_ttl
        self._max_size = max_size
        self._lock = threading.RLock()
        self._last_cleanup = time.time()
        self._cleanup_interval = cleanup_interval

    def get(self, key: str) -> Optional[T]:
        """
        Get value from cache

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            if entry.is_expired:
                del self._cache[key]
                return None
            return entry.value

    def set(
        self,
        key: str,
        value: T,
        ttl: Optional[float] = None
    ) -> None:
        """
        Set value in cache

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (uses default if not specified)
        """
        with self._lock:
            self._maybe_cleanup()

            if len(self._cache) >= self._max_size:
                self._evict_oldest()

            expires_at = time.time() + (ttl or self._default_ttl)
            self._cache[key] = CacheEntry(value=value, expires_at=expires_at)

    def delete(self, key: str) -> bool:
        """
        Delete value from cache

        Args:
            key: Cache key

        Returns:
            True if deleted, False if not found
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        """Clear all cached values"""
        with self._lock:
            self._cache.clear()

    def get_or_set(
        self,
        key: str,
        factory: Callable[[], T],
        ttl: Optional[float] = None
    ) -> T:
        """
        Get value from cache or compute and cache it

        Args:
            key: Cache key
            factory: Function to compute value if not cached
            ttl: Time-to-live in seconds

        Returns:
            Cached or computed value
        """
        value = self.get(key)
        if value is not None:
            return value

        value = factory()
        self.set(key, value, ttl)
        return value

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

    def _evict_oldest(self) -> None:
        """Evict oldest entry when cache is full"""
        if not self._cache:
            return

        oldest_key = min(
            self._cache.keys(),
            key=lambda k: self._cache[k].expires_at
        )
        del self._cache[oldest_key]

    @property
    def size(self) -> int:
        """Get current cache size"""
        return len(self._cache)

    def stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._lock:
            expired_count = sum(1 for e in self._cache.values() if e.is_expired)
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "expired_count": expired_count,
                "default_ttl": self._default_ttl,
            }


# ==================== Global Cache Instance ====================

_global_cache: Optional[TTLCache] = None
_cache_lock = threading.Lock()


def get_cache(
    default_ttl: float = 300.0,
    max_size: int = 10000
) -> TTLCache:
    """
    Get global cache instance (singleton)

    Args:
        default_ttl: Default TTL in seconds (only used on first call)
        max_size: Maximum cache size (only used on first call)

    Returns:
        Global TTLCache instance
    """
    global _global_cache
    if _global_cache is None:
        with _cache_lock:
            if _global_cache is None:
                _global_cache = TTLCache(
                    default_ttl=default_ttl,
                    max_size=max_size
                )
                logger.info(f"Global cache initialized: ttl={default_ttl}s, max_size={max_size}")
    return _global_cache


def cached(
    ttl: float = 300.0,
    key_prefix: str = ""
) -> Callable:
    """
    Caching decorator

    Args:
        ttl: Cache TTL in seconds
        key_prefix: Prefix for cache keys

    Returns:
        Decorator function

    Example:
        @cached(ttl=600, key_prefix="user")
        def get_user(user_id):
            return fetch_user_from_db(user_id)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            key_parts = [key_prefix, func.__name__]
            if args:
                key_parts.append(str(args))
            if kwargs:
                key_parts.append(str(sorted(kwargs.items())))
            cache_key = ":".join(filter(None, key_parts))

            # Try to get from cache
            cache = get_cache()
            cached_value = cache.get(cache_key)

            if cached_value is not None:
                logger.debug(f"Cache hit: {cache_key}")
                return cached_value

            # Cache miss, execute function
            result = func(*args, **kwargs)

            # Store in cache
            cache.set(cache_key, result, ttl)
            logger.debug(f"Cache set: {cache_key}")

            return result
        return wrapper
    return decorator


# ==================== Specialized Caches ====================

class PeerCache(TTLCache[Dict[str, Any]]):
    """
    Specialized cache for Telegram peer information

    Caches peer data to reduce API calls.
    """

    def __init__(self) -> None:
        super().__init__(
            default_ttl=3600.0,  # 1 hour
            max_size=1000,
            cleanup_interval=300.0  # 5 minutes
        )

    def get_peer(self, peer_id: str) -> Optional[Dict[str, Any]]:
        """Get cached peer info"""
        return self.get(f"peer:{peer_id}")

    def set_peer(self, peer_id: str, peer_info: Dict[str, Any]) -> None:
        """Cache peer info"""
        self.set(f"peer:{peer_id}", peer_info)

    def invalidate_peer(self, peer_id: str) -> bool:
        """Invalidate cached peer info"""
        return self.delete(f"peer:{peer_id}")


class MessageCache(TTLCache[Any]):
    """
    Specialized cache for message deduplication

    Short TTL cache to prevent duplicate message processing.
    """

    def __init__(self) -> None:
        super().__init__(
            default_ttl=60.0,  # 1 minute
            max_size=5000,
            cleanup_interval=30.0
        )

    def is_duplicate(self, message_id: str) -> bool:
        """Check if message was recently processed"""
        return self.get(f"msg:{message_id}") is not None

    def mark_processed(self, message_id: str) -> None:
        """Mark message as processed"""
        self.set(f"msg:{message_id}", True)


# Import from new modules
from .interface import CacheInterface, CacheEventListener, InvalidationStrategy
from .unified import UnifiedCache, CacheStats, get_unified_cache
from .decorators import cached as enhanced_cached, cache_invalidate, cache_aside
from .managers import (
    BaseCacheManager,
    NoteCacheManager,
    ConfigCacheManager,
    PeerCacheManager,
    get_note_cache_manager,
    get_config_cache_manager,
    get_peer_cache_manager,
)
from .monitoring import CacheMonitor, CacheMetrics, get_cache_monitor

# Export all public classes and functions
__all__ = [
    # Legacy exports (backward compatibility)
    "CacheEntry",
    "TTLCache",
    "get_cache",
    "cached",
    "PeerCache",
    "MessageCache",
    # New unified interface
    "CacheInterface",
    "CacheEventListener",
    "InvalidationStrategy",
    # Unified cache
    "UnifiedCache",
    "CacheStats",
    "get_unified_cache",
    # Enhanced decorators
    "enhanced_cached",
    "cache_invalidate",
    "cache_aside",
    # Cache managers
    "BaseCacheManager",
    "NoteCacheManager",
    "ConfigCacheManager",
    "PeerCacheManager",
    "get_note_cache_manager",
    "get_config_cache_manager",
    "get_peer_cache_manager",
    # Monitoring
    "CacheMonitor",
    "CacheMetrics",
    "get_cache_monitor",
]
