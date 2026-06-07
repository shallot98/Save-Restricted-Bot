"""Cache infrastructure public exports."""

from .decorators import cache_aside, cache_invalidate
from .decorators import cached as enhanced_cached
from .interface import CacheEventListener, CacheInterface, InvalidationStrategy
from .legacy import CacheEntry, MessageCache, PeerCache, TTLCache, cached, get_cache
from .managers import (
    BaseCacheManager,
    ConfigCacheManager,
    NoteCacheManager,
    PeerCacheManager,
    get_config_cache_manager,
    get_note_cache_manager,
    get_peer_cache_manager,
)
from .monitoring import CacheMetrics, CacheMonitor, get_cache_monitor
from .unified import CacheStats, UnifiedCache, get_unified_cache

__all__ = [
    "CacheEntry",
    "TTLCache",
    "get_cache",
    "cached",
    "PeerCache",
    "MessageCache",
    "CacheInterface",
    "CacheEventListener",
    "InvalidationStrategy",
    "UnifiedCache",
    "CacheStats",
    "get_unified_cache",
    "enhanced_cached",
    "cache_invalidate",
    "cache_aside",
    "BaseCacheManager",
    "NoteCacheManager",
    "ConfigCacheManager",
    "PeerCacheManager",
    "get_note_cache_manager",
    "get_config_cache_manager",
    "get_peer_cache_manager",
    "CacheMonitor",
    "CacheMetrics",
    "get_cache_monitor",
]
