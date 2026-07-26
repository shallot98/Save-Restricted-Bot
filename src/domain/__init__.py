"""
Domain Layer - Business Logic Core
===================================

Contains:
- entities/      Domain entities (Note, Watch, Calibration)
- magnet/        Magnet link parsing (pure domain logic)
- services/      Domain services (business rules)
- repositories/  Repository interfaces
- events/        Domain events
"""

from src.domain.entities import Note, WatchTask, CalibrationTask

__all__ = ["Note", "WatchTask", "CalibrationTask"]
