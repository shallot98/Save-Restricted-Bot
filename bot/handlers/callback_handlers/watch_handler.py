"""
Watch callback handler - 监控回调处理器

处理监控相关的回调：watch_add, watch_list, watch_remove, watch_view

Architecture: Uses new layered architecture
- src/core/container for service access
"""

from pyrogram import Client
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from .base import CallbackHandler
from bot.utils.status import user_states
from bot.handlers.watch_task_utils import extract_watch_id, resolve_watch_entry

# New architecture imports
from src.core.container import get_watch_service


class WatchCallbackHandler(CallbackHandler):
    """监控回调处理器"""

    def can_handle(self, data: str) -> bool:
        """判断是否为监控回调"""
        return data.startswith("watch_") or data.startswith("set_dest_") or data.startswith("dest_")

    def handle(self, client: Client, callback_query: CallbackQuery) -> None:
        """处理监控回调"""
        params = self.get_common_params(callback_query)
        data = params['data']
        chat_id = params['chat_id']
        message_id = params['message_id']
        user_id = params['user_id']

        if data == "watch_add_start":
            self._handle_add_start(callback_query, chat_id, message_id, user_id)
        elif data == "watch_list":
            self._handle_list(callback_query, chat_id, message_id, user_id)
        elif data == "watch_remove_start":
            self._handle_remove_start(callback_query, chat_id, message_id, user_id)
        elif data.startswith("watch_view_"):
            self._handle_view(callback_query, chat_id, message_id, user_id, data)
        elif data.startswith("watch_remove_"):
            self._handle_remove(callback_query, chat_id, message_id, user_id, data)
        elif data.startswith("set_dest_"):
            self._handle_set_dest(callback_query, chat_id, message_id, user_id, data)
        elif data == "dest_custom":
            self._handle_dest_custom(callback_query, chat_id, message_id, user_id)
        elif data == "watch_mode_record":
            self._handle_mode_record(callback_query, chat_id, message_id, user_id)
        elif data == "watch_mode_forward":
            self._handle_mode_forward(callback_query, chat_id, message_id, user_id)

    def _handle_add_start(self, callback_query: CallbackQuery, chat_id: int, message_id: int, user_id: str) -> None:
        """处理添加监控开始"""
        user_states[user_id] = {"action": "add_source"}

        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("❌ 取消", callback_data="menu_watch")]])

        text = "**➕ 添加监控任务**\n\n"
        text += "**步骤 1/2：** 请发送来源频道/群组\n\n"
        text += "可以发送：\n"
        text += "• 输入 `me` 监控自己的收藏夹\n"
        text += "• 频道/群组用户名（如 `@channel_name`）\n"
        text += "• 频道/群组ID（如 `-1001234567890`）\n"
        text += "• 转发一条来自该频道/群组的消息\n\n"
        text += "💡 机器人需要能够访问该频道/群组"

        self.bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)
        self.answer_and_log(callback_query)

    def _handle_list(self, callback_query: CallbackQuery, chat_id: int, message_id: int, user_id: str) -> None:
        """处理查看监控列表"""
        watch_service = get_watch_service()
        watch_config = watch_service.get_all_configs_dict()

        if user_id not in watch_config or not watch_config[user_id]:
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回", callback_data="menu_watch")]])
            self.bot.edit_message_text(chat_id, message_id, "**📋 监控列表**\n\n暂无监控任务\n\n点击\"添加监控\"开始设置", reply_markup=keyboard)
            self.answer_and_log(callback_query, "暂无监控任务")
            return

        buttons = []
        for idx, (watch_key, watch_data) in enumerate(watch_config[user_id].items(), 1):
            source, dest, record_mode = self._parse_watch_data(watch_key, watch_data)
            source_display = source if len(source) <= 15 else source[:12] + "..."
            dest_display = dest if len(dest) <= 15 else dest[:12] + "..."
            task_ref = extract_watch_id(watch_data) or str(idx)
            buttons.append([InlineKeyboardButton(f"{idx}. {source_display} ➡️ {dest_display}", callback_data=f"watch_view_{task_ref}")])

        buttons.append([InlineKeyboardButton("🔙 返回", callback_data="menu_watch")])
        keyboard = InlineKeyboardMarkup(buttons)

        text = "**📋 监控任务列表**\n\n"
        text += f"共 **{len(watch_config[user_id])}** 个监控任务\n\n"
        text += "点击任务查看详情和编辑 👇"

        self.bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)
        self.answer_and_log(callback_query)

    def _handle_remove_start(self, callback_query: CallbackQuery, chat_id: int, message_id: int, user_id: str) -> None:
        """处理删除监控开始"""
        watch_service = get_watch_service()
        watch_config = watch_service.get_all_configs_dict()

        if user_id not in watch_config or not watch_config[user_id]:
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回", callback_data="menu_watch")]])
            self.bot.edit_message_text(chat_id, message_id, "**🗑 删除监控**\n\n暂无监控任务可删除", reply_markup=keyboard)
            self.answer_and_log(callback_query, "暂无监控任务")
            return

        buttons = []
        for idx, (watch_key, watch_data) in enumerate(watch_config[user_id].items(), 1):
            source, dest, _ = self._parse_watch_data(watch_key, watch_data)
            task_ref = extract_watch_id(watch_data) or str(idx)
            buttons.append([InlineKeyboardButton(f"🗑 {idx}. {source} ➡️ {dest}", callback_data=f"watch_remove_{task_ref}")])

        buttons.append([InlineKeyboardButton("❌ 取消", callback_data="menu_watch")])
        keyboard = InlineKeyboardMarkup(buttons)

        text = "**🗑 删除监控**\n\n"
        text += "选择要删除的监控任务："

        self.bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)
        self.answer_and_log(callback_query)

    def _handle_view(self, callback_query: CallbackQuery, chat_id: int, message_id: int, user_id: str, data: str) -> None:
        """处理查看监控详情"""
        token = data.split("_")[2]
        watch_service = get_watch_service()
        watch_config = watch_service.get_all_configs_dict()

        if user_id not in watch_config or not watch_config[user_id]:
            self.answer_and_log(callback_query, "❌ 监控任务不存在", show_alert=True)
            return

        watch_key, watch_data, watch_id = resolve_watch_entry(watch_config[user_id], token)
        if not watch_key:
            self.answer_and_log(callback_query, "❌ 任务编号无效", show_alert=True)
            return

        task_ref = watch_id or token

        # 解析监控数据
        if isinstance(watch_data, dict):
            source_id = watch_data.get("source", watch_key.split("|")[0] if "|" in watch_key else watch_key)
            dest = watch_data.get("dest", watch_key.split("|")[1] if "|" in watch_key else "unknown")
            whitelist = watch_data.get("whitelist", [])
            blacklist = watch_data.get("blacklist", [])
            whitelist_regex = watch_data.get("whitelist_regex", [])
            blacklist_regex = watch_data.get("blacklist_regex", [])
            preserve_source = watch_data.get("preserve_forward_source", False)
            forward_mode = watch_data.get("forward_mode", "full")
            extract_patterns = watch_data.get("extract_patterns", [])
            record_mode = watch_data.get("record_mode", False)
        else:
            # 旧格式兼容
            source_id = watch_key
            dest = watch_data
            whitelist = []
            blacklist = []
            whitelist_regex = []
            blacklist_regex = []
            preserve_source = False
            forward_mode = "full"
            extract_patterns = []
            record_mode = False

        # 处理 None 值
        if source_id is None:
            source_id = "未知来源"
        if dest is None:
            dest = "未知目标"

        # 构建详情文本
        text = f"**📋 监控任务详情**\n\n"
        text += f"**来源：** `{source_id}`\n"

        if record_mode:
            text += f"**模式：** 📝 记录模式（保存到网页）\n\n"
        else:
            text += f"**目标：** `{dest}`\n\n"
            text += f"**转发模式：** {'🎯 提取模式' if forward_mode == 'extract' else '📦 完整转发'}\n"
            text += f"**保留来源：** {'✅ 是' if preserve_source else '❌ 否'}\n"

        text += "\n**过滤规则：**\n"
        if whitelist:
            text += f"🟢 关键词白名单: `{', '.join(whitelist)}`\n"
        if blacklist:
            text += f"🔴 关键词黑名单: `{', '.join(blacklist)}`\n"
        if whitelist_regex:
            text += f"🟢 正则白名单: `{', '.join(whitelist_regex)}`\n"
        if blacklist_regex:
            text += f"🔴 正则黑名单: `{', '.join(blacklist_regex)}`\n"
        if not (whitelist or blacklist or whitelist_regex or blacklist_regex):
            text += "⏭ 无过滤（转发所有消息）\n"

        if forward_mode == "extract" and extract_patterns:
            text += f"\n**提取规则：**\n"
            for pattern in extract_patterns:
                text += f"• `{pattern}`\n"

        # 构建按钮
        buttons = [[InlineKeyboardButton("✏️ 编辑过滤规则", callback_data=f"edit_filter_{task_ref}")]]
        if not record_mode:
            buttons.append([InlineKeyboardButton("📤 切换保留来源", callback_data=f"edit_preserve_{task_ref}")])
        buttons.append([InlineKeyboardButton("🗑 删除此监控", callback_data=f"watch_remove_{task_ref}")])
        buttons.append([InlineKeyboardButton("🔙 返回列表", callback_data="watch_list")])

        keyboard = InlineKeyboardMarkup(buttons)
        self.bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)
        self.answer_and_log(callback_query)

    def _handle_remove(self, callback_query: CallbackQuery, chat_id: int, message_id: int, user_id: str, data: str) -> None:
        """处理删除监控"""
        token = data.split("_")[2]
        watch_service = get_watch_service()
        watch_config = watch_service.get_all_configs_dict()

        if user_id not in watch_config or not watch_config[user_id]:
            self.answer_and_log(callback_query, "❌ 监控任务不存在", show_alert=True)
            return

        watch_key, watch_data, _watch_id = resolve_watch_entry(watch_config[user_id], token)
        if not watch_key:
            self.answer_and_log(callback_query, "❌ 任务编号无效", show_alert=True)
            return

        source_id, dest_id, _ = self._parse_watch_data(watch_key, watch_data)

        del watch_config[user_id][watch_key]

        if not watch_config[user_id]:
            del watch_config[user_id]

        watch_service.save_config_dict(watch_config)

        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回监控管理", callback_data="menu_watch")]])
        text = f"**✅ 监控任务已删除**\n\n来源：`{source_id}`\n目标：`{dest_id}`"

        self.bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)
        self.answer_and_log(callback_query, "✅ 删除成功")

    def _handle_set_dest(self, callback_query: CallbackQuery, chat_id: int, message_id: int, user_id: str, data: str) -> None:
        """处理设置目标"""
        from bot.handlers.watch_setup import show_filter_options

        dest_choice = data.split("_")[2]

        if user_id not in user_states or "source_id" not in user_states[user_id]:
            self.answer_and_log(callback_query, "❌ 会话已过期，请重新开始", show_alert=True)
            return

        if dest_choice == "me":
            user_states[user_id]["dest_id"] = "me"
            user_states[user_id]["dest_name"] = "个人收藏"

        show_filter_options(chat_id, message_id, user_id)
        self.answer_and_log(callback_query)

    def _handle_dest_custom(self, callback_query: CallbackQuery, chat_id: int, message_id: int, user_id: str) -> None:
        """处理自定义目标"""
        user_states[user_id]["action"] = "add_dest"

        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("❌ 取消", callback_data="menu_watch")]])

        text = "**➕ 添加监控任务**\n\n"
        text += "**步骤 3：** 请发送目标频道/群组\n\n"
        text += "可以发送：\n"
        text += "• 频道/群组用户名（如 `@channel_name`）\n"
        text += "• 频道/群组ID（如 `-1001234567890`）\n"
        text += "• 转发一条来自该频道/群组的消息\n\n"
        text += "💡 机器人需要有发送消息的权限"

        self.bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)
        self.answer_and_log(callback_query)

    def _handle_mode_record(self, callback_query: CallbackQuery, chat_id: int, message_id: int, user_id: str) -> None:
        """处理记录模式"""
        from bot.handlers.watch_setup import show_filter_options_single

        if user_id not in user_states or "source_id" not in user_states[user_id]:
            self.answer_and_log(callback_query, "❌ 会话已过期，请重新开始", show_alert=True)
            return

        user_states[user_id]["dest_id"] = None
        user_states[user_id]["dest_name"] = "网页笔记"
        user_states[user_id]["record_mode"] = True

        show_filter_options_single(chat_id, message_id, user_id)
        self.answer_and_log(callback_query)

    def _handle_mode_forward(self, callback_query: CallbackQuery, chat_id: int, message_id: int, user_id: str) -> None:
        """处理转发模式"""
        if user_id not in user_states or "source_id" not in user_states[user_id]:
            self.answer_and_log(callback_query, "❌ 会话已过期，请重新开始", show_alert=True)
            return

        user_states[user_id]["action"] = "add_dest"
        user_states[user_id]["record_mode"] = False

        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("❌ 取消", callback_data="menu_watch")]])

        source_name = user_states[user_id].get("source_name", "未知")

        text = "**➕ 添加监控任务**\n\n"
        text += f"✅ 来源已设置：`{source_name}`\n\n"
        text += "**步骤 3：** 请输入转发目标\n\n"
        text += "可以输入：\n"
        text += "• `me` - 转发到你的收藏夹\n"
        text += "• 频道/群组用户名（如 `@channel_name`）\n"
        text += "• 频道/群组ID（如 `-1001234567890`）\n"
        text += "• 转发一条来自目标频道/群组的消息\n\n"
        text += "💡 输入 `me` 表示转发到收藏夹"

        self.bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)
        self.answer_and_log(callback_query)

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
