"""
Watch configuration data models

NOTE: This file now delegates to the new layered architecture.
      For new code, prefer using:
          from src.domain.entities import WatchTask, WatchConfig
"""

# Re-export from new architecture for backward compatibility
from src.domain.entities.watch import WatchTask, WatchConfig

__all__ = ["WatchTask", "WatchConfig"]
