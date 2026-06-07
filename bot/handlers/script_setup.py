"""脚本管理的输入处理辅助函数。"""

from __future__ import annotations

from dataclasses import dataclass

from pyrogram.errors import ChannelPrivate, UsernameInvalid
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.handlers.chat_input import resolve_chat_input
from bot.handlers.instances import get_bot_instance
from bot.services.pt_pay_manager import get_pt_pay_monitor_manager
from bot.services.pt_pay_models import describe_trigger_delay_spec
from bot.utils.status import user_states

_resolve_chat_input = resolve_chat_input


@dataclass(frozen=True)
class ScriptSourceContext:
    source_chat_id: str
    source_name: str


def handle_script_add_source(message: Message, user_id: str) -> None:
    bot = get_bot_instance()

    try:
        source_id, source_name, _source_ref = _resolve_chat_input(message, allow_saved_messages=True, require_bot=False)
    except (ChannelPrivate, UsernameInvalid, ValueError) as exc:
        bot.send_message(message.chat.id, f"**❌ 无法识别监控群聊：** `{str(exc)}`")
        return
    except Exception as exc:
        bot.send_message(message.chat.id, f"**❌ 错误：** `{str(exc)}`")
        return

    user_states[user_id]["script_source_chat_id"] = source_id
    user_states[user_id]["script_source_name"] = source_name
    user_states[user_id]["action"] = "script_add_target_bot"

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("❌ 取消", callback_data="menu_script")]])
    text = "**🤖 添加联动脚本**\n\n"
    text += f"✅ 已设置监控群：`{source_name}`\n\n"
    text += "**步骤 2/2：** 请输入目标对象\n\n"
    text += "可以发送：\n"
    text += "• Bot 或好友用户名（如 `@some_bot` / `@friend_name`）\n"
    text += "• 私聊对象 chat_id\n"
    text += "• 转发一条来自该对象的消息"
    bot.send_message(message.chat.id, text, reply_markup=keyboard)


def handle_script_add_target_bot(message: Message, user_id: str) -> None:
    bot = get_bot_instance()
    manager = get_pt_pay_monitor_manager()

    try:
        target_bot_id, target_bot_name, target_bot_ref = _resolve_chat_input(
            message,
            allow_saved_messages=False,
            require_bot=False,
        )
    except (ChannelPrivate, UsernameInvalid, ValueError) as exc:
        bot.send_message(message.chat.id, f"**❌ 无法识别目标对象：** `{str(exc)}`")
        return
    except Exception as exc:
        bot.send_message(message.chat.id, f"**❌ 错误：** `{str(exc)}`")
        return

    source = _load_script_source_context(message, user_id)
    if source is None:
        return

    try:
        task = manager.add_task(
            user_id=user_id,
            source_chat_id=source.source_chat_id,
            source_name=source.source_name,
            target_bot_id=int(target_bot_id),
            target_bot_name=target_bot_name,
            target_bot_ref=target_bot_ref,
        )
    except ValueError as exc:
        bot.send_message(message.chat.id, f"**⚠️ 无法创建脚本：** `{str(exc)}`")
        return

    _clear_state(user_id)
    _send_script_created_message(message, task)


def _load_script_source_context(message: Message, user_id: str) -> ScriptSourceContext | None:
    state = user_states.get(user_id, {})
    source = ScriptSourceContext(
        source_chat_id=str(state.get("script_source_chat_id") or ""),
        source_name=str(state.get("script_source_name") or ""),
    )
    if source.source_chat_id and source.source_name:
        return source
    get_bot_instance().send_message(message.chat.id, "**❌ 会话已过期，请重新开始**")
    _clear_state(user_id)
    return None


def _send_script_created_message(message: Message, task) -> None:
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 查看脚本列表", callback_data="script_list")],
        [InlineKeyboardButton("🔍 查看详情", callback_data=f"script_view_{task.task_id}")],
        [InlineKeyboardButton("🏠 返回主菜单", callback_data="menu_main")],
    ])
    text = "**✅ 联动脚本已创建并启动**\n\n"
    text += f"监控群：`{task.source_name}`\n"
    text += f"目标对象：`{task.target_bot_name}`\n"
    text += f"目标引用：`{task.target_bot_ref}`\n"
    text += "状态：`运行中`"
    get_bot_instance().send_message(message.chat.id, text, reply_markup=keyboard)


def handle_script_set_delay(message: Message, user_id: str) -> None:
    bot = get_bot_instance()
    manager = get_pt_pay_monitor_manager()

    state = user_states.get(user_id, {})
    task_id = str(state.get("task_id") or "").strip()
    if not task_id:
        bot.send_message(message.chat.id, "**❌ 会话已过期，请重新开始**")
        _clear_state(user_id)
        return

    raw_value = (message.text or "").strip()
    try:
        updated = manager.update_delay_spec(user_id, task_id, raw_value)
    except ValueError as exc:
        bot.send_message(message.chat.id, f"**❌ 延时格式错误：** `{str(exc)}`\n\n请输入 `5` 或 `0-100`")
        return

    _clear_state(user_id)

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回详情", callback_data=f"script_view_{updated.task_id}")]])
    text = "**✅ 触发延时已更新**\n\n"
    text += f"当前设置：`{describe_trigger_delay_spec(updated.trigger_delay_spec)}`"
    bot.send_message(message.chat.id, text, reply_markup=keyboard)


def _clear_state(user_id: str) -> None:
    if user_id in user_states:
        del user_states[user_id]
