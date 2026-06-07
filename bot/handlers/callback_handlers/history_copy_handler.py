"""History copy keyboard callback handler."""

from __future__ import annotations

from datetime import datetime

from pyrogram import Client
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from bot.services.history_copy_task_manager import get_history_copy_task_manager
from bot.services.history_copy_task_models import (
    RESTARTABLE_STATUSES,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_RUNNING,
    HistoryCopyTaskConfig,
    describe_history_limit,
    describe_task_status,
)
from bot.utils.status import user_states

from .base import CallbackContext, CallbackHandler


class HistoryCopyCallbackHandler(CallbackHandler):
    """Handle keyboard flows for history copy tasks."""

    def can_handle(self, data: str) -> bool:
        return data.startswith("history_copy_")

    def handle(self, client: Client, callback_query: CallbackQuery) -> None:
        context = self.get_common_context(client, callback_query)

        if self.acc is None:
            self.answer_and_log(callback_query, "❌ 需要配置 String Session", show_alert=True)
            return

        self.dispatch_context(
            context,
            {
                "history_copy_add_start": self._handle_add_start,
                "history_copy_list": self._handle_list,
            },
            (
                ("history_copy_view_", self._handle_view),
                ("history_copy_restart_", self._handle_restart),
                ("history_copy_remove_", self._handle_remove),
            ),
        )

    def _handle_add_start(self, context: CallbackContext) -> None:
        user_states[context.user_id] = {"action": "history_copy_add_source"}
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ 取消", callback_data="menu_script_history_copy")]]
        )
        text = "**📚 新建历史复制任务**\n\n"
        text += "**步骤 1/3：** 请输入来源群聊/频道\n\n"
        text += "可以发送：\n"
        text += "• 群聊/频道用户名（如 `@source_channel`）\n"
        text += "• 群聊/频道 chat_id（如 `-1001234567890`）\n"
        text += "• 转发一条来自该群聊的消息\n"
        text += "• 输入 `me` 使用收藏夹"
        self.bot.edit_message_text(context.chat_id, context.message_id, text, reply_markup=keyboard)
        self.answer_and_log(context.callback_query)

    def _handle_list(self, context: CallbackContext) -> None:
        manager = get_history_copy_task_manager()
        tasks = manager.list_user_tasks(context.user_id)
        if not tasks:
            keyboard = InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 返回", callback_data="menu_script_history_copy")]]
            )
            self.bot.edit_message_text(
                context.chat_id,
                context.message_id,
                "**📚 历史复制任务**\n\n暂无任务记录",
                reply_markup=keyboard,
            )
            self.answer_and_log(context.callback_query, "暂无历史复制任务")
            return

        buttons = [
            [InlineKeyboardButton(_build_task_label(task), callback_data=f"history_copy_view_{task.task_id}")]
            for task in tasks
        ]
        buttons.append([InlineKeyboardButton("🔙 返回", callback_data="menu_script_history_copy")])
        keyboard = InlineKeyboardMarkup(buttons)
        text = f"**📚 历史复制任务**\n\n共 **{len(tasks)}** 个任务，点击条目查看详情"
        self.bot.edit_message_text(context.chat_id, context.message_id, text, reply_markup=keyboard)
        self.answer_and_log(context.callback_query)

    def _handle_view(self, context: CallbackContext) -> None:
        task_id = context.data.removeprefix("history_copy_view_")
        manager = get_history_copy_task_manager()
        task = manager.get_user_task(context.user_id, task_id)
        if task is None:
            self.answer_and_log(context.callback_query, "❌ 历史复制任务不存在", show_alert=True)
            return
        updated = self._render_task_detail(context.chat_id, context.message_id, task)
        tip = "" if updated else "状态未变化"
        self.answer_and_log(context.callback_query, tip)

    def _handle_remove(self, context: CallbackContext) -> None:
        task_id = context.data.removeprefix("history_copy_remove_")
        manager = get_history_copy_task_manager()
        try:
            task = manager.remove_task(context.user_id, task_id)
        except ValueError as exc:
            self.answer_and_log(context.callback_query, f"❌ {str(exc)}", show_alert=True)
            return

        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 返回历史复制菜单", callback_data="menu_script_history_copy")]]
        )
        text = "**✅ 历史复制任务记录已删除**\n\n"
        text += f"来源：`{task.source_name}`\n"
        text += f"目标：`{task.dest_name}`"
        self.bot.edit_message_text(context.chat_id, context.message_id, text, reply_markup=keyboard)
        self.answer_and_log(context.callback_query, "✅ 删除成功")

    def _handle_restart(self, context: CallbackContext) -> None:
        task_id = context.data.removeprefix("history_copy_restart_")
        manager = get_history_copy_task_manager()
        try:
            task = manager.restart_task(context.user_id, task_id)
        except ValueError as exc:
            self.answer_and_log(context.callback_query, f"❌ {str(exc)}", show_alert=True)
            return

        self._render_task_detail(context.chat_id, context.message_id, task)
        self.answer_and_log(context.callback_query, "✅ 已重启")

    def _render_task_detail(
        self,
        chat_id: int,
        message_id: int,
        task: HistoryCopyTaskConfig,
    ) -> bool:
        try:
            self.bot.edit_message_text(
                chat_id,
                message_id,
                _build_task_detail_text(task),
                reply_markup=_build_task_detail_keyboard(task),
            )
        except Exception as exc:
            if _is_message_not_modified(exc):
                return False
            raise
        return True


def _build_task_label(task: HistoryCopyTaskConfig) -> str:
    prefix = {
        STATUS_RUNNING: "🟡",
        STATUS_COMPLETED: "✅",
        STATUS_FAILED: "❌",
    }.get(task.status, "⚠️")
    return f"{prefix} {task.source_name} → {task.dest_name}"


def _format_ts(value: float) -> str:
    if value <= 0:
        return "-"
    return datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M:%S")


def _task_stats_text(task: HistoryCopyTaskConfig) -> str:
    if task.status_message:
        return f"\n统计：`{task.status_message}`\n"
    return (
        f"\n统计：`scanned={task.scanned_count} copied={task.copied_count} "
        f"skipped={task.skipped_count} failed={task.failed_count}`\n"
    )


def _task_status_hint(task: HistoryCopyTaskConfig) -> str:
    if task.status == STATUS_RUNNING:
        return "\n运行中任务不支持中止；可稍后点击“刷新状态”查看最新结果。"
    if task.status in RESTARTABLE_STATUSES:
        return "\n该任务已停止，可点击“重启任务”继续使用原断点库执行。"
    return ""


def _build_task_detail_text(task: HistoryCopyTaskConfig) -> str:
    lines = [
        "**📚 历史复制任务详情**\n",
        f"来源：`{task.source_name}`",
        f"来源引用：`{task.source_chat_ref}`",
    ]
    if task.source_chat_id:
        lines.append(f"来源 chat_id：`{task.source_chat_id}`")
    lines.extend([
        f"目标：`{task.dest_name}`",
        f"目标引用：`{task.dest_chat_ref}`",
    ])
    if task.dest_chat_id:
        lines.append(f"目标 chat_id：`{task.dest_chat_id}`")
    lines.extend([
        f"范围：`{describe_history_limit(task.history_limit)}`",
        f"状态：{describe_task_status(task.status)}",
        f"断点库：`{task.state_db_path}`",
    ])
    if task.started_at:
        lines.append(f"开始时间：`{_format_ts(task.started_at)}`")
    if task.finished_at:
        lines.append(f"结束时间：`{_format_ts(task.finished_at)}`")
    text = "\n".join(lines) + "\n"
    if task.error_message:
        return text + _task_stats_text(task) + f"\n错误：`{task.error_message}`\n" + _task_status_hint(task)
    return text + _task_stats_text(task) + _task_status_hint(task)


def _build_task_detail_keyboard(task: HistoryCopyTaskConfig) -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton("🔄 刷新状态", callback_data=f"history_copy_view_{task.task_id}")]]
    if task.status in RESTARTABLE_STATUSES:
        buttons.append([InlineKeyboardButton("▶️ 重启任务", callback_data=f"history_copy_restart_{task.task_id}")])
    if task.status != STATUS_RUNNING:
        buttons.append([InlineKeyboardButton("🗑 删除记录", callback_data=f"history_copy_remove_{task.task_id}")])
    buttons.append([InlineKeyboardButton("🔙 返回列表", callback_data="history_copy_list")])
    return InlineKeyboardMarkup(buttons)


def _is_message_not_modified(exc: Exception) -> bool:
    return type(exc).__name__ == "MessageNotModified" or "MESSAGE_NOT_MODIFIED" in str(exc)
