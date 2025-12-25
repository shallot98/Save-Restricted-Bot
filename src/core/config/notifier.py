"""
配置变更通知器
==============

提供配置变更的订阅和通知机制。
"""

import logging
import threading
import uuid
from typing import Callable, Dict, Any, Optional

logger = logging.getLogger(__name__)

# 配置变更回调类型
ConfigChangeCallback = Callable[[str, Any, Any], None]
"""配置变更回调函数类型: (config_type, old_value, new_value) -> None"""


class ConfigChangeNotifier:
    """
    配置变更通知器

    管理配置变更的订阅者，并在配置变更时通知所有订阅者。

    特性:
    - 线程安全
    - 支持多个订阅者
    - 单个订阅者失败不影响其他订阅者
    - 返回订阅ID用于取消订阅

    Example:
        >>> notifier = ConfigChangeNotifier()
        >>> def on_change(config_type, old, new):
        ...     print(f"配置 {config_type} 已变更")
        >>> sub_id = notifier.subscribe(on_change)
        >>> notifier.notify("main", {}, {"TOKEN": "new"})
        >>> notifier.unsubscribe(sub_id)
    """

    def __init__(self):
        """初始化配置变更通知器"""
        self._subscribers: Dict[str, ConfigChangeCallback] = {}
        self._lock = threading.RLock()

    def subscribe(self, callback: ConfigChangeCallback) -> str:
        """
        订阅配置变更通知

        Args:
            callback: 回调函数，签名为 (config_type, old_value, new_value) -> None

        Returns:
            str: 订阅ID，用于取消订阅

        Example:
            >>> def on_config_change(config_type, old, new):
            ...     print(f"配置 {config_type} 从 {old} 变更为 {new}")
            >>> sub_id = notifier.subscribe(on_config_change)
        """
        with self._lock:
            subscription_id = str(uuid.uuid4())
            self._subscribers[subscription_id] = callback
            logger.debug(f"新增订阅者: {subscription_id}")
            return subscription_id

    def unsubscribe(self, subscription_id: str) -> bool:
        """
        取消订阅配置变更通知

        Args:
            subscription_id: 订阅ID（由subscribe方法返回）

        Returns:
            bool: 是否成功取消订阅

        Example:
            >>> notifier.unsubscribe(sub_id)
            True
        """
        with self._lock:
            if subscription_id in self._subscribers:
                del self._subscribers[subscription_id]
                logger.debug(f"移除订阅者: {subscription_id}")
                return True
            return False

    def notify(self, config_type: str, old_value: Any, new_value: Any) -> None:
        """
        通知所有订阅者配置已变更

        Args:
            config_type: 配置类型（如 "main", "webdav", "watch"）
            old_value: 旧配置值
            new_value: 新配置值

        Note:
            单个订阅者的异常不会影响其他订阅者的通知

        Example:
            >>> notifier.notify("main", {"TOKEN": "old"}, {"TOKEN": "new"})
        """
        with self._lock:
            subscribers = list(self._subscribers.items())

        logger.info(f"通知 {len(subscribers)} 个订阅者: 配置 '{config_type}' 已变更")

        for sub_id, callback in subscribers:
            try:
                callback(config_type, old_value, new_value)
            except Exception as e:
                logger.error(f"订阅者 {sub_id} 处理配置变更时出错: {e}")

    def clear(self) -> None:
        """清空所有订阅者"""
        with self._lock:
            count = len(self._subscribers)
            self._subscribers.clear()
            logger.debug(f"已清空 {count} 个订阅者")

    def subscriber_count(self) -> int:
        """
        获取订阅者数量

        Returns:
            int: 当前订阅者数量
        """
        with self._lock:
            return len(self._subscribers)


__all__ = ['ConfigChangeNotifier', 'ConfigChangeCallback']
