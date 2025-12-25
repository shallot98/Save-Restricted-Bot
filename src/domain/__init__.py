"""
Domain Layer - Business Logic Core
===================================

Contains:
- entities/      Domain entities (Note, Watch, Calibration)
- value_objects/ Value objects (immutable domain concepts)
- services/      Domain services (business rules)
- repositories/  Repository interfaces
- events/        Domain events
"""

from src.domain.entities import Note, WatchTask, CalibrationTask

__all__ = ["Note", "WatchTask", "CalibrationTask"]
