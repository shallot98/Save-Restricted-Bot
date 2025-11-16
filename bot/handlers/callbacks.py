"""
Callback query handlers for bot interactions
"""
import pyrogram
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import ChannelPrivate, UsernameInvalid
import re

from config import load_watch_config, save_watch_config
from bot.handlers import get_bot_instance, get_acc_instance
from bot.utils.status import get_user_state, set_user_state, clear_user_state, update_user_state, user_states


def show_filter_options(chat_id, message_id, user_id):
    """Show filter options menu for forward mode"""
    bot = get_bot_instance()
    
    source_name = user_states[user_id].get("source_name", "未知")
    dest_name = user_states[user_id].get("dest_name", "未知")
    
    # Get current filter settings
    whitelist = user_states[user_id].get("whitelist", [])
    blacklist = user_states[user_id].get("blacklist", [])
    whitelist_regex = user_states[user_id].get("whitelist_regex", [])
    blacklist_regex = user_states[user_id].get("blacklist_regex", [])
    
    # Build filter status text
    filter_status = "📋 **已设置的规则：**\n"
    has_filters = False
    
    if whitelist:
        filter_status += f"🟢 关键词白名单: `{', '.join(whitelist)}`\n"
        has_filters = True
    
    if blacklist:
        filter_status += f"🔴 关键词黑名单: `{', '.join(blacklist)}`\n"
        has_filters = True
    
    if whitelist_regex:
        filter_status += f"🟢 正则白名单: `{', '.join(whitelist_regex)}`\n"
        has_filters = True
    
    if blacklist_regex:
        filter_status += f"🔴 正则黑名单: `{', '.join(blacklist_regex)}`\n"
        has_filters = True
    
    if not has_filters:
        filter_status = "📋 **暂未设置过滤规则**\n"
    
    # Build keyboard with new options
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🟢 关键词白名单", callback_data="filter_whitelist")],
        [InlineKeyboardButton("🔴 关键词黑名单", callback_data="filter_blacklist")],
        [InlineKeyboardButton("🟢 正则白名单", callback_data="filter_regex_whitelist")],
        [InlineKeyboardButton("🔴 正则黑名单", callback_data="filter_regex_blacklist")],
        [InlineKeyboardButton("✅ 完成设置", callback_data="filter_done")],
        [InlineKeyboardButton("🗑️ 清空规则", callback_data="clear_filters")],
        [InlineKeyboardButton("❌ 取消", callback_data="menu_watch")]
    ])
    
    text = "**➕ 添加监控任务**\n\n"
    text += f"来源：`{source_name}`\n"
    text += f"目标：`{dest_name}`\n\n"
    text += f"{filter_status}\n"
    text += "**步骤 3：** 是否需要设置/修改过滤规则？\n\n"
    text += "🟢 **关键词白名单** - 包含关键词才转发\n"
    text += "🔴 **关键词黑名单** - 包含关键词不转发\n"
    text += "🟢 **正则白名单** - 匹配正则才转发\n"
    text += "🔴 **正则黑名单** - 匹配正则不转发\n\n"
    text += "✅ **完成设置** - 保存并继续\n"
    text += "🗑️ **清空规则** - 清空所有过滤规则\n\n"
    text += "💡 可以设置多种规则，黑名单优先于白名单"
    
    try:
        bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)
    except:
        bot.send_message(chat_id, text, reply_markup=keyboard)


def show_filter_options_single(chat_id, message_id, user_id):
    """Show filter options menu for record mode"""
    bot = get_bot_instance()
    
    source_name = user_states[user_id].get("source_name", "未知")
    
    # Get current filter settings
    whitelist = user_states[user_id].get("whitelist", [])
    blacklist = user_states[user_id].get("blacklist", [])
    whitelist_regex = user_states[user_id].get("whitelist_regex", [])
    blacklist_regex = user_states[user_id].get("blacklist_regex", [])
    
    # Build filter status text
    filter_status = "📋 **已设置的规则：**\n"
    has_filters = False
    
    if whitelist:
        filter_status += f"🟢 关键词白名单: `{', '.join(whitelist)}`\n"
        has_filters = True
    
    if blacklist:
        filter_status += f"🔴 关键词黑名单: `{', '.join(blacklist)}`\n"
        has_filters = True
    
    if whitelist_regex:
        filter_status += f"🟢 正则白名单: `{', '.join(whitelist_regex)}`\n"
        has_filters = True
    
    if blacklist_regex:
        filter_status += f"🔴 正则黑名单: `{', '.join(blacklist_regex)}`\n"
        has_filters = True
    
    if not has_filters:
        filter_status = "📋 **暂未设置过滤规则**\n"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🟢 关键词白名单", callback_data="filter_whitelist")],
        [InlineKeyboardButton("🔴 关键词黑名单", callback_data="filter_blacklist")],
        [InlineKeyboardButton("🟢 正则白名单", callback_data="filter_regex_whitelist")],
        [InlineKeyboardButton("🔴 正则黑名单", callback_data="filter_regex_blacklist")],
        [InlineKeyboardButton("✅ 完成设置", callback_data="filter_done_single")],
        [InlineKeyboardButton("🗑️ 清空规则", callback_data="clear_filters_single")],
        [InlineKeyboardButton("❌ 取消", callback_data="menu_watch")]
    ])
    
    text = "**➕ 添加监控任务（记录模式）**\n\n"
    text += f"来源：`{source_name}`\n"
    text += f"模式：📝 **记录模式**（保存到网页笔记）\n\n"
    text += f"{filter_status}\n"
    text += "**步骤 3：** 是否需要设置/修改过滤规则？\n\n"
    text += "🟢 **关键词白名单** - 包含关键词才记录\n"
    text += "🔴 **关键词黑名单** - 包含关键词不记录\n"
    text += "🟢 **正则白名单** - 匹配正则才记录\n"
    text += "🔴 **正则黑名单** - 匹配正则不记录\n\n"
    text += "✅ **完成设置** - 保存并继续\n"
    text += "🗑️ **清空规则** - 清空所有过滤规则\n\n"
    text += "💡 可以设置多种规则，黑名单优先于白名单"
    
    try:
        bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)
    except:
        bot.send_message(chat_id, text, reply_markup=keyboard)


def show_preserve_source_options(chat_id, message_id, user_id):
    """Show preserve source options menu"""
    bot = get_bot_instance()
    
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
    """Show forward mode options menu"""
    bot = get_bot_instance()
    
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
    """Complete watch setup for forward mode"""
    bot = get_bot_instance()
    
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
    """Complete watch setup for record mode"""
    bot = get_bot_instance()
    
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
    """Handle add source flow"""
    bot = get_bot_instance()
    acc = get_acc_instance()
    
    if acc is None:
        bot.send_message(message.chat.id, "**❌ 需要配置 String Session 才能使用监控功能**")
        return
    
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
    """Handle add destination flow"""
    bot = get_bot_instance()
    acc = get_acc_instance()
    
    if acc is None:
        bot.send_message(message.chat.id, "**❌ 需要配置 String Session 才能使用监控功能**")
        return
    
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


def callback_handler(client: pyrogram.client.Client, callback_query: CallbackQuery):
    """Main callback query handler"""
    bot = get_bot_instance()
    acc = get_acc_instance()
    
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
        
        elif data == "filter_done":
            if user_id not in user_states:
                callback_query.answer("❌ 会话已过期", show_alert=True)
                return
            
            # Continue to next step (preserve source options)
            show_preserve_source_options(chat_id, message_id, user_id)
            callback_query.answer("✅ 过滤规则已保存")
        
        elif data == "filter_done_single":
            if user_id not in user_states:
                callback_query.answer("❌ 会话已过期", show_alert=True)
                return
            
            whitelist = user_states[user_id].get("whitelist", [])
            blacklist = user_states[user_id].get("blacklist", [])
            whitelist_regex = user_states[user_id].get("whitelist_regex", [])
            blacklist_regex = user_states[user_id].get("blacklist_regex", [])
            
            msg = bot.send_message(chat_id, "⏳ 正在完成设置...")
            bot.delete_messages(chat_id, [message_id])
            complete_watch_setup_single(msg.chat.id, msg.id, user_id, whitelist, blacklist, whitelist_regex, blacklist_regex)
            callback_query.answer("✅ 过滤规则已保存")
        
        elif data == "clear_filters":
            if user_id not in user_states:
                callback_query.answer("❌ 会话已过期", show_alert=True)
                return
            
            # Clear all filter rules
            user_states[user_id]["whitelist"] = []
            user_states[user_id]["blacklist"] = []
            user_states[user_id]["whitelist_regex"] = []
            user_states[user_id]["blacklist_regex"] = []
            
            # Refresh the menu to show cleared filters
            show_filter_options(chat_id, message_id, user_id)
            callback_query.answer("✅ 已清空所有过滤规则")
        
        elif data == "clear_filters_single":
            if user_id not in user_states:
                callback_query.answer("❌ 会话已过期", show_alert=True)
                return
            
            # Clear all filter rules
            user_states[user_id]["whitelist"] = []
            user_states[user_id]["blacklist"] = []
            user_states[user_id]["whitelist_regex"] = []
            user_states[user_id]["blacklist_regex"] = []
            
            # Refresh the menu to show cleared filters
            show_filter_options_single(chat_id, message_id, user_id)
            callback_query.answer("✅ 已清空所有过滤规则")
        
        # Handle filter type selections
        elif data == "filter_whitelist":
            user_states[user_id]["action"] = "add_whitelist"
            
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("❌ 取消", callback_data="menu_watch")]])
            
            text = "**➕ 添加监控任务**\n\n"
            text += "**步骤 3：设置关键词白名单**\n\n"
            text += "请发送关键词，用逗号分隔\n\n"
            text += "示例：`比特币,以太坊,区块链`\n\n"
            text += "💡 只有包含这些关键词的消息才会被转发"
            
            bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)
            callback_query.answer()
        
        elif data == "filter_blacklist":
            user_states[user_id]["action"] = "add_blacklist"
            
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("❌ 取消", callback_data="menu_watch")]])
            
            text = "**➕ 添加监控任务**\n\n"
            text += "**步骤 3：设置关键词黑名单**\n\n"
            text += "请发送关键词，用逗号分隔\n\n"
            text += "示例：`广告,推广,spam`\n\n"
            text += "💡 包含这些关键词的消息不会被转发"
            
            bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)
            callback_query.answer()
        
        elif data == "filter_regex_whitelist":
            user_states[user_id]["action"] = "add_regex_whitelist"
            
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("❌ 取消", callback_data="menu_watch")]])
            
            text = "**➕ 添加监控任务**\n\n"
            text += "**步骤 3：设置正则白名单**\n\n"
            text += "请发送正则表达式，用逗号分隔\n\n"
            text += "示例：`https?://[^\\s]+,\\d{6,}`\n\n"
            text += "💡 只有匹配这些正则的消息才会被转发"
            
            bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)
            callback_query.answer()
        
        elif data == "filter_regex_blacklist":
            user_states[user_id]["action"] = "add_regex_blacklist"
            
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("❌ 取消", callback_data="menu_watch")]])
            
            text = "**➕ 添加监控任务**\n\n"
            text += "**步骤 3：设置正则黑名单**\n\n"
            text += "请发送正则表达式，用逗号分隔\n\n"
            text += "示例：`广告.*推广,spam`\n\n"
            text += "💡 匹配这些正则的消息不会被转发"
            
            bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)
            callback_query.answer()
        
        # Handle preserve source options
        elif data == "preserve_yes":
            if user_id not in user_states:
                callback_query.answer("❌ 会话已过期", show_alert=True)
                return
            
            whitelist = user_states[user_id].get("whitelist", [])
            blacklist = user_states[user_id].get("blacklist", [])
            whitelist_regex = user_states[user_id].get("whitelist_regex", [])
            blacklist_regex = user_states[user_id].get("blacklist_regex", [])
            
            show_forward_mode_options(chat_id, message_id, user_id, whitelist, blacklist, whitelist_regex, blacklist_regex, True)
            callback_query.answer()
        
        elif data == "preserve_no":
            if user_id not in user_states:
                callback_query.answer("❌ 会话已过期", show_alert=True)
                return
            
            whitelist = user_states[user_id].get("whitelist", [])
            blacklist = user_states[user_id].get("blacklist", [])
            whitelist_regex = user_states[user_id].get("whitelist_regex", [])
            blacklist_regex = user_states[user_id].get("blacklist_regex", [])
            
            show_forward_mode_options(chat_id, message_id, user_id, whitelist, blacklist, whitelist_regex, blacklist_regex, False)
            callback_query.answer()
        
        # Handle forward mode options
        elif data == "fwdmode_full":
            if user_id not in user_states:
                callback_query.answer("❌ 会话已过期", show_alert=True)
                return
            
            whitelist = user_states[user_id].get("whitelist", [])
            blacklist = user_states[user_id].get("blacklist", [])
            whitelist_regex = user_states[user_id].get("whitelist_regex", [])
            blacklist_regex = user_states[user_id].get("blacklist_regex", [])
            preserve_source = user_states[user_id].get("preserve_source", False)
            
            msg = bot.send_message(chat_id, "⏳ 正在完成设置...")
            bot.delete_messages(chat_id, [message_id])
            complete_watch_setup(msg.chat.id, msg.id, user_id, whitelist, blacklist, whitelist_regex, blacklist_regex, preserve_source, "full", [])
            callback_query.answer()
        
        elif data == "fwdmode_extract":
            if user_id not in user_states:
                callback_query.answer("❌ 会话已过期", show_alert=True)
                return
            
            user_states[user_id]["action"] = "add_extract_patterns"
            
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("❌ 取消", callback_data="menu_watch")]])
            
            text = "**➕ 添加监控任务**\n\n"
            text += "**最后一步：设置提取规则**\n\n"
            text += "请发送正则表达式（用于提取内容），用逗号分隔\n\n"
            text += "示例：`https?://[^\\s]+,\\d{6,}`\n\n"
            text += "💡 Bot将提取匹配的内容，然后发送到目标"
            
            bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)
            callback_query.answer()
    
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"⚠️ callback_handler 错误: {type(e).__name__}: {e}", exc_info=True)
        callback_query.answer(f"❌ 错误: {str(e)}", show_alert=True)
