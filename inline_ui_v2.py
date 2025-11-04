"""
Inline keyboard UI handlers with centralized callback routing (v2)
"""

import logging
from typing import Dict, List
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from callback_router import router, build_callback_data, validate_callback_length
from watch_manager import (
    load_watch_config,
    get_user_watches,
    get_watch_by_id,
    update_watch_forward_mode,
    update_watch_preserve_source,
    update_watch_enabled,
    add_watch_keyword,
    remove_watch_keyword,
    add_watch_pattern,
    remove_watch_pattern
)
from peer_utils import ensure_peer

logger = logging.getLogger(__name__)

# User input state tracking
user_input_states = {}


# ============================================================================
# Keyboard builders using new callback format
# ============================================================================

def get_watch_list_keyboard(user_watches: Dict, page: int = 1, watches_per_page: int = 5) -> InlineKeyboardMarkup:
    """Generate paginated list of watches"""
    keyboard = []
    watch_items = list(user_watches.items())
    
    # Calculate pagination
    total_pages = (len(watch_items) + watches_per_page - 1) // watches_per_page
    start_idx = (page - 1) * watches_per_page
    end_idx = min(start_idx + watches_per_page, len(watch_items))
    
    # Add watch buttons
    for watch_id, watch_data in watch_items[start_idx:end_idx]:
        source = watch_data.get("source", {})
        if isinstance(source, dict):
            source_title = source.get("title", "Unknown")
        else:
            source_title = "Unknown"
        
        enabled = watch_data.get("enabled", True)
        status_icon = "✅" if enabled else "❌"
        
        callback_data = build_callback_data(watch_id[:8], sec="d", act="show")
        keyboard.append([
            InlineKeyboardButton(
                f"{status_icon} {source_title}",
                callback_data=callback_data
            )
        ])
    
    # Pagination buttons
    if total_pages > 1:
        nav_buttons = []
        if page > 1:
            nav_buttons.append(
                InlineKeyboardButton(
                    "⬅️",
                    callback_data=build_callback_data("list", act="page", p=page-1)
                )
            )
        nav_buttons.append(
            InlineKeyboardButton(
                f"{page}/{total_pages}",
                callback_data=build_callback_data("noop")
            )
        )
        if page < total_pages:
            nav_buttons.append(
                InlineKeyboardButton(
                    "➡️",
                    callback_data=build_callback_data("list", act="page", p=page+1)
                )
            )
        keyboard.append(nav_buttons)
    
    return InlineKeyboardMarkup(keyboard)


def get_watch_detail_keyboard(watch_id: str, watch_data: Dict) -> InlineKeyboardMarkup:
    """Generate inline keyboard for watch detail view"""
    
    forward_mode = watch_data.get("forward_mode", "full")
    preserve_source = watch_data.get("preserve_source", False)
    enabled = watch_data.get("enabled", True)
    
    monitor_filters = watch_data.get("monitor_filters", {})
    extract_filters = watch_data.get("extract_filters", {})
    
    monitor_kw_count = len(monitor_filters.get("keywords", []))
    monitor_re_count = len(monitor_filters.get("patterns", []))
    extract_kw_count = len(extract_filters.get("keywords", []))
    extract_re_count = len(extract_filters.get("patterns", []))
    
    # Use short watch_id for callback data
    short_id = watch_id[:8]
    
    keyboard = []
    
    # Mode selection (mutually exclusive)
    keyboard.append([
        InlineKeyboardButton(
            f"{'✅' if forward_mode == 'full' else '⬜'} Full",
            callback_data=build_callback_data(short_id, sec="d", act="mode", m="full")
        ),
        InlineKeyboardButton(
            f"{'✅' if forward_mode == 'extract' else '⬜'} Extract",
            callback_data=build_callback_data(short_id, sec="d", act="mode", m="extract")
        )
    ])
    
    # Monitor filters section
    keyboard.append([
        InlineKeyboardButton(
            f"📊 监控过滤器 ({monitor_kw_count}+{monitor_re_count})",
            callback_data=build_callback_data(short_id, sec="m", act="menu")
        )
    ])
    
    # Extract filters section
    keyboard.append([
        InlineKeyboardButton(
            f"✂️ 提取过滤器 ({extract_kw_count}+{extract_re_count})",
            callback_data=build_callback_data(short_id, sec="e", act="menu")
        )
    ])
    
    # Preserve source toggle
    keyboard.append([
        InlineKeyboardButton(
            f"{'✅' if preserve_source else '❌'} 保留来源",
            callback_data=build_callback_data(short_id, sec="d", act="preserve")
        )
    ])
    
    # Enable/Disable
    keyboard.append([
        InlineKeyboardButton(
            f"{'🔵 禁用' if enabled else '🟢 启用'}",
            callback_data=build_callback_data(short_id, sec="d", act="enabled")
        )
    ])
    
    # Preview & Delete
    keyboard.append([
        InlineKeyboardButton(
            "🔍 预览",
            callback_data=build_callback_data(short_id, sec="d", act="preview")
        ),
        InlineKeyboardButton(
            "🗑️ 删除",
            callback_data=build_callback_data(short_id, sec="d", act="del_conf")
        )
    ])
    
    # Back button
    keyboard.append([
        InlineKeyboardButton(
            "⬅️ 返回列表",
            callback_data=build_callback_data("list", act="page", p=1)
        )
    ])
    
    return InlineKeyboardMarkup(keyboard)


def get_filter_menu_keyboard(watch_id: str, section: str) -> InlineKeyboardMarkup:
    """
    Generate inline keyboard for filter management
    
    Args:
        watch_id: Watch ID (will be truncated to 8 chars)
        section: 'm' for monitor, 'e' for extract
    """
    short_id = watch_id[:8]
    filter_name = "监控" if section == "m" else "提取"
    
    keyboard = [
        [
            InlineKeyboardButton(
                "➕ 添加关键词",
                callback_data=build_callback_data(short_id, sec=section, act="add_kw")
            )
        ],
        [
            InlineKeyboardButton(
                "➕ 添加正则",
                callback_data=build_callback_data(short_id, sec=section, act="add_re")
            )
        ],
        [
            InlineKeyboardButton(
                "📋 查看/删除关键词",
                callback_data=build_callback_data(short_id, sec=section, act="list_kw", p=1)
            )
        ],
        [
            InlineKeyboardButton(
                "📋 查看/删除正则",
                callback_data=build_callback_data(short_id, sec=section, act="list_re", p=1)
            )
        ],
        [
            InlineKeyboardButton(
                f"🗑️ 清空所有{filter_name}过滤器",
                callback_data=build_callback_data(short_id, sec=section, act="clear_conf")
            )
        ],
        [
            InlineKeyboardButton(
                "⬅️ 返回",
                callback_data=build_callback_data(short_id, sec="d", act="show")
            )
        ]
    ]
    
    return InlineKeyboardMarkup(keyboard)


def get_filter_list_keyboard(
    watch_id: str,
    section: str,
    item_type: str,
    items: List[str],
    page: int = 1,
    items_per_page: int = 5
) -> InlineKeyboardMarkup:
    """
    Generate paginated list of filters with delete buttons
    
    Args:
        watch_id: Watch ID
        section: 'm' or 'e'
        item_type: 'kw' or 're'
        items: List of items to display
        page: Current page number
        items_per_page: Items per page
    """
    short_id = watch_id[:8]
    keyboard = []
    
    # Calculate pagination
    total_pages = max(1, (len(items) + items_per_page - 1) // items_per_page)
    start_idx = (page - 1) * items_per_page
    end_idx = min(start_idx + items_per_page, len(items))
    
    # Add items with delete buttons
    for i in range(start_idx, end_idx):
        item = items[i]
        display_text = item[:25] + "..." if len(item) > 25 else item
        
        keyboard.append([
            InlineKeyboardButton(
                f"{i+1}. {display_text}",
                callback_data=build_callback_data(short_id, sec=section, act="noop")
            ),
            InlineKeyboardButton(
                "🗑️",
                callback_data=build_callback_data(
                    short_id, sec=section,
                    act=f"del_{item_type}",
                    i=i
                )
            )
        ])
    
    # Pagination buttons
    if total_pages > 1:
        nav_buttons = []
        if page > 1:
            nav_buttons.append(
                InlineKeyboardButton(
                    "⬅️",
                    callback_data=build_callback_data(
                        short_id, sec=section,
                        act=f"list_{item_type}",
                        p=page-1
                    )
                )
            )
        nav_buttons.append(
            InlineKeyboardButton(
                f"{page}/{total_pages}",
                callback_data=build_callback_data(short_id, sec=section, act="noop")
            )
        )
        if page < total_pages:
            nav_buttons.append(
                InlineKeyboardButton(
                    "➡️",
                    callback_data=build_callback_data(
                        short_id, sec=section,
                        act=f"list_{item_type}",
                        p=page+1
                    )
                )
            )
        keyboard.append(nav_buttons)
    
    # Back button
    keyboard.append([
        InlineKeyboardButton(
            "⬅️ 返回",
            callback_data=build_callback_data(short_id, sec=section, act="menu")
        )
    ])
    
    return InlineKeyboardMarkup(keyboard)


# ============================================================================
# Watch list and detail handlers
# ============================================================================

def handle_watch_list_page(bot, callback_query: CallbackQuery, parsed: Dict, watch_config: Dict):
    """Handle watch list pagination"""
    user_id = str(callback_query.from_user.id)
    message = callback_query.message
    
    page = int(parsed.get("p", 1))
    user_watches = get_user_watches(watch_config, user_id)
    
    if not user_watches:
        bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=message.id,
            text="**📋 你还没有设置任何监控任务**\n\n使用 `/watch add <来源> <目标>` 来添加监控"
        )
        bot.answer_callback_query(callback_query.id)
        return
    
    keyboard = get_watch_list_keyboard(user_watches, page)
    result_text = f"**📋 监控任务列表** (共 {len(user_watches)} 个)\n\n"
    result_text += "点击任务查看详情和管理"
    
    bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=message.id,
        text=result_text,
        reply_markup=keyboard
    )
    bot.answer_callback_query(callback_query.id)


def handle_watch_detail(bot, callback_query: CallbackQuery, parsed: Dict, watch_config: Dict):
    """Show watch detail view"""
    user_id = str(callback_query.from_user.id)
    message = callback_query.message
    watch_id_short = parsed["watch_id"]
    
    # Find full watch_id
    user_watches = get_user_watches(watch_config, user_id)
    watch_id = None
    for wid in user_watches.keys():
        if wid.startswith(watch_id_short):
            watch_id = wid
            break
    
    if not watch_id:
        bot.answer_callback_query(callback_query.id, "❌ 找不到该监控任务", show_alert=True)
        return
    
    watch_data = get_watch_by_id(watch_config, user_id, watch_id)
    if not watch_data:
        bot.answer_callback_query(callback_query.id, "❌ 找不到该监控任务", show_alert=True)
        return
    
    # Build detail text
    source = watch_data.get("source", {})
    if isinstance(source, dict):
        source_title = source.get("title", "Unknown")
        source_type = source.get("type", "channel")
    else:
        source_title = "Unknown"
        source_type = "channel"
    
    target_chat_id = watch_data.get("target_chat_id", "unknown")
    forward_mode = watch_data.get("forward_mode", "full")
    enabled = watch_data.get("enabled", True)
    
    detail_text = f"**📊 监控任务详情**\n\n"
    detail_text += f"**来源:** {source_title}\n"
    detail_text += f"**类型:** {source_type}\n"
    detail_text += f"**目标:** {target_chat_id}\n"
    detail_text += f"**模式:** {forward_mode}\n"
    detail_text += f"**状态:** {'🟢 启用' if enabled else '🔴 禁用'}\n\n"
    detail_text += "选择下方操作进行管理："
    
    keyboard = get_watch_detail_keyboard(watch_id, watch_data)
    bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=message.id,
        text=detail_text,
        reply_markup=keyboard
    )
    bot.answer_callback_query(callback_query.id)


def handle_watch_mode(bot, callback_query: CallbackQuery, parsed: Dict, watch_config: Dict):
    """Toggle forward mode"""
    user_id = str(callback_query.from_user.id)
    message = callback_query.message
    watch_id_short = parsed["watch_id"]
    new_mode = parsed.get("m", "full")
    
    # Find full watch_id
    user_watches = get_user_watches(watch_config, user_id)
    watch_id = None
    for wid in user_watches.keys():
        if wid.startswith(watch_id_short):
            watch_id = wid
            break
    
    if not watch_id:
        bot.answer_callback_query(callback_query.id, "❌ 找不到该监控任务", show_alert=True)
        return
    
    success, msg = update_watch_forward_mode(watch_config, user_id, watch_id, new_mode)
    
    if success:
        # Reload and update keyboard
        watch_config = load_watch_config()
        watch_data = get_watch_by_id(watch_config, user_id, watch_id)
        keyboard = get_watch_detail_keyboard(watch_id, watch_data)
        
        bot.edit_message_reply_markup(
            chat_id=message.chat.id,
            message_id=message.id,
            reply_markup=keyboard
        )
        bot.answer_callback_query(callback_query.id, f"✅ {msg}")
    else:
        bot.answer_callback_query(callback_query.id, f"❌ {msg}", show_alert=True)


def handle_watch_preserve(bot, callback_query: CallbackQuery, parsed: Dict, watch_config: Dict):
    """Toggle preserve source"""
    user_id = str(callback_query.from_user.id)
    message = callback_query.message
    watch_id_short = parsed["watch_id"]
    
    # Find full watch_id
    user_watches = get_user_watches(watch_config, user_id)
    watch_id = None
    for wid in user_watches.keys():
        if wid.startswith(watch_id_short):
            watch_id = wid
            break
    
    if not watch_id:
        bot.answer_callback_query(callback_query.id, "❌ 找不到该监控任务", show_alert=True)
        return
    
    watch_data = get_watch_by_id(watch_config, user_id, watch_id)
    current = watch_data.get("preserve_source", False)
    
    success, msg = update_watch_preserve_source(watch_config, user_id, watch_id, not current)
    
    if success:
        # Reload and update keyboard
        watch_config = load_watch_config()
        watch_data = get_watch_by_id(watch_config, user_id, watch_id)
        keyboard = get_watch_detail_keyboard(watch_id, watch_data)
        
        bot.edit_message_reply_markup(
            chat_id=message.chat.id,
            message_id=message.id,
            reply_markup=keyboard
        )
        bot.answer_callback_query(callback_query.id, f"✅ {msg}")
    else:
        bot.answer_callback_query(callback_query.id, f"❌ {msg}", show_alert=True)


def handle_watch_enabled(bot, callback_query: CallbackQuery, parsed: Dict, watch_config: Dict):
    """Toggle enabled state"""
    user_id = str(callback_query.from_user.id)
    message = callback_query.message
    watch_id_short = parsed["watch_id"]
    
    # Find full watch_id
    user_watches = get_user_watches(watch_config, user_id)
    watch_id = None
    for wid in user_watches.keys():
        if wid.startswith(watch_id_short):
            watch_id = wid
            break
    
    if not watch_id:
        bot.answer_callback_query(callback_query.id, "❌ 找不到该监控任务", show_alert=True)
        return
    
    watch_data = get_watch_by_id(watch_config, user_id, watch_id)
    current = watch_data.get("enabled", True)
    
    success, msg = update_watch_enabled(watch_config, user_id, watch_id, not current)
    
    if success:
        # Reload and update keyboard
        watch_config = load_watch_config()
        watch_data = get_watch_by_id(watch_config, user_id, watch_id)
        keyboard = get_watch_detail_keyboard(watch_id, watch_data)
        
        bot.edit_message_reply_markup(
            chat_id=message.chat.id,
            message_id=message.id,
            reply_markup=keyboard
        )
        bot.answer_callback_query(callback_query.id, f"✅ {msg}")
    else:
        bot.answer_callback_query(callback_query.id, f"❌ {msg}", show_alert=True)


def handle_watch_preview(bot, callback_query: CallbackQuery, parsed: Dict, watch_config: Dict):
    """Preview watch source"""
    from main import acc
    
    user_id = str(callback_query.from_user.id)
    message = callback_query.message
    watch_id_short = parsed["watch_id"]
    
    if acc is None:
        bot.answer_callback_query(
            callback_query.id,
            "❌ 需要配置用户会话才能预览",
            show_alert=True
        )
        return
    
    # Find full watch_id
    user_watches = get_user_watches(watch_config, user_id)
    watch_id = None
    for wid in user_watches.keys():
        if wid.startswith(watch_id_short):
            watch_id = wid
            break
    
    if not watch_id:
        bot.answer_callback_query(callback_query.id, "❌ 找不到该监控任务", show_alert=True)
        return
    
    watch_data = get_watch_by_id(watch_config, user_id, watch_id)
    
    # Safe peer resolution
    success, error_msg, chat = ensure_peer(acc, watch_data)
    
    if not success:
        bot.answer_callback_query(
            callback_query.id,
            f"❌ {error_msg}",
            show_alert=True
        )
        return
    
    # Successfully resolved
    source = watch_data.get("source", {})
    if isinstance(source, dict):
        source_type = source.get("type", "channel")
    else:
        source_type = "channel"
    
    preview_text = f"**🔍 频道预览**\n\n"
    preview_text += f"**标题:** {chat.title or 'N/A'}\n"
    preview_text += f"**用户名:** @{chat.username or 'N/A'}\n"
    preview_text += f"**ID:** `{chat.id}`\n"
    preview_text += f"**类型:** {source_type}\n"
    
    if hasattr(chat, 'members_count') and chat.members_count:
        preview_text += f"**成员数:** {chat.members_count}\n"
    
    if hasattr(chat, 'description') and chat.description:
        desc = chat.description[:100] + "..." if len(chat.description) > 100 else chat.description
        preview_text += f"\n**简介:** {desc}\n"
    
    preview_text += f"\n✅ 机器人可以访问此频道/群组"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "⬅️ 返回",
            callback_data=build_callback_data(watch_id_short, sec="d", act="show")
        )]
    ])
    
    bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=message.id,
        text=preview_text,
        reply_markup=keyboard
    )
    bot.answer_callback_query(callback_query.id, "✅ 预览成功")


def handle_watch_delete_confirm(bot, callback_query: CallbackQuery, parsed: Dict, watch_config: Dict):
    """Show delete confirmation"""
    watch_id_short = parsed["watch_id"]
    message = callback_query.message
    
    confirm_text = "**⚠️ 确认删除**\n\n确定要删除这个监控任务吗？\n\n此操作不可撤销！"
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "✅ 确认删除",
                callback_data=build_callback_data(watch_id_short, sec="d", act="del_yes")
            ),
            InlineKeyboardButton(
                "❌ 取消",
                callback_data=build_callback_data(watch_id_short, sec="d", act="show")
            )
        ]
    ])
    
    bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=message.id,
        text=confirm_text,
        reply_markup=keyboard
    )
    bot.answer_callback_query(callback_query.id)


def handle_watch_delete_yes(bot, callback_query: CallbackQuery, parsed: Dict, watch_config: Dict):
    """Actually delete the watch"""
    from watch_manager import remove_watch
    
    user_id = str(callback_query.from_user.id)
    message = callback_query.message
    watch_id_short = parsed["watch_id"]
    
    # Find full watch_id
    user_watches = get_user_watches(watch_config, user_id)
    watch_id = None
    for wid in user_watches.keys():
        if wid.startswith(watch_id_short):
            watch_id = wid
            break
    
    if not watch_id:
        bot.answer_callback_query(callback_query.id, "❌ 找不到该监控任务", show_alert=True)
        return
    
    success, msg = remove_watch(watch_config, user_id, watch_id)
    
    if success:
        bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=message.id,
            text=f"**✅ {msg}**\n\n使用 /watch list 查看剩余监控任务"
        )
        bot.answer_callback_query(callback_query.id, "已删除")
    else:
        bot.answer_callback_query(callback_query.id, f"❌ {msg}", show_alert=True)


def handle_noop(bot, callback_query: CallbackQuery, parsed: Dict, watch_config: Dict):
    """No-op handler for display-only buttons"""
    bot.answer_callback_query(callback_query.id)


# ============================================================================
# Filter menu handlers
# ============================================================================

def handle_filter_menu(bot, callback_query: CallbackQuery, parsed: Dict, watch_config: Dict):
    """Show filter menu (monitor or extract)"""
    user_id = str(callback_query.from_user.id)
    message = callback_query.message
    watch_id_short = parsed["watch_id"]
    section = parsed["sec"]  # 'm' or 'e'
    
    # Find full watch_id
    user_watches = get_user_watches(watch_config, user_id)
    watch_id = None
    for wid in user_watches.keys():
        if wid.startswith(watch_id_short):
            watch_id = wid
            break
    
    if not watch_id:
        bot.answer_callback_query(callback_query.id, "❌ 找不到该监控任务", show_alert=True)
        return
    
    watch_data = get_watch_by_id(watch_config, user_id, watch_id)
    
    filter_type = "monitor" if section == "m" else "extract"
    filter_name = "监控过滤器" if section == "m" else "提取过滤器"
    filter_key = f"{filter_type}_filters"
    
    filters = watch_data.get(filter_key, {})
    kw_count = len(filters.get("keywords", []))
    re_count = len(filters.get("patterns", []))
    
    menu_text = f"**{filter_name}管理**\n\n"
    menu_text += f"关键词: {kw_count} 个\n"
    menu_text += f"正则表达式: {re_count} 个\n\n"
    
    if section == "m":
        menu_text += "**作用:** 决定是否转发消息（full模式）\n"
        menu_text += "如果为空则转发所有消息"
    else:
        menu_text += "**作用:** 从消息中提取匹配片段（extract模式）\n"
        menu_text += "如果为空则不提取任何内容"
    
    keyboard = get_filter_menu_keyboard(watch_id, section)
    bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=message.id,
        text=menu_text,
        reply_markup=keyboard
    )
    bot.answer_callback_query(callback_query.id)


# ============================================================================
# Filter add handlers (trigger input flows)
# ============================================================================

def handle_filter_add_keyword(bot, callback_query: CallbackQuery, parsed: Dict, watch_config: Dict):
    """Trigger keyword input flow"""
    user_id = str(callback_query.from_user.id)
    message = callback_query.message
    watch_id_short = parsed["watch_id"]
    section = parsed["sec"]
    
    filter_type = "monitor" if section == "m" else "extract"
    
    # Set input state
    user_input_states[user_id] = {
        "action": "add_keyword",
        "watch_id": watch_id_short,
        "filter_type": filter_type,
        "section": section,
        "message_id": message.id
    }
    
    bot.answer_callback_query(
        callback_query.id,
        "请在下一条消息中发送要添加的关键词",
        show_alert=True
    )
    bot.send_message(
        message.chat.id,
        "**➕ 添加关键词**\n\n请发送要添加的关键词："
    )
    
    logger.info(f"User {user_id} entering keyword input flow for watch {watch_id_short}, section {section}")


def handle_filter_add_regex(bot, callback_query: CallbackQuery, parsed: Dict, watch_config: Dict):
    """Trigger regex input flow"""
    user_id = str(callback_query.from_user.id)
    message = callback_query.message
    watch_id_short = parsed["watch_id"]
    section = parsed["sec"]
    
    filter_type = "monitor" if section == "m" else "extract"
    
    # Set input state
    user_input_states[user_id] = {
        "action": "add_pattern",
        "watch_id": watch_id_short,
        "filter_type": filter_type,
        "section": section,
        "message_id": message.id
    }
    
    bot.answer_callback_query(
        callback_query.id,
        "请在下一条消息中发送要添加的正则表达式",
        show_alert=True
    )
    bot.send_message(
        message.chat.id,
        "**➕ 添加正则表达式**\n\n请发送正则表达式模式：\n\n"
        "支持 /pattern/flags 格式\n"
        "示例: `/urgent|important/i`"
    )
    
    logger.info(f"User {user_id} entering regex input flow for watch {watch_id_short}, section {section}")


# ============================================================================
# Filter list handlers
# ============================================================================

def handle_filter_list_keywords(bot, callback_query: CallbackQuery, parsed: Dict, watch_config: Dict):
    """List keywords with pagination"""
    user_id = str(callback_query.from_user.id)
    message = callback_query.message
    watch_id_short = parsed["watch_id"]
    section = parsed["sec"]
    page = int(parsed.get("p", 1))
    
    # Find full watch_id
    user_watches = get_user_watches(watch_config, user_id)
    watch_id = None
    for wid in user_watches.keys():
        if wid.startswith(watch_id_short):
            watch_id = wid
            break
    
    if not watch_id:
        bot.answer_callback_query(callback_query.id, "❌ 找不到该监控任务", show_alert=True)
        return
    
    watch_data = get_watch_by_id(watch_config, user_id, watch_id)
    filter_type = "monitor" if section == "m" else "extract"
    filter_key = f"{filter_type}_filters"
    keywords = watch_data.get(filter_key, {}).get("keywords", [])
    
    if not keywords:
        filter_name = "监控过滤器" if section == "m" else "提取过滤器"
        bot.answer_callback_query(
            callback_query.id,
            f"{filter_name}没有关键词",
            show_alert=True
        )
        return
    
    list_text = f"**关键词列表** (共 {len(keywords)} 个)\n\n"
    list_text += "点击🗑️删除相应关键词"
    
    keyboard = get_filter_list_keyboard(watch_id, section, "kw", keywords, page)
    bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=message.id,
        text=list_text,
        reply_markup=keyboard
    )
    bot.answer_callback_query(callback_query.id)


def handle_filter_list_regex(bot, callback_query: CallbackQuery, parsed: Dict, watch_config: Dict):
    """List regex patterns with pagination"""
    user_id = str(callback_query.from_user.id)
    message = callback_query.message
    watch_id_short = parsed["watch_id"]
    section = parsed["sec"]
    page = int(parsed.get("p", 1))
    
    # Find full watch_id
    user_watches = get_user_watches(watch_config, user_id)
    watch_id = None
    for wid in user_watches.keys():
        if wid.startswith(watch_id_short):
            watch_id = wid
            break
    
    if not watch_id:
        bot.answer_callback_query(callback_query.id, "❌ 找不到该监控任务", show_alert=True)
        return
    
    watch_data = get_watch_by_id(watch_config, user_id, watch_id)
    filter_type = "monitor" if section == "m" else "extract"
    filter_key = f"{filter_type}_filters"
    patterns = watch_data.get(filter_key, {}).get("patterns", [])
    
    if not patterns:
        filter_name = "监控过滤器" if section == "m" else "提取过滤器"
        bot.answer_callback_query(
            callback_query.id,
            f"{filter_name}没有正则表达式",
            show_alert=True
        )
        return
    
    list_text = f"**正则表达式列表** (共 {len(patterns)} 个)\n\n"
    list_text += "点击🗑️删除相应模式"
    
    keyboard = get_filter_list_keyboard(watch_id, section, "re", patterns, page)
    bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=message.id,
        text=list_text,
        reply_markup=keyboard
    )
    bot.answer_callback_query(callback_query.id)


# ============================================================================
# Filter delete handlers
# ============================================================================

def handle_filter_delete_keyword(bot, callback_query: CallbackQuery, parsed: Dict, watch_config: Dict):
    """Delete keyword by index"""
    user_id = str(callback_query.from_user.id)
    message = callback_query.message
    watch_id_short = parsed["watch_id"]
    section = parsed["sec"]
    index = int(parsed.get("i", 0))
    
    # Find full watch_id
    user_watches = get_user_watches(watch_config, user_id)
    watch_id = None
    for wid in user_watches.keys():
        if wid.startswith(watch_id_short):
            watch_id = wid
            break
    
    if not watch_id:
        bot.answer_callback_query(callback_query.id, "❌ 找不到该监控任务", show_alert=True)
        return
    
    watch_data = get_watch_by_id(watch_config, user_id, watch_id)
    filter_type = "monitor" if section == "m" else "extract"
    filter_key = f"{filter_type}_filters"
    keywords = watch_data.get(filter_key, {}).get("keywords", [])
    
    if 0 <= index < len(keywords):
        success, msg = remove_watch_keyword(
            watch_config, user_id, watch_id, str(index + 1), filter_type
        )
        if success:
            # Reload and show list
            watch_config = load_watch_config()
            watch_data = get_watch_by_id(watch_config, user_id, watch_id)
            keywords = watch_data.get(filter_key, {}).get("keywords", [])
            
            if keywords:
                keyboard = get_filter_list_keyboard(watch_id, section, "kw", keywords)
                bot.edit_message_reply_markup(
                    chat_id=message.chat.id,
                    message_id=message.id,
                    reply_markup=keyboard
                )
            else:
                # No more keywords, go back to menu
                keyboard = get_filter_menu_keyboard(watch_id, section)
                filter_name = "监控过滤器" if section == "m" else "提取过滤器"
                bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=message.id,
                    text=f"**{filter_name}管理**\n\n所有关键词已删除",
                    reply_markup=keyboard
                )
            
            bot.answer_callback_query(callback_query.id, f"✅ {msg}")
        else:
            bot.answer_callback_query(callback_query.id, f"❌ {msg}", show_alert=True)
    else:
        bot.answer_callback_query(callback_query.id, "❌ 索引无效", show_alert=True)


def handle_filter_delete_regex(bot, callback_query: CallbackQuery, parsed: Dict, watch_config: Dict):
    """Delete regex pattern by index"""
    user_id = str(callback_query.from_user.id)
    message = callback_query.message
    watch_id_short = parsed["watch_id"]
    section = parsed["sec"]
    index = int(parsed.get("i", 0))
    
    # Find full watch_id
    user_watches = get_user_watches(watch_config, user_id)
    watch_id = None
    for wid in user_watches.keys():
        if wid.startswith(watch_id_short):
            watch_id = wid
            break
    
    if not watch_id:
        bot.answer_callback_query(callback_query.id, "❌ 找不到该监控任务", show_alert=True)
        return
    
    watch_data = get_watch_by_id(watch_config, user_id, watch_id)
    filter_type = "monitor" if section == "m" else "extract"
    filter_key = f"{filter_type}_filters"
    patterns = watch_data.get(filter_key, {}).get("patterns", [])
    
    if 0 <= index < len(patterns):
        success, msg = remove_watch_pattern(
            watch_config, user_id, watch_id, str(index + 1), filter_type
        )
        if success:
            # Reload and show list
            watch_config = load_watch_config()
            watch_data = get_watch_by_id(watch_config, user_id, watch_id)
            patterns = watch_data.get(filter_key, {}).get("patterns", [])
            
            if patterns:
                keyboard = get_filter_list_keyboard(watch_id, section, "re", patterns)
                bot.edit_message_reply_markup(
                    chat_id=message.chat.id,
                    message_id=message.id,
                    reply_markup=keyboard
                )
            else:
                # No more patterns, go back to menu
                keyboard = get_filter_menu_keyboard(watch_id, section)
                filter_name = "监控过滤器" if section == "m" else "提取过滤器"
                bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=message.id,
                    text=f"**{filter_name}管理**\n\n所有正则表达式已删除",
                    reply_markup=keyboard
                )
            
            bot.answer_callback_query(callback_query.id, f"✅ {msg}")
        else:
            bot.answer_callback_query(callback_query.id, f"❌ {msg}", show_alert=True)
    else:
        bot.answer_callback_query(callback_query.id, "❌ 索引无效", show_alert=True)


def handle_filter_clear_confirm(bot, callback_query: CallbackQuery, parsed: Dict, watch_config: Dict):
    """Show clear all filters confirmation"""
    watch_id_short = parsed["watch_id"]
    section = parsed["sec"]
    message = callback_query.message
    
    filter_name = "监控过滤器" if section == "m" else "提取过滤器"
    
    confirm_text = f"**⚠️ 确认清空**\n\n确定要清空所有{filter_name}吗？\n\n此操作不可撤销！"
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "✅ 确认清空",
                callback_data=build_callback_data(watch_id_short, sec=section, act="clear_yes")
            ),
            InlineKeyboardButton(
                "❌ 取消",
                callback_data=build_callback_data(watch_id_short, sec=section, act="menu")
            )
        ]
    ])
    
    bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=message.id,
        text=confirm_text,
        reply_markup=keyboard
    )
    bot.answer_callback_query(callback_query.id)


def handle_filter_clear_yes(bot, callback_query: CallbackQuery, parsed: Dict, watch_config: Dict):
    """Actually clear all filters"""
    user_id = str(callback_query.from_user.id)
    message = callback_query.message
    watch_id_short = parsed["watch_id"]
    section = parsed["sec"]
    
    # Find full watch_id
    user_watches = get_user_watches(watch_config, user_id)
    watch_id = None
    for wid in user_watches.keys():
        if wid.startswith(watch_id_short):
            watch_id = wid
            break
    
    if not watch_id:
        bot.answer_callback_query(callback_query.id, "❌ 找不到该监控任务", show_alert=True)
        return
    
    watch_data = get_watch_by_id(watch_config, user_id, watch_id)
    filter_type = "monitor" if section == "m" else "extract"
    filter_key = f"{filter_type}_filters"
    
    # Clear all filters
    if watch_id in watch_config.get("watches", {}).get(user_id, {}):
        watch_config["watches"][user_id][watch_id][filter_key] = {
            "keywords": [],
            "patterns": []
        }
        from watch_manager import save_watch_config
        save_watch_config(watch_config)
        
        filter_name = "监控过滤器" if section == "m" else "提取过滤器"
        keyboard = get_filter_menu_keyboard(watch_id, section)
        bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=message.id,
            text=f"**✅ 已清空所有{filter_name}**",
            reply_markup=keyboard
        )
        bot.answer_callback_query(callback_query.id, "已清空")
        logger.info(f"Cleared all {filter_type} filters for watch {watch_id[:8]}")
    else:
        bot.answer_callback_query(callback_query.id, "❌ 操作失败", show_alert=True)


# ============================================================================
# User input handler
# ============================================================================

def handle_user_input(bot, message, acc):
    """
    Handle user text input for adding keywords/patterns
    
    Returns:
        True if handled, False if not expecting input
    """
    user_id = str(message.from_user.id)
    
    if user_id not in user_input_states:
        return False  # Not expecting input from this user
    
    state = user_input_states[user_id]
    action = state.get("action")
    watch_id_short = state.get("watch_id")
    filter_type = state.get("filter_type")
    section = state.get("section")
    original_message_id = state.get("message_id")
    
    # Find full watch_id
    watch_config = load_watch_config()
    user_watches = get_user_watches(watch_config, user_id)
    watch_id = None
    for wid in user_watches.keys():
        if wid.startswith(watch_id_short):
            watch_id = wid
            break
    
    if not watch_id:
        bot.send_message(message.chat.id, "❌ 监控任务不存在")
        del user_input_states[user_id]
        return True
    
    watch_data = get_watch_by_id(watch_config, user_id, watch_id)
    
    if not watch_data:
        bot.send_message(message.chat.id, "❌ 监控任务不存在")
        del user_input_states[user_id]
        return True
    
    try:
        if action == "add_keyword":
            keyword = message.text.strip()
            
            if not keyword:
                bot.send_message(message.chat.id, "❌ 关键词不能为空")
                del user_input_states[user_id]
                return True
            
            success, msg = add_watch_keyword(watch_config, user_id, watch_id, keyword, filter_type)
            
            if success:
                bot.send_message(message.chat.id, f"✅ {msg}")
                # Update original message keyboard
                watch_config = load_watch_config()
                watch_data = get_watch_by_id(watch_config, user_id, watch_id)
                keyboard = get_filter_menu_keyboard(watch_id, section)
                try:
                    bot.edit_message_reply_markup(
                        chat_id=message.chat.id,
                        message_id=original_message_id,
                        reply_markup=keyboard
                    )
                except:
                    pass
                logger.info(f"Added keyword '{keyword}' to {filter_type} filters for watch {watch_id[:8]}")
            else:
                bot.send_message(message.chat.id, f"❌ {msg}")
        
        elif action == "add_pattern":
            pattern = message.text.strip()
            
            if not pattern:
                bot.send_message(message.chat.id, "❌ 正则表达式不能为空")
                del user_input_states[user_id]
                return True
            
            # Validate regex pattern
            from regex_filters import parse_regex_pattern
            try:
                parse_regex_pattern(pattern)
            except Exception as e:
                bot.send_message(message.chat.id, f"❌ 正则表达式无效: {str(e)}")
                del user_input_states[user_id]
                return True
            
            success, msg = add_watch_pattern(watch_config, user_id, watch_id, pattern, filter_type)
            
            if success:
                bot.send_message(message.chat.id, f"✅ {msg}")
                # Update original message keyboard
                watch_config = load_watch_config()
                watch_data = get_watch_by_id(watch_config, user_id, watch_id)
                keyboard = get_filter_menu_keyboard(watch_id, section)
                try:
                    bot.edit_message_reply_markup(
                        chat_id=message.chat.id,
                        message_id=original_message_id,
                        reply_markup=keyboard
                    )
                except:
                    pass
                logger.info(f"Added regex pattern '{pattern}' to {filter_type} filters for watch {watch_id[:8]}")
            else:
                bot.send_message(message.chat.id, f"❌ {msg}")
        
        # Clear state
        del user_input_states[user_id]
        return True
    
    except Exception as e:
        logger.error(f"Error handling user input: {e}", exc_info=True)
        bot.send_message(message.chat.id, f"❌ 错误: {str(e)}")
        del user_input_states[user_id]
        return True


# ============================================================================
# Register all handlers with the router
# ============================================================================

def register_all_handlers():
    """Register all callback handlers with the router"""
    
    # Watch list and detail
    router.register("", "page", handle_watch_list_page)  # watch_id="list"
    router.register("d", "show", handle_watch_detail)
    router.register("d", "mode", handle_watch_mode)
    router.register("d", "preserve", handle_watch_preserve)
    router.register("d", "enabled", handle_watch_enabled)
    router.register("d", "preview", handle_watch_preview)
    router.register("d", "del_conf", handle_watch_delete_confirm)
    router.register("d", "del_yes", handle_watch_delete_yes)
    router.register("d", "noop", handle_noop)
    
    # Monitor filters (section = m)
    router.register("m", "menu", handle_filter_menu)
    router.register("m", "add_kw", handle_filter_add_keyword)
    router.register("m", "add_re", handle_filter_add_regex)
    router.register("m", "list_kw", handle_filter_list_keywords)
    router.register("m", "list_re", handle_filter_list_regex)
    router.register("m", "del_kw", handle_filter_delete_keyword)
    router.register("m", "del_re", handle_filter_delete_regex)
    router.register("m", "clear_conf", handle_filter_clear_confirm)
    router.register("m", "clear_yes", handle_filter_clear_yes)
    router.register("m", "noop", handle_noop)
    
    # Extract filters (section = e)
    router.register("e", "menu", handle_filter_menu)
    router.register("e", "add_kw", handle_filter_add_keyword)
    router.register("e", "add_re", handle_filter_add_regex)
    router.register("e", "list_kw", handle_filter_list_keywords)
    router.register("e", "list_re", handle_filter_list_regex)
    router.register("e", "del_kw", handle_filter_delete_keyword)
    router.register("e", "del_re", handle_filter_delete_regex)
    router.register("e", "clear_conf", handle_filter_clear_confirm)
    router.register("e", "clear_yes", handle_filter_clear_yes)
    router.register("e", "noop", handle_noop)
    
    # Noop for special buttons
    router.register("", "noop", handle_noop)
    
    logger.info(f"Registered {len(router.handlers)} callback handlers")


# Initialize handlers on module import
register_all_handlers()
