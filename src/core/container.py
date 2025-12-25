"""
Service Container
==================

Dependency injection container for managing service instances.
"""

import logging
from typing import Optional

from src.infrastructure.persistence.repositories import (
    SQLiteNoteRepository,
    SQLiteWatchRepository,
    SQLiteCalibrationRepository,
    SQLiteCalibrationConfigRepository,
)
from src.application.services import (
    NoteService,
    WatchService,
    CalibrationService,
)

logger = logging.getLogger(__name__)


class ServiceContainer:
    """
    Service container for dependency injection

    Manages singleton instances of repositories and services.
    Provides lazy initialization for better startup performance.
    """

    _instance: Optional['ServiceContainer'] = None

    def __new__(cls) -> 'ServiceContainer':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return

        # Repository instances (lazy)
        self._note_repository: Optional[SQLiteNoteRepository] = None
        self._watch_repository: Optional[SQLiteWatchRepository] = None
        self._calibration_repository: Optional[SQLiteCalibrationRepository] = None
        self._calibration_config_repository: Optional[SQLiteCalibrationConfigRepository] = None

        # Service instances (lazy)
        self._note_service: Optional[NoteService] = None
        self._watch_service: Optional[WatchService] = None
        self._calibration_service: Optional[CalibrationService] = None

        self._initialized = True
        logger.debug("ServiceContainer initialized")

    # ==================== Repositories ====================

    @property
    def note_repository(self) -> SQLiteNoteRepository:
        """Get note repository instance"""
        if self._note_repository is None:
            self._note_repository = SQLiteNoteRepository()
        return self._note_repository

    @property
    def watch_repository(self) -> SQLiteWatchRepository:
        """Get watch repository instance"""
        if self._watch_repository is None:
            self._watch_repository = SQLiteWatchRepository()
        return self._watch_repository

    @property
    def calibration_repository(self) -> SQLiteCalibrationRepository:
        """Get calibration repository instance"""
        if self._calibration_repository is None:
            self._calibration_repository = SQLiteCalibrationRepository()
        return self._calibration_repository

    @property
    def calibration_config_repository(self) -> SQLiteCalibrationConfigRepository:
        """Get calibration config repository instance"""
        if self._calibration_config_repository is None:
            self._calibration_config_repository = SQLiteCalibrationConfigRepository()
        return self._calibration_config_repository

    # ==================== Services ====================

    @property
    def note_service(self) -> NoteService:
        """Get note service instance"""
        if self._note_service is None:
            self._note_service = NoteService(self.note_repository)
        return self._note_service

    @property
    def watch_service(self) -> WatchService:
        """Get watch service instance"""
        if self._watch_service is None:
            self._watch_service = WatchService(self.watch_repository)
        return self._watch_service

    @property
    def calibration_service(self) -> CalibrationService:
        """Get calibration service instance"""
        if self._calibration_service is None:
            self._calibration_service = CalibrationService(
                self.calibration_repository,
                self.calibration_config_repository
            )
        return self._calibration_service

    # ==================== Lifecycle ====================

    def reset(self) -> None:
        """Reset all instances (useful for testing)"""
        self._note_repository = None
        self._watch_repository = None
        self._calibration_repository = None
        self._calibration_config_repository = None
        self._note_service = None
        self._watch_service = None
        self._calibration_service = None
        logger.debug("ServiceContainer reset")


# Global container instance
_container: Optional[ServiceContainer] = None


def get_container() -> ServiceContainer:
    """
    Get the global service container instance

    Returns:
        ServiceContainer: Global container instance
    """
    global _container
    if _container is None:
        _container = ServiceContainer()
    return _container


# Convenience functions for direct service access
def get_note_service() -> NoteService:
    """Get note service from container"""
    return get_container().note_service


def get_watch_service() -> WatchService:
    """Get watch service from container"""
    return get_container().watch_service


def get_calibration_service() -> CalibrationService:
    """Get calibration service from container"""
    return get_container().calibration_service
