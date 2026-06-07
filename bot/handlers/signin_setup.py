"""定时签到脚本的输入处理辅助函数。"""

from __future__ import annotations

from dataclasses import dataclass

from pyrogram.errors import ChannelPrivate, UsernameInvalid
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.handlers.chat_input import resolve_chat_input
from bot.handlers.instances import get_bot_instance
from bot.services.signin_manager import get_scheduled_signin_manager
from bot.services.signin_models import describe_interval_spec, normalize_interval_spec
from bot.utils.status import user_states


@dataclass(frozen=True)
class SigninAddContext:
    chat_id: str
    chat_name: str
    chat_ref: str
    message_text: str


def handle_signin_add_chat(message: Message, user_id: str) -> None:
    bot = get_bot_instance()

    try:
        chat_id, chat_name, chat_ref = resolve_chat_input(
            message,
            allow_saved_messages=False,
            require_bot=False,
        )
    except (ChannelPrivate, UsernameInvalid, ValueError) as exc:
        bot.send_message(message.chat.id, f"**❌ 无法识别签到目标群聊：** `{str(exc)}`")
        return
    except Exception as exc:
        bot.send_message(message.chat.id, f"**❌ 错误：** `{str(exc)}`")
        return

    user_states[user_id]["signin_chat_id"] = chat_id
    user_states[user_id]["signin_chat_name"] = chat_name
    user_states[user_id]["signin_chat_ref"] = chat_ref
    user_states[user_id]["action"] = "signin_add_message"

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("❌ 取消", callback_data="menu_script")]])
    text = "**🕒 添加定时签到脚本**\n\n"
    text += f"✅ 已设置目标群聊：`{chat_name}`\n\n"
    text += "**步骤 2/3：** 请输入要定时发送的消息\n\n"
    text += "可以直接写完整内容，例如：\n"
    text += "• `司机人，记得签到`\n"
    text += "• `@username 签到`\n"
    text += "• 任意你希望周期发送的文本"
    bot.send_message(message.chat.id, text, reply_markup=keyboard)


def handle_signin_add_message(message: Message, user_id: str) -> None:
    bot = get_bot_instance()

    message_text = (message.text or "").strip()
    if not message_text:
        bot.send_message(message.chat.id, "**❌ 签到消息不能为空**")
        return

    if not _ensure_signin_context(user_id, message.chat.id):
        return

    user_states[user_id]["signin_message_text"] = message_text
    user_states[user_id]["action"] = "signin_add_interval"

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("❌ 取消", callback_data="menu_script")]])
    text = "**🕒 添加定时签到脚本**\n\n"
    text += f"✅ 已设置消息：`{message_text}`\n\n"
    text += "**步骤 3/3：** 请输入发送间隔\n\n"
    text += "支持格式：\n"
    text += "• `3600` 表示每 3600 秒\n"
    text += "• `30m` 表示每 30 分钟\n"
    text += "• `8h` 表示每 8 小时\n"
    text += "• `1d` 表示每天一次"
    bot.send_message(message.chat.id, text, reply_markup=keyboard)


def handle_signin_add_interval(message: Message, user_id: str) -> None:
    bot = get_bot_instance()
    manager = get_scheduled_signin_manager()

    context = _load_signin_add_context(user_id, message.chat.id)
    if context is None:
        return

    try:
        interval_spec = normalize_interval_spec((message.text or "").strip())
    except ValueError as exc:
        bot.send_message(
            message.chat.id,
            f"**❌ 间隔格式错误：** `{str(exc)}`\n\n请输入 `3600`、`30m`、`8h` 或 `1d`",
        )
        return

    try:
        task = manager.add_task(
            user_id=user_id,
            chat_id=context.chat_id,
            chat_name=context.chat_name,
            chat_ref=context.chat_ref,
            message_text=context.message_text,
            interval_spec=interval_spec,
        )
    except ValueError as exc:
        bot.send_message(
            message.chat.id,
            f"**⚠️ 无法创建签到脚本：** `{str(exc)}`",
        )
        return

    _clear_state(user_id)
    _send_signin_created_message(message, task)


def _load_signin_add_context(user_id: str, chat_id: int) -> SigninAddContext | None:
    state = user_states.get(user_id, {})
    context = SigninAddContext(
        chat_id=str(state.get("signin_chat_id") or "").strip(),
        chat_name=str(state.get("signin_chat_name") or "").strip(),
        chat_ref=str(state.get("signin_chat_ref") or "").strip(),
        message_text=str(state.get("signin_message_text") or "").strip(),
    )
    if context.chat_id and context.chat_name and context.chat_ref and context.message_text:
        return context
    get_bot_instance().send_message(chat_id, "**❌ 会话已过期，请重新开始**")
    _clear_state(user_id)
    return None


def _send_signin_created_message(message: Message, task) -> None:
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 查看签到脚本", callback_data="signin_list")],
        [InlineKeyboardButton("🔍 查看详情", callback_data=f"signin_view_{task.task_id}")],
        [InlineKeyboardButton("🏠 返回脚本管理", callback_data="menu_script")],
    ])
    text = "**✅ 定时签到脚本已创建并启动**\n\n"
    text += f"目标群聊：`{task.chat_name}`\n"
    text += f"发送间隔：`{describe_interval_spec(task.interval_spec)}`\n"
    text += f"消息内容：`{task.message_text}`\n"
    text += "状态：`运行中`"
    get_bot_instance().send_message(message.chat.id, text, reply_markup=keyboard)


def handle_signin_edit_message(message: Message, user_id: str) -> None:
    bot = get_bot_instance()
    manager = get_scheduled_signin_manager()

    state = user_states.get(user_id, {})
    task_id = str(state.get("task_id") or "").strip()
    if not task_id:
        bot.send_message(message.chat.id, "**❌ 会话已过期，请重新开始**")
        _clear_state(user_id)
        return

    try:
        updated = manager.update_message_text(user_id, task_id, (message.text or "").strip())
    except ValueError as exc:
        bot.send_message(message.chat.id, f"**❌ 消息内容错误：** `{str(exc)}`")
        return

    _clear_state(user_id)

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回详情", callback_data=f"signin_view_{updated.task_id}")]])
    text = "**✅ 签到消息已更新**\n\n"
    text += f"当前消息：`{updated.message_text}`"
    bot.send_message(message.chat.id, text, reply_markup=keyboard)


def handle_signin_edit_interval(message: Message, user_id: str) -> None:
    bot = get_bot_instance()
    manager = get_scheduled_signin_manager()

    state = user_states.get(user_id, {})
    task_id = str(state.get("task_id") or "").strip()
    if not task_id:
        bot.send_message(message.chat.id, "**❌ 会话已过期，请重新开始**")
        _clear_state(user_id)
        return

    try:
        updated = manager.update_interval_spec(user_id, task_id, (message.text or "").strip())
    except ValueError as exc:
        bot.send_message(
            message.chat.id,
            f"**❌ 间隔格式错误：** `{str(exc)}`\n\n请输入 `3600`、`30m`、`8h` 或 `1d`",
        )
        return

    _clear_state(user_id)

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回详情", callback_data=f"signin_view_{updated.task_id}")]])
    text = "**✅ 发送间隔已更新**\n\n"
    text += f"当前间隔：`{describe_interval_spec(updated.interval_spec)}`"
    bot.send_message(message.chat.id, text, reply_markup=keyboard)


def _ensure_signin_context(user_id: str, chat_id: int) -> bool:
    bot = get_bot_instance()
    state = user_states.get(user_id, {})
    if state.get("signin_chat_id") and state.get("signin_chat_name") and state.get("signin_chat_ref"):
        return True

    bot.send_message(chat_id, "**❌ 会话已过期，请重新开始**")
    _clear_state(user_id)
    return False


def _clear_state(user_id: str) -> None:
    if user_id in user_states:
        del user_states[user_id]
