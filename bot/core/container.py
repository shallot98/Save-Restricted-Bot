"""
依赖注入容器
管理应用程序的依赖关系，替换全局变量
"""
from typing import Optional, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class BotContext:
    """Bot上下文，包含所有核心依赖

    使用依赖注入模式，替换全局变量，提升可测试性
    """
    bot: Any  # Pyrogram Bot客户端
    acc: Optional[Any] = None  # Pyrogram User客户端（可选）
    message_queue: Optional[Any] = None  # 消息队列（可选）
    config: Optional[dict] = None  # 配置字典

    def __post_init__(self):
        """初始化后验证"""
        if self.bot is None:
            raise ValueError("bot客户端不能为None")

        logger.info("✅ BotContext已创建")
        logger.info(f"   - Bot: {self.bot.me.username if hasattr(self.bot, 'me') else 'Unknown'}")
        logger.info(f"   - User客户端: {'已配置' if self.acc else '未配置'}")
        logger.info(f"   - 消息队列: {'已启用' if self.message_queue else '未启用'}")

    def has_user_client(self) -> bool:
        """检查是否有User客户端"""
        return self.acc is not None

    def has_message_queue(self) -> bool:
        """检查是否有消息队列"""
        return self.message_queue is not None


class DependencyContainer:
    """依赖注入容器

    单例模式，管理应用程序的所有依赖
    """

    _instance: Optional['DependencyContainer'] = None
    _context: Optional[BotContext] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def register_context(self, context: BotContext):
        """注册Bot上下文

        Args:
            context: Bot上下文对象
        """
        self._context = context
        logger.info("📦 依赖容器已注册上下文")

    def get_context(self) -> BotContext:
        """获取Bot上下文

        Returns:
            Bot上下文对象

        Raises:
            RuntimeError: 如果上下文未注册
        """
        if self._context is None:
            raise RuntimeError("BotContext未注册，请先调用register_context()")
        return self._context

    def get_bot(self):
        """获取Bot客户端"""
        return self.get_context().bot

    def get_acc(self):
        """获取User客户端"""
        return self.get_context().acc

    def get_message_queue(self):
        """获取消息队列"""
        return self.get_context().message_queue

    def get_config(self) -> dict:
        """获取配置"""
        return self.get_context().config or {}

    def clear(self):
        """清除容器（主要用于测试）"""
        self._context = None
        logger.info("🧹 依赖容器已清除")


# 全局容器实例
container = DependencyContainer()


# 便捷函数（向后兼容）
def get_bot_context() -> BotContext:
    """获取Bot上下文（便捷函数）"""
    return container.get_context()


def get_bot():
    """获取Bot客户端（便捷函数）"""
    return container.get_bot()


def get_acc():
    """获取User客户端（便捷函数）"""
    return container.get_acc()


def get_message_queue():
    """获取消息队列（便捷函数）"""
    return container.get_message_queue()
