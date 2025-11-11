# 转发逻辑更新说明

## 修改概述

修改了 `preserve_forward_source=false` 时的转发逻辑，从使用 `copy_message()` 改为使用 `forward_messages(drop_author=True)`。

## 问题背景

### 之前的问题

当 `preserve_forward_source=false` 时：
- 使用 `acc.copy_message()` 来复制消息
- **问题**：如果源消息包含多张图片+文字（媒体组/media group），`copy_message()` 只能转发第一张图片带文字，其他图片会被分开转发
- 结果：原本一个完整的多图+文字消息被拆分成多条消息

### 用户需求

- 保留多张图片+文字在同一个消息组中的完整性
- 但同时要隐藏"Forwarded from..."的转发来源标签
- 简单说：希望转发的消息看起来像是原创的，但保持原有的媒体组结构

## 解决方案

### 新的实现

使用 Pyrogram 的 `forward_messages()` 方法配合 `drop_author=True` 参数：

```python
# preserve_forward_source=false 时
acc.forward_messages(dest_chat_id, message.chat.id, message.id, drop_author=True)
```

### 参数说明

- `drop_author=True`: 转发消息但隐藏原始作者信息
  - 消息会被转发但不显示"Forwarded from..."标签
  - 媒体组（多图片+文字）保持完整
  - 转发的消息看起来像是由转发者原创的

## 修改详情

### 代码位置

文件：`main.py`
行数：1861-1874

### 修改前的代码

```python
# Full forward mode
else:
    if preserve_forward_source:
        if dest_chat_id == "me":
            acc.forward_messages("me", message.chat.id, message.id)
        else:
            acc.forward_messages(int(dest_chat_id), message.chat.id, message.id)
    else:
        if dest_chat_id == "me":
            acc.copy_message("me", message.chat.id, message.id)  # ❌ 会拆分媒体组
        else:
            acc.copy_message(int(dest_chat_id), message.chat.id, message.id)  # ❌ 会拆分媒体组
```

### 修改后的代码

```python
# Full forward mode
else:
    if preserve_forward_source:
        # 保留转发来源标签
        if dest_chat_id == "me":
            acc.forward_messages("me", message.chat.id, message.id)
        else:
            acc.forward_messages(int(dest_chat_id), message.chat.id, message.id)
    else:
        # 不显示转发来源，但保留媒体组完整性（多图片+文字）
        if dest_chat_id == "me":
            acc.forward_messages("me", message.chat.id, message.id, drop_author=True)  # ✅ 保持完整
        else:
            acc.forward_messages(int(dest_chat_id), message.chat.id, message.id, drop_author=True)  # ✅ 保持完整
```

## 功能对比

| 场景 | preserve_forward_source | 旧逻辑 | 新逻辑 | 效果 |
|------|------------------------|--------|--------|------|
| 单张图片+文字 | false | copy_message() | forward_messages(drop_author=True) | ✅ 无变化，都能正常转发 |
| 多张图片+文字 | false | copy_message() ❌ 拆分 | forward_messages(drop_author=True) ✅ 保持完整 | ✅ 问题修复 |
| 单张图片+文字 | true | forward_messages() | forward_messages() | ✅ 无变化 |
| 多张图片+文字 | true | forward_messages() | forward_messages() | ✅ 无变化 |

## 优势

1. **保留媒体组完整性**：多张图片+文字不会被拆分
2. **隐藏转发来源**：不显示"Forwarded from..."标签
3. **用户体验更好**：转发的消息看起来更自然
4. **兼容性好**：不影响其他功能

## 测试方法

### 测试步骤

1. 启动机器人
2. 使用 `/watch` 添加监控任务
3. 设置 `preserve_forward_source=false`（默认值）
4. 从被监控的频道发送一条包含多张图片+文字的消息
5. 检查转发到目标的消息

### 预期结果

- ✅ 所有图片和文字都在同一个消息组中
- ✅ 没有"Forwarded from..."标签
- ✅ 消息看起来像是由目标账号原创的

### 对比测试

如果想测试旧行为，可以临时修改代码：
```python
# 临时恢复旧逻辑进行对比（不推荐）
acc.copy_message(int(dest_chat_id), message.chat.id, message.id)
```

结果：会看到媒体组被拆分成多条消息。

## 其他说明

### 不影响手动转发

这次修改只影响自动监控转发功能。手动发送链接转发的功能（第 1528 行）仍然使用 `bot.copy_message()`，这是有意为之的：

- 手动转发单条消息时，用户可以选择是否加 `?single` 参数
- 如果需要转发媒体组，可以使用 `copy_media_group()`
- 手动转发和自动监控是两个不同的使用场景

### 记录模式不受影响

Record Mode（记录模式）不使用转发功能，而是直接保存到数据库，因此不受此修改影响。

## 相关文档

- Pyrogram 官方文档：https://docs.pyrogram.org/api/methods/forward_messages
- `drop_author` 参数说明：https://docs.pyrogram.org/api/methods/forward_messages#pyrogram.Client.forward_messages

## 版本信息

- 修改日期：2024
- 修改文件：main.py
- 影响行数：1869-1874
- 向后兼容：是
- 破坏性变更：否

## 总结

这次修改解决了多图片+文字消息被拆分的问题，同时保持了隐藏转发来源的功能。用户现在可以：

✅ 转发多图片+文字消息时保持完整
✅ 隐藏"Forwarded from..."标签
✅ 让转发的消息看起来像原创内容

这是一个重要的功能改进，提升了用户体验，特别是对于需要转发图文混合内容的用户。
