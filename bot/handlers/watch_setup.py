"""
Watch configuration and setup handlers

Architecture: Uses new layered architecture
- src/core/container for service access
"""
from typing import List, Optional
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from pyrogram.errors import ChannelPrivate, UsernameInvalid

from bot.handlers.instances import get_bot_instance, get_acc_instance
from bot.utils.status import user_states

# New architecture imports
from src.core.container import get_watch_service


def show_filter_options(chat_id: int, message_id: int, user_id: str) -> None:
    """Show filter options for forward mode"""
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


def show_filter_options_single(chat_id: int, message_id: int, user_id: str) -> None:
    """Show filter options for record mode"""
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


def show_preserve_source_options(chat_id: int, message_id: int, user_id: str) -> None:
    """Show preserve source options"""
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


def show_forward_mode_options(
    chat_id: int,
    message_id: int,
    user_id: str,
    whitelist: List[str],
    blacklist: List[str],
    whitelist_regex: List[str],
    blacklist_regex: List[str],
    preserve_source: bool
) -> None:
    """Show forward mode options"""
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


def show_dn_append_options(chat_id: int, message_id: int, user_id: str, forward_mode: str) -> None:
    """Show DN append options for forward mode"""
    bot = get_bot_instance()

    source_name = user_states[user_id].get("source_name", "未知")
    dest_name = user_states[user_id].get("dest_name", "未知")

    user_states[user_id]["forward_mode"] = forward_mode

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ 是", callback_data="dn_append_yes")],
        [InlineKeyboardButton("❌ 否（默认）", callback_data="dn_append_no")],
        [InlineKeyboardButton("🔙 返回", callback_data="back_to_forward_mode")]
    ])

    text = "**➕ 添加监控任务**\n\n"
    text += f"来源：`{source_name}`\n"
    text += f"目标：`{dest_name}`\n"
    text += f"转发模式：{'🎯 提取模式' if forward_mode == 'extract' else '📦 完整转发'}\n\n"
    # 已删除 show_dn_append_options 函数（不再使用DN补全功能）
    pass


def complete_watch_setup(
    chat_id: int,
    message_id: int,
    user_id: str,
    whitelist: List[str],
    blacklist: List[str],
    whitelist_regex: List[str],
    blacklist_regex: List[str],
    preserve_source: bool,
    forward_mode: str,
    extract_patterns: List[str]
) -> None:
    """Complete watch setup for forward mode"""
    bot = get_bot_instance()

    try:
        source_id = user_states[user_id]["source_id"]
        source_name = user_states[user_id]["source_name"]
        dest_id = user_states[user_id]["dest_id"]
        dest_name = user_states[user_id]["dest_name"]

        # 使用 WatchService 获取和保存配置
        watch_service = get_watch_service()
        watch_config = watch_service.get_all_configs_dict()

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
        watch_service.save_config_dict(watch_config)

        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回监控列表", callback_data="watch_list")]])

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
        # Note: append_dn feature has been removed
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


def complete_watch_setup_single(
    chat_id: int,
    message_id: int,
    user_id: str,
    whitelist: List[str],
    blacklist: List[str],
    whitelist_regex: List[str],
    blacklist_regex: List[str]
) -> None:
    """Complete watch setup for record mode"""
    bot = get_bot_instance()
    
    try:
        source_id = user_states[user_id]["source_id"]
        source_name = user_states[user_id]["source_name"]
        
        # 使用 WatchService 获取和保存配置
        watch_service = get_watch_service()
        watch_config = watch_service.get_all_configs_dict()

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
        watch_service.save_config_dict(watch_config)
        
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回监控列表", callback_data="watch_list")]])

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


def handle_add_source(message: Message, user_id: str) -> None:
    """Handle add source step"""
    bot = get_bot_instance()
    acc = get_acc_instance()
    
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
            [InlineKeyboardButton("📝 记录模式", callback_data="watch_mode_record")],
            [InlineKeyboardButton("➡️ 转发模式", callback_data="watch_mode_forward")],
            [InlineKeyboardButton("❌ 取消", callback_data="menu_watch")]
        ])

        text = "**➕ 添加监控任务**\n\n"
        text += f"✅ 来源已设置：`{source_name}`\n\n"
        text += "**步骤 2：** 选择监控模式\n\n"
        text += "📝 **记录模式** - 只监控这一个频道，消息保存到网页笔记\n"
        text += "➡️ **转发模式** - 从这个频道转发消息到另一个频道/群组"

        bot.send_message(message.chat.id, text, reply_markup=keyboard)
    
    except ChannelPrivate:
        bot.send_message(message.chat.id, "**❌ 无法访问该频道/群组**\n\n请确保账号已加入")
    except UsernameInvalid:
        bot.send_message(message.chat.id, "**❌ 频道/群组用户名无效**\n\n请检查输入")
    except Exception as e:
        bot.send_message(message.chat.id, f"**❌ 错误：** `{str(e)}`")


def handle_add_dest(message: Message, user_id: str) -> None:
    """Handle add destination step"""
    bot = get_bot_instance()
    acc = get_acc_instance()

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
