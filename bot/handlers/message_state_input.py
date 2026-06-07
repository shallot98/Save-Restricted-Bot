"""User-state text input handlers for multi-step bot flows."""

import re
from dataclasses import dataclass
from typing import Optional

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.handlers.history_copy_setup import (
    handle_history_copy_add_dest,
    handle_history_copy_add_limit,
    handle_history_copy_add_source,
)
from bot.handlers.script_setup import handle_script_add_source, handle_script_add_target_bot, handle_script_set_delay
from bot.handlers.signin_setup import (
    handle_signin_add_chat,
    handle_signin_add_interval,
    handle_signin_add_message,
    handle_signin_edit_interval,
    handle_signin_edit_message,
)
from bot.handlers.watch_setup import (
    complete_watch_setup,
    handle_add_dest,
    handle_add_source,
    show_filter_options,
    show_filter_options_single,
)
from bot.utils.status import user_states
from src.core.container import get_watch_service

DIRECT_ACTION_HANDLERS = {
    "add_source": handle_add_source,
    "add_dest": handle_add_dest,
    "script_add_source": handle_script_add_source,
    "script_add_target_bot": handle_script_add_target_bot,
    "script_set_delay": handle_script_set_delay,
    "history_copy_add_source": handle_history_copy_add_source,
    "history_copy_add_dest": handle_history_copy_add_dest,
    "history_copy_add_limit": handle_history_copy_add_limit,
    "signin_add_chat": handle_signin_add_chat,
    "signin_add_message": handle_signin_add_message,
    "signin_add_interval": handle_signin_add_interval,
    "signin_edit_message": handle_signin_edit_message,
    "signin_edit_interval": handle_signin_edit_interval,
}


@dataclass(frozen=True)
class StateInputContext:
    message: object
    user_id: str
    bot: object


@dataclass(frozen=True)
class FilterEditTarget:
    filter_type: str
    color: Optional[str]


def handle_user_state_input(message, user_id: str, bot) -> tuple[bool, Optional[str]]:
    """Handle text input for an active user state."""
    state = user_states.get(user_id)
    if not state:
        return False, None

    context = StateInputContext(message=message, user_id=user_id, bot=bot)
    action = state.get("action")
    category = action or "user_state"
    if action in DIRECT_ACTION_HANDLERS:
        DIRECT_ACTION_HANDLERS[action](message, user_id)
        return True, category

    if action == "add_whitelist":
        return _handle_keyword_list(context, "whitelist", required=True), category
    if action == "add_blacklist":
        return _handle_keyword_list(context, "blacklist", required=False), category
    if action == "add_regex_whitelist":
        return _handle_regex_list(context, "whitelist_regex", "正则白名单"), category
    if action == "add_regex_blacklist":
        return _handle_regex_list(context, "blacklist_regex", "正则黑名单"), category
    if action == "add_extract_patterns":
        return _handle_add_extract_patterns(context), category
    if action and action.startswith("edit_filter_"):
        return _handle_edit_filter(context, action), category
    if action == "edit_extract_patterns":
        return _handle_edit_extract_patterns(context), category

    return False, category


def _parse_csv(text: str) -> list[str]:
    return [item.strip() for item in text.split(",") if item.strip()]


def _validate_patterns(patterns: list[str]) -> None:
    for pattern in patterns:
        re.compile(pattern)


def _show_filter_continue(context: StateInputContext) -> None:
    msg = context.bot.send_message(context.message.chat.id, "⏳ 继续设置...")
    if user_states[context.user_id].get("record_mode"):
        show_filter_options_single(context.message.chat.id, msg.id, context.user_id)
    else:
        show_filter_options(context.message.chat.id, msg.id, context.user_id)


def _handle_keyword_list(context: StateInputContext, key: str, required: bool) -> bool:
    keywords = _parse_csv(context.message.text)
    if not keywords and required:
        context.bot.send_message(context.message.chat.id, "**❌ 请输入至少一个关键词**")
        return True

    user_states[context.user_id][key] = keywords
    if keywords:
        label = "白名单" if key == "whitelist" else "黑名单"
        context.bot.send_message(context.message.chat.id, f"✅ 关键词{label}已设置：`{', '.join(keywords)}`")

    _show_filter_continue(context)
    return True


def _handle_regex_list(context: StateInputContext, key: str, label: str) -> bool:
    patterns = _parse_csv(context.message.text)
    if not patterns:
        context.bot.send_message(context.message.chat.id, "**❌ 请输入至少一个正则表达式**")
        return True

    try:
        _validate_patterns(patterns)
    except re.error as e:
        context.bot.send_message(context.message.chat.id, f"**❌ 正则表达式错误：** `{str(e)}`\n\n请重新输入")
        return True

    user_states[context.user_id][key] = patterns
    context.bot.send_message(context.message.chat.id, f"✅ {label}已设置：`{', '.join(patterns)}`")
    _show_filter_continue(context)
    return True


def _handle_add_extract_patterns(context: StateInputContext) -> bool:
    patterns = _parse_csv(context.message.text)
    if not patterns:
        context.bot.send_message(context.message.chat.id, "**❌ 请输入至少一个正则表达式**")
        return True

    try:
        _validate_patterns(patterns)
    except re.error as e:
        context.bot.send_message(context.message.chat.id, f"**❌ 正则表达式错误：** `{str(e)}`\n\n请重新输入")
        return True

    state = user_states[context.user_id]
    msg = context.bot.send_message(context.message.chat.id, "⏳ 正在完成设置...")
    complete_watch_setup(
        context.message.chat.id,
        msg.id,
        context.user_id,
        state.get("whitelist", []),
        state.get("blacklist", []),
        state.get("whitelist_regex", []),
        state.get("blacklist_regex", []),
        state.get("preserve_source", False),
        "extract",
        patterns,
    )
    return True


def _handle_edit_filter(context: StateInputContext, action: str) -> bool:
    parts = action.split("_")
    target = FilterEditTarget(
        filter_type=parts[2],
        color=None if parts[2] == "extract" else parts[3] if len(parts) > 3 else None,
    )
    state = user_states[context.user_id]
    watch_service = get_watch_service()
    watch_config = watch_service.get_all_configs_dict()
    user_id_str = str(context.message.from_user.id)
    watch_key = state.get("watch_key")

    if not _apply_filter_edit(context, watch_config[user_id_str][watch_key], target):
        return True

    watch_service.save_config_dict(watch_config)
    _send_filter_updated(context, state, "**✅ 规则已更新**")
    return True


def _apply_filter_edit(context: StateInputContext, task_config: dict, target: FilterEditTarget) -> bool:
    if target.filter_type == "kw":
        key = "whitelist" if target.color == "white" else "blacklist"
        task_config[key] = _parse_csv(context.message.text)
        return True

    patterns = _parse_csv(context.message.text)
    try:
        _validate_patterns(patterns)
    except re.error as e:
        context.bot.send_message(context.message.chat.id, f"**❌ 正则表达式错误：** `{str(e)}`\n\n请重新输入")
        return False

    if target.filter_type == "re":
        key = "whitelist_regex" if target.color == "white" else "blacklist_regex"
        task_config[key] = patterns
    elif target.filter_type == "extract":
        task_config["extract_patterns"] = patterns
    return True


def _handle_edit_extract_patterns(context: StateInputContext) -> bool:
    patterns = _parse_csv(context.message.text)
    if not patterns:
        context.bot.send_message(context.message.chat.id, "**❌ 请输入至少一个正则表达式**")
        return True

    try:
        _validate_patterns(patterns)
    except re.error as e:
        context.bot.send_message(context.message.chat.id, f"**❌ 正则表达式错误：** `{str(e)}`\n\n请重新输入")
        return True

    state = user_states[context.user_id]
    watch_service = get_watch_service()
    watch_config = watch_service.get_all_configs_dict()
    user_id_str = str(context.message.from_user.id)
    watch_key = state.get("watch_key")

    if isinstance(watch_config[user_id_str][watch_key], dict):
        watch_config[user_id_str][watch_key]["extract_patterns"] = patterns

    watch_service.save_config_dict(watch_config)
    _send_filter_updated(context, state, "**✅ 提取规则已设置**")
    return True


def _send_filter_updated(context: StateInputContext, state: dict, text: str) -> None:
    task_ref = state.get("task_ref") or state.get("task_id")
    del user_states[context.user_id]
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔙 返回详情", callback_data=f"watch_view_{task_ref}")]]
    )
    context.bot.send_message(context.message.chat.id, text, reply_markup=keyboard)
