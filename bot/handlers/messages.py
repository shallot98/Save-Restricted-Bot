"""
Message handlers for bot interactions
"""
import pyrogram
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import os
import threading
import re

from bot.handlers import get_bot_instance, get_acc_instance
from bot.handlers.callbacks import (
    show_filter_options, show_filter_options_single,
    handle_add_source, handle_add_dest, complete_watch_setup
)
from bot.utils.status import user_states
from bot.utils.progress import progress, downstatus, upstatus


def get_message_type(msg: pyrogram.types.messages_and_media.message.Message):
    """Get the type of message"""
    try:
        msg.document.file_id
        return "Document"
    except: pass

    try:
        msg.video.file_id
        return "Video"
    except: pass

    try:
        msg.animation.file_id
        return "Animation"
    except: pass

    try:
        msg.sticker.file_id
        return "Sticker"
    except: pass

    try:
        msg.voice.file_id
        return "Voice"
    except: pass

    try:
        msg.audio.file_id
        return "Audio"
    except: pass

    try:
        msg.photo.file_id
        return "Photo"
    except: pass

    try:
        msg.text
        return "Text"
    except: pass


def handle_private(message: pyrogram.types.messages_and_media.message.Message, chatid: int, msgid: int):
    """Handle private message forwarding"""
    bot = get_bot_instance()
    acc = get_acc_instance()
    
    if acc is None:
        bot.send_message(message.chat.id, "**❌ 需要配置 String Session 才能使用此功能**")
        return
    
    msg: pyrogram.types.messages_and_media.message.Message = acc.get_messages(chatid, msgid)
    msg_type = get_message_type(msg)

    if "Text" == msg_type:
        bot.send_message(message.chat.id, msg.text, entities=msg.entities)
        return

    smsg = bot.send_message(message.chat.id, '__⬇️ 下载中__', reply_to_message_id=message.id)
    dosta = threading.Thread(target=lambda:downstatus(f'{message.id}downstatus.txt',smsg),daemon=True)
    dosta.start()
    file = acc.download_media(msg, progress=progress, progress_args=[message,"down"])
    os.remove(f'{message.id}downstatus.txt')

    upsta = threading.Thread(target=lambda:upstatus(f'{message.id}upstatus.txt',smsg),daemon=True)
    upsta.start()
    
    thumb = None
    
    if "Document" == msg_type:
        try:
            thumb = acc.download_media(msg.document.thumbs[0].file_id)
        except: thumb = None
        
        bot.send_document(message.chat.id, file, thumb=thumb, caption=msg.caption, caption_entities=msg.caption_entities, progress=progress, progress_args=[message,"up"])
        if thumb != None: os.remove(thumb)

    elif "Video" == msg_type:
        try: 
            thumb = acc.download_media(msg.video.thumbs[0].file_id)
        except: thumb = None

        bot.send_video(message.chat.id, file, duration=msg.video.duration, width=msg.video.width, height=msg.video.height, thumb=thumb, caption=msg.caption, caption_entities=msg.caption_entities, progress=progress, progress_args=[message,"up"])
        if thumb != None: os.remove(thumb)

    elif "Animation" == msg_type:
        bot.send_animation(message.chat.id, file)
           
    elif "Sticker" == msg_type:
        bot.send_sticker(message.chat.id, file)

    elif "Voice" == msg_type:
        bot.send_voice(message.chat.id, file, caption=msg.caption, caption_entities=msg.caption_entities, progress=progress, progress_args=[message,"up"])

    elif "Audio" == msg_type:
        try:
            thumb = acc.download_media(msg.audio.thumbs[0].file_id)
        except: thumb = None
            
        bot.send_audio(message.chat.id, file, caption=msg.caption, caption_entities=msg.caption_entities, progress=progress, progress_args=[message,"up"])   
        if thumb != None: os.remove(thumb)

    elif "Photo" == msg_type:
        bot.send_photo(message.chat.id, file, caption=msg.caption, caption_entities=msg.caption_entities)

    os.remove(file)
    if os.path.exists(f'{message.id}upstatus.txt'): os.remove(f'{message.id}upstatus.txt')
    bot.delete_messages(message.chat.id,[smsg.id])


def save(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
    """Handle user text input during multi-step interactions or link forwarding"""
    bot = get_bot_instance()
    acc = get_acc_instance()
    
    print(message.text)
    user_id = str(message.from_user.id)
    
    if user_id in user_states:
        action = user_states[user_id].get("action")
        
        if action == "add_source":
            handle_add_source(message, user_id)
            return
        
        elif action == "add_dest":
            handle_add_dest(message, user_id)
            return
        
        elif action == "add_whitelist":
            keywords = [kw.strip() for kw in message.text.split(',') if kw.strip()]
            if keywords:
                user_states[user_id]["whitelist"] = keywords
                bot.send_message(message.chat.id, f"✅ 关键词白名单已设置：`{', '.join(keywords)}`")
                msg = bot.send_message(message.chat.id, "⏳ 继续设置...")
                if user_states[user_id].get("record_mode"):
                    show_filter_options_single(message.chat.id, msg.id, user_id)
                else:
                    show_filter_options(message.chat.id, msg.id, user_id)
            else:
                bot.send_message(message.chat.id, "**❌ 请输入至少一个关键词**")
            return
        
        elif action == "add_blacklist":
            keywords = [kw.strip() for kw in message.text.split(',') if kw.strip()]
            if keywords:
                user_states[user_id]["blacklist"] = keywords
                bot.send_message(message.chat.id, f"✅ 关键词黑名单已设置：`{', '.join(keywords)}`")
            else:
                user_states[user_id]["blacklist"] = []
            msg = bot.send_message(message.chat.id, "⏳ 继续设置...")
            if user_states[user_id].get("record_mode"):
                show_filter_options_single(message.chat.id, msg.id, user_id)
            else:
                show_filter_options(message.chat.id, msg.id, user_id)
            return
        
        elif action == "add_regex_whitelist":
            patterns = [p.strip() for p in message.text.split(',') if p.strip()]
            if patterns:
                try:
                    for pattern in patterns:
                        re.compile(pattern)
                    user_states[user_id]["whitelist_regex"] = patterns
                    bot.send_message(message.chat.id, f"✅ 正则白名单已设置：`{', '.join(patterns)}`")
                    msg = bot.send_message(message.chat.id, "⏳ 继续设置...")
                    if user_states[user_id].get("record_mode"):
                        show_filter_options_single(message.chat.id, msg.id, user_id)
                    else:
                        show_filter_options(message.chat.id, msg.id, user_id)
                except re.error as e:
                    bot.send_message(message.chat.id, f"**❌ 正则表达式错误：** `{str(e)}`\n\n请重新输入")
            else:
                bot.send_message(message.chat.id, "**❌ 请输入至少一个正则表达式**")
            return
        
        elif action == "add_regex_blacklist":
            patterns = [p.strip() for p in message.text.split(',') if p.strip()]
            if patterns:
                try:
                    for pattern in patterns:
                        re.compile(pattern)
                    user_states[user_id]["blacklist_regex"] = patterns
                    bot.send_message(message.chat.id, f"✅ 正则黑名单已设置：`{', '.join(patterns)}`")
                    msg = bot.send_message(message.chat.id, "⏳ 继续设置...")
                    if user_states[user_id].get("record_mode"):
                        show_filter_options_single(message.chat.id, msg.id, user_id)
                    else:
                        show_filter_options(message.chat.id, msg.id, user_id)
                except re.error as e:
                    bot.send_message(message.chat.id, f"**❌ 正则表达式错误：** `{str(e)}`\n\n请重新输入")
            else:
                bot.send_message(message.chat.id, "**❌ 请输入至少一个正则表达式**")
            return
        
        elif action == "add_extract_patterns":
            patterns = [p.strip() for p in message.text.split(',') if p.strip()]
            if patterns:
                try:
                    for pattern in patterns:
                        re.compile(pattern)
                    
                    whitelist = user_states[user_id].get("whitelist", [])
                    blacklist = user_states[user_id].get("blacklist", [])
                    whitelist_regex = user_states[user_id].get("whitelist_regex", [])
                    blacklist_regex = user_states[user_id].get("blacklist_regex", [])
                    preserve_source = user_states[user_id].get("preserve_source", False)
                    
                    msg = bot.send_message(message.chat.id, "⏳ 正在完成设置...")
                    complete_watch_setup(message.chat.id, msg.id, user_id, whitelist, blacklist, whitelist_regex, blacklist_regex, preserve_source, "extract", patterns)
                except re.error as e:
                    bot.send_message(message.chat.id, f"**❌ 正则表达式错误：** `{str(e)}`\n\n请重新输入")
            else:
                bot.send_message(message.chat.id, "**❌ 请输入至少一个正则表达式**")
            return
    
    # If not in user_states or no matching action, handle as link forwarding (legacy behavior)
    # This would require the full link parsing logic from main_old.py
    # For now, just show a simple message
    bot.send_message(
        message.chat.id,
        "**📌 提示**\n\n"
        "请使用 /start 命令开始使用机器人功能\n"
        "或使用 /watch 命令管理监控任务"
    )


# Usage text constant
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
