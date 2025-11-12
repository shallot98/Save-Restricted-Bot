# Peer Cache 问题修复指南

## 问题描述

用户报告监控转发功能失效，日志显示以下错误：

```
KeyError: 'ID not found: -1002904815462'
ValueError: Peer id invalid: -1002904815462
```

## 问题根源

这是 Pyrogram 的经典 **Peer Cache 问题**：

1. Pyrogram 需要在内部数据库中缓存所有 chat/channel 的 peer 信息
2. 当收到来自未缓存频道的消息时，Pyrogram 无法解析 peer_id
3. 错误发生在 Pyrogram 内部的 `handle_updates` 方法中，在调用我们的 handler 之前
4. 导致整个监控转发功能失效

## 解决方案

### 1. 启动时预加载所有频道 (主要方案)

**实现位置**: `print_startup_config()` 函数

在 bot 启动时：
- 遍历所有监控配置
- 提取所有 source_chat_id
- 对每个频道调用 `acc.get_chat()` 和 `acc.get_history()` 强制缓存
- 显示详细的缓存结果和失败原因

### 2. 运行时动态缓存 (辅助方案)

**实现位置**: `auto_forward()` 函数开始处

在接收到消息时：
- 尝试调用 `client.get_chat(message.chat.id)` 确保 peer 被缓存
- 捕获并记录错误，但不中断处理流程
- 作为预加载的补充保护

### 3. 改进配置格式验证

**实现位置**: 配置加载和显示逻辑

- 确保正确提取 `source` 字段
- 支持旧格式（key 作为 source）和新格式（显式 source 字段）
- 显示详细的缓存状态（将缓存/跳过缓存/缓存原因）

## 使用建议

### 启动 Bot 时

1. **检查启动日志**，确保看到以下信息：
   ```
   🔄 预加载频道信息到缓存...
   需要缓存 X 个频道
   频道ID列表: [...]
   
   ✅ 已缓存: -1001234567890
      名称: 频道名称
      类型: 频道
      验证: ✓ Peer 已完全缓存
   ```

2. **检查缓存结果**：
   ```
   📦 缓存结果: 成功 X/Y 个频道
   ```

3. **如果有缓存失败**：
   ```
   ⚠️ 警告: 以下 N 个频道缓存失败，将无法正常监控:
      • -1002904815462
   
   💡 解决方法:
      1. 确保账号已加入这些频道/群组
      2. 检查频道/群组 ID 是否正确
      3. 重新启动机器人以重试缓存
   ```

### 常见错误和解决方法

| 错误信息 | 原因 | 解决方法 |
|---------|------|---------|
| `CHAT_INVALID` / `No such peer` / `PEER_ID_INVALID` | 账号未加入频道 | 使用 String Session 账号先加入频道 |
| `FLOOD_WAIT_X` | API 请求过快 | 等待 X 秒后重新启动 |
| `验证: ⚠ 无法获取历史记录` | 频道限制访问历史 | 正常，基本缓存已完成 |

### 配置文件格式

确保配置文件使用正确的格式：

```json
{
  "user_id": {
    "source_id|dest_id": {
      "source": "source_id",  # 必须包含此字段
      "dest": "dest_id",
      "whitelist": [],
      "blacklist": [],
      "whitelist_regex": [],
      "blacklist_regex": [],
      "preserve_forward_source": false,
      "forward_mode": "full",
      "extract_patterns": [],
      "record_mode": false
    }
  }
}
```

**关键点**：
- Key 格式：`source_id|dest_id`
- 必须包含 `"source"` 字段
- source_id 必须是负数（频道/群组 ID）

### 监控检查清单

在启动 bot 后，确认：

- [ ] 所有监控任务已列出
- [ ] 需要缓存的频道 ID 正确
- [ ] 所有频道缓存成功（100% 成功率）
- [ ] 没有 `Peer id invalid` 错误
- [ ] 测试发送消息能正常转发

## 技术细节

### 为什么预加载是必须的？

Pyrogram 的更新处理流程：

1. 接收 Telegram 更新 (Update)
2. **调用 `resolve_peer()` 解析 peer_id** ← 在这一步失败
3. 构造 Message 对象
4. 调用用户的 handler（我们的 `auto_forward` 函数）

由于错误发生在第 2 步，我们的代码甚至没有机会运行。因此：
- **运行时缓存是无效的**（错误发生在我们代码之前）
- **预加载是唯一解决方案**（确保 peer 在接收更新前就已缓存）

### 缓存方法对比

| 方法 | 效果 | 说明 |
|------|------|------|
| `get_chat(chat_id)` | ✓ 缓存基本信息 | 快速，但可能不完整 |
| `get_history(chat_id, limit=1)` | ✓✓ 完全缓存 | 确保 peer 完全加载 |
| 运行时 `get_chat()` | ✗ 无效 | 太晚了，错误已发生 |

## 版本历史

### v2.3.5 (修复版本)

**主要改进**：
1. ✅ 改进预加载逻辑，正确提取所有 source_id
2. ✅ 添加 `get_history()` 验证，确保 peer 完全缓存
3. ✅ 详细的启动日志和缓存状态显示
4. ✅ 清晰的错误提示和解决建议
5. ✅ 更新配置文件示例格式
6. ✅ 运行时额外保护（辅助）

**对比 v2.3.3 被删除的修复**：
- v2.3.3: 简单的预加载逻辑
- v2.3.5: 完整的预加载 + 验证 + 详细反馈

## 参考资料

- [Pyrogram Issue #1060](https://github.com/pyrogram/pyrogram/issues/1060) - Peer ID Invalid 问题讨论
- [Telegram Bot API Docs](https://core.telegram.org/bots/api) - Chat ID 格式说明
- 项目 Memory - v2.3.3 修复记录

## 故障排查

### 1. 启动时没有看到预加载日志

**原因**: 配置文件为空或格式错误

**检查**:
```bash
cat $DATA_DIR/config/watch_config.json
```

### 2. 所有频道缓存失败

**原因**: String Session 账号配置错误

**检查**:
```python
# 检查 acc 是否正常初始化
if acc is not None:
    print("✓ String Session 正常")
else:
    print("✗ String Session 未配置")
```

### 3. 仍然出现 Peer id invalid 错误

**可能原因**:
1. 缓存时成功但后来失败（Session 文件损坏）
2. 频道 ID 在配置中拼写错误
3. 账号被频道踢出

**解决**:
1. 删除 Session 文件重新启动
2. 检查日志中的缓存 ID 是否与错误的 ID 一致
3. 重新加入频道

---

**最后更新**: 2025-01-XX
**修复版本**: v2.3.5
**状态**: ✅ 已测试通过
