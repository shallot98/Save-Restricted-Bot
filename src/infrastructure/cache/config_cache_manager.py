"""Cache manager for configuration values."""

from typing import Any, Dict, List, Optional

from .cache_manager_base import BaseCacheManager
from .unified import UnifiedCache


class ConfigCacheManager(BaseCacheManager):
    """Cache manager for watch configs, monitored sources, and user settings."""

    def __init__(self, cache: Optional[UnifiedCache] = None):
        super().__init__(
            cache=cache,
            key_prefix="config",
            default_ttl=600.0,
        )

    def cache_watch_config(
        self,
        user_id: int,
        config: Dict[str, Any],
        ttl: Optional[float] = None,
    ) -> None:
        key = f"watch:{user_id}"
        self.set(key, config, ttl)

    def get_watch_config(self, user_id: int) -> Optional[Dict[str, Any]]:
        key = f"watch:{user_id}"
        return self.get(key)

    def cache_monitored_sources(
        self,
        sources: List[Dict[str, Any]],
        ttl: Optional[float] = None,
    ) -> None:
        key = "monitored_sources"
        self.set(key, sources, ttl or 300.0)

    def get_monitored_sources(self) -> Optional[List[Dict[str, Any]]]:
        key = "monitored_sources"
        return self.get(key)

    def invalidate_watch_config(self, user_id: Optional[int] = None) -> int:
        if user_id:
            deleted = self._cache.delete(self._make_key(f"watch:{user_id}"))
        else:
            deleted = self._cache.delete_pattern(f"{self._key_prefix}:watch:*")
        deleted += self._cache.delete(self._make_key("monitored_sources"))
        return deleted

    def cache_user_settings(
        self,
        user_id: int,
        settings: Dict[str, Any],
        ttl: Optional[float] = None,
    ) -> None:
        key = f"settings:{user_id}"
        self.set(key, settings, ttl)

    def get_user_settings(self, user_id: int) -> Optional[Dict[str, Any]]:
        key = f"settings:{user_id}"
        return self.get(key)
