"""
Application Constants
=====================

Centralized configuration for magic numbers and constants.
Follows SOLID principles - constants are grouped by domain.
"""

from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True)
class CacheConstants:
    """Cache-related constants"""

    MAX_MEDIA_GROUP_CACHE: ClassVar[int] = 50
    MESSAGE_CACHE_CLEANUP_THRESHOLD: ClassVar[int] = 200
    MEDIA_GROUP_CLEANUP_BATCH_SIZE: ClassVar[int] = 25
    MAX_CACHED_PEERS: ClassVar[int] = 30
    MAX_FAILED_PEERS: ClassVar[int] = 20


@dataclass(frozen=True)
class TimeConstants:
    """Time-related constants (in seconds)"""

    MESSAGE_CACHE_TTL: ClassVar[float] = 0.2
    WORKER_STATS_INTERVAL: ClassVar[int] = 20
    RATE_LIMIT_DELAY: ClassVar[float] = 1.0
    OPERATION_TIMEOUT: ClassVar[float] = 30.0
    DB_DEDUP_WINDOW: ClassVar[int] = 5


@dataclass(frozen=True)
class RetryConstants:
    """Retry-related constants"""

    MAX_RETRIES: ClassVar[int] = 3
    MAX_FLOOD_RETRIES: ClassVar[int] = 3

    @staticmethod
    def get_backoff_time(retry_count: int) -> int:
        """Calculate exponential backoff time: 1s, 2s, 4s"""
        return 2 ** (retry_count - 1)


@dataclass(frozen=True)
class MediaConstants:
    """Media-related constants"""

    MAX_MEDIA_PER_GROUP: ClassVar[int] = 9


class AppConstants:
    """
    Application-wide constants aggregator

    Usage:
        from src.core.constants import AppConstants

        max_cache = AppConstants.Cache.MAX_MEDIA_GROUP_CACHE
        timeout = AppConstants.Time.OPERATION_TIMEOUT
        backoff = AppConstants.Retry.get_backoff_time(2)
    """

    Cache = CacheConstants
    Time = TimeConstants
    Retry = RetryConstants
    Media = MediaConstants
