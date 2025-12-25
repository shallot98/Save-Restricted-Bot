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
        message: Optional[str] = None
    ):
        """
        初始化配置验证错误

        Args:
            field_name: 字段名称
            current_value: 当前值
            expected_format: 期望的格式或类型描述
            message: 自定义错误消息（可选）
        """
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


__all__ = [
    'ConfigValidationError',
    'ConfigLoadError',
    'ConfigSaveError',
]
