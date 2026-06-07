"""Global cache manager factories."""

from typing import Optional

from .config_cache_manager import ConfigCacheManager
from .note_cache_manager import NoteCacheManager
from .peer_cache_manager import PeerCacheManager

_note_cache_manager: Optional[NoteCacheManager] = None
_config_cache_manager: Optional[ConfigCacheManager] = None
_peer_cache_manager: Optional[PeerCacheManager] = None


def get_note_cache_manager() -> NoteCacheManager:
    """Get global note cache manager."""
    global _note_cache_manager
    if _note_cache_manager is None:
        _note_cache_manager = NoteCacheManager()
    return _note_cache_manager


def get_config_cache_manager() -> ConfigCacheManager:
    """Get global config cache manager."""
    global _config_cache_manager
    if _config_cache_manager is None:
        _config_cache_manager = ConfigCacheManager()
    return _config_cache_manager


def get_peer_cache_manager() -> PeerCacheManager:
    """Get global peer cache manager."""
    global _peer_cache_manager
    if _peer_cache_manager is None:
        _peer_cache_manager = PeerCacheManager()
    return _peer_cache_manager
