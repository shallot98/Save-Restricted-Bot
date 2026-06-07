"""
Mode callback handler - 模式回调处理器

处理模式相关的回调：mode_single, mode_forward, fwdmode_*, extract_*
"""

from pyrogram import Client
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from .base import CallbackContext, CallbackHandler
from bot.utils.status import user_states
from bot.handlers.watch_setup import (
    show_filter_options, show_filter_options_single,
    show_forward_mode_options, complete_watch_setup
)


class ModeCallbackHandler(CallbackHandler):
    """模式回调处理器"""

    def can_handle(self, data: str) -> bool:
        """判断是否为模式回调"""
        return (data.startswith("mode_") or
                data.startswith("fwdmode_") or
                data.startswith("extract_") or
                data == "back_to_forward_mode")

    def handle(self, client: Client, callback_query: CallbackQuery) -> None:
        """处理模式回调"""
        context = self.get_common_context(client, callback_query)
        self.dispatch_context(
            context,
            {
                "mode_single": self._handle_mode_single,
                "mode_forward": self._handle_mode_forward,
                "extract_custom": self._handle_extract_custom,
                "extract_magnet": self._handle_extract_magnet,
                "back_to_forward_mode": self._handle_back_to_forward_mode,
            },
            (("fwdmode_", self._handle_fwdmode),),
        )

    def _handle_mode_single(self, context: CallbackContext) -> None:
        """处理记录模式"""
        if context.user_id not in user_states or "source_id" not in user_states[context.user_id]:
            self.answer_and_log(context.callback_query, "❌ 会话已过期，请重新开始", show_alert=True)
            return

        user_states[context.user_id]["dest_id"] = None
        user_states[context.user_id]["dest_name"] = "记录模式"
        user_states[context.user_id]["record_mode"] = True

        show_filter_options_single(context.chat_id, context.message_id, context.user_id)
        self.answer_and_log(context.callback_query)

    def _handle_mode_forward(self, context: CallbackContext) -> None:
        """处理转发模式"""
        if context.user_id not in user_states or "source_id" not in user_states[context.user_id]:
            self.answer_and_log(context.callback_query, "❌ 会话已过期，请重新开始", show_alert=True)
            return

        user_states[context.user_id]["action"] = "choose_dest"
        user_states[context.user_id]["record_mode"] = False

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💾 保存到收藏夹", callback_data="set_dest_me")],
            [InlineKeyboardButton("📤 自定义目标", callback_data="dest_custom")],
            [InlineKeyboardButton("❌ 取消", callback_data="menu_watch")]
        ])

        source_name = user_states[context.user_id].get("source_name", "未知")

        text = "**➕ 添加监控任务**\n\n"
        text += f"✅ 来源已设置：`{source_name}`\n\n"
        text += "**步骤 3：** 选择转发目标\n\n"
        text += "💾 **保存到收藏夹** - 转发到你的个人收藏\n"
        text += "📤 **自定义目标** - 转发到其他频道/群组"

        self.bot.edit_message_text(context.chat_id, context.message_id, text, reply_markup=keyboard)
        self.answer_and_log(context.callback_query)

    def _handle_fwdmode(self, context: CallbackContext) -> None:
        """处理转发模式选择"""
        mode = context.data.split("_")[1]

        if context.user_id not in user_states:
            self.answer_and_log(context.callback_query, "❌ 会话已过期", show_alert=True)
            return

        if mode == "extract":
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📝 自定义提取", callback_data="extract_custom")],
                [InlineKeyboardButton("🧲 磁力链接提取", callback_data="extract_magnet")],
                [InlineKeyboardButton("❌ 取消", callback_data="menu_watch")]
            ])

            text = "**➕ 添加监控任务**\n\n"
            text += "**选择提取类型：**\n\n"
            text += "📝 **自定义提取** - 使用正则表达式提取\n"
            text += "🧲 **磁力链接提取** - 自动提取磁力链接"

            self.bot.edit_message_text(context.chat_id, context.message_id, text, reply_markup=keyboard)
            self.answer_and_log(context.callback_query)
        else:
            # 完整转发模式，直接完成设置
            whitelist = user_states[context.user_id].get("whitelist", [])
            blacklist = user_states[context.user_id].get("blacklist", [])
            whitelist_regex = user_states[context.user_id].get("whitelist_regex", [])
            blacklist_regex = user_states[context.user_id].get("blacklist_regex", [])
            preserve_source = user_states[context.user_id].get("preserve_source", False)
            complete_watch_setup(context.chat_id, context.message_id, context.user_id, whitelist, blacklist, whitelist_regex, blacklist_regex, preserve_source, "full", [])
            self.answer_and_log(context.callback_query, "✅ 监控已添加")

    def _handle_extract_custom(self, context: CallbackContext) -> None:
        """处理自定义提取"""
        if context.user_id not in user_states:
            self.answer_and_log(context.callback_query, "❌ 会话已过期", show_alert=True)
            return

        user_states[context.user_id]["action"] = "add_extract_patterns"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ 取消", callback_data="menu_watch")]
        ])

        text = "**➕ 添加监控任务**\n\n"
        text += "**设置提取规则**\n\n"
        text += "请发送提取用的正则表达式，用逗号分隔\n\n"
        text += "示例：`https?://[^\\s]+,\\d{6,}`\n\n"
        text += "💡 消息匹配过滤规则后，将使用这些正则提取内容并转发"

        self.bot.edit_message_text(context.chat_id, context.message_id, text, reply_markup=keyboard)
        self.answer_and_log(context.callback_query, "请输入提取规则")

    def _handle_extract_magnet(self, context: CallbackContext) -> None:
        """处理磁力链接提取"""
        if context.user_id not in user_states:
            self.answer_and_log(context.callback_query, "❌ 会话已过期", show_alert=True)
            return

        whitelist = user_states[context.user_id].get("whitelist", [])
        blacklist = user_states[context.user_id].get("blacklist", [])
        whitelist_regex = user_states[context.user_id].get("whitelist_regex", [])
        blacklist_regex = user_states[context.user_id].get("blacklist_regex", [])
        preserve_source = user_states[context.user_id].get("preserve_source", False)

        magnet_pattern = r'magnet:\?xt=urn:btih:[a-zA-Z0-9]+(?:[&?][^\n\r|]*)?'
        complete_watch_setup(context.chat_id, context.message_id, context.user_id, whitelist, blacklist, whitelist_regex, blacklist_regex, preserve_source, "extract", [magnet_pattern])
        self.answer_and_log(context.callback_query, "✅ 监控已添加")

    def _handle_back_to_forward_mode(self, context: CallbackContext) -> None:
        """处理返回转发模式选择"""
        if context.user_id not in user_states:
            self.answer_and_log(context.callback_query, "❌ 会话已过期", show_alert=True)
            return

        whitelist = user_states[context.user_id].get("whitelist", [])
        blacklist = user_states[context.user_id].get("blacklist", [])
        whitelist_regex = user_states[context.user_id].get("whitelist_regex", [])
        blacklist_regex = user_states[context.user_id].get("blacklist_regex", [])
        preserve_source = user_states[context.user_id].get("preserve_source", False)

        show_forward_mode_options(context.chat_id, context.message_id, context.user_id, whitelist, blacklist, whitelist_regex, blacklist_regex, preserve_source)
        self.answer_and_log(context.callback_query)
