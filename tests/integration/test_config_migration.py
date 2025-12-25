"""
配置迁移兼容性测试
================

测试配置迁移后的兼容性和功能正确性。
"""

import pytest
import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.config import settings
from src.compat.config_compat import (
    load_config, load_watch_config, load_webdav_config, load_viewer_config,
    DATA_DIR, CONFIG_DIR, MEDIA_DIR, CONFIG_FILE, WATCH_FILE
)


class TestCompatibilityLayer:
    """测试兼容层功能"""

    def test_load_config_returns_dict(self):
        """测试load_config返回字典"""
        config = load_config()
        assert isinstance(config, dict)

    def test_load_watch_config_returns_dict(self):
        """测试load_watch_config返回字典"""
        config = load_watch_config()
        assert isinstance(config, dict)

    def test_load_webdav_config_returns_dict(self):
        """测试load_webdav_config返回字典"""
        config = load_webdav_config()
        assert isinstance(config, dict)
        # 验证必需字段
        assert 'enabled' in config
        assert 'url' in config

    def test_load_viewer_config_returns_dict(self):
        """测试load_viewer_config返回字典"""
        config = load_viewer_config()
        assert isinstance(config, dict)
        assert 'viewer_url' in config

    def test_path_constants_are_strings(self):
        """测试路径常量是字符串"""
        assert isinstance(DATA_DIR, str)
        assert isinstance(CONFIG_DIR, str)
        assert isinstance(MEDIA_DIR, str)
        assert isinstance(CONFIG_FILE, str)
        assert isinstance(WATCH_FILE, str)


class TestSettingsIntegration:
    """测试Settings类集成"""

    def test_settings_paths_accessible(self):
        """测试settings路径可访问"""
        assert settings.paths.data_dir is not None
        assert settings.paths.config_dir is not None
        assert settings.paths.media_dir is not None

    def test_settings_main_config_accessible(self):
        """测试主配置可访问"""
        config = settings.main_config
        assert isinstance(config, dict)

    def test_settings_webdav_config_accessible(self):
        """测试WebDAV配置可访问"""
        config = settings.webdav_config
        assert isinstance(config, dict)
        assert 'enabled' in config

    def test_settings_watch_config_accessible(self):
        """测试监控配置可访问"""
        config = settings.watch_config
        assert isinstance(config, dict)


class TestConfigConsistency:
    """测试配置一致性"""

    def test_compat_layer_matches_settings(self):
        """测试兼容层和Settings返回一致的配置"""
        # 主配置
        compat_config = load_config()
        settings_config = settings.main_config
        # 两者应该返回相同的数据
        assert compat_config == settings_config

    def test_webdav_config_consistency(self):
        """测试WebDAV配置一致性"""
        compat_config = load_webdav_config()
        settings_config = settings.webdav_config
        assert compat_config == settings_config

    def test_path_constants_match_settings(self):
        """测试路径常量与settings一致"""
        assert DATA_DIR == str(settings.paths.data_dir)
        assert CONFIG_DIR == str(settings.paths.config_dir)
        assert MEDIA_DIR == str(settings.paths.media_dir)


class TestDatabaseModule:
    """测试database模块"""

    def test_database_imports_settings(self):
        """测试database模块正确导入settings"""
        import database
        # 验证database模块使用了settings
        assert hasattr(database, 'DATA_DIR')
        assert hasattr(database, 'DATABASE_FILE')

    def test_database_paths_correct(self):
        """测试database路径正确"""
        import database
        # 验证路径是字符串
        assert isinstance(database.DATA_DIR, str)
        assert isinstance(database.DATABASE_FILE, str)
        # 验证路径包含正确的目录
        assert 'data' in database.DATA_DIR or 'DATA' in database.DATA_DIR


class TestWebRoutes:
    """测试web路由"""

    def test_web_routes_imports_settings(self):
        """测试web路由正确导入settings"""
        from web.routes import main
        # 验证导入了settings
        assert hasattr(main, 'settings')

    def test_web_routes_health_check(self):
        """测试健康检查端点使用正确的配置"""
        from web.routes.main import health
        # 函数应该存在
        assert callable(health)


class TestMessageWorker:
    """测试消息工作器"""

    def test_message_worker_imports_settings(self):
        """测试消息工作器正确导入settings"""
        from bot.workers import message_worker
        # 验证导入了settings
        assert hasattr(message_worker, 'settings')

    def test_message_worker_webdav_config(self):
        """测试消息工作器可以访问WebDAV配置"""
        # 验证settings.webdav_config可用
        config = settings.webdav_config
        assert isinstance(config, dict)
        assert 'enabled' in config


class TestSourcesManager:
    """测试监控源管理器"""

    def test_sources_manager_initialization(self):
        """测试监控源管理器可以初始化"""
        from bot.utils.sources_manager import MonitoredSourcesManager
        from src.compat.config_compat import load_watch_config

        # 使用兼容层函数初始化
        manager = MonitoredSourcesManager(config_loader=load_watch_config)
        assert manager is not None

    def test_sources_manager_reload(self):
        """测试监控源管理器可以重载"""
        from bot.utils.sources_manager import MonitoredSourcesManager
        from src.compat.config_compat import load_watch_config

        manager = MonitoredSourcesManager(config_loader=load_watch_config)
        sources = manager.reload()
        assert isinstance(sources, set)


class TestMigrationScript:
    """测试迁移脚本"""

    def test_migration_script_exists(self):
        """测试迁移脚本文件存在"""
        script_path = Path(__file__).parent.parent.parent / 'scripts' / 'migrate_config.py'
        assert script_path.exists()

    def test_migration_script_dry_run(self):
        """测试迁移脚本dry-run模式"""
        import subprocess
        script_path = Path(__file__).parent.parent.parent / 'scripts' / 'migrate_config.py'

        # 运行dry-run模式
        result = subprocess.run(
            [sys.executable, str(script_path), '--dry-run'],
            capture_output=True,
            text=True,
            timeout=30
        )

        # 验证脚本可以运行
        assert result.returncode == 0


class TestBackwardCompatibility:
    """测试向后兼容性"""

    def test_old_import_style_works(self):
        """测试旧的导入方式仍然有效"""
        # 旧的导入方式
        from config import load_config, CONFIG_FILE, DATA_DIR

        # 验证函数可用
        assert callable(load_config)
        # 验证常量可用
        assert isinstance(CONFIG_FILE, str)
        assert isinstance(DATA_DIR, str)

    def test_old_config_access_pattern(self):
        """测试旧的配置访问模式仍然有效"""
        from config import load_config

        config = load_config()
        # 旧的访问方式：config.get('KEY')
        token = config.get('TOKEN', '')
        assert isinstance(token, str)


# 参数化测试
@pytest.mark.parametrize("config_func,expected_keys", [
    (load_config, ['TOKEN', 'HASH', 'ID', 'STRING', 'OWNER_ID']),
    (load_webdav_config, ['enabled', 'url', 'username', 'password']),
    (load_viewer_config, ['viewer_url']),
])
def test_config_functions_return_expected_keys(config_func, expected_keys):
    """参数化测试配置函数返回期望的键"""
    config = config_func()
    for key in expected_keys:
        assert key in config, f"配置缺少键: {key}"
