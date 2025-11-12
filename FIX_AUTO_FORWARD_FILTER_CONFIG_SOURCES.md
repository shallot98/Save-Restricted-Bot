# Fix: Auto-Forward Filter Config Sources Only

**Version**: 2.3.4  
**Date**: 2025-01-XX  
**Type**: Bug Fix - Critical

## 问题描述

### 现象
- `auto_forward` 循环处理**所有**接收到的消息，而不仅仅是 `watch_config.json` 中配置的源频道消息
- 导致尝试处理无关频道（如 `-1002201840184`, `-1002529437122` 等）的消息
- 这些频道在 Pyrogram storage 中没有 peer 信息，导致 `Peer ID invalid` 错误
- `watch_config.json` 中根本没有这些频道 ID，说明这些消息不应该被处理

### 日志示例
```
📨 收到消息 - 来源: Unknown Channel (-1002529437122), 内容预览: [media]...
⚠️ 无法缓存源频道 Peer -1002529437122: Peer id invalid
🔍 检查 12 个监控任务...
```

### 根本原因

1. **消息过滤不完善**  
   - `auto_forward` 函数没有在处理早期检查源频道是否在监控列表中
   - 对所有传入的消息都进行处理，包括不需要转发的消息

2. **处理顺序问题**  
   - 先记录日志、尝试缓存 Peer，然后才在循环中检查是否匹配任务
   - 即使消息来自完全不相关的频道，仍然会执行这些操作

3. **缺少源验证**  
   - 没有在消息处理开始时验证消息来源是否在配置的监控源频道列表中

## 修复方案

### 核心思路
在处理消息的**最开始**，先提取所有监控任务的源频道 ID 集合，检查 `message.chat.id` 是否在这个集合中。如果不在，立即返回，不做任何处理。

### 实现步骤

#### 1. 提前提取监控源频道 ID
```python
# Load watch configuration
watch_config = load_watch_config()
source_chat_id = str(message.chat.id)

# Step 1: Extract all monitored source chat IDs
monitored_sources = set()
for user_id, watches in watch_config.items():
    for watch_key, watch_data in watches.items():
        if isinstance(watch_data, dict):
            # New format: extract source from watch_data
            task_source = watch_data.get("source", watch_key.split("|")[0] if "|" in watch_key else watch_key)
            if task_source:
                monitored_sources.add(task_source)
        else:
            # Old format: key is source
            monitored_sources.add(watch_key)
```

#### 2. 早期过滤非监控频道消息
```python
# Step 2: Check if message is from a monitored source
if source_chat_id not in monitored_sources:
    # Message is not from a monitored channel - skip silently
    return
```

#### 3. 仅对监控频道记录日志
```python
# Step 3: Message is from a monitored source - proceed with processing
# Log incoming message for debugging
chat_name = message.chat.title or message.chat.username or message.chat.id
msg_preview = (message.text or message.caption or "[media]")[:50]
print(f"📨 收到监控消息 - 来源: {chat_name} ({message.chat.id}), 内容预览: {msg_preview}...")
```

### 代码变更

#### 修改前 (main.py, 行 1761-1783)
```python
@acc.on_message(filters.channel | filters.group | filters.private)
def auto_forward(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
    try:
        # Log incoming message for debugging
        chat_name = message.chat.title or message.chat.username or message.chat.id
        msg_preview = (message.text or message.caption or "[media]")[:50]
        print(f"📨 收到消息 - 来源: {chat_name} ({message.chat.id}), 内容预览: {msg_preview}...")
        
        # Ensure the source peer is resolved to prevent "Peer id invalid" errors
        source_chat_str = str(message.chat.id)
        if source_chat_str not in cached_peers and source_chat_str not in failed_peers_cache:
            success, error = cache_peer(acc, source_chat_str, "源频道")
            if success:
                print(f"✅ 成功缓存源频道 Peer: {message.chat.id}")
            else:
                print(f"⚠️ 无法缓存源频道 Peer {message.chat.id}: {error}")
                # Don't return here - continue processing in case other tasks can handle it
        
        watch_config = load_watch_config()
        source_chat_id = str(message.chat.id)
```

#### 修改后 (main.py, 行 1761-1803)
```python
@acc.on_message(filters.channel | filters.group | filters.private)
def auto_forward(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
    try:
        # Load watch configuration
        watch_config = load_watch_config()
        source_chat_id = str(message.chat.id)
        
        # Step 1: Extract all monitored source chat IDs
        monitored_sources = set()
        for user_id, watches in watch_config.items():
            for watch_key, watch_data in watches.items():
                if isinstance(watch_data, dict):
                    # New format: extract source from watch_data
                    task_source = watch_data.get("source", watch_key.split("|")[0] if "|" in watch_key else watch_key)
                    if task_source:
                        monitored_sources.add(task_source)
                else:
                    # Old format: key is source
                    monitored_sources.add(watch_key)
        
        # Step 2: Check if message is from a monitored source
        if source_chat_id not in monitored_sources:
            # Message is not from a monitored channel - skip silently
            return
        
        # Step 3: Message is from a monitored source - proceed with processing
        # Log incoming message for debugging
        chat_name = message.chat.title or message.chat.username or message.chat.id
        msg_preview = (message.text or message.caption or "[media]")[:50]
        print(f"📨 收到监控消息 - 来源: {chat_name} ({message.chat.id}), 内容预览: {msg_preview}...")
        
        # Ensure the source peer is resolved to prevent "Peer id invalid" errors
        source_chat_str = str(message.chat.id)
        if source_chat_str not in cached_peers and source_chat_str not in failed_peers_cache:
            success, error = cache_peer(acc, source_chat_str, "源频道")
            if success:
                print(f"✅ 成功缓存源频道 Peer: {message.chat.id}")
            else:
                print(f"⚠️ 无法缓存源频道 Peer {message.chat.id}: {error}")
                # Don't return here - continue processing in case other tasks can handle it
```

## 修复效果

### 优点

1. **✅ 避免无关频道处理**  
   - 非监控频道的消息在最开始就被过滤掉
   - 不再尝试处理 `-1002201840184`、`-1002529437122` 等无关频道

2. **✅ 消除 Peer ID Invalid 错误**  
   - 不再对无关频道进行 Peer 缓存尝试
   - 避免 "Peer id invalid" 错误（针对未配置频道）

3. **✅ 日志更清晰**  
   - 只记录监控频道的消息
   - 日志噪音大幅减少
   - 更容易追踪实际处理的消息

4. **✅ 性能提升**  
   - 早期过滤（O(1) set 查找）
   - 避免不必要的循环遍历
   - 减少日志 I/O

5. **✅ 兼容性保持**  
   - 支持新格式配置（`watch_data` 中的 `source` 字段）
   - 支持旧格式配置（`watch_key` 作为 source）
   - 边界情况处理（None、空字符串等）

### 行为变化

#### 修复前
```
📨 收到消息 - 来源: Channel A (-1002201840184), 内容预览: [media]...
⚠️ 无法缓存源频道 Peer -1002201840184: Peer id invalid
🔍 检查 12 个监控任务...
(遍历所有任务，无匹配)

📨 收到消息 - 来源: Channel B (-1002529437122), 内容预览: Hello...
⚠️ 无法缓存源频道 Peer -1002529437122: Peer id invalid
🔍 检查 12 个监控任务...
(遍历所有任务，无匹配)

📨 收到消息 - 来源: 监控频道 (-1002314545813), 内容预览: Test...
✅ 成功缓存源频道 Peer: -1002314545813
🔍 检查 12 个监控任务...
✅ 匹配任务: -1002314545813 → -1002201840184 (用户 123456)
```

#### 修复后
```
(无关频道 A 的消息：静默跳过，无日志)

(无关频道 B 的消息：静默跳过，无日志)

📨 收到监控消息 - 来源: 监控频道 (-1002314545813), 内容预览: Test...
✅ 成功缓存源频道 Peer: -1002314545813
🔍 检查 12 个监控任务...
✅ 匹配任务: -1002314545813 → -1002201840184 (用户 123456)
```

## 测试验证

### 测试脚本
创建了 `test_filter_config_sources.py` 测试脚本，包含以下测试用例：

1. **测试 1**: 从 `watch_config` 提取监控源频道
   - ✅ 通过：成功提取所有监控源频道

2. **测试 2**: 源频道验证逻辑
   - ✅ 通过：所有源频道验证正确
   - 测试了 7 个不同场景（配置源、目标频道、无关频道等）

3. **测试 3**: 旧格式兼容性
   - ✅ 通过：旧格式兼容性正常

4. **测试 4**: 空配置处理
   - ✅ 通过：空配置处理正常

5. **测试 5**: 边界情况
   - ✅ 通过：边界情况处理正常
   - 测试了 None source、空字符串、无效 key 格式等

### 运行测试
```bash
python3 test_filter_config_sources.py
```

### 验证方法

#### 部署后验证
1. **重启 Bot**，观察启动日志
   - 应该看到监控任务的预加载信息
   - 不应该看到无关频道的错误

2. **发送消息到配置的源频道**
   - 消息应该被正常处理
   - 日志应该显示 "收到监控消息"

3. **发送消息到未配置的频道**
   - 消息应该被静默跳过（无日志记录）
   - 不应该有 Peer ID invalid 错误

4. **检查日志**
   - 不应该再有无关频道的处理记录
   - 不应该有 "无法缓存源频道 Peer" 错误（针对未配置频道）

## 相关文件

- **修改文件**:
  - `main.py` - 修改 `auto_forward` 函数（行 1761-1803）

- **测试文件**:
  - `test_filter_config_sources.py` - 新增测试脚本

- **文档文件**:
  - `FIX_AUTO_FORWARD_FILTER_CONFIG_SOURCES.md` - 本文档

## 版本历史

- **v2.3.4** (2025-01-XX): 修复 auto_forward 消息过滤逻辑，仅处理配置频道
- **v2.3.3** (2024-12-XX): 修复多频道 Peer 缓存问题
- **v2.3.2** (2024-12-XX): 修复 auto_forward 循环启动问题
- **v2.3.1** (2024-12-XX): 完整 DATA_DIR 支持和移动端优化
- **v2.3.0** (2024-12-XX): 搜索功能优化和 UI 改进

## 总结

此修复通过在消息处理的最开始添加源频道验证，确保 `auto_forward` 函数只处理 `watch_config.json` 中明确配置的源频道消息。这不仅消除了 "Peer ID invalid" 错误，还提升了性能、减少了日志噪音，使系统更加高效和清晰。

**关键改进**:
- 🎯 早期过滤（O(1) 时间复杂度）
- 🚫 避免无关频道处理
- 📝 日志更清晰
- ⚡ 性能提升
- 🔧 完全向后兼容

---
**修复完成** ✅
