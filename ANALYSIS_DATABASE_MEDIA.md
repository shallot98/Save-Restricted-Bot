# Save-Restricted-Bot 数据库和媒体处理分析

## 审查日期
2024年（基于当前代码库状态）

---

## 1. 数据库连接管理

### 当前实现
**文件位置**: `database.py`

#### 连接管理机制
```python
@contextmanager
def get_db_connection():
    """Database connection context manager"""
    conn = sqlite3.connect(DATABASE_FILE)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
```

#### 特点
- ✅ **使用上下文管理器**：自动处理 commit/rollback/close
- ✅ **异常安全**：出错时自动回滚
- ❌ **无连接池**：每次操作都创建新连接
- ✅ **资源清理**：finally 块确保连接关闭

#### 连接生命周期
1. 函数调用时创建新连接
2. 执行 SQL 操作
3. 成功则 commit，失败则 rollback
4. finally 块关闭连接

### 评估
- **适用场景**：SQLite + 中低并发
- **性能影响**：每次查询都创建连接有开销，但 SQLite 连接创建成本较低
- **潜在问题**：高并发时可能成为瓶颈
- **内存占用**：✅ 良好，连接立即释放，无泄漏风险

---

## 2. 查询结果内存加载

### 查询函数分析

#### `get_notes()` - 笔记列表查询
**文件位置**: `database.py:255-290`

```python
def get_notes(..., limit=50, offset=0):
    query += ' ORDER BY timestamp DESC LIMIT ? OFFSET ?'
    params.extend([limit, offset])
    cursor.execute(query, params)
    notes = [_parse_media_paths(dict(row)) for row in cursor.fetchall()]
    return notes
```

- ✅ **使用分页**：LIMIT 50 + OFFSET
- ✅ **避免全量加载**：每次只加载 50 条记录
- ✅ **内存友好**：即使数据库有百万条记录，内存中只有 50 条

#### `get_note_count()` - 计数查询
**文件位置**: `database.py:292-322`

```python
def get_note_count(...):
    query = 'SELECT COUNT(*) FROM notes WHERE 1=1'
    cursor.execute(query, params)
    return cursor.fetchone()[0]
```

- ✅ **只返回数字**：不加载数据到内存
- ✅ **高效计数**：SQL 引擎优化

#### `get_sources()` - 来源列表
**文件位置**: `database.py:324-338`

```python
def get_sources(user_id=None):
    query = 'SELECT DISTINCT source_chat_id, source_name FROM notes WHERE 1=1'
    cursor.execute(query, params)
    return [dict(row) for row in cursor.fetchall()]
```

- ⚠️ **全量加载所有来源**：无分页
- ✅ **通常数据量小**：DISTINCT 结果集通常不大（< 100 个来源）
- 📊 **风险评估**：低风险，除非用户监控数百个频道

### Web UI 分页
**文件位置**: `app.py:58-95`

```python
NOTES_PER_PAGE = 50
offset = (page - 1) * NOTES_PER_PAGE
notes_list = get_notes(..., limit=NOTES_PER_PAGE, offset=offset)
```

- ✅ **完整分页实现**：前端 + 后端配合
- ✅ **内存控制**：每页只加载 50 条

### 评估
- **内存占用**：✅ 优秀，所有大查询都有分页限制
- **潜在问题**：无（当前实现合理）

---

## 3. 媒体文件处理

### 媒体下载位置

#### 主要处理函数
**文件位置**: `bot/workers/message_worker.py`

##### 3.1 `_handle_media_group()` - 媒体组（多图）
**行数**: 375-484

```python
def _handle_media_group(self, message, content_to_save):
    media_group = self.acc.get_media_group(message.chat.id, message.id)
    for idx, msg in enumerate(media_group):
        if msg.photo:
            file_path = os.path.join(MEDIA_DIR, file_name)
            self.acc.download_media(msg.photo.file_id, file_name=file_path)
            # 保存到本地或 WebDAV
```

- 📥 **处理类型**：图片、视频缩略图、GIF 缩略图
- 📁 **保存位置**：`$DATA_DIR/media/`
- 🔢 **数量限制**：最多 9 个媒体（MAX_MEDIA_PER_GROUP）

##### 3.2 `_handle_single_photo()` - 单张图片
**行数**: 486-505

```python
def _handle_single_photo(self, message):
    file_path = os.path.join(MEDIA_DIR, file_name)
    self.acc.download_media(message.photo.file_id, file_name=file_path)
```

##### 3.3 `_handle_single_video()` - 视频缩略图
**行数**: 507-541

```python
def _handle_single_video(self, message):
    file_path = os.path.join(MEDIA_DIR, file_name)
    self.acc.download_media(thumb.file_id, file_name=file_path)
```

##### 3.4 `_handle_single_animation()` - GIF 缩略图
**行数**: 543-577

### 文件下载流程

```
消息队列 → MessageWorker.process_message()
    ↓
_handle_record_mode()
    ↓
判断媒体类型（media_group / photo / video / animation）
    ↓
调用对应的 _handle_* 函数
    ↓
acc.download_media() ← Pyrogram 流式下载
    ↓
保存到 $DATA_DIR/media/文件名.jpg
    ↓
存储位置记录到数据库（相对路径）
```

### 媒体下载是否全量加载？

#### Pyrogram 下载机制
```python
self.acc.download_media(file_id, file_name=file_path)
```

- ✅ **流式处理**：Pyrogram 使用流式下载，分块写入磁盘
- ✅ **不占用大量内存**：内存中只保留小缓冲区（通常 64KB-1MB）
- ✅ **适合大文件**：即使下载几百 MB 的文件也不会占用对应的内存

#### 证据
Pyrogram 内部使用 `aiofiles` 和流式 HTTP 下载：
- 数据分块传输（chunked transfer）
- 边下载边写入磁盘
- 内存占用恒定，与文件大小无关

### 数据库存储
**文件位置**: `database.py:188-236`

```python
def add_note(..., media_path=None, media_paths=None):
    # 只存储相对文件名，如 "123456_20240101_120000.jpg"
    cursor.execute('''
        INSERT INTO notes (..., media_path, media_paths, ...)
        VALUES (?, ?, ?, ...)
    ''', (..., media_path, media_paths_json, ...))
```

- ✅ **只存储文件名**：不存储完整路径或二进制数据
- ✅ **JSON 数组**：媒体组用 JSON 存储多个文件名
- ✅ **轻量级**：数据库行很小（几百字节）

### 评估
- **下载方式**：✅ 流式处理，内存占用低
- **存储方式**：✅ 磁盘存储，数据库只存元数据
- **内存风险**：✅ 无风险

---

## 4. 媒体缓存清理策略

### 当前实现

#### 删除笔记时清理
**文件位置**: `database.py:383-416`

```python
def delete_note(note_id):
    # 先获取笔记信息以删除关联的媒体文件
    cursor.execute('SELECT media_path, media_paths FROM notes WHERE id = ?', (note_id,))
    result = cursor.fetchone()
    
    # 收集所有媒体文件
    media_files = set()
    if result:
        single_path, media_paths_json = result
        if single_path:
            media_files.add(single_path)
        if media_paths_json:
            media_files.update(json.loads(media_paths_json))
    
    # 删除数据库记录
    cursor.execute('DELETE FROM notes WHERE id = ?', (note_id,))
    
    # 删除关联的媒体文件
    for media_path in media_files:
        full_media_path = os.path.join(DATA_DIR, 'media', media_path)
        if os.path.exists(full_media_path):
            os.remove(full_media_path)
```

- ✅ **手动删除时清理**：用户删除笔记会同步删除媒体文件
- ✅ **防止孤儿文件**：数据库记录和媒体文件一致

### 缺失的功能

#### ❌ 自动清理策略
- 没有基于时间的自动清理（如删除 90 天前的媒体）
- 没有基于大小的限制（如媒体目录超过 10GB 时清理）
- 没有定期清理孤儿文件（数据库已删但文件仍存在）

#### ❌ 冷存储迁移
- 没有将旧媒体移动到冷存储（如 S3、对象存储）
- 所有媒体永久保存在本地磁盘

#### ❌ 磁盘空间监控
- 没有磁盘空间使用率监控
- 没有空间不足的告警机制

### 潜在问题

#### 磁盘空间耗尽
假设场景：
- 每天接收 1000 条媒体消息
- 平均每个媒体文件 200KB（缩略图）
- 每天占用：1000 × 200KB = 200MB
- 一年占用：200MB × 365 = 73GB

#### 孤儿文件
可能场景：
- 程序崩溃时文件已下载但数据库未提交
- 手动删除数据库记录但未删除文件
- 媒体文件名存储错误导致无法关联

### 评估
- **当前状态**：❌ **无自动清理策略**
- **风险等级**：🔴 **高风险**（长期运行会耗尽磁盘空间）
- **影响**：磁盘空间持续增长，无自动回收机制

---

## 5. 长期运行的全局对象

### 5.1 消息去重缓存
**文件位置**: `bot/utils/dedup.py`

#### `processed_messages` - 消息缓存
```python
processed_messages: Dict[str, float] = {}  # key → timestamp
MESSAGE_CACHE_TTL = 0.3  # 0.3 秒
MESSAGE_CACHE_MAX_SIZE = 500  # 最大 500 条
```

- ✅ **有清理机制**：`cleanup_old_messages()` 定期清理
- ✅ **时间窗口**：只保留 0.3 秒内的消息
- ✅ **大小限制**：超过 500 条时强制清理 50%
- ✅ **线程安全**：使用 `_message_lock`

#### `processed_media_groups` - 媒体组缓存
```python
processed_media_groups: OrderedDict[str, float] = OrderedDict()
MAX_MEDIA_GROUP_CACHE = 200  # 最大 200 条
MEDIA_GROUP_DEDUP_WINDOW = 2.0  # 2 秒窗口
```

- ✅ **LRU 缓存**：OrderedDict 实现 LRU
- ✅ **批量清理**：超过限制时移除最旧的 50 条
- ✅ **时间窗口**：2 秒内的重复会被过滤
- ✅ **线程安全**：使用 `_media_group_lock`

### 5.2 Peer 缓存
**文件位置**: `bot/utils/peer.py`

#### `cached_dest_peers` - 目标频道缓存
```python
cached_dest_peers: OrderedDict[str, float] = OrderedDict()
MAX_CACHED_PEERS = 100  # 最大 100 个
```

- ✅ **LRU 缓存**：OrderedDict 实现
- ✅ **大小限制**：超过 100 个时移除最旧的
- ✅ **防止无限增长**

#### `failed_peers` - 失败 Peer 缓存
```python
failed_peers: OrderedDict[str, float] = OrderedDict()
MAX_FAILED_PEERS = 50  # 最大 50 个
RETRY_COOLDOWN = 60  # 60 秒重试冷却
```

- ✅ **LRU 缓存**：OrderedDict 实现
- ✅ **大小限制**：超过 50 个时移除最旧的
- ✅ **自动清理**：成功缓存后从失败列表移除

### 5.3 用户状态
**文件位置**: `bot/utils/status.py`

```python
user_states: Dict[str, Dict[str, Any]] = {}
```

- ✅ **使用后清理**：完成多步操作后调用 `clear_user_state()`
- ✅ **临时存储**：只在用户交互期间存在
- ⚠️ **潜在风险**：如果用户中断操作未清理，会残留

### 5.4 消息队列
**文件位置**: `bot/workers/message_worker.py`

```python
self.message_queue = queue.Queue()  # 无界队列
```

- ✅ **处理后移除**：`task_done()` 确保消息处理后移除
- ⚠️ **无界队列**：理论上可以无限增长
- ✅ **实际影响小**：消息处理速度通常快于接收速度

### 评估
- **整体状况**：✅ **良好**，大多数全局对象有限制
- **潜在问题**：
  - `user_states` 可能残留未完成的交互状态
  - 消息队列无上限（极端情况可能积压）

---

## 6. 发现的潜在问题

### 6.1 媒体目录无限增长 🔴 高优先级
**问题**: 媒体文件永久保存，无自动清理
**影响**: 
- 磁盘空间耗尽
- 备份时间增加
- I/O 性能下降

**证据**:
```python
# delete_note() 是唯一删除媒体的地方
def delete_note(note_id):
    # 手动删除笔记才会删除媒体
    os.remove(full_media_path)
```

### 6.2 无数据库索引优化 🟡 中优先级
**问题**: 查询性能可能随数据量增长而下降
**影响**: 
- 大量数据时查询变慢
- Web UI 响应时间增加

**证据**:
```python
# 未创建索引的查询字段
query += ' AND user_id = ?'  # 无索引
query += ' AND source_chat_id = ?'  # 无索引
query += ' AND DATE(timestamp) >= ?'  # 无索引
```

### 6.3 孤儿媒体文件 🟡 中优先级
**问题**: 可能存在数据库已删但文件仍在的情况
**影响**: 
- 磁盘空间浪费
- 难以清理

**场景**:
- 程序崩溃时事务回滚
- 手动编辑数据库
- 文件路径记录错误

### 6.4 连接池缺失 🟢 低优先级
**问题**: 每次查询都创建新连接
**影响**: 
- 高并发时性能开销
- 对 SQLite 影响较小

### 6.5 消息队列无上限 🟢 低优先级
**问题**: 理论上可以无限增长
**影响**: 
- 极端情况内存耗尽
- 实际场景很少发生

---

## 7. 可操作的优化建议

### 7.1 实施媒体清理策略 🔴 必须

#### 选项 A：基于时间的自动清理
创建定期任务（cron 或后台线程）：

```python
def cleanup_old_media(days_to_keep=90):
    """删除 N 天前的媒体文件"""
    cutoff_date = datetime.now() - timedelta(days=days_to_keep)
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, media_path, media_paths FROM notes WHERE timestamp < ?",
            (cutoff_date,)
        )
        for note in cursor.fetchall():
            # 删除媒体文件
            # 可选：保留数据库记录，只删文件
```

**优点**: 简单直接，可配置保留期
**缺点**: 旧笔记失去媒体文件

#### 选项 B：基于磁盘空间的清理
监控磁盘使用率，超过阈值时清理：

```python
def cleanup_by_disk_usage(max_gb=50):
    """当媒体目录超过 N GB 时，删除最旧的媒体"""
    total_size = get_directory_size(MEDIA_DIR)
    if total_size > max_gb * 1024**3:
        # 删除最旧的 20% 媒体
```

**优点**: 磁盘空间可控
**缺点**: 实现稍复杂

#### 选项 C：WebDAV + 本地缓存
- 所有媒体上传到 WebDAV
- 本地只保留最近 7 天的缓存
- 过期后从本地删除（WebDAV 仍保留）

**优点**: 历史数据不丢失，本地空间可控
**缺点**: 需要配置 WebDAV 服务器

**推荐**: 选项 A + 选项 C 组合

### 7.2 添加数据库索引 🟡 推荐

```sql
CREATE INDEX idx_user_id ON notes(user_id);
CREATE INDEX idx_source_chat_id ON notes(source_chat_id);
CREATE INDEX idx_timestamp ON notes(timestamp);
CREATE INDEX idx_media_group_id ON notes(media_group_id);
```

**影响**: 
- 查询速度提升 10-100 倍（取决于数据量）
- 轻微的写入性能下降（可忽略）

**实施**: 在 `init_database()` 中添加索引创建

### 7.3 定期清理孤儿文件 🟡 推荐

创建清理脚本：

```python
def cleanup_orphan_media():
    """删除数据库中不存在的媒体文件"""
    # 1. 获取数据库中所有媒体文件名
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT media_path, media_paths FROM notes")
        db_files = set()
        for row in cursor.fetchall():
            # 收集所有文件名
    
    # 2. 扫描媒体目录
    disk_files = set(os.listdir(MEDIA_DIR))
    
    # 3. 找出孤儿文件
    orphans = disk_files - db_files
    
    # 4. 删除孤儿文件
    for orphan in orphans:
        os.remove(os.path.join(MEDIA_DIR, orphan))
```

**建议频率**: 每周执行一次

### 7.4 添加磁盘监控 🟡 推荐

集成监控工具或自定义告警：

```python
def check_disk_usage():
    """检查磁盘使用率"""
    total, used, free = shutil.disk_usage(DATA_DIR)
    usage_percent = (used / total) * 100
    
    if usage_percent > 90:
        logger.warning(f"⚠️ 磁盘使用率过高: {usage_percent:.1f}%")
        # 发送告警通知
```

**建议**: 在 MessageWorker 的统计日志中添加磁盘监控

### 7.5 优化消息队列 🟢 可选

添加队列大小限制：

```python
self.message_queue = queue.Queue(maxsize=1000)  # 最多 1000 条
```

**影响**: 
- 队列满时新消息会阻塞
- 防止内存耗尽

**建议**: 暂时不需要，除非实际遇到积压问题

### 7.6 连接池 🟢 可选

对于 SQLite，连接池意义不大。如果未来迁移到 PostgreSQL/MySQL：

```python
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

engine = create_engine(
    'postgresql://...', 
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10
)
```

**建议**: 当前无需实施

---

## 8. 实施优先级

### 立即实施（1-2 周内）
1. ✅ **媒体清理策略** - 防止磁盘耗尽
2. ✅ **数据库索引** - 提升查询性能

### 短期实施（1 个月内）
3. ✅ **孤儿文件清理** - 释放磁盘空间
4. ✅ **磁盘监控** - 预警机制

### 中长期规划（3 个月内）
5. 🔄 **WebDAV 集成优化** - 已实现基础功能，可扩展
6. 🔄 **数据归档策略** - 将历史数据移至冷存储

---

## 9. 总结

### 优点 ✅
- 数据库连接管理良好（上下文管理器）
- 查询都有分页，无全量加载风险
- 媒体下载使用流式处理，内存占用低
- 全局缓存都有大小限制和 LRU 清理
- 代码结构清晰，易于维护

### 缺点 ❌
- 媒体文件无自动清理，磁盘空间持续增长
- 缺少数据库索引，大数据量时性能下降
- 无孤儿文件清理机制
- 无磁盘空间监控和告警

### 风险评估
- 🔴 **高风险**: 媒体目录无限增长（长期运行必须解决）
- 🟡 **中风险**: 数据库性能、孤儿文件（影响用户体验）
- 🟢 **低风险**: 连接池、消息队列（当前实现可接受）

### 推荐行动
1. **优先实施媒体清理策略**（选项 A + C）
2. **添加数据库索引**（执行时间 < 1 分钟）
3. **创建定期清理脚本**（每周自动执行）
4. **添加磁盘监控**（集成到现有日志系统）

---

## 附录：代码位置速查

| 功能 | 文件 | 行数 |
|------|------|------|
| 数据库连接管理 | `database.py` | 22-33 |
| 查询分页 | `database.py` | 255-290 |
| 媒体组下载 | `bot/workers/message_worker.py` | 375-484 |
| 单张图片下载 | `bot/workers/message_worker.py` | 486-505 |
| 视频缩略图下载 | `bot/workers/message_worker.py` | 507-541 |
| 删除笔记（含媒体） | `database.py` | 383-416 |
| 消息去重缓存 | `bot/utils/dedup.py` | 14-156 |
| Peer 缓存 | `bot/utils/peer.py` | 13-131 |
| Web UI 分页 | `app.py` | 58-95 |

