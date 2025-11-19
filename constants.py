"""
Application-wide constants
Centralized configuration for magic numbers and constants
Optimized for minimal memory usage
"""

# Cache sizes (optimized for minimal memory usage)
MAX_MEDIA_GROUP_CACHE = 100  # 减少媒体组缓存（从300→100）
MAX_MESSAGE_CACHE = 200  # 消息缓存使用LRU，固定大小
MESSAGE_CACHE_CLEANUP_THRESHOLD = 500  # 降低清理阈值（从1000→500）
MEDIA_GROUP_CLEANUP_BATCH_SIZE = 50
MAX_QUEUE_SIZE = 1000  # 消息队列最大大小，防止内存溢出

# Time constants (seconds)
MESSAGE_CACHE_TTL = 1
USER_STATE_TTL = 3600  # 用户状态1小时后过期
FAILED_PEER_CLEANUP_AGE = 86400  # 失败的peer记录24小时后清理
WORKER_STATS_INTERVAL = 300  # 增加统计日志间隔（从60s→300s），减少日志开销
RATE_LIMIT_DELAY = 1.5  # 增加到1.5秒，避免批量发送时触发FloodWait

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

# Usage help text
USAGE = """**📌 公开频道/群组**

__直接发送帖子链接即可__

**🔒 私有频道/群组**

__首先发送频道邀请链接（如果 String Session 账号已加入则不需要）
然后发送帖子链接__

**🤖 机器人聊天**

__发送带有 '/b/'、机器人用户名和消息 ID 的链接，你可能需要使用一些非官方客户端来获取 ID，如下所示__

```
https://t.me/b/botusername/4321
```

**📦 批量下载**

__按照上述方式发送公开/私有帖子链接，使用 "from - to" 格式发送多条消息，如下所示__

```
https://t.me/xxxx/1001-1010

https://t.me/c/xxxx/101 - 120
```

__注意：中间的空格无关紧要__
"""
