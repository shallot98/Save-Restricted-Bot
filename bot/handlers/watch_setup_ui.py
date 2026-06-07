"""UI rendering helpers for watch setup flows."""

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.handlers.instances import get_bot_instance
from bot.handlers.watch_setup_models import ForwardModeChoiceOptions, WatchFilterOptions, WatchSetupTarget
from bot.utils.status import user_states


def _state_list(user_id: str, key: str) -> list[str]:
    value = user_states[user_id].get(key, [])
    return value if isinstance(value, list) else []


def _build_filter_status(user_id: str) -> str:
    labels = {
        "whitelist": "🟢 关键词白名单",
        "blacklist": "🔴 关键词黑名单",
        "whitelist_regex": "🟢 正则白名单",
        "blacklist_regex": "🔴 正则黑名单",
    }
    lines: List[str] = []
    for key, label in labels.items():
        values = _state_list(user_id, key)
        if values:
            lines.append(f"{label}: `{', '.join(values)}`")
    if not lines:
        return "📋 **暂未设置过滤规则**\n"
    return "📋 **已设置的规则：**\n" + "\n".join(lines) + "\n"


def _build_filter_keyboard(record_mode: bool) -> InlineKeyboardMarkup:
    done_callback = "filter_done_single" if record_mode else "filter_done"
    clear_callback = "clear_filters_single" if record_mode else "clear_filters"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🟢 关键词白名单", callback_data="filter_whitelist")],
        [InlineKeyboardButton("🔴 关键词黑名单", callback_data="filter_blacklist")],
        [InlineKeyboardButton("🟢 正则白名单", callback_data="filter_regex_whitelist")],
        [InlineKeyboardButton("🔴 正则黑名单", callback_data="filter_regex_blacklist")],
        [InlineKeyboardButton("✅ 完成设置", callback_data=done_callback)],
        [InlineKeyboardButton("🗑️ 清空规则", callback_data=clear_callback)],
        [InlineKeyboardButton("❌ 取消", callback_data="menu_watch")],
    ])


def _send_or_edit(chat_id: int, message_id: int, text: str, *, keyboard: InlineKeyboardMarkup) -> None:
    bot = get_bot_instance()
    try:
        bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)
    except Exception:
        bot.send_message(chat_id, text, reply_markup=keyboard)


def _render_filter_prompt(user_id: str, record_mode: bool) -> str:
    source_name = user_states[user_id].get("source_name", "未知")
    dest_name = user_states[user_id].get("dest_name", "未知")
    mode_title = "（记录模式）" if record_mode else ""
    mode_line = (
        "模式：📝 **记录模式**（保存到网页笔记）\n\n"
        if record_mode
        else f"目标：`{dest_name}`\n\n"
    )
    action_word = "记录" if record_mode else "转发"
    return (
        f"**➕ 添加监控任务{mode_title}**\n\n"
        f"来源：`{source_name}`\n"
        f"{mode_line}"
        f"{_build_filter_status(user_id)}\n"
        "**步骤 3：** 是否需要设置/修改过滤规则？\n\n"
        f"🟢 **关键词白名单** - 包含关键词才{action_word}\n"
        f"🔴 **关键词黑名单** - 包含关键词不{action_word}\n"
        f"🟢 **正则白名单** - 匹配正则才{action_word}\n"
        f"🔴 **正则黑名单** - 匹配正则不{action_word}\n\n"
        "✅ **完成设置** - 保存并继续\n"
        "🗑️ **清空规则** - 清空所有过滤规则\n\n"
        "💡 可以设置多种规则，黑名单优先于白名单"
    )


def show_filter_options(chat_id: int, message_id: int, user_id: str) -> None:
    """Show filter options for forward mode."""
    _send_or_edit(
        chat_id,
        message_id,
        _render_filter_prompt(user_id, record_mode=False),
        keyboard=_build_filter_keyboard(False),
    )


def show_filter_options_single(chat_id: int, message_id: int, user_id: str) -> None:
    """Show filter options for record mode."""
    _send_or_edit(
        chat_id,
        message_id,
        _render_filter_prompt(user_id, record_mode=True),
        keyboard=_build_filter_keyboard(True),
    )


def show_preserve_source_options(chat_id: int, message_id: int, user_id: str) -> None:
    """Show preserve source options."""
    bot = get_bot_instance()
    source_name = user_states[user_id].get("source_name", "未知")
    dest_name = user_states[user_id].get("dest_name", "未知")
    whitelist = _state_list(user_id, "whitelist")
    blacklist = _state_list(user_id, "blacklist")

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ 否（推荐）", callback_data="preserve_no")],
        [InlineKeyboardButton("✅ 是", callback_data="preserve_yes")],
        [InlineKeyboardButton("🔙 取消", callback_data="menu_watch")],
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
    target: WatchSetupTarget | int,
    options: ForwardModeChoiceOptions | int,
    *legacy_args,
) -> None:
    """Show forward mode options."""
    target, options = _resolve_forward_mode_args(target, options, legacy_args)
    bot = get_bot_instance()
    source_name = user_states[target.user_id].get("source_name", "未知")
    dest_name = user_states[target.user_id].get("dest_name", "未知")

    user_states[target.user_id]["whitelist"] = options.filters.whitelist
    user_states[target.user_id]["blacklist"] = options.filters.blacklist
    user_states[target.user_id]["whitelist_regex"] = options.filters.whitelist_regex
    user_states[target.user_id]["blacklist_regex"] = options.filters.blacklist_regex
    user_states[target.user_id]["preserve_source"] = options.preserve_source

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 完整转发", callback_data="fwdmode_full")],
        [InlineKeyboardButton("🎯 提取模式", callback_data="fwdmode_extract")],
        [InlineKeyboardButton("🔙 取消", callback_data="menu_watch")],
    ])

    text = (
        "**➕ 添加监控任务**\n\n"
        f"来源：`{source_name}`\n"
        f"目标：`{dest_name}`\n\n"
        "**选择转发模式：**\n\n"
        "📦 **完整转发** - 转发整条消息（默认）\n"
        "🎯 **提取模式** - 使用正则提取特定内容后转发\n\n"
        "💡 提取模式需要设置提取规则"
    )
    bot.edit_message_text(target.chat_id, target.message_id, text, reply_markup=keyboard)


def _resolve_forward_mode_args(
    target: WatchSetupTarget | int,
    options: ForwardModeChoiceOptions | int,
    legacy_args: tuple,
) -> tuple[WatchSetupTarget, ForwardModeChoiceOptions]:
    if isinstance(target, WatchSetupTarget) and isinstance(options, ForwardModeChoiceOptions):
        return target, options
    if not isinstance(target, int) or not isinstance(options, int) or len(legacy_args) != 6:
        raise TypeError("show_forward_mode_options expects WatchSetupTarget and ForwardModeChoiceOptions")
    user_id, whitelist, blacklist, whitelist_regex, blacklist_regex, preserve_source = legacy_args
    filters = WatchFilterOptions(whitelist, blacklist, whitelist_regex, blacklist_regex)
    return WatchSetupTarget(target, options, user_id), ForwardModeChoiceOptions(filters, preserve_source)


def show_dn_append_options(chat_id: int, message_id: int, user_id: str, *, forward_mode: str) -> None:
    """Deprecated: DN 补全功能已移除，保留函数仅用于显式暴露误调用。"""
    raise RuntimeError("show_dn_append_options 已废弃：DN 补全流程已移除")
