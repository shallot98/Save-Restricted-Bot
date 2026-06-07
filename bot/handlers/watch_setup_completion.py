"""Completion handlers for watch setup flows."""

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.handlers.instances import get_bot_instance
from bot.handlers.watch_setup_models import (
    ForwardWatchSetupOptions,
    WatchFilterOptions,
    WatchSetupTarget,
)
from bot.utils.status import user_states
from src.core.container import get_watch_setup_service


def complete_watch_setup(
    target: WatchSetupTarget | int,
    options: ForwardWatchSetupOptions | int,
    *legacy_args,
) -> None:
    """Complete watch setup for forward mode."""
    target, options = _resolve_forward_setup_args(target, options, legacy_args)
    bot = get_bot_instance()
    service = get_watch_setup_service()

    try:
        result = service.create_forward_watch(
            user_id=target.user_id,
            source_id=user_states[target.user_id]["source_id"],
            source_name=user_states[target.user_id]["source_name"],
            dest_id=user_states[target.user_id]["dest_id"],
            dest_name=user_states[target.user_id]["dest_name"],
            whitelist=options.filters.whitelist,
            blacklist=options.filters.blacklist,
            whitelist_regex=options.filters.whitelist_regex,
            blacklist_regex=options.filters.blacklist_regex,
            preserve_source=options.preserve_source,
            forward_mode=options.forward_mode,
            extract_patterns=options.extract_patterns,
        )
        _edit_completion_message(bot, target, result)
    except Exception as e:
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回", callback_data="menu_watch")]])
        bot.edit_message_text(target.chat_id, target.message_id, f"**❌ 错误：** `{str(e)}`", reply_markup=keyboard)
    finally:
        user_states.pop(target.user_id, None)


def complete_watch_setup_single(
    target: WatchSetupTarget | int,
    filters: WatchFilterOptions | int,
    *legacy_args,
) -> None:
    """Complete watch setup for record mode."""
    target, filters = _resolve_record_setup_args(target, filters, legacy_args)
    bot = get_bot_instance()
    service = get_watch_setup_service()

    try:
        result = service.create_record_watch(
            user_id=target.user_id,
            source_id=user_states[target.user_id]["source_id"],
            source_name=user_states[target.user_id]["source_name"],
            whitelist=filters.whitelist,
            blacklist=filters.blacklist,
            whitelist_regex=filters.whitelist_regex,
            blacklist_regex=filters.blacklist_regex,
        )
        _edit_completion_message(bot, target, result)
    except Exception as e:
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回", callback_data="menu_watch")]])
        bot.edit_message_text(target.chat_id, target.message_id, f"**❌ 错误：** `{str(e)}`", reply_markup=keyboard)
    finally:
        user_states.pop(target.user_id, None)


def _resolve_forward_setup_args(
    target: WatchSetupTarget | int,
    options: ForwardWatchSetupOptions | int,
    legacy_args: tuple,
) -> tuple[WatchSetupTarget, ForwardWatchSetupOptions]:
    if isinstance(target, WatchSetupTarget) and isinstance(options, ForwardWatchSetupOptions):
        return target, options
    if not isinstance(target, int) or not isinstance(options, int) or len(legacy_args) != 8:
        raise TypeError("complete_watch_setup expects WatchSetupTarget and ForwardWatchSetupOptions")
    user_id, whitelist, blacklist, whitelist_regex, blacklist_regex, preserve_source, forward_mode, extract_patterns = legacy_args
    filters = WatchFilterOptions(whitelist, blacklist, whitelist_regex, blacklist_regex)
    setup = ForwardWatchSetupOptions(filters, preserve_source, forward_mode, extract_patterns)
    return WatchSetupTarget(target, options, user_id), setup


def _resolve_record_setup_args(
    target: WatchSetupTarget | int,
    filters: WatchFilterOptions | int,
    legacy_args: tuple,
) -> tuple[WatchSetupTarget, WatchFilterOptions]:
    if isinstance(target, WatchSetupTarget) and isinstance(filters, WatchFilterOptions):
        return target, filters
    if not isinstance(target, int) or not isinstance(filters, int) or len(legacy_args) != 5:
        raise TypeError("complete_watch_setup_single expects WatchSetupTarget and WatchFilterOptions")
    user_id, whitelist, blacklist, whitelist_regex, blacklist_regex = legacy_args
    return WatchSetupTarget(target, filters, user_id), WatchFilterOptions(
        whitelist,
        blacklist,
        whitelist_regex,
        blacklist_regex,
    )


def _edit_completion_message(bot, target: WatchSetupTarget, result) -> None:
    callback = "menu_watch" if result.duplicate else "watch_list"
    label = "🔙 返回" if result.duplicate else "🔙 返回监控列表"
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(label, callback_data=callback)]])
    bot.edit_message_text(target.chat_id, target.message_id, result.message_text, reply_markup=keyboard)
