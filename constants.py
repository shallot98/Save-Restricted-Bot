"""
Application-wide constants
Centralized configuration for magic numbers and constants
"""

# Cache sizes
MAX_MEDIA_GROUP_CACHE = 300
MESSAGE_CACHE_CLEANUP_THRESHOLD = 1000
MEDIA_GROUP_CLEANUP_BATCH_SIZE = 50

# Time constants (seconds)
MESSAGE_CACHE_TTL = 1
WORKER_STATS_INTERVAL = 60
RATE_LIMIT_DELAY = 0.5

# Retry configuration
MAX_RETRIES = 3
MAX_FLOOD_RETRIES = 3
OPERATION_TIMEOUT = 30.0

# Backoff configuration
def get_backoff_time(retry_count: int) -> int:
    """Calculate exponential backoff time: 1s, 2s, 4s"""
    return 2 ** (retry_count - 1)

# Media limits
MAX_MEDIA_PER_GROUP = 9

# Database deduplication window (seconds)
DB_DEDUP_WINDOW = 5
