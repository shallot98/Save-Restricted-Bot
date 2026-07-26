"""Write-operation helpers for NoteService."""

from __future__ import annotations

import logging
import threading
from typing import Optional

from src.application.dto import NoteDTO
from src.core.exceptions import NotFoundError, ValidationError
from src.core.interfaces import CalibrationScheduler, CalibrationSchedulerProvider
from src.domain.entities.note import NoteCreate
from src.domain.magnet import MagnetLinkParser

logger = logging.getLogger(__name__)


class NoteServiceWritesMixin:
    # 由 NoteService.__init__ 注入（组合根装配），此处仅声明契约供类型检查使用。
    _calibration_scheduler_provider: Optional[CalibrationSchedulerProvider]

    def create_note(self, note_data: NoteCreate) -> NoteDTO:
        if self._repository.check_duplicate(
            user_id=note_data.user_id,
            source_chat_id=note_data.source_chat_id,
            message_text=note_data.message_text,
            media_group_id=note_data.media_group_id,
        ):
            raise ValidationError("Duplicate note detected")

        note = self._repository.create(note_data)
        logger.info(f"Note created: id={note.id}, user={note.user_id}")
        self._invalidate_note_caches(note.user_id)
        self._schedule_calibration_if_needed(note.id, note_data.message_text)
        return NoteDTO.from_entity(note)

    def _schedule_calibration_if_needed(self, note_id: Optional[int], message_text: Optional[str]) -> None:
        if not message_text or note_id is None:
            return
        try:
            if not _message_has_magnet(message_text):
                return
            manager = self._resolve_calibration_scheduler()
            if manager is None:
                return
            if manager.is_enabled():
                threading.Thread(
                    target=manager.add_note_to_calibration_queue,
                    args=(note_id,),
                    daemon=True,
                ).start()
                logger.debug(f"Calibration scheduled for note {note_id}")
        except Exception as exc:
            logger.error(f"Failed to schedule calibration for note {note_id}: {exc}")

    def delete_note(self, note_id: int) -> bool:
        note = self._require_note(note_id)
        if not self._repository.delete(note_id):
            self._raise_note_not_found(note_id)
        self._invalidate_note_caches(note.user_id)
        self._delete_note_media_best_effort(note)
        logger.info(f"Note deleted: id={note_id}")
        return True

    def toggle_favorite(self, note_id: int) -> bool:
        note = self._require_note(note_id)
        result = self._repository.toggle_favorite(note_id)
        self._invalidate_note_caches(note.user_id)
        return result

    def update_magnet(self, note_id: int, magnet_link: str, filename: Optional[str] = None) -> bool:
        if not magnet_link or not magnet_link.strip():
            raise ValidationError("Magnet link cannot be empty")
        if not self._repository.update_magnet(note_id, magnet_link, filename):
            self._raise_note_not_found(note_id)
        self._invalidate_note_caches()
        logger.info(f"Note magnet updated: id={note_id}")
        return True

    def apply_calibrated_magnet(self, note_id: int, new_magnet_link: str, filename: str) -> bool:
        if not hasattr(self._repository, "update_calibrated_magnet"):
            raise NotImplementedError("Repository does not support calibrated magnet updates")
        if not self._repository.update_calibrated_magnet(note_id, new_magnet_link, filename):
            self._raise_note_not_found(note_id)
        self._invalidate_note_caches()
        return True

    def apply_calibrated_magnets(self, note_id: int, calibrated_results: list[dict]) -> bool:
        if not hasattr(self._repository, "update_calibrated_magnets"):
            raise NotImplementedError("Repository does not support calibrated magnet updates")
        if not self._repository.update_calibrated_magnets(note_id, calibrated_results):
            self._raise_note_not_found(note_id)
        self._invalidate_note_caches()
        return True

    def update_text(self, note_id: int, message_text: str) -> bool:
        if not message_text or not message_text.strip():
            raise ValidationError("Message text cannot be empty")
        if not self._repository.update_text(note_id, message_text):
            self._raise_note_not_found(note_id)
        self._invalidate_note_caches()
        logger.info(f"Note text updated: id={note_id}")
        return True

    def _resolve_calibration_scheduler(self) -> Optional[CalibrationScheduler]:
        """Resolve the injected calibration scheduler; None means not wired."""
        scheduler = (
            self._calibration_scheduler_provider()
            if self._calibration_scheduler_provider is not None
            else None
        )
        if scheduler is None:
            logger.warning(
                "Calibration scheduler unavailable (composition root not wired); "
                "skipping calibration scheduling"
            )
        return scheduler

    @staticmethod
    def _raise_note_not_found(note_id: int) -> None:
        raise NotFoundError(
            f"Note not found: {note_id}",
            resource_type="Note",
            resource_id=note_id,
        )


def _message_has_magnet(message_text: str) -> bool:
    return bool(MagnetLinkParser.extract_all_magnets(message_text))
