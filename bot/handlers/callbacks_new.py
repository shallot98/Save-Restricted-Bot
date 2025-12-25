"""
Callback query handlers - 重构版

使用策略模式 + 处理器注册表，将原来的 927 行超长函数重构为模块化架构
"""

import pyrogram
from pyrogram import Client
from pyrogram.types import CallbackQuery

from .callback_registry import get_callback_registry


def callback_handler(client: pyrogram.client.Client, callback_query: CallbackQuery):
    """
    处理所有回调查询 - 重构版

    原函数：927 行超长函数，包含 30+ 个 if-elif 分支
    重构后：使用注册表模式，仅 20 行，职责单一

    架构：
    - CallbackRegistry: 处理器注册表和分发器
    - MenuCallbackHandler: 菜单回调处理（menu_*）
    - WatchCallbackHandler: 监控回调处理（watch_*）
    - FilterCallbackHandler: 过滤回调处理（filter_*）
    - EditCallbackHandler: 编辑回调处理（edit_*）
    - ModeCallbackHandler: 模式回调处理（mode_*, fwdmode_*）

    优势：
    - ✅ 单一职责原则（SRP）- 每个处理器负责一类回调
    - ✅ 开闭原则（OCP）- 易于扩展新处理器
    - ✅ 可测试性提升 - 每个处理器可独立测试
    - ✅ 代码可读性 - 从 927 行降至 50-150 行/类
    """
    registry = get_callback_registry()
    registry.dispatch(client, callback_query)
