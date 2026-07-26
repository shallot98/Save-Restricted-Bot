"""
Edit callback handler - 编辑回调处理器

处理编辑相关的回调：edit_filter, edit_preserve, editf_*, clear_filter_*

Architecture: Uses new layered architecture
- WatchService 由 CallbackRegistry 构造期注入（self.watch_service）
"""

from dataclasses import dataclass

from pyrogram import Client
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from .base import CallbackContext, CallbackHandler
from bot.utils.status import user_states
from bot.handlers.watch_task_utils import resolve_watch_entry


@dataclass(frozen=True)
class EditFilterSelection:
    filter_type: str
    color: str | None
    token: str


def _parse_edit_filter_selection(data: str) -> EditFilterSelection:
    parts = data.split("_")
    filter_type = parts[1]
    if filter_type == "extract":
        return EditFilterSelection(filter_type=filter_type, color=None, token=parts[2])
    return EditFilterSelection(filter_type=filter_type, color=parts[2], token=parts[3])


def _edit_filter_action(selection: EditFilterSelection) -> str:
    if selection.color:
        return f"edit_filter_{selection.filter_type}_{selection.color}"
    return f"edit_filter_{selection.filter_type}"


def _build_edit_filter_keyboard(selection: EditFilterSelection, task_ref: str) -> InlineKeyboardMarkup:
    if selection.filter_type == "extract":
        clear_callback = f"clear_filter_extract_{task_ref}"
    else:
        clear_callback = f"clear_filter_{selection.filter_type}_{selection.color}_{task_ref}"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🗑 清空", callback_data=clear_callback)],
        [InlineKeyboardButton("❌ 取消", callback_data=f"watch_view_{task_ref}")]
    ])


def _filter_prompt_details(selection: EditFilterSelection) -> tuple[str, str]:
    if selection.filter_type == "kw":
        return (
            "关键词白名单" if selection.color == "white" else "关键词黑名单",
            "重要,紧急,通知" if selection.color == "white" else "广告,推广,垃圾",
        )
    if selection.filter_type == "re":
        return (
            "正则白名单" if selection.color == "white" else "正则黑名单",
            "https?://[^\\s]+,\\d{6,}" if selection.color == "white" else "广告|推广",
        )
    return "提取规则", "https?://[^\\s]+,\\d{6,}"


def _render_edit_filter_prompt(selection: EditFilterSelection) -> str:
    filter_name, example = _filter_prompt_details(selection)
    return (
        f"**✏️ 修改{filter_name}**\n\n"
        "请发送新的规则，用逗号分隔\n\n"
        f"示例：`{example}`\n\n"
        "💡 发送新规则将覆盖原有规则\n"
        "💡 点击\"清空\"可删除所有规则"
    )


class EditCallbackHandler(CallbackHandler):
    """编辑回调处理器"""

    def can_handle(self, data: str) -> bool:
        """判断是否为编辑回调"""
        return (data.startswith("edit_filter_") or
                data.startswith("edit_preserve_") or
                data.startswith("editf_") or
                data.startswith("clear_filter_"))

    def handle(self, client: Client, callback_query: CallbackQuery) -> None:
        """处理编辑回调"""
        context = self.get_common_context(client, callback_query)
        self.dispatch_context(
            context,
            prefixes=(
                ("edit_filter_", self._handle_edit_filter_menu),
                ("edit_preserve_", self._handle_edit_preserve),
                ("editf_", self._handle_editf),
                ("clear_filter_", self._handle_clear_filter),
            ),
        )

    def _handle_edit_filter_menu(self, context: CallbackContext) -> None:
        """处理编辑过滤规则菜单"""
        token = context.data.split("_")[2]

        watch_service = self.watch_service
        watch_config = watch_service.get_all_configs_dict()
        if context.user_id not in watch_config or not watch_config[context.user_id]:
            self.answer_and_log(context.callback_query, "❌ 监控任务不存在", show_alert=True)
            return

        watch_key, _watch_data, watch_id = resolve_watch_entry(watch_config[context.user_id], token)
        if not watch_key:
            self.answer_and_log(context.callback_query, "❌ 任务编号无效", show_alert=True)
            return

        task_ref = watch_id or token

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🟢 修改关键词白名单", callback_data=f"editf_kw_white_{task_ref}")],
            [InlineKeyboardButton("🔴 修改关键词黑名单", callback_data=f"editf_kw_black_{task_ref}")],
            [InlineKeyboardButton("🟢 修改正则白名单", callback_data=f"editf_re_white_{task_ref}")],
            [InlineKeyboardButton("🔴 修改正则黑名单", callback_data=f"editf_re_black_{task_ref}")],
            [InlineKeyboardButton("🎯 修改提取规则", callback_data=f"editf_extract_{task_ref}")],
            [InlineKeyboardButton("🔙 返回", callback_data=f"watch_view_{task_ref}")]
        ])

        text = "**✏️ 编辑过滤规则**\n\n"
        text += "选择要修改的规则：\n\n"
        text += "🟢 **关键词白名单** - 包含关键词才转发\n"
        text += "🔴 **关键词黑名单** - 包含关键词不转发\n"
        text += "🟢 **正则白名单** - 匹配正则才转发\n"
        text += "🔴 **正则黑名单** - 匹配正则不转发\n"
        text += "🎯 **提取规则** - 提取模式的正则表达式"

        self.bot.edit_message_text(context.chat_id, context.message_id, text, reply_markup=keyboard)
        self.answer_and_log(context.callback_query)

    def _handle_edit_preserve(self, context: CallbackContext) -> None:
        """处理切换保留来源"""
        from bot.handlers.callbacks import callback_handler

        token = context.data.split("_")[2]
        watch_service = self.watch_service
        watch_config = watch_service.get_all_configs_dict()

        if context.user_id not in watch_config or not watch_config[context.user_id]:
            self.answer_and_log(context.callback_query, "❌ 监控任务不存在", show_alert=True)
            return

        watch_key, _watch_data, watch_id = resolve_watch_entry(watch_config[context.user_id], token)
        if not watch_key:
            self.answer_and_log(context.callback_query, "❌ 任务编号无效", show_alert=True)
            return

        task_ref = watch_id or token

        if isinstance(watch_config[context.user_id][watch_key], dict):
            current_preserve = watch_config[context.user_id][watch_key].get("preserve_forward_source", False)
            watch_config[context.user_id][watch_key]["preserve_forward_source"] = not current_preserve
        else:
            # 旧格式兼容 - 转换为新格式
            old_dest = watch_config[context.user_id][watch_key]
            source_id = watch_key
            watch_config[context.user_id][watch_key] = {
                "source": source_id,
                "dest": old_dest,
                "whitelist": [],
                "blacklist": [],
                "preserve_forward_source": True
            }

        watch_service.save_config_dict(watch_config)

        # 刷新视图
        context.callback_query.data = f"watch_view_{task_ref}"
        callback_handler(context.client, context.callback_query)

    def _handle_editf(self, context: CallbackContext) -> None:
        """处理编辑过滤规则"""
        selection = _parse_edit_filter_selection(context.data)
        watch_service = self.watch_service
        watch_config = watch_service.get_all_configs_dict()
        if context.user_id not in watch_config or not watch_config[context.user_id]:
            self.answer_and_log(context.callback_query, "❌ 监控任务不存在", show_alert=True)
            return

        watch_key, _watch_data, watch_id = resolve_watch_entry(watch_config[context.user_id], selection.token)
        if not watch_key:
            self.answer_and_log(context.callback_query, "❌ 任务编号无效", show_alert=True)
            return

        task_ref = watch_id or selection.token

        user_states[context.user_id] = {
            "action": _edit_filter_action(selection),
            "task_ref": task_ref,
            "watch_key": watch_key,
        }

        keyboard = _build_edit_filter_keyboard(selection, task_ref)
        self.bot.edit_message_text(
            context.chat_id,
            context.message_id,
            _render_edit_filter_prompt(selection),
            reply_markup=keyboard,
        )
        self.answer_and_log(context.callback_query, "请输入新规则")

    def _handle_clear_filter(self, context: CallbackContext) -> None:
        """处理清空过滤规则"""
        from bot.handlers.callbacks import callback_handler

        parts = context.data.split("_")

        # 处理不同的回调格式
        if parts[2] == "extract":
            # 格式: clear_filter_extract_{task_id}
            filter_type = "extract"
            color = None
            token = parts[3]
        else:
            # 格式: clear_filter_kw_white_{task_id} 或 clear_filter_re_black_{task_id}
            filter_type = parts[2]
            color = parts[3]
            token = parts[4]

        watch_service = self.watch_service
        watch_config = watch_service.get_all_configs_dict()

        if context.user_id not in watch_config or not watch_config[context.user_id]:
            self.answer_and_log(context.callback_query, "❌ 监控任务不存在", show_alert=True)
            return

        watch_key, _watch_data, watch_id = resolve_watch_entry(watch_config[context.user_id], token)
        if not watch_key:
            self.answer_and_log(context.callback_query, "❌ 任务编号无效", show_alert=True)
            return

        task_ref = watch_id or token

        if isinstance(watch_config[context.user_id][watch_key], dict):
            if filter_type == "kw":
                key = "whitelist" if color == "white" else "blacklist"
            elif filter_type == "re":
                key = "whitelist_regex" if color == "white" else "blacklist_regex"
            else:  # extract
                key = "extract_patterns"

            watch_config[context.user_id][watch_key][key] = []
            watch_service.save_config_dict(watch_config)

            self.answer_and_log(context.callback_query, "✅ 已清空")

        # 刷新视图
        context.callback_query.data = f"watch_view_{task_ref}"
        callback_handler(context.client, context.callback_query)
