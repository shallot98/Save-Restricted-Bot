"""Hot reload helpers for legacy Settings."""

import logging
from pathlib import Path

from .hot_reload import HotReloadManager
from .manager import ConfigChangeCallback
from .models import MainConfig, ViewerConfig, WatchConfig, WebDAVConfig

logger = logging.getLogger(__name__)


class SettingsHotReloadMixin:
    """Hot reload and subscription helpers shared by Settings."""

    def enable_hot_reload(self) -> None:
        """Enable configuration hot reload."""
        with self._rw_lock:
            if self._hot_reload_manager is not None and self._hot_reload_manager.is_running():
                logger.warning("热重载已经启用")
                return

            self._hot_reload_manager = HotReloadManager(
                config_dir=self._paths.config_dir,
                reload_callback=self._handle_config_reload,
            )
            self._hot_reload_manager.start()
            logger.info("配置热重载已启用")

    def disable_hot_reload(self) -> None:
        """Disable configuration hot reload."""
        with self._rw_lock:
            if self._hot_reload_manager is not None:
                self._hot_reload_manager.stop()
                self._hot_reload_manager = None
                logger.info("配置热重载已禁用")

    def subscribe(self, callback: ConfigChangeCallback) -> str:
        """Subscribe to configuration change notifications."""
        if self._hot_reload_manager is None:
            self._hot_reload_manager = HotReloadManager(
                config_dir=self._paths.config_dir,
                reload_callback=self._handle_config_reload,
            )
        return self._hot_reload_manager.notifier.subscribe(callback)

    def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe from configuration change notifications."""
        if self._hot_reload_manager is not None:
            return self._hot_reload_manager.notifier.unsubscribe(subscription_id)
        return False

    def _handle_config_reload(self, file_path: Path) -> None:
        """Reload the configuration represented by file_path."""
        with self._rw_lock:
            logger.info(f"重新加载配置: {file_path.name}")
            try:
                self._reload_config_file(file_path)
                logger.info(f"配置 {file_path.name} 重载成功")
            except Exception as e:
                logger.error(f"配置重载失败: {e}")
                raise

    def _reload_config_file(self, file_path: Path) -> None:
        if file_path.name == "config.json":
            self._main_config = self._loader.load_and_validate(
                MainConfig,
                file_path=file_path,
                env_prefix="",
            )
            return

        if file_path.name == "watch_config.json":
            watch_data = self._loader.load_from_file(file_path, default={})
            self._watch_config = WatchConfig(sources=watch_data)
            self._watch_config_revision += 1
            self._rebuild_monitored_sources()
            return

        if file_path.name == "webdav_config.json":
            self._webdav_config = self._loader.load_and_validate(
                WebDAVConfig,
                file_path=file_path,
                env_prefix="WEBDAV_",
            )
            return

        if file_path.name == "viewer_config.json":
            self._viewer_config = self._loader.load_and_validate(
                ViewerConfig,
                file_path=file_path,
                env_prefix="VIEWER_",
            )
