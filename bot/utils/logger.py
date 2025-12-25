"""
日志配置模块 - 统一管理项目日志

NOTE: This module now delegates to the new layered architecture.
      For new code, prefer using:
          from src.infrastructure.logging import setup_logging, get_logger
"""

# Re-export from new architecture
from src.infrastructure.logging import setup_logging, get_logger

__all__ = ["setup_logging", "get_logger"]
