"""
Message Worker Service
======================

Application-level orchestration helpers for the legacy message worker.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

from src.domain.magnet import MagnetLinkParser
from src.application.services.note_service import NoteService
from src.core.interfaces import BusinessMetricsProvider, ErrorTrackerProvider
from src.domain.entities.note import NoteCreate
from src.domain.entities.watch import WatchTask
from src.domain.services.filter_service import FilterService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RecordedNoteSaveRequest:
    user_id: str
    source_chat_id: str
    source_name: str
    content_to_save: Optional[str]
    media_type: Optional[str]
    media_path: Optional[str]
    media_paths: List[str]
    media_group_id: Optional[str]


class MessageWorkerService:
    """Own the business decisions behind worker message processing.

    可观测性协作者由组合根注入（`composition/container.py`）：
    - ``metrics_provider``：业务计数端口的惰性提供者
    - ``error_tracker_provider``：错误追踪端口的惰性提供者

    未装配时按 DEBUG 记一条并跳过——指标缺失不该影响消息处理，
    但也不能像原来那样吞掉全部异常后一声不响。
    """

    def __init__(
        self,
        note_service: NoteService,
        *,
        metrics_provider: Optional[BusinessMetricsProvider] = None,
        error_tracker_provider: Optional[ErrorTrackerProvider] = None,
    ) -> None:
        self._note_service = note_service
        self._metrics_provider = metrics_provider
        self._error_tracker_provider = error_tracker_provider

    @staticmethod
    def build_watch_task(
        *,
        source_chat_id: str,
        dest_chat_id: Optional[str],
        watch_data: Dict[str, Any],
    ) -> WatchTask:
        return WatchTask(
            source=str(source_chat_id),
            dest=dest_chat_id,
            whitelist=watch_data.get('whitelist', []),
            blacklist=watch_data.get('blacklist', []),
            whitelist_regex=watch_data.get('whitelist_regex', []),
            blacklist_regex=watch_data.get('blacklist_regex', []),
            preserve_forward_source=watch_data.get('preserve_forward_source', False),
            forward_mode=watch_data.get('forward_mode', 'full'),
            extract_patterns=watch_data.get('extract_patterns', []),
            record_mode=watch_data.get('record_mode', False),
        )

    @staticmethod
    def should_process(task: WatchTask, message_text: Optional[str]) -> bool:
        return FilterService.should_forward(task, message_text)

    def save_recorded_note(
        self,
        request: RecordedNoteSaveRequest | None = None,
        **legacy_fields: Any,
    ) -> int:
        request = _recorded_note_save_request(request, legacy_fields)
        note_dto = self._note_service.create_note(
            NoteCreate(
                user_id=int(request.user_id),
                source_chat_id=request.source_chat_id,
                source_name=request.source_name,
                message_text=request.content_to_save if request.content_to_save else None,
                media_type=request.media_type,
                media_path=request.media_path,
                media_paths=request.media_paths if request.media_paths else None,
                media_group_id=request.media_group_id,
            )
        )
        if request.content_to_save:
            magnet_link = MagnetLinkParser.extract_magnet_from_text(request.content_to_save)
            if magnet_link:
                self._note_service.update_magnet(note_dto.id, magnet_link, filename=None)
        return note_dto.id

    def _resolve_metrics(self) -> Optional[Any]:
        return _resolve_observability(self._metrics_provider, label="Business metrics")

    def _resolve_error_tracker(self) -> Optional[Any]:
        return _resolve_observability(self._error_tracker_provider, label="Error tracker")

    def record_note_saved(self, success: bool, has_media: bool, error_type: Optional[str] = None) -> None:
        metrics = self._resolve_metrics()
        if metrics is None:
            return
        try:
            metrics.record_note_saved(
                success=success,
                has_media=has_media,
                error_type=error_type,
            )
        except Exception:
            logger.warning("Failed to record note_saved metric", exc_info=True)

    def record_forward(self, success: bool, preserve_source: bool, error_type: Optional[str] = None) -> None:
        metrics = self._resolve_metrics()
        if metrics is None:
            return
        try:
            metrics.record_forward(
                success=success,
                preserve_source=preserve_source,
                error_type=error_type,
            )
        except Exception:
            logger.warning("Failed to record forward metric", exc_info=True)

    def track_processing_error(
        self,
        error: Exception,
        *,
        user_id: str,
        source_chat_id: str,
        watch_key: str,
    ) -> None:
        tracker = self._resolve_error_tracker()
        if tracker is None:
            return
        try:
            tracker.track_error(
                error=error,
                context={
                    'component': 'message_worker',
                    'stage': 'process_message',
                    'user_id': user_id,
                    'source_chat_id': source_chat_id,
                    'watch_key': watch_key,
                },
            )
        except Exception:
            logger.warning("Failed to track processing error", exc_info=True)


def _resolve_observability(provider: Optional[Any], *, label: str) -> Optional[Any]:
    """Resolve an observability provider; missing wiring is logged, not swallowed."""
    if provider is None:
        logger.debug("%s unavailable (provider not wired); metric dropped.", label)
        return None
    try:
        return provider()
    except Exception:
        logger.warning("%s provider failed; metric dropped.", label, exc_info=True)
        return None


def _recorded_note_save_request(
    request: RecordedNoteSaveRequest | None,
    legacy_fields: dict[str, Any],
) -> RecordedNoteSaveRequest:
    if request is not None:
        if legacy_fields:
            raise TypeError("save_recorded_note received both request object and legacy fields")
        return request
    return RecordedNoteSaveRequest(**legacy_fields)
