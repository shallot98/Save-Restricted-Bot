"""Path and numeric range validators."""

from pathlib import Path
from typing import Any, Optional

from .exceptions import ConfigValidationError
from .validator_base import Validator


class PathValidator(Validator):
    """Validate path existence and type."""

    def __init__(
        self,
        must_exist: bool = False,
        must_be_dir: bool = False,
        must_be_file: bool = False,
        *legacy_create_if_missing: bool,
        create_if_missing: bool = False,
    ):
        if len(legacy_create_if_missing) > 1:
            raise TypeError("PathValidator accepts at most one legacy create_if_missing argument")
        if legacy_create_if_missing:
            if create_if_missing:
                raise TypeError("PathValidator received duplicate create_if_missing values")
            create_if_missing = legacy_create_if_missing[0]

        self.must_exist = must_exist
        self.must_be_dir = must_be_dir
        self.must_be_file = must_be_file
        self.create_if_missing = create_if_missing

        if must_be_dir and must_be_file:
            raise ValueError("must_be_dir和must_be_file不能同时为True")

    def validate(self, field_name: str, value: Any) -> None:
        if not isinstance(value, (str, Path)):
            raise ConfigValidationError(
                field_name=field_name,
                current_value=value,
                expected_format="字符串或Path对象",
                message=f"字段 '{field_name}' 必须是字符串或Path对象",
            )

        path = Path(value) if isinstance(value, str) else value
        self._validate_exists(field_name, path)
        self._validate_type(field_name, path)

    def _validate_exists(self, field_name: str, path: Path) -> None:
        if not self.must_exist or path.exists():
            return

        if self.create_if_missing and self.must_be_dir:
            path.mkdir(parents=True, exist_ok=True)
            return

        raise ConfigValidationError(
            field_name=field_name,
            current_value=str(path),
            expected_format="存在的路径",
            message=f"路径 '{path}' 不存在",
        )

    def _validate_type(self, field_name: str, path: Path) -> None:
        if not path.exists():
            return

        if self.must_be_dir and not path.is_dir():
            raise ConfigValidationError(
                field_name=field_name,
                current_value=str(path),
                expected_format="目录路径",
                message=f"路径 '{path}' 不是目录",
            )

        if self.must_be_file and not path.is_file():
            raise ConfigValidationError(
                field_name=field_name,
                current_value=str(path),
                expected_format="文件路径",
                message=f"路径 '{path}' 不是文件",
            )


class RangeValidator(Validator):
    """Validate that a number is in the configured range."""

    def __init__(
        self,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
        inclusive: bool = True,
    ):
        self.min_value = min_value
        self.max_value = max_value
        self.inclusive = inclusive

    def validate(self, field_name: str, value: Any) -> None:
        if not isinstance(value, (int, float)):
            raise ConfigValidationError(
                field_name=field_name,
                current_value=value,
                expected_format="数值类型",
                message=f"字段 '{field_name}' 必须是数值类型",
            )

        self._validate_min(field_name, value)
        self._validate_max(field_name, value)

    def _validate_min(self, field_name: str, value: float) -> None:
        if self.min_value is None:
            return

        if self.inclusive and value < self.min_value:
            raise ConfigValidationError(
                field_name=field_name,
                current_value=value,
                expected_format=f">= {self.min_value}",
                message=f"字段 '{field_name}' 值 {value} 小于最小值 {self.min_value}",
            )

        if not self.inclusive and value <= self.min_value:
            raise ConfigValidationError(
                field_name=field_name,
                current_value=value,
                expected_format=f"> {self.min_value}",
                message=f"字段 '{field_name}' 值 {value} 不大于最小值 {self.min_value}",
            )

    def _validate_max(self, field_name: str, value: float) -> None:
        if self.max_value is None:
            return

        if self.inclusive and value > self.max_value:
            raise ConfigValidationError(
                field_name=field_name,
                current_value=value,
                expected_format=f"<= {self.max_value}",
                message=f"字段 '{field_name}' 值 {value} 大于最大值 {self.max_value}",
            )

        if not self.inclusive and value >= self.max_value:
            raise ConfigValidationError(
                field_name=field_name,
                current_value=value,
                expected_format=f"< {self.max_value}",
                message=f"字段 '{field_name}' 值 {value} 不小于最大值 {self.max_value}",
            )
