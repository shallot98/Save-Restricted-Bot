"""
Cache Managers
==============

Specialized cache managers for different business domains.
Each manager encapsulates domain-specific caching logic.
"""

import logging
from typing import Optional, Dict, Any, List, Callable

from .unified import UnifiedCache, get_unified_cache
from .interface import InvalidationStrategy

logger = logging.getLogger(__name__)


class BaseCacheManager:
    """
    Base class for specialized cache managers

    Provides common functionality for domain-specific cache managers.
    """

    def __init__(
        self,
        cache: Optional[UnifiedCache] = None,
        key_prefix: str = "",
        default_ttl: float = 300.0
    ):
        """
        Initialize cache manager

        Args:
            cache: Cache instance (uses global if None)
            key_prefix: Prefix for all keys managed by this manager
            default_ttl: Default TTL for cached values
        """
        self._cache = cache or get_unified_cache()
        self._key_prefix = key_prefix
        self._default_ttl = default_ttl

    def _make_key(self, *parts: str) -> str:
        """Build cache key with prefix"""
        all_parts = [self._key_prefix] + list(parts)
        return ":".join(filter(None, all_parts))

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        return self._cache.get(self._make_key(key))

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """Set value in cache"""
        self._cache.set(self._make_key(key), value, ttl or self._default_ttl)

    def delete(self, key: str) -> bool:
        """Delete value from cache"""
        return self._cache.delete(self._make_key(key))

    def invalidate_all(self) -> int:
        """Invalidate all keys managed by this manager"""
        return self._cache.delete_prefix(self._key_prefix)

    def stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return self._cache.stats()


class NoteCacheManager(BaseCacheManager):
    """
    Cache manager for notes

    Handles caching of:
    - Note lists (paginated)
    - Note counts
    - Source lists
    - Individual notes
    """

    def __init__(self, cache: Optional[UnifiedCache] = None):
        super().__init__(
            cache=cache,
            key_prefix="notes",
            default_ttl=300.0  # 5 minutes
        )

    def cache_note_list(
        self,
        user_id: int,
        source: Optional[str],
        search: Optional[str],
        page: int,
        notes: List[Dict[str, Any]],
        ttl: Optional[float] = None
    ) -> None:
        """
        Cache note list query result

        Args:
            user_id: User ID
            source: Source filter (optional)
            search: Search query (optional)
            page: Page number
            notes: List of notes to cache
            ttl: Cache TTL
        """
        key = self._build_list_key(user_id, source, search, page)
        self.set(key, notes, ttl)
        logger.debug(f"Cached note list: user={user_id}, page={page}")

    def get_note_list(
        self,
        user_id: int,
        source: Optional[str],
        search: Optional[str],
        page: int
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get cached note list

        Args:
            user_id: User ID
            source: Source filter
            search: Search query
            page: Page number

        Returns:
            Cached notes or None
        """
        key = self._build_list_key(user_id, source, search, page)
        return self.get(key)

    def _build_list_key(
        self,
        user_id: int,
        source: Optional[str],
        search: Optional[str],
        page: int
    ) -> str:
        """Build cache key for note list"""
        source_part = source or "all"
        search_part = search[:20] if search else "none"
        return f"list:{user_id}:{source_part}:{search_part}:{page}"

    def cache_note_count(
        self,
        user_id: int,
        source: Optional[str],
        search: Optional[str],
        count: int,
        ttl: Optional[float] = None
    ) -> None:
        """Cache note count"""
        key = f"count:{user_id}:{source or 'all'}:{search or 'none'}"
        self.set(key, count, ttl)

    def get_note_count(
        self,
        user_id: int,
        source: Optional[str],
        search: Optional[str]
    ) -> Optional[int]:
        """Get cached note count"""
        key = f"count:{user_id}:{source or 'all'}:{search or 'none'}"
        return self.get(key)

    def cache_sources(
        self,
        user_id: int,
        sources: List[str],
        ttl: Optional[float] = None
    ) -> None:
        """Cache source list for user"""
        key = f"sources:{user_id}"
        self.set(key, sources, ttl or 600.0)  # 10 minutes for sources

    def get_sources(self, user_id: int) -> Optional[List[str]]:
        """Get cached source list"""
        key = f"sources:{user_id}"
        return self.get(key)

    def invalidate_user_notes(self, user_id: int) -> int:
        """Invalidate all cached notes for a user"""
        pattern = f"{self._key_prefix}:*:{user_id}:*"
        deleted = self._cache.delete_pattern(pattern)
        # Also invalidate list and count caches
        deleted += self._cache.delete_pattern(f"{self._key_prefix}:list:{user_id}:*")
        deleted += self._cache.delete_pattern(f"{self._key_prefix}:count:{user_id}:*")
        deleted += self._cache.delete(self._make_key(f"sources:{user_id}"))
        logger.info(f"Invalidated {deleted} cache entries for user {user_id}")
        return deleted

    def invalidate_note(self, note_id: int, user_id: int) -> int:
        """Invalidate cache for a specific note"""
        # Invalidate individual note
        deleted = self._cache.delete(self._make_key(f"note:{note_id}"))
        # Also invalidate list caches for the user
        deleted += self._cache.delete_pattern(f"{self._key_prefix}:list:{user_id}:*")
        deleted += self._cache.delete_pattern(f"{self._key_prefix}:count:{user_id}:*")
        return deleted


class ConfigCacheManager(BaseCacheManager):
    """
    Cache manager for configuration

    Handles caching of:
    - Watch configurations
    - Monitored sources
    - User settings
    """

    def __init__(self, cache: Optional[UnifiedCache] = None):
        super().__init__(
            cache=cache,
            key_prefix="config",
            default_ttl=600.0  # 10 minutes
        )

    def cache_watch_config(
        self,
        user_id: int,
        config: Dict[str, Any],
        ttl: Optional[float] = None
    ) -> None:
        """Cache watch configuration"""
        key = f"watch:{user_id}"
        self.set(key, config, ttl)

    def get_watch_config(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get cached watch configuration"""
        key = f"watch:{user_id}"
        return self.get(key)

    def cache_monitored_sources(
        self,
        sources: List[Dict[str, Any]],
        ttl: Optional[float] = None
    ) -> None:
        """Cache monitored sources list"""
        key = "monitored_sources"
        self.set(key, sources, ttl or 300.0)

    def get_monitored_sources(self) -> Optional[List[Dict[str, Any]]]:
        """Get cached monitored sources"""
        key = "monitored_sources"
        return self.get(key)

    def invalidate_watch_config(self, user_id: Optional[int] = None) -> int:
        """Invalidate watch configuration cache"""
        if user_id:
            deleted = self._cache.delete(self._make_key(f"watch:{user_id}"))
        else:
            deleted = self._cache.delete_pattern(f"{self._key_prefix}:watch:*")
        # Also invalidate monitored sources
        deleted += self._cache.delete(self._make_key("monitored_sources"))
        return deleted

    def cache_user_settings(
        self,
        user_id: int,
        settings: Dict[str, Any],
        ttl: Optional[float] = None
    ) -> None:
        """Cache user settings"""
        key = f"settings:{user_id}"
        self.set(key, settings, ttl)

    def get_user_settings(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get cached user settings"""
        key = f"settings:{user_id}"
        return self.get(key)


class PeerCacheManager(BaseCacheManager):
    """
    Cache manager for Telegram peers

    Handles caching of:
    - Peer information (chats, channels, users)
    - Dialog lists
    - Entity resolution
    """

    def __init__(self, cache: Optional[UnifiedCache] = None):
        super().__init__(
            cache=cache,
            key_prefix="peer",
            default_ttl=3600.0  # 1 hour
        )

    def cache_peer(
        self,
        peer_id: int,
        peer_type: str,
        peer_info: Dict[str, Any],
        ttl: Optional[float] = None
    ) -> None:
        """
        Cache peer information

        Args:
            peer_id: Peer ID
            peer_type: Type of peer (channel, chat, user)
            peer_info: Peer information dict
            ttl: Cache TTL
        """
        key = f"{peer_type}:{peer_id}"
        self.set(key, peer_info, ttl)

    def get_peer(self, peer_id: int, peer_type: str) -> Optional[Dict[str, Any]]:
        """Get cached peer information"""
        key = f"{peer_type}:{peer_id}"
        return self.get(key)

    def cache_peer_by_username(
        self,
        username: str,
        peer_info: Dict[str, Any],
        ttl: Optional[float] = None
    ) -> None:
        """Cache peer by username"""
        key = f"username:{username.lower()}"
        self.set(key, peer_info, ttl)

    def get_peer_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get cached peer by username"""
        key = f"username:{username.lower()}"
        return self.get(key)

    def invalidate_peer(self, peer_id: int, peer_type: str) -> bool:
        """Invalidate cached peer"""
        key = f"{peer_type}:{peer_id}"
        return self.delete(key)

    def mark_peer_cached(self, peer_id: int) -> None:
        """Mark peer as cached (for tracking)"""
        key = f"cached:{peer_id}"
        self.set(key, True, ttl=86400.0)  # 24 hours

    def is_peer_cached(self, peer_id: int) -> bool:
        """Check if peer is marked as cached"""
        key = f"cached:{peer_id}"
        return self.get(key) is True


# Global manager instances
_note_cache_manager: Optional[NoteCacheManager] = None
_config_cache_manager: Optional[ConfigCacheManager] = None
_peer_cache_manager: Optional[PeerCacheManager] = None


def get_note_cache_manager() -> NoteCacheManager:
    """Get global note cache manager"""
    global _note_cache_manager
    if _note_cache_manager is None:
        _note_cache_manager = NoteCacheManager()
    return _note_cache_manager


def get_config_cache_manager() -> ConfigCacheManager:
    """Get global config cache manager"""
    global _config_cache_manager
    if _config_cache_manager is None:
        _config_cache_manager = ConfigCacheManager()
    return _config_cache_manager


def get_peer_cache_manager() -> PeerCacheManager:
    """Get global peer cache manager"""
    global _peer_cache_manager
    if _peer_cache_manager is None:
        _peer_cache_manager = PeerCacheManager()
    return _peer_cache_manager


__all__ = [
    "BaseCacheManager",
    "NoteCacheManager",
    "ConfigCacheManager",
    "PeerCacheManager",
    "get_note_cache_manager",
    "get_config_cache_manager",
    "get_peer_cache_manager",
]
