"""Basic type, required-field, and format validators."""

import re
from typing import Any, Pattern, Type

from .exceptions import ConfigValidationError
from .validator_base import Validator


class TypeValidator(Validator):
    """Validate that a value has the expected type."""

    def __init__(self, expected_type: Type, allow_none: bool = False):
        self.expected_type = expected_type
        self.allow_none = allow_none

    def validate(self, field_name: str, value: Any) -> None:
        if value is None:
            if not self.allow_none:
                raise ConfigValidationError(
                    field_name=field_name,
                    current_value=value,
                    expected_format=f"类型 {self.expected_type.__name__}（不允许None）",
                )
            return

        if not isinstance(value, self.expected_type):
            raise ConfigValidationError(
                field_name=field_name,
                current_value=value,
                expected_format=f"类型 {self.expected_type.__name__}",
                message=(
                    f"字段 '{field_name}' 类型错误: "
                    f"期望 {self.expected_type.__name__}，实际 {type(value).__name__}"
                ),
            )


class RequiredFieldValidator(Validator):
    """Validate that a value is present and non-empty."""

    def __init__(self, allow_empty_string: bool = False):
        self.allow_empty_string = allow_empty_string

    def validate(self, field_name: str, value: Any) -> None:
        if value is None:
            raise ConfigValidationError(
                field_name=field_name,
                current_value=value,
                expected_format="非空值",
                message=f"必填字段 '{field_name}' 不能为None",
            )

        if isinstance(value, str) and not self.allow_empty_string and not value.strip():
            raise ConfigValidationError(
                field_name=field_name,
                current_value=value,
                expected_format="非空字符串",
                message=f"必填字段 '{field_name}' 不能为空字符串",
            )

        if isinstance(value, (list, dict, set, tuple)) and len(value) == 0:
            raise ConfigValidationError(
                field_name=field_name,
                current_value=value,
                expected_format="非空集合",
                message=f"必填字段 '{field_name}' 不能为空集合",
            )


class FormatValidator(Validator):
    """Validate a string value against a regular expression."""

    def __init__(self, pattern: str, format_description: str, allow_empty: bool = False):
        self.pattern: Pattern = re.compile(pattern)
        self.format_description = format_description
        self.allow_empty = allow_empty

    def validate(self, field_name: str, value: Any) -> None:
        if not isinstance(value, str):
            raise ConfigValidationError(
                field_name=field_name,
                current_value=value,
                expected_format=f"字符串（{self.format_description}）",
                message=f"字段 '{field_name}' 必须是字符串类型",
            )

        if not value and self.allow_empty:
            return

        if not self.pattern.match(value):
            raise ConfigValidationError(
                field_name=field_name,
                current_value=value,
                expected_format=self.format_description,
                message=f"字段 '{field_name}' 格式错误: 期望 {self.format_description}",
            )
