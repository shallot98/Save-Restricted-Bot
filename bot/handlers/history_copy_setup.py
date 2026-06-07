"""Input helpers for keyboard-triggered history copy tasks."""

from __future__ import annotations

from pyrogram.errors import ChannelPrivate, UsernameInvalid
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.handlers.chat_input import resolve_chat_input
from bot.handlers.instances import get_bot_instance
from bot.services.history_copy_task_manager import get_history_copy_task_manager
from bot.utils.status import user_states


def parse_history_limit_input(raw_value: str) -> int | None:
    value = str(raw_value or "").strip()
    if value.lower() in {"all", "全部"}:
        return None
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError("请输入正整数，或输入 `ALL` / `全部` 表示全部历史") from exc
    if parsed <= 0:
        raise ValueError("历史条数必须大于 0")
    return parsed


def handle_history_copy_add_source(message: Message, user_id: str) -> None:
    bot = get_bot_instance()
    try:
        source_chat_id, source_name, source_ref = resolve_chat_input(
            message,
            allow_saved_messages=True,
            require_bot=False,
        )
    except (ChannelPrivate, UsernameInvalid, ValueError) as exc:
        bot.send_message(message.chat.id, f"**❌ 无法识别来源群聊：** `{str(exc)}`")
        return
    except Exception as exc:
        bot.send_message(message.chat.id, f"**❌ 错误：** `{str(exc)}`")
        return

    state = user_states[user_id]
    state["history_copy_source_chat_ref"] = source_ref or source_chat_id
    state["history_copy_source_name"] = source_name
    state["action"] = "history_copy_add_dest"

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("❌ 取消", callback_data="menu_script_history_copy")]])
    text = "**📚 新建历史复制任务**\n\n"
    text += f"✅ 来源已设置：`{source_name}`\n\n"
    text += "**步骤 2/3：** 请输入目标群聊/频道\n\n"
    text += "可以发送：\n"
    text += "• 群聊/频道用户名（如 `@target_channel`）\n"
    text += "• 群聊/频道 chat_id（如 `-1001234567890`）\n"
    text += "• 转发一条来自该群聊的消息\n"
    text += "• 输入 `me` 发送到收藏夹"
    bot.send_message(message.chat.id, text, reply_markup=keyboard)


def handle_history_copy_add_dest(message: Message, user_id: str) -> None:
    bot = get_bot_instance()
    try:
        dest_chat_id, dest_name, dest_ref = resolve_chat_input(
            message,
            allow_saved_messages=True,
            require_bot=False,
        )
    except (ChannelPrivate, UsernameInvalid, ValueError) as exc:
        bot.send_message(message.chat.id, f"**❌ 无法识别目标群聊：** `{str(exc)}`")
        return
    except Exception as exc:
        bot.send_message(message.chat.id, f"**❌ 错误：** `{str(exc)}`")
        return

    state = user_states[user_id]
    state["history_copy_dest_chat_ref"] = dest_ref or dest_chat_id
    state["history_copy_dest_name"] = dest_name
    state["action"] = "history_copy_add_limit"

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("❌ 取消", callback_data="menu_script_history_copy")]])
    text = "**📚 新建历史复制任务**\n\n"
    text += f"来源：`{state.get('history_copy_source_name', '未知')}`\n"
    text += f"目标：`{dest_name}`\n\n"
    text += "**步骤 3/3：** 请输入复制范围\n\n"
    text += "• 输入正整数，如 `500`，表示最近 500 条\n"
    text += "• 输入 `ALL` 或 `全部`，表示复制全部历史"
    bot.send_message(message.chat.id, text, reply_markup=keyboard)


def handle_history_copy_add_limit(message: Message, user_id: str) -> None:
    bot = get_bot_instance()
    state = user_states.get(user_id, {})
    source_ref = str(state.get("history_copy_source_chat_ref") or "").strip()
    source_name = str(state.get("history_copy_source_name") or "").strip()
    dest_ref = str(state.get("history_copy_dest_chat_ref") or "").strip()
    dest_name = str(state.get("history_copy_dest_name") or "").strip()
    if not source_ref or not dest_ref:
        bot.send_message(message.chat.id, "**❌ 会话已过期，请重新开始**")
        if user_id in user_states:
            del user_states[user_id]
        return

    try:
        history_limit = parse_history_limit_input(message.text or "")
        task = get_history_copy_task_manager().add_task(
            user_id=user_id,
            source_chat_ref=source_ref,
            source_name=source_name,
            dest_chat_ref=dest_ref,
            dest_name=dest_name,
            history_limit=history_limit,
        )
    except ValueError as exc:
        bot.send_message(message.chat.id, f"**❌ 输入错误：** `{str(exc)}`")
        return

    if user_id in user_states:
        del user_states[user_id]

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 查看任务详情", callback_data=f"history_copy_view_{task.task_id}")],
        [InlineKeyboardButton("📋 查看历史复制任务", callback_data="history_copy_list")],
        [InlineKeyboardButton("🔙 返回脚本管理", callback_data="menu_script")],
    ])
    text = "**✅ 历史复制任务已启动**\n\n"
    text += f"来源：`{task.source_name}`\n"
    text += f"目标：`{task.dest_name}`\n"
    text += f"范围：`{'全部历史' if task.history_limit is None else f'最近 {task.history_limit} 条'}`\n\n"
    text += "任务已在后台执行；可随时进入“历史复制任务”查看状态。"
    bot.send_message(message.chat.id, text, reply_markup=keyboard)
