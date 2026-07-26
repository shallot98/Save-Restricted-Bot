"""Calibrated magnet update helpers for SQLite notes."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

logger = logging.getLogger(__name__)
MAX_OPTIMISTIC_UPDATE_ATTEMPTS = 3


@dataclass(frozen=True)
class NoteTextFields:
    message_text: Optional[str]
    magnet_link: Optional[str]
    filename: Optional[str]


@dataclass(frozen=True)
class PersistCalibratedUpdateContext:
    cursor: object
    note_id: int
    original: NoteTextFields
    updated_fields: Tuple[Optional[str], Optional[str], Optional[str]]


class SQLiteNoteCalibrationMixin:
    def update_calibrated_magnet(self, note_id: int, new_magnet_link: str, filename: str) -> bool:
        def _build_update(row: NoteTextFields):
            return (
                self._replace_single_calibrated_magnet(row.message_text, new_magnet_link, filename),
                new_magnet_link,
                filename,
            )

        return self._update_note_text_fields_with_retry(note_id, _build_update)

    def update_calibrated_magnets(self, note_id: int, calibrated_results: List[Dict[str, Any]]) -> bool:
        def _build_update(row: NoteTextFields):
            updated_text = self._replace_multiple_calibrated_magnets(row.message_text, calibrated_results)
            new_magnet_link, new_filename = self._pick_primary_calibrated_link(
                row.magnet_link,
                row.filename,
                calibrated_results,
            )
            return updated_text, new_magnet_link, new_filename

        return self._update_note_text_fields_with_retry(note_id, _build_update)

    def _update_note_text_fields_with_retry(self, note_id: int, build_update) -> bool:
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            for attempt in range(1, MAX_OPTIMISTIC_UPDATE_ATTEMPTS + 1):
                row = self._load_note_text_fields(cursor, note_id)
                if row is None:
                    return False
                context = PersistCalibratedUpdateContext(cursor, note_id, row, build_update(row))
                if self._try_persist_calibrated_update(context):
                    return True
                logger.debug(f"更新笔记 {note_id} 发生并发冲突，重试 {attempt}/{MAX_OPTIMISTIC_UPDATE_ATTEMPTS}")
        logger.warning(f"⚠️ 更新笔记 {note_id} 失败：并发冲突超过最大重试次数")
        return False

    @staticmethod
    def _load_note_text_fields(cursor, note_id: int) -> Optional[NoteTextFields]:
        cursor.execute("SELECT message_text, magnet_link, filename FROM notes WHERE id = ?", (note_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return NoteTextFields(row[0], row[1], row[2])

    def _try_persist_calibrated_update(self, context: PersistCalibratedUpdateContext) -> bool:
        updated_text, new_magnet_link, new_filename = context.updated_fields
        context.cursor.execute(
            "UPDATE notes SET message_text = ?, magnet_link = ?, filename = ? "
            "WHERE id = ? AND message_text IS ? AND magnet_link IS ? AND filename IS ?",
            (
                updated_text,
                new_magnet_link,
                new_filename,
                context.note_id,
                context.original.message_text,
                context.original.magnet_link,
                context.original.filename,
            ),
        )
        return context.cursor.rowcount > 0

    def _replace_single_calibrated_magnet(
        self,
        message_text: Optional[str],
        new_magnet_link: str,
        filename: str,
    ) -> Optional[str]:
        if not message_text:
            return message_text
        regex = self._regex()
        info_hash_match = regex.search(r"xt=urn:btih:([a-zA-Z0-9]+)", new_magnet_link, regex.IGNORECASE)
        if not info_hash_match:
            return message_text
        info_hash = info_hash_match.group(1)
        text_magnet_base = regex.sub(r"[&?]dn=[^&]*", "", new_magnet_link)
        text_magnet = f"{text_magnet_base}&dn={filename}"
        magnet_pattern = rf"magnet:\?xt=urn:btih:{regex.escape(info_hash)}(?:[&?][^\n\r]*)?"
        return regex.sub(magnet_pattern, text_magnet, message_text, flags=regex.IGNORECASE)

    def _replace_multiple_calibrated_magnets(
        self,
        message_text: Optional[str],
        calibrated_results: List[Dict[str, Any]],
    ) -> Optional[str]:
        if not message_text:
            return message_text
        updated_text = message_text
        for result in calibrated_results:
            updated_text = self._replace_calibrated_result(updated_text, result)
        return updated_text

    def _replace_calibrated_result(self, message_text: str, result: Dict[str, Any]) -> str:
        if not result.get("success"):
            return message_text
        from src.domain.magnet import MagnetLinkParser

        regex = self._regex()
        info_hash = result["info_hash"]
        filename = MagnetLinkParser.clean_filename(result.get("filename", ""))
        new_magnet = f"magnet:?xt=urn:btih:{info_hash}&dn={filename}"
        magnet_pattern = rf"magnet:\?xt=urn:btih:\s*{regex.escape(info_hash)}[^\n#]*?(?=\s*(?:#|magnet:|$))"
        return regex.sub(magnet_pattern, new_magnet, message_text, flags=regex.IGNORECASE)

    def _pick_primary_calibrated_link(
        self,
        old_magnet_link: Optional[str],
        old_filename: Optional[str],
        calibrated_results: List[Dict[str, Any]],
    ) -> Tuple[Optional[str], Optional[str]]:
        for result in calibrated_results:
            if result.get("success"):
                return self._build_primary_calibrated_link(result)
        return old_magnet_link, old_filename

    def _build_primary_calibrated_link(self, result: Dict[str, Any]) -> Tuple[str, str]:
        from src.domain.magnet import MagnetLinkParser

        regex = self._regex()
        filename = MagnetLinkParser.clean_filename(result.get("filename", ""))
        old_magnet_for_db = result["old_magnet"]
        new_magnet_base = regex.sub(r"[&?]dn=[^&]*", "", old_magnet_for_db)
        encoded_filename = quote(filename) if filename else ""
        return f"{new_magnet_base}&dn={encoded_filename}", filename
