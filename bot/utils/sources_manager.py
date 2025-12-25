"""
监控源管理器

遵循 SOLID 原则：
- SRP: 仅负责监控源集合的管理
- OCP: 通过配置加载器扩展数据源
- DIP: 依赖抽象的配置加载接口

特性：
- 线程安全
- 自动同步配置文件
- 支持热重载
"""
import threading
import logging
from typing import Set, Callable, Optional, Dict, Any

logger = logging.getLogger(__name__)


class MonitoredSourcesManager:
    """线程安全的监控源管理器

    特性：
    - 线程安全的读写操作
    - 支持配置文件自动同步
    - 支持热重载

    Usage:
        manager = MonitoredSourcesManager(config_loader=load_watch_config)
        manager.reload()
        sources = manager.get_all()
        if manager.contains("-1001234567890"):
            ...
    """

    def __init__(self, config_loader: Optional[Callable[[], Dict[str, Any]]] = None):
        """初始化监控源管理器

        Args:
            config_loader: 配置加载函数，返回 watch_config 字典
        """
        self._sources: Set[str] = set()
        self._lock = threading.RLock()
        self._config_loader = config_loader

    def set_config_loader(self, loader: Callable[[], Dict[str, Any]]) -> None:
        """设置配置加载器

        Args:
            loader: 配置加载函数
        """
        self._config_loader = loader

    def reload(self) -> Set[str]:
        """从配置文件重新加载监控源

        Returns:
            Set[str]: 更新后的监控源集合
        """
        if self._config_loader is None:
            logger.warning("⚠️ 未设置配置加载器，无法重载监控源")
            return self.get_all()

        try:
            watch_config = self._config_loader()
            sources = self._build_sources_from_config(watch_config)

            with self._lock:
                self._sources = sources
                logger.info(f"🔄 监控源已更新: {self._sources if self._sources else '无'}")

            return sources.copy()

        except Exception as e:
            logger.error(f"❌ 重载监控源失败: {e}")
            return self.get_all()

    def _build_sources_from_config(self, watch_config: Dict[str, Any]) -> Set[str]:
        """从配置构建监控源集合

        Args:
            watch_config: 监控配置字典

        Returns:
            Set[str]: 监控源集合
        """
        sources = set()

        for user_id, watches in watch_config.items():
            for watch_key, watch_data in watches.items():
                if isinstance(watch_data, dict):
                    source = watch_data.get('source')
                else:
                    # 旧格式兼容：key 就是 source
                    source = watch_key

                # 添加有效的源（排除 None 和 "me"）
                if source and source != 'me':
                    sources.add(str(source))

        return sources

    def get_all(self) -> Set[str]:
        """获取所有监控源

        Returns:
            Set[str]: 监控源集合的副本
        """
        with self._lock:
            # 如果集合为空，尝试重新加载
            if not self._sources and self._config_loader:
                logger.warning("⚠️ 监控源集合为空，尝试重新加载...")
                # 释放锁后重载
                self._lock.release()
                try:
                    self.reload()
                finally:
                    self._lock.acquire()

            return self._sources.copy()

    def contains(self, source_id: str) -> bool:
        """检查是否包含指定监控源

        Args:
            source_id: 源 ID

        Returns:
            bool: 是否包含
        """
        with self._lock:
            return source_id in self._sources

    def add(self, source_id: str) -> None:
        """添加监控源

        Args:
            source_id: 源 ID
        """
        with self._lock:
            self._sources.add(str(source_id))

    def remove(self, source_id: str) -> bool:
        """移除监控源

        Args:
            source_id: 源 ID

        Returns:
            bool: 是否成功移除
        """
        with self._lock:
            if source_id in self._sources:
                self._sources.discard(source_id)
                return True
            return False

    def clear(self) -> None:
        """清空所有监控源"""
        with self._lock:
            self._sources.clear()

    def __contains__(self, source_id: str) -> bool:
        """支持 `in` 操作符"""
        return self.contains(source_id)

    def __len__(self) -> int:
        """支持 `len()` 函数"""
        with self._lock:
            return len(self._sources)

    def __iter__(self):
        """支持迭代"""
        return iter(self.get_all())

    def stats(self) -> Dict[str, Any]:
        """获取统计信息

        Returns:
            Dict: 统计信息
        """
        with self._lock:
            return {
                "total_sources": len(self._sources),
                "sources": list(self._sources)
            }


# 全局单例实例
_sources_manager: Optional[MonitoredSourcesManager] = None
_instance_lock = threading.Lock()


def get_sources_manager() -> MonitoredSourcesManager:
    """获取全局监控源管理器单例

    Returns:
        MonitoredSourcesManager: 监控源管理器实例
    """
    global _sources_manager
    if _sources_manager is None:
        with _instance_lock:
            if _sources_manager is None:
                _sources_manager = MonitoredSourcesManager()
    return _sources_manager


def init_sources_manager(config_loader: Callable[[], Dict[str, Any]]) -> MonitoredSourcesManager:
    """初始化全局监控源管理器

    Args:
        config_loader: 配置加载函数

    Returns:
        MonitoredSourcesManager: 初始化后的管理器实例
    """
    manager = get_sources_manager()
    manager.set_config_loader(config_loader)
    manager.reload()
    return manager
