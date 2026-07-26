"""
Common Interfaces Module
========================

Abstract base classes and protocols for dependency inversion.
"""

from src.core.interfaces.cache import (
    ConfigCache,
    ConfigCacheProvider,
    NoteCache,
    NoteCacheProvider,
)
from src.core.interfaces.calibration import (
    CalibrationScheduler,
    CalibrationSchedulerProvider,
)
from src.core.interfaces.metrics import (
    BusinessMetricsProvider,
    BusinessMetricsRecorder,
    ErrorTracker,
    ErrorTrackerProvider,
)
from src.core.interfaces.repository import Repository
from src.core.interfaces.service import Service
from src.core.interfaces.storage import (
    MediaStorage,
    MediaStorageProvider,
    StorageBackend,
)

__all__ = [
    "BusinessMetricsProvider",
    "BusinessMetricsRecorder",
    "CalibrationScheduler",
    "CalibrationSchedulerProvider",
    "ConfigCache",
    "ConfigCacheProvider",
    "ErrorTracker",
    "ErrorTrackerProvider",
    "MediaStorage",
    "MediaStorageProvider",
    "NoteCache",
    "NoteCacheProvider",
    "Repository",
    "Service",
    "StorageBackend",
]
