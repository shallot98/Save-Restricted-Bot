"""
配置热重载测试
============

测试配置热重载功能。
"""

import pytest
import sys
import json
import time
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.config.notifier import ConfigChangeNotifier
from src.core.config.watcher import ConfigWatcher
from src.core.config.hot_reload import HotReloadManager


class TestConfigChangeNotifier:
    """测试配置变更通知器"""

    def test_subscribe_and_notify(self):
        """测试订阅和通知"""
        notifier = ConfigChangeNotifier()
        notifications = []

        def callback(config_type, old, new):
            notifications.append((config_type, old, new))

        # 订阅
        sub_id = notifier.subscribe(callback)
        assert isinstance(sub_id, str)

        # 通知
        notifier.notify("main", {"old": "value"}, {"new": "value"})

        # 验证收到通知
        assert len(notifications) == 1
        assert notifications[0][0] == "main"

        # 取消订阅
        assert notifier.unsubscribe(sub_id) is True

    def test_multiple_subscribers(self):
        """测试多个订阅者"""
        notifier = ConfigChangeNotifier()
        notifications1 = []
        notifications2 = []

        def callback1(config_type, old, new):
            notifications1.append(config_type)

        def callback2(config_type, old, new):
            notifications2.append(config_type)

        # 订阅
        sub_id1 = notifier.subscribe(callback1)
        sub_id2 = notifier.subscribe(callback2)

        # 通知
        notifier.notify("main", None, None)

        # 验证两个订阅者都收到通知
        assert len(notifications1) == 1
        assert len(notifications2) == 1

        # 清理
        notifier.unsubscribe(sub_id1)
        notifier.unsubscribe(sub_id2)

    def test_subscriber_error_handling(self):
        """测试订阅者错误处理"""
        notifier = ConfigChangeNotifier()

        def bad_callback(config_type, old, new):
            raise Exception("订阅者错误")

        def good_callback(config_type, old, new):
            pass

        # 订阅
        notifier.subscribe(bad_callback)
        notifier.subscribe(good_callback)

        # 通知（不应该抛出异常）
        notifier.notify("main", None, None)


class TestConfigWatcher:
    """测试配置文件监控器"""

    def test_watcher_creation(self, tmp_path):
        """测试监控器创建"""
        changes = []

        def on_change(file_path):
            changes.append(file_path)

        watcher = ConfigWatcher(
            watch_dir=tmp_path,
            watch_files={"test.json"},
            on_change=on_change
        )

        assert watcher is not None
        assert not watcher.is_running()

    def test_watcher_start_stop(self, tmp_path):
        """测试监控器启动和停止"""
        def on_change(file_path):
            pass

        watcher = ConfigWatcher(
            watch_dir=tmp_path,
            watch_files={"test.json"},
            on_change=on_change
        )

        # 启动
        watcher.start()
        assert watcher.is_running()

        # 停止
        watcher.stop()
        time.sleep(0.5)  # 等待停止完成
        assert not watcher.is_running()

    def test_watcher_detects_file_change(self, tmp_path):
        """测试监控器检测文件变更"""
        changes = []

        def on_change(file_path):
            changes.append(file_path.name)

        watcher = ConfigWatcher(
            watch_dir=tmp_path,
            watch_files={"test.json"},
            on_change=on_change,
            debounce_seconds=0.1
        )

        # 启动监控
        watcher.start()

        try:
            # 创建测试文件
            test_file = tmp_path / "test.json"
            test_file.write_text('{"key": "value"}')

            # 等待文件系统事件
            time.sleep(0.5)

            # 修改文件
            test_file.write_text('{"key": "new_value"}')

            # 等待检测到变更
            time.sleep(0.5)

            # 验证检测到变更
            assert len(changes) > 0
            assert "test.json" in changes

        finally:
            watcher.stop()


class TestHotReloadManager:
    """测试热重载管理器"""

    def test_hot_reload_manager_creation(self, tmp_path):
        """测试热重载管理器创建"""
        reloads = []

        def reload_callback(file_path):
            reloads.append(file_path)

        manager = HotReloadManager(
            config_dir=tmp_path,
            reload_callback=reload_callback
        )

        assert manager is not None
        assert not manager.is_running()

    def test_hot_reload_start_stop(self, tmp_path):
        """测试热重载启动和停止"""
        def reload_callback(file_path):
            pass

        manager = HotReloadManager(
            config_dir=tmp_path,
            reload_callback=reload_callback
        )

        # 启动
        manager.start()
        assert manager.is_running()

        # 停止
        manager.stop()
        time.sleep(0.5)
        assert not manager.is_running()

    def test_hot_reload_with_notification(self, tmp_path):
        """测试热重载和通知"""
        reloads = []
        notifications = []

        def reload_callback(file_path):
            reloads.append(file_path.name)

        def on_change(config_type, old, new):
            notifications.append(config_type)

        manager = HotReloadManager(
            config_dir=tmp_path,
            reload_callback=reload_callback,
            watch_files={"config.json"}
        )

        # 订阅通知
        sub_id = manager.notifier.subscribe(on_change)

        # 启动热重载
        manager.start()

        try:
            # 创建配置文件
            config_file = tmp_path / "config.json"
            config_file.write_text('{"TOKEN": "test"}')

            # 等待文件系统事件
            time.sleep(0.5)

            # 修改配置文件
            config_file.write_text('{"TOKEN": "updated"}')

            # 等待检测到变更和重载
            time.sleep(1.5)

            # 验证重载被触发
            assert len(reloads) > 0
            assert "config.json" in reloads

            # 验证通知被发送
            assert len(notifications) > 0

        finally:
            manager.notifier.unsubscribe(sub_id)
            manager.stop()


class TestSettingsHotReload:
    """测试Settings类的热重载功能"""

    def test_settings_subscribe(self):
        """测试Settings订阅功能"""
        from src.core.config import settings

        notifications = []

        def callback(config_type, old, new):
            notifications.append(config_type)

        # 订阅
        sub_id = settings.subscribe(callback)
        assert isinstance(sub_id, str)

        # 取消订阅
        assert settings.unsubscribe(sub_id) is True

    def test_settings_enable_disable_hot_reload(self):
        """测试Settings启用和禁用热重载"""
        from src.core.config import settings

        # 启用热重载
        settings.enable_hot_reload()

        # 验证热重载已启用
        assert settings._hot_reload_manager is not None
        assert settings._hot_reload_manager.is_running()

        # 禁用热重载
        settings.disable_hot_reload()

        # 验证热重载已禁用
        assert settings._hot_reload_manager is None


# 参数化测试
@pytest.mark.parametrize("config_file,config_type", [
    ("config.json", "main"),
    ("watch_config.json", "watch"),
    ("webdav_config.json", "webdav"),
    ("viewer_config.json", "viewer"),
])
def test_config_type_mapping(config_file, config_type):
    """参数化测试配置类型映射"""
    from src.core.config.hot_reload import HotReloadManager

    def reload_callback(file_path):
        pass

    manager = HotReloadManager(
        config_dir=Path("/tmp"),
        reload_callback=reload_callback
    )

    # 测试配置类型映射
    result = manager._get_config_type(config_file)
    assert result == config_type
