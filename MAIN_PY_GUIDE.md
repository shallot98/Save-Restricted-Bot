# main.py 修改指南

## 需要修改的功能

### 1. 修改记录模式支持多图片（第1773-1835行）

**位置：** auto_forward 函数中的 record_mode 部分

**需要修改的代码：**

找到这段代码（大约在第1797-1826行）：
```python
# Handle media
media_type = None
media_path = None

if message.photo:
    media_type = "photo"
    photo = message.photo
    file_name = f"{message.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    file_path = os.path.join("data", "media", file_name)
    os.makedirs(os.path.join("data", "media"), exist_ok=True)
    acc.download_media(photo.file_id, file_name=file_path)
    media_path = file_name

elif message.video:
    # ... 视频处理代码
```

**替换为：**

```python
# Handle media - 支持多图片
media_type = None
media_path = None
media_paths_list = []

# 检查是否是媒体组（多图片/视频）
if hasattr(message, 'media_group_id') and message.media_group_id:
    # 这是媒体组的一部分，需要获取整个组
    try:
        # 获取媒体组中的所有消息
        media_group = acc.get_media_group(message.chat.id, message.id)
        for media_msg in media_group:
            if media_msg.photo:
                file_name = f"{media_msg.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                file_path = os.path.join("data", "media", file_name)
                os.makedirs(os.path.join("data", "media"), exist_ok=True)
                acc.download_media(media_msg.photo.file_id, file_name=file_path)
                media_paths_list.append({"type": "photo", "path": file_name})
            elif media_msg.video:
                # 保存视频缩略图
                thumb = media_msg.video.thumbs[0] if media_msg.video.thumbs else None
                if thumb:
                    file_name = f"{media_msg.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_thumb.jpg"
                    file_path = os.path.join("data", "media", file_name)
                    os.makedirs(os.path.join("data", "media"), exist_ok=True)
                    acc.download_media(thumb.file_id, file_name=file_path)
                    media_paths_list.append({"type": "video", "path": file_name})
    except Exception as e:
        print(f"Error handling media group: {e}")
        # 如果获取媒体组失败，回退到单张处理
        if message.photo:
            media_type = "photo"
            file_name = f"{message.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            file_path = os.path.join("data", "media", file_name)
            os.makedirs(os.path.join("data", "media"), exist_ok=True)
            acc.download_media(message.photo.file_id, file_name=file_path)
            media_path = file_name
else:
    # 单张图片或视频（保持原有逻辑）
    if message.photo:
        media_type = "photo"
        photo = message.photo
        file_name = f"{message.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        file_path = os.path.join("data", "media", file_name)
        os.makedirs(os.path.join("data", "media"), exist_ok=True)
        acc.download_media(photo.file_id, file_name=file_path)
        media_path = file_name
    
    elif message.video:
        media_type = "video"
        try:
            thumb = message.video.thumbs[0] if message.video.thumbs else None
            if thumb:
                file_name = f"{message.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_thumb.jpg"
                file_path = os.path.join("data", "media", file_name)
                os.makedirs(os.path.join("data", "media"), exist_ok=True)
                acc.download_media(thumb.file_id, file_name=file_path)
                media_path = file_name
        except Exception as e:
            print(f"Error downloading video thumbnail: {e}")
```

**然后修改 add_note 调用（大约在第1828行）：**

找到：
```python
add_note(
    user_id=int(user_id),
    source_chat_id=source_chat_id,
    source_name=source_name,
    message_text=content_to_save if content_to_save else None,
    media_type=media_type,
    media_path=media_path
)
```

替换为：
```python
add_note(
    user_id=int(user_id),
    source_chat_id=source_chat_id,
    source_name=source_name,
    message_text=content_to_save if content_to_save else None,
    media_type=media_type,
    media_path=media_path,
    media_paths=media_paths_list if media_paths_list else None
)
```

### 2. 修改转发模式保留多图片结构（第1862-1872行）

**位置：** auto_forward 函数中的 Full forward mode 部分

**需要修改的代码：**

找到这段代码（大约在第1862-1872行）：
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
            acc.copy_message("me", message.chat.id, message.id)
        else:
            acc.copy_message(int(dest_chat_id), message.chat.id, message.id)
```

**替换为：**

```python
# Full forward mode
else:
    # 检查是否是媒体组（多图片）
    if hasattr(message, 'media_group_id') and message.media_group_id:
        # 多图片消息，使用 copy_media_group 保留完整结构
        try:
            if dest_chat_id == "me":
                acc.copy_media_group("me", message.chat.id, message.id)
            else:
                acc.copy_media_group(int(dest_chat_id), message.chat.id, message.id)
        except Exception as e:
            print(f"Error copying media group: {e}")
            # 回退到单条复制
            if dest_chat_id == "me":
                acc.copy_message("me", message.chat.id, message.id)
            else:
                acc.copy_message(int(dest_chat_id), message.chat.id, message.id)
    else:
        # 单条消息
        if preserve_forward_source:
            if dest_chat_id == "me":
                acc.forward_messages("me", message.chat.id, message.id)
            else:
                acc.forward_messages(int(dest_chat_id), message.chat.id, message.id)
        else:
            if dest_chat_id == "me":
                acc.copy_message("me", message.chat.id, message.id)
            else:
                acc.copy_message(int(dest_chat_id), message.chat.id, message.id)
```

## 修改说明

1. **多图片支持**：使用  检测媒体组，使用  获取所有图片
2. **保留完整结构**：使用  而不是  来转发多图片
3. **向后兼容**：保留原有的单图片处理逻辑
4. **错误处理**：添加 try-except 确保失败时回退到单条处理

## 测试建议

1. 测试单张图片转发
2. 测试多张图片转发（2-10张）
3. 测试记录模式保存多图片
4. 测试不保存转发来源的多图片转发

---
作者：老王
