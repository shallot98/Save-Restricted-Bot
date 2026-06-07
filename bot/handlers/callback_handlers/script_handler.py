"""脚本管理回调处理器。"""

from __future__ import annotations

from pyrogram import Client
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from bot.services.pt_pay_manager import get_pt_pay_monitor_manager
from bot.services.pt_pay_models import PTPayTaskConfig, describe_trigger_delay_spec
from bot.utils.status import user_states

from .base import CallbackContext, CallbackHandler


class ScriptCallbackHandler(CallbackHandler):
    """处理联动脚本相关回调。"""

    def can_handle(self, data: str) -> bool:
        return data.startswith("script_")

    def handle(self, client: Client, callback_query: CallbackQuery) -> None:
        context = self.get_common_context(client, callback_query)

        if self.acc is None:
            self.answer_and_log(callback_query, "❌ 需要配置 String Session", show_alert=True)
            return

        self.dispatch_context(
            context,
            {
                "script_add_start": self._handle_add_start,
                "script_list": self._handle_list,
            },
            (
                ("script_view_", self._handle_view),
                ("script_toggle_", self._handle_toggle),
                ("script_delay_", self._handle_delay),
                ("script_remove_", self._handle_remove),
            ),
        )

    def _handle_add_start(self, context: CallbackContext) -> None:
        user_states[context.user_id] = {"action": "script_add_source"}
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("❌ 取消", callback_data="menu_script")]])
        text = "**🤖 添加联动脚本**\n\n"
        text += "**步骤 1/2：** 请输入要监控的群聊\n\n"
        text += "可以发送：\n"
        text += "• 群聊/频道用户名（如 `@group_name`）\n"
        text += "• 群聊/频道 chat_id（如 `-1001234567890`）\n"
        text += "• 转发一条来自该群聊的消息"
        self.bot.edit_message_text(context.chat_id, context.message_id, text, reply_markup=keyboard)
        self.answer_and_log(context.callback_query)

    def _handle_list(self, context: CallbackContext) -> None:
        manager = get_pt_pay_monitor_manager()
        tasks = manager.list_user_tasks(context.user_id)
        if not tasks:
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回", callback_data="menu_script")]])
            self.bot.edit_message_text(context.chat_id, context.message_id, "**🤖 脚本列表**\n\n暂无联动脚本", reply_markup=keyboard)
            self.answer_and_log(context.callback_query, "暂无脚本")
            return

        buttons = [
            [
                InlineKeyboardButton(
                    f"{'🟢' if task.enabled else '⚪️'} {task.source_name} → {task.target_bot_name}",
                    callback_data=f"script_view_{task.task_id}",
                )
            ]
            for task in tasks
        ]
        buttons.append([InlineKeyboardButton("🔙 返回", callback_data="menu_script")])
        keyboard = InlineKeyboardMarkup(buttons)
        text = f"**🤖 脚本列表**\n\n共 **{len(tasks)}** 个联动脚本\n点击条目查看详情"
        self.bot.edit_message_text(context.chat_id, context.message_id, text, reply_markup=keyboard)
        self.answer_and_log(context.callback_query)

    def _handle_view(self, context: CallbackContext) -> None:
        task_id = context.data.removeprefix("script_view_")
        manager = get_pt_pay_monitor_manager()
        task = manager.get_user_task(context.user_id, task_id)
        if task is None:
            self.answer_and_log(context.callback_query, "❌ 脚本不存在", show_alert=True)
            return
        self._render_task_detail(context.chat_id, context.message_id, task)
        self.answer_and_log(context.callback_query)

    def _handle_toggle(self, context: CallbackContext) -> None:
        task_id = context.data.removeprefix("script_toggle_")
        manager = get_pt_pay_monitor_manager()
        try:
            task = manager.toggle_task(context.user_id, task_id)
        except ValueError as exc:
            self.answer_and_log(context.callback_query, f"❌ {str(exc)}", show_alert=True)
            return

        self._render_task_detail(context.chat_id, context.message_id, task)
        tip = "✅ 已启动" if task.enabled else "⏹ 已停止"
        self.answer_and_log(context.callback_query, tip)

    def _handle_delay(self, context: CallbackContext) -> None:
        task_id = context.data.removeprefix("script_delay_")
        manager = get_pt_pay_monitor_manager()
        task = manager.get_user_task(context.user_id, task_id)
        if task is None:
            self.answer_and_log(context.callback_query, "❌ 脚本不存在", show_alert=True)
            return

        user_states[context.user_id] = {"action": "script_set_delay", "task_id": task_id}
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("❌ 取消", callback_data=f"script_view_{task_id}")]])
        text = "**⏱ 设置触发延时**\n\n"
        text += f"当前设置：`{describe_trigger_delay_spec(task.trigger_delay_spec)}`\n\n"
        text += "请输入延时秒数：\n"
        text += "• 固定值：`5` 表示每次检测后固定等待 5 秒\n"
        text += "• 随机范围：`0-100` 表示每次检测后在 0 到 100 秒内随机等待\n"
        text += "• `0` 表示立即发送"
        self.bot.edit_message_text(context.chat_id, context.message_id, text, reply_markup=keyboard)
        self.answer_and_log(context.callback_query)

    def _handle_remove(self, context: CallbackContext) -> None:
        task_id = context.data.removeprefix("script_remove_")
        manager = get_pt_pay_monitor_manager()
        try:
            task = manager.remove_task(context.user_id, task_id)
        except ValueError as exc:
            self.answer_and_log(context.callback_query, f"❌ {str(exc)}", show_alert=True)
            return

        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回脚本管理", callback_data="menu_script")]])
        text = "**✅ 联动脚本已删除**\n\n"
        text += f"监控群：`{task.source_name}`\n"
        text += f"目标对象：`{task.target_bot_name}`"
        self.bot.edit_message_text(context.chat_id, context.message_id, text, reply_markup=keyboard)
        self.answer_and_log(context.callback_query, "✅ 删除成功")

    def _render_task_detail(self, chat_id: int, message_id: int, task: PTPayTaskConfig) -> None:
        text = "**🤖 联动脚本详情**\n\n"
        text += f"监控群：`{task.source_name}`\n"
        text += f"源 chat_id：`{task.source_chat_id}`\n"
        text += f"目标对象：`{task.target_bot_name}`\n"
        text += f"目标 chat_id：`{task.target_bot_id}`\n"
        text += f"命令：`{task.command_prefix}`\n"
        text += f"触发延时：`{describe_trigger_delay_spec(task.trigger_delay_spec)}`\n"
        text += f"成功关键字：`{', '.join(task.success_keywords)}`\n"
        text += f"状态：{'🟢 运行中' if task.enabled else '⚪️ 已停止'}"

        toggle_label = "⏹ 停止脚本" if task.enabled else "▶️ 启动脚本"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(toggle_label, callback_data=f"script_toggle_{task.task_id}")],
            [InlineKeyboardButton("⏱ 设置延时", callback_data=f"script_delay_{task.task_id}")],
            [InlineKeyboardButton("🗑 删除脚本", callback_data=f"script_remove_{task.task_id}")],
            [InlineKeyboardButton("🔙 返回列表", callback_data="script_list")],
        ])
        self.bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)
