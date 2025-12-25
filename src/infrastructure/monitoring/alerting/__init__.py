"""
告警系统

提供 AlertManager 以及多渠道告警发送能力（日志、Telegram）。
"""

from .alert_manager import AlertManager, get_alert_manager
from .channels import AlertChannel, LogChannel, TelegramChannel
from .rules import AlertRule, ThresholdRule, RateRule

__all__ = [
    "AlertManager",
    "get_alert_manager",
    "AlertChannel",
    "LogChannel",
    "TelegramChannel",
    "AlertRule",
    "ThresholdRule",
    "RateRule",
]

