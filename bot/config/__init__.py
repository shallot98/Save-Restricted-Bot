"""
配置模块
"""
from bot.config.constants import (
    AppConstants,
    DatabaseConstants,
    CalibrationConstants,
    MessageConstants,
    StorageConstants,
    LoggingConstants,
    # 向后兼容
    NOTES_PER_PAGE,
    DB_DEDUP_WINDOW,
    MESSAGE_FORWARD_DELAY,
)

__all__ = [
    'AppConstants',
    'DatabaseConstants',
    'CalibrationConstants',
    'MessageConstants',
    'StorageConstants',
    'LoggingConstants',
    'NOTES_PER_PAGE',
    'DB_DEDUP_WINDOW',
    'MESSAGE_FORWARD_DELAY',
]
