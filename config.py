"""
Configuration Facade - 旧版配置 API 的兼容外观，计划 Phase 4 删除

Phase 3 收尾时删除了 ``src/compat/``，本模块因此从「三跳转接」
（``config.py`` → ``src.compat.config_compat`` → ``src.core.config`` / 组合根）
收敛为两跳：实现要么在 ``src.core.config``（路径常量、取值 helper、webdav /
viewer 配置），要么在 ``WatchService``（watch 配置族）。

**watch 配置族为什么留在这里而不是搬进 src/**：这 5 个函数都要经组合根
``composition.container.get_watch_service()`` 拿服务实例。放在 ``src/`` 里就是
``src → composition`` 的反向边（import-linter 契约 2），此前正是靠一条逐条豁免
硬撑着。搬到仓库根后这条边消失——根模块本就位于组合根之上、不入契约，是遗留
外观的正确归属。豁免已随之删除（见 ``.importlinter``）。

新代码请直接用权威源：
    from src.core.config import settings, getenv, getenv_optional
    from composition.container import get_watch_service
"""

import logging
import os
from typing import Any, Dict, Set

from src.core.config import getenv, getenv_optional, settings

logger = logging.getLogger(__name__)


# ==================== 路径常量 ====================
# 快照语义：import 时求值一次。settings.paths.* 每次访问都重读 DATA_DIR 环境变量，
# 而旧调用方（如 media_cleanup 的默认参数）依赖「进程内恒定」，故此处固化。
DATA_DIR = str(settings.paths.data_dir)
CONFIG_DIR = str(settings.paths.config_dir)
MEDIA_DIR = str(settings.paths.media_dir)
CONFIG_FILE = str(settings.paths.config_file)
WATCH_FILE = str(settings.paths.watch_file)
WEBDAV_CONFIG_FILE = str(settings.paths.webdav_file)
VIEWER_CONFIG_FILE = str(settings.paths.viewer_file)

DEFAULT_DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), 'data'))

# 目录兜底（Settings 也会建，保留以防调用方绕过 Settings 直接用常量）
os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(MEDIA_DIR, exist_ok=True)

# Import monitored sources manager for backward compatibility
from bot.utils.sources_manager import (
    MonitoredSourcesManager,
    get_sources_manager,
    init_sources_manager
)


# ==================== 主配置 ====================

def load_config() -> Dict[str, Any]:
    """加载主配置（委托 Settings）。"""
    return settings.main_config


# ==================== watch 配置族（经组合根） ====================

def load_watch_config() -> Dict[str, Any]:
    """读取 watch 配置字典。"""
    from composition.container import get_watch_service

    return get_watch_service().get_all_configs_dict()


def save_watch_config(config: Dict[str, Any], auto_reload: bool = True) -> None:
    """保存 watch 配置，并按需重建监控源集合。

    Args:
        config: 待保存的配置字典。
        auto_reload: 为 True 时保存后立即 reload + 失效缓存。
    """
    from composition.container import get_watch_service

    get_watch_service().save_config_dict(config)
    if auto_reload:
        get_watch_service().reload_config()
        get_watch_service().invalidate_cache()


def build_monitored_sources() -> Set[str]:
    """构建被监控的 source chat id 集合。"""
    from composition.container import get_watch_service

    return get_watch_service().get_monitored_sources()


def reload_monitored_sources() -> None:
    """配置变更后重建监控源集合。"""
    from composition.container import get_watch_service

    get_watch_service().reload_config()
    get_watch_service().invalidate_cache()


def get_monitored_sources() -> Set[str]:
    """获取当前监控源集合。"""
    from composition.container import get_watch_service

    return get_watch_service().get_monitored_sources()


# ==================== WebDAV / 前台展示配置 ====================

def load_webdav_config() -> Dict[str, Any]:
    """加载 WebDAV 配置（委托 Settings）。"""
    return settings.webdav_config


def save_webdav_config(config: Dict[str, Any]) -> None:
    """保存 WebDAV 配置（委托 Settings）。"""
    settings.save_webdav_config(config)


def load_viewer_config() -> Dict[str, Any]:
    """加载前台展示配置（委托 Settings）。"""
    return settings.viewer_config


def save_viewer_config(config: Dict[str, Any]) -> None:
    """保存前台展示配置（委托 Settings）。"""
    settings.save_viewer_config(config)


def _env_bool(key: str, default: bool) -> bool:
    value = os.environ.get(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(key: str, default: int) -> int:
    value = os.environ.get(key)
    if value is None:
        return default
    try:
        return int(value.strip())
    except ValueError:
        return default


# Monitoring configuration (example/defaults).
# NOTE: Current monitoring implementation is primarily env-driven; this dict is provided for
#       documentation/consistency and optional app-side wiring.
MONITORING_CONFIG = {
    # 性能监控
    "performance": {
        "enabled": _env_bool("MONITORING_ENABLED", True),
        "slow_operation_threshold_ms": _env_int("SLOW_OPERATION_THRESHOLD_MS", 1000),
        "api_monitoring_enabled": _env_bool("MONITORING_ENABLED", True),
        "db_monitoring_enabled": _env_bool("DB_MONITORING_ENABLED", True),
    },

    # 慢查询告警
    "slow_query": {
        "enabled": _env_bool("DB_MONITORING_ENABLED", True),
        "threshold_ms": _env_int("SLOW_QUERY_THRESHOLD_MS", 100),
        "log_query": _env_bool("SLOW_QUERY_LOG_QUERY", True),
        "alert_enabled": _env_bool("SLOW_QUERY_ALERT_ENABLED", True),
    },

    # 错误追踪
    "error_tracking": {
        "enabled": _env_bool("ERROR_TRACKING_ENABLED", True),
        "max_stacktrace_length": _env_int("ERROR_MAX_STACKTRACE_LENGTH", 2000),
        "aggregation_window_seconds": _env_int("ERROR_AGGREGATION_WINDOW_SECONDS", 300),
        "retention_seconds": _env_int("ERROR_RETENTION_SECONDS", 3600),
    },

    # 告警配置
    "alerting": {
        "enabled": _env_bool("ALERTING_ENABLED", True),
        "channels": ["log", "telegram"],
        "suppression_window_minutes": _env_int("ALERT_SUPPRESSION_WINDOW_MINUTES", 5),
        "max_alerts_per_window": _env_int("ALERT_MAX_ALERTS_PER_WINDOW", 10),
        "dedup_window_seconds": _env_int("ALERT_DEDUP_WINDOW_SECONDS", 60),
    },

    # 存储配置
    "storage": {
        "memory_retention_hours": _env_int("MONITORING_MEMORY_RETENTION_HOURS", 1),
        "db_retention_days": _env_int("MONITORING_DB_RETENTION_DAYS", 30),
        "db_path": "data/monitoring.db",
    },
}

__all__ = [
    # Path constants
    "DEFAULT_DATA_DIR",
    "DATA_DIR",
    "CONFIG_DIR",
    "MEDIA_DIR",
    "CONFIG_FILE",
    "WATCH_FILE",
    "WEBDAV_CONFIG_FILE",
    "VIEWER_CONFIG_FILE",
    # Config functions
    "load_config",
    "getenv",
    "getenv_optional",
    "load_watch_config",
    "save_watch_config",
    "build_monitored_sources",
    "reload_monitored_sources",
    "get_monitored_sources",
    "load_webdav_config",
    "save_webdav_config",
    "load_viewer_config",
    "save_viewer_config",
    # Sources manager
    "MonitoredSourcesManager",
    "get_sources_manager",
    "init_sources_manager",
    # Monitoring config
    "MONITORING_CONFIG",
]
