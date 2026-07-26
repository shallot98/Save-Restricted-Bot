"""
Filter callback handler - 过滤回调处理器

处理过滤相关的回调：filter_whitelist, filter_blacklist, filter_regex, skip_*
"""

from pyrogram import Client
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from .base import CallbackContext, CallbackHandler
from bot.utils.status import user_states
from bot.handlers.watch_setup import (
    show_filter_options, show_filter_options_single,
    show_preserve_source_options, complete_watch_setup_single
)


class FilterCallbackHandler(CallbackHandler):
    """过滤回调处理器"""

    def can_handle(self, data: str) -> bool:
        """判断是否为过滤回调"""
        return (data.startswith("filter_") or
                data.startswith("skip_") or
                data.startswith("clear_filters") or
                data.startswith("preserve_"))

    def handle(self, client: Client, callback_query: CallbackQuery) -> None:
        """处理过滤回调"""
        context = self.get_common_context(client, callback_query)
        self.dispatch_context(
            context,
            {
                "filter_done": self._handle_filter_done,
                "filter_done_single": self._handle_filter_done_single,
                "clear_filters": self._handle_clear_filters,
                "clear_filters_single": self._handle_clear_filters_single,
                "filter_whitelist": self._handle_filter_whitelist,
                "filter_blacklist": self._handle_filter_blacklist,
                "filter_regex_whitelist": self._handle_filter_regex_whitelist,
                "filter_regex_blacklist": self._handle_filter_regex_blacklist,
                "skip_whitelist": self._handle_skip_whitelist,
                "skip_blacklist": self._handle_skip_blacklist,
                "skip_regex_whitelist": self._handle_skip_regex_whitelist,
                "skip_regex_blacklist": self._handle_skip_regex_blacklist,
            },
            (("preserve_", self._handle_preserve),),
        )

    def _handle_filter_done(self, context: CallbackContext) -> None:
        """处理过滤完成（转发模式）"""
        if context.user_id not in user_states:
            self.answer_and_log(context.callback_query, "❌ 会话已过期", show_alert=True)
            return

        show_preserve_source_options(context.chat_id, context.message_id, context.user_id)
        self.answer_and_log(context.callback_query, "✅ 过滤规则已保存")

    def _handle_filter_done_single(self, context: CallbackContext) -> None:
        """处理过滤完成（记录模式）"""
        if context.user_id not in user_states:
            self.answer_and_log(context.callback_query, "❌ 会话已过期", show_alert=True)
            return

        whitelist = user_states[context.user_id].get("whitelist", [])
        blacklist = user_states[context.user_id].get("blacklist", [])
        whitelist_regex = user_states[context.user_id].get("whitelist_regex", [])
        blacklist_regex = user_states[context.user_id].get("blacklist_regex", [])

        msg = self.bot.send_message(context.chat_id, "⏳ 正在完成设置...")
        self.bot.delete_messages(context.chat_id, [context.message_id])
        complete_watch_setup_single(
            msg.chat.id, msg.id, context.user_id,
            whitelist, blacklist, whitelist_regex, blacklist_regex,
            watch_setup_service=self.watch_setup_service,
        )
        self.answer_and_log(context.callback_query, "✅ 过滤规则已保存")

    def _handle_clear_filters(self, context: CallbackContext) -> None:
        """处理清空过滤（转发模式）"""
        if context.user_id not in user_states:
            self.answer_and_log(context.callback_query, "❌ 会话已过期", show_alert=True)
            return

        user_states[context.user_id]["whitelist"] = []
        user_states[context.user_id]["blacklist"] = []
        user_states[context.user_id]["whitelist_regex"] = []
        user_states[context.user_id]["blacklist_regex"] = []

        show_filter_options(context.chat_id, context.message_id, context.user_id)
        self.answer_and_log(context.callback_query, "✅ 已清空所有过滤规则")

    def _handle_clear_filters_single(self, context: CallbackContext) -> None:
        """处理清空过滤（记录模式）"""
        if context.user_id not in user_states:
            self.answer_and_log(context.callback_query, "❌ 会话已过期", show_alert=True)
            return

        user_states[context.user_id]["whitelist"] = []
        user_states[context.user_id]["blacklist"] = []
        user_states[context.user_id]["whitelist_regex"] = []
        user_states[context.user_id]["blacklist_regex"] = []

        show_filter_options_single(context.chat_id, context.message_id, context.user_id)
        self.answer_and_log(context.callback_query, "✅ 已清空所有过滤规则")

    def _handle_filter_whitelist(self, context: CallbackContext) -> None:
        """处理关键词白名单"""
        user_states[context.user_id]["action"] = "add_whitelist"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏭ 跳过", callback_data="skip_whitelist")],
            [InlineKeyboardButton("❌ 取消", callback_data="menu_watch")]
        ])

        text = "**➕ 添加监控任务**\n\n"
        text += "**步骤 3：设置白名单**\n\n"
        text += "请发送白名单关键词，用逗号分隔\n\n"
        text += "示例：`重要,紧急,通知`\n\n"
        text += "💡 只有包含这些关键词的消息才会被转发"

        self.bot.edit_message_text(context.chat_id, context.message_id, text, reply_markup=keyboard)
        self.answer_and_log(context.callback_query)

    def _handle_filter_blacklist(self, context: CallbackContext) -> None:
        """处理关键词黑名单"""
        user_states[context.user_id]["action"] = "add_blacklist"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏭ 跳过", callback_data="skip_blacklist")],
            [InlineKeyboardButton("❌ 取消", callback_data="menu_watch")]
        ])

        text = "**➕ 添加监控任务**\n\n"
        text += "**步骤 3：设置黑名单**\n\n"
        text += "请发送黑名单关键词，用逗号分隔\n\n"
        text += "示例：`广告,推广,垃圾`\n\n"
        text += "💡 包含这些关键词的消息不会被转发"

        self.bot.edit_message_text(context.chat_id, context.message_id, text, reply_markup=keyboard)
        self.answer_and_log(context.callback_query)

    def _handle_filter_regex_whitelist(self, context: CallbackContext) -> None:
        """处理正则白名单"""
        user_states[context.user_id]["action"] = "add_regex_whitelist"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏭ 跳过", callback_data="skip_regex_whitelist")],
            [InlineKeyboardButton("❌ 取消", callback_data="menu_watch")]
        ])

        text = "**➕ 添加监控任务**\n\n"
        text += "**步骤 3：设置正则白名单**\n\n"
        text += "请发送正则表达式，用逗号分隔\n\n"
        text += "示例：`https?://[^\\s]+,\\d{6,}`\n\n"
        text += "💡 只有匹配这些正则的消息才会被转发"

        self.bot.edit_message_text(context.chat_id, context.message_id, text, reply_markup=keyboard)
        self.answer_and_log(context.callback_query)

    def _handle_filter_regex_blacklist(self, context: CallbackContext) -> None:
        """处理正则黑名单"""
        user_states[context.user_id]["action"] = "add_regex_blacklist"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏭ 跳过", callback_data="skip_regex_blacklist")],
            [InlineKeyboardButton("❌ 取消", callback_data="menu_watch")]
        ])

        text = "**➕ 添加监控任务**\n\n"
        text += "**步骤 3：设置正则黑名单**\n\n"
        text += "请发送正则表达式，用逗号分隔\n\n"
        text += "示例：`广告|推广|垃圾`\n\n"
        text += "💡 匹配这些正则的消息不会被转发"

        self.bot.edit_message_text(context.chat_id, context.message_id, text, reply_markup=keyboard)
        self.answer_and_log(context.callback_query)

    def _handle_skip_whitelist(self, context: CallbackContext) -> None:
        """处理跳过关键词白名单"""
        if context.user_id in user_states:
            user_states[context.user_id]["whitelist"] = []
            msg = self.bot.send_message(context.chat_id, "⏳ 继续设置...")
            if user_states[context.user_id].get("record_mode"):
                show_filter_options_single(context.chat_id, msg.id, context.user_id)
            else:
                show_filter_options(context.chat_id, msg.id, context.user_id)
            self.bot.delete_messages(context.chat_id, [context.message_id])
            self.answer_and_log(context.callback_query, "已跳过关键词白名单")

    def _handle_skip_blacklist(self, context: CallbackContext) -> None:
        """处理跳过关键词黑名单"""
        if context.user_id in user_states:
            user_states[context.user_id]["blacklist"] = []
            msg = self.bot.send_message(context.chat_id, "⏳ 继续设置...")
            if user_states[context.user_id].get("record_mode"):
                show_filter_options_single(context.chat_id, msg.id, context.user_id)
            else:
                show_filter_options(context.chat_id, msg.id, context.user_id)
            self.bot.delete_messages(context.chat_id, [context.message_id])
            self.answer_and_log(context.callback_query, "已跳过关键词黑名单")

    def _handle_skip_regex_whitelist(self, context: CallbackContext) -> None:
        """处理跳过正则白名单"""
        if context.user_id in user_states:
            user_states[context.user_id]["whitelist_regex"] = []
            msg = self.bot.send_message(context.chat_id, "⏳ 继续设置...")
            if user_states[context.user_id].get("record_mode"):
                show_filter_options_single(context.chat_id, msg.id, context.user_id)
            else:
                show_filter_options(context.chat_id, msg.id, context.user_id)
            self.bot.delete_messages(context.chat_id, [context.message_id])
            self.answer_and_log(context.callback_query, "已跳过正则白名单")

    def _handle_skip_regex_blacklist(self, context: CallbackContext) -> None:
        """处理跳过正则黑名单"""
        if context.user_id in user_states:
            user_states[context.user_id]["blacklist_regex"] = []
            msg = self.bot.send_message(context.chat_id, "⏳ 继续设置...")
            if user_states[context.user_id].get("record_mode"):
                show_filter_options_single(context.chat_id, msg.id, context.user_id)
            else:
                show_filter_options(context.chat_id, msg.id, context.user_id)
            self.bot.delete_messages(context.chat_id, [context.message_id])
            self.answer_and_log(context.callback_query, "已跳过正则黑名单")

    def _handle_preserve(self, context: CallbackContext) -> None:
        """处理保留来源选项"""
        from bot.handlers.watch_setup import show_forward_mode_options

        preserve = context.data.split("_")[1] == "yes"

        if context.user_id not in user_states:
            self.answer_and_log(context.callback_query, "❌ 会话已过期", show_alert=True)
            return

        whitelist = user_states[context.user_id].get("whitelist", [])
        blacklist = user_states[context.user_id].get("blacklist", [])
        whitelist_regex = user_states[context.user_id].get("whitelist_regex", [])
        blacklist_regex = user_states[context.user_id].get("blacklist_regex", [])

        show_forward_mode_options(context.chat_id, context.message_id, context.user_id, whitelist, blacklist, whitelist_regex, blacklist_regex, preserve)
        self.answer_and_log(context.callback_query)
