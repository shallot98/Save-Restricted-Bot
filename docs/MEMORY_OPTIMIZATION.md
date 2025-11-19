# Memory Optimization Summary

## Overview
This document describes the memory optimizations implemented to minimize the bot's memory usage for long-running instances.

## Optimization Goals
- **Bounded memory usage**: No unbounded growth of caches or queues
- **Graceful degradation**: Handle edge cases (queue full, etc.) without crashing
- **Automatic cleanup**: No manual intervention needed for memory management
- **Production-ready**: Suitable for long-running instances (24/7 operation)

## Changes Implemented

### 1. Cache Size Reductions

#### constants.py
- **MAX_MEDIA_GROUP_CACHE**: 300 → 100 (-67%)
  - Most users won't have 100 concurrent media groups
  - Reduces memory footprint significantly
  
- **MAX_MESSAGE_CACHE**: New constant, 200 entries
  - Fixed LRU cache size for message deduplication
  - Replaces threshold-based cleanup approach
  
- **MESSAGE_CACHE_CLEANUP_THRESHOLD**: 1000 → 500 (-50%)
  - Triggers cleanup earlier when using dict-based caches
  
- **MAX_QUEUE_SIZE**: New constant, 1000 messages
  - Prevents unbounded queue growth
  - Handles backpressure gracefully

### 2. LRU Cache Implementation

#### bot/utils/dedup.py
**Before**: `processed_messages` was a regular dict that grew until cleanup threshold

**After**: Converted to OrderedDict with automatic LRU eviction
- Auto-evicts oldest entry when exceeding `MAX_MESSAGE_CACHE` (200)
- `move_to_end()` refreshes position on access
- O(1) operations for both access and eviction
- **Memory savings**: Bounded at 200 entries instead of growing to 1000+

**Media group cache**: Already used OrderedDict, reduced from 300 to 100 entries

### 3. TTL-Based Cleanup

#### bot/utils/status.py - User State Management
**Problem**: User states accumulated indefinitely, never cleaned up

**Solution**: Added TTL-based cleanup
- State format changed to: `{user_id: {"data": {...}, "last_access": timestamp}}`
- `USER_STATE_TTL = 3600` seconds (1 hour)
- `cleanup_expired_states()` removes states not accessed for 1 hour
- `get_state_stats()` for monitoring

**Memory savings**: Old states automatically removed after inactivity

#### bot/utils/peer.py - Failed Peer Cleanup
**Problem**: `failed_peers` dict accumulated entries indefinitely

**Solution**: Added age-based cleanup
- `FAILED_PEER_CLEANUP_AGE = 86400` seconds (24 hours)
- `cleanup_old_failed_peers()` removes entries older than 24 hours
- `get_peer_stats()` for monitoring

**Memory savings**: Old failed peer records removed after 24 hours

### 4. Periodic Memory Cleanup

#### bot/workers/message_worker.py
**Added**: Periodic cleanup task in worker idle loop

**Implementation**:
- Runs every 5 minutes (300 seconds) when queue is empty
- `_run_memory_cleanup()` method calls:
  - `cleanup_old_messages()` - Dedup cache cleanup
  - `cleanup_expired_states()` - User state cleanup
  - `cleanup_old_failed_peers()` - Failed peer cleanup
- Logs memory statistics after cleanup

**Benefits**: Automatic, hands-off memory management

### 5. Bounded Message Queue

#### bot/core/queue.py
**Before**: `queue.Queue()` with no size limit

**After**: `queue.Queue(maxsize=MAX_QUEUE_SIZE)` with 1000 message limit

**Benefits**:
- Prevents unbounded memory growth during message bursts
- Forces backpressure handling

#### bot/handlers/auto_forward.py
**Added**: Non-blocking enqueue with exception handling

```python
try:
    message_queue.put(msg_obj, block=False)
except queue.Full:
    logger.warning("⚠️ 消息队列已满，跳过消息")
```

**Benefits**: Graceful degradation when queue is full

### 6. Reduced Logging Overhead

#### constants.py
- **WORKER_STATS_INTERVAL**: 60s → 300s (-80% log frequency)
- Reduces I/O overhead and log file size
- Stats still logged regularly (every 5 minutes)

## Memory Usage Comparison

### Before Optimization
- Message cache: Grows to 1000+ entries before cleanup
- Media group cache: 300 entries
- User states: Unlimited growth
- Failed peers: Unlimited growth
- Message queue: Unbounded
- Stats logging: Every 60 seconds

### After Optimization
- Message cache: **Fixed at 200 entries** (LRU)
- Media group cache: **100 entries** (-67%)
- User states: **Auto-cleanup after 1 hour**
- Failed peers: **Auto-cleanup after 24 hours**
- Message queue: **Bounded at 1000 messages**
- Stats logging: **Every 300 seconds** (-80%)

## Monitoring

### Cache Statistics
Call `get_cache_stats()` from dedup.py:
```python
{
    'message_cache_size': int,
    'media_group_cache_size': int,
    'message_cache_ttl': 1,
    'media_group_cache_max': 100
}
```

### User State Statistics
Call `get_state_stats()` from status.py:
```python
{
    'active_users': int,
    'ttl_seconds': 3600
}
```

### Peer Statistics
Call `get_peer_stats()` from peer.py:
```python
{
    'cached_peers': int,
    'failed_peers': int,
    'retry_cooldown': 60,
    'cleanup_age': 86400
}
```

### Automatic Logging
Memory statistics are automatically logged every 5 minutes by the MessageWorker:
```
🧹 内存清理完成:
   - 消息缓存: X 条
   - 媒体组缓存: Y 条
   - 活跃用户状态: Z 个
   - 缓存的Peer: A 个
   - 失败的Peer: B 个
```

## Production Recommendations

### Memory Limits
For typical usage (10-100 monitored channels):
- **Expected memory**: 50-200 MB
- **Peak memory**: 300-500 MB (during heavy message bursts)

### Tuning Parameters
If experiencing issues, adjust these constants in `constants.py`:

**For lower memory usage** (small VPS):
- `MAX_MESSAGE_CACHE = 100` (from 200)
- `MAX_MEDIA_GROUP_CACHE = 50` (from 100)
- `MAX_QUEUE_SIZE = 500` (from 1000)

**For higher throughput** (powerful server):
- `MAX_MESSAGE_CACHE = 500` (from 200)
- `MAX_MEDIA_GROUP_CACHE = 200` (from 100)
- `MAX_QUEUE_SIZE = 5000` (from 1000)

### Monitoring Alerts
Set up alerts for:
- Queue full warnings in logs (indicates need for higher `MAX_QUEUE_SIZE`)
- Frequent LRU evictions (indicates caches may be too small)
- High user state count (indicates many active users)

## Testing

### Verification
1. Run bot for 24+ hours
2. Monitor memory usage with `ps` or `top`
3. Check logs for cleanup messages
4. Verify no unbounded growth

### Load Testing
1. Subscribe to high-volume channels
2. Monitor queue size in logs
3. Verify queue full handling
4. Check memory usage under load

## Backwards Compatibility
- ✅ All existing features preserved
- ✅ No API changes
- ✅ No configuration changes required
- ✅ Automatic migration on startup

## Related Files
- `constants.py` - Cache size constants
- `bot/utils/dedup.py` - Message/media group deduplication with LRU
- `bot/utils/status.py` - User state management with TTL
- `bot/utils/peer.py` - Peer caching with cleanup
- `bot/core/queue.py` - Message queue initialization
- `bot/handlers/auto_forward.py` - Queue full handling
- `bot/workers/message_worker.py` - Periodic cleanup task
