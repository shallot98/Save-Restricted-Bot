"""
Menu callback handler - 菜单回调处理器

处理所有菜单相关的回调：menu_main, menu_help, menu_watch

Architecture: Uses new layered architecture
- src/core/container for service access
"""

from pyrogram import Client
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from .base import CallbackHandler

# New architecture imports
from src.core.container import get_watch_service


class MenuCallbackHandler(CallbackHandler):
    """菜单回调处理器"""

    def can_handle(self, data: str) -> bool:
        """判断是否为菜单回调"""
        return data.startswith("menu_")

    def handle(self, client: Client, callback_query: CallbackQuery) -> None:
        """处理菜单回调"""
        params = self.get_common_params(callback_query)
        data = params['data']
        chat_id = params['chat_id']
        message_id = params['message_id']
        user_id = params['user_id']

        if data == "menu_main":
            self._handle_main_menu(callback_query, chat_id, message_id)
        elif data == "menu_help":
            self._handle_help_menu(callback_query, chat_id, message_id)
        elif data == "menu_watch":
            self._handle_watch_menu(callback_query, chat_id, message_id, user_id)

    def _handle_main_menu(self, callback_query: CallbackQuery, chat_id: int, message_id: int) -> None:
        """处理主菜单"""
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 监控管理", callback_data="menu_watch")],
            [InlineKeyboardButton("❓ 帮助说明", callback_data="menu_help")],
            [InlineKeyboardButton("🌐 源代码", url="https://github.com/bipinkrish/Save-Restricted-Bot")]
        ])

        welcome_text = f"👋 你好 **{callback_query.from_user.mention}**！\n\n"
        welcome_text += "我是受限内容保存机器人，可以帮你：\n\n"
        welcome_text += "📥 **转发消息** - 直接发送 Telegram 链接\n"
        welcome_text += "👁 **监控频道/群组** - 自动转发新消息\n"
        welcome_text += "🔍 **智能过滤** - 关键词、正则表达式过滤\n"
        welcome_text += "🎯 **提取模式** - 提取特定内容转发\n\n"
        welcome_text += "点击下方按钮开始使用 👇"

        self.bot.edit_message_text(chat_id, message_id, welcome_text, reply_markup=keyboard)
        self.answer_and_log(callback_query)

    def _handle_help_menu(self, callback_query: CallbackQuery, chat_id: int, message_id: int) -> None:
        """处理帮助菜单"""
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 监控管理", callback_data="menu_watch")],
            [InlineKeyboardButton("🏠 返回主菜单", callback_data="menu_main")]
        ])

        help_text = """**📖 使用帮助**

**📥 转发消息**
直接发送 Telegram 消息链接即可转发内容

**📋 监控功能**
• 点击"监控管理"按钮设置自动转发或记录
• 支持监控频道、群组和收藏夹
• 输入 `me` 可监控自己的收藏夹
• 支持关键词过滤（白名单/黑名单）
• 支持正则表达式过滤
• 支持提取模式（正则提取特定内容）
• 可选择是否保留转发来源
• 📝 支持记录模式（保存到网页笔记）
• 可随时编辑监控设置

**📝 记录模式**
• 将监控内容保存到网页而非转发
• 记录文字、图片和视频封面
• 包含时间戳信息
• 过滤规则和提取模式仍然生效
• 通过 Web 界面查看记录（端口 5000）
• 默认登录账号：admin/admin
• 搜索功能支持高亮显示

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
• 可以使用 `me` 监控收藏夹或作为目标
• 关键词过滤不区分大小写
• 正则表达式支持完整的 Python re 语法
• 提取模式会将匹配的内容单独发送
• 所有操作都可通过按钮完成，无需记忆复杂命令
• 机器人重启后会自动加载所有配置
"""
        self.bot.edit_message_text(chat_id, message_id, help_text, reply_markup=keyboard)
        self.answer_and_log(callback_query)

    def _handle_watch_menu(self, callback_query: CallbackQuery, chat_id: int, message_id: int, user_id: str) -> None:
        """处理监控管理菜单"""
        if self.acc is None:
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 返回主菜单", callback_data="menu_main")]])
            self.bot.edit_message_text(chat_id, message_id, "**❌ 需要配置 String Session 才能使用监控功能**", reply_markup=keyboard)
            self.answer_and_log(callback_query, "❌ 需要配置 String Session", show_alert=True)
            return

        watch_service = get_watch_service()
        watch_config = watch_service.get_all_configs_dict()
        watch_count = len(watch_config.get(user_id, {}))

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ 添加监控", callback_data="watch_add_start")],
            [InlineKeyboardButton(f"📋 查看列表 ({watch_count})", callback_data="watch_list")],
            [InlineKeyboardButton("🗑 删除监控", callback_data="watch_remove_start")],
            [InlineKeyboardButton("🏠 返回主菜单", callback_data="menu_main")]
        ])

        text = "**📋 监控管理**\n\n"
        text += "选择操作：\n\n"
        text += "➕ **添加监控** - 设置新的自动转发任务\n"
        text += "📋 **查看列表** - 查看所有监控任务\n"
        text += "🗑 **删除监控** - 移除现有监控任务\n\n"
        text += f"当前监控任务数：**{watch_count}** 个"

        self.bot.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)
        self.answer_and_log(callback_query)
