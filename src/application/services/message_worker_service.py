"""
Message Worker Service
======================

Application-level orchestration helpers for the legacy message worker.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List, Dict, Any

from bot.utils.magnet_utils import MagnetLinkParser
from src.application.services.note_service import NoteService
from src.domain.entities.note import NoteCreate
from src.domain.entities.watch import WatchTask
from src.domain.services.filter_service import FilterService


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
    """Own the business decisions behind worker message processing."""

    def __init__(self, note_service: NoteService) -> None:
        self._note_service = note_service

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

    @staticmethod
    def record_note_saved(success: bool, has_media: bool, error_type: Optional[str] = None) -> None:
        try:
            from src.infrastructure.monitoring.performance.business_metrics import get_business_metrics

            get_business_metrics().record_note_saved(
                success=success,
                has_media=has_media,
                error_type=error_type,
            )
        except Exception:
            return

    @staticmethod
    def record_forward(success: bool, preserve_source: bool, error_type: Optional[str] = None) -> None:
        try:
            from src.infrastructure.monitoring.performance.business_metrics import get_business_metrics

            get_business_metrics().record_forward(
                success=success,
                preserve_source=preserve_source,
                error_type=error_type,
            )
        except Exception:
            return

    @staticmethod
    def track_processing_error(
        error: Exception,
        *,
        user_id: str,
        source_chat_id: str,
        watch_key: str,
    ) -> None:
        try:
            from src.infrastructure.monitoring.errors.tracker import get_error_tracker

            get_error_tracker().track_error(
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
            return


def _recorded_note_save_request(
    request: RecordedNoteSaveRequest | None,
    legacy_fields: dict[str, Any],
) -> RecordedNoteSaveRequest:
    if request is not None:
        if legacy_fields:
            raise TypeError("save_recorded_note received both request object and legacy fields")
        return request
    return RecordedNoteSaveRequest(**legacy_fields)
