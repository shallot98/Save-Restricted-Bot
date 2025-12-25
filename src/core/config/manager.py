"""
配置管理器接口定义
================

定义统一的配置管理器协议，提供：
- 配置读写接口
- 配置验证机制
- 配置热重载支持
- 配置变更通知
"""

from typing import Protocol, Any, Optional, Callable, Dict
from pathlib import Path


# 配置变更回调类型
ConfigChangeCallback = Callable[[str, Any, Any], None]
"""配置变更回调函数类型: (key, old_value, new_value) -> None"""


class ConfigManager(Protocol):
    """
    配置管理器协议

    定义统一的配置管理接口，所有配置管理器实现都应遵循此协议。
    """

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值

        Args:
            key: 配置键，支持点号分隔的嵌套键（如 "webdav.enabled"）
            default: 默认值，当配置不存在时返回

        Returns:
            配置值或默认值

        Example:
            >>> manager.get("TOKEN")
            "your_bot_token"
            >>> manager.get("webdav.enabled", False)
            False
        """
        ...

    def set(self, key: str, value: Any, persist: bool = True) -> None:
        """
        设置配置值

        Args:
            key: 配置键，支持点号分隔的嵌套键
            value: 配置值
            persist: 是否立即持久化到文件，默认True

        Raises:
            ValueError: 配置值验证失败

        Example:
            >>> manager.set("webdav.enabled", True)
            >>> manager.set("TOKEN", "new_token", persist=False)
        """
        ...

    def reload(self, config_type: Optional[str] = None) -> None:
        """
        重新加载配置

        从配置文件重新加载配置，覆盖内存中的配置。

        Args:
            config_type: 配置类型，可选值: "main", "watch", "webdav", "viewer"
                        如果为None，则重新加载所有配置

        Example:
            >>> manager.reload()  # 重新加载所有配置
            >>> manager.reload("webdav")  # 只重新加载WebDAV配置
        """
        ...

    def save(self, config_type: Optional[str] = None) -> None:
        """
        保存配置到文件

        将内存中的配置持久化到配置文件。

        Args:
            config_type: 配置类型，可选值: "main", "watch", "webdav", "viewer"
                        如果为None，则保存所有配置

        Example:
            >>> manager.save()  # 保存所有配置
            >>> manager.save("watch")  # 只保存监控配置
        """
        ...

    def validate(self, config_type: Optional[str] = None) -> Dict[str, list]:
        """
        验证配置

        验证配置的完整性和正确性。

        Args:
            config_type: 配置类型，如果为None则验证所有配置

        Returns:
            验证错误字典，格式: {config_type: [error_messages]}
            如果验证通过，返回空字典

        Example:
            >>> errors = manager.validate()
            >>> if errors:
            ...     print(f"配置验证失败: {errors}")
        """
        ...

    def subscribe(self, callback: ConfigChangeCallback, key_pattern: Optional[str] = None) -> str:
        """
        订阅配置变更通知

        注册回调函数，当配置发生变更时接收通知。

        Args:
            callback: 回调函数，签名为 (key, old_value, new_value) -> None
            key_pattern: 键模式，支持通配符（如 "webdav.*"）
                        如果为None，则订阅所有配置变更

        Returns:
            订阅ID，用于取消订阅

        Example:
            >>> def on_config_change(key, old, new):
            ...     print(f"配置 {key} 从 {old} 变更为 {new}")
            >>> sub_id = manager.subscribe(on_config_change, "webdav.*")
        """
        ...

    def unsubscribe(self, subscription_id: str) -> bool:
        """
        取消订阅配置变更通知

        Args:
            subscription_id: 订阅ID（由subscribe方法返回）

        Returns:
            是否成功取消订阅

        Example:
            >>> manager.unsubscribe(sub_id)
            True
        """
        ...

    @property
    def config_dir(self) -> Path:
        """
        获取配置目录路径

        Returns:
            配置目录的Path对象
        """
        ...


class ConfigValidator(Protocol):
    """
    配置验证器协议

    定义配置验证接口，用于实现自定义验证逻辑。
    """

    def validate(self, config: Any) -> list[str]:
        """
        验证配置

        Args:
            config: 配置对象

        Returns:
            错误消息列表，如果验证通过则返回空列表
        """
        ...


# 导出所有接口
__all__ = [
    'ConfigManager',
    'ConfigValidator',
    'ConfigChangeCallback',
]
