"""
Compatibility Layer
===================

Provides backward compatibility with legacy code.
Allows gradual migration to the new architecture.

Usage:
    # Old code continues to work
    from config import load_config, save_watch_config

    # New code can use the new architecture
    from src.core.config import settings
"""

from src.compat.config_compat import (
    # Config functions
    load_config,
    getenv,
    load_watch_config,
    save_watch_config,
    load_webdav_config,
    save_webdav_config,
    load_viewer_config,
    save_viewer_config,
    # Monitored sources
    build_monitored_sources,
    reload_monitored_sources,
    get_monitored_sources,
    # Path constants
    DATA_DIR,
    CONFIG_DIR,
    MEDIA_DIR,
    CONFIG_FILE,
    WATCH_FILE,
    WEBDAV_CONFIG_FILE,
    VIEWER_CONFIG_FILE,
)

from src.compat.constants_compat import (
    # Cache constants
    MAX_MEDIA_GROUP_CACHE,
    MESSAGE_CACHE_CLEANUP_THRESHOLD,
    MEDIA_GROUP_CLEANUP_BATCH_SIZE,
    MAX_CACHED_PEERS,
    MAX_FAILED_PEERS,
    # Time constants
    MESSAGE_CACHE_TTL,
    WORKER_STATS_INTERVAL,
    RATE_LIMIT_DELAY,
    # Retry constants
    MAX_RETRIES,
    MAX_FLOOD_RETRIES,
    OPERATION_TIMEOUT,
    get_backoff_time,
    # Media constants
    MAX_MEDIA_PER_GROUP,
    DB_DEDUP_WINDOW,
    # Messages
    USAGE,
)

__all__ = [
    # Config
    "load_config",
    "getenv",
    "load_watch_config",
    "save_watch_config",
    "load_webdav_config",
    "save_webdav_config",
    "load_viewer_config",
    "save_viewer_config",
    "build_monitored_sources",
    "reload_monitored_sources",
    "get_monitored_sources",
    "DATA_DIR",
    "CONFIG_DIR",
    "MEDIA_DIR",
    "CONFIG_FILE",
    "WATCH_FILE",
    "WEBDAV_CONFIG_FILE",
    "VIEWER_CONFIG_FILE",
    # Constants
    "MAX_MEDIA_GROUP_CACHE",
    "MESSAGE_CACHE_CLEANUP_THRESHOLD",
    "MEDIA_GROUP_CLEANUP_BATCH_SIZE",
    "MAX_CACHED_PEERS",
    "MAX_FAILED_PEERS",
    "MESSAGE_CACHE_TTL",
    "WORKER_STATS_INTERVAL",
    "RATE_LIMIT_DELAY",
    "MAX_RETRIES",
    "MAX_FLOOD_RETRIES",
    "OPERATION_TIMEOUT",
    "get_backoff_time",
    "MAX_MEDIA_PER_GROUP",
    "DB_DEDUP_WINDOW",
    "USAGE",
]
