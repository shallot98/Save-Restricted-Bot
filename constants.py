"""
Constants Facade - 扁平名 → ``AppConstants`` 嵌套名的再导出，计划 Phase 4 删除

Phase 3 删除 ``src/compat/`` 后，本模块从 ``constants.py`` →
``src.compat.constants_compat`` → ``src.core.constants`` 的两跳收敛为直接引用
权威源。零逻辑，只做名字映射。

**为什么本轮没有连同删除**：生产消费方 10 个文件、约 50 处取值点——

    bot/workers/{media_handling,forwarding,telegram_execution,queue_loop}_mixin.py
    bot/workers/message_worker.py
    bot/handlers/auto_forward_progress.py
    bot/core/{startup,queue}.py
    bot/utils/{peer,dedup}.py

改到权威源不是换 import 行，而是把每处 ``MAX_RETRIES`` 改写成
``AppConstants.Retry.MAX_RETRIES``，且这些文件本轮有并行改动。按 §6.1
「现在不该动」的判据（收益是删 50 行外观，代价是 50 处跨文件改写 + 冲突风险），
留到 Phase 4 与 ``config.py`` / ``database.py`` 一起收口。

新代码请直接用权威源：
    from src.core.constants import AppConstants, Messages
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

# Media limits
MAX_MEDIA_PER_GROUP = AppConstants.Media.MAX_MEDIA_PER_GROUP

# Database deduplication window (seconds)
DB_DEDUP_WINDOW = AppConstants.Time.DB_DEDUP_WINDOW

# Usage help text
USAGE = Messages.USAGE


def get_backoff_time(retry_count: int) -> int:
    """指数退避时长：1s、2s、4s（委托 AppConstants.Retry）。"""
    return AppConstants.Retry.get_backoff_time(retry_count)


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
