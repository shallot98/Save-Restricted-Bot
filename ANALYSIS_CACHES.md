# Save-Restricted-Bot 缓存实现分析报告

## 执行摘要

本报告审查了 Save-Restricted-Bot 中的所有缓存实现，诊断潜在的内存瓶颈。经过分析，发现了 **3 个主要内存风险**，其中 2 个已在最近优化中得到缓解，但仍有 **3 个严重的未受限缓存** 需要关注。

---

## 1. 消息去重缓存 (`processed_messages`)

### 位置
- 文件：`bot/utils/dedup.py`
- 行数：15
- 类型：`Dict[str, float]`

### 代码实现
```python
# Message deduplication cache
processed_messages: Dict[str, float] = {}
_message_lock = threading.Lock()

# 消息缓存清理阈值（当缓存超过此大小时触发清理）
MESSAGE_CACHE_MAX_SIZE = MESSAGE_CACHE_CLEANUP_THRESHOLD  # 500

def is_message_processed(message_id: int, chat_id: int) -> bool:
    """Check if a message has been recently processed (thread-safe)"""
    key = f"{chat_id}_{message_id}"
    
    with _message_lock:
        if key in processed_messages:
            timestamp = processed_messages[key]
            if time.time() - timestamp < MESSAGE_CACHE_TTL:  # 0.3秒
                return True
            # Expired, remove it
            del processed_messages[key]
        return False

def cleanup_old_messages():
    """Clean up expired message records (thread-safe)"""
    current_time = time.time()
    
    with _message_lock:
        # 清理过期条目
        expired_keys = [key for key, timestamp in processed_messages.items()
                        if current_time - timestamp > MESSAGE_CACHE_TTL]
        for key in expired_keys:
            del processed_messages[key]
        
        if expired_keys:
            logger.debug(f"🧹 消息缓存清理: 移除{len(expired_keys)}个过期条目")
        
        # 如果缓存仍然过大，强制清理最旧的条目
        if len(processed_messages) > MESSAGE_CACHE_MAX_SIZE:
            # 按时间戳排序，删除最旧的50%
            sorted_items = sorted(processed_messages.items(), key=lambda x: x[1])
            remove_count = len(sorted_items) // 2
            for key, _ in sorted_items[:remove_count]:
                del processed_messages[key]
            logger.info(f"🧹 消息缓存超限，强制清理{remove_count}个最旧条目")
```

### 当前状态
- **大小限制**：✅ 有 - `MESSAGE_CACHE_CLEANUP_THRESHOLD = 500`
- **TTL**：✅ 有 - `MESSAGE_CACHE_TTL = 0.3` 秒
- **清理机制**：✅ 有 - 定期清理 + 超限强制清理
- **触发时机**：每 60 秒（`WORKER_STATS_INTERVAL`）

### 内存估算（1000 条消息场景）
- **键大小**：`"{chat_id}_{message_id}"` ≈ 30 字符 ≈ 50 字节
- **值大小**：`float` 时间戳 ≈ 8 字节
- **单条记录**：~58 字节
- **1000 条消息**：~58 KB
- **实际最大值**（500 条限制）：~29 KB

### 评估
✅ **状态：已优化良好**
- 有明确的大小限制
- 有双重清理机制（TTL + 超限强制）
- 内存占用可预测且较小

---

## 2. 媒体组去重缓存 (`processed_media_groups`)

### 位置
- 文件：`bot/utils/dedup.py`
- 行数：20
- 类型：`OrderedDict[str, float]`

### 代码实现
```python
# Media group deduplication cache (LRU with OrderedDict for efficient cleanup)
processed_media_groups: OrderedDict[str, float] = OrderedDict()
_media_group_lock = threading.Lock()

# 媒体组去重的时间窗口（秒）
MEDIA_GROUP_DEDUP_WINDOW = 2.0  # 2秒内的重复媒体组会被过滤

def register_processed_media_group(key: str):
    """Register a media group as processed (thread-safe, LRU cache with timestamp)"""
    current_time = time.time()
    
    with _media_group_lock:
        # Move to end if exists (refresh LRU position)
        if key in processed_media_groups:
            processed_media_groups.move_to_end(key)
        
        # 存储当前时间戳
        processed_media_groups[key] = current_time
        
        # LRU cleanup: remove oldest entries if cache exceeds limit
        if len(processed_media_groups) > MAX_MEDIA_GROUP_CACHE:  # 200
            # Remove oldest entries efficiently with loop protection
            removed_count = 0
            max_iterations = MEDIA_GROUP_CLEANUP_BATCH_SIZE  # 50
            
            for _ in range(max_iterations):
                if len(processed_media_groups) > MAX_MEDIA_GROUP_CACHE:
                    processed_media_groups.popitem(last=False)  # Remove oldest (FIFO)
                    removed_count += 1
                else:
                    break
            
            if removed_count > 0:
                logger.debug(f"🧹 媒体组缓存清理: 移除最旧的 {removed_count} 个条目")

def is_media_group_processed(key: str) -> bool:
    """Check if a media group has been processed within the dedup window"""
    current_time = time.time()
    
    with _media_group_lock:
        if key in processed_media_groups:
            timestamp = processed_media_groups[key]
            # 检查是否在去重时间窗口内
            if current_time - timestamp < MEDIA_GROUP_DEDUP_WINDOW:
                return True
            else:
                # 超过时间窗口，删除旧记录
                del processed_media_groups[key]
                return False
        return False
```

### 当前状态
- **大小限制**：✅ 有 - `MAX_MEDIA_GROUP_CACHE = 200`
- **TTL**：✅ 有 - `MEDIA_GROUP_DEDUP_WINDOW = 2.0` 秒
- **清理机制**：✅ 有 - LRU 机制 + 时间窗口检查
- **数据结构**：`OrderedDict` - 高效 LRU 实现

### 内存估算（200 条媒体组限制）
- **键大小**：`"{user_id}_{watch_key}_{dest_chat_id}_{mode_suffix}_{media_group_id}"` ≈ 100 字节
- **值大小**：`float` 时间戳 ≈ 8 字节
- **单条记录**：~108 字节
- **最大值**（200 条限制）：~21.6 KB

### 评估
✅ **状态：已优化良好**
- 使用 `OrderedDict` 实现高效 LRU
- 有严格的大小限制
- 双重清理机制（LRU + TTL）

---

## 3. Peer 缓存 (`cached_dest_peers`)

### 位置
- 文件：`bot/utils/peer.py`
- 行数：14
- 类型：`OrderedDict[str, float]`

### 代码实现
```python
# Cached destination peers (LRU cache with max size)
cached_dest_peers: OrderedDict[str, float] = OrderedDict()

# Failed peers that need delayed loading retry (LRU cache with max size)
failed_peers: OrderedDict[str, float] = OrderedDict()

# Retry cooldown in seconds (wait before retrying failed peer)
RETRY_COOLDOWN = 60

def mark_dest_cached(dest_id: str):
    """Mark destination peer as cached (LRU mechanism)"""
    # Add/update timestamp and move to end (most recently used)
    cached_dest_peers[dest_id] = time.time()
    cached_dest_peers.move_to_end(dest_id)
    
    # LRU cleanup: remove oldest entries if cache exceeds limit
    if len(cached_dest_peers) > MAX_CACHED_PEERS:  # 100
        oldest_peer = cached_dest_peers.popitem(last=False)
        logger.debug(f"🧹 Peer缓存已满，移除最旧的: {oldest_peer[0]}")
    
    # Remove from failed peers if it was there
    if dest_id in failed_peers:
        del failed_peers[dest_id]

def mark_peer_failed(peer_id: str):
    """Mark peer as failed to cache (LRU mechanism)"""
    # Add/update timestamp and move to end
    failed_peers[peer_id] = time.time()
    failed_peers.move_to_end(peer_id)
    
    # LRU cleanup: remove oldest entries if cache exceeds limit
    if len(failed_peers) > MAX_FAILED_PEERS:  # 50
        oldest_failed = failed_peers.popitem(last=False)
        logger.debug(f"🧹 失败Peer缓存已满，移除最旧的: {oldest_failed[0]}")
```

### 当前状态
- **大小限制**：✅ 有 - `MAX_CACHED_PEERS = 100` / `MAX_FAILED_PEERS = 50`
- **清理机制**：✅ 有 - LRU 机制
- **数据结构**：`OrderedDict` - 高效 LRU 实现

### 内存估算
- **单个 Peer ID**：~20 字节（字符串）+ 8 字节（时间戳）≈ 28 字节
- **最大缓存**（100 + 50）：~4.2 KB

### 评估
✅ **状态：已优化良好**
- 新增的限制（之前无限制）
- 使用 LRU 机制自动清理
- 内存占用很小

---

## 4. 用户状态缓存 (`user_states`)

### 位置
- 文件：`bot/utils/status.py`
- 行数：7
- 类型：`Dict[str, Any]`

### 代码实现
```python
# User state storage
user_states: Dict[str, Any] = {}

def get_user_state(user_id: str) -> Dict[str, Any]:
    """Get user state"""
    return user_states.get(user_id, {})

def set_user_state(user_id: str, state: Dict[str, Any]):
    """Set user state"""
    user_states[user_id] = state

def clear_user_state(user_id: str):
    """Clear user state"""
    if user_id in user_states:
        del user_states[user_id]

def update_user_state(user_id: str, **kwargs):
    """Update user state with new values"""
    if user_id not in user_states:
        user_states[user_id] = {}
    user_states[user_id].update(kwargs)
```

### 当前状态
- **大小限制**：❌ **无限制**
- **TTL**：❌ **无 TTL**
- **清理机制**：⚠️ 仅在用户完成交互时手动清理
- **泄漏风险**：⚠️ **中等** - 用户放弃交互时状态永不清理

### 内存估算（1000 个活跃用户场景）
- **单个状态**：~100 字节（包含用户 ID、操作状态、临时数据）
- **1000 个用户**：~100 KB
- **10000 个遗弃状态**：~1 MB

### 评估
⚠️ **状态：需要优化**
- 无自动清理机制
- 用户放弃多步操作时状态会永久保留
- 长期运行可能积累大量遗弃状态

### 建议
1. 添加 TTL 机制（如 1 小时）
2. 定期清理过期状态
3. 添加最大状态数量限制

---

## 5. 消息队列 (`message_queue`)

### 位置
- 文件：`bot/core/queue.py` / `main.py`
- 行数：34
- 类型：`queue.Queue`

### 代码实现
```python
def initialize_message_queue(acc):
    """初始化消息队列和工作线程"""
    # 创建消息队列
    message_queue = queue.Queue()  # ⚠️ 无大小限制
    
    # 创建消息工作线程
    message_worker = MessageWorker(message_queue, acc, max_retries=MAX_RETRIES)
    worker_thread = threading.Thread(
        target=message_worker.run,
        daemon=True,
        name="MessageWorker"
    )
    
    # 启动工作线程
    worker_thread.start()
    
    return message_queue, message_worker
```

### 当前状态
- **大小限制**：❌ **无限制**
- **清理机制**：✅ 消息处理后自动移除
- **增长模式**：在消息爆发期间可能快速增长
- **风险场景**：
  - 大量消息同时到达
  - 工作线程处理速度慢（网络问题、API 限流）
  - 重试机制导致消息重新入队

### 内存估算
- **单个 Message 对象**：~1-2 KB（包含消息元数据、文本、配置）
- **1000 条消息积压**：~1-2 MB
- **10000 条消息积压**：~10-20 MB

### 评估
⚠️ **状态：高风险 - 无限制增长**
- 在消息爆发或处理延迟时可能快速增长
- 无队列大小限制
- 无过载保护机制

### 建议
1. 添加队列最大大小限制（如 `maxsize=10000`）
2. 当队列接近满时记录警告
3. 考虑在极端过载时拒绝或跳过消息
4. 添加队列大小监控指标

---

## 6. Pyrogram Session Peer 缓存（最严重）

### 位置
- 文件：`session-storage/myacc.session`（SQLite 数据库）
- 管理：Pyrogram 内部
- 初始化：`bot/core/client.py` 行 47-54

### 代码实现
```python
# 先尝试使用已有的 session 文件（包含 Peer 缓存）
os.makedirs("session-storage", exist_ok=True)
session_file = "session-storage/myacc"

if os.path.exists(f"{session_file}.session"):
    logger.info("📂 发现已有 Session 文件，将保留 Peer 缓存")
    acc = Client(session_file, api_id=api_id, api_hash=api_hash)
else:
    logger.info("📝 首次启动，使用 Session String 创建 Session 文件")
    acc = Client(session_file, api_id=api_id, api_hash=api_hash, session_string=ss)

# 启动User客户端
acc.start()
```

### Session 文件结构（Pyrogram 内部）
Pyrogram 使用 SQLite 数据库存储：
- **peers 表**：存储所有遇到的 peer（用户、群组、频道）
  - user_id, access_hash, username, phone_number
  - chat_id, title, username
  - channel_id, title, username
- **版本信息**
- **会话密钥**

### 当前状态
- **大小限制**：❌ **无限制**
- **清理机制**：❌ **完全没有**
- **增长模式**：
  - 每次遇到新 peer 就添加
  - 永不删除旧 peer
  - 随时间线性增长
- **泄漏风险**：🔴 **严重** - 长期运行必定增长

### 内存估算
- **单个 Peer 记录**：~200-500 字节（包含 SQLite 开销）
- **1000 个 Peer**：~1-5 MB（磁盘）
- **10000 个 Peer**：~10-50 MB（磁盘）
- **长期运行（数月）**：可能达到 100+ MB

### 实际影响
- **磁盘空间**：Session 文件持续增长
- **启动时间**：Pyrogram 加载 session 时间增加
- **内存占用**：Pyrogram 将部分 peer 数据加载到内存

### 评估
🔴 **状态：严重风险 - 无限制长期增长**
- Pyrogram 不提供自动清理机制
- Bot 长期运行后 session 文件必然膨胀
- 是最严重的内存/磁盘泄漏源

### 建议
1. **定期重建 Session 文件**（推荐）
   ```python
   # 定期（如每周）删除 session 文件，让 Pyrogram 重建
   # 备份 → 删除 → 重启 → 重建（只保留活跃 peer）
   ```

2. **手动清理 Session 数据库**（高级）
   ```python
   # 使用 SQLite 直接操作 session 文件
   # 删除旧的/不活跃的 peer 记录
   # 风险：可能影响 Pyrogram 正常运行
   ```

3. **监控 Session 文件大小**
   ```python
   # 定期检查文件大小，超过阈值时告警
   session_size = os.path.getsize("session-storage/myacc.session")
   if session_size > 50 * 1024 * 1024:  # 50MB
       logger.warning(f"⚠️ Session 文件过大: {session_size / 1024 / 1024:.1f} MB")
   ```

4. **使用内存模式**（不推荐生产环境）
   ```python
   # 使用 ":memory:" 作为 session，但会失去持久化
   # 不适合生产环境，每次重启需重新缓存
   ```

---

## 7. 监控源集合 (`_monitored_sources`)

### 位置
- 文件：`config.py`
- 行数：25
- 类型：`Set[str]`

### 代码实现
```python
# Global state
_monitored_sources: Set[str] = set()

def build_monitored_sources() -> Set[str]:
    """Build a set of all monitored source chat IDs from watch config"""
    watch_config = load_watch_config()
    sources = set()
    
    for user_id, watches in watch_config.items():
        for watch_key, watch_data in watches.items():
            if isinstance(watch_data, dict):
                source = watch_data.get('source')
            else:
                source = watch_key
            
            if source and source != 'me':
                sources.add(str(source))
    
    return sources

def reload_monitored_sources():
    """Reload the monitored sources set (call after config changes)"""
    global _monitored_sources
    _monitored_sources = build_monitored_sources()
    logger.info(f"🔄 监控源已更新: {_monitored_sources if _monitored_sources else '无'}")
```

### 当前状态
- **大小限制**：取决于配置（通常很小）
- **清理机制**：配置更新时重新加载
- **内存估算**：通常 < 1 KB（几十个源）

### 评估
✅ **状态：无风险**
- 大小由用户配置决定，通常很小
- 不会无限增长

---

## 三大内存瓶颈排名

### 🔴 1. Pyrogram Session Peer 缓存（最严重）
**风险等级：严重 | 增长模式：长期线性增长 | 清理：无**

- **问题**：Pyrogram 内部 SQLite 数据库，永不清理旧 peer
- **影响**：磁盘 + 内存，长期运行后必定膨胀（数月可达 100+ MB）
- **紧急度**：🔴 高 - 长期运行必现
- **优先级**：**最高**

**估算：**
- 1 个月运行：~5-20 MB
- 6 个月运行：~30-100 MB
- 1 年运行：~60-200 MB

### ⚠️ 2. 消息队列 (`message_queue`)（高风险）
**风险等级：高 | 增长模式：爆发性增长 | 清理：处理后自动移除**

- **问题**：无大小限制，消息爆发时可能积压
- **影响**：仅内存，短期内可能快速增长
- **触发条件**：消息爆发、网络延迟、API 限流
- **紧急度**：⚠️ 中 - 特定场景触发
- **优先级**：**次高**

**估算：**
- 正常运行：< 1 MB
- 消息爆发（1000 条积压）：~1-2 MB
- 极端爆发（10000 条积压）：~10-20 MB

### ⚠️ 3. 用户状态缓存 (`user_states`)（中等风险）
**风险等级：中等 | 增长模式：缓慢积累 | 清理：手动清理**

- **问题**：无 TTL，用户放弃交互时状态永不清理
- **影响**：仅内存，缓慢积累
- **触发条件**：用户频繁开始但不完成多步操作
- **紧急度**：⚠️ 低 - 缓慢积累
- **优先级**：**第三**

**估算：**
- 正常运行（100 个活跃用户）：~10 KB
- 1000 个遗弃状态：~100 KB
- 10000 个遗弃状态：~1 MB

---

## 已优化的缓存（良好实践）✅

以下缓存已经实现了良好的大小限制和清理机制：

1. ✅ **消息去重缓存** - TTL + 大小限制 + 强制清理
2. ✅ **媒体组去重缓存** - LRU + 大小限制 + TTL
3. ✅ **Peer 缓存** - LRU + 大小限制
4. ✅ **失败 Peer 缓存** - LRU + 大小限制
5. ✅ **监控源集合** - 配置驱动，自动同步

这些优化展示了良好的缓存管理实践，可作为其他缓存优化的参考模板。

---

## 初步优化建议

### 优先级 1：Pyrogram Session Peer 缓存（立即处理）

#### 方案 A：定期重建 Session 文件（推荐）
```python
# 新增: bot/maintenance/session_cleaner.py
import os
import shutil
from datetime import datetime

def cleanup_session_file(session_path, backup_dir="session-backups"):
    """清理 Session 文件"""
    if not os.path.exists(f"{session_path}.session"):
        return
    
    # 检查文件大小
    file_size = os.path.getsize(f"{session_path}.session") / (1024 * 1024)  # MB
    
    if file_size > 50:  # 超过 50MB
        logger.warning(f"⚠️ Session 文件过大: {file_size:.1f} MB，建议清理")
        
        # 备份
        os.makedirs(backup_dir, exist_ok=True)
        backup_path = f"{backup_dir}/myacc_{datetime.now().strftime('%Y%m%d_%H%M%S')}.session"
        shutil.copy(f"{session_path}.session", backup_path)
        logger.info(f"✅ 已备份 Session 到: {backup_path}")
        
        # 删除（重启后 Pyrogram 会重建）
        os.remove(f"{session_path}.session")
        logger.info("🗑️ 已删除旧 Session 文件，重启后将重建")
```

#### 方案 B：监控 + 告警
```python
# 在 main.py 启动时添加
session_path = "session-storage/myacc.session"
if os.path.exists(session_path):
    size_mb = os.path.getsize(session_path) / (1024 * 1024)
    logger.info(f"📊 Session 文件大小: {size_mb:.1f} MB")
    if size_mb > 50:
        logger.warning(f"⚠️ Session 文件过大，建议清理")
```

### 优先级 2：消息队列大小限制

```python
# 修改: bot/core/queue.py
def initialize_message_queue(acc):
    """初始化消息队列和工作线程"""
    # 创建有限大小的消息队列
    MAX_QUEUE_SIZE = 10000  # 最多积压 10000 条消息
    message_queue = queue.Queue(maxsize=MAX_QUEUE_SIZE)
    
    # ... 其余代码不变
```

```python
# 修改: 入队逻辑（需要处理队列满的情况）
try:
    message_queue.put(msg_obj, block=False)  # 非阻塞
except queue.Full:
    logger.warning("⚠️ 消息队列已满，跳过此消息（过载保护）")
    # 可选：增加丢弃计数器
```

### 优先级 3：用户状态 TTL 清理

```python
# 修改: bot/utils/status.py
import time
from typing import Dict, Any

# User state storage with timestamps
user_states: Dict[str, Dict[str, Any]] = {}
USER_STATE_TTL = 3600  # 1小时

def set_user_state(user_id: str, state: Dict[str, Any]):
    """Set user state with timestamp"""
    user_states[user_id] = {
        'data': state,
        'timestamp': time.time()
    }

def get_user_state(user_id: str) -> Dict[str, Any]:
    """Get user state (auto-cleanup expired)"""
    if user_id in user_states:
        state_obj = user_states[user_id]
        if time.time() - state_obj['timestamp'] < USER_STATE_TTL:
            return state_obj['data']
        else:
            # 过期，清理
            del user_states[user_id]
    return {}

def cleanup_expired_states():
    """Clean up expired user states (call periodically)"""
    current_time = time.time()
    expired_users = [
        uid for uid, state_obj in user_states.items()
        if current_time - state_obj['timestamp'] > USER_STATE_TTL
    ]
    for uid in expired_users:
        del user_states[uid]
    if expired_users:
        logger.debug(f"🧹 清理了 {len(expired_users)} 个过期用户状态")
```

---

## 内存使用总结（1000 条消息场景）

| 缓存名称 | 当前大小 | 是否有限制 | 清理机制 | 风险等级 |
|---------|---------|-----------|---------|---------|
| 消息去重缓存 | ~29 KB | ✅ 500条 | ✅ TTL + 强制 | ✅ 低 |
| 媒体组缓存 | ~21.6 KB | ✅ 200条 | ✅ LRU + TTL | ✅ 低 |
| Peer 缓存 | ~4.2 KB | ✅ 150条 | ✅ LRU | ✅ 低 |
| 用户状态 | ~100 KB | ❌ 无 | ⚠️ 手动 | ⚠️ 中 |
| 消息队列 | ~1-2 MB | ❌ 无 | ⚠️ 处理后 | ⚠️ 高 |
| Session Peer | ~10-50 MB | ❌ 无 | ❌ 无 | 🔴 严重 |
| 监控源 | ~1 KB | ✅ 配置限制 | ✅ 自动 | ✅ 低 |
| **总计（估算）** | **~11-53 MB** | - | - | - |

**注意**：Session Peer 缓存会随时间线性增长，是唯一的长期泄漏源。

---

## 监控建议

### 1. 添加缓存统计端点
```python
# 在 app.py 添加监控路由
@app.route('/api/cache-stats')
def cache_stats():
    """返回所有缓存的统计信息"""
    from bot.utils.dedup import get_cache_stats
    from bot.utils.peer import cached_dest_peers, failed_peers
    from bot.utils.status import user_states
    import os
    
    stats = {
        'message_cache': get_cache_stats(),
        'peer_cache': {
            'cached_peers': len(cached_dest_peers),
            'failed_peers': len(failed_peers),
        },
        'user_states': len(user_states),
        'queue_size': message_queue.qsize() if message_queue else 0,
        'session_file_mb': os.path.getsize("session-storage/myacc.session") / (1024 * 1024)
            if os.path.exists("session-storage/myacc.session") else 0
    }
    return jsonify(stats)
```

### 2. 定期日志记录
```python
# 在 MessageWorker.run() 中添加
if time.time() - self.last_stats_time > WORKER_STATS_INTERVAL:
    # 现有统计
    logger.info(f"📊 队列统计: ...")
    
    # 新增：缓存统计
    logger.info(f"📊 缓存统计: "
                f"消息={len(processed_messages)}, "
                f"媒体组={len(processed_media_groups)}, "
                f"Peer={len(cached_dest_peers)}, "
                f"用户状态={len(user_states)}")
```

---

## 结论

Save-Restricted-Bot 的缓存实现**整体良好**，多数缓存已实现了有效的大小限制和清理机制。但存在 **3 个关键问题**：

1. 🔴 **Pyrogram Session Peer 缓存** - 严重长期泄漏，需立即处理
2. ⚠️ **消息队列无限制** - 爆发期间风险，需添加限制
3. ⚠️ **用户状态无清理** - 缓慢积累，需添加 TTL

建议按优先级依次处理这些问题，以确保 Bot 长期稳定运行。

---

**生成时间**: 2024
**分析版本**: v1.0
**下一步**: 根据优先级实施优化建议
