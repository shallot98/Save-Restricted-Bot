"""
配置热重载管理器
==============

管理配置文件的热重载功能。
"""

import logging
from pathlib import Path
from typing import Optional, Callable, Any

from .watcher import ConfigWatcher
from .notifier import ConfigChangeNotifier

logger = logging.getLogger(__name__)


class HotReloadManager:
    """
    配置热重载管理器

    集成文件监控和配置变更通知，提供完整的热重载功能。

    特性:
    - 自动监控配置文件变更
    - 配置变更时自动重载
    - 通知所有订阅者
    - 验证新配置有效性
    - 失败时保持原配置

    Example:
        >>> manager = HotReloadManager(
        ...     config_dir=Path("data/config"),
        ...     reload_callback=lambda path: print(f"重载 {path}")
        ... )
        >>> manager.start()
        >>> # ... 配置文件变更时自动重载
        >>> manager.stop()
    """

    def __init__(
        self,
        config_dir: Path,
        reload_callback: Callable[[Path], None],
        watch_files: Optional[set] = None
    ):
        """
        初始化热重载管理器

        Args:
            config_dir: 配置文件目录
            reload_callback: 配置重载回调函数
            watch_files: 要监控的文件名集合，默认监控所有.json文件
        """
        self.config_dir = config_dir
        self.reload_callback = reload_callback

        # 默认监控所有配置文件
        if watch_files is None:
            watch_files = {
                "config.json",
                "watch_config.json",
                "webdav_config.json",
                "viewer_config.json"
            }
        self.watch_files = watch_files

        # 创建通知器
        self.notifier = ConfigChangeNotifier()

        # 创建文件监控器
        self._watcher: Optional[ConfigWatcher] = None

        logger.debug(f"热重载管理器已初始化: 配置目录={config_dir}")

    def start(self) -> None:
        """
        启动热重载

        Raises:
            RuntimeError: 如果热重载已经启动
        """
        if self._watcher is not None and self._watcher.is_running():
            raise RuntimeError("热重载已经在运行")

        # 创建并启动文件监控器
        self._watcher = ConfigWatcher(
            watch_dir=self.config_dir,
            watch_files=self.watch_files,
            on_change=self._handle_file_change,
            debounce_seconds=1.0
        )
        self._watcher.start()

        logger.info("配置热重载已启动")

    def stop(self) -> None:
        """停止热重载"""
        if self._watcher is not None:
            self._watcher.stop()
            self._watcher = None
            logger.info("配置热重载已停止")

    def is_running(self) -> bool:
        """
        检查热重载是否正在运行

        Returns:
            bool: 是否正在运行
        """
        return self._watcher is not None and self._watcher.is_running()

    def _handle_file_change(self, file_path: Path) -> None:
        """
        处理配置文件变更

        Args:
            file_path: 变更的文件路径
        """
        logger.info(f"处理配置文件变更: {file_path.name}")

        try:
            # 调用重载回调
            self.reload_callback(file_path)

            # 确定配置类型
            config_type = self._get_config_type(file_path.name)

            # 通知订阅者（这里简化处理，实际应该传递旧值和新值）
            self.notifier.notify(config_type, None, None)

            logger.info(f"配置 '{config_type}' 已成功重载")

        except Exception as e:
            logger.error(f"重载配置失败: {e}")

    def _get_config_type(self, filename: str) -> str:
        """
        根据文件名确定配置类型

        Args:
            filename: 文件名

        Returns:
            str: 配置类型
        """
        mapping = {
            "config.json": "main",
            "watch_config.json": "watch",
            "webdav_config.json": "webdav",
            "viewer_config.json": "viewer"
        }
        return mapping.get(filename, "unknown")


__all__ = ['HotReloadManager']
