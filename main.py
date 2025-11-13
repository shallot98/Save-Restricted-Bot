import pyrogram
from pyrogram import Client, filters
from pyrogram.errors import UserAlreadyParticipant, InviteHashExpired, UsernameNotOccupied, ChannelPrivate, UsernameInvalid
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

import time
import os
import threading
import json
import re
from datetime import datetime
from database import add_note

# 数据目录 - 独立存储，防止更新时丢失
DEFAULT_DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), 'data'))
DATA_DIR = os.environ.get('DATA_DIR', DEFAULT_DATA_DIR)
CONFIG_DIR = os.path.join(DATA_DIR, 'config')
MEDIA_DIR = os.path.join(DATA_DIR, 'media')
CONFIG_FILE = os.path.join(CONFIG_DIR, 'config.json')
WATCH_FILE = os.path.join(CONFIG_DIR, 'watch_config.json')

# 确保配置和媒体目录存在
os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(MEDIA_DIR, exist_ok=True)

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    config_data = {}
    for key in ["TOKEN", "HASH", "ID", "STRING", "OWNER_ID"]:
        value = os.environ.get(key)
        if value:
            config_data[key] = value
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config_data, f, indent=4, ensure_ascii=False)
    return config_data

DATA = load_config()

def getenv(var):
    return os.environ.get(var) or DATA.get(var)

# User state management for multi-step interactions
user_states = {}

def load_watch_config():
    if os.path.exists(WATCH_FILE):
        try:
            with open(WATCH_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    with open(WATCH_FILE, 'w', encoding='utf-8') as f:
        json.dump({}, f, indent=4, ensure_ascii=False)
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
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 监控管理", callback_data="menu_watch")],
        [InlineKeyboardButton("❓ 帮助说明", callback_data="menu_help")],
        [InlineKeyboardButton("🌐 源代码", url="https://github.com/bipinkrish/Save-Restricted-Bot")]
    ])
    
    welcome_text = f"👋 你好 **{message.from_user.mention}**！\n\n"
    welcome_text += "我是受限内容保存机器人，可以帮你：\n\n"
    welcome_text += "📥 **转发消息** - 直接发送 Telegram 链接\n"
    welcome_text += "👁 **监控频道/群组** - 自动转发新消息\n"
    welcome_text += "🔍 **智能过滤** - 关键词、正则表达式过滤\n"
    welcome_text += "🎯 **提取模式** - 提取特定内容转发\n\n"
    welcome_text += "点击下方按钮开始使用 👇"
    
    bot.send_message(message.chat.id, welcome_text, reply_markup=keyboard, reply_to_message_id=message.id)

# help command
@bot.on_message(filters.command(["help"]))
def send_help(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 监控管理", callback_data="menu_watch")],
        [InlineKeyboardButton("🏠 返回主菜单", callback_data="menu_main")]
    ])
    
    help_text = """**📖 使用帮助**

**📥 转发消息**
直接发送 Telegram 消息链接即可转发内容

**📋 监控功能**
• 点击"监控管理"按钮设置自动转发
• 支持监控频道和群组
• 支持关键词过滤（白名单/黑名单）
• 支持正则表达式过滤
• 支持提取模式（正则提取特定内容）
• 可选择是否保留转发来源
• 可随时编辑监控设置

**🔗 链接格式**

公开频道/群组：
`https://t.me/username/123`

私有频道/群组（需要先加入）：
`https://t.me/c/123456789/123`

批量下载（范围）：
`https://t.me/username/100-120`

机器人消息：
`https://t.me/b/botusername/123`

**💡 提示**
• 私有频道需要配置 String Session
• 可以使用"me"作为目标保存到收藏夹
• 关键词过滤不区分大小写
• 正则表达式支持完整的 Python re 语法
• 提取模式会将匹配的内容单独发送
• 所有操作都可通过按钮完成，无需记忆复杂命令
"""
    bot.send_message(message.chat.id, help_text, reply_markup=keyboard, reply_to_message_id=message.id)

# watch command - now with inline keyboard
@bot.on_message(filters.command(["watch"]))
def watch_command(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
    if acc is None:
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 返回主菜单", callback_data="menu_main")]])
        bot.send_message(message.chat.id, "**❌ 需要配置 String Session 才能使用监控功能**", reply_markup=keyboard, reply_to_message_id=message.id)
        return
    
    show_watch_menu(message.chat.id, message.id)

def show_watch_menu(chat_id, reply_to_message_id=None):
    watch_config = load_watch_config()
    user_id = str(chat_id)
    
    watch_count = len(watch_config.get(user_id, {}))
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ 添加监控", callback_data="watch_add_start")],
        [InlineKeyboardButton(f"📋 查看列表 ({watch_count})", callback_data="watch_list")],
        [InlineKeyboardButton("🗑 删除监控", callback_data="watch_remove_start")],
        [InlineKeyboardButton("🏠 返回主菜单", callback_data="menu_main")]
    ])
    
    text = "**📋 监控管理**\n\n"
    text += "选择操作：\n\n"
    text += "➕ **添加监控** - 设置新的自动转发任务\n"
    text += "📋 **查看列表** - 查看所有监控任务\n"
    text += "🗑 **删除监控** - 移除现有监控任务\n\n"
    text += f"当前监控任务数：**{watch_count}** 个"
    
    bot.send_message(chat_id, text, reply_markup=keyboard, reply_to_message_id=reply_to_message_id)

# Callback query handler
@bot.on_callback_query()
def callback_handler(client: pyrogram.client.Client, callback_query: CallbackQuery):
    data = callback_query.data
    chat_id = callback_query.message.chat.id
    message_id = callback_query.message.id
    user_id = str(callback_query.from_user.id)
    
    try:
        if data == "menu_main":
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 监控管理", callback_data="menu_watch")],
                [InlineKeyboardButton("❓ 帮助说明", callback_data="menu_help")],
                [InlineKeyboardButton("🌐 源代码", url="https://github.com/bipinkrish/Save-Restricted-Bot")]
            ])
            
            welcome_text = f"👋 你好 **{callback_query.from_user.mention}**！\n\n"
            welcome_text += "我是受限内容保存机器人，可以帮你：\n\n"
            welcome_text += "📥 **转发消息** - 直接发送 Telegram 链接\n"
            welcome_text += "👁 **监控频道/群组** - 自动转发新消息\n"
            welcome_text += "🔍 **智能过滤** - 关键词、正则表达式过滤\n"
            welcome_text += "🎯 **提取模式** - 提取特定内容转发\n\n"
            welcome_text += "点击下方按钮开始使用 👇"
            
            bot.edit_message_text(chat_id, message_id, welcome_text, reply_markup=keyboard)
            callback_query.answer()
        
        elif data == "menu_help":
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 监控管理", callback_data="menu_watch")],
                [InlineKeyboardButton("🏠 返回主菜单", callback_data="menu_main")]
            ])
            
            help_text = """**📖 使用帮助**

**📥 转发消息**
直接发送 Telegram 消息链接即可转发内容

**📋 监控功能**
• 点击"监控管理"按钮设置自动转发或记录
• 支持监控频道、群组和收藏夹
• 输入 `me` 可监控自己的收藏夹
• 支持关键词过滤（白名单/黑名单）
• 支持正则表达式过滤
• 支持提取模式（正则提取特定内容）
• 可选择是否保留转发来源
• 📝 支持记录模式（保存到网页笔记）
• 可随时编辑监控设置

**📝 记录模式**
• 将监控内容保存到网页而非转发
• 记录文字、图片和视频封面
• 包含时间戳信息
• 过滤规则和提取模式仍然生效
• 通过 Web 界面查看记录（端口 5000）
• 默认登录账号：admin/admin
• 搜索功能支持高亮显示

**🔗 链接格式**

公开频道/群组：
`https://t.me/username/123`

私有频道/群组（需要先加入）：
`https://t.me/c/123456789/123`

批量下载（范围）：
`https://t.me/username/100-120`

机器人消息：
`https://t.me/b/botusername/123`

**💡 提示**
• 私有频道需要配置 String Session
• 可以使用 `me` 监控收藏夹或作为目标
• 关键词过滤不区分大小写
• 正则表达式支持完整的 Python re 语法
• 提取模式会将匹配的内容单独发送
• 所有操作都可通过按钮完成，无需记忆复杂命令
• 机器人重启后会自动加载所有配置
"""
            bot.edit_message_text(chat_id, message_id, help_text, reply_markup=keyboard)
            callback_query.answer()
        
        elif data == "menu_watch":
            if acc is None:
                keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 返回主菜单", callback_data="menu_main")]])
                bot.edit_message_text(chat_id, message_id, "**❌ 需要配置 String Session 才能使用监控功能**", reply_markup=keyboard)
                callback_query.answer("❌ 需要配置 String Session", show_alert=True)
                return
            
            watch_config = load_watch_config()
            watch_count = len(watch_config.get(user_id, {}))
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ 添加监控", callback_data="watch_add_start")],
                [InlineKeyboardButton(f"📋 查看列表 ({watch_count})", callback_data="watch_list")],
                [InlineKeyboardButton("🗑 删除监控", callback_data="watch_remove_start")],
                [InlineKeyboardButton("🏠 返回主菜单", callback_data="menu_main")]
            ])
            
            text = "**📋 监控管理**\n\n"
            text += "选择操作：\n\n"
            text += "➕ **添加监控** - 设置新的自动转发任务\n"
            text += "📋 **查看列表** - 查看所有监控任务\n"
            text += "🗑 **删除监控** - 移除现有监控任务\n\n"
            text += f"当前监控任务数：**{watch_count}** 个"
            
            bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)
            callback_query.answer()
        
        elif data == "watch_add_start":
            user_states[user_id] = {"action": "add_source"}
            
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("❌ 取消", callback_data="menu_watch")]])
            
            text = "**➕ 添加监控任务**\n\n"
            text += "**步骤 1/2：** 请发送来源频道/群组\n\n"
            text += "可以发送：\n"
            text += "• 输入 `me` 监控自己的收藏夹\n"
            text += "• 频道/群组用户名（如 `@channel_name`）\n"
            text += "• 频道/群组ID（如 `-1001234567890`）\n"
            text += "• 转发一条来自该频道/群组的消息\n\n"
            text += "💡 机器人需要能够访问该频道/群组"
            
            bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)
            callback_query.answer()
        
        elif data == "watch_list":
            watch_config = load_watch_config()
            
            if user_id not in watch_config or not watch_config[user_id]:
                keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回", callback_data="menu_watch")]])
                bot.edit_message_text(chat_id, message_id, "**📋 监控列表**\n\n暂无监控任务\n\n点击\"添加监控\"开始设置", reply_markup=keyboard)
                callback_query.answer("暂无监控任务")
                return
            
            buttons = []
            for idx, (watch_key, watch_data) in enumerate(watch_config[user_id].items(), 1):
                if isinstance(watch_data, dict):
                    # New format with source|dest key
                    source = watch_data.get("source", watch_key.split("|")[0] if "|" in watch_key else watch_key)
                    dest = watch_data.get("dest", watch_key.split("|")[1] if "|" in watch_key else "unknown")
                else:
                    # Old format compatibility
                    source = watch_key
                    dest = watch_data
                
                # Handle None values
                if source is None:
                    source = "未知来源"
                if dest is None:
                    dest = "未知目标"
                
                # Truncate source and dest for button display
                source_display = source if len(source) <= 15 else source[:12] + "..."
                dest_display = dest if len(dest) <= 15 else dest[:12] + "..."
                
                buttons.append([InlineKeyboardButton(f"{idx}. {source_display} ➡️ {dest_display}", callback_data=f"watch_view_{idx}")])
            
            buttons.append([InlineKeyboardButton("🔙 返回", callback_data="menu_watch")])
            keyboard = InlineKeyboardMarkup(buttons)
            
            text = "**📋 监控任务列表**\n\n"
            text += f"共 **{len(watch_config[user_id])}** 个监控任务\n\n"
            text += "点击任务查看详情和编辑 👇"
            
            bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)
            callback_query.answer()
        
        elif data == "watch_remove_start":
            watch_config = load_watch_config()
            
            if user_id not in watch_config or not watch_config[user_id]:
                keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回", callback_data="menu_watch")]])
                bot.edit_message_text(chat_id, message_id, "**🗑 删除监控**\n\n暂无监控任务可删除", reply_markup=keyboard)
                callback_query.answer("暂无监控任务")
                return
            
            buttons = []
            for idx, (watch_key, watch_data) in enumerate(watch_config[user_id].items(), 1):
                if isinstance(watch_data, dict):
                    # New format with source|dest key
                    source = watch_data.get("source", watch_key.split("|")[0] if "|" in watch_key else watch_key)
                    dest = watch_data.get("dest", watch_key.split("|")[1] if "|" in watch_key else "unknown")
                else:
                    # Old format compatibility
                    source = watch_key
                    dest = watch_data
                
                # Handle None values
                if source is None:
                    source = "未知来源"
                if dest is None:
                    dest = "未知目标"
                
                buttons.append([InlineKeyboardButton(f"🗑 {idx}. {source} ➡️ {dest}", callback_data=f"watch_remove_{idx}")])
            
            buttons.append([InlineKeyboardButton("❌ 取消", callback_data="menu_watch")])
            keyboard = InlineKeyboardMarkup(buttons)
            
            text = "**🗑 删除监控**\n\n"
            text += "选择要删除的监控任务："
            
            bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)
            callback_query.answer()
        
        elif data.startswith("watch_view_"):
            task_id = int(data.split("_")[2])
            watch_config = load_watch_config()
            
            if user_id not in watch_config or not watch_config[user_id]:
                callback_query.answer("❌ 监控任务不存在", show_alert=True)
                return
            
            if task_id < 1 or task_id > len(watch_config[user_id]):
                callback_query.answer("❌ 任务编号无效", show_alert=True)
                return
            
            watch_key = list(watch_config[user_id].keys())[task_id - 1]
            watch_data = watch_config[user_id][watch_key]
            
            if isinstance(watch_data, dict):
                # New format with source|dest key
                source_id = watch_data.get("source", watch_key.split("|")[0] if "|" in watch_key else watch_key)
                dest = watch_data.get("dest", watch_key.split("|")[1] if "|" in watch_key else "unknown")
                whitelist = watch_data.get("whitelist", [])
                blacklist = watch_data.get("blacklist", [])
                whitelist_regex = watch_data.get("whitelist_regex", [])
                blacklist_regex = watch_data.get("blacklist_regex", [])
                preserve_source = watch_data.get("preserve_forward_source", False)
                forward_mode = watch_data.get("forward_mode", "full")
                extract_patterns = watch_data.get("extract_patterns", [])
                record_mode = watch_data.get("record_mode", False)
            else:
                # Old format compatibility
                source_id = watch_key
                dest = watch_data
                whitelist = []
                blacklist = []
                whitelist_regex = []
                blacklist_regex = []
                preserve_source = False
                forward_mode = "full"
                extract_patterns = []
                record_mode = False
            
            # Handle None values
            if source_id is None:
                source_id = "未知来源"
            if dest is None:
                dest = "未知目标"
            
            text = f"**📋 监控任务详情**\n\n"
            text += f"**来源：** `{source_id}`\n"
            
            if record_mode:
                text += f"**模式：** 📝 记录模式（保存到网页）\n\n"
            else:
                text += f"**目标：** `{dest}`\n\n"
                text += f"**转发模式：** {'🎯 提取模式' if forward_mode == 'extract' else '📦 完整转发'}\n"
                if preserve_source:
                    text += f"**保留来源：** ✅ 是\n"
                else:
                    text += f"**保留来源：** ❌ 否\n"
            
            text += "\n**过滤规则：**\n"
            if whitelist:
                text += f"🟢 关键词白名单: `{', '.join(whitelist)}`\n"
            if blacklist:
                text += f"🔴 关键词黑名单: `{', '.join(blacklist)}`\n"
            if whitelist_regex:
                text += f"🟢 正则白名单: `{', '.join(whitelist_regex)}`\n"
            if blacklist_regex:
                text += f"🔴 正则黑名单: `{', '.join(blacklist_regex)}`\n"
            if not (whitelist or blacklist or whitelist_regex or blacklist_regex):
                text += "⏭ 无过滤（转发所有消息）\n"
            
            if forward_mode == "extract" and extract_patterns:
                text += f"\n**提取规则：**\n"
                for pattern in extract_patterns:
                    text += f"• `{pattern}`\n"
            
            buttons = [[InlineKeyboardButton("✏️ 编辑过滤规则", callback_data=f"edit_filter_{task_id}")]]
            
            if not record_mode:
                buttons.append([InlineKeyboardButton("🔄 切换转发模式", callback_data=f"edit_mode_{task_id}")])
                buttons.append([InlineKeyboardButton("📤 切换保留来源", callback_data=f"edit_preserve_{task_id}")])
            
            buttons.append([InlineKeyboardButton("🗑 删除此监控", callback_data=f"watch_remove_{task_id}")])
            buttons.append([InlineKeyboardButton("🔙 返回列表", callback_data="watch_list")])
            
            keyboard = InlineKeyboardMarkup(buttons)
            
            bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)
            callback_query.answer()
        
        elif data.startswith("watch_remove_"):
            task_id = int(data.split("_")[2])
            watch_config = load_watch_config()
            
            if user_id not in watch_config or not watch_config[user_id]:
                callback_query.answer("❌ 监控任务不存在", show_alert=True)
                return
            
            if task_id < 1 or task_id > len(watch_config[user_id]):
                callback_query.answer("❌ 任务编号无效", show_alert=True)
                return
            
            watch_key = list(watch_config[user_id].keys())[task_id - 1]
            watch_data = watch_config[user_id][watch_key]
            
            if isinstance(watch_data, dict):
                # New format with source|dest key
                source_id = watch_data.get("source", watch_key.split("|")[0] if "|" in watch_key else watch_key)
                dest_id = watch_data.get("dest", watch_key.split("|")[1] if "|" in watch_key else "unknown")
            else:
                # Old format compatibility
                source_id = watch_key
                dest_id = watch_data
            
            # Handle None values
            if source_id is None:
                source_id = "未知来源"
            if dest_id is None:
                dest_id = "未知目标"
            
            del watch_config[user_id][watch_key]
            
            if not watch_config[user_id]:
                del watch_config[user_id]
            
            save_watch_config(watch_config)
            
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回监控管理", callback_data="menu_watch")]])
            text = f"**✅ 监控任务已删除**\n\n来源：`{source_id}`\n目标：`{dest_id}`"
            
            bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)
            callback_query.answer("✅ 删除成功")
        
        elif data.startswith("set_dest_"):
            dest_choice = data.split("_")[2]
            
            if user_id not in user_states or "source_id" not in user_states[user_id]:
                callback_query.answer("❌ 会话已过期，请重新开始", show_alert=True)
                return
            
            if dest_choice == "me":
                user_states[user_id]["dest_id"] = "me"
                user_states[user_id]["dest_name"] = "个人收藏"
            
            show_filter_options(chat_id, message_id, user_id)
            callback_query.answer()
        
        elif data == "mode_single":
            if user_id not in user_states or "source_id" not in user_states[user_id]:
                callback_query.answer("❌ 会话已过期，请重新开始", show_alert=True)
                return
            
            user_states[user_id]["dest_id"] = None
            user_states[user_id]["dest_name"] = "记录模式"
            user_states[user_id]["record_mode"] = True
            
            show_filter_options_single(chat_id, message_id, user_id)
            callback_query.answer()
        
        elif data == "mode_forward":
            if user_id not in user_states or "source_id" not in user_states[user_id]:
                callback_query.answer("❌ 会话已过期，请重新开始", show_alert=True)
                return
            
            user_states[user_id]["action"] = "choose_dest"
            user_states[user_id]["record_mode"] = False
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("💾 保存到收藏夹", callback_data="set_dest_me")],
                [InlineKeyboardButton("📤 自定义目标", callback_data="dest_custom")],
                [InlineKeyboardButton("❌ 取消", callback_data="menu_watch")]
            ])
            
            source_name = user_states[user_id].get("source_name", "未知")
            
            text = "**➕ 添加监控任务**\n\n"
            text += f"✅ 来源已设置：`{source_name}`\n\n"
            text += "**步骤 3：** 选择转发目标\n\n"
            text += "💾 **保存到收藏夹** - 转发到你的个人收藏\n"
            text += "📤 **自定义目标** - 转发到其他频道/群组"
            
            bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)
            callback_query.answer()
        
        elif data == "dest_custom":
            user_states[user_id]["action"] = "add_dest"
            
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("❌ 取消", callback_data="menu_watch")]])
            
            text = "**➕ 添加监控任务**\n\n"
            text += "**步骤 3：** 请发送目标频道/群组\n\n"
            text += "可以发送：\n"
            text += "• 频道/群组用户名（如 `@channel_name`）\n"
            text += "• 频道/群组ID（如 `-1001234567890`）\n"
            text += "• 转发一条来自该频道/群组的消息\n\n"
            text += "💡 机器人需要有发送消息的权限"
            
            bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)
            callback_query.answer()
        
        elif data == "filter_none":
            if user_id not in user_states:
                callback_query.answer("❌ 会话已过期", show_alert=True)
                return
            
            user_states[user_id]["whitelist"] = []
            user_states[user_id]["blacklist"] = []
            user_states[user_id]["whitelist_regex"] = []
            user_states[user_id]["blacklist_regex"] = []
            show_preserve_source_options(chat_id, message_id, user_id)
            callback_query.answer()
        
        elif data == "filter_none_single":
            if user_id not in user_states:
                callback_query.answer("❌ 会话已过期", show_alert=True)
                return
            
            user_states[user_id]["whitelist"] = []
            user_states[user_id]["blacklist"] = []
            user_states[user_id]["whitelist_regex"] = []
            user_states[user_id]["blacklist_regex"] = []
            
            msg = bot.send_message(chat_id, "⏳ 正在完成设置...")
            bot.delete_messages(chat_id, [message_id])
            complete_watch_setup_single(msg.chat.id, msg.id, user_id, [], [], [], [])
            callback_query.answer()
        
        elif data == "filter_regex_whitelist":
            user_states[user_id]["action"] = "add_regex_whitelist"
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⏭ 跳过", callback_data="skip_regex_whitelist")],
                [InlineKeyboardButton("❌ 取消", callback_data="menu_watch")]
            ])
            
            text = "**➕ 添加监控任务**\n\n"
            text += "**步骤 3：设置正则白名单**\n\n"
            text += "请发送正则表达式，用逗号分隔\n\n"
            text += "示例：`https?://[^\\s]+,\\d{6,}`\n\n"
            text += "💡 只有匹配这些正则的消息才会被转发"
            
            bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)
            callback_query.answer()
        
        elif data == "filter_regex_blacklist":
            user_states[user_id]["action"] = "add_regex_blacklist"
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⏭ 跳过", callback_data="skip_regex_blacklist")],
                [InlineKeyboardButton("❌ 取消", callback_data="menu_watch")]
            ])
            
            text = "**➕ 添加监控任务**\n\n"
            text += "**步骤 3：设置正则黑名单**\n\n"
            text += "请发送正则表达式，用逗号分隔\n\n"
            text += "示例：`广告|推广|垃圾`\n\n"
            text += "💡 匹配这些正则的消息不会被转发"
            
            bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)
            callback_query.answer()
        
        elif data == "skip_regex_whitelist":
            if user_id in user_states:
                user_states[user_id]["whitelist_regex"] = []
                msg = bot.send_message(chat_id, "⏳ 继续设置...")
                show_filter_options(chat_id, msg.id, user_id)
                bot.delete_messages(chat_id, [message_id])
                callback_query.answer("已跳过正则白名单")
        
        elif data == "skip_regex_blacklist":
            if user_id in user_states:
                user_states[user_id]["blacklist_regex"] = []
                msg = bot.send_message(chat_id, "⏳ 继续设置...")
                show_filter_options(chat_id, msg.id, user_id)
                bot.delete_messages(chat_id, [message_id])
                callback_query.answer("已跳过正则黑名单")
        
        elif data == "filter_whitelist":
            user_states[user_id]["action"] = "add_whitelist"
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⏭ 跳过", callback_data="skip_whitelist")],
                [InlineKeyboardButton("❌ 取消", callback_data="menu_watch")]
            ])
            
            text = "**➕ 添加监控任务**\n\n"
            text += "**步骤 3：设置白名单**\n\n"
            text += "请发送白名单关键词，用逗号分隔\n\n"
            text += "示例：`重要,紧急,通知`\n\n"
            text += "💡 只有包含这些关键词的消息才会被转发"
            
            bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)
            callback_query.answer()
        
        elif data == "filter_blacklist":
            user_states[user_id]["action"] = "add_blacklist"
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⏭ 跳过", callback_data="skip_blacklist")],
                [InlineKeyboardButton("❌ 取消", callback_data="menu_watch")]
            ])
            
            text = "**➕ 添加监控任务**\n\n"
            text += "**步骤 3：设置黑名单**\n\n"
            text += "请发送黑名单关键词，用逗号分隔\n\n"
            text += "示例：`广告,推广,垃圾`\n\n"
            text += "💡 包含这些关键词的消息不会被转发"
            
            bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)
            callback_query.answer()
        
        elif data == "skip_whitelist":
            if user_id in user_states:
                user_states[user_id]["whitelist"] = []
                msg = bot.send_message(chat_id, "⏳ 继续设置...")
                show_filter_options(chat_id, msg.id, user_id)
                bot.delete_messages(chat_id, [message_id])
                callback_query.answer("已跳过关键词白名单")
        
        elif data == "skip_blacklist":
            if user_id in user_states:
                user_states[user_id]["blacklist"] = []
                msg = bot.send_message(chat_id, "⏳ 继续设置...")
                show_filter_options(chat_id, msg.id, user_id)
                bot.delete_messages(chat_id, [message_id])
                callback_query.answer("已跳过关键词黑名单")
        
        elif data.startswith("preserve_"):
            preserve = data.split("_")[1] == "yes"
            
            if user_id not in user_states:
                callback_query.answer("❌ 会话已过期", show_alert=True)
                return
            
            whitelist = user_states[user_id].get("whitelist", [])
            blacklist = user_states[user_id].get("blacklist", [])
            whitelist_regex = user_states[user_id].get("whitelist_regex", [])
            blacklist_regex = user_states[user_id].get("blacklist_regex", [])
            
            # Show forward mode selection
            show_forward_mode_options(chat_id, message_id, user_id, whitelist, blacklist, whitelist_regex, blacklist_regex, preserve)
            callback_query.answer()
        
        elif data.startswith("edit_preserve_"):
            task_id = int(data.split("_")[2])
            watch_config = load_watch_config()
            
            if user_id not in watch_config or not watch_config[user_id]:
                callback_query.answer("❌ 监控任务不存在", show_alert=True)
                return
            
            if task_id < 1 or task_id > len(watch_config[user_id]):
                callback_query.answer("❌ 任务编号无效", show_alert=True)
                return
            
            watch_key = list(watch_config[user_id].keys())[task_id - 1]
            
            if isinstance(watch_config[user_id][watch_key], dict):
                current_preserve = watch_config[user_id][watch_key].get("preserve_forward_source", False)
                watch_config[user_id][watch_key]["preserve_forward_source"] = not current_preserve
            else:
                # Old format compatibility - convert to new format
                old_dest = watch_config[user_id][watch_key]
                source_id = watch_key
                watch_config[user_id][watch_key] = {
                    "source": source_id,
                    "dest": old_dest,
                    "whitelist": [],
                    "blacklist": [],
                    "preserve_forward_source": True
                }
            
            save_watch_config(watch_config)
            
            # Refresh the view
            callback_query.data = f"watch_view_{task_id}"
            callback_handler(client, callback_query)
            return
        
        elif data.startswith("edit_mode_"):
            task_id = int(data.split("_")[2])
            watch_config = load_watch_config()
            
            if user_id not in watch_config or not watch_config[user_id]:
                callback_query.answer("❌ 监控任务不存在", show_alert=True)
                return
            
            if task_id < 1 or task_id > len(watch_config[user_id]):
                callback_query.answer("❌ 任务编号无效", show_alert=True)
                return
            
            watch_key = list(watch_config[user_id].keys())[task_id - 1]
            
            if isinstance(watch_config[user_id][watch_key], dict):
                current_mode = watch_config[user_id][watch_key].get("forward_mode", "full")
            else:
                current_mode = "full"
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📦 完整转发", callback_data=f"setmode_full_{task_id}")],
                [InlineKeyboardButton("🎯 提取模式", callback_data=f"setmode_extract_{task_id}")],
                [InlineKeyboardButton("🔙 返回", callback_data=f"watch_view_{task_id}")]
            ])
            
            text = f"**🔄 选择转发模式**\n\n"
            text += f"当前模式：**{'🎯 提取模式' if current_mode == 'extract' else '📦 完整转发'}**\n\n"
            text += "📦 **完整转发** - 转发整条消息\n"
            text += "🎯 **提取模式** - 使用正则提取特定内容后转发"
            
            bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)
            callback_query.answer()
        
        elif data.startswith("setmode_"):
            parts = data.split("_")
            mode = parts[1]
            task_id = int(parts[2])
            
            watch_config = load_watch_config()
            
            if user_id not in watch_config or not watch_config[user_id]:
                callback_query.answer("❌ 监控任务不存在", show_alert=True)
                return
            
            if task_id < 1 or task_id > len(watch_config[user_id]):
                callback_query.answer("❌ 任务编号无效", show_alert=True)
                return
            
            watch_key = list(watch_config[user_id].keys())[task_id - 1]
            
            if isinstance(watch_config[user_id][watch_key], dict):
                watch_config[user_id][watch_key]["forward_mode"] = mode
                if mode == "extract" and not watch_config[user_id][watch_key].get("extract_patterns"):
                    # Extract source_id for user_states
                    source_id = watch_config[user_id][watch_key].get("source", watch_key.split("|")[0] if "|" in watch_key else watch_key)
                    
                    user_states[user_id] = {
                        "action": "edit_extract_patterns",
                        "task_id": task_id,
                        "watch_key": watch_key
                    }
                    
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("❌ 取消", callback_data=f"watch_view_{task_id}")]
                    ])
                    
                    text = "**🎯 设置提取规则**\n\n"
                    text += "请发送提取用的正则表达式，用逗号分隔\n\n"
                    text += "示例：`https?://[^\\s]+,\\d{6,}`\n\n"
                    text += "💡 消息匹配过滤规则后，将使用这些正则提取内容并转发"
                    
                    bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)
                    callback_query.answer("请输入提取规则")
                    save_watch_config(watch_config)
                    return
            else:
                # Old format compatibility - convert to new format
                old_dest = watch_config[user_id][watch_key]
                source_id = watch_key
                watch_config[user_id][watch_key] = {
                    "source": source_id,
                    "dest": old_dest,
                    "whitelist": [],
                    "blacklist": [],
                    "preserve_forward_source": False,
                    "forward_mode": mode,
                    "extract_patterns": []
                }
            
            save_watch_config(watch_config)
            
            # Refresh the view
            callback_query.data = f"watch_view_{task_id}"
            callback_handler(client, callback_query)
            return
        
        elif data.startswith("edit_filter_"):
            task_id = int(data.split("_")[2])
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🟢 修改关键词白名单", callback_data=f"editf_kw_white_{task_id}")],
                [InlineKeyboardButton("🔴 修改关键词黑名单", callback_data=f"editf_kw_black_{task_id}")],
                [InlineKeyboardButton("🟢 修改正则白名单", callback_data=f"editf_re_white_{task_id}")],
                [InlineKeyboardButton("🔴 修改正则黑名单", callback_data=f"editf_re_black_{task_id}")],
                [InlineKeyboardButton("🎯 修改提取规则", callback_data=f"editf_extract_{task_id}")],
                [InlineKeyboardButton("🔙 返回", callback_data=f"watch_view_{task_id}")]
            ])
            
            text = "**✏️ 编辑过滤规则**\n\n"
            text += "选择要修改的规则：\n\n"
            text += "🟢 **关键词白名单** - 包含关键词才转发\n"
            text += "🔴 **关键词黑名单** - 包含关键词不转发\n"
            text += "🟢 **正则白名单** - 匹配正则才转发\n"
            text += "🔴 **正则黑名单** - 匹配正则不转发\n"
            text += "🎯 **提取规则** - 提取模式的正则表达式"
            
            bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)
            callback_query.answer()
        
        elif data.startswith("editf_"):
            parts = data.split("_")
            filter_type = parts[1]
            color = parts[2]
            task_id = int(parts[3])
            
            user_states[user_id] = {
                "action": f"edit_filter_{filter_type}_{color}",
                "task_id": task_id
            }
            
            watch_config = load_watch_config()
            watch_key = list(watch_config[user_id].keys())[task_id - 1]
            user_states[user_id]["watch_key"] = watch_key
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🗑 清空", callback_data=f"clear_filter_{filter_type}_{color}_{task_id}")],
                [InlineKeyboardButton("❌ 取消", callback_data=f"watch_view_{task_id}")]
            ])
            
            if filter_type == "kw":
                filter_name = "关键词白名单" if color == "white" else "关键词黑名单"
                example = "重要,紧急,通知" if color == "white" else "广告,推广,垃圾"
            elif filter_type == "re":
                filter_name = "正则白名单" if color == "white" else "正则黑名单"
                example = "https?://[^\\s]+,\\d{6,}" if color == "white" else "广告|推广"
            else:  # extract
                filter_name = "提取规则"
                example = "https?://[^\\s]+,\\d{6,}"
            
            text = f"**✏️ 修改{filter_name}**\n\n"
            text += f"请发送新的规则，用逗号分隔\n\n"
            text += f"示例：`{example}`\n\n"
            text += "💡 发送新规则将覆盖原有规则\n"
            text += "💡 点击\"清空\"可删除所有规则"
            
            bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)
            callback_query.answer("请输入新规则")
        
        elif data.startswith("clear_filter_"):
            parts = data.split("_")
            filter_type = parts[2]
            color = parts[3]
            task_id = int(parts[4])
            
            watch_config = load_watch_config()
            
            if user_id not in watch_config or not watch_config[user_id]:
                callback_query.answer("❌ 监控任务不存在", show_alert=True)
                return
            
            if task_id < 1 or task_id > len(watch_config[user_id]):
                callback_query.answer("❌ 任务编号无效", show_alert=True)
                return
            
            watch_key = list(watch_config[user_id].keys())[task_id - 1]
            
            if isinstance(watch_config[user_id][watch_key], dict):
                if filter_type == "kw":
                    key = "whitelist" if color == "white" else "blacklist"
                elif filter_type == "re":
                    key = "whitelist_regex" if color == "white" else "blacklist_regex"
                else:  # extract
                    key = "extract_patterns"
                
                watch_config[user_id][watch_key][key] = []
                save_watch_config(watch_config)
                
                callback_query.answer("✅ 已清空")
            
            # Refresh the view
            callback_query.data = f"watch_view_{task_id}"
            callback_handler(client, callback_query)
            return
        
        elif data.startswith("fwdmode_"):
            mode = data.split("_")[1]
            
            if user_id not in user_states:
                callback_query.answer("❌ 会话已过期", show_alert=True)
                return
            
            if mode == "extract":
                user_states[user_id]["action"] = "add_extract_patterns"
                
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("❌ 取消", callback_data="menu_watch")]
                ])
                
                text = "**➕ 添加监控任务**\n\n"
                text += "**设置提取规则**\n\n"
                text += "请发送提取用的正则表达式，用逗号分隔\n\n"
                text += "示例：`https?://[^\\s]+,\\d{6,}`\n\n"
                text += "💡 消息匹配过滤规则后，将使用这些正则提取内容并转发"
                
                bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)
                callback_query.answer("请输入提取规则")
            else:
                whitelist = user_states[user_id].get("whitelist", [])
                blacklist = user_states[user_id].get("blacklist", [])
                whitelist_regex = user_states[user_id].get("whitelist_regex", [])
                blacklist_regex = user_states[user_id].get("blacklist_regex", [])
                preserve_source = user_states[user_id].get("preserve_source", False)
                
                complete_watch_setup(chat_id, message_id, user_id, whitelist, blacklist, whitelist_regex, blacklist_regex, preserve_source, "full", [])
                callback_query.answer("✅ 监控已添加")
        
    except Exception as e:
        print(f"Callback error: {e}")
        callback_query.answer(f"❌ 错误: {str(e)}", show_alert=True)

def show_filter_options(chat_id, message_id, user_id):
    source_name = user_states[user_id].get("source_name", "未知")
    dest_name = user_states[user_id].get("dest_name", "未知")
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🟢 关键词白名单", callback_data="filter_whitelist")],
        [InlineKeyboardButton("🔴 关键词黑名单", callback_data="filter_blacklist")],
        [InlineKeyboardButton("🟢 正则白名单", callback_data="filter_regex_whitelist")],
        [InlineKeyboardButton("🔴 正则黑名单", callback_data="filter_regex_blacklist")],
        [InlineKeyboardButton("⏭ 不设置过滤", callback_data="filter_none")],
        [InlineKeyboardButton("❌ 取消", callback_data="menu_watch")]
    ])
    
    text = "**➕ 添加监控任务**\n\n"
    text += f"来源：`{source_name}`\n"
    text += f"目标：`{dest_name}`\n\n"
    text += "**步骤 3：** 是否需要过滤规则？\n\n"
    text += "🟢 **关键词白名单** - 包含关键词才转发\n"
    text += "🔴 **关键词黑名单** - 包含关键词不转发\n"
    text += "🟢 **正则白名单** - 匹配正则才转发\n"
    text += "🔴 **正则黑名单** - 匹配正则不转发\n"
    text += "⏭ **不设置** - 转发所有消息\n\n"
    text += "💡 可以设置多种规则，按顺序生效"
    
    bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)

def show_filter_options_single(chat_id, message_id, user_id):
    source_name = user_states[user_id].get("source_name", "未知")
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🟢 关键词白名单", callback_data="filter_whitelist")],
        [InlineKeyboardButton("🔴 关键词黑名单", callback_data="filter_blacklist")],
        [InlineKeyboardButton("🟢 正则白名单", callback_data="filter_regex_whitelist")],
        [InlineKeyboardButton("🔴 正则黑名单", callback_data="filter_regex_blacklist")],
        [InlineKeyboardButton("⏭ 不设置过滤", callback_data="filter_none_single")],
        [InlineKeyboardButton("❌ 取消", callback_data="menu_watch")]
    ])
    
    text = "**➕ 添加监控任务（记录模式）**\n\n"
    text += f"来源：`{source_name}`\n"
    text += f"模式：📝 **记录模式**（保存到网页笔记）\n\n"
    text += "**步骤 3：** 是否需要过滤规则？\n\n"
    text += "🟢 **关键词白名单** - 包含关键词才记录\n"
    text += "🔴 **关键词黑名单** - 包含关键词不记录\n"
    text += "🟢 **正则白名单** - 匹配正则才记录\n"
    text += "🔴 **正则黑名单** - 匹配正则不记录\n"
    text += "⏭ **不设置** - 记录所有消息\n\n"
    text += "💡 可以设置多种规则，按顺序生效"
    
    bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)

def show_preserve_source_options(chat_id, message_id, user_id):
    source_name = user_states[user_id].get("source_name", "未知")
    dest_name = user_states[user_id].get("dest_name", "未知")
    whitelist = user_states[user_id].get("whitelist", [])
    blacklist = user_states[user_id].get("blacklist", [])
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ 否（推荐）", callback_data="preserve_no")],
        [InlineKeyboardButton("✅ 是", callback_data="preserve_yes")],
        [InlineKeyboardButton("🔙 取消", callback_data="menu_watch")]
    ])
    
    text = "**➕ 添加监控任务**\n\n"
    text += f"来源：`{source_name}`\n"
    text += f"目标：`{dest_name}`\n"
    if whitelist:
        text += f"白名单：`{', '.join(whitelist)}`\n"
    if blacklist:
        text += f"黑名单：`{', '.join(blacklist)}`\n"
    text += "\n**最后一步：** 是否保留转发来源信息？\n\n"
    text += "✅ **是** - 显示 \"Forwarded from...\"\n"
    text += "❌ **否** - 不显示来源（推荐）"
    
    bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)

def show_forward_mode_options(chat_id, message_id, user_id, whitelist, blacklist, whitelist_regex, blacklist_regex, preserve_source):
    source_name = user_states[user_id].get("source_name", "未知")
    dest_name = user_states[user_id].get("dest_name", "未知")
    
    user_states[user_id]["whitelist"] = whitelist
    user_states[user_id]["blacklist"] = blacklist
    user_states[user_id]["whitelist_regex"] = whitelist_regex
    user_states[user_id]["blacklist_regex"] = blacklist_regex
    user_states[user_id]["preserve_source"] = preserve_source
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 完整转发", callback_data="fwdmode_full")],
        [InlineKeyboardButton("🎯 提取模式", callback_data="fwdmode_extract")],
        [InlineKeyboardButton("🔙 取消", callback_data="menu_watch")]
    ])
    
    text = "**➕ 添加监控任务**\n\n"
    text += f"来源：`{source_name}`\n"
    text += f"目标：`{dest_name}`\n\n"
    text += "**选择转发模式：**\n\n"
    text += "📦 **完整转发** - 转发整条消息（默认）\n"
    text += "🎯 **提取模式** - 使用正则提取特定内容后转发\n\n"
    text += "💡 提取模式需要设置提取规则"
    
    bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)

def complete_watch_setup(chat_id, message_id, user_id, whitelist, blacklist, whitelist_regex, blacklist_regex, preserve_source, forward_mode, extract_patterns):
    try:
        source_id = user_states[user_id]["source_id"]
        source_name = user_states[user_id]["source_name"]
        dest_id = user_states[user_id]["dest_id"]
        dest_name = user_states[user_id]["dest_name"]
        
        watch_config = load_watch_config()
        
        if user_id not in watch_config:
            watch_config[user_id] = {}
        
        # Use composite key: source_id|dest_id to allow one source to multiple targets
        watch_key = f"{source_id}|{dest_id}"
        
        if watch_key in watch_config[user_id]:
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回", callback_data="menu_watch")]])
            bot.edit_message_text(chat_id, message_id, f"**⚠️ 该监控任务已存在**\n\n来源：`{source_name}`\n目标：`{dest_name}`", reply_markup=keyboard)
            del user_states[user_id]
            return
        
        watch_config[user_id][watch_key] = {
            "source": source_id,
            "dest": dest_id,
            "whitelist": whitelist,
            "blacklist": blacklist,
            "whitelist_regex": whitelist_regex,
            "blacklist_regex": blacklist_regex,
            "preserve_forward_source": preserve_source,
            "forward_mode": forward_mode,
            "extract_patterns": extract_patterns,
            "record_mode": False
        }
        save_watch_config(watch_config)
        
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回监控管理", callback_data="menu_watch")]])
        
        result_msg = f"**✅ 监控任务添加成功！**\n\n"
        result_msg += f"来源：`{source_name}`\n"
        result_msg += f"目标：`{dest_name}`\n"
        result_msg += f"转发模式：{'🎯 提取模式' if forward_mode == 'extract' else '📦 完整转发'}\n"
        if whitelist:
            result_msg += f"关键词白名单：`{', '.join(whitelist)}`\n"
        if blacklist:
            result_msg += f"关键词黑名单：`{', '.join(blacklist)}`\n"
        if whitelist_regex:
            result_msg += f"正则白名单：`{', '.join(whitelist_regex)}`\n"
        if blacklist_regex:
            result_msg += f"正则黑名单：`{', '.join(blacklist_regex)}`\n"
        if extract_patterns:
            result_msg += f"提取规则：`{', '.join(extract_patterns)}`\n"
        if preserve_source:
            result_msg += f"保留来源：`是`\n"
        result_msg += "\n从现在开始，新消息将自动转发 🎉"
        
        bot.edit_message_text(chat_id, message_id, result_msg, reply_markup=keyboard)
        del user_states[user_id]
        
    except Exception as e:
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回", callback_data="menu_watch")]])
        bot.edit_message_text(chat_id, message_id, f"**❌ 错误：** `{str(e)}`", reply_markup=keyboard)
        if user_id in user_states:
            del user_states[user_id]

def complete_watch_setup_single(chat_id, message_id, user_id, whitelist, blacklist, whitelist_regex, blacklist_regex):
    try:
        source_id = user_states[user_id]["source_id"]
        source_name = user_states[user_id]["source_name"]
        
        watch_config = load_watch_config()
        
        if user_id not in watch_config:
            watch_config[user_id] = {}
        
        # Use composite key with "record" as dest for record mode
        watch_key = f"{source_id}|record"
        
        if watch_key in watch_config[user_id]:
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回", callback_data="menu_watch")]])
            bot.edit_message_text(chat_id, message_id, f"**⚠️ 该监控任务已存在**\n\n来源：`{source_name}`\n模式：记录模式", reply_markup=keyboard)
            del user_states[user_id]
            return
        
        watch_config[user_id][watch_key] = {
            "source": source_id,
            "dest": None,
            "whitelist": whitelist,
            "blacklist": blacklist,
            "whitelist_regex": whitelist_regex,
            "blacklist_regex": blacklist_regex,
            "preserve_forward_source": False,
            "forward_mode": "full",
            "extract_patterns": [],
            "record_mode": True
        }
        save_watch_config(watch_config)
        
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回监控管理", callback_data="menu_watch")]])
        
        result_msg = f"**✅ 监控任务添加成功！**\n\n"
        result_msg += f"来源：`{source_name}`\n"
        result_msg += f"模式：📝 **记录模式**\n"
        if whitelist:
            result_msg += f"关键词白名单：`{', '.join(whitelist)}`\n"
        if blacklist:
            result_msg += f"关键词黑名单：`{', '.join(blacklist)}`\n"
        if whitelist_regex:
            result_msg += f"正则白名单：`{', '.join(whitelist_regex)}`\n"
        if blacklist_regex:
            result_msg += f"正则黑名单：`{', '.join(blacklist_regex)}`\n"
        result_msg += "\n从现在开始，新消息将自动记录到网页笔记 📝"
        
        bot.edit_message_text(chat_id, message_id, result_msg, reply_markup=keyboard)
        del user_states[user_id]
        
    except Exception as e:
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回", callback_data="menu_watch")]])
        bot.edit_message_text(chat_id, message_id, f"**❌ 错误：** `{str(e)}`", reply_markup=keyboard)
        if user_id in user_states:
            del user_states[user_id]

def handle_add_source(message, user_id):
    try:
        if message.forward_from_chat:
            source_id = str(message.forward_from_chat.id)
            source_name = message.forward_from_chat.title or message.forward_from_chat.username or source_id
        else:
            text = message.text.strip()
            # Special handling for "me" - monitor Saved Messages (user's own favorites)
            if text.lower() == "me":
                source_id = str(message.from_user.id)
                source_name = "我的收藏夹 (Saved Messages)"
            elif text.startswith('@'):
                source_info = acc.get_chat(text)
                source_id = str(source_info.id)
                source_name = source_info.title or source_info.username or source_id
            else:
                try:
                    source_chat_id = int(text)
                    source_info = acc.get_chat(source_chat_id)
                    source_id = str(source_info.id)
                    source_name = source_info.title or source_info.username or source_id
                except ValueError:
                    bot.send_message(message.chat.id, "**❌ 无效的频道/群组ID**\n\n请输入正确的格式")
                    return
        
        user_states[user_id]["source_id"] = source_id
        user_states[user_id]["source_name"] = source_name
        user_states[user_id]["action"] = "choose_mode"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 单一监控（记录模式）", callback_data="mode_single")],
            [InlineKeyboardButton("➡️ 转发到另一个", callback_data="mode_forward")],
            [InlineKeyboardButton("❌ 取消", callback_data="menu_watch")]
        ])
        
        text = "**➕ 添加监控任务**\n\n"
        text += f"✅ 来源已设置：`{source_name}`\n\n"
        text += "**步骤 2：** 选择监控模式\n\n"
        text += "📝 **单一监控（记录模式）** - 只监控这一个频道，消息保存到网页笔记\n"
        text += "➡️ **转发到另一个** - 从这个频道转发消息到另一个频道/群组"
        
        bot.send_message(message.chat.id, text, reply_markup=keyboard)
    
    except ChannelPrivate:
        bot.send_message(message.chat.id, "**❌ 无法访问该频道/群组**\n\n请确保账号已加入")
    except UsernameInvalid:
        bot.send_message(message.chat.id, "**❌ 频道/群组用户名无效**\n\n请检查输入")
    except Exception as e:
        bot.send_message(message.chat.id, f"**❌ 错误：** `{str(e)}`")

def handle_add_dest(message, user_id):
    try:
        if message.forward_from_chat:
            dest_id = str(message.forward_from_chat.id)
            dest_name = message.forward_from_chat.title or message.forward_from_chat.username or dest_id
        else:
            text = message.text.strip()
            if text.lower() == "me":
                dest_id = "me"
                dest_name = "个人收藏"
            elif text.startswith('@'):
                dest_info = acc.get_chat(text)
                dest_id = str(dest_info.id)
                dest_name = dest_info.title or dest_info.username or dest_id
            else:
                try:
                    dest_chat_id = int(text)
                    dest_info = acc.get_chat(dest_chat_id)
                    dest_id = str(dest_info.id)
                    dest_name = dest_info.title or dest_info.username or dest_id
                except ValueError:
                    bot.send_message(message.chat.id, "**❌ 无效的频道/群组ID**\n\n请输入正确的格式")
                    return
        
        user_states[user_id]["dest_id"] = dest_id
        user_states[user_id]["dest_name"] = dest_name
        
        msg = bot.send_message(message.chat.id, "⏳ 正在设置...")
        show_filter_options(message.chat.id, msg.id, user_id)
    
    except ChannelPrivate:
        bot.send_message(message.chat.id, "**❌ 无法访问该频道/群组**\n\n请确保机器人有发送权限")
    except UsernameInvalid:
        bot.send_message(message.chat.id, "**❌ 频道/群组用户名无效**\n\n请检查输入")
    except Exception as e:
        bot.send_message(message.chat.id, f"**❌ 错误：** `{str(e)}`")

# Handle user text input during multi-step interactions
@bot.on_message(filters.text & filters.private & ~filters.command(["start", "help", "watch"]))
def save(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
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
                msg = bot.send_message(message.chat.id, f"✅ 关键词白名单已设置：`{', '.join(keywords)}`\n\n⏳ 继续设置...")
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
                msg = bot.send_message(message.chat.id, f"✅ 关键词黑名单已设置：`{', '.join(keywords)}`\n\n⏳ 继续设置...")
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
                    msg = bot.send_message(message.chat.id, f"✅ 正则白名单已设置：`{', '.join(patterns)}`\n\n⏳ 继续设置...")
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
                    msg = bot.send_message(message.chat.id, f"✅ 正则黑名单已设置：`{', '.join(patterns)}`\n\n⏳ 继续设置...")
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
        
        elif action.startswith("edit_filter_"):
            parts = action.split("_")
            filter_type = parts[2]
            color = parts[3]
            task_id = user_states[user_id].get("task_id")
            watch_key = user_states[user_id].get("watch_key")
            
            watch_config = load_watch_config()
            user_id_str = str(message.from_user.id)
            
            if filter_type == "kw":
                keywords = [kw.strip() for kw in message.text.split(',') if kw.strip()]
                key = "whitelist" if color == "white" else "blacklist"
                watch_config[user_id_str][watch_key][key] = keywords
            elif filter_type == "re":
                patterns = [p.strip() for p in message.text.split(',') if p.strip()]
                try:
                    for pattern in patterns:
                        re.compile(pattern)
                    key = "whitelist_regex" if color == "white" else "blacklist_regex"
                    watch_config[user_id_str][watch_key][key] = patterns
                except re.error as e:
                    bot.send_message(message.chat.id, f"**❌ 正则表达式错误：** `{str(e)}`\n\n请重新输入")
                    return
            
            save_watch_config(watch_config)
            
            del user_states[user_id]
            
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回详情", callback_data=f"watch_view_{task_id}")]])
            bot.send_message(message.chat.id, "**✅ 规则已更新**", reply_markup=keyboard)
            return
        
        elif action == "edit_extract_patterns":
            patterns = [p.strip() for p in message.text.split(',') if p.strip()]
            task_id = user_states[user_id].get("task_id")
            watch_key = user_states[user_id].get("watch_key")
            
            if patterns:
                try:
                    for pattern in patterns:
                        re.compile(pattern)
                    
                    watch_config = load_watch_config()
                    user_id_str = str(message.from_user.id)
                    
                    if isinstance(watch_config[user_id_str][watch_key], dict):
                        watch_config[user_id_str][watch_key]["extract_patterns"] = patterns
                    
                    save_watch_config(watch_config)
                    del user_states[user_id]
                    
                    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回详情", callback_data=f"watch_view_{task_id}")]])
                    bot.send_message(message.chat.id, "**✅ 提取规则已设置**", reply_markup=keyboard)
                except re.error as e:
                    bot.send_message(message.chat.id, f"**❌ 正则表达式错误：** `{str(e)}`\n\n请重新输入")
            else:
                bot.send_message(message.chat.id, "**❌ 请输入至少一个正则表达式**")
            return

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

# Track media groups to process only once per task
processed_media_groups = set()
processed_media_groups_order = []


def register_processed_media_group(key):
    if not key:
        return
    processed_media_groups.add(key)
    processed_media_groups_order.append(key)
    if len(processed_media_groups_order) > 300:
        old_key = processed_media_groups_order.pop(0)
        processed_media_groups.discard(old_key)

# Auto-forward handler for watched channels
if acc is not None:
    @acc.on_message(filters.channel | filters.group | filters.private)
    def auto_forward(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
        try:
            # Ensure the peer is resolved to prevent "Peer id invalid" errors
            try:
                if message.chat.id:
                    acc.get_chat(message.chat.id)
            except Exception as e:
                print(f"Warning: Could not resolve peer {message.chat.id}: {e}")
                return
            
            watch_config = load_watch_config()
            source_chat_id = str(message.chat.id)
            
            for user_id, watches in watch_config.items():
                # Iterate through all watch tasks for this user
                for watch_key, watch_data in watches.items():
                    # Check if this task matches the source
                    if isinstance(watch_data, dict):
                        # New format: check if source matches
                        task_source = watch_data.get("source", watch_key.split("|")[0] if "|" in watch_key else watch_key)
                        
                        # Handle None value for task_source
                        if task_source is None:
                            continue
                        
                        if task_source != source_chat_id:
                            continue
                        
                        dest_chat_id = watch_data.get("dest")
                        whitelist = watch_data.get("whitelist", [])
                        blacklist = watch_data.get("blacklist", [])
                        whitelist_regex = watch_data.get("whitelist_regex", [])
                        blacklist_regex = watch_data.get("blacklist_regex", [])
                        preserve_forward_source = watch_data.get("preserve_forward_source", False)
                        forward_mode = watch_data.get("forward_mode", "full")
                        extract_patterns = watch_data.get("extract_patterns", [])
                        record_mode = watch_data.get("record_mode", False)
                    else:
                        # Old format compatibility: key is source
                        if watch_key != source_chat_id:
                            continue
                        
                        dest_chat_id = watch_data
                        whitelist = []
                        blacklist = []
                        whitelist_regex = []
                        blacklist_regex = []
                        preserve_forward_source = False
                        forward_mode = "full"
                        extract_patterns = []
                        record_mode = False
                    
                    # Handle None value for dest_chat_id (skip if not in record mode)
                    if not record_mode and dest_chat_id is None:
                        continue
                    
                    media_group_key = None
                    if message.media_group_id:
                        media_group_key = f"{user_id}_{watch_key}_{message.media_group_id}"
                        if media_group_key in processed_media_groups:
                            continue
                    
                    message_text = message.text or message.caption or ""
                    
                    # Check keyword whitelist
                    if whitelist:
                        if not any(keyword.lower() in message_text.lower() for keyword in whitelist):
                            continue
                    
                    # Check keyword blacklist
                    if blacklist:
                        if any(keyword.lower() in message_text.lower() for keyword in blacklist):
                            continue
                    
                    # Check regex whitelist
                    if whitelist_regex:
                        match_found = False
                        for pattern in whitelist_regex:
                            try:
                                if re.search(pattern, message_text):
                                    match_found = True
                                    break
                            except re.error:
                                pass
                        if not match_found:
                            continue
                    
                    # Check regex blacklist
                    if blacklist_regex:
                        skip_message = False
                        for pattern in blacklist_regex:
                            try:
                                if re.search(pattern, message_text):
                                    skip_message = True
                                    break
                            except re.error:
                                pass
                        if skip_message:
                            continue
                    
                    try:
                        # Record mode - save to database
                        if record_mode:
                            source_name = message.chat.title or message.chat.username or source_chat_id
                            
                            # Handle text content with extraction
                            content_to_save = message_text
                            if forward_mode == "extract" and extract_patterns:
                                extracted_content = []
                                for pattern in extract_patterns:
                                    try:
                                        matches = re.findall(pattern, message_text)
                                        if matches:
                                            if isinstance(matches[0], tuple):
                                                for match_group in matches:
                                                    extracted_content.extend(match_group)
                                            else:
                                                extracted_content.extend(matches)
                                    except re.error:
                                        pass
                                
                                if extracted_content:
                                    content_to_save = "\n".join(set(extracted_content))
                                else:
                                    content_to_save = ""
                            
                            # Handle media
                            media_type = None
                            media_path = None
                            media_paths = []
                            
                            # Check if this is a media group (multiple images)
                            if message.media_group_id:
                                try:
                                    media_group = acc.get_media_group(message.chat.id, message.id)
                                    if media_group:
                                        print(f"📝 记录模式：发现媒体组，共 {len(media_group)} 个媒体")
                                        for idx, msg in enumerate(media_group):
                                            if msg.photo:
                                                media_type = "photo"
                                                file_name = f"{msg.id}_{idx}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                                                file_path = os.path.join(MEDIA_DIR, file_name)
                                                acc.download_media(msg.photo.file_id, file_name=file_path)
                                                media_paths.append(file_name)
                                                if idx == 0:
                                                    media_path = file_name
                                                # Limit to 9 images
                                                if len(media_paths) >= 9:
                                                    print(f"⚠️ 记录模式：媒体组超过9张图片，仅保存前9张")
                                                    break
                                            # Capture caption if available and not already set (common on last item)
                                            if msg.caption and not content_to_save:
                                                content_to_save = msg.caption
                                except Exception as e:
                                    print(f"Error fetching media group: {e}")
                                    # Fallback to single image
                                    if message.photo:
                                        media_type = "photo"
                                        file_name = f"{message.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                                        file_path = os.path.join(MEDIA_DIR, file_name)
                                        acc.download_media(message.photo.file_id, file_name=file_path)
                                        media_path = file_name
                                        media_paths = [file_name]
                            
                            # Single photo
                            elif message.photo:
                                media_type = "photo"
                                photo = message.photo
                                file_name = f"{message.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                                file_path = os.path.join(MEDIA_DIR, file_name)
                                acc.download_media(photo.file_id, file_name=file_path)
                                media_path = file_name
                                media_paths = [file_name]
                            
                            # Single video
                            elif message.video:
                                media_type = "video"
                                try:
                                    # Download video thumbnail
                                    thumb = message.video.thumbs[0] if message.video.thumbs else None
                                    if thumb:
                                        file_name = f"{message.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_thumb.jpg"
                                        file_path = os.path.join(MEDIA_DIR, file_name)
                                        acc.download_media(thumb.file_id, file_name=file_path)
                                        media_path = file_name
                                        media_paths = [file_name]
                                except Exception as e:
                                    print(f"Error downloading video thumbnail: {e}")
                            
                            # Save to database
                            print(f"✅ 记录模式：保存笔记 (文本: {bool(content_to_save)}, 媒体: {len(media_paths)} 个)")
                            add_note(
                                user_id=int(user_id),
                                source_chat_id=source_chat_id,
                                source_name=source_name,
                                message_text=content_to_save if content_to_save else None,
                                media_type=media_type,
                                media_path=media_path,
                                media_paths=media_paths if media_paths else None
                            )
                            
                            # Mark as processed
                            if media_group_key:
                                register_processed_media_group(media_group_key)
                        
                        # Forward mode
                        else:
                            # Extract mode
                            if forward_mode == "extract" and extract_patterns:
                                extracted_content = []
                                for pattern in extract_patterns:
                                    try:
                                        matches = re.findall(pattern, message_text)
                                        if matches:
                                            if isinstance(matches[0], tuple):
                                                for match_group in matches:
                                                    extracted_content.extend(match_group)
                                            else:
                                                extracted_content.extend(matches)
                                    except re.error:
                                        pass
                                
                                if extracted_content:
                                    extracted_text = "\n".join(set(extracted_content))
                                    if dest_chat_id == "me":
                                        acc.send_message("me", extracted_text)
                                    else:
                                        acc.send_message(int(dest_chat_id), extracted_text)
                                    if media_group_key:
                                        register_processed_media_group(media_group_key)
                            
                            # Full forward mode
                            else:
                                dest_id = "me" if dest_chat_id == "me" else int(dest_chat_id)
                                
                                if preserve_forward_source:
                                    # Keep forward source - forward full media group when available
                                    if message.media_group_id:
                                        try:
                                            media_group = acc.get_media_group(message.chat.id, message.id)
                                            if media_group:
                                                message_ids = [msg.id for msg in media_group]
                                            else:
                                                message_ids = [message.id]
                                            acc.forward_messages(dest_id, message.chat.id, message_ids)
                                            if media_group_key:
                                                register_processed_media_group(media_group_key)
                                        except Exception as e:
                                            print(f"Warning: forward media group failed, fallback to single forward: {e}")
                                            acc.forward_messages(dest_id, message.chat.id, message.id)
                                            if media_group_key:
                                                register_processed_media_group(media_group_key)
                                    else:
                                        acc.forward_messages(dest_id, message.chat.id, message.id)
                                else:
                                    # Hide forward source - use copy for single messages or copy_media_group for albums
                                    if message.media_group_id:
                                        try:
                                            # Use copy_media_group to keep multiple images together
                                            acc.copy_media_group(dest_id, message.chat.id, message.id)
                                            print(f"📤 转发模式：复制媒体组到 {dest_id}（隐藏引用）")
                                            # Mark as processed
                                            if media_group_key:
                                                register_processed_media_group(media_group_key)
                                        except Exception as e:
                                            print(f"Warning: copy_media_group failed, falling back to copy_message: {e}")
                                            acc.copy_message(dest_id, message.chat.id, message.id)
                                            if media_group_key:
                                                register_processed_media_group(media_group_key)
                                    else:
                                        # Single message - use copy_message
                                        acc.copy_message(dest_id, message.chat.id, message.id)
                    except Exception as e:
                        print(f"Error processing message: {e}")
        except Exception as e:
            print(f"Error in auto_forward: {e}")


# 启动时加载并打印配置信息
def print_startup_config():
    print("\n" + "="*60)
    print("🤖 Telegram Save-Restricted Bot 启动成功")
    print("="*60)
    
    watch_config = load_watch_config()
    if not watch_config:
        print("\n📋 当前没有监控任务")
    else:
        total_tasks = sum(len(watches) for watches in watch_config.values())
        print(f"\n📋 已加载 {len(watch_config)} 个用户的 {total_tasks} 个监控任务：\n")
        
        # Collect all unique source IDs to pre-cache
        source_ids_to_cache = set()
        
        for user_id, watches in watch_config.items():
            print(f"👤 用户 {user_id}:")
            for watch_key, watch_data in watches.items():
                if isinstance(watch_data, dict):
                    source_id = watch_data.get("source", watch_key.split("|")[0] if "|" in watch_key else watch_key)
                    dest_id = watch_data.get("dest", "未知")
                    record_mode = watch_data.get("record_mode", False)
                    
                    # Handle None values
                    if source_id is None:
                        source_id = "未知来源"
                    if dest_id is None:
                        dest_id = "未知目标"
                    
                    # Add to cache list if it's a valid chat ID (channels/groups have negative IDs)
                    if source_id not in ["未知来源", "me"] and source_id:
                        try:
                            # Try to parse as int to verify it's a valid chat ID
                            # Only cache negative IDs (channels/groups), not positive IDs (users)
                            chat_id_int = int(source_id)
                            if chat_id_int < 0:
                                source_ids_to_cache.add(source_id)
                        except (ValueError, TypeError):
                            pass
                    
                    if record_mode:
                        print(f"   📝 {source_id} → 记录模式")
                    else:
                        print(f"   📤 {source_id} → {dest_id}")
                else:
                    # Handle None values in old format
                    source_display = watch_key if watch_key is not None else "未知来源"
                    dest_display = watch_data if watch_data is not None else "未知目标"
                    
                    # Add to cache list if it's a valid chat ID (channels/groups have negative IDs)
                    if watch_key not in ["未知来源", "me", None] and watch_key:
                        try:
                            # Only cache negative IDs (channels/groups), not positive IDs (users)
                            chat_id_int = int(watch_key)
                            if chat_id_int < 0:
                                source_ids_to_cache.add(watch_key)
                        except (ValueError, TypeError):
                            pass
                    
                    print(f"   📤 {source_display} → {dest_display}")
            print()
        
        # Pre-cache all source channels to prevent "Peer id invalid" errors
        if acc is not None and source_ids_to_cache:
            print("🔄 预加载频道信息到缓存...")
            cached_count = 0
            for source_id in source_ids_to_cache:
                try:
                    acc.get_chat(int(source_id))
                    cached_count += 1
                    print(f"   ✅ 已缓存: {source_id}")
                except Exception as e:
                    print(f"   ⚠️ 无法缓存 {source_id}: {str(e)}")
            print(f"📦 成功缓存 {cached_count}/{len(source_ids_to_cache)} 个频道\n")
    
    print("="*60)
    print("✅ 机器人已就绪，正在监听消息...")
    print("="*60 + "\n")

# 打印启动配置
print_startup_config()

# infinty polling
bot.run()
if acc is not None:
    acc.stop()
