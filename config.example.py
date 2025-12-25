"""
监控与告警配置示例

说明：
- 当前实现主要通过环境变量驱动（便于部署与热配置）。
- 该文件提供一个可拷贝的配置结构示例，便于团队统一口径。
"""

MONITORING_CONFIG = {
    # 性能监控
    "performance": {
        "enabled": True,
        "slow_operation_threshold_ms": 1000,
        "api_monitoring_enabled": True,
        "db_monitoring_enabled": True,
    },

    # 慢查询告警
    "slow_query": {
        "enabled": True,
        "threshold_ms": 100,
        "log_query": True,
        "alert_enabled": True,
    },

    # 错误追踪
    "error_tracking": {
        "enabled": True,
        "max_stacktrace_length": 2000,
        "aggregation_window_seconds": 300,
        "retention_seconds": 3600,
    },

    # 告警配置
    "alerting": {
        "enabled": True,
        "channels": ["log", "telegram"],
        "suppression_window_minutes": 5,
        "max_alerts_per_window": 10,
        "dedup_window_seconds": 60,
    },

    # 存储配置
    "storage": {
        "memory_retention_hours": 1,
        "db_retention_days": 30,
        "db_path": "data/monitoring.db",
    },
}

