import pyrogram
from pyrogram import Client, filters
from pyrogram.errors import UserAlreadyParticipant, InviteHashExpired, UsernameNotOccupied, ChannelPrivate, UsernameInvalid
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import time
import os
import threading
import json
import re

# Import regex filter functions
from regex_filters import (
    load_filter_config, 
    save_filter_config, 
    parse_regex_pattern, 
    compile_patterns,
    compile_pattern_list, 
    safe_regex_match, 
    matches_filters,
    extract_matches,
    format_snippets_for_telegram,
    MAX_PATTERN_LENGTH,
    MAX_PATTERN_COUNT
)

# Import watch manager functions
from watch_manager import (
    load_watch_config,
    save_watch_config,
    get_user_watches,
    get_watch_by_id,
    get_watch_by_source,
    add_watch as add_watch_entry,
    remove_watch as remove_watch_entry,
    update_watch_flag,
    add_watch_keyword,
    remove_watch_keyword,
    add_watch_pattern,
    remove_watch_pattern,
    generate_watch_id
)

with open('config.json', 'r') as f: DATA = json.load(f)
def getenv(var): return os.environ.get(var) or DATA.get(var, None)

# Watch configurations are now managed by watch_manager module

# Compiled patterns cache
compiled_patterns = []

bot_token = getenv("TOKEN") 
api_hash = getenv("HASH") 
api_id = getenv("ID")
bot = Client("mybot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)

ss = getenv("STRING")
if ss is not None:
    acc = Client("myacc" ,api_id=api_id, api_hash=api_hash, session_string=ss)
    acc.start()
else: acc = None

# Initialize compiled patterns at startup
compiled_patterns = compile_patterns()

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

**消息转发功能：**
直接发送 Telegram 消息链接，机器人会帮你获取内容

**监控功能 (/watch)：**
每个监控任务都有独立的过滤器和设置

• `/watch list` - 查看所有监控任务及其设置
• `/watch add <来源> <目标> [选项]` - 添加监控任务
• `/watch remove <任务ID>` - 删除监控任务
• `/watch set <任务ID> <设置> <值>` - 修改监控任务设置

**监控任务选项：**
• `--extract on|off` - 提取模式（仅转发匹配片段）
• `--kw on|off` - 关键词/正则过滤开关
• `--preserve on|off` - 保留原始转发来源

**监控任务过滤器（每个任务独立）：**
• `/watch keywords add <任务ID> <关键词>` - 添加关键词
• `/watch keywords del <任务ID> <索引|关键词>` - 删除关键词
• `/watch keywords list <任务ID>` - 查看关键词列表
• `/watch regex add <任务ID> <模式>` - 添加正则表达式
• `/watch regex del <任务ID> <索引|模式>` - 删除正则表达式
• `/watch regex list <任务ID>` - 查看正则表达式列表

**测试功能：**
• `/watch preview <任务ID> <文本>` - 预览该任务的提取效果

**全局正则表达式（已弃用，建议使用每任务过滤器）：**
• `/addre <pattern>` - 添加全局正则表达式模式
• `/delre <index>` - 删除全局正则表达式模式
• `/listre` - 列出所有全局正则表达式模式
• `/testre <pattern> <text>` - 测试正则表达式模式

**正则表达式说明：**
• 支持标准 Python 正则表达式语法
• 使用 /pattern/flags 格式指定标志（如 /test/i）
• 支持的标志：i（忽略大小写）、m（多行）、s（点匹配所有）、x（详细）
• 默认为不区分大小写匹配
• 示例：`/watch regex add <ID> /urgent|important/i`

**使用示例：**
1. 基础监控：
   `/watch add @source_channel me`
   
2. 带关键词过滤的监控：
   `/watch add @source me --kw on`
   `/watch keywords add <ID> 重要`
   `/watch keywords add <ID> 紧急`
   
3. 带提取模式的监控：
   `/watch add @source me --extract on --kw on`
   `/watch regex add <ID> /bitcoin|crypto/i`
   
4. 保留原始来源：
   `/watch add @source @dest --preserve on`
   
5. 修改现有任务：
   `/watch set <ID> extract on`
   `/watch set <ID> preserve off`

{USAGE}
"""
    bot.send_message(message.chat.id, help_text, reply_to_message_id=message.id)

# watch command - Main entry point for watch management
@bot.on_message(filters.command(["watch"]))
def watch_command(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
    if acc is None:
        bot.send_message(message.chat.id, "**❌ 需要配置 String Session 才能使用监控功能**", reply_to_message_id=message.id)
        return
    
    text = message.text.strip()
    parts = text.split(maxsplit=1)
    
    if len(parts) == 1:
        # Default to /watch list
        watch_list_command(message)
        return
    
    subcommand = parts[1].split()[0].lower()
    
    if subcommand == "list":
        watch_list_command(message)
    elif subcommand == "add":
        watch_add_command(message, parts[1])
    elif subcommand == "remove":
        watch_remove_command(message, parts[1])
    elif subcommand == "set":
        watch_set_command(message, parts[1])
    elif subcommand == "keywords":
        watch_keywords_command(message, parts[1])
    elif subcommand == "regex":
        watch_regex_command(message, parts[1])
    elif subcommand == "preview":
        watch_preview_command(message, parts[1])
    else:
        bot.send_message(message.chat.id, 
            "**❌ 未知子命令**\n\n"
            "可用命令：\n"
            "• `/watch list` - 查看监控列表\n"
            "• `/watch add` - 添加监控\n"
            "• `/watch remove` - 删除监控\n"
            "• `/watch set` - 修改设置\n"
            "• `/watch keywords` - 管理关键词\n"
            "• `/watch regex` - 管理正则表达式\n"
            "• `/watch preview` - 预览提取效果",
            reply_to_message_id=message.id)


def watch_list_command(message):
    """List all watches for the user"""
    watch_config = load_watch_config()
    user_id = str(message.from_user.id)
    user_watches = get_user_watches(watch_config, user_id)
    
    if not user_watches:
        bot.send_message(message.chat.id, 
            "**📋 你还没有设置任何监控任务**\n\n"
            "使用 `/watch add <来源> <目标>` 来添加监控\n\n"
            "示例：`/watch add @channel me --kw on --extract on`",
            reply_to_message_id=message.id)
        return
    
    result = "**📋 你的监控任务列表：**\n\n"
    
    for idx, (watch_id, watch_data) in enumerate(user_watches.items(), 1):
        source = watch_data.get("source", "unknown")
        dest = watch_data.get("dest", "unknown")
        enabled = watch_data.get("enabled", True)
        flags = watch_data.get("flags", {})
        filters = watch_data.get("filters", {})
        
        status_icon = "✅" if enabled else "❌"
        result += f"{idx}. {status_icon} `{source}` ➡️ `{dest}`\n"
        result += f"   ID: `{watch_id[:8]}...`\n"
        
        # Show flags
        extract = "开" if flags.get("extract_mode") else "关"
        kw_filter = "开" if flags.get("keywords_enabled") else "关"
        preserve = "是" if flags.get("preserve_source") else "否"
        result += f"   提取模式: {extract} | 过滤器: {kw_filter} | 保留来源: {preserve}\n"
        
        # Show filter counts
        kw_count = len(filters.get("keywords", []))
        pattern_count = len(filters.get("patterns", []))
        if kw_count > 0 or pattern_count > 0:
            result += f"   关键词: {kw_count} 个 | 正则: {pattern_count} 个\n"
        
        result += "\n"
    
    result += f"**总计：** {len(user_watches)} 个监控任务\n\n"
    result += "💡 **提示：** 使用 `/watch set <ID>` 修改设置"
    
    bot.send_message(message.chat.id, result, reply_to_message_id=message.id)


def watch_add_command(message, args_str):
    """Add a new watch"""
    args = args_str.split()[1:]  # Remove 'add' subcommand
    
    if len(args) < 2:
        bot.send_message(message.chat.id,
            "**❌ 用法错误**\n\n"
            "正确格式：`/watch add <来源> <目标> [选项]`\n\n"
            "选项：\n"
            "• `--extract on|off` - 提取模式\n"
            "• `--kw on|off` - 关键词过滤\n"
            "• `--preserve on|off` - 保留来源\n\n"
            "示例：\n"
            "• `/watch add @channel me`\n"
            "• `/watch add @channel me --kw on --extract on`",
            reply_to_message_id=message.id)
        return
    
    source_chat = args[0].strip()
    dest_chat = args[1].strip()
    user_id = str(message.from_user.id)
    
    # Parse options
    extract_mode = False
    keywords_enabled = False
    preserve_source = False
    
    i = 2
    while i < len(args):
        arg = args[i].lower()
        if arg == "--extract" and i + 1 < len(args):
            extract_mode = args[i + 1].lower() in ['on', 'true', '1']
            i += 2
        elif arg == "--kw" and i + 1 < len(args):
            keywords_enabled = args[i + 1].lower() in ['on', 'true', '1']
            i += 2
        elif arg == "--preserve" and i + 1 < len(args):
            preserve_source = args[i + 1].lower() in ['on', 'true', '1']
            i += 2
        else:
            i += 1
    
    try:
        # Resolve source chat ID
        if source_chat.startswith('@'):
            source_info = acc.get_chat(source_chat)
            source_id = str(source_info.id)
        else:
            source_id = source_chat
            source_info = acc.get_chat(int(source_chat))
        
        # Resolve destination chat ID
        if dest_chat.lower() == "me":
            dest_id = "me"
        elif dest_chat.startswith('@'):
            dest_info = acc.get_chat(dest_chat)
            dest_id = str(dest_info.id)
        else:
            dest_id = dest_chat
            dest_info = acc.get_chat(int(dest_chat))
        
        # Add watch
        watch_config = load_watch_config()
        success, msg, watch_id = add_watch_entry(
            watch_config, user_id, source_id, dest_id,
            extract_mode=extract_mode,
            keywords_enabled=keywords_enabled,
            preserve_source=preserve_source
        )
        
        if not success:
            bot.send_message(message.chat.id, f"**❌ {msg}**", reply_to_message_id=message.id)
            return
        
        result_msg = f"**✅ {msg}！**\n\n"
        result_msg += f"来源：`{source_chat}`\n"
        result_msg += f"目标：`{dest_chat}`\n"
        result_msg += f"任务ID：`{watch_id[:8]}...`\n\n"
        result_msg += "**设置：**\n"
        result_msg += f"• 提取模式：{'开启' if extract_mode else '关闭'}\n"
        result_msg += f"• 关键词过滤：{'开启' if keywords_enabled else '关闭'}\n"
        result_msg += f"• 保留来源：{'是' if preserve_source else '否'}\n\n"
        
        if keywords_enabled:
            result_msg += "💡 使用 `/watch keywords add <ID> <关键词>` 添加过滤关键词"
        
        bot.send_message(message.chat.id, result_msg, reply_to_message_id=message.id)
    
    except ChannelPrivate:
        bot.send_message(message.chat.id, 
            "**❌ 无法访问该频道**\n\n"
            "请确保：\n"
            "1. 账号已加入该频道\n"
            "2. 频道ID/用户名正确",
            reply_to_message_id=message.id)
    except UsernameInvalid:
        bot.send_message(message.chat.id, 
            "**❌ 频道用户名无效**\n\n"
            "请检查用户名是否正确",
            reply_to_message_id=message.id)
    except Exception as e:
        bot.send_message(message.chat.id, f"**❌ 错误：** `{str(e)}`", reply_to_message_id=message.id)


def watch_remove_command(message, args_str):
    """Remove a watch"""
    args = args_str.split()[1:]  # Remove 'remove' subcommand
    
    if len(args) < 1:
        bot.send_message(message.chat.id,
            "**❌ 用法错误**\n\n"
            "正确格式：`/watch remove <任务ID或编号>`\n\n"
            "使用 `/watch list` 查看任务ID",
            reply_to_message_id=message.id)
        return
    
    watch_config = load_watch_config()
    user_id = str(message.from_user.id)
    user_watches = get_user_watches(watch_config, user_id)
    
    if not user_watches:
        bot.send_message(message.chat.id, "**❌ 你没有任何监控任务**", reply_to_message_id=message.id)
        return
    
    identifier = args[0].strip()
    
    # Try as index first
    try:
        index = int(identifier)
        if 1 <= index <= len(user_watches):
            watch_id = list(user_watches.keys())[index - 1]
        else:
            bot.send_message(message.chat.id,
                f"**❌ 任务编号无效**\n\n"
                f"请输入 1 到 {len(user_watches)} 之间的数字",
                reply_to_message_id=message.id)
            return
    except ValueError:
        # Try as watch ID (partial match)
        watch_id = None
        for wid in user_watches.keys():
            if wid.startswith(identifier):
                watch_id = wid
                break
        
        if not watch_id:
            bot.send_message(message.chat.id,
                "**❌ 找不到该监控任务**\n\n"
                "请检查任务ID或使用 `/watch list` 查看",
                reply_to_message_id=message.id)
            return
    
    watch_data = user_watches[watch_id]
    success, msg = remove_watch_entry(watch_config, user_id, watch_id)
    
    if success:
        bot.send_message(message.chat.id,
            f"**✅ {msg}**\n\n"
            f"来源：`{watch_data.get('source')}`\n"
            f"目标：`{watch_data.get('dest')}`",
            reply_to_message_id=message.id)
    else:
        bot.send_message(message.chat.id, f"**❌ {msg}**", reply_to_message_id=message.id)


def watch_set_command(message, args_str):
    """Set watch flags"""
    args = args_str.split()[1:]  # Remove 'set' subcommand
    
    if len(args) < 3:
        bot.send_message(message.chat.id,
            "**❌ 用法错误**\n\n"
            "正确格式：`/watch set <任务ID> <设置> <值>`\n\n"
            "可用设置：\n"
            "• `extract` - 提取模式 (on/off)\n"
            "• `kw` - 关键词过滤 (on/off)\n"
            "• `preserve` - 保留来源 (on/off)\n\n"
            "示例：`/watch set abc123 extract on`",
            reply_to_message_id=message.id)
        return
    
    watch_config = load_watch_config()
    user_id = str(message.from_user.id)
    identifier = args[0].strip()
    flag_name_short = args[1].lower()
    value_str = args[2].lower()
    
    # Map short names to full flag names
    flag_map = {
        "extract": "extract_mode",
        "kw": "keywords_enabled",
        "preserve": "preserve_source"
    }
    
    if flag_name_short not in flag_map:
        bot.send_message(message.chat.id,
            f"**❌ 无效的设置名称**\n\n"
            f"可用设置：{', '.join(flag_map.keys())}",
            reply_to_message_id=message.id)
        return
    
    flag_name = flag_map[flag_name_short]
    value = value_str in ['on', 'true', '1']
    
    # Find watch ID
    user_watches = get_user_watches(watch_config, user_id)
    watch_id = None
    for wid in user_watches.keys():
        if wid.startswith(identifier) or wid == identifier:
            watch_id = wid
            break
    
    if not watch_id:
        bot.send_message(message.chat.id,
            "**❌ 找不到该监控任务**\n\n"
            "使用 `/watch list` 查看任务ID",
            reply_to_message_id=message.id)
        return
    
    success, msg = update_watch_flag(watch_config, user_id, watch_id, flag_name, value)
    
    if success:
        status = "开启" if value else "关闭"
        bot.send_message(message.chat.id,
            f"**✅ 设置已更新**\n\n"
            f"任务ID：`{watch_id[:8]}...`\n"
            f"{flag_name_short}：{status}",
            reply_to_message_id=message.id)
    else:
        bot.send_message(message.chat.id, f"**❌ {msg}**", reply_to_message_id=message.id)


def watch_keywords_command(message, args_str):
    """Manage watch keywords"""
    args = args_str.split()[1:]  # Remove 'keywords' subcommand
    
    if len(args) < 2:
        bot.send_message(message.chat.id,
            "**❌ 用法错误**\n\n"
            "正确格式：\n"
            "• `/watch keywords add <ID> <关键词>`\n"
            "• `/watch keywords del <ID> <索引|关键词>`\n"
            "• `/watch keywords list <ID>`",
            reply_to_message_id=message.id)
        return
    
    action = args[0].lower()
    identifier = args[1].strip()
    
    watch_config = load_watch_config()
    user_id = str(message.from_user.id)
    user_watches = get_user_watches(watch_config, user_id)
    
    # Find watch ID
    watch_id = None
    for wid in user_watches.keys():
        if wid.startswith(identifier) or wid == identifier:
            watch_id = wid
            break
    
    if not watch_id:
        bot.send_message(message.chat.id,
            "**❌ 找不到该监控任务**",
            reply_to_message_id=message.id)
        return
    
    if action == "add":
        if len(args) < 3:
            bot.send_message(message.chat.id,
                "**❌ 请指定要添加的关键词**",
                reply_to_message_id=message.id)
            return
        
        keyword = " ".join(args[2:])
        success, msg = add_watch_keyword(watch_config, user_id, watch_id, keyword)
        bot.send_message(message.chat.id,
            f"**{'✅' if success else '❌'} {msg}**",
            reply_to_message_id=message.id)
    
    elif action in ["del", "delete", "remove"]:
        if len(args) < 3:
            bot.send_message(message.chat.id,
                "**❌ 请指定要删除的关键词或索引**",
                reply_to_message_id=message.id)
            return
        
        keyword_or_index = " ".join(args[2:])
        success, msg = remove_watch_keyword(watch_config, user_id, watch_id, keyword_or_index)
        bot.send_message(message.chat.id,
            f"**{'✅' if success else '❌'} {msg}**",
            reply_to_message_id=message.id)
    
    elif action == "list":
        watch = get_watch_by_id(watch_config, user_id, watch_id)
        keywords = watch.get("filters", {}).get("keywords", [])
        
        if not keywords:
            bot.send_message(message.chat.id,
                "**📋 该监控任务没有关键词**\n\n"
                "使用 `/watch keywords add <ID> <关键词>` 添加",
                reply_to_message_id=message.id)
            return
        
        result = f"**📋 监控任务关键词列表：**\n\n"
        result += f"任务ID：`{watch_id[:8]}...`\n\n"
        for idx, kw in enumerate(keywords, 1):
            result += f"{idx}. `{kw}`\n"
        result += f"\n**总计：** {len(keywords)} 个关键词"
        
        bot.send_message(message.chat.id, result, reply_to_message_id=message.id)
    
    else:
        bot.send_message(message.chat.id,
            "**❌ 无效的操作**\n\n"
            "可用操作：add, del, list",
            reply_to_message_id=message.id)


def watch_regex_command(message, args_str):
    """Manage watch regex patterns"""
    args = args_str.split()[1:]  # Remove 'regex' subcommand
    
    if len(args) < 2:
        bot.send_message(message.chat.id,
            "**❌ 用法错误**\n\n"
            "正确格式：\n"
            "• `/watch regex add <ID> <模式>`\n"
            "• `/watch regex del <ID> <索引|模式>`\n"
            "• `/watch regex list <ID>`",
            reply_to_message_id=message.id)
        return
    
    action = args[0].lower()
    identifier = args[1].strip()
    
    watch_config = load_watch_config()
    user_id = str(message.from_user.id)
    user_watches = get_user_watches(watch_config, user_id)
    
    # Find watch ID
    watch_id = None
    for wid in user_watches.keys():
        if wid.startswith(identifier) or wid == identifier:
            watch_id = wid
            break
    
    if not watch_id:
        bot.send_message(message.chat.id,
            "**❌ 找不到该监控任务**",
            reply_to_message_id=message.id)
        return
    
    if action == "add":
        if len(args) < 3:
            bot.send_message(message.chat.id,
                "**❌ 请指定要添加的正则表达式模式**",
                reply_to_message_id=message.id)
            return
        
        pattern = " ".join(args[2:])
        success, msg = add_watch_pattern(watch_config, user_id, watch_id, pattern)
        bot.send_message(message.chat.id,
            f"**{'✅' if success else '❌'} {msg}**",
            reply_to_message_id=message.id)
    
    elif action in ["del", "delete", "remove"]:
        if len(args) < 3:
            bot.send_message(message.chat.id,
                "**❌ 请指定要删除的模式或索引**",
                reply_to_message_id=message.id)
            return
        
        pattern_or_index = " ".join(args[2:])
        success, msg = remove_watch_pattern(watch_config, user_id, watch_id, pattern_or_index)
        bot.send_message(message.chat.id,
            f"**{'✅' if success else '❌'} {msg}**",
            reply_to_message_id=message.id)
    
    elif action == "list":
        watch = get_watch_by_id(watch_config, user_id, watch_id)
        patterns = watch.get("filters", {}).get("patterns", [])
        
        if not patterns:
            bot.send_message(message.chat.id,
                "**📋 该监控任务没有正则表达式模式**\n\n"
                "使用 `/watch regex add <ID> <模式>` 添加",
                reply_to_message_id=message.id)
            return
        
        result = f"**📋 监控任务正则表达式列表：**\n\n"
        result += f"任务ID：`{watch_id[:8]}...`\n\n"
        for idx, pattern in enumerate(patterns, 1):
            result += f"{idx}. `{pattern}`\n"
        result += f"\n**总计：** {len(patterns)} 个模式"
        
        bot.send_message(message.chat.id, result, reply_to_message_id=message.id)
    
    else:
        bot.send_message(message.chat.id,
            "**❌ 无效的操作**\n\n"
            "可用操作：add, del, list",
            reply_to_message_id=message.id)


def watch_preview_command(message, args_str):
    """Preview extraction for a watch"""
    args = args_str.split(maxsplit=2)[1:]  # Remove 'preview' subcommand
    
    if len(args) < 2:
        bot.send_message(message.chat.id,
            "**❌ 用法错误**\n\n"
            "正确格式：`/watch preview <任务ID> <测试文本>`\n\n"
            "示例：`/watch preview abc123 This is a test message`",
            reply_to_message_id=message.id)
        return
    
    identifier = args[0].strip()
    test_text = args[1]
    
    watch_config = load_watch_config()
    user_id = str(message.from_user.id)
    user_watches = get_user_watches(watch_config, user_id)
    
    # Find watch ID
    watch_id = None
    for wid in user_watches.keys():
        if wid.startswith(identifier) or wid == identifier:
            watch_id = wid
            break
    
    if not watch_id:
        bot.send_message(message.chat.id,
            "**❌ 找不到该监控任务**",
            reply_to_message_id=message.id)
        return
    
    watch = get_watch_by_id(watch_config, user_id, watch_id)
    flags = watch.get("flags", {})
    filters = watch.get("filters", {})
    
    keywords = filters.get("keywords", [])
    patterns = filters.get("patterns", [])
    keywords_enabled = flags.get("keywords_enabled", False)
    extract_mode = flags.get("extract_mode", False)
    
    # Compile patterns
    compiled = compile_pattern_list(patterns)
    
    # Check if keywords/patterns are enabled
    if not keywords_enabled:
        bot.send_message(message.chat.id,
            "**⚠️ 该监控任务的关键词过滤已关闭**\n\n"
            "所有消息都会被转发（不进行过滤）",
            reply_to_message_id=message.id)
        return
    
    # Check for matches
    has_matches, snippets = extract_matches(test_text, keywords, compiled)
    
    if not has_matches:
        bot.send_message(message.chat.id,
            "**❌ 没有匹配**\n\n"
            f"该文本不匹配任何过滤器\n\n"
            f"关键词数量：{len(keywords)}\n"
            f"正则模式数量：{len(patterns)}",
            reply_to_message_id=message.id)
        return
    
    # Show results
    result = f"**✅ 预览结果**\n\n"
    result += f"任务ID：`{watch_id[:8]}...`\n"
    result += f"提取模式：{'开启' if extract_mode else '关闭'}\n"
    result += f"找到匹配：{len(snippets)} 个\n\n"
    
    if extract_mode:
        result += "**提取的片段：**\n\n"
        # Format snippets
        metadata = {
            "author": "预览测试",
            "chat_title": "测试频道",
            "link": "https://t.me/test/123"
        }
        formatted = format_snippets_for_telegram(snippets, metadata, include_metadata=True)
        bot.send_message(message.chat.id, result, reply_to_message_id=message.id)
        for msg in formatted:
            bot.send_message(message.chat.id, msg, parse_mode="html")
    else:
        result += "**转发模式：** 完整消息\n\n"
        result += f"原始文本：\n`{test_text[:200]}{'...' if len(test_text) > 200 else ''}`"
        bot.send_message(message.chat.id, result, reply_to_message_id=message.id)


# addre command - add regex pattern
@bot.on_message(filters.command(["addre"]))
def add_regex(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
    global compiled_patterns
    
    text = message.text.strip()
    parts = text.split(maxsplit=1)
    
    if len(parts) < 2:
        bot.send_message(message.chat.id, "**❌ 用法错误**\n\n正确格式：`/addre <pattern>`\n\n示例：\n• `/addre /urgent|important/i`\n• `/addre bitcoin`\n• `/addre /\\d{3}-\\d{4}/`", reply_to_message_id=message.id)
        return
    
    pattern_str = parts[1].strip()
    
    # Check pattern length
    if len(pattern_str) > MAX_PATTERN_LENGTH:
        bot.send_message(message.chat.id, f"**❌ 模式太长**\n\n最大长度：{MAX_PATTERN_LENGTH} 字符", reply_to_message_id=message.id)
        return
    
    # Load current config
    filter_config = load_filter_config()
    patterns = filter_config.get("patterns", [])
    
    # Check pattern count
    if len(patterns) >= MAX_PATTERN_COUNT:
        bot.send_message(message.chat.id, f"**❌ 已达到最大模式数量**\n\n最大数量：{MAX_PATTERN_COUNT}", reply_to_message_id=message.id)
        return
    
    # Check if pattern already exists
    if pattern_str in patterns:
        bot.send_message(message.chat.id, "**⚠️ 该模式已存在**", reply_to_message_id=message.id)
        return
    
    # Try to compile the pattern
    try:
        pattern, flags = parse_regex_pattern(pattern_str)
        compiled_re = re.compile(pattern, flags)
    except re.error as e:
        bot.send_message(message.chat.id, f"**❌ 无效的正则表达式**\n\n错误：`{str(e)}`\n\n请检查你的模式语法", reply_to_message_id=message.id)
        return
    
    # Add pattern to config
    patterns.append(pattern_str)
    filter_config["patterns"] = patterns
    save_filter_config(filter_config)
    
    # Recompile all patterns
    compiled_patterns = compile_patterns()
    
    bot.send_message(message.chat.id, f"**✅ 已添加正则表达式模式**\n\n模式：`{pattern_str}`\n编译后的模式：`{pattern}`\n\n使用 `/listre` 查看所有模式", reply_to_message_id=message.id)


# delre command - delete regex pattern
@bot.on_message(filters.command(["delre"]))
def delete_regex(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
    global compiled_patterns
    
    text = message.text.strip()
    parts = text.split(maxsplit=1)
    
    if len(parts) < 2:
        bot.send_message(message.chat.id, "**❌ 用法错误**\n\n正确格式：`/delre <index>`\n\n使用 `/listre` 查看模式索引", reply_to_message_id=message.id)
        return
    
    # Load current config
    filter_config = load_filter_config()
    patterns = filter_config.get("patterns", [])
    
    if not patterns:
        bot.send_message(message.chat.id, "**❌ 没有任何正则表达式模式**", reply_to_message_id=message.id)
        return
    
    try:
        index = int(parts[1].strip())
    except ValueError:
        bot.send_message(message.chat.id, "**❌ 索引必须是数字**", reply_to_message_id=message.id)
        return
    
    if index < 1 or index > len(patterns):
        bot.send_message(message.chat.id, f"**❌ 索引无效**\n\n请输入 1 到 {len(patterns)} 之间的数字", reply_to_message_id=message.id)
        return
    
    # Remove pattern
    removed_pattern = patterns.pop(index - 1)
    filter_config["patterns"] = patterns
    save_filter_config(filter_config)
    
    # Recompile all patterns
    compiled_patterns = compile_patterns()
    
    bot.send_message(message.chat.id, f"**✅ 已删除正则表达式模式**\n\n模式：`{removed_pattern}`", reply_to_message_id=message.id)


# listre command - list regex patterns
@bot.on_message(filters.command(["listre"]))
def list_regex(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
    filter_config = load_filter_config()
    patterns = filter_config.get("patterns", [])
    
    if not patterns:
        bot.send_message(message.chat.id, "**📋 没有设置任何正则表达式模式**\n\n使用 `/addre <pattern>` 来添加模式", reply_to_message_id=message.id)
        return
    
    result = "**📋 正则表达式模式列表：**\n\n"
    for idx, pattern_str in enumerate(patterns, 1):
        result += f"{idx}. `{pattern_str}`\n"
        
        # Check if pattern compiled successfully
        for orig, compiled, error in compiled_patterns:
            if orig == pattern_str:
                if error:
                    result += f"   ⚠️ 错误：`{error}`\n"
                else:
                    result += f"   ✅ 已编译\n"
                break
    
    result += f"\n**总计：** {len(patterns)} 个模式"
    bot.send_message(message.chat.id, result, reply_to_message_id=message.id)


# testre command - test regex pattern
@bot.on_message(filters.command(["testre"]))
def test_regex(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
    text = message.text.strip()
    parts = text.split(maxsplit=2)
    
    if len(parts) < 3:
        bot.send_message(message.chat.id, "**❌ 用法错误**\n\n正确格式：`/testre <pattern> <text>`\n\n示例：\n• `/testre /\\d{3}-\\d{4}/ 123-4567`\n• `/testre bitcoin This is a bitcoin message`", reply_to_message_id=message.id)
        return
    
    pattern_str = parts[1].strip()
    test_text = parts[2].strip()
    
    # Try to compile and test the pattern
    try:
        pattern, flags = parse_regex_pattern(pattern_str)
        compiled_re = re.compile(pattern, flags)
    except re.error as e:
        bot.send_message(message.chat.id, f"**❌ 无效的正则表达式**\n\n错误：`{str(e)}`", reply_to_message_id=message.id)
        return
    
    # Test the pattern
    match = safe_regex_match(compiled_re, test_text)
    
    if match:
        result = "**✅ 匹配成功！**\n\n"
        result += f"模式：`{pattern_str}`\n"
        result += f"测试文本：`{test_text}`\n\n"
        result += f"匹配的文本：`{match.group()}`\n"
        result += f"位置：{match.start()} - {match.end()}\n"
        
        # Show groups if any
        if match.groups():
            result += f"\n**捕获组：**\n"
            for i, group in enumerate(match.groups(), 1):
                result += f"{i}. `{group}`\n"
    else:
        result = "**❌ 没有匹配**\n\n"
        result += f"模式：`{pattern_str}`\n"
        result += f"测试文本：`{test_text}`"
    
    bot.send_message(message.chat.id, result, reply_to_message_id=message.id)


# mode command - manage extraction mode
@bot.on_message(filters.command(["mode"]))
def mode_command(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
    text = message.text.strip()
    parts = text.split(maxsplit=2)
    
    if len(parts) == 1 or (len(parts) == 2 and parts[1].lower() == "show"):
        filter_config = load_filter_config()
        extract_mode = filter_config.get("extract_mode", False)
        status = "✅ 开启" if extract_mode else "❌ 关闭"
        
        result = f"**📊 提取模式状态**\n\n"
        result += f"提取模式: {status}\n\n"
        result += "**说明:**\n"
        result += "• 开启时: 仅转发匹配的文本片段\n"
        result += "• 关闭时: 转发完整消息（默认行为）\n\n"
        result += "使用 `/mode extract on` 或 `/mode extract off` 来切换"
        
        bot.send_message(message.chat.id, result, reply_to_message_id=message.id)
    
    elif len(parts) >= 3 and parts[1].lower() == "extract":
        action = parts[2].lower()
        
        if action not in ["on", "off"]:
            bot.send_message(message.chat.id, "**❌ 无效参数**\n\n使用 `on` 或 `off`", reply_to_message_id=message.id)
            return
        
        filter_config = load_filter_config()
        new_value = (action == "on")
        filter_config["extract_mode"] = new_value
        save_filter_config(filter_config)
        
        status = "✅ 已开启" if new_value else "❌ 已关闭"
        result = f"**{status} 提取模式**\n\n"
        
        if new_value:
            result += "现在监控的消息将只转发匹配的文本片段。\n\n"
            result += "**提示:** 使用 `/preview <text>` 测试提取效果"
        else:
            result += "现在监控的消息将转发完整内容（默认行为）。"
        
        bot.send_message(message.chat.id, result, reply_to_message_id=message.id)
    
    else:
        bot.send_message(message.chat.id, "**❌ 用法错误**\n\n可用命令：\n• `/mode show` - 查看当前模式\n• `/mode extract on` - 开启提取模式\n• `/mode extract off` - 关闭提取模式", reply_to_message_id=message.id)


# preview command - test extraction
@bot.on_message(filters.command(["preview"]))
def preview_command(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
    text = message.text.strip()
    parts = text.split(maxsplit=1)
    
    if len(parts) < 2:
        bot.send_message(message.chat.id, "**❌ 用法错误**\n\n正确格式：`/preview <text>`\n\n示例：\n• `/preview This is an urgent message about bitcoin`", reply_to_message_id=message.id)
        return
    
    test_text = parts[1].strip()
    
    # Load filters
    filter_config = load_filter_config()
    global_keywords = filter_config.get("keywords", [])
    
    # Check for matches and extract snippets
    has_matches, snippets = extract_matches(test_text, global_keywords, compiled_patterns)
    
    if not has_matches:
        result = "**❌ 没有匹配**\n\n"
        result += f"测试文本: `{test_text}`\n\n"
        result += "该文本不匹配任何全局关键词或正则表达式模式。\n\n"
        result += "**提示:**\n"
        result += "• 使用 `/listre` 查看正则表达式模式\n"
        result += "• 注意：监控任务的白名单/黑名单单独检查"
        bot.send_message(message.chat.id, result, reply_to_message_id=message.id)
        return
    
    # Format snippets with metadata
    metadata = {
        "author": "预览测试",
        "chat_title": "测试频道",
        "link": "https://t.me/test/123"
    }
    
    formatted_messages = format_snippets_for_telegram(snippets, metadata, include_metadata=True)
    
    if not formatted_messages:
        bot.send_message(message.chat.id, "**⚠️ 提取失败**\n\n无法从文本中提取片段", reply_to_message_id=message.id)
        return
    
    # Send preview header
    header = "**✅ 预览结果**\n\n"
    header += f"原始文本长度: {len(test_text)} 字符\n"
    header += f"找到匹配: {len(snippets)} 个\n"
    header += f"生成消息: {len(formatted_messages)} 条\n\n"
    header += "─" * 30 + "\n\n"
    
    bot.send_message(message.chat.id, header, reply_to_message_id=message.id)
    
    # Send formatted messages
    for msg in formatted_messages:
        bot.send_message(message.chat.id, msg, parse_mode="html")


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

# Auto-forward handler for watched channels (per-watch filters)
if acc is not None:
    @acc.on_message(filters.channel | filters.group)
    def auto_forward(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
        try:
            watch_config = load_watch_config()
            source_chat_id = str(message.chat.id)
            
            # Find all watches for this source
            result = get_watch_by_source(watch_config, source_chat_id)
            if not result:
                return
            
            user_id, watch_id, watch_data = result
            
            # Check if watch is enabled
            if not watch_data.get("enabled", True):
                return
            
            # Get watch configuration
            dest_chat_id = watch_data.get("dest")
            flags = watch_data.get("flags", {})
            filters_data = watch_data.get("filters", {})
            
            extract_mode = flags.get("extract_mode", False)
            keywords_enabled = flags.get("keywords_enabled", False)
            preserve_source = flags.get("preserve_source", False)
            
            keywords = filters_data.get("keywords", [])
            patterns = filters_data.get("patterns", [])
            
            # Handle legacy whitelist/blacklist if present
            legacy_whitelist = watch_data.get("_legacy_whitelist", [])
            legacy_blacklist = watch_data.get("_legacy_blacklist", [])
            
            # Build text to check: include message text, caption, and document filename
            message_text = message.text or message.caption or ""
            
            # Add document filename if present
            if message.document and hasattr(message.document, 'file_name') and message.document.file_name:
                message_text += " " + message.document.file_name
            
            # Handle legacy whitelist/blacklist (for backward compatibility)
            if legacy_whitelist:
                if not any(keyword.lower() in message_text.lower() for keyword in legacy_whitelist):
                    return
            
            if legacy_blacklist:
                if any(keyword.lower() in message_text.lower() for keyword in legacy_blacklist):
                    return
            
            # Apply per-watch filters if keywords_enabled
            if keywords_enabled and (keywords or patterns):
                # Compile this watch's patterns
                compiled = compile_pattern_list(patterns)
                
                # Check for matches
                has_matches, snippets = extract_matches(message_text, keywords, compiled)
                
                # If filters are enabled but no match, skip
                if not has_matches:
                    return
                
                # If extract mode is on, send extracted snippets
                if extract_mode:
                    try:
                        # Build metadata for snippets
                        metadata = {}
                        
                        # Get author name
                        if message.from_user:
                            if message.from_user.first_name:
                                author = message.from_user.first_name
                                if message.from_user.last_name:
                                    author += " " + message.from_user.last_name
                                metadata["author"] = author
                            elif message.from_user.username:
                                metadata["author"] = "@" + message.from_user.username
                        
                        # Get chat title
                        if message.chat:
                            if message.chat.title:
                                metadata["chat_title"] = message.chat.title
                            elif message.chat.username:
                                metadata["chat_title"] = "@" + message.chat.username
                        
                        # Generate message link
                        if message.chat.username:
                            metadata["link"] = f"https://t.me/{message.chat.username}/{message.id}"
                        else:
                            # Private channel/group
                            chat_id_str = str(message.chat.id).replace("-100", "")
                            metadata["link"] = f"https://t.me/c/{chat_id_str}/{message.id}"
                        
                        # Format snippets for telegram
                        formatted_messages = format_snippets_for_telegram(snippets, metadata, include_metadata=True)
                        
                        # Send formatted messages
                        for formatted_msg in formatted_messages:
                            if dest_chat_id == "me":
                                acc.send_message("me", formatted_msg, parse_mode="html")
                            else:
                                acc.send_message(int(dest_chat_id), formatted_msg, parse_mode="html")
                    except Exception as e:
                        print(f"Error sending extracted snippets: {e}")
                    return
            
            # Forward the full message (either filters disabled or extract mode off)
            try:
                if preserve_source:
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
                print(f"Error forwarding message: {e}")
        except Exception as e:
            print(f"Error in auto_forward: {e}")


# infinty polling
bot.run()
if acc is not None:
    acc.stop()
