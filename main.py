import pyrogram
from pyrogram import Client, filters
from pyrogram.errors import UserAlreadyParticipant, InviteHashExpired, UsernameNotOccupied, ChannelPrivate, UsernameInvalid
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import time
import os
import threading
import json

with open('config.json', 'r') as f: DATA = json.load(f)
def getenv(var): return os.environ.get(var) or DATA.get(var, None)

# Watch configurations file
WATCH_FILE = 'watch_config.json'

def load_watch_config():
    if os.path.exists(WATCH_FILE):
        with open(WATCH_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_watch_config(config):
    with open(WATCH_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

bot_token = getenv("TOKEN") 
api_hash = getenv("HASH") 
api_id = getenv("ID")
bot = Client("mybot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)

ss = getenv("STRING")
if ss is not None:
    acc = Client("myacc" ,api_id=api_id, api_hash=api_hash, session_string=ss)
    acc.start()
else: acc = None

# download status
def downstatus(statusfile,message):
    while True:
        if os.path.exists(statusfile):
            break

    time.sleep(3)      
    while os.path.exists(statusfile):
        with open(statusfile,"r") as downread:
            txt = downread.read()
        try:
            bot.edit_message_text(message.chat.id, message.id, f"__⬇️ 已下载__ : **{txt}**")
            time.sleep(10)
        except:
            time.sleep(5)


# upload status
def upstatus(statusfile,message):
    while True:
        if os.path.exists(statusfile):
            break

    time.sleep(3)      
    while os.path.exists(statusfile):
        with open(statusfile,"r") as upread:
            txt = upread.read()
        try:
            bot.edit_message_text(message.chat.id, message.id, f"__⬆️ 已上传__ : **{txt}**")
            time.sleep(10)
        except:
            time.sleep(5)


# progress writter
def progress(current, total, message, type):
    with open(f'{message.id}{type}status.txt',"w") as fileup:
        fileup.write(f"{current * 100 / total:.1f}%")


# start command
@bot.on_message(filters.command(["start"]))
def send_start(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
    bot.send_message(message.chat.id, f"__👋 你好 **{message.from_user.mention}**，我是受限内容保存机器人，我可以通过帖子链接发送受限内容给你__\n\n{USAGE}",
    reply_markup=InlineKeyboardMarkup([[ InlineKeyboardButton("🌐 源代码", url="https://github.com/bipinkrish/Save-Restricted-Bot")]]), reply_to_message_id=message.id)

# help command
@bot.on_message(filters.command(["help"]))
def send_help(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
    help_text = """**📖 命令帮助**

**基本命令：**
/start - 启动机器人并查看使用说明
/help - 显示此帮助信息
/watch - 监控频道/群组并自动转发消息

**消息转发功能：**
直接发送 Telegram 消息链接，机器人会帮你获取内容

**监控功能 (/watch)：**
/watch list - 查看所有监控任务
/watch add <来源频道> <目标位置> [whitelist:关键词1,关键词2] [blacklist:关键词3,关键词4] [preserve_source:true/false] - 添加监控任务
/watch remove <任务ID> - 删除监控任务

**关键词过滤：**
• whitelist（白名单）- 只转发包含这些关键词的消息
• blacklist（黑名单）- 不转发包含这些关键词的消息
• 关键词用逗号分隔，不区分大小写

**转发选项：**
• preserve_source（保留转发来源）- true 保留原始转发来源信息，false 不保留（默认：false）

**示例：**
• `/watch add @source_channel @dest_channel` - 将来源频道消息转发到目标频道
• `/watch add @source_channel me` - 将消息保存到个人收藏
• `/watch add @source me whitelist:重要,紧急` - 只转发包含"重要"或"紧急"的消息
• `/watch add @source me blacklist:广告,推广` - 不转发包含"广告"或"推广"的消息
• `/watch add @source me whitelist:新闻 blacklist:娱乐` - 转发包含"新闻"但不包含"娱乐"的消息
• `/watch add @source me preserve_source:true` - 转发时保留原始来源信息
• `/watch list` - 查看所有活动的监控任务
• `/watch remove 1` - 删除第1个监控任务

{USAGE}
"""
    bot.send_message(message.chat.id, help_text, reply_to_message_id=message.id)

# watch command
@bot.on_message(filters.command(["watch"]))
def watch_command(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
    if acc is None:
        bot.send_message(message.chat.id, "**❌ 需要配置 String Session 才能使用监控功能**", reply_to_message_id=message.id)
        return
    
    text = message.text.strip()
    parts = text.split(maxsplit=2)
    
    if len(parts) == 1 or (len(parts) == 2 and parts[1].lower() == "list"):
        watch_config = load_watch_config()
        user_id = str(message.from_user.id)
        
        if user_id not in watch_config or not watch_config[user_id]:
            bot.send_message(message.chat.id, "**📋 你还没有设置任何监控任务**\n\n使用 `/watch add <来源> <目标>` 来添加监控", reply_to_message_id=message.id)
            return
        
        result = "**📋 你的监控任务列表：**\n\n"
        for idx, (source, watch_data) in enumerate(watch_config[user_id].items(), 1):
            if isinstance(watch_data, dict):
                dest = watch_data.get("dest", "unknown")
                whitelist = watch_data.get("whitelist", [])
                blacklist = watch_data.get("blacklist", [])
                preserve_source = watch_data.get("preserve_forward_source", False)
                result += f"{idx}. `{source}` ➡️ `{dest}`\n"
                if whitelist:
                    result += f"   白名单: `{', '.join(whitelist)}`\n"
                if blacklist:
                    result += f"   黑名单: `{', '.join(blacklist)}`\n"
                if preserve_source:
                    result += f"   保留转发来源: `是`\n"
            else:
                result += f"{idx}. `{source}` ➡️ `{watch_data}`\n"
        
        result += f"\n**总计：** {len(watch_config[user_id])} 个监控任务"
        bot.send_message(message.chat.id, result, reply_to_message_id=message.id)
    
    elif len(parts) >= 2 and parts[1].lower() == "add":
        if len(parts) < 3:
            bot.send_message(message.chat.id, "**❌ 用法错误**\n\n正确格式：`/watch add <来源频道> <目标位置> [whitelist:关键词1,关键词2] [blacklist:关键词3,关键词4] [preserve_source:true/false]`\n\n示例：\n• `/watch add @channel @dest`\n• `/watch add @channel me whitelist:重要,紧急`\n• `/watch add @channel me blacklist:广告,垃圾`\n• `/watch add @channel me preserve_source:true`", reply_to_message_id=message.id)
            return
        
        args = parts[2].split()
        if len(args) < 2:
            bot.send_message(message.chat.id, "**❌ 用法错误**\n\n需要指定来源和目标\n\n示例：`/watch add @source_channel @dest_channel`", reply_to_message_id=message.id)
            return
        
        source_chat = args[0].strip()
        dest_chat = args[1].strip()
        user_id = str(message.from_user.id)
        
        whitelist = []
        blacklist = []
        preserve_forward_source = False
        
        for arg in args[2:]:
            if arg.startswith('whitelist:'):
                whitelist = [kw.strip() for kw in arg[10:].split(',') if kw.strip()]
            elif arg.startswith('blacklist:'):
                blacklist = [kw.strip() for kw in arg[10:].split(',') if kw.strip()]
            elif arg.startswith('preserve_source:'):
                preserve_forward_source = arg[16:].lower() in ['true', '1', 'yes']
        
        try:
            if source_chat.startswith('@'):
                source_info = acc.get_chat(source_chat)
                source_id = str(source_info.id)
            else:
                source_id = source_chat
                source_info = acc.get_chat(int(source_chat))
            
            if dest_chat.lower() == "me":
                dest_id = "me"
            elif dest_chat.startswith('@'):
                dest_info = acc.get_chat(dest_chat)
                dest_id = str(dest_info.id)
            else:
                dest_id = dest_chat
                dest_info = acc.get_chat(int(dest_chat))
            
            watch_config = load_watch_config()
            
            if user_id not in watch_config:
                watch_config[user_id] = {}
            
            if source_id in watch_config[user_id]:
                bot.send_message(message.chat.id, f"**⚠️ 该来源频道已经在监控中**\n\n来源：`{source_chat}`", reply_to_message_id=message.id)
                return
            
            watch_config[user_id][source_id] = {
                "dest": dest_id,
                "whitelist": whitelist,
                "blacklist": blacklist,
                "preserve_forward_source": preserve_forward_source
            }
            save_watch_config(watch_config)
            
            result_msg = f"**✅ 监控任务添加成功！**\n\n来源：`{source_chat}`\n目标：`{dest_chat}`"
            if whitelist:
                result_msg += f"\n白名单关键词：`{', '.join(whitelist)}`"
            if blacklist:
                result_msg += f"\n黑名单关键词：`{', '.join(blacklist)}`"
            if preserve_forward_source:
                result_msg += f"\n保留转发来源：`是`"
            result_msg += "\n\n从现在开始，该频道的新消息将自动转发"
            
            bot.send_message(message.chat.id, result_msg, reply_to_message_id=message.id)
        
        except ChannelPrivate:
            bot.send_message(message.chat.id, "**❌ 无法访问该频道**\n\n请确保：\n1. 账号已加入该频道\n2. 频道ID/用户名正确", reply_to_message_id=message.id)
        except UsernameInvalid:
            bot.send_message(message.chat.id, "**❌ 频道用户名无效**\n\n请检查用户名是否正确", reply_to_message_id=message.id)
        except Exception as e:
            bot.send_message(message.chat.id, f"**❌ 错误：** `{str(e)}`", reply_to_message_id=message.id)
    
    elif len(parts) >= 2 and parts[1].lower() == "remove":
        if len(parts) < 3:
            bot.send_message(message.chat.id, "**❌ 用法错误**\n\n正确格式：`/watch remove <任务编号>`\n\n使用 `/watch list` 查看任务编号", reply_to_message_id=message.id)
            return
        
        try:
            task_id = int(parts[2].strip())
        except ValueError:
            bot.send_message(message.chat.id, "**❌ 任务编号必须是数字**", reply_to_message_id=message.id)
            return
        
        watch_config = load_watch_config()
        user_id = str(message.from_user.id)
        
        if user_id not in watch_config or not watch_config[user_id]:
            bot.send_message(message.chat.id, "**❌ 你没有任何监控任务**", reply_to_message_id=message.id)
            return
        
        if task_id < 1 or task_id > len(watch_config[user_id]):
            bot.send_message(message.chat.id, f"**❌ 任务编号无效**\n\n请输入 1 到 {len(watch_config[user_id])} 之间的数字", reply_to_message_id=message.id)
            return
        
        source_id = list(watch_config[user_id].keys())[task_id - 1]
        watch_data = watch_config[user_id][source_id]
        
        if isinstance(watch_data, dict):
            dest_id = watch_data.get("dest", "unknown")
        else:
            dest_id = watch_data
        
        del watch_config[user_id][source_id]
        
        if not watch_config[user_id]:
            del watch_config[user_id]
        
        save_watch_config(watch_config)
        
        bot.send_message(message.chat.id, f"**✅ 监控任务已删除**\n\n来源：`{source_id}`\n目标：`{dest_id}`", reply_to_message_id=message.id)
    
    else:
        bot.send_message(message.chat.id, "**❌ 未知命令**\n\n可用命令：\n• `/watch list` - 查看监控列表\n• `/watch add <来源> <目标>` - 添加监控\n• `/watch remove <编号>` - 删除监控", reply_to_message_id=message.id)


@bot.on_message(filters.text)
def save(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
    print(message.text)

    # joining chats
    if "https://t.me/+" in message.text or "https://t.me/joinchat/" in message.text:

        if acc is None:
            bot.send_message(message.chat.id,f"**❌ 未设置 String Session**", reply_to_message_id=message.id)
            return

        try:
            try: acc.join_chat(message.text)
            except Exception as e: 
                bot.send_message(message.chat.id,f"**❌ 错误** : __{e}__", reply_to_message_id=message.id)
                return
            bot.send_message(message.chat.id,"**✅ 已加入频道**", reply_to_message_id=message.id)
        except UserAlreadyParticipant:
            bot.send_message(message.chat.id,"**✅ 已经加入该频道**", reply_to_message_id=message.id)
        except InviteHashExpired:
            bot.send_message(message.chat.id,"**❌ 无效链接**", reply_to_message_id=message.id)

    # getting message
    elif "https://t.me/" in message.text:

        datas = message.text.split("/")
        temp = datas[-1].replace("?single","").split("-")
        fromID = int(temp[0].strip())
        try: toID = int(temp[1].strip())
        except: toID = fromID

        for msgid in range(fromID, toID+1):

            # private
            if "https://t.me/c/" in message.text:
                chatid = int("-100" + datas[4])
                
                if acc is None:
                    bot.send_message(message.chat.id,f"**❌ 未设置 String Session**", reply_to_message_id=message.id)
                    return
                
                try: handle_private(message,chatid,msgid)
                except Exception as e: pass  # Silently ignore forwarding failures
            
            # bot
            elif "https://t.me/b/" in message.text:
                username = datas[4]
                
                if acc is None:
                    bot.send_message(message.chat.id,f"**❌ 未设置 String Session**", reply_to_message_id=message.id)
                    return
                try: handle_private(message,username,msgid)
                except Exception as e: pass  # Silently ignore forwarding failures

            # public
            else:
                username = datas[3]

                try: msg  = bot.get_messages(username,msgid)
                except UsernameNotOccupied: 
                    bot.send_message(message.chat.id,f"**❌ 该用户名未被占用**", reply_to_message_id=message.id)
                    return
                try:
                    if '?single' not in message.text:
                        bot.copy_message(message.chat.id, msg.chat.id, msg.id)
                    else:
                        bot.copy_media_group(message.chat.id, msg.chat.id, msg.id)
                except:
                    if acc is None:
                        bot.send_message(message.chat.id,f"**❌ 未设置 String Session**", reply_to_message_id=message.id)
                        return
                    try: handle_private(message,username,msgid)
                    except Exception as e: pass  # Silently ignore forwarding failures

            # wait time
            time.sleep(3)


# handle private
def handle_private(message: pyrogram.types.messages_and_media.message.Message, chatid: int, msgid: int):
        msg: pyrogram.types.messages_and_media.message.Message = acc.get_messages(chatid,msgid)
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
            bot.send_voice(message.chat.id, file, caption=msg.caption, thumb=thumb, caption_entities=msg.caption_entities, progress=progress, progress_args=[message,"up"])

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


# get the type of message
def get_message_type(msg: pyrogram.types.messages_and_media.message.Message):
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

# Auto-forward handler for watched channels
if acc is not None:
    @acc.on_message(filters.channel | filters.group)
    def auto_forward(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
        try:
            watch_config = load_watch_config()
            source_chat_id = str(message.chat.id)
            
            for user_id, watches in watch_config.items():
                if source_chat_id in watches:
                    watch_data = watches[source_chat_id]
                    
                    if isinstance(watch_data, dict):
                        dest_chat_id = watch_data.get("dest")
                        whitelist = watch_data.get("whitelist", [])
                        blacklist = watch_data.get("blacklist", [])
                        preserve_forward_source = watch_data.get("preserve_forward_source", False)
                    else:
                        dest_chat_id = watch_data
                        whitelist = []
                        blacklist = []
                        preserve_forward_source = False
                    
                    message_text = message.text or message.caption or ""
                    
                    if whitelist:
                        if not any(keyword.lower() in message_text.lower() for keyword in whitelist):
                            continue
                    
                    if blacklist:
                        if any(keyword.lower() in message_text.lower() for keyword in blacklist):
                            continue
                    
                    try:
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
                    except Exception as e:
                        pass
        except Exception as e:
            print(f"Error in auto_forward: {e}")


# infinty polling
bot.run()
if acc is not None:
    acc.stop()
