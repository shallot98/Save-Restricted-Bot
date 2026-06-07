"""定时签到脚本回调处理器。"""

from __future__ import annotations

from pyrogram import Client
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from bot.services.signin_manager import get_scheduled_signin_manager
from bot.services.signin_models import ScheduledSigninTaskConfig, describe_interval_spec
from bot.utils.status import user_states

from .base import CallbackContext, CallbackHandler


class SigninCallbackHandler(CallbackHandler):
    """处理定时签到脚本相关回调。"""

    def can_handle(self, data: str) -> bool:
        return data.startswith("signin_")

    def handle(self, client: Client, callback_query: CallbackQuery) -> None:
        context = self.get_common_context(client, callback_query)

        if self.acc is None:
            self.answer_and_log(callback_query, "❌ 需要配置 String Session", show_alert=True)
            return

        self.dispatch_context(
            context,
            {
                "signin_add_start": self._handle_add_start,
                "signin_list": self._handle_list,
            },
            (
                ("signin_view_", self._handle_view),
                ("signin_toggle_", self._handle_toggle),
                ("signin_message_", self._handle_message),
                ("signin_interval_", self._handle_interval),
                ("signin_remove_", self._handle_remove),
            ),
        )

    def _handle_add_start(self, context: CallbackContext) -> None:
        user_states[context.user_id] = {"action": "signin_add_chat"}
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("❌ 取消", callback_data="menu_script")]])
        text = "**🕒 添加定时签到脚本**\n\n"
        text += "**步骤 1/3：** 请输入要发送消息的群聊/频道\n\n"
        text += "可以发送：\n"
        text += "• 群聊/频道用户名（如 `@group_name`）\n"
        text += "• 群聊/频道 chat_id（如 `-1001234567890`）\n"
        text += "• 转发一条来自该群聊的消息"
        self.bot.edit_message_text(context.chat_id, context.message_id, text, reply_markup=keyboard)
        self.answer_and_log(context.callback_query)

    def _handle_list(self, context: CallbackContext) -> None:
        manager = get_scheduled_signin_manager()
        tasks = manager.list_user_tasks(context.user_id)
        if not tasks:
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回", callback_data="menu_script")]])
            self.bot.edit_message_text(context.chat_id, context.message_id, "**🕒 签到脚本列表**\n\n暂无定时签到脚本", reply_markup=keyboard)
            self.answer_and_log(context.callback_query, "暂无签到脚本")
            return

        buttons = [
            [
                InlineKeyboardButton(
                    _build_task_label(task),
                    callback_data=f"signin_view_{task.task_id}",
                )
            ]
            for task in tasks
        ]
        buttons.append([InlineKeyboardButton("🔙 返回", callback_data="menu_script")])
        keyboard = InlineKeyboardMarkup(buttons)
        text = f"**🕒 签到脚本列表**\n\n共 **{len(tasks)}** 个定时签到脚本\n点击条目查看详情"
        self.bot.edit_message_text(context.chat_id, context.message_id, text, reply_markup=keyboard)
        self.answer_and_log(context.callback_query)

    def _handle_view(self, context: CallbackContext) -> None:
        task_id = context.data.removeprefix("signin_view_")
        manager = get_scheduled_signin_manager()
        task = manager.get_user_task(context.user_id, task_id)
        if task is None:
            self.answer_and_log(context.callback_query, "❌ 签到脚本不存在", show_alert=True)
            return
        self._render_task_detail(context.chat_id, context.message_id, task)
        self.answer_and_log(context.callback_query)

    def _handle_toggle(self, context: CallbackContext) -> None:
        task_id = context.data.removeprefix("signin_toggle_")
        manager = get_scheduled_signin_manager()
        try:
            task = manager.toggle_task(context.user_id, task_id)
        except ValueError as exc:
            self.answer_and_log(context.callback_query, f"❌ {str(exc)}", show_alert=True)
            return

        self._render_task_detail(context.chat_id, context.message_id, task)
        tip = "✅ 已启动" if task.enabled else "⏹ 已停止"
        self.answer_and_log(context.callback_query, tip)

    def _handle_message(self, context: CallbackContext) -> None:
        task_id = context.data.removeprefix("signin_message_")
        manager = get_scheduled_signin_manager()
        task = manager.get_user_task(context.user_id, task_id)
        if task is None:
            self.answer_and_log(context.callback_query, "❌ 签到脚本不存在", show_alert=True)
            return

        user_states[context.user_id] = {"action": "signin_edit_message", "task_id": task_id}
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("❌ 取消", callback_data=f"signin_view_{task_id}")]])
        text = "**✏️ 修改签到消息**\n\n"
        text += f"当前内容：`{task.message_text}`\n\n"
        text += "请直接发送新的消息文本。"
        self.bot.edit_message_text(context.chat_id, context.message_id, text, reply_markup=keyboard)
        self.answer_and_log(context.callback_query)

    def _handle_interval(self, context: CallbackContext) -> None:
        task_id = context.data.removeprefix("signin_interval_")
        manager = get_scheduled_signin_manager()
        task = manager.get_user_task(context.user_id, task_id)
        if task is None:
            self.answer_and_log(context.callback_query, "❌ 签到脚本不存在", show_alert=True)
            return

        user_states[context.user_id] = {"action": "signin_edit_interval", "task_id": task_id}
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("❌ 取消", callback_data=f"signin_view_{task_id}")]])
        text = "**⏱ 修改发送间隔**\n\n"
        text += f"当前间隔：`{describe_interval_spec(task.interval_spec)}`\n\n"
        text += "支持格式：`3600`、`30m`、`8h`、`1d`"
        self.bot.edit_message_text(context.chat_id, context.message_id, text, reply_markup=keyboard)
        self.answer_and_log(context.callback_query)

    def _handle_remove(self, context: CallbackContext) -> None:
        task_id = context.data.removeprefix("signin_remove_")
        manager = get_scheduled_signin_manager()
        try:
            task = manager.remove_task(context.user_id, task_id)
        except ValueError as exc:
            self.answer_and_log(context.callback_query, f"❌ {str(exc)}", show_alert=True)
            return

        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回脚本管理", callback_data="menu_script")]])
        text = "**✅ 定时签到脚本已删除**\n\n"
        text += f"目标群聊：`{task.chat_name}`\n"
        text += f"消息内容：`{task.message_text}`"
        self.bot.edit_message_text(context.chat_id, context.message_id, text, reply_markup=keyboard)
        self.answer_and_log(context.callback_query, "✅ 删除成功")

    def _render_task_detail(self, chat_id: int, message_id: int, task: ScheduledSigninTaskConfig) -> None:
        text = "**🕒 定时签到脚本详情**\n\n"
        text += f"目标群聊：`{task.chat_name}`\n"
        text += f"目标 chat_id：`{task.chat_id}`\n"
        text += f"发送间隔：`{describe_interval_spec(task.interval_spec)}`\n"
        text += f"消息内容：`{task.message_text}`\n"
        text += f"状态：{'🟢 运行中' if task.enabled else '⚪️ 已停止'}"

        toggle_label = "⏹ 停止脚本" if task.enabled else "▶️ 启动脚本"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(toggle_label, callback_data=f"signin_toggle_{task.task_id}")],
            [InlineKeyboardButton("✏️ 修改消息", callback_data=f"signin_message_{task.task_id}")],
            [InlineKeyboardButton("⏱ 修改间隔", callback_data=f"signin_interval_{task.task_id}")],
            [InlineKeyboardButton("🗑 删除脚本", callback_data=f"signin_remove_{task.task_id}")],
            [InlineKeyboardButton("🔙 返回列表", callback_data="signin_list")],
        ])
        self.bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)


def _build_task_label(task: ScheduledSigninTaskConfig) -> str:
    preview = task.message_text.replace("\n", " ").strip()
    if len(preview) > 10:
        preview = f"{preview[:10]}..."
    return f"{'🟢' if task.enabled else '⚪️'} {task.chat_name} · {preview}"
