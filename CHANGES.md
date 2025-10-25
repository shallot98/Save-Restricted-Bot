# 更新说明 / Changes

## 版本更新 / Version Update

本次更新添加了三个主要功能改进 / This update adds three major feature improvements:

### 1. 静默转发失败 / Silent Forward Failures

**功能说明 / Description:**
- 转发失败时不再显示错误提示，直接忽略
- When forwarding fails, no error messages are shown - failures are silently ignored

**实现细节 / Implementation:**
- 所有转发操作的错误都被静默捕获
- All forwarding operation errors are silently caught
- 只有配置相关的错误才会显示给用户
- Only configuration-related errors are shown to users

### 2. 直接转发内容 / Direct Forwarding

**功能说明 / Description:**
- 执行命令时直接转发内容，不再回复命令消息
- When executing forwarding commands, content is forwarded directly without replying to the command message

**实现细节 / Implementation:**
- 从所有内容转发操作中移除了 `reply_to_message_id` 参数
- Removed `reply_to_message_id` parameter from all content forwarding operations
- 状态消息（下载中/上传中）仍然会回复命令以提供用户反馈
- Status messages (downloading/uploading) still reply to commands for user feedback

**效果对比 / Comparison:**

Before:
```
User: https://t.me/channel/123
Bot: ⬇️ 下载中 (replying to command)
Bot: [Forwarded content] (replying to command)
```

After:
```
User: https://t.me/channel/123
Bot: ⬇️ 下载中 (replying to command)
Bot: [Forwarded content] (NOT replying to command)
```

### 3. 关键词黑白名单过滤 / Keyword Blacklist/Whitelist Filtering

**功能说明 / Description:**
- 监控功能支持关键词白名单和黑名单
- Monitoring now supports keyword whitelist and blacklist
- ~~匹配的关键词会显示在转发消息中~~ (已移除 / Removed)
- ~~Matched keywords are displayed in forwarded messages~~ (已移除 / Removed)

**使用方法 / Usage:**

```bash
# 基本监控（无过滤）/ Basic monitoring (no filtering)
/watch add @source @dest

# 白名单过滤 / Whitelist filtering
/watch add @source me whitelist:重要,紧急,新闻

# 黑名单过滤 / Blacklist filtering
/watch add @source me blacklist:广告,推广,垃圾

# 组合使用 / Combined usage
/watch add @source me whitelist:新闻 blacklist:娱乐

# 保留转发来源 / Preserve forward source (NEW)
/watch add @source me preserve_source:true
```

**过滤规则 / Filtering Rules:**
1. **白名单 (Whitelist):** 只转发包含至少一个白名单关键词的消息
   - Only forwards messages containing at least one whitelisted keyword
2. **黑名单 (Blacklist):** 不转发包含任何黑名单关键词的消息
   - Does not forward messages containing any blacklisted keyword
3. **优先级 (Priority):** 黑名单优先级高于白名单
   - Blacklist has higher priority than whitelist
4. **不区分大小写 (Case-insensitive):** 关键词匹配不区分大小写
   - Keyword matching is case-insensitive

**消息格式 / Message Format:**

转发的消息保持原始内容，不添加任何前缀信息
Forwarded messages maintain original content without any prefix

```
[原始消息内容]
[Original message content]
```

### 4. 保留转发来源选项 / Preserve Forward Source Option (NEW)

**功能说明 / Description:**
- 可选择是否在转发时保留原始消息来源信息
- Option to preserve original message source information when forwarding
- 默认不保留（与之前版本行为一致）
- Default: do not preserve (consistent with previous version behavior)

**使用方法 / Usage:**

```bash
# 不保留来源（默认）/ Don't preserve source (default)
/watch add @source @dest

# 保留来源 / Preserve source
/watch add @source @dest preserve_source:true
```

**效果对比 / Comparison:**

- `preserve_source:false` (默认 / default): 使用 `copy_message()`，消息不显示来源
  - Uses `copy_message()`, message doesn't show source
- `preserve_source:true`: 使用 `forward_messages()`，消息显示 "Forwarded from [原频道]"
  - Uses `forward_messages()`, message shows "Forwarded from [original channel]"

**配置结构 / Configuration Structure:**

新格式 / New format:
```json
{
  "user_id": {
    "source_chat_id": {
      "dest": "destination_chat_id",
      "whitelist": ["keyword1", "keyword2"],
      "blacklist": ["keyword3", "keyword4"],
      "preserve_forward_source": false
    }
  }
}
```

旧格式（仍然支持）/ Old format (still supported):
```json
{
  "user_id": {
    "source_chat_id": "destination_chat_id"
  }
}
```

## 向后兼容 / Backward Compatibility

- 所有更改都向后兼容
- All changes are backward compatible
- 旧的监控配置会继续正常工作
- Old monitoring configurations will continue to work
- 新功能是可选的
- New features are optional

## 命令更新 / Command Updates

### /watch list
现在显示关键词信息和转发来源选项 / Now shows keyword information and forward source option:
```
📋 你的监控任务列表：

1. `-100123456789` ➡️ `me`
   白名单: `重要, 紧急`
   黑名单: `广告, 垃圾`
   保留转发来源: `是`

总计： 1 个监控任务
```

### /watch add
新增关键词参数和转发来源选项 / New keyword parameters and forward source option:
```
/watch add <source> <dest> [whitelist:kw1,kw2] [blacklist:kw3,kw4] [preserve_source:true/false]
```

### /watch remove
功能保持不变，支持新旧配置格式 / Unchanged, supports both old and new configuration formats

## 测试 / Testing

运行测试脚本 / Run test script:
```bash
python3 test_changes.py
```

## 注意事项 / Notes

1. 关键词匹配作用于消息文本和媒体标题
   - Keyword matching applies to message text and media captions
2. 如果消息既没有文本也没有标题，不会被关键词过滤
   - Messages without text or caption won't be filtered by keywords
3. 转发失败不会有任何通知，请确保目标频道设置正确
   - No notifications for forwarding failures, ensure destination is configured correctly
4. 关键词信息不再显示在转发的消息中（已移除此功能）
   - Keyword information is no longer displayed in forwarded messages (feature removed)
5. 保留转发来源默认为关闭，与之前版本保持一致
   - Preserve forward source defaults to off, consistent with previous versions
