"""
配置文件监控器
==============

使用watchdog监控配置文件变更。
"""

import logging
import time
from pathlib import Path
from typing import Callable, Set, Optional
from watchdog.events import FileSystemEventHandler, FileSystemEvent
from watchdog.observers import Observer

logger = logging.getLogger(__name__)


class ConfigWatcher(FileSystemEventHandler):
    """
    配置文件监控器

    监控配置文件的变更，并在检测到变更时触发回调。

    特性:
    - 基于watchdog的文件系统监控
    - 防抖机制避免频繁触发
    - 只监控指定的配置文件
    - 线程安全

    Example:
        >>> def on_change(file_path):
        ...     print(f"配置文件 {file_path} 已变更")
        >>> watcher = ConfigWatcher(
        ...     watch_dir=Path("data/config"),
        ...     watch_files={"config.json", "watch_config.json"},
        ...     on_change=on_change
        ... )
        >>> watcher.start()
        >>> # ... 配置文件变更时会触发回调
        >>> watcher.stop()
    """

    def __init__(
        self,
        watch_dir: Path,
        watch_files: Set[str],
        on_change: Callable[[Path], None],
        debounce_seconds: float = 1.0
    ):
        """
        初始化配置文件监控器

        Args:
            watch_dir: 监控的目录路径
            watch_files: 要监控的文件名集合
            on_change: 文件变更时的回调函数
            debounce_seconds: 防抖时间（秒），默认1秒
        """
        super().__init__()
        self.watch_dir = watch_dir
        self.watch_files = watch_files
        self.on_change = on_change
        self.debounce_seconds = debounce_seconds

        # 防抖机制：记录每个文件的最后触发时间
        self._last_trigger_time: dict[str, float] = {}

        # Observer实例
        self._observer: Optional[Observer] = None

        logger.debug(f"配置监控器已初始化: 监控目录={watch_dir}, 文件={watch_files}")

    def on_modified(self, event: FileSystemEvent) -> None:
        """
        处理文件修改事件

        Args:
            event: 文件系统事件
        """
        # 忽略目录事件
        if event.is_directory:
            return

        # 获取文件路径
        file_path = Path(event.src_path)

        # 检查是否为监控的配置文件
        if file_path.name not in self.watch_files:
            return

        # 防抖：检查距离上次触发的时间
        current_time = time.time()
        last_time = self._last_trigger_time.get(file_path.name, 0)

        if current_time - last_time < self.debounce_seconds:
            logger.debug(f"防抖：忽略 {file_path.name} 的变更（距上次触发 {current_time - last_time:.2f}秒）")
            return

        # 更新最后触发时间
        self._last_trigger_time[file_path.name] = current_time

        # 触发回调
        logger.info(f"检测到配置文件变更: {file_path.name}")
        try:
            self.on_change(file_path)
        except Exception as e:
            logger.error(f"处理配置文件变更时出错: {e}")

    def start(self) -> None:
        """
        启动文件监控

        Raises:
            RuntimeError: 如果监控已经启动
        """
        if self._observer is not None and self._observer.is_alive():
            raise RuntimeError("配置监控器已经在运行")

        # 确保监控目录存在
        if not self.watch_dir.exists():
            logger.warning(f"监控目录不存在，创建目录: {self.watch_dir}")
            self.watch_dir.mkdir(parents=True, exist_ok=True)

        # 创建并启动Observer
        self._observer = Observer()
        self._observer.schedule(self, str(self.watch_dir), recursive=False)
        self._observer.start()

        logger.info(f"配置监控器已启动: 监控 {self.watch_dir}")

    def stop(self) -> None:
        """停止文件监控"""
        if self._observer is not None and self._observer.is_alive():
            self._observer.stop()
            self._observer.join(timeout=5)
            logger.info("配置监控器已停止")

    def is_running(self) -> bool:
        """
        检查监控器是否正在运行

        Returns:
            bool: 是否正在运行
        """
        return self._observer is not None and self._observer.is_alive()


__all__ = ['ConfigWatcher']
