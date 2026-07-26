"""Note application service."""

from __future__ import annotations

from typing import Optional

from src.application.services.note_service_cache import NoteServiceCacheMixin
from src.application.services.note_service_media import NoteServiceMediaMixin
from src.application.services.note_service_query import NoteServiceQueryMixin
from src.application.services.note_service_sources import NoteServiceSourcesMixin
from src.application.services.note_service_writes import NoteServiceWritesMixin
from src.core.interfaces import (
    CalibrationSchedulerProvider,
    MediaStorage,
    MediaStorageProvider,
    NoteCache,
    NoteCacheProvider,
)
from src.domain.repositories.note_repository import NoteRepository


class NoteService(
    NoteServiceQueryMixin,
    NoteServiceWritesMixin,
    NoteServiceSourcesMixin,
    NoteServiceMediaMixin,
    NoteServiceCacheMixin,
):
    """Orchestrate note operations between presentation and domain layers.

    外部协作者一律由组合根注入（`composition/container.py` 装配基础设施侧，
    `composition/wiring.py` 装配表现层侧）：
    - ``calibration_scheduler_provider``：磁力校准排队端口的惰性提供者
    - ``media_storage_provider``：笔记媒体删除端口的惰性提供者
    - ``cache_provider``：笔记查询缓存端口的惰性提供者

    三者都是「提供者」而非实例，因为具体实现的构造会触碰数据库/配置，
    必须推迟到真正用到时才发生。未装配时服务显式记警告并降级，不静默失败。
    """

    def __init__(
        self,
        note_repository: NoteRepository,
        *,
        calibration_scheduler_provider: Optional[CalibrationSchedulerProvider] = None,
        media_storage_provider: Optional[MediaStorageProvider] = None,
        cache_provider: Optional[NoteCacheProvider] = None,
    ) -> None:
        self._repository = note_repository
        self._cache: Optional[NoteCache] = None
        self._cache_provider = cache_provider
        self._calibration_scheduler_provider = calibration_scheduler_provider
        self._media_storage_provider = media_storage_provider
        self._storage_manager: Optional[MediaStorage] = None
