"""Duplicate detection helpers for SQLite notes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.core.constants import AppConstants
from src.core.utils.datetime_utils import db_cutoff


@dataclass(frozen=True)
class DuplicateCheckRequest:
    user_id: int
    source_chat_id: str
    message_text: Optional[str]
    media_group_id: Optional[str] = None


class SQLiteNoteDuplicateMixin:
    def check_duplicate(
        self,
        user_id: DuplicateCheckRequest | int,
        source_chat_id: Optional[str] = None,
        message_text: Optional[str] = None,
        *legacy_media_group_id: Optional[str],
        media_group_id: Optional[str] = None,
    ) -> bool:
        request = _duplicate_check_request(
            user_id,
            legacy_media_group_id,
            source_chat_id=source_chat_id,
            message_text=message_text,
            media_group_id=media_group_id,
        )
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            if self._has_media_group_duplicate(cursor, request):
                return True
            return self._has_message_duplicate(cursor, request)

    def find_duplicate_id(
        self,
        user_id: DuplicateCheckRequest | int,
        source_chat_id: Optional[str] = None,
        message_text: Optional[str] = None,
        *legacy_media_group_id: Optional[str],
        media_group_id: Optional[str] = None,
    ) -> Optional[int]:
        request = _duplicate_check_request(
            user_id,
            legacy_media_group_id,
            source_chat_id=source_chat_id,
            message_text=message_text,
            media_group_id=media_group_id,
        )
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            duplicate_id = self._find_media_group_duplicate_id(cursor, request)
            if duplicate_id is not None:
                return duplicate_id
            return self._find_message_duplicate_id(cursor, request)

    @staticmethod
    def _has_media_group_duplicate(cursor, request: DuplicateCheckRequest) -> bool:
        return SQLiteNoteDuplicateMixin._find_media_group_duplicate_id(
            cursor,
            request,
        ) is not None

    @staticmethod
    def _find_media_group_duplicate_id(cursor, request: DuplicateCheckRequest) -> Optional[int]:
        if not request.media_group_id:
            return None
        cursor.execute(
            """SELECT id FROM notes
               WHERE user_id = ? AND source_chat_id = ? AND media_group_id = ?
               LIMIT 1""",
            (request.user_id, request.source_chat_id, request.media_group_id),
        )
        row = cursor.fetchone()
        return int(row[0]) if row else None

    @staticmethod
    def _has_message_duplicate(cursor, request: DuplicateCheckRequest) -> bool:
        return SQLiteNoteDuplicateMixin._find_message_duplicate_id(
            cursor,
            request,
        ) is not None

    @staticmethod
    def _find_message_duplicate_id(cursor, request: DuplicateCheckRequest) -> Optional[int]:
        if not request.message_text:
            return None
        cursor.execute(
            """SELECT id FROM notes
               WHERE user_id = ? AND source_chat_id = ? AND message_text = ?
               AND datetime(timestamp) > datetime(?)
               LIMIT 1""",
            (
                request.user_id,
                request.source_chat_id,
                request.message_text,
                db_cutoff(AppConstants.Time.DB_DEDUP_WINDOW),
            ),
        )
        row = cursor.fetchone()
        return int(row[0]) if row else None


def _duplicate_check_request(
    request: DuplicateCheckRequest | int,
    legacy_media_group_id: tuple[Optional[str], ...],
    *,
    source_chat_id: Optional[str],
    message_text: Optional[str],
    media_group_id: Optional[str],
) -> DuplicateCheckRequest:
    if len(legacy_media_group_id) > 1:
        raise TypeError("duplicate check accepts at most one legacy media_group_id argument")
    if isinstance(request, DuplicateCheckRequest):
        if source_chat_id is not None or message_text is not None or legacy_media_group_id:
            raise TypeError("duplicate check received both request and legacy positional fields")
        if media_group_id is not None:
            raise TypeError("duplicate check received both request and legacy keyword fields")
        return request
    if legacy_media_group_id:
        if media_group_id is not None:
            raise TypeError("duplicate check received duplicate media_group_id values")
        media_group_id = legacy_media_group_id[0]
    if source_chat_id is None or message_text is None:
        raise TypeError("duplicate check requires source_chat_id and message_text")
    return DuplicateCheckRequest(request, source_chat_id, message_text, media_group_id)
