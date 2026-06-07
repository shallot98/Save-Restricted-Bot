"""
Settings Module
===============

Centralized configuration management with:
- Singleton pattern for global access
- Environment variable fallback
- JSON file persistence
- Thread-safe operations
- Pydantic-based configuration models
- Configuration validation
"""

import logging
import os
import threading
from typing import Any, Dict, Optional, Set, Callable

from .loader import ConfigLoader
from .models import MainConfig, WatchConfig, WebDAVConfig, ViewerConfig
from .settings_hot_reload import SettingsHotReloadMixin
from .settings_paths import PathConfig
from .settings_persistence import SettingsPersistenceMixin

logger = logging.getLogger(__name__)


class Settings(SettingsPersistenceMixin, SettingsHotReloadMixin):
    """
    Centralized settings management

    Implements Singleton pattern for global access.
    Thread-safe with read-write lock.
    """

    _instance: Optional['Settings'] = None
    _lock = threading.Lock()

    def __new__(cls) -> 'Settings':
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return

        self._rw_lock = threading.RLock()
        self._paths = PathConfig()
        self._paths.ensure_directories()

        # Configuration loader
        self._loader = ConfigLoader()

        # Configuration models (Pydantic instances)
        self._main_config: MainConfig = MainConfig()
        self._watch_config: WatchConfig = WatchConfig()
        self._watch_config_revision: int = 0
        self._webdav_config: WebDAVConfig = WebDAVConfig()
        self._viewer_config: ViewerConfig = ViewerConfig()

        # Monitored sources cache
        self._monitored_sources: Set[str] = set()
        self._sources_loader: Optional[Callable[[], Dict[str, Any]]] = None

        # Hot reload manager
        self._hot_reload_manager: Optional[HotReloadManager] = None

        # Load initial configurations
        self._load_all_configs()

        self._initialized = True

    @property
    def paths(self) -> PathConfig:
        """Get path configuration"""
        return self._paths

    # ==================== Main Config ====================

    def _load_all_configs(self) -> None:
        """Load all configuration files using ConfigLoader"""
        try:
            # Load main config (with environment variables)
            self._main_config = self._loader.load_and_validate(
                MainConfig,
                file_path=self._paths.config_file,
                env_prefix="",
                default_config={}
            )

            # Load watch config
            watch_data = self._loader.load_from_file(self._paths.watch_file, default={})
            self._watch_config = WatchConfig(sources=watch_data)
            self._watch_config_revision += 1

            # Load WebDAV config
            self._webdav_config = self._loader.load_and_validate(
                WebDAVConfig,
                file_path=self._paths.webdav_file,
                env_prefix="WEBDAV_",
                default_config=self._default_webdav_config()
            )

            # Load viewer config
            self._viewer_config = self._loader.load_and_validate(
                ViewerConfig,
                file_path=self._paths.viewer_file,
                env_prefix="VIEWER_",
                default_config=self._default_viewer_config()
            )

            self._rebuild_monitored_sources()
            logger.info("所有配置加载成功")
        except Exception as e:
            logger.error(f"配置加载失败: {e}")
            # 使用默认配置
            self._main_config = MainConfig()
            self._watch_config = WatchConfig()
            self._webdav_config = WebDAVConfig()
            self._viewer_config = ViewerConfig()

    # ==================== Config Access ====================

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value

        Priority:
        1. Config file value (from Pydantic model)
        2. Environment variable
        3. Default value
        """
        with self._rw_lock:
            # 尝试从Pydantic模型获取
            if hasattr(self._main_config, key):
                value = getattr(self._main_config, key)
                if value:  # 如果值不为空
                    return value

            # 尝试从环境变量获取
            env_value = os.environ.get(key)
            if env_value is not None:
                return env_value

            return default

    def set(self, key: str, value: Any) -> None:
        """Set configuration value and persist"""
        with self._rw_lock:
            # 更新Pydantic模型
            if hasattr(self._main_config, key):
                setattr(self._main_config, key, value)
                # 持久化到文件
                config_dict = self._main_config.model_dump()
                self._persist_config(self._paths.config_file, config_dict)
            else:
                logger.warning(f"配置键 '{key}' 不存在于MainConfig模型中")

    @property
    def main_config(self) -> Dict[str, Any]:
        """Get main configuration (read-only copy)"""
        with self._rw_lock:
            return self._main_config.model_dump()

    # ==================== Watch Config ====================

    @property
    def watch_config(self) -> Dict[str, Any]:
        """Get watch configuration (read-only copy)"""
        with self._rw_lock:
            return self._watch_config.sources.copy()

    @property
    def watch_config_revision(self) -> int:
        """Get watch configuration revision (monotonic increasing)."""
        with self._rw_lock:
            return self._watch_config_revision

    def save_watch_config(self, config: Dict[str, Any], auto_reload: bool = True) -> None:
        """Save watch configuration"""
        with self._rw_lock:
            logger.info(f"Saving watch config to: {self._paths.watch_file}")
            self._watch_config = WatchConfig(sources=config)
            self._watch_config_revision += 1
            self._persist_config(self._paths.watch_file, config)

            if auto_reload:
                self._rebuild_monitored_sources()

    def reload_watch_config(self) -> Dict[str, Any]:
        """Reload watch configuration from file"""
        with self._rw_lock:
            watch_data = self._loader.load_from_file(self._paths.watch_file, default={})
            self._watch_config = WatchConfig(sources=watch_data)
            self._watch_config_revision += 1
            self._rebuild_monitored_sources()
            return self._watch_config.sources.copy()

    # ==================== Monitored Sources ====================

    def _rebuild_monitored_sources(self) -> None:
        """Rebuild monitored sources set from watch config"""
        sources = self._watch_config.get_all_source_ids()
        self._monitored_sources = sources
        logger.debug(f"Rebuilt monitored sources: {len(sources)} sources")

    @property
    def monitored_sources(self) -> Set[str]:
        """Get monitored sources set (read-only copy)"""
        with self._rw_lock:
            return self._monitored_sources.copy()

    def reload_monitored_sources(self) -> Set[str]:
        """Reload monitored sources"""
        with self._rw_lock:
            self._rebuild_monitored_sources()
            return self._monitored_sources.copy()

    # ==================== WebDAV Config ====================

    @property
    def webdav_config(self) -> Dict[str, Any]:
        """Get WebDAV configuration (read-only copy)"""
        with self._rw_lock:
            return self._webdav_config.model_dump()

    def save_webdav_config(self, config: Dict[str, Any]) -> None:
        """Save WebDAV configuration"""
        with self._rw_lock:
            logger.info(f"Saving WebDAV config to: {self._paths.webdav_file}")
            self._webdav_config = WebDAVConfig(**config)
            self._persist_config(self._paths.webdav_file, config)

    # ==================== Viewer Config ====================

    @property
    def viewer_config(self) -> Dict[str, Any]:
        """Get viewer configuration (read-only copy)"""
        with self._rw_lock:
            return self._viewer_config.model_dump()

    def save_viewer_config(self, config: Dict[str, Any]) -> None:
        """Save viewer configuration"""
        with self._rw_lock:
            logger.info(f"Saving viewer config to: {self._paths.viewer_file}")
            self._viewer_config = ViewerConfig(**config)
            self._persist_config(self._paths.viewer_file, config)

# Global singleton instance
settings = Settings()
