"""
Inline keyboard UI handlers for watch management
"""

import pyrogram
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from typing import Dict, List, Optional, Tuple
import json
import logging

logger = logging.getLogger(__name__)

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
from regex_filters import compile_pattern_list, extract_matches, format_snippets_for_telegram
from peer_utils import ensure_peer


# User input state tracking
user_input_states = {}


def get_watch_detail_keyboard(watch_id: str, watch_data: Dict) -> InlineKeyboardMarkup:
    """Generate inline keyboard for watch detail view"""
    
    # Extract watch info
    source = watch_data.get("source", {})
    if isinstance(source, dict):
        source_title = source.get("title", "Unknown")
        source_id = source.get("id", "")
    else:
        source_title = "Unknown"
        source_id = source
    
    forward_mode = watch_data.get("forward_mode", "full")
    preserve_source = watch_data.get("preserve_source", False)
    enabled = watch_data.get("enabled", True)
    
    monitor_filters = watch_data.get("monitor_filters", {})
    extract_filters = watch_data.get("extract_filters", {})
    
    monitor_kw_count = len(monitor_filters.get("keywords", []))
    monitor_re_count = len(monitor_filters.get("patterns", []))
    extract_kw_count = len(extract_filters.get("keywords", []))
    extract_re_count = len(extract_filters.get("patterns", []))
    
    # Build keyboard
    keyboard = []
    
    # Mode selection (mutually exclusive)
    keyboard.append([
        InlineKeyboardButton(
            f"{'✅' if forward_mode == 'full' else '⬜'} Full",
            callback_data=f"w:{watch_id}:mode:full"
        ),
        InlineKeyboardButton(
            f"{'✅' if forward_mode == 'extract' else '⬜'} Extract",
            callback_data=f"w:{watch_id}:mode:extract"
        )
    ])
    
    # Monitor filters section
    keyboard.append([
        InlineKeyboardButton(
            f"📊 监控过滤器 ({monitor_kw_count}+{monitor_re_count})",
            callback_data=f"w:{watch_id}:mfilter:menu"
        )
    ])
    
    # Extract filters section
    keyboard.append([
        InlineKeyboardButton(
            f"✂️ 提取过滤器 ({extract_kw_count}+{extract_re_count})",
            callback_data=f"w:{watch_id}:efilter:menu"
        )
    ])
    
    # Preserve source toggle
    keyboard.append([
        InlineKeyboardButton(
            f"{'✅' if preserve_source else '❌'} 保留来源",
            callback_data=f"w:{watch_id}:preserve:toggle"
        )
    ])
    
    # Enable/Disable
    keyboard.append([
        InlineKeyboardButton(
            f"{'🔵 禁用' if enabled else '🟢 启用'}",
            callback_data=f"w:{watch_id}:enabled:toggle"
        )
    ])
    
    # Preview & Delete
    keyboard.append([
        InlineKeyboardButton("🔍 预览", callback_data=f"w:{watch_id}:preview"),
        InlineKeyboardButton("🗑️ 删除", callback_data=f"w:{watch_id}:delete:confirm")
    ])
    
    # Back button
    keyboard.append([
        InlineKeyboardButton("⬅️ 返回列表", callback_data="w:list:1")
    ])
    
    return InlineKeyboardMarkup(keyboard)


def get_filter_menu_keyboard(watch_id: str, filter_type: str) -> InlineKeyboardMarkup:
    """Generate inline keyboard for filter management (monitor or extract)"""
    
    filter_name = "监控" if filter_type == "monitor" else "提取"
    
    keyboard = [
        [
            InlineKeyboardButton(
                f"➕ 添加关键词",
                callback_data=f"w:{watch_id}:{filter_type}:kw:add"
            )
        ],
        [
            InlineKeyboardButton(
                f"➕ 添加正则",
                callback_data=f"w:{watch_id}:{filter_type}:re:add"
            )
        ],
        [
            InlineKeyboardButton(
                f"📋 查看/删除关键词",
                callback_data=f"w:{watch_id}:{filter_type}:kw:list"
            )
        ],
        [
            InlineKeyboardButton(
                f"📋 查看/删除正则",
                callback_data=f"w:{watch_id}:{filter_type}:re:list"
            )
        ],
        [
            InlineKeyboardButton(
                f"🗑️ 清空所有{filter_name}过滤器",
                callback_data=f"w:{watch_id}:{filter_type}:clear:confirm"
            )
        ],
        [
            InlineKeyboardButton(
                "⬅️ 返回",
                callback_data=f"w:{watch_id}:detail"
            )
        ]
    ]
    
    return InlineKeyboardMarkup(keyboard)


def get_filter_list_keyboard(
    watch_id: str,
    filter_type: str,
    item_type: str,
    items: List[str],
    page: int = 1,
    items_per_page: int = 5
) -> InlineKeyboardMarkup:
    """Generate paginated list of filters with delete buttons"""
    
    keyboard = []
    
    # Calculate pagination
    total_pages = (len(items) + items_per_page - 1) // items_per_page
    start_idx = (page - 1) * items_per_page
    end_idx = min(start_idx + items_per_page, len(items))
    
    # Add items with delete buttons
    for i in range(start_idx, end_idx):
        item = items[i]
        display_text = item[:30] + "..." if len(item) > 30 else item
        keyboard.append([
            InlineKeyboardButton(
                f"{i+1}. {display_text}",
                callback_data=f"w:{watch_id}:noop"
            ),
            InlineKeyboardButton(
                "🗑️",
                callback_data=f"w:{watch_id}:{filter_type}:{item_type}:del:{i}"
            )
        ])
    
    # Pagination buttons
    if total_pages > 1:
        nav_buttons = []
        if page > 1:
            nav_buttons.append(
                InlineKeyboardButton(
                    "⬅️",
                    callback_data=f"w:{watch_id}:{filter_type}:{item_type}:list:{page-1}"
                )
            )
        nav_buttons.append(
            InlineKeyboardButton(
                f"{page}/{total_pages}",
                callback_data=f"w:{watch_id}:noop"
            )
        )
        if page < total_pages:
            nav_buttons.append(
                InlineKeyboardButton(
                    "➡️",
                    callback_data=f"w:{watch_id}:{filter_type}:{item_type}:list:{page+1}"
                )
            )
        keyboard.append(nav_buttons)
    
    # Back button
    keyboard.append([
        InlineKeyboardButton(
            "⬅️ 返回",
            callback_data=f"w:{watch_id}:{filter_type}:menu"
        )
    ])
    
    return InlineKeyboardMarkup(keyboard)


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
        
        keyboard.append([
            InlineKeyboardButton(
                f"{status_icon} {source_title}",
                callback_data=f"w:{watch_id}:detail"
            )
        ])
    
    # Pagination buttons
    if total_pages > 1:
        nav_buttons = []
        if page > 1:
            nav_buttons.append(
                InlineKeyboardButton("⬅️", callback_data=f"w:list:{page-1}")
            )
        nav_buttons.append(
            InlineKeyboardButton(f"{page}/{total_pages}", callback_data="w:list:noop")
        )
        if page < total_pages:
            nav_buttons.append(
                InlineKeyboardButton("➡️", callback_data=f"w:list:{page+1}")
            )
        keyboard.append(nav_buttons)
    
    return InlineKeyboardMarkup(keyboard)


def handle_callback(bot, callback_query: CallbackQuery):
    """
    Main callback handler for inline keyboard interactions
    
    Callback data format: 
    - w:<watch_id>:<action>:<param1>:<param2>:... (watch management)
    - iktest:<action> (inline keyboard test)
    """
    data = callback_query.data
    user_id = str(callback_query.from_user.id)
    message = callback_query.message
    
    try:
        # Parse callback data
        parts = data.split(":")
        
        if len(parts) < 2:
            bot.answer_callback_query(callback_query.id, "无效的操作")
            return
        
        prefix = parts[0]
        
        # Handle iktest callbacks
        if prefix == "iktest":
            action = parts[1] if len(parts) > 1 else "ok"
            if action == "ok":
                bot.answer_callback_query(callback_query.id, "✅ 按钮工作正常！", show_alert=True)
            elif action == "refresh":
                bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=message.id,
                    text="**🧪 Inline Keyboard Test (Refreshed)**\n\n"
                         "Buttons are working correctly!\n\n"
                         f"Chat ID: `{message.chat.id}`\n"
                         f"User ID: {callback_query.from_user.id}",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("✅ Test Button", callback_data="iktest:ok")],
                        [InlineKeyboardButton("🔄 Refresh", callback_data="iktest:refresh")]
                    ])
                )
                bot.answer_callback_query(callback_query.id, "🔄 已刷新")
            return
        
        # Watch management callbacks
        if prefix != "w":
            return  # Not our callback
        
        # Load config
        watch_config = load_watch_config()
        
        # Handle watch list
        if parts[1] == "list":
            page = int(parts[2]) if len(parts) > 2 and parts[2] != "noop" else 1
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
            return
        
        # All other operations require a watch_id
        watch_id = parts[1]
        watch_data = get_watch_by_id(watch_config, user_id, watch_id)
        
        if not watch_data:
            bot.answer_callback_query(callback_query.id, "找不到该监控任务")
            return
        
        # Handle different actions
        action = parts[2] if len(parts) > 2 else None
        
        if action == "detail":
            # Show watch detail
            source = watch_data.get("source", {})
            if isinstance(source, dict):
                source_title = source.get("title", "Unknown")
                source_id = source.get("id", "")
                source_type = source.get("type", "channel")
            else:
                source_title = "Unknown"
                source_id = source
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
        
        elif action == "mode":
            # Toggle forward mode
            new_mode = parts[3] if len(parts) > 3 else "full"
            success, msg = update_watch_forward_mode(watch_config, user_id, watch_id, new_mode)
            
            if success:
                # Reload and show detail
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
        
        elif action == "preserve":
            # Toggle preserve source
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
        
        elif action == "enabled":
            # Toggle enabled state
            current = watch_data.get("enabled", True)
            from watch_manager import update_watch_enabled
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
        
        elif action in ["mfilter", "efilter"]:
            # Monitor or extract filter menu
            filter_type = "monitor" if action == "mfilter" else "extract"
            sub_action = parts[3] if len(parts) > 3 else "menu"
            
            if sub_action == "menu":
                # Show filter menu
                filter_name = "监控过滤器" if filter_type == "monitor" else "提取过滤器"
                menu_text = f"**{filter_name}管理**\n\n"
                
                filter_key = f"{filter_type}_filters"
                filters = watch_data.get(filter_key, {})
                kw_count = len(filters.get("keywords", []))
                re_count = len(filters.get("patterns", []))
                
                menu_text += f"关键词: {kw_count} 个\n"
                menu_text += f"正则表达式: {re_count} 个\n\n"
                
                if filter_type == "monitor":
                    menu_text += "**作用:** 决定是否转发消息（full模式）\n"
                    menu_text += "如果为空则转发所有消息"
                else:
                    menu_text += "**作用:** 从消息中提取匹配片段（extract模式）\n"
                    menu_text += "如果为空则不提取任何内容"
                
                keyboard = get_filter_menu_keyboard(watch_id, filter_type)
                bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=message.id,
                    text=menu_text,
                    reply_markup=keyboard
                )
                bot.answer_callback_query(callback_query.id)
            
            elif sub_action == "kw":
                # Keyword operations
                kw_action = parts[4] if len(parts) > 4 else None
                
                if kw_action == "add":
                    # Request keyword input
                    user_input_states[user_id] = {
                        "action": "add_keyword",
                        "watch_id": watch_id,
                        "filter_type": filter_type,
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
                
                elif kw_action == "list":
                    # List keywords
                    page = int(parts[5]) if len(parts) > 5 else 1
                    filter_key = f"{filter_type}_filters"
                    keywords = watch_data.get(filter_key, {}).get("keywords", [])
                    
                    if not keywords:
                        filter_name = "监控过滤器" if filter_type == "monitor" else "提取过滤器"
                        bot.answer_callback_query(
                            callback_query.id,
                            f"{filter_name}没有关键词",
                            show_alert=True
                        )
                        return
                    
                    list_text = f"**关键词列表** (共 {len(keywords)} 个)\n\n"
                    list_text += "点击🗑️删除相应关键词"
                    
                    keyboard = get_filter_list_keyboard(watch_id, filter_type, "kw", keywords, page)
                    bot.edit_message_text(
                        chat_id=message.chat.id,
                        message_id=message.id,
                        text=list_text,
                        reply_markup=keyboard
                    )
                    bot.answer_callback_query(callback_query.id)
                
                elif kw_action == "del":
                    # Delete keyword by index
                    index = int(parts[5]) if len(parts) > 5 else 0
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
                                keyboard = get_filter_list_keyboard(watch_id, filter_type, "kw", keywords)
                                bot.edit_message_reply_markup(
                                    chat_id=message.chat.id,
                                    message_id=message.id,
                                    reply_markup=keyboard
                                )
                            else:
                                # No more keywords, go back to menu
                                keyboard = get_filter_menu_keyboard(watch_id, filter_type)
                                bot.edit_message_reply_markup(
                                    chat_id=message.chat.id,
                                    message_id=message.id,
                                    reply_markup=keyboard
                                )
                            
                            bot.answer_callback_query(callback_query.id, f"✅ {msg}")
                        else:
                            bot.answer_callback_query(callback_query.id, f"❌ {msg}", show_alert=True)
            
            elif sub_action == "re":
                # Regex pattern operations
                re_action = parts[4] if len(parts) > 4 else None
                
                if re_action == "add":
                    # Request pattern input
                    user_input_states[user_id] = {
                        "action": "add_pattern",
                        "watch_id": watch_id,
                        "filter_type": filter_type,
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
                
                elif re_action == "list":
                    # List patterns
                    page = int(parts[5]) if len(parts) > 5 else 1
                    filter_key = f"{filter_type}_filters"
                    patterns = watch_data.get(filter_key, {}).get("patterns", [])
                    
                    if not patterns:
                        filter_name = "监控过滤器" if filter_type == "monitor" else "提取过滤器"
                        bot.answer_callback_query(
                            callback_query.id,
                            f"{filter_name}没有正则表达式",
                            show_alert=True
                        )
                        return
                    
                    list_text = f"**正则表达式列表** (共 {len(patterns)} 个)\n\n"
                    list_text += "点击🗑️删除相应模式"
                    
                    keyboard = get_filter_list_keyboard(watch_id, filter_type, "re", patterns, page)
                    bot.edit_message_text(
                        chat_id=message.chat.id,
                        message_id=message.id,
                        text=list_text,
                        reply_markup=keyboard
                    )
                    bot.answer_callback_query(callback_query.id)
                
                elif re_action == "del":
                    # Delete pattern by index
                    index = int(parts[5]) if len(parts) > 5 else 0
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
                                keyboard = get_filter_list_keyboard(watch_id, filter_type, "re", patterns)
                                bot.edit_message_reply_markup(
                                    chat_id=message.chat.id,
                                    message_id=message.id,
                                    reply_markup=keyboard
                                )
                            else:
                                # No more patterns, go back to menu
                                keyboard = get_filter_menu_keyboard(watch_id, filter_type)
                                bot.edit_message_reply_markup(
                                    chat_id=message.chat.id,
                                    message_id=message.id,
                                    reply_markup=keyboard
                                )
                            
                            bot.answer_callback_query(callback_query.id, f"✅ {msg}")
                        else:
                            bot.answer_callback_query(callback_query.id, f"❌ {msg}", show_alert=True)
        
        elif action == "preview":
            # Preview watch source - safely resolve peer
            # This requires network access and may fail
            from main import acc
            
            if acc is None:
                bot.answer_callback_query(
                    callback_query.id,
                    "❌ 需要配置用户会话才能预览",
                    show_alert=True
                )
                return
            
            # Safe peer resolution
            success, error_msg, chat = ensure_peer(acc, watch_data)
            
            if not success:
                bot.answer_callback_query(
                    callback_query.id,
                    f"❌ {error_msg}",
                    show_alert=True
                )
                return
            
            # Successfully resolved, show preview
            source = watch_data.get("source", {})
            if isinstance(source, dict):
                source_title = source.get("title", "Unknown")
                source_type = source.get("type", "channel")
            else:
                source_title = "Unknown"
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
                [InlineKeyboardButton("⬅️ 返回", callback_data=f"w:{watch_id}:detail")]
            ])
            
            bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=message.id,
                text=preview_text,
                reply_markup=keyboard
            )
            bot.answer_callback_query(callback_query.id, "✅ 预览成功")
        
        elif action == "delete":
            # Delete watch confirmation
            if parts[3] == "confirm":
                # Show confirmation
                confirm_text = "**⚠️ 确认删除**\n\n确定要删除这个监控任务吗？\n\n此操作不可撤销！"
                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ 确认删除", callback_data=f"w:{watch_id}:delete:yes"),
                        InlineKeyboardButton("❌ 取消", callback_data=f"w:{watch_id}:detail")
                    ]
                ])
                bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=message.id,
                    text=confirm_text,
                    reply_markup=keyboard
                )
                bot.answer_callback_query(callback_query.id)
            
            elif parts[3] == "yes":
                # Actually delete
                from watch_manager import remove_watch
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
        
        elif action == "noop":
            # No operation (for display-only buttons)
            bot.answer_callback_query(callback_query.id)
        
        else:
            bot.answer_callback_query(callback_query.id, "未知操作")
    
    except Exception as e:
        logger.error(f"Error in callback handler: {e}", exc_info=True)
        error_summary = str(e)[:100]  # Truncate for callback query
        bot.answer_callback_query(callback_query.id, f"错误: {error_summary}", show_alert=True)


def handle_user_input(bot, message, acc):
    """
    Handle user text input for adding keywords/patterns
    """
    user_id = str(message.from_user.id)
    
    if user_id not in user_input_states:
        return False  # Not expecting input from this user
    
    state = user_input_states[user_id]
    action = state.get("action")
    watch_id = state.get("watch_id")
    filter_type = state.get("filter_type")
    original_message_id = state.get("message_id")
    
    watch_config = load_watch_config()
    watch_data = get_watch_by_id(watch_config, user_id, watch_id)
    
    if not watch_data:
        bot.send_message(message.chat.id, "❌ 监控任务不存在")
        del user_input_states[user_id]
        return True
    
    try:
        if action == "add_keyword":
            keyword = message.text.strip()
            success, msg = add_watch_keyword(watch_config, user_id, watch_id, keyword, filter_type)
            
            if success:
                bot.send_message(message.chat.id, f"✅ {msg}")
                # Update original message keyboard
                watch_config = load_watch_config()
                watch_data = get_watch_by_id(watch_config, user_id, watch_id)
                keyboard = get_filter_menu_keyboard(watch_id, filter_type)
                try:
                    bot.edit_message_reply_markup(
                        chat_id=message.chat.id,
                        message_id=original_message_id,
                        reply_markup=keyboard
                    )
                except:
                    pass
            else:
                bot.send_message(message.chat.id, f"❌ {msg}")
        
        elif action == "add_pattern":
            pattern = message.text.strip()
            success, msg = add_watch_pattern(watch_config, user_id, watch_id, pattern, filter_type)
            
            if success:
                bot.send_message(message.chat.id, f"✅ {msg}")
                # Update original message keyboard
                watch_config = load_watch_config()
                watch_data = get_watch_by_id(watch_config, user_id, watch_id)
                keyboard = get_filter_menu_keyboard(watch_id, filter_type)
                try:
                    bot.edit_message_reply_markup(
                        chat_id=message.chat.id,
                        message_id=original_message_id,
                        reply_markup=keyboard
                    )
                except:
                    pass
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
