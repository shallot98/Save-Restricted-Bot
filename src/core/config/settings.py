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

import os
import json
import logging
import threading
import tempfile
import shutil
from pathlib import Path
from typing import Any, Dict, Optional, Set, Callable
from dataclasses import dataclass, field

from .loader import ConfigLoader
from .models import MainConfig, WatchConfig, WebDAVConfig, ViewerConfig
from .exceptions import ConfigLoadError, ConfigSaveError
from .hot_reload import HotReloadManager
from .notifier import ConfigChangeCallback

logger = logging.getLogger(__name__)


@dataclass
class PathConfig:
    """Path configuration for data directories"""

    base_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent.parent.parent)

    @property
    def data_dir(self) -> Path:
        """Data directory path"""
        env_dir = os.environ.get('DATA_DIR')
        if env_dir:
            return Path(env_dir)
        return self.base_dir / 'data'

    @property
    def config_dir(self) -> Path:
        """Configuration directory path"""
        return self.data_dir / 'config'

    @property
    def media_dir(self) -> Path:
        """Media storage directory path"""
        return self.data_dir / 'media'

    @property
    def config_file(self) -> Path:
        """Main config file path"""
        return self.config_dir / 'config.json'

    @property
    def watch_file(self) -> Path:
        """Watch config file path"""
        return self.config_dir / 'watch_config.json'

    @property
    def webdav_file(self) -> Path:
        """WebDAV config file path"""
        return self.config_dir / 'webdav_config.json'

    @property
    def viewer_file(self) -> Path:
        """Viewer config file path"""
        return self.config_dir / 'viewer_config.json'

    def ensure_directories(self) -> None:
        """Ensure all required directories exist"""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.media_dir.mkdir(parents=True, exist_ok=True)


class Settings:
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

    def _load_json_config(self, path: Path, default: Dict[str, Any]) -> Dict[str, Any]:
        """Load JSON configuration from file"""
        if path.exists():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to load config from {path}: {e}")

        # Save default config
        self._save_json_config(path, default)
        return default

    def _save_json_config(self, path: Path, config: Dict[str, Any]) -> None:
        """Save configuration to JSON file (legacy method)"""
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())

    def _persist_config(self, path: Path, config: Dict[str, Any]) -> None:
        """
        原子写入配置文件

        使用临时文件 + 重命名实现原子写入，确保配置文件不会损坏。

        Args:
            path: 配置文件路径
            config: 配置字典

        Raises:
            ConfigSaveError: 保存失败
        """
        try:
            # 确保目录存在
            path.parent.mkdir(parents=True, exist_ok=True)

            # 创建临时文件（在同一目录下，确保在同一文件系统）
            temp_fd, temp_path = tempfile.mkstemp(
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp"
            )

            try:
                # 写入临时文件
                with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=4, ensure_ascii=False)
                    f.flush()
                    os.fsync(f.fileno())

                # 如果原文件存在，创建备份
                if path.exists():
                    backup_path = path.with_suffix(path.suffix + '.bak')
                    shutil.copy2(path, backup_path)
                    logger.debug(f"配置文件已备份: {backup_path}")

                # 原子替换（在同一文件系统上，rename是原子操作）
                os.replace(temp_path, path)
                logger.debug(f"配置已保存: {path}")

            except Exception as e:
                # 清理临时文件
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                raise e

        except Exception as e:
            logger.error(f"配置持久化失败: {path}, 错误: {e}")
            raise ConfigSaveError(str(path), str(e))

    @staticmethod
    def _get_env_config() -> Dict[str, Any]:
        """Get configuration from environment variables"""
        config = {}
        for key in ["TOKEN", "HASH", "ID", "STRING", "OWNER_ID"]:
            value = os.environ.get(key)
            if value:
                config[key] = value
        return config

    @staticmethod
    def _default_webdav_config() -> Dict[str, Any]:
        """Default WebDAV configuration"""
        return {
            "enabled": False,
            "url": "",
            "username": "",
            "password": "",
            "base_path": "/telegram_media",
            "keep_local_copy": False
        }

    @staticmethod
    def _default_viewer_config() -> Dict[str, Any]:
        """Default viewer configuration"""
        return {
            "viewer_url": "https://example.com/watch?dn="
        }

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

    # ==================== Hot Reload ====================

    def enable_hot_reload(self) -> None:
        """
        启用配置热重载

        启动文件监控，当配置文件变更时自动重新加载。

        Example:
            >>> settings.enable_hot_reload()
            >>> # 配置文件变更时会自动重载
        """
        with self._rw_lock:
            if self._hot_reload_manager is not None and self._hot_reload_manager.is_running():
                logger.warning("热重载已经启用")
                return

            # 创建热重载管理器
            self._hot_reload_manager = HotReloadManager(
                config_dir=self._paths.config_dir,
                reload_callback=self._handle_config_reload
            )

            # 启动热重载
            self._hot_reload_manager.start()
            logger.info("配置热重载已启用")

    def disable_hot_reload(self) -> None:
        """
        禁用配置热重载

        停止文件监控。

        Example:
            >>> settings.disable_hot_reload()
        """
        with self._rw_lock:
            if self._hot_reload_manager is not None:
                self._hot_reload_manager.stop()
                self._hot_reload_manager = None
                logger.info("配置热重载已禁用")

    def subscribe(self, callback: ConfigChangeCallback) -> str:
        """
        订阅配置变更通知

        Args:
            callback: 回调函数，签名为 (config_type, old_value, new_value) -> None

        Returns:
            str: 订阅ID，用于取消订阅

        Example:
            >>> def on_config_change(config_type, old, new):
            ...     print(f"配置 {config_type} 已变更")
            >>> sub_id = settings.subscribe(on_config_change)
        """
        # 确保热重载管理器已创建
        if self._hot_reload_manager is None:
            self._hot_reload_manager = HotReloadManager(
                config_dir=self._paths.config_dir,
                reload_callback=self._handle_config_reload
            )

        return self._hot_reload_manager.notifier.subscribe(callback)

    def unsubscribe(self, subscription_id: str) -> bool:
        """
        取消订阅配置变更通知

        Args:
            subscription_id: 订阅ID（由subscribe方法返回）

        Returns:
            bool: 是否成功取消订阅

        Example:
            >>> settings.unsubscribe(sub_id)
            True
        """
        if self._hot_reload_manager is not None:
            return self._hot_reload_manager.notifier.unsubscribe(subscription_id)
        return False

    def _handle_config_reload(self, file_path: Path) -> None:
        """
        处理配置重载

        Args:
            file_path: 变更的配置文件路径
        """
        with self._rw_lock:
            logger.info(f"重新加载配置: {file_path.name}")

            try:
                # 根据文件名重新加载对应的配置
                if file_path.name == "config.json":
                    self._main_config = self._loader.load_and_validate(
                        MainConfig,
                        file_path=file_path,
                        env_prefix=""
                    )
                elif file_path.name == "watch_config.json":
                    watch_data = self._loader.load_from_file(file_path, default={})
                    self._watch_config = WatchConfig(sources=watch_data)
                    self._watch_config_revision += 1
                    self._rebuild_monitored_sources()
                elif file_path.name == "webdav_config.json":
                    self._webdav_config = self._loader.load_and_validate(
                        WebDAVConfig,
                        file_path=file_path,
                        env_prefix="WEBDAV_"
                    )
                elif file_path.name == "viewer_config.json":
                    self._viewer_config = self._loader.load_and_validate(
                        ViewerConfig,
                        file_path=file_path,
                        env_prefix="VIEWER_"
                    )

                logger.info(f"配置 {file_path.name} 重载成功")

            except Exception as e:
                logger.error(f"配置重载失败: {e}")
                raise


# Global singleton instance
settings = Settings()
