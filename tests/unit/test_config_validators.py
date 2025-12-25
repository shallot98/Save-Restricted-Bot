"""
配置验证器单元测试
================

测试配置验证器的各种场景。
"""

import pytest
import sys
from pathlib import Path
from typing import Any

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.config.validators import (
    TypeValidator,
    RequiredFieldValidator,
    FormatValidator,
    PathValidator,
    RangeValidator,
    ValidatorRegistry,
)
from src.core.config.exceptions import ConfigValidationError


class TestTypeValidator:
    """测试TypeValidator"""

    def test_validate_correct_type(self):
        """测试正确的类型"""
        validator = TypeValidator(str)
        validator.validate("name", "John")  # 不应抛出异常

    def test_validate_wrong_type(self):
        """测试错误的类型"""
        validator = TypeValidator(str)
        with pytest.raises(ConfigValidationError) as exc_info:
            validator.validate("name", 123)
        assert "类型错误" in str(exc_info.value)

    def test_validate_none_not_allowed(self):
        """测试不允许None值"""
        validator = TypeValidator(str, allow_none=False)
        with pytest.raises(ConfigValidationError):
            validator.validate("name", None)

    def test_validate_none_allowed(self):
        """测试允许None值"""
        validator = TypeValidator(str, allow_none=True)
        validator.validate("name", None)  # 不应抛出异常

    def test_validate_complex_type(self):
        """测试复杂类型"""
        validator = TypeValidator(dict)
        validator.validate("config", {"key": "value"})  # 不应抛出异常

        with pytest.raises(ConfigValidationError):
            validator.validate("config", "not a dict")


class TestRequiredFieldValidator:
    """测试RequiredFieldValidator"""

    def test_validate_field_exists(self):
        """测试必填字段存在"""
        validator = RequiredFieldValidator()
        validator.validate("token", "abc123")  # 不应抛出异常

    def test_validate_field_missing_none(self):
        """测试必填字段为None"""
        validator = RequiredFieldValidator()
        with pytest.raises(ConfigValidationError) as exc_info:
            validator.validate("token", None)
        assert "不能为None" in str(exc_info.value)

    def test_validate_empty_string_not_allowed(self):
        """测试不允许空字符串"""
        validator = RequiredFieldValidator(allow_empty_string=False)
        with pytest.raises(ConfigValidationError) as exc_info:
            validator.validate("token", "")
        assert "不能为空字符串" in str(exc_info.value)

    def test_validate_empty_string_allowed(self):
        """测试允许空字符串"""
        validator = RequiredFieldValidator(allow_empty_string=True)
        validator.validate("token", "")  # 不应抛出异常

    def test_validate_empty_collection(self):
        """测试空集合"""
        validator = RequiredFieldValidator()

        with pytest.raises(ConfigValidationError):
            validator.validate("items", [])

        with pytest.raises(ConfigValidationError):
            validator.validate("items", {})

        with pytest.raises(ConfigValidationError):
            validator.validate("items", set())


class TestFormatValidator:
    """测试FormatValidator"""

    def test_validate_correct_format(self):
        """测试正确的格式"""
        validator = FormatValidator(r'^https?://.+', "URL格式")
        validator.validate("url", "https://example.com")  # 不应抛出异常
        validator.validate("url", "http://example.com")  # 不应抛出异常

    def test_validate_wrong_format(self):
        """测试错误的格式"""
        validator = FormatValidator(r'^https?://.+', "URL格式")
        with pytest.raises(ConfigValidationError) as exc_info:
            validator.validate("url", "invalid_url")
        assert "格式错误" in str(exc_info.value)

    def test_validate_empty_string_not_allowed(self):
        """测试不允许空字符串"""
        validator = FormatValidator(r'^https?://.+', "URL格式", allow_empty=False)
        with pytest.raises(ConfigValidationError):
            validator.validate("url", "")

    def test_validate_empty_string_allowed(self):
        """测试允许空字符串"""
        validator = FormatValidator(r'^https?://.+', "URL格式", allow_empty=True)
        validator.validate("url", "")  # 不应抛出异常

    def test_validate_non_string_value(self):
        """测试非字符串值"""
        validator = FormatValidator(r'^https?://.+', "URL格式")
        with pytest.raises(ConfigValidationError) as exc_info:
            validator.validate("url", 123)
        assert "必须是字符串类型" in str(exc_info.value)


class TestPathValidator:
    """测试PathValidator"""

    def test_validate_existing_path(self, tmp_path):
        """测试存在的路径"""
        validator = PathValidator(must_exist=True)
        validator.validate("path", str(tmp_path))  # 不应抛出异常

    def test_validate_non_existing_path(self):
        """测试不存在的路径"""
        validator = PathValidator(must_exist=True)
        with pytest.raises(ConfigValidationError) as exc_info:
            validator.validate("path", "/non/existing/path")
        assert "不存在" in str(exc_info.value)

    def test_validate_directory(self, tmp_path):
        """测试目录路径"""
        validator = PathValidator(must_exist=True, must_be_dir=True)
        validator.validate("dir", str(tmp_path))  # 不应抛出异常

    def test_validate_file(self, tmp_path):
        """测试文件路径"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        validator = PathValidator(must_exist=True, must_be_file=True)
        validator.validate("file", str(test_file))  # 不应抛出异常

    def test_validate_create_if_missing(self, tmp_path):
        """测试自动创建目录"""
        new_dir = tmp_path / "new_dir"
        validator = PathValidator(must_exist=True, must_be_dir=True, create_if_missing=True)
        validator.validate("dir", str(new_dir))  # 不应抛出异常
        assert new_dir.exists()


class TestRangeValidator:
    """测试RangeValidator"""

    def test_validate_in_range(self):
        """测试值在范围内"""
        validator = RangeValidator(min_value=0, max_value=100)
        validator.validate("port", 80)  # 不应抛出异常

    def test_validate_below_min(self):
        """测试值小于最小值"""
        validator = RangeValidator(min_value=0, max_value=100)
        with pytest.raises(ConfigValidationError) as exc_info:
            validator.validate("port", -1)
        assert "小于最小值" in str(exc_info.value)

    def test_validate_above_max(self):
        """测试值大于最大值"""
        validator = RangeValidator(min_value=0, max_value=100)
        with pytest.raises(ConfigValidationError) as exc_info:
            validator.validate("port", 101)
        assert "大于最大值" in str(exc_info.value)

    def test_validate_boundary_inclusive(self):
        """测试边界值（包含）"""
        validator = RangeValidator(min_value=0, max_value=100, inclusive=True)
        validator.validate("port", 0)  # 不应抛出异常
        validator.validate("port", 100)  # 不应抛出异常

    def test_validate_boundary_exclusive(self):
        """测试边界值（不包含）"""
        validator = RangeValidator(min_value=0, max_value=100, inclusive=False)
        with pytest.raises(ConfigValidationError):
            validator.validate("port", 0)
        with pytest.raises(ConfigValidationError):
            validator.validate("port", 100)


class TestValidatorRegistry:
    """测试ValidatorRegistry"""

    def test_register_validator(self):
        """测试注册验证器"""
        registry = ValidatorRegistry()
        validator = TypeValidator(str)
        registry.register("name", validator)

        validators = registry.get_validators("name")
        assert len(validators) == 1
        assert isinstance(validators[0], TypeValidator)

    def test_register_multiple_validators(self):
        """测试注册多个验证器"""
        registry = ValidatorRegistry()
        registry.register("token", RequiredFieldValidator())
        registry.register("token", TypeValidator(str))

        validators = registry.get_validators("token")
        assert len(validators) == 2

    def test_validate_field_success(self):
        """测试字段验证成功"""
        registry = ValidatorRegistry()
        registry.register("token", RequiredFieldValidator())
        registry.register("token", TypeValidator(str))

        errors = registry.validate_field("token", "abc123")
        assert len(errors) == 0

    def test_validate_field_failure(self):
        """测试字段验证失败"""
        registry = ValidatorRegistry()
        registry.register("token", RequiredFieldValidator())

        errors = registry.validate_field("token", None)
        assert len(errors) > 0
        assert "不能为None" in errors[0]

    def test_validate_all_success(self):
        """测试验证所有字段成功"""
        registry = ValidatorRegistry()
        registry.register("token", RequiredFieldValidator())
        registry.register("port", RangeValidator(min_value=0, max_value=65535))

        config = {"token": "abc123", "port": 8080}
        errors = registry.validate_all(config)
        assert len(errors) == 0

    def test_validate_all_failure(self):
        """测试验证所有字段失败"""
        registry = ValidatorRegistry()
        registry.register("token", RequiredFieldValidator())
        registry.register("port", RangeValidator(min_value=0, max_value=65535))

        config = {"token": None, "port": 70000}
        errors = registry.validate_all(config)
        assert len(errors) == 2
        assert "token" in errors
        assert "port" in errors

    def test_clear_validators(self):
        """测试清空验证器"""
        registry = ValidatorRegistry()
        registry.register("token", RequiredFieldValidator())
        registry.clear()

        validators = registry.get_validators("token")
        assert len(validators) == 0


# 参数化测试示例
@pytest.mark.parametrize("value,expected_valid", [
    ("https://example.com", True),
    ("http://example.com", True),
    ("ftp://example.com", False),
    ("invalid", False),
    ("", False),
])
def test_url_format_validation(value: str, expected_valid: bool):
    """参数化测试URL格式验证"""
    validator = FormatValidator(r'^https?://.+', "URL格式")

    if expected_valid:
        validator.validate("url", value)  # 不应抛出异常
    else:
        with pytest.raises(ConfigValidationError):
            validator.validate("url", value)


@pytest.mark.parametrize("value,expected_valid", [
    (50, True),
    (0, True),
    (100, True),
    (-1, False),
    (101, False),
])
def test_range_validation(value: int, expected_valid: bool):
    """参数化测试范围验证"""
    validator = RangeValidator(min_value=0, max_value=100)

    if expected_valid:
        validator.validate("value", value)  # 不应抛出异常
    else:
        with pytest.raises(ConfigValidationError):
            validator.validate("value", value)
