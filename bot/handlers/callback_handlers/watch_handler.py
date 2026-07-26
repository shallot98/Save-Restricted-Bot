"""
Watch callback handler - 监控回调处理器

处理监控相关的回调：watch_add, watch_list, watch_remove, watch_view

Architecture: Uses new layered architecture
- WatchService 由 CallbackRegistry 构造期注入（self.watch_service）
"""

from pyrogram import Client
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from .base import CallbackContext, CallbackHandler
from .watch_detail import build_watch_detail, build_watch_detail_keyboard, render_watch_detail_text
from bot.utils.status import user_states
from bot.handlers.watch_task_utils import extract_watch_id, resolve_watch_entry


class WatchCallbackHandler(CallbackHandler):
    """监控回调处理器"""

    def can_handle(self, data: str) -> bool:
        """判断是否为监控回调"""
        return data.startswith("watch_") or data.startswith("set_dest_") or data.startswith("dest_")

    def handle(self, client: Client, callback_query: CallbackQuery) -> None:
        """处理监控回调"""
        context = self.get_common_context(client, callback_query)
        self.dispatch_context(
            context,
            {
                "watch_add_start": self._handle_add_start,
                "watch_list": self._handle_list,
                "watch_remove_start": self._handle_remove_start,
                "dest_custom": self._handle_dest_custom,
                "watch_mode_record": self._handle_mode_record,
                "watch_mode_forward": self._handle_mode_forward,
            },
            (
                ("watch_view_", self._handle_view),
                ("watch_remove_", self._handle_remove),
                ("set_dest_", self._handle_set_dest),
            ),
        )

    def _handle_add_start(self, context: CallbackContext) -> None:
        """处理添加监控开始"""
        user_states[context.user_id] = {"action": "add_source"}

        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("❌ 取消", callback_data="menu_watch")]])

        text = "**➕ 添加监控任务**\n\n"
        text += "**步骤 1/2：** 请发送来源频道/群组\n\n"
        text += "可以发送：\n"
        text += "• 输入 `me` 监控自己的收藏夹\n"
        text += "• 频道/群组用户名（如 `@channel_name`）\n"
        text += "• 频道/群组ID（如 `-1001234567890`）\n"
        text += "• 转发一条来自该频道/群组的消息\n\n"
        text += "💡 机器人需要能够访问该频道/群组"

        self.bot.edit_message_text(context.chat_id, context.message_id, text, reply_markup=keyboard)
        self.answer_and_log(context.callback_query)

    def _handle_list(self, context: CallbackContext) -> None:
        """处理查看监控列表"""
        watch_service = self.watch_service
        watch_config = watch_service.get_all_configs_dict()

        if context.user_id not in watch_config or not watch_config[context.user_id]:
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回", callback_data="menu_watch")]])
            self.bot.edit_message_text(context.chat_id, context.message_id, "**📋 监控列表**\n\n暂无监控任务\n\n点击\"添加监控\"开始设置", reply_markup=keyboard)
            self.answer_and_log(context.callback_query, "暂无监控任务")
            return

        buttons = []
        for idx, (watch_key, watch_data) in enumerate(watch_config[context.user_id].items(), 1):
            source, dest, record_mode = self._parse_watch_data(watch_key, watch_data)
            source_display = source if len(source) <= 15 else source[:12] + "..."
            dest_display = dest if len(dest) <= 15 else dest[:12] + "..."
            task_ref = extract_watch_id(watch_data) or str(idx)
            buttons.append([InlineKeyboardButton(f"{idx}. {source_display} ➡️ {dest_display}", callback_data=f"watch_view_{task_ref}")])

        buttons.append([InlineKeyboardButton("🔙 返回", callback_data="menu_watch")])
        keyboard = InlineKeyboardMarkup(buttons)

        text = "**📋 监控任务列表**\n\n"
        text += f"共 **{len(watch_config[context.user_id])}** 个监控任务\n\n"
        text += "点击任务查看详情和编辑 👇"

        self.bot.edit_message_text(context.chat_id, context.message_id, text, reply_markup=keyboard)
        self.answer_and_log(context.callback_query)

    def _handle_remove_start(self, context: CallbackContext) -> None:
        """处理删除监控开始"""
        watch_service = self.watch_service
        watch_config = watch_service.get_all_configs_dict()

        if context.user_id not in watch_config or not watch_config[context.user_id]:
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回", callback_data="menu_watch")]])
            self.bot.edit_message_text(context.chat_id, context.message_id, "**🗑 删除监控**\n\n暂无监控任务可删除", reply_markup=keyboard)
            self.answer_and_log(context.callback_query, "暂无监控任务")
            return

        buttons = []
        for idx, (watch_key, watch_data) in enumerate(watch_config[context.user_id].items(), 1):
            source, dest, _ = self._parse_watch_data(watch_key, watch_data)
            task_ref = extract_watch_id(watch_data) or str(idx)
            buttons.append([InlineKeyboardButton(f"🗑 {idx}. {source} ➡️ {dest}", callback_data=f"watch_remove_{task_ref}")])

        buttons.append([InlineKeyboardButton("❌ 取消", callback_data="menu_watch")])
        keyboard = InlineKeyboardMarkup(buttons)

        text = "**🗑 删除监控**\n\n"
        text += "选择要删除的监控任务："

        self.bot.edit_message_text(context.chat_id, context.message_id, text, reply_markup=keyboard)
        self.answer_and_log(context.callback_query)

    def _handle_view(self, context: CallbackContext) -> None:
        """处理查看监控详情"""
        token = context.data.split("_")[2]
        watch_service = self.watch_service
        watch_config = watch_service.get_all_configs_dict()

        if context.user_id not in watch_config or not watch_config[context.user_id]:
            self.answer_and_log(context.callback_query, "❌ 监控任务不存在", show_alert=True)
            return

        watch_key, watch_data, watch_id = resolve_watch_entry(watch_config[context.user_id], token)
        if not watch_key:
            self.answer_and_log(context.callback_query, "❌ 任务编号无效", show_alert=True)
            return

        task_ref = watch_id or token

        detail = build_watch_detail(watch_key, watch_data)
        text = render_watch_detail_text(detail)
        keyboard = build_watch_detail_keyboard(task_ref, detail.record_mode)
        self.bot.edit_message_text(context.chat_id, context.message_id, text, reply_markup=keyboard)
        self.answer_and_log(context.callback_query)

    def _handle_remove(self, context: CallbackContext) -> None:
        """处理删除监控"""
        token = context.data.split("_")[2]
        watch_service = self.watch_service
        watch_config = watch_service.get_all_configs_dict()

        if context.user_id not in watch_config or not watch_config[context.user_id]:
            self.answer_and_log(context.callback_query, "❌ 监控任务不存在", show_alert=True)
            return

        watch_key, watch_data, _watch_id = resolve_watch_entry(watch_config[context.user_id], token)
        if not watch_key:
            self.answer_and_log(context.callback_query, "❌ 任务编号无效", show_alert=True)
            return

        source_id, dest_id, _ = self._parse_watch_data(watch_key, watch_data)

        del watch_config[context.user_id][watch_key]

        if not watch_config[context.user_id]:
            del watch_config[context.user_id]

        watch_service.save_config_dict(watch_config)

        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回监控管理", callback_data="menu_watch")]])
        text = f"**✅ 监控任务已删除**\n\n来源：`{source_id}`\n目标：`{dest_id}`"

        self.bot.edit_message_text(context.chat_id, context.message_id, text, reply_markup=keyboard)
        self.answer_and_log(context.callback_query, "✅ 删除成功")

    def _handle_set_dest(self, context: CallbackContext) -> None:
        """处理设置目标"""
        from bot.handlers.watch_setup import show_filter_options

        dest_choice = context.data.split("_")[2]

        if context.user_id not in user_states or "source_id" not in user_states[context.user_id]:
            self.answer_and_log(context.callback_query, "❌ 会话已过期，请重新开始", show_alert=True)
            return

        if dest_choice == "me":
            user_states[context.user_id]["dest_id"] = "me"
            user_states[context.user_id]["dest_name"] = "个人收藏"

        show_filter_options(context.chat_id, context.message_id, context.user_id)
        self.answer_and_log(context.callback_query)

    def _handle_dest_custom(self, context: CallbackContext) -> None:
        """处理自定义目标"""
        user_states[context.user_id]["action"] = "add_dest"

        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("❌ 取消", callback_data="menu_watch")]])

        text = "**➕ 添加监控任务**\n\n"
        text += "**步骤 3：** 请发送目标频道/群组\n\n"
        text += "可以发送：\n"
        text += "• 频道/群组用户名（如 `@channel_name`）\n"
        text += "• 频道/群组ID（如 `-1001234567890`）\n"
        text += "• 转发一条来自该频道/群组的消息\n\n"
        text += "💡 机器人需要有发送消息的权限"

        self.bot.edit_message_text(context.chat_id, context.message_id, text, reply_markup=keyboard)
        self.answer_and_log(context.callback_query)

    def _handle_mode_record(self, context: CallbackContext) -> None:
        """处理记录模式"""
        from bot.handlers.watch_setup import show_filter_options_single

        if context.user_id not in user_states or "source_id" not in user_states[context.user_id]:
            self.answer_and_log(context.callback_query, "❌ 会话已过期，请重新开始", show_alert=True)
            return

        user_states[context.user_id]["dest_id"] = None
        user_states[context.user_id]["dest_name"] = "网页笔记"
        user_states[context.user_id]["record_mode"] = True

        show_filter_options_single(context.chat_id, context.message_id, context.user_id)
        self.answer_and_log(context.callback_query)

    def _handle_mode_forward(self, context: CallbackContext) -> None:
        """处理转发模式"""
        if context.user_id not in user_states or "source_id" not in user_states[context.user_id]:
            self.answer_and_log(context.callback_query, "❌ 会话已过期，请重新开始", show_alert=True)
            return

        user_states[context.user_id]["action"] = "add_dest"
        user_states[context.user_id]["record_mode"] = False

        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("❌ 取消", callback_data="menu_watch")]])

        source_name = user_states[context.user_id].get("source_name", "未知")

        text = "**➕ 添加监控任务**\n\n"
        text += f"✅ 来源已设置：`{source_name}`\n\n"
        text += "**步骤 3：** 请输入转发目标\n\n"
        text += "可以输入：\n"
        text += "• `me` - 转发到你的收藏夹\n"
        text += "• 频道/群组用户名（如 `@channel_name`）\n"
        text += "• 频道/群组ID（如 `-1001234567890`）\n"
        text += "• 转发一条来自目标频道/群组的消息\n\n"
        text += "💡 输入 `me` 表示转发到收藏夹"

        self.bot.edit_message_text(context.chat_id, context.message_id, text, reply_markup=keyboard)
        self.answer_and_log(context.callback_query)

    def _parse_watch_data(self, watch_key: str, watch_data) -> tuple:
        """
        解析监控数据

        Returns:
            tuple: (source, dest, record_mode)
        """
        if isinstance(watch_data, dict):
            source = watch_data.get("source", watch_key.split("|")[0] if "|" in watch_key else watch_key)
            dest = watch_data.get("dest", watch_key.split("|")[1] if "|" in watch_key else "unknown")
            record_mode = watch_data.get("record_mode", False)
        else:
            source = watch_key
            dest = watch_data
            record_mode = False

        # 处理 None 值
        if source is None:
            source = "未知来源"
        if dest is None or record_mode:
            dest = "网页笔记"

        return source, dest, record_mode
