"""CRUD helpers for SQLite notes."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional, Tuple
from zoneinfo import ZoneInfo

from src.core.utils.datetime_utils import format_db_datetime
from src.domain.entities.note import Note, NoteCreate

logger = logging.getLogger(__name__)
CHINA_TZ = ZoneInfo("Asia/Shanghai")


class SQLiteNoteCrudMixin:
    def get_by_id(self, note_id: int) -> Optional[Note]:
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM notes WHERE id = ?", (note_id,))
            row = cursor.fetchone()
            return self._row_to_note(dict(row)) if row else None

    def get_by_user(self, user_id: int, limit: int = 50, offset: int = 0) -> List[Note]:
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT * FROM notes
                   WHERE user_id = ?
                   ORDER BY timestamp DESC
                   LIMIT ? OFFSET ?""",
                (user_id, limit, offset),
            )
            return [self._row_to_note(dict(row)) for row in cursor.fetchall()]

    def create(self, note_data: NoteCreate) -> Note:
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            self._insert_note(cursor, note_data)
            note_id = cursor.lastrowid
            logger.info(f"Note created: id={note_id}")
            return self._fetch_note_from_cursor(cursor, note_id)

    def _insert_note(self, cursor, note_data: NoteCreate) -> None:
        cursor.execute(
            """
            INSERT INTO notes (
                user_id, source_chat_id, source_name, message_text,
                timestamp, media_type, media_path, media_paths, media_group_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                note_data.user_id,
                note_data.source_chat_id,
                note_data.source_name,
                note_data.message_text,
                format_db_datetime(datetime.now(CHINA_TZ)),
                note_data.media_type,
                note_data.media_path,
                self._media_paths_json(note_data.media_paths),
                note_data.media_group_id,
            ),
        )

    def update(self, note: Note) -> Note:
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            self._update_note_row(cursor, note)
            return self._fetch_note_from_cursor(cursor, note.id)

    def _update_note_row(self, cursor, note: Note) -> None:
        cursor.execute(
            """
            UPDATE notes SET
                message_text = ?,
                media_type = ?,
                media_path = ?,
                media_paths = ?,
                magnet_link = ?,
                filename = ?,
                is_favorite = ?
            WHERE id = ?
            """,
            (
                note.message_text,
                note.media_type,
                note.media_path,
                self._media_paths_json(note.media_paths),
                note.magnet_link,
                note.filename,
                int(note.is_favorite),
                note.id,
            ),
        )

    def delete(self, note_id: int) -> bool:
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM notes WHERE id = ?", (note_id,))
            return cursor.rowcount > 0

    def update_magnet(self, note_id: int, magnet_link: str, filename: Optional[str] = None) -> bool:
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE notes SET magnet_link = ?, filename = ? WHERE id = ?",
                (magnet_link, filename, note_id),
            )
            return cursor.rowcount > 0

    def toggle_favorite(self, note_id: int) -> bool:
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE notes SET is_favorite = 1 - is_favorite WHERE id = ?", (note_id,))
            if cursor.rowcount <= 0:
                return False
            cursor.execute("SELECT is_favorite FROM notes WHERE id = ?", (note_id,))
            return bool(cursor.fetchone()[0])

    def update_text(self, note_id: int, message_text: str) -> bool:
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE notes SET message_text = ? WHERE id = ?", (message_text, note_id))
            return cursor.rowcount > 0

    def get_sources(self, user_id: int) -> List[Tuple[str, str, int]]:
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT source_chat_id, source_name, COUNT(*) as count
                FROM notes
                WHERE user_id = ?
                GROUP BY source_chat_id, source_name
                ORDER BY count DESC
                """,
                (user_id,),
            )
            return [(row[0], row[1], row[2]) for row in cursor.fetchall()]

    def get_all_sources(self) -> List[Tuple[str, Optional[str], int]]:
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT source_chat_id, source_name, COUNT(*) as count
                FROM notes
                GROUP BY source_chat_id
                ORDER BY count DESC
                """
            )
            return [(row[0], row[1], row[2]) for row in cursor.fetchall()]

    def _fetch_note_from_cursor(self, cursor, note_id: int) -> Note:
        cursor.execute("SELECT * FROM notes WHERE id = ?", (note_id,))
        row = cursor.fetchone()
        return self._row_to_note(dict(row)) if row else None
