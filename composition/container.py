"""
Service Container - 组合根装配
==============================

Dependency injection container for managing service instances.

本模块是唯一允许同时 import `src.infrastructure` 与 `src.application`
具体实现的地方（组合根语义，见 composition/__init__.py 的说明）。
原位置 `src/core/container.py` 会让最内层反向依赖外层，已于 Phase 2 迁出。
"""

import logging
from typing import Optional

from src.core.interfaces import (
    BusinessMetricsRecorder,
    CalibrationScheduler,
    CalibrationSchedulerProvider,
    ConfigCache,
    ErrorTracker,
    MediaStorage,
    MediaStorageProvider,
    NoteCache,
)
from src.infrastructure.cache.managers import (
    get_config_cache_manager,
    get_note_cache_manager,
)
from src.infrastructure.monitoring.errors.tracker import get_error_tracker
from src.infrastructure.monitoring.performance.business_metrics import (
    get_business_metrics,
)
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
    WatchSetupService,
    QBittorrentService,
    CalibrationWorkflowService,
    MessageWorkerService,
)

logger = logging.getLogger(__name__)


# ==================== Infrastructure providers ====================
#
# 这四个 provider 是「组合根装配基础设施实现」的全部内容。它们存在的理由是
# `src.application` 不再函数内 import `src.infrastructure`（报告 §5.2）：
# 服务只认识 `src.core.interfaces` 的端口，具体实现从这里传进去。
#
# 保持惰性（provider 而非实例）的原因：
#   - 缓存管理器构造会建统一缓存实例，服务未真正查询前不必发生；
#   - `get_business_metrics()` 会起一个后台上报线程，只在第一条指标时才该启动。


def _note_cache_provider() -> Optional[NoteCache]:
    """Resolve the note query cache implementation."""
    return get_note_cache_manager()


def _config_cache_provider() -> Optional[ConfigCache]:
    """Resolve the watch config cache implementation."""
    return get_config_cache_manager()


def _business_metrics_provider() -> Optional[BusinessMetricsRecorder]:
    """Resolve the business metrics collector (starts its reporter thread lazily)."""
    return get_business_metrics()


def _error_tracker_provider() -> Optional[ErrorTracker]:
    """Resolve the error tracker."""
    return get_error_tracker()


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
        self._watch_setup_service: Optional[WatchSetupService] = None
        self._qbittorrent_service: Optional[QBittorrentService] = None
        self._calibration_workflow_service: Optional[CalibrationWorkflowService] = None
        self._message_worker_service: Optional[MessageWorkerService] = None

        # 表现层实现的提供者（由 composition/wiring.py 在启动时注册）
        self._calibration_scheduler_provider: Optional[CalibrationSchedulerProvider] = None
        self._media_storage_provider: Optional[MediaStorageProvider] = None

        self._initialized = True
        logger.debug("ServiceContainer initialized")

    # ==================== Implementation wiring ====================

    def set_calibration_scheduler_provider(self, provider: CalibrationSchedulerProvider) -> None:
        """Register the concrete calibration scheduler provider (composition root only)."""
        self._calibration_scheduler_provider = provider

    def set_media_storage_provider(self, provider: MediaStorageProvider) -> None:
        """Register the concrete media storage provider (composition root only)."""
        self._media_storage_provider = provider

    def _resolve_calibration_scheduler(self) -> Optional[CalibrationScheduler]:
        """Late-bound lookup so wiring order never matters to built services."""
        if self._calibration_scheduler_provider is None:
            return None
        return self._calibration_scheduler_provider()

    def _resolve_media_storage(self) -> Optional[MediaStorage]:
        """Late-bound lookup so wiring order never matters to built services."""
        if self._media_storage_provider is None:
            return None
        return self._media_storage_provider()

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
            self._note_service = NoteService(
                self.note_repository,
                calibration_scheduler_provider=self._resolve_calibration_scheduler,
                media_storage_provider=self._resolve_media_storage,
                cache_provider=_note_cache_provider,
            )
        return self._note_service

    @property
    def watch_service(self) -> WatchService:
        """Get watch service instance"""
        if self._watch_service is None:
            self._watch_service = WatchService(
                self.watch_repository,
                cache_provider=_config_cache_provider,
            )
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

    @property
    def watch_setup_service(self) -> WatchSetupService:
        """Get watch setup orchestration service instance"""
        if self._watch_setup_service is None:
            self._watch_setup_service = WatchSetupService(self.watch_service)
        return self._watch_setup_service

    @property
    def qbittorrent_service(self) -> QBittorrentService:
        """Get qBittorrent orchestration service instance"""
        if self._qbittorrent_service is None:
            self._qbittorrent_service = QBittorrentService()
        return self._qbittorrent_service

    @property
    def calibration_workflow_service(self) -> CalibrationWorkflowService:
        """Get manual calibration workflow service instance"""
        if self._calibration_workflow_service is None:
            self._calibration_workflow_service = CalibrationWorkflowService(
                self.note_service,
                self.calibration_service,
                self._resolve_calibration_scheduler,
            )
        return self._calibration_workflow_service

    @property
    def message_worker_service(self) -> MessageWorkerService:
        """Get message worker orchestration helper instance"""
        if self._message_worker_service is None:
            self._message_worker_service = MessageWorkerService(
                self.note_service,
                metrics_provider=_business_metrics_provider,
                error_tracker_provider=_error_tracker_provider,
            )
        return self._message_worker_service

    # ==================== Lifecycle ====================

    def reset(self) -> None:
        """Reset all instances (useful for testing).

        注意：不清除实现提供者——它们是启动期一次性装配，不属于会话状态。
        """
        self._note_repository = None
        self._watch_repository = None
        self._calibration_repository = None
        self._calibration_config_repository = None
        self._note_service = None
        self._watch_service = None
        self._calibration_service = None
        self._watch_setup_service = None
        self._qbittorrent_service = None
        self._calibration_workflow_service = None
        self._message_worker_service = None
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


def get_watch_setup_service() -> WatchSetupService:
    """Get watch setup service from container"""
    return get_container().watch_setup_service


def get_qbittorrent_service() -> QBittorrentService:
    """Get qBittorrent service from container"""
    return get_container().qbittorrent_service


def get_calibration_workflow_service() -> CalibrationWorkflowService:
    """Get manual calibration workflow service from container"""
    return get_container().calibration_workflow_service


def get_message_worker_service() -> MessageWorkerService:
    """Get message worker helper service from container"""
    return get_container().message_worker_service
