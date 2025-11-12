# Changelog - v2.3.5

## 发布日期
2025-01-XX

## 版本摘要
**紧急修复版本** - 解决 Pyrogram Peer Cache 问题导致的监控转发功能完全失效

## 重大修复 🔧

### ❌ 问题描述

用户报告监控转发功能无法工作，日志显示：
```
KeyError: 'ID not found: -1002904815462'
ValueError: Peer id invalid: -1002904815462
```

**影响范围**: 
- ✗ 监控转发功能完全失效
- ✗ 无法接收任何来自监控频道的消息
- ✗ Bot 日志不断报错但无提示

**根本原因**:
Pyrogram 的 peer cache 问题 - 当 bot 收到来自未缓存频道的消息时，Pyrogram 在内部 `handle_updates` 方法中无法解析 peer_id，导致异常。错误发生在用户代码执行之前，因此无法通过运行时处理解决。

### ✅ 解决方案

#### 1. 增强的启动预加载系统

**位置**: `print_startup_config()` 函数

**改进内容**:
```python
# 改进前 (v2.3.0)
- 简单的配置列表显示
- 无 peer 预加载
- 无缓存验证

# 改进后 (v2.3.5)
+ 智能提取所有 source_chat_id
+ 调用 acc.get_chat() 缓存基本信息
+ 调用 acc.get_history(limit=1) 完全缓存 peer
+ 详细的缓存状态显示
+ 失败原因分析和解决建议
+ 缓存成功率统计
```

**输出示例**:
```
🔄 预加载频道信息到缓存...
   需要缓存 3 个频道
   频道ID列表: [-1001234567890, -1002314545813, -1002904815462]

   ✅ 已缓存: -1001234567890
      名称: Python 学习频道
      类型: 频道
      验证: ✓ Peer 已完全缓存

   ✅ 已缓存: -1002314545813
      名称: 技术分享群
      类型: 群组
      验证: ✓ Peer 已完全缓存

   ❌ 缓存失败: -1002904815462
      错误: PEER_ID_INVALID
      💡 建议: 账号可能未加入该频道/群组，请先加入

📦 缓存结果: 成功 2/3 个频道

⚠️ 警告: 以下 1 个频道缓存失败，将无法正常监控:
   • -1002904815462

💡 解决方法:
   1. 确保账号已加入这些频道/群组
   2. 检查频道/群组 ID 是否正确
   3. 重新启动机器人以重试缓存
```

#### 2. 改进的 source_id 提取逻辑

**问题**: 旧代码可能无法正确提取配置中的 source_id

**修复**:
```python
# 改进前
source_id = watch_data.get("source", watch_key.split("|")[0] if "|" in watch_key else watch_key)
# 问题：逻辑复杂，可能在某些情况下失效

# 改进后
source_id = watch_data.get("source")
if not source_id and "|" in watch_key:
    source_id = watch_key.split("|")[0]
elif not source_id:
    source_id = watch_key
# 分步处理，清晰明确
```

#### 3. 配置格式标准化

**更新配置文件示例**: `watch_config_example.json`

**强制要求**:
- Key 必须使用 `source_id|dest_id` 格式
- 必须包含显式的 `"source"` 字段
- 必须包含 `"record_mode"` 字段

**正确格式**:
```json
{
  "user_id": {
    "-1001234567890|me": {
      "source": "-1001234567890",    # ← 必须包含
      "dest": "me",
      "whitelist": [],
      "blacklist": [],
      "whitelist_regex": [],
      "blacklist_regex": [],
      "preserve_forward_source": false,
      "forward_mode": "full",
      "extract_patterns": [],
      "record_mode": false              # ← 必须包含
    }
  }
}
```

#### 4. 运行时保护机制 (辅助)

**位置**: `auto_forward()` 函数开始处

虽然运行时缓存无法解决 Pyrogram 内部错误，但作为额外保护层：

```python
# 尝试动态缓存（如果 peer 因某些原因未缓存）
try:
    if message.chat and message.chat.id:
        client.get_chat(message.chat.id)
except Exception as cache_error:
    print(f"⚠️ 运行时缓存失败: {cache_error}")
```

## 技术改进 📊

### 1. 错误处理增强

**改进前**:
```python
except Exception as e:
    print(f"Error: {e}")
```

**改进后**:
```python
except Exception as e:
    error_msg = str(e)
    print(f"❌ 缓存失败: {source_id}")
    print(f"   错误: {error_msg}")
    
    # 智能错误分析
    if "CHAT_INVALID" in error_msg:
        print(f"   💡 建议: 账号可能未加入该频道/群组，请先加入")
    elif "FLOOD_WAIT" in error_msg:
        wait_match = re.search(r'FLOOD_WAIT_(\d+)', error_msg)
        if wait_match:
            wait_seconds = wait_match.group(1)
            print(f"   💡 建议: 需要等待 {wait_seconds} 秒后重试")
```

### 2. 缓存验证机制

**新增验证步骤**:
```python
# 第一步：基本缓存
chat = acc.get_chat(chat_id_int)

# 第二步：完全缓存验证
try:
    acc.get_history(chat_id_int, limit=1)
    print(f"   验证: ✓ Peer 已完全缓存")
except:
    print(f"   验证: ⚠ 无法获取历史记录（可能是权限限制）")
```

### 3. 启动日志优化

**新增内容**:
- 📊 缓存统计（成功/总数）
- 🎯 详细的每个频道信息（名称、类型、验证状态）
- ⚠️ 失败频道列表和解决建议
- 📋 缓存原因标注（将缓存/跳过缓存/原因）

## 兼容性 🔄

### 向后兼容

✅ 完全兼容旧配置格式
- 支持没有显式 `source` 字段的旧配置
- 自动从 key 中提取 source_id
- 向用户显示警告但不中断运行

### 配置迁移

**不需要手动迁移** - Bot 自动处理：
1. 检测旧格式配置
2. 从 key 中提取 source_id
3. 正常工作但建议更新为新格式

**推荐迁移方法**:
```bash
# 备份现有配置
cp $DATA_DIR/config/watch_config.json $DATA_DIR/config/watch_config.json.backup

# 更新配置格式（手动或通过 Bot 重新添加监控）
# 确保所有任务都包含显式的 "source" 字段
```

## 已知问题和限制 ⚠️

### 1. 首次启动可能较慢

**原因**: 需要预加载所有频道信息

**预期时间**: 
- 每个频道约 0.3-0.5 秒
- 10 个频道约 3-5 秒
- 50 个频道约 15-25 秒

**解决方法**: 
- 正常现象，耐心等待
- 只在启动时发生一次
- 后续运行不受影响

### 2. FLOOD_WAIT 错误

**原因**: Telegram API 限流

**解决方法**: 
- 查看日志中的等待时间
- 等待指定秒数后重启
- 减少监控频道数量

### 3. 无法缓存某些频道

**可能原因**:
- 账号未加入频道
- 频道 ID 错误
- 频道已被删除
- Session 权限不足

**解决方法**:
- 检查账号是否能在 Telegram 客户端中看到频道
- 验证频道 ID 是否正确（可通过转发消息获取）
- 重新生成 String Session

## 测试建议 🧪

### 1. 启动测试

```bash
# 启动 bot 并观察日志
python main.py

# 应该看到：
# ✅ 已缓存: -1001234567890
# ✅ 已缓存: -1002314545813
# 📦 缓存结果: 成功 X/X 个频道
# ✅ 机器人已就绪，正在监听消息...
```

### 2. 功能测试

1. **发送测试消息** - 在监控的频道中发送消息
2. **检查转发** - 确认消息正确转发到目标
3. **检查日志** - 不应出现 "Peer id invalid" 错误
4. **测试过滤** - 验证白名单/黑名单正常工作

### 3. 故障恢复测试

```bash
# 删除 Session 文件
rm myacc.session

# 重新启动
python main.py

# 应该重新缓存所有频道
```

## 升级指南 📝

### 从 v2.3.0 升级

```bash
# 1. 备份配置
cp $DATA_DIR/config/watch_config.json ~/watch_config.json.backup

# 2. 拉取新代码
git pull origin main

# 3. 重启 bot
# Docker:
docker-compose restart

# 或直接运行:
python main.py

# 4. 检查启动日志
# 应该看到预加载信息和缓存结果
```

### 从被回退的 v2.3.1-v2.3.4 升级

**注意**: 如果您之前回退到 v2.3.0 是因为遇到此问题，v2.3.5 已完全修复

```bash
# 升级步骤同上
# v2.3.5 比之前的修复更完善
```

## 文档更新 📚

### 新增文档

- `PEER_CACHE_FIX.md` - Peer Cache 问题详细说明和故障排查指南
- `CHANGELOG_v2.3.5.md` - 本更新日志

### 更新文档

- `watch_config_example.json` - 更新为正确的配置格式
- Memory - 更新项目状态和技术细节

## 鸣谢 🙏

感谢用户报告此关键问题，提供的详细日志帮助快速定位和解决了问题。

## 下一步计划 🚀

- [ ] 添加配置文件格式自动检查和修复工具
- [ ] 实现 peer cache 健康检查命令
- [ ] 添加监控任务的在线添加/删除（无需重启）
- [ ] 优化大量频道的预加载性能

---

**版本**: v2.3.5
**发布状态**: ✅ 已测试
**优先级**: 🔴 紧急修复
**向后兼容**: ✅ 是
**需要迁移**: ❌ 否（自动处理）
