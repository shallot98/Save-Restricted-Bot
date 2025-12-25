"""
Cache Interface
===============

Abstract base class defining the unified cache interface.
All cache implementations must implement this interface.
"""

from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Optional, Callable, Any, Dict, List
from enum import Enum

T = TypeVar('T')


class InvalidationStrategy(Enum):
    """Cache invalidation strategies"""
    TIME_BASED = "time_based"      # Invalidate based on TTL expiration
    EVENT_BASED = "event_based"    # Invalidate based on events (write operations)
    MANUAL = "manual"              # Manual invalidation only


class CacheInterface(ABC, Generic[T]):
    """
    Unified cache interface

    Defines the contract for all cache implementations.
    Supports 5 core methods: get, set, delete, clear, get_or_set
    """

    @abstractmethod
    def get(self, key: str) -> Optional[T]:
        """
        Get value from cache

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        pass

    @abstractmethod
    def set(self, key: str, value: T, ttl: Optional[float] = None) -> None:
        """
        Set value in cache

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (uses default if not specified)
        """
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        """
        Delete value from cache

        Args:
            key: Cache key

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all cached values"""
        pass

    @abstractmethod
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
        pass

    # Extended interface methods (optional implementation)

    def exists(self, key: str) -> bool:
        """
        Check if key exists in cache

        Args:
            key: Cache key

        Returns:
            True if key exists and not expired
        """
        return self.get(key) is not None

    def delete_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching pattern

        Args:
            pattern: Key pattern (supports * wildcard)

        Returns:
            Number of keys deleted
        """
        raise NotImplementedError("Pattern deletion not supported")

    def get_many(self, keys: List[str]) -> Dict[str, Optional[T]]:
        """
        Get multiple values from cache

        Args:
            keys: List of cache keys

        Returns:
            Dictionary mapping keys to values (None for missing)
        """
        return {key: self.get(key) for key in keys}

    def set_many(self, items: Dict[str, T], ttl: Optional[float] = None) -> None:
        """
        Set multiple values in cache

        Args:
            items: Dictionary of key-value pairs
            ttl: Time-to-live in seconds
        """
        for key, value in items.items():
            self.set(key, value, ttl)

    @property
    def size(self) -> int:
        """Get current cache size"""
        raise NotImplementedError("Size property not supported")

    def stats(self) -> Dict[str, Any]:
        """
        Get cache statistics

        Returns:
            Dictionary with cache statistics
        """
        raise NotImplementedError("Stats not supported")


class CacheEventListener(ABC):
    """
    Cache event listener interface

    Implement this to receive cache events for event-based invalidation.
    """

    @abstractmethod
    def on_set(self, key: str, value: Any) -> None:
        """Called when a value is set in cache"""
        pass

    @abstractmethod
    def on_delete(self, key: str) -> None:
        """Called when a value is deleted from cache"""
        pass

    @abstractmethod
    def on_clear(self) -> None:
        """Called when cache is cleared"""
        pass


__all__ = [
    "CacheInterface",
    "CacheEventListener",
    "InvalidationStrategy",
]
