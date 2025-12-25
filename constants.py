"""
Application-wide constants
Centralized configuration for magic numbers and constants

NOTE: This file now delegates to the new layered architecture.
      For new code, prefer using:
          from src.core.constants import AppConstants, Messages
"""

# Import from new architecture via compatibility layer
from src.compat.constants_compat import (
    # Cache sizes
    MAX_MEDIA_GROUP_CACHE,
    MESSAGE_CACHE_CLEANUP_THRESHOLD,
    MEDIA_GROUP_CLEANUP_BATCH_SIZE,
    # Peer cache limits
    MAX_CACHED_PEERS,
    MAX_FAILED_PEERS,
    # Time constants (seconds)
    MESSAGE_CACHE_TTL,
    WORKER_STATS_INTERVAL,
    RATE_LIMIT_DELAY,
    # Retry configuration
    MAX_RETRIES,
    MAX_FLOOD_RETRIES,
    OPERATION_TIMEOUT,
    # Backoff configuration
    get_backoff_time,
    # Media limits
    MAX_MEDIA_PER_GROUP,
    # Database deduplication window (seconds)
    DB_DEDUP_WINDOW,
    # Usage help text
    USAGE,
)

__all__ = [
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
