"""
配置异常定义
============

定义配置管理相关的异常类。
"""

from typing import Any, Optional


class ConfigValidationError(ValueError):
    """
    配置验证错误

    当配置值不符合验证规则时抛出此异常。

    Attributes:
        field_name: 字段名称
        current_value: 当前值
        expected_format: 期望的格式或类型
        message: 错误消息
    """

    def __init__(
        self,
        field_name: str,
        current_value: Any,
        expected_format: str,
        *legacy_message: Optional[str],
        message: Optional[str] = None,
    ):
        """
        初始化配置验证错误

        Args:
            field_name: 字段名称
            current_value: 当前值
            expected_format: 期望的格式或类型描述
            message: 自定义错误消息（可选）
        """
        if len(legacy_message) > 1:
            raise TypeError("ConfigValidationError accepts at most one legacy message argument")
        if legacy_message and message is not None:
            raise TypeError("ConfigValidationError received duplicate message values")
        if legacy_message:
            message = legacy_message[0]

        self.field_name = field_name
        self.current_value = current_value
        self.expected_format = expected_format

        if message:
            self.message = message
        else:
            self.message = (
                f"配置字段 '{field_name}' 验证失败: "
                f"当前值 '{current_value}' 不符合期望格式 '{expected_format}'"
            )

        super().__init__(self.message)

    def __str__(self) -> str:
        """格式化错误信息"""
        return self.message

    def __repr__(self) -> str:
        """返回详细的错误表示"""
        return (
            f"ConfigValidationError("
            f"field_name='{self.field_name}', "
            f"current_value='{self.current_value}', "
            f"expected_format='{self.expected_format}')"
        )


class ConfigLoadError(Exception):
    """
    配置加载错误

    当配置文件加载失败时抛出此异常。
    """

    def __init__(self, config_file: str, reason: str):
        """
        初始化配置加载错误

        Args:
            config_file: 配置文件路径
            reason: 失败原因
        """
        self.config_file = config_file
        self.reason = reason
        self.message = f"配置文件 '{config_file}' 加载失败: {reason}"
        super().__init__(self.message)


class ConfigSaveError(Exception):
    """
    配置保存错误

    当配置文件保存失败时抛出此异常。
    """

    def __init__(self, config_file: str, reason: str):
        """
        初始化配置保存错误

        Args:
            config_file: 配置文件路径
            reason: 失败原因
        """
        self.config_file = config_file
        self.reason = reason
        self.message = f"配置文件 '{config_file}' 保存失败: {reason}"
        super().__init__(self.message)


class HotReloadUnavailableError(RuntimeError):
    """
    配置热重载不可用

    热重载依赖可选依赖 watchdog（见 requirements.dev.txt）。运行时镜像只安装
    requirements.runtime.txt，因此默认不含 watchdog；显式启用热重载时如果缺少它，
    抛出本异常并给出安装提示，而不是静默降级成「启用了但不生效」。
    """

    INSTALL_HINT = "pip install 'watchdog>=3.0.0'"

    def __init__(self, reason: Optional[BaseException] = None):
        """
        Args:
            reason: 触发本异常的原始 ImportError（可选）
        """
        self.reason = reason
        self.message = (
            "配置热重载需要可选依赖 watchdog，当前环境未安装。"
            f"如需启用请先安装：{self.INSTALL_HINT}"
        )
        if reason is not None:
            self.message += f"（原始导入错误：{reason}）"
        super().__init__(self.message)


__all__ = [
    'ConfigValidationError',
    'ConfigLoadError',
    'ConfigSaveError',
    'HotReloadUnavailableError',
]
