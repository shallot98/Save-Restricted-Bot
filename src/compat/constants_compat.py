"""
Constants Compatibility Layer
=============================

Provides backward-compatible constants that delegate to the new AppConstants.
"""

from src.core.constants import AppConstants, Messages

# Cache sizes
MAX_MEDIA_GROUP_CACHE = AppConstants.Cache.MAX_MEDIA_GROUP_CACHE
MESSAGE_CACHE_CLEANUP_THRESHOLD = AppConstants.Cache.MESSAGE_CACHE_CLEANUP_THRESHOLD
MEDIA_GROUP_CLEANUP_BATCH_SIZE = AppConstants.Cache.MEDIA_GROUP_CLEANUP_BATCH_SIZE

# Peer cache limits
MAX_CACHED_PEERS = AppConstants.Cache.MAX_CACHED_PEERS
MAX_FAILED_PEERS = AppConstants.Cache.MAX_FAILED_PEERS

# Time constants (seconds)
MESSAGE_CACHE_TTL = AppConstants.Time.MESSAGE_CACHE_TTL
WORKER_STATS_INTERVAL = AppConstants.Time.WORKER_STATS_INTERVAL
RATE_LIMIT_DELAY = AppConstants.Time.RATE_LIMIT_DELAY

# Retry configuration
MAX_RETRIES = AppConstants.Retry.MAX_RETRIES
MAX_FLOOD_RETRIES = AppConstants.Retry.MAX_FLOOD_RETRIES
OPERATION_TIMEOUT = AppConstants.Time.OPERATION_TIMEOUT


def get_backoff_time(retry_count: int) -> int:
    """Calculate exponential backoff time: 1s, 2s, 4s

    Backward compatible function that delegates to AppConstants.
    """
    return AppConstants.Retry.get_backoff_time(retry_count)


# Media limits
MAX_MEDIA_PER_GROUP = AppConstants.Media.MAX_MEDIA_PER_GROUP

# Database deduplication window (seconds)
DB_DEDUP_WINDOW = AppConstants.Time.DB_DEDUP_WINDOW

# Usage help text
USAGE = Messages.USAGE
