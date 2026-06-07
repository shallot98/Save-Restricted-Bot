"""Base class for specialized cache managers."""

from typing import Any, Dict, Optional

from .unified import UnifiedCache, get_unified_cache


class BaseCacheManager:
    """Common functionality for domain-specific cache managers."""

    def __init__(
        self,
        cache: Optional[UnifiedCache] = None,
        key_prefix: str = "",
        default_ttl: float = 300.0,
    ):
        self._cache = cache or get_unified_cache()
        self._key_prefix = key_prefix
        self._default_ttl = default_ttl

    def _make_key(self, *parts: str) -> str:
        all_parts = [self._key_prefix] + list(parts)
        return ":".join(filter(None, all_parts))

    def get(self, key: str) -> Optional[Any]:
        return self._cache.get(self._make_key(key))

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        self._cache.set(self._make_key(key), value, ttl or self._default_ttl)

    def delete(self, key: str) -> bool:
        return self._cache.delete(self._make_key(key))

    def invalidate_all(self) -> int:
        return self._cache.delete_prefix(self._key_prefix)

    def stats(self) -> Dict[str, Any]:
        return self._cache.stats()
