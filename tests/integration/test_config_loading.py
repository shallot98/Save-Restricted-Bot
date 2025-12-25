"""
配置加载集成测试
================

测试配置加载、优先级、持久化等功能。
"""

import pytest
import os
import sys
import json
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.config.loader import ConfigLoader
from src.core.config.models import MainConfig, WebDAVConfig, ViewerConfig, WatchConfig
from src.core.config.exceptions import ConfigValidationError, ConfigLoadError


class TestConfigLoader:
    """测试ConfigLoader类"""

    def test_load_from_env(self):
        """测试从环境变量加载配置"""
        loader = ConfigLoader()

        with patch.dict(os.environ, {"WEBDAV_ENABLED": "true", "WEBDAV_URL": "https://example.com"}):
            config = loader.load_from_env(prefix="WEBDAV_", keys=["ENABLED", "URL"])

        assert config["ENABLED"] == "true"
        assert config["URL"] == "https://example.com"

    def test_load_from_file(self, tmp_path):
        """测试从文件加载配置"""
        loader = ConfigLoader()

        # 创建测试配置文件
        config_file = tmp_path / "test_config.json"
        test_data = {"TOKEN": "test_token", "HASH": "test_hash"}
        with open(config_file, 'w') as f:
            json.dump(test_data, f)

        config = loader.load_from_file(config_file)
        assert config["TOKEN"] == "test_token"
        assert config["HASH"] == "test_hash"

    def test_load_from_file_not_exists(self, tmp_path):
        """测试加载不存在的文件"""
        loader = ConfigLoader()
        config_file = tmp_path / "non_existent.json"

        config = loader.load_from_file(config_file, default={"key": "value"})
        assert config == {"key": "value"}

    def test_merge_configs(self):
        """测试配置合并"""
        loader = ConfigLoader()

        env_config = {"TOKEN": "env_token"}
        file_config = {"TOKEN": "file_token", "HASH": "file_hash"}
        default_config = {"TOKEN": "", "HASH": "", "ID": ""}

        merged = loader.merge_configs(env_config, file_config, default_config)

        # 环境变量优先级最高
        assert merged["TOKEN"] == "env_token"
        # 文件配置次之
        assert merged["HASH"] == "file_hash"
        # 默认值最低
        assert merged["ID"] == ""

    def test_validate_config_success(self):
        """测试配置验证成功"""
        loader = ConfigLoader()

        config_data = {
            "TOKEN": "test_token",
            "HASH": "test_hash",
            "ID": "123",
            "STRING": "test_string",
            "OWNER_ID": "456"
        }

        config = loader.validate_config(MainConfig, config_data)
        assert config.TOKEN == "test_token"
        assert config.HASH == "test_hash"

    def test_validate_config_failure(self):
        """测试配置验证失败"""
        loader = ConfigLoader()

        # WebDAV URL格式错误
        config_data = {
            "enabled": True,
            "url": "invalid_url",  # 无效的URL格式
            "username": "user",
            "password": "pass"
        }

        with pytest.raises(ConfigValidationError):
            loader.validate_config(WebDAVConfig, config_data)

    def test_load_and_validate(self, tmp_path):
        """测试一站式加载和验证"""
        loader = ConfigLoader()

        # 创建配置文件
        config_file = tmp_path / "config.json"
        test_data = {"TOKEN": "file_token", "HASH": "file_hash"}
        with open(config_file, 'w') as f:
            json.dump(test_data, f)

        # 设置环境变量（优先级更高）
        with patch.dict(os.environ, {"TOKEN": "env_token"}):
            config = loader.load_and_validate(
                MainConfig,
                file_path=config_file,
                env_prefix="",
                default_config={}
            )

        # 环境变量应该覆盖文件配置
        assert config.TOKEN == "env_token"
        assert config.HASH == "file_hash"

    def test_save_to_file(self, tmp_path):
        """测试保存配置到文件"""
        loader = ConfigLoader()

        config = MainConfig(TOKEN="test_token", HASH="test_hash")
        config_file = tmp_path / "config.json"

        loader.save_to_file(config, config_file)

        # 验证文件已创建
        assert config_file.exists()

        # 验证文件内容
        with open(config_file, 'r') as f:
            data = json.load(f)
        assert data["TOKEN"] == "test_token"
        assert data["HASH"] == "test_hash"


class TestConfigPriority:
    """测试配置优先级"""

    def test_env_overrides_file(self, tmp_path):
        """测试环境变量覆盖文件配置"""
        loader = ConfigLoader()

        # 创建配置文件
        config_file = tmp_path / "config.json"
        with open(config_file, 'w') as f:
            json.dump({"TOKEN": "file_token"}, f)

        # 设置环境变量
        with patch.dict(os.environ, {"TOKEN": "env_token"}):
            config = loader.load_and_validate(
                MainConfig,
                file_path=config_file,
                env_prefix=""
            )

        assert config.TOKEN == "env_token"

    def test_file_overrides_default(self, tmp_path):
        """测试文件配置覆盖默认值"""
        loader = ConfigLoader()

        # 创建配置文件
        config_file = tmp_path / "config.json"
        with open(config_file, 'w') as f:
            json.dump({"TOKEN": "file_token"}, f)

        config = loader.load_and_validate(
            MainConfig,
            file_path=config_file,
            env_prefix="",
            default_config={"TOKEN": "default_token"}
        )

        assert config.TOKEN == "file_token"

    def test_default_when_no_other_source(self):
        """测试无其他配置源时使用默认值"""
        loader = ConfigLoader()

        config = loader.load_and_validate(
            MainConfig,
            file_path=None,
            env_prefix="",
            default_config={"TOKEN": "default_token"}
        )

        assert config.TOKEN == "default_token"


class TestConfigPersistence:
    """测试配置持久化"""

    def test_atomic_write(self, tmp_path):
        """测试原子写入"""
        loader = ConfigLoader()

        config = MainConfig(TOKEN="test_token")
        config_file = tmp_path / "config.json"

        # 第一次写入
        loader.save_to_file(config, config_file)
        assert config_file.exists()

        # 修改并再次写入
        config.TOKEN = "updated_token"
        loader.save_to_file(config, config_file)

        # 验证文件已更新
        with open(config_file, 'r') as f:
            data = json.load(f)
        assert data["TOKEN"] == "updated_token"


class TestConfigModels:
    """测试配置模型"""

    def test_main_config_validation(self):
        """测试MainConfig验证"""
        # 正常情况
        config = MainConfig(TOKEN="test", HASH="hash", ID="123")
        assert config.TOKEN == "test"

        # 空值（开发环境允许）
        # 注意：MainConfig会从环境变量加载，所以需要显式设置为空
        config = MainConfig(TOKEN="", HASH="", ID="", STRING="", OWNER_ID="")
        assert config.TOKEN == ""

    def test_webdav_config_validation(self):
        """测试WebDAVConfig验证"""
        # 正常情况
        config = WebDAVConfig(
            enabled=True,
            url="https://example.com",
            username="user",
            password="pass"
        )
        assert config.enabled is True

        # URL格式验证
        with pytest.raises(Exception):  # Pydantic会抛出ValidationError
            WebDAVConfig(url="invalid_url")

    def test_viewer_config_validation(self):
        """测试ViewerConfig验证"""
        # 正常情况
        config = ViewerConfig(viewer_url="https://example.com/watch?dn=")
        assert config.viewer_url.startswith("https://")

        # URL格式验证
        with pytest.raises(Exception):
            ViewerConfig(viewer_url="invalid_url")

    def test_watch_config_operations(self):
        """测试WatchConfig操作"""
        config = WatchConfig()

        # 设置用户监控源
        config.set_user_sources("123", {"source1": {"name": "Test"}})
        assert "123" in config.user_sources

        # 获取用户监控源
        sources = config.get_user_sources("123")
        assert "source1" in sources

        # 获取所有监控源ID
        all_ids = config.get_all_source_ids()
        assert "source1" in all_ids


class TestErrorHandling:
    """测试错误处理"""

    def test_invalid_json_file(self, tmp_path):
        """测试无效的JSON文件"""
        loader = ConfigLoader()

        # 创建无效的JSON文件
        config_file = tmp_path / "invalid.json"
        with open(config_file, 'w') as f:
            f.write("invalid json content")

        with pytest.raises(ConfigLoadError):
            loader.load_from_file(config_file)

    def test_validation_error_details(self):
        """测试验证错误详情"""
        loader = ConfigLoader()

        # 提供无效的配置
        config_data = {"url": "invalid_url"}

        try:
            loader.validate_config(WebDAVConfig, config_data)
            pytest.fail("应该抛出ConfigValidationError")
        except ConfigValidationError as e:
            # 验证错误信息包含字段名
            assert "url" in str(e).lower() or "viewer_url" in str(e).lower()


class TestThreadSafety:
    """测试线程安全"""

    def test_concurrent_config_access(self, tmp_path):
        """测试并发配置访问"""
        loader = ConfigLoader()
        config_file = tmp_path / "config.json"

        # 创建初始配置
        initial_config = {"TOKEN": "initial"}
        with open(config_file, 'w') as f:
            json.dump(initial_config, f)

        results = []
        errors = []

        def load_config():
            try:
                config = loader.load_from_file(config_file)
                results.append(config)
            except Exception as e:
                errors.append(e)

        # 创建多个线程并发加载配置
        threads = [threading.Thread(target=load_config) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 验证所有线程都成功加载
        assert len(errors) == 0
        assert len(results) == 10
        assert all(r["TOKEN"] == "initial" for r in results)


# 参数化测试
@pytest.mark.parametrize("env_value,file_value,expected", [
    ("env", "file", "env"),  # 环境变量优先
    (None, "file", "file"),  # 文件次之
])
def test_config_priority_parametrized(env_value, file_value, expected, tmp_path):
    """参数化测试配置优先级"""
    loader = ConfigLoader()

    # 创建配置文件
    config_file = tmp_path / "config.json"
    if file_value:
        with open(config_file, 'w') as f:
            json.dump({"TOKEN": file_value}, f)

    # 设置环境变量（清除现有的TOKEN环境变量）
    env_dict = {"TOKEN": env_value} if env_value else {}
    # 使用clear=True清除所有环境变量，然后只设置我们需要的
    with patch.dict(os.environ, env_dict, clear=True):
        config = loader.load_and_validate(
            MainConfig,
            file_path=config_file if file_value else None,
            env_prefix=""
        )

    assert config.TOKEN == expected
