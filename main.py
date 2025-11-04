import pyrogram
from pyrogram import Client, filters
from pyrogram.errors import UserAlreadyParticipant, InviteHashExpired, UsernameNotOccupied, ChannelPrivate, UsernameInvalid
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

import time
import os
import threading
import json

with open('config.json', 'r') as f: DATA = json.load(f)
def getenv(var): return os.environ.get(var) or DATA.get(var, None)

# Watch configurations file
WATCH_FILE = 'watch_config.json'

# User state management for multi-step interactions
user_states = {}

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
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 监控管理", callback_data="menu_watch")],
        [InlineKeyboardButton("❓ 帮助说明", callback_data="menu_help")],
        [InlineKeyboardButton("🌐 源代码", url="https://github.com/bipinkrish/Save-Restricted-Bot")]
    ])
    
    welcome_text = f"👋 你好 **{message.from_user.mention}**！\n\n"
    welcome_text += "我是受限内容保存机器人，可以帮你：\n\n"
    welcome_text += "📥 **转发消息** - 直接发送 Telegram 链接\n"
    welcome_text += "👁 **监控频道/群组** - 自动转发新消息\n"
    welcome_text += "🔍 **关键词过滤** - 只转发你关心的内容\n\n"
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
• 可选择是否保留转发来源

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
            welcome_text += "🔍 **关键词过滤** - 只转发你关心的内容\n\n"
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
• 点击"监控管理"按钮设置自动转发
• 支持监控频道和群组
• 支持关键词过滤（白名单/黑名单）
• 可选择是否保留转发来源

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
• 所有操作都可通过按钮完成，无需记忆复杂命令
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
            
            result = "**📋 监控任务列表**\n\n"
            for idx, (source, watch_data) in enumerate(watch_config[user_id].items(), 1):
                if isinstance(watch_data, dict):
                    dest = watch_data.get("dest", "unknown")
                    whitelist = watch_data.get("whitelist", [])
                    blacklist = watch_data.get("blacklist", [])
                    preserve_source = watch_data.get("preserve_forward_source", False)
                    
                    result += f"**{idx}.** `{source}` ➡️ `{dest}`\n"
                    if whitelist:
                        result += f"   🟢 白名单: `{', '.join(whitelist)}`\n"
                    if blacklist:
                        result += f"   🔴 黑名单: `{', '.join(blacklist)}`\n"
                    if preserve_source:
                        result += f"   📤 保留来源\n"
                    result += "\n"
                else:
                    result += f"**{idx}.** `{source}` ➡️ `{watch_data}`\n\n"
            
            result += f"**总计：** {len(watch_config[user_id])} 个监控任务"
            
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回", callback_data="menu_watch")]])
            bot.edit_message_text(chat_id, message_id, result, reply_markup=keyboard)
            callback_query.answer()
        
        elif data == "watch_remove_start":
            watch_config = load_watch_config()
            
            if user_id not in watch_config or not watch_config[user_id]:
                keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回", callback_data="menu_watch")]])
                bot.edit_message_text(chat_id, message_id, "**🗑 删除监控**\n\n暂无监控任务可删除", reply_markup=keyboard)
                callback_query.answer("暂无监控任务")
                return
            
            buttons = []
            for idx, (source, watch_data) in enumerate(watch_config[user_id].items(), 1):
                if isinstance(watch_data, dict):
                    dest = watch_data.get("dest", "unknown")
                else:
                    dest = watch_data
                buttons.append([InlineKeyboardButton(f"🗑 {idx}. {source} ➡️ {dest}", callback_data=f"watch_remove_{idx}")])
            
            buttons.append([InlineKeyboardButton("❌ 取消", callback_data="menu_watch")])
            keyboard = InlineKeyboardMarkup(buttons)
            
            text = "**🗑 删除监控**\n\n"
            text += "选择要删除的监控任务："
            
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
        
        elif data == "dest_custom":
            user_states[user_id]["action"] = "add_dest"
            
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("❌ 取消", callback_data="menu_watch")]])
            
            text = "**➕ 添加监控任务**\n\n"
            text += "**步骤 2/2：** 请发送目标频道/群组\n\n"
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
            
            complete_watch_setup(chat_id, message_id, user_id, [], [], False)
            callback_query.answer("✅ 监控已添加")
        
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
                user_states[user_id]["action"] = "add_blacklist"
                
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("⏭ 跳过", callback_data="skip_blacklist")],
                    [InlineKeyboardButton("❌ 取消", callback_data="menu_watch")]
                ])
                
                text = "**➕ 添加监控任务**\n\n"
                text += "**步骤 4：设置黑名单**\n\n"
                text += "请发送黑名单关键词，用逗号分隔\n\n"
                text += "示例：`广告,推广,垃圾`\n\n"
                text += "💡 包含这些关键词的消息不会被转发"
                
                bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)
                callback_query.answer("已跳过白名单设置")
        
        elif data == "skip_blacklist":
            if user_id in user_states:
                user_states[user_id]["blacklist"] = []
                show_preserve_source_options(chat_id, message_id, user_id)
                callback_query.answer("已跳过黑名单设置")
        
        elif data.startswith("preserve_"):
            preserve = data.split("_")[1] == "yes"
            
            if user_id not in user_states:
                callback_query.answer("❌ 会话已过期", show_alert=True)
                return
            
            whitelist = user_states[user_id].get("whitelist", [])
            blacklist = user_states[user_id].get("blacklist", [])
            
            complete_watch_setup(chat_id, message_id, user_id, whitelist, blacklist, preserve)
            callback_query.answer("✅ 监控已添加")
        
    except Exception as e:
        print(f"Callback error: {e}")
        callback_query.answer(f"❌ 错误: {str(e)}", show_alert=True)

def show_filter_options(chat_id, message_id, user_id):
    source_name = user_states[user_id].get("source_name", "未知")
    dest_name = user_states[user_id].get("dest_name", "未知")
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🟢 设置白名单", callback_data="filter_whitelist")],
        [InlineKeyboardButton("🔴 设置黑名单", callback_data="filter_blacklist")],
        [InlineKeyboardButton("⏭ 不设置过滤", callback_data="filter_none")],
        [InlineKeyboardButton("❌ 取消", callback_data="menu_watch")]
    ])
    
    text = "**➕ 添加监控任务**\n\n"
    text += f"来源：`{source_name}`\n"
    text += f"目标：`{dest_name}`\n\n"
    text += "**步骤 3：** 是否需要关键词过滤？\n\n"
    text += "🟢 **白名单** - 只转发包含关键词的消息\n"
    text += "🔴 **黑名单** - 不转发包含关键词的消息\n"
    text += "⏭ **不设置** - 转发所有消息"
    
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

def complete_watch_setup(chat_id, message_id, user_id, whitelist, blacklist, preserve_source):
    try:
        source_id = user_states[user_id]["source_id"]
        source_name = user_states[user_id]["source_name"]
        dest_id = user_states[user_id]["dest_id"]
        dest_name = user_states[user_id]["dest_name"]
        
        watch_config = load_watch_config()
        
        if user_id not in watch_config:
            watch_config[user_id] = {}
        
        if source_id in watch_config[user_id]:
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回", callback_data="menu_watch")]])
            bot.edit_message_text(chat_id, message_id, f"**⚠️ 该来源已在监控中**\n\n来源：`{source_name}`", reply_markup=keyboard)
            del user_states[user_id]
            return
        
        watch_config[user_id][source_id] = {
            "dest": dest_id,
            "whitelist": whitelist,
            "blacklist": blacklist,
            "preserve_forward_source": preserve_source
        }
        save_watch_config(watch_config)
        
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回监控管理", callback_data="menu_watch")]])
        
        result_msg = f"**✅ 监控任务添加成功！**\n\n"
        result_msg += f"来源：`{source_name}`\n"
        result_msg += f"目标：`{dest_name}`\n"
        if whitelist:
            result_msg += f"白名单：`{', '.join(whitelist)}`\n"
        if blacklist:
            result_msg += f"黑名单：`{', '.join(blacklist)}`\n"
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

def handle_add_source(message, user_id):
    try:
        if message.forward_from_chat:
            source_id = str(message.forward_from_chat.id)
            source_name = message.forward_from_chat.title or message.forward_from_chat.username or source_id
        else:
            text = message.text.strip()
            if text.startswith('@'):
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
        user_states[user_id]["action"] = "choose_dest"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💾 保存到收藏夹", callback_data="set_dest_me")],
            [InlineKeyboardButton("📤 自定义目标", callback_data="dest_custom")],
            [InlineKeyboardButton("❌ 取消", callback_data="menu_watch")]
        ])
        
        text = "**➕ 添加监控任务**\n\n"
        text += f"✅ 来源已设置：`{source_name}`\n\n"
        text += "**步骤 2/2：** 选择转发目标\n\n"
        text += "💾 **保存到收藏夹** - 转发到你的个人收藏\n"
        text += "📤 **自定义目标** - 转发到其他频道/群组"
        
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
                user_states[user_id]["action"] = "add_blacklist"
                
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("⏭ 跳过", callback_data="skip_blacklist")],
                    [InlineKeyboardButton("❌ 取消", callback_data="menu_watch")]
                ])
                
                text = "**➕ 添加监控任务**\n\n"
                text += f"✅ 白名单已设置：`{', '.join(keywords)}`\n\n"
                text += "**步骤 4：设置黑名单**\n\n"
                text += "请发送黑名单关键词，用逗号分隔\n\n"
                text += "示例：`广告,推广,垃圾`\n\n"
                text += "💡 包含这些关键词的消息不会被转发"
                
                bot.send_message(message.chat.id, text, reply_markup=keyboard)
            else:
                bot.send_message(message.chat.id, "**❌ 请输入至少一个关键词**")
            return
        
        elif action == "add_blacklist":
            keywords = [kw.strip() for kw in message.text.split(',') if kw.strip()]
            if keywords:
                user_states[user_id]["blacklist"] = keywords
            else:
                user_states[user_id]["blacklist"] = []
            
            msg = bot.send_message(message.chat.id, "⏳ 正在完成设置...")
            show_preserve_source_options(message.chat.id, msg.id, user_id)
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
