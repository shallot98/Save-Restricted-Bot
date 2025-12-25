"""
Repository Interfaces
=====================

Abstract interfaces for data persistence.
Implementations are in the infrastructure layer.
"""

from src.domain.repositories.note_repository import NoteRepository
from src.domain.repositories.watch_repository import WatchRepository
from src.domain.repositories.calibration_repository import (
    CalibrationRepository,
    CalibrationConfigRepository,
)

__all__ = [
    "NoteRepository",
    "WatchRepository",
    "CalibrationRepository",
    "CalibrationConfigRepository",
]
