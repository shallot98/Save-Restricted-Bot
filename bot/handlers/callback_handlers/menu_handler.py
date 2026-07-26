"""
Menu callback handler - 菜单回调处理器

处理所有菜单相关的回调：menu_main, menu_help, menu_watch

Architecture: Uses new layered architecture
- WatchService 由 CallbackRegistry 构造期注入（self.watch_service）
"""

from pyrogram import Client
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from .base import CallbackContext, CallbackHandler
from bot.services.history_copy_task_manager import get_history_copy_task_manager
from bot.services.pt_pay_manager import get_pt_pay_monitor_manager
from bot.services.signin_manager import get_scheduled_signin_manager


_HELP_TEXT = """**📖 使用帮助**

**📥 转发消息**
直接发送 Telegram 消息链接即可转发内容

**🤖 脚本联动**
• 可监控指定群聊/频道的新消息
• 当一条消息中按行出现至少两个 `PT-xx` 时，会按顺序提取
• 自动向目标对象发送 `/pay PT-xx`
• 当 Bot 回复包含“成功”关键字时立即停止后续尝试
• 支持在菜单中启停和删除脚本

**🕒 定时签到**
• 可按固定间隔向指定群聊/频道发送自定义文本
• 支持修改消息内容和发送间隔
• 适合周期发送签到提醒或固定通知

**📚 历史复制**
• 可把来源群聊/频道的历史消息复制到目标群聊/频道
• 支持全部历史或最近 N 条
• 内置断点续传、发送节流和自动冷却

**🔗 链接格式**

公开频道/群组：
`https://t.me/username/123`

私有频道/群组（需要先加入）：
`https://t.me/c/123456789/123`

批量下载（范围）：
`https://t.me/username/100-120`

机器人消息：
`https://t.me/b/botusername/123`

**💡 提示**
• 私有频道需要配置 String Session
• 转发功能保持不变，直接发送 Telegram 链接即可
• 所有操作都可通过按钮完成，无需记忆复杂命令
• 机器人重启后会自动加载所有配置
"""


def _help_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🤖 脚本管理", callback_data="menu_script")],
        [InlineKeyboardButton("🏠 返回主菜单", callback_data="menu_main")],
    ])


class MenuCallbackHandler(CallbackHandler):
    """菜单回调处理器"""

    def can_handle(self, data: str) -> bool:
        """判断是否为菜单回调"""
        return data.startswith("menu_")

    def handle(self, client: Client, callback_query: CallbackQuery) -> None:
        """处理菜单回调"""
        context = self.get_common_context(client, callback_query)
        self.dispatch_context(
            context,
            {
                "menu_main": self._handle_main_menu,
                "menu_help": self._handle_help_menu,
                "menu_watch": self._handle_watch_menu,
                "menu_script": self._handle_script_menu,
                "menu_script_pt": self._handle_pt_script_menu,
                "menu_script_signin": self._handle_signin_script_menu,
                "menu_script_history_copy": self._handle_history_copy_menu,
            },
        )

    def _handle_main_menu(self, context: CallbackContext) -> None:
        """处理主菜单"""
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🤖 脚本管理", callback_data="menu_script")],
            [InlineKeyboardButton("❓ 帮助说明", callback_data="menu_help")],
            [InlineKeyboardButton("🌐 源代码", url="https://github.com/bipinkrish/Save-Restricted-Bot")]
        ])

        welcome_text = f"👋 你好 **{context.callback_query.from_user.mention}**！\n\n"
        welcome_text += "我是受限内容保存机器人，可以帮你：\n\n"
        welcome_text += "📥 **转发消息** - 直接发送 Telegram 链接\n"
        welcome_text += "🤖 **脚本模式** - 管理 PT 联动、定时签到和历史复制任务\n\n"
        welcome_text += "点击下方按钮开始使用 👇"

        self.bot.edit_message_text(context.chat_id, context.message_id, welcome_text, reply_markup=keyboard)
        self.answer_and_log(context.callback_query)

    def _handle_help_menu(self, context: CallbackContext) -> None:
        """处理帮助菜单"""
        self.bot.edit_message_text(
            context.chat_id,
            context.message_id,
            _HELP_TEXT,
            reply_markup=_help_menu_keyboard(),
        )
        self.answer_and_log(context.callback_query)

    def _handle_watch_menu(self, context: CallbackContext) -> None:
        """处理监控管理菜单"""
        if self.acc is None:
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 返回主菜单", callback_data="menu_main")]])
            self.bot.edit_message_text(context.chat_id, context.message_id, "**❌ 需要配置 String Session 才能使用监控功能**", reply_markup=keyboard)
            self.answer_and_log(context.callback_query, "❌ 需要配置 String Session", show_alert=True)
            return

        watch_config = self.watch_service.get_all_configs_dict()
        watch_count = len(watch_config.get(context.user_id, {}))

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ 添加监控", callback_data="watch_add_start")],
            [InlineKeyboardButton(f"📋 查看列表 ({watch_count})", callback_data="watch_list")],
            [InlineKeyboardButton("🗑 删除监控", callback_data="watch_remove_start")],
            [InlineKeyboardButton("🤖 脚本管理", callback_data="menu_script")],
            [InlineKeyboardButton("🏠 返回主菜单", callback_data="menu_main")]
        ])

        text = "**📋 监控管理**\n\n"
        text += "选择操作：\n\n"
        text += "➕ **添加监控** - 设置新的自动转发任务\n"
        text += "📋 **查看列表** - 查看所有监控任务\n"
        text += "🗑 **删除监控** - 移除现有监控任务\n\n"
        text += f"当前监控任务数：**{watch_count}** 个"

        self.bot.edit_message_text(context.chat_id, context.message_id, text, reply_markup=keyboard)
        self.answer_and_log(context.callback_query)

    def _handle_script_menu(self, context: CallbackContext) -> None:
        if self.acc is None:
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 返回主菜单", callback_data="menu_main")]])
            self.bot.edit_message_text(context.chat_id, context.message_id, "**❌ 需要配置 String Session 才能使用脚本管理**", reply_markup=keyboard)
            self.answer_and_log(context.callback_query, "❌ 需要配置 String Session", show_alert=True)
            return

        pt_manager = get_pt_pay_monitor_manager()
        signin_manager = get_scheduled_signin_manager()
        history_copy_manager = get_history_copy_task_manager()
        pt_tasks = pt_manager.list_user_tasks(context.user_id)
        signin_tasks = signin_manager.list_user_tasks(context.user_id)
        pt_total = pt_manager.count_user_tasks(context.user_id)
        pt_enabled = pt_manager.count_enabled_user_tasks(context.user_id)
        signin_total = signin_manager.count_user_tasks(context.user_id)
        signin_enabled = signin_manager.count_enabled_user_tasks(context.user_id)
        history_total = history_copy_manager.count_user_tasks(context.user_id)
        history_running = history_copy_manager.count_running_user_tasks(context.user_id)

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(_build_pt_overview_label(pt_total, pt_enabled), callback_data="menu_script_pt")],
            [InlineKeyboardButton(_build_signin_overview_label(signin_total, signin_enabled), callback_data="menu_script_signin")],
            [InlineKeyboardButton(_build_history_copy_overview_label(history_total, history_running), callback_data="menu_script_history_copy")],
            [InlineKeyboardButton("🏠 返回主菜单", callback_data="menu_main")],
        ])

        text = "**🤖 脚本管理**\n\n"
        text += "先选择脚本类型，再进入对应页面添加或管理脚本。\n\n"
        text += f"PT 脚本：**{pt_total}** 个，其中运行中 **{pt_enabled}** 个\n"
        text += f"签到脚本：**{signin_total}** 个，其中运行中 **{signin_enabled}** 个\n"
        text += f"历史复制：**{history_total}** 个，其中运行中 **{history_running}** 个\n\n"
        if pt_tasks or signin_tasks or history_total:
            text += "点进任一脚本类型后，可以继续添加脚本，或进入管理页查看、启停和删除已有脚本。"
        else:
            text += "当前还没有脚本，先选择类型后再添加。"
        self.bot.edit_message_text(context.chat_id, context.message_id, text, reply_markup=keyboard)
        self.answer_and_log(context.callback_query)

    def _handle_pt_script_menu(self, context: CallbackContext) -> None:
        manager = get_pt_pay_monitor_manager()
        total = manager.count_user_tasks(context.user_id)
        enabled = manager.count_enabled_user_tasks(context.user_id)

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ 添加 PT 脚本", callback_data="script_add_start")],
            [InlineKeyboardButton(f"📋 管理 PT 脚本 ({total})", callback_data="script_list")],
            [InlineKeyboardButton("🔙 返回脚本管理", callback_data="menu_script")],
        ])

        text = "**🤖 PT 联动脚本**\n\n"
        text += "这里管理 PT 联动脚本。\n\n"
        text += "• 添加脚本：新建 PT 自动联动\n"
        text += "• 管理脚本：查看详情、启停、设置延时、删除\n\n"
        text += f"当前共 **{total}** 个脚本，其中运行中 **{enabled}** 个"
        self.bot.edit_message_text(context.chat_id, context.message_id, text, reply_markup=keyboard)
        self.answer_and_log(context.callback_query)

    def _handle_history_copy_menu(self, context: CallbackContext) -> None:
        manager = get_history_copy_task_manager()
        total = manager.count_user_tasks(context.user_id)
        running = manager.count_running_user_tasks(context.user_id)

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ 新建历史复制", callback_data="history_copy_add_start")],
            [InlineKeyboardButton(f"📋 历史复制任务 ({total})", callback_data="history_copy_list")],
            [InlineKeyboardButton("🔙 返回脚本管理", callback_data="menu_script")],
        ])

        text = "**📚 历史复制**\n\n"
        text += "这里管理一次性的历史复制任务。\n\n"
        text += "• 新建历史复制：选择来源、目标和复制范围后后台执行\n"
        text += "• 历史复制任务：查看运行状态、结果和错误信息\n"
        text += "• 同一时间只允许一个历史复制任务运行，以降低账号风险\n\n"
        text += f"当前共 **{total}** 个任务，其中运行中 **{running}** 个"
        self.bot.edit_message_text(context.chat_id, context.message_id, text, reply_markup=keyboard)
        self.answer_and_log(context.callback_query)

    def _handle_signin_script_menu(self, context: CallbackContext) -> None:
        manager = get_scheduled_signin_manager()
        total = manager.count_user_tasks(context.user_id)
        enabled = manager.count_enabled_user_tasks(context.user_id)

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ 添加签到脚本", callback_data="signin_add_start")],
            [InlineKeyboardButton(f"📋 管理签到脚本 ({total})", callback_data="signin_list")],
            [InlineKeyboardButton("🔙 返回脚本管理", callback_data="menu_script")],
        ])

        text = "**🕒 定时签到脚本**\n\n"
        text += "这里管理定时签到脚本。\n\n"
        text += "• 添加脚本：新建定时发送任务\n"
        text += "• 管理脚本：查看详情、启停、修改消息和间隔、删除\n\n"
        text += f"当前共 **{total}** 个脚本，其中运行中 **{enabled}** 个"
        self.bot.edit_message_text(context.chat_id, context.message_id, text, reply_markup=keyboard)
        self.answer_and_log(context.callback_query)


def _build_pt_overview_label(total: int, enabled: int) -> str:
    return f"🤖 PT 联动脚本 ({enabled}/{total} 运行中)"


def _build_signin_overview_label(total: int, enabled: int) -> str:
    return f"🕒 定时签到脚本 ({enabled}/{total} 运行中)"


def _build_history_copy_overview_label(total: int, running: int) -> str:
    return f"📚 历史复制 ({running}/{total} 运行中)"
