"""
Configuration management module
Handles loading, saving, and accessing configuration files

NOTE: This file now delegates to the new layered architecture.
      For new code, prefer using:
          from src.core.config import settings
"""

import os
import json
import logging
import threading
from typing import Dict, Any, Set

logger = logging.getLogger(__name__)

# Import from new architecture via compatibility layer
from src.compat.config_compat import (
    DATA_DIR,
    CONFIG_DIR,
    MEDIA_DIR,
    CONFIG_FILE,
    WATCH_FILE,
    WEBDAV_CONFIG_FILE,
    VIEWER_CONFIG_FILE,
    load_config,
    getenv,
    getenv_optional,
    load_watch_config,
    save_watch_config,
    build_monitored_sources,
    reload_monitored_sources,
    get_monitored_sources,
    load_webdav_config,
    save_webdav_config,
    load_viewer_config,
    save_viewer_config,
)

# Re-export path constants as module-level variables for backward compatibility
DEFAULT_DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), 'data'))

# Ensure directories exist (handled by Settings, but keep for safety)
os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(MEDIA_DIR, exist_ok=True)

# Import monitored sources manager for backward compatibility
from bot.utils.sources_manager import (
    MonitoredSourcesManager,
    get_sources_manager,
    init_sources_manager
)

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
