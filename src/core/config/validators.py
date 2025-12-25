"""
配置验证器
==========

提供配置验证功能，包括类型验证、必填字段验证、格式验证等。
"""

import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Pattern, Type, Callable
from pathlib import Path

from .exceptions import ConfigValidationError


class Validator(ABC):
    """
    验证器基类

    所有验证器都应继承此类并实现validate方法。
    """

    @abstractmethod
    def validate(self, field_name: str, value: Any) -> None:
        """
        验证字段值

        Args:
            field_name: 字段名称
            value: 字段值

        Raises:
            ConfigValidationError: 验证失败时抛出
        """
        pass


class TypeValidator(Validator):
    """
    类型验证器

    验证字段值是否符合指定的类型。

    Example:
        >>> validator = TypeValidator(str)
        >>> validator.validate("name", "John")  # 通过
        >>> validator.validate("name", 123)  # 抛出ConfigValidationError
    """

    def __init__(self, expected_type: Type, allow_none: bool = False):
        """
        初始化类型验证器

        Args:
            expected_type: 期望的类型
            allow_none: 是否允许None值
        """
        self.expected_type = expected_type
        self.allow_none = allow_none

    def validate(self, field_name: str, value: Any) -> None:
        """验证字段类型"""
        if value is None:
            if not self.allow_none:
                raise ConfigValidationError(
                    field_name=field_name,
                    current_value=value,
                    expected_format=f"类型 {self.expected_type.__name__}（不允许None）"
                )
            return

        if not isinstance(value, self.expected_type):
            raise ConfigValidationError(
                field_name=field_name,
                current_value=value,
                expected_format=f"类型 {self.expected_type.__name__}",
                message=f"字段 '{field_name}' 类型错误: 期望 {self.expected_type.__name__}，实际 {type(value).__name__}"
            )


class RequiredFieldValidator(Validator):
    """
    必填字段验证器

    验证必填字段是否存在且不为空。

    Example:
        >>> validator = RequiredFieldValidator()
        >>> validator.validate("token", "abc123")  # 通过
        >>> validator.validate("token", "")  # 抛出ConfigValidationError
        >>> validator.validate("token", None)  # 抛出ConfigValidationError
    """

    def __init__(self, allow_empty_string: bool = False):
        """
        初始化必填字段验证器

        Args:
            allow_empty_string: 是否允许空字符串
        """
        self.allow_empty_string = allow_empty_string

    def validate(self, field_name: str, value: Any) -> None:
        """验证必填字段"""
        if value is None:
            raise ConfigValidationError(
                field_name=field_name,
                current_value=value,
                expected_format="非空值",
                message=f"必填字段 '{field_name}' 不能为None"
            )

        if isinstance(value, str) and not self.allow_empty_string:
            if not value.strip():
                raise ConfigValidationError(
                    field_name=field_name,
                    current_value=value,
                    expected_format="非空字符串",
                    message=f"必填字段 '{field_name}' 不能为空字符串"
                )

        if isinstance(value, (list, dict, set, tuple)):
            if len(value) == 0:
                raise ConfigValidationError(
                    field_name=field_name,
                    current_value=value,
                    expected_format="非空集合",
                    message=f"必填字段 '{field_name}' 不能为空集合"
                )


class FormatValidator(Validator):
    """
    格式验证器

    使用正则表达式验证字段格式。

    Example:
        >>> # URL格式验证
        >>> validator = FormatValidator(r'^https?://.+', "URL格式（http://或https://开头）")
        >>> validator.validate("url", "https://example.com")  # 通过
        >>> validator.validate("url", "invalid")  # 抛出ConfigValidationError
    """

    def __init__(self, pattern: str, format_description: str, allow_empty: bool = False):
        """
        初始化格式验证器

        Args:
            pattern: 正则表达式模式
            format_description: 格式描述（用于错误消息）
            allow_empty: 是否允许空字符串
        """
        self.pattern: Pattern = re.compile(pattern)
        self.format_description = format_description
        self.allow_empty = allow_empty

    def validate(self, field_name: str, value: Any) -> None:
        """验证字段格式"""
        if not isinstance(value, str):
            raise ConfigValidationError(
                field_name=field_name,
                current_value=value,
                expected_format=f"字符串（{self.format_description}）",
                message=f"字段 '{field_name}' 必须是字符串类型"
            )

        if not value and self.allow_empty:
            return

        if not self.pattern.match(value):
            raise ConfigValidationError(
                field_name=field_name,
                current_value=value,
                expected_format=self.format_description,
                message=f"字段 '{field_name}' 格式错误: 期望 {self.format_description}"
            )


class PathValidator(Validator):
    """
    路径验证器

    验证路径是否存在、是否为目录/文件等。

    Example:
        >>> validator = PathValidator(must_exist=True, must_be_dir=True)
        >>> validator.validate("data_dir", "/path/to/data")
    """

    def __init__(
        self,
        must_exist: bool = False,
        must_be_dir: bool = False,
        must_be_file: bool = False,
        create_if_missing: bool = False
    ):
        """
        初始化路径验证器

        Args:
            must_exist: 路径必须存在
            must_be_dir: 必须是目录
            must_be_file: 必须是文件
            create_if_missing: 如果不存在则创建（仅对目录有效）
        """
        self.must_exist = must_exist
        self.must_be_dir = must_be_dir
        self.must_be_file = must_be_file
        self.create_if_missing = create_if_missing

        if must_be_dir and must_be_file:
            raise ValueError("must_be_dir和must_be_file不能同时为True")

    def validate(self, field_name: str, value: Any) -> None:
        """验证路径"""
        if not isinstance(value, (str, Path)):
            raise ConfigValidationError(
                field_name=field_name,
                current_value=value,
                expected_format="字符串或Path对象",
                message=f"字段 '{field_name}' 必须是字符串或Path对象"
            )

        path = Path(value) if isinstance(value, str) else value

        if self.must_exist:
            if not path.exists():
                if self.create_if_missing and self.must_be_dir:
                    path.mkdir(parents=True, exist_ok=True)
                else:
                    raise ConfigValidationError(
                        field_name=field_name,
                        current_value=str(path),
                        expected_format="存在的路径",
                        message=f"路径 '{path}' 不存在"
                    )

        if path.exists():
            if self.must_be_dir and not path.is_dir():
                raise ConfigValidationError(
                    field_name=field_name,
                    current_value=str(path),
                    expected_format="目录路径",
                    message=f"路径 '{path}' 不是目录"
                )

            if self.must_be_file and not path.is_file():
                raise ConfigValidationError(
                    field_name=field_name,
                    current_value=str(path),
                    expected_format="文件路径",
                    message=f"路径 '{path}' 不是文件"
                )


class RangeValidator(Validator):
    """
    范围验证器

    验证数值是否在指定范围内。

    Example:
        >>> validator = RangeValidator(min_value=0, max_value=100)
        >>> validator.validate("port", 80)  # 通过
        >>> validator.validate("port", 200)  # 抛出ConfigValidationError
    """

    def __init__(
        self,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
        inclusive: bool = True
    ):
        """
        初始化范围验证器

        Args:
            min_value: 最小值
            max_value: 最大值
            inclusive: 是否包含边界值
        """
        self.min_value = min_value
        self.max_value = max_value
        self.inclusive = inclusive

    def validate(self, field_name: str, value: Any) -> None:
        """验证数值范围"""
        if not isinstance(value, (int, float)):
            raise ConfigValidationError(
                field_name=field_name,
                current_value=value,
                expected_format="数值类型",
                message=f"字段 '{field_name}' 必须是数值类型"
            )

        if self.min_value is not None:
            if self.inclusive:
                if value < self.min_value:
                    raise ConfigValidationError(
                        field_name=field_name,
                        current_value=value,
                        expected_format=f">= {self.min_value}",
                        message=f"字段 '{field_name}' 值 {value} 小于最小值 {self.min_value}"
                    )
            else:
                if value <= self.min_value:
                    raise ConfigValidationError(
                        field_name=field_name,
                        current_value=value,
                        expected_format=f"> {self.min_value}",
                        message=f"字段 '{field_name}' 值 {value} 不大于最小值 {self.min_value}"
                    )

        if self.max_value is not None:
            if self.inclusive:
                if value > self.max_value:
                    raise ConfigValidationError(
                        field_name=field_name,
                        current_value=value,
                        expected_format=f"<= {self.max_value}",
                        message=f"字段 '{field_name}' 值 {value} 大于最大值 {self.max_value}"
                    )
            else:
                if value >= self.max_value:
                    raise ConfigValidationError(
                        field_name=field_name,
                        current_value=value,
                        expected_format=f"< {self.max_value}",
                        message=f"字段 '{field_name}' 值 {value} 不小于最大值 {self.max_value}"
                    )


class ValidatorRegistry:
    """
    验证器注册表

    管理验证器的注册和执行。

    Example:
        >>> registry = ValidatorRegistry()
        >>> registry.register("token", RequiredFieldValidator())
        >>> registry.register("token", TypeValidator(str))
        >>> registry.validate_all({"token": "abc123"})  # 通过
        >>> registry.validate_all({"token": ""})  # 抛出ConfigValidationError
    """

    def __init__(self):
        """初始化验证器注册表"""
        self._validators: Dict[str, List[Validator]] = {}

    def register(self, field_name: str, validator: Validator) -> None:
        """
        注册验证器

        Args:
            field_name: 字段名称
            validator: 验证器实例
        """
        if field_name not in self._validators:
            self._validators[field_name] = []
        self._validators[field_name].append(validator)

    def validate_field(self, field_name: str, value: Any) -> List[str]:
        """
        验证单个字段

        Args:
            field_name: 字段名称
            value: 字段值

        Returns:
            错误消息列表，如果验证通过则返回空列表
        """
        errors = []
        validators = self._validators.get(field_name, [])

        for validator in validators:
            try:
                validator.validate(field_name, value)
            except ConfigValidationError as e:
                errors.append(str(e))

        return errors

    def validate_all(self, config: Dict[str, Any]) -> Dict[str, List[str]]:
        """
        验证所有字段

        Args:
            config: 配置字典

        Returns:
            错误字典，格式: {field_name: [error_messages]}
            如果验证通过则返回空字典
        """
        all_errors = {}

        for field_name in self._validators.keys():
            value = config.get(field_name)
            errors = self.validate_field(field_name, value)
            if errors:
                all_errors[field_name] = errors

        return all_errors

    def clear(self) -> None:
        """清空所有注册的验证器"""
        self._validators.clear()

    def get_validators(self, field_name: str) -> List[Validator]:
        """
        获取字段的所有验证器

        Args:
            field_name: 字段名称

        Returns:
            验证器列表
        """
        return self._validators.get(field_name, []).copy()


__all__ = [
    'Validator',
    'TypeValidator',
    'RequiredFieldValidator',
    'FormatValidator',
    'PathValidator',
    'RangeValidator',
    'ValidatorRegistry',
]
