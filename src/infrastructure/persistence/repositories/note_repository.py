"""
SQLite Note Repository
======================

SQLite implementation of NoteRepository interface.
"""

import json
import logging
import re
import sqlite3
from datetime import datetime
from typing import Optional, List, Tuple, Any
from zoneinfo import ZoneInfo

from src.domain.entities.note import Note, NoteCreate, NoteFilter
from src.domain.repositories.note_repository import NoteRepository
from src.infrastructure.persistence.sqlite.connection import get_db_connection
from src.core.constants import AppConstants
from src.core.utils.datetime_utils import parse_db_datetime, format_db_datetime

logger = logging.getLogger(__name__)

CHINA_TZ = ZoneInfo("Asia/Shanghai")


class SQLiteNoteRepository(NoteRepository):
    """
    SQLite implementation of NoteRepository

    Provides CRUD operations for notes using SQLite database.
    """

    def get_by_id(self, note_id: int) -> Optional[Note]:
        """Get note by ID"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM notes WHERE id = ?', (note_id,))
            row = cursor.fetchone()

            if row:
                return self._row_to_note(dict(row))
            return None

    def get_by_user(
        self,
        user_id: int,
        limit: int = 50,
        offset: int = 0
    ) -> List[Note]:
        """Get notes for a user"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''SELECT * FROM notes
                   WHERE user_id = ?
                   ORDER BY timestamp DESC
                   LIMIT ? OFFSET ?''',
                (user_id, limit, offset)
            )
            return [self._row_to_note(dict(row)) for row in cursor.fetchall()]

    def search(self, filter_criteria: NoteFilter) -> Tuple[List[Note], int]:
        """Search notes with filter criteria"""
        with get_db_connection() as conn:
            cursor = conn.cursor()

            conditions, params = self._build_filter_conditions(filter_criteria, include_search=False)
            order_clause = "notes.timestamp DESC"
            fts_query: Optional[str] = None

            search_query = (filter_criteria.search_query or "").strip()
            if search_query:
                candidate_fts_query = self._build_fts_query(search_query)
                if candidate_fts_query and self._notes_fts_exists(cursor):
                    fts_query = candidate_fts_query
                    order_clause = "rank ASC, notes.timestamp DESC"
                else:
                    conditions.append("(notes.message_text LIKE ? OR notes.source_name LIKE ?)")
                    pattern = f"%{search_query}%"
                    params.extend([pattern, pattern])

            where_clause = " AND ".join(conditions) if conditions else "1=1"

            if fts_query:
                query = f"""SELECT notes.*, f.rank AS rank, COUNT(*) OVER() AS total_count
                FROM (
                    SELECT rowid AS note_id, bm25(notes_fts) AS rank
                    FROM notes_fts
                    WHERE notes_fts MATCH ?
                ) AS f
                JOIN notes ON notes.id = f.note_id
                WHERE {where_clause}
                ORDER BY {order_clause}
                LIMIT ? OFFSET ?"""
                query_params = [fts_query] + list(params) + [filter_criteria.limit, filter_criteria.offset]
            else:
                query = f"""SELECT notes.*, COUNT(*) OVER() AS total_count
                FROM notes
                WHERE {where_clause}
                ORDER BY {order_clause}
                LIMIT ? OFFSET ?"""
                query_params = list(params) + [filter_criteria.limit, filter_criteria.offset]

            cursor.execute(query, query_params)
            rows = cursor.fetchall()

            total_count = int(rows[0]['total_count']) if rows else 0
            notes = [self._row_to_note(dict(row)) for row in rows]

            return notes, total_count

    def create(self, note_data: NoteCreate) -> Note:
        """Create a new note"""
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Prepare media paths JSON
            media_paths_json = None
            if note_data.media_paths:
                media_paths_json = json.dumps(note_data.media_paths, ensure_ascii=False)

            timestamp = format_db_datetime(datetime.now(CHINA_TZ))

            cursor.execute('''
                INSERT INTO notes (
                    user_id, source_chat_id, source_name, message_text,
                    timestamp, media_type, media_path, media_paths, media_group_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                note_data.user_id,
                note_data.source_chat_id,
                note_data.source_name,
                note_data.message_text,
                timestamp,
                note_data.media_type,
                note_data.media_path,
                media_paths_json,
                note_data.media_group_id,
            ))

            note_id = cursor.lastrowid
            logger.info(f"Note created: id={note_id}")

            return self.get_by_id(note_id)

    def update(self, note: Note) -> Note:
        """Update existing note"""
        with get_db_connection() as conn:
            cursor = conn.cursor()

            media_paths_json = json.dumps(note.media_paths, ensure_ascii=False) if note.media_paths else None

            cursor.execute('''
                UPDATE notes SET
                    message_text = ?,
                    media_type = ?,
                    media_path = ?,
                    media_paths = ?,
                    magnet_link = ?,
                    filename = ?,
                    is_favorite = ?
                WHERE id = ?
            ''', (
                note.message_text,
                note.media_type,
                note.media_path,
                media_paths_json,
                note.magnet_link,
                note.filename,
                int(note.is_favorite),
                note.id,
            ))

            return self.get_by_id(note.id)

    def delete(self, note_id: int) -> bool:
        """Delete note by ID"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM notes WHERE id = ?', (note_id,))
            return cursor.rowcount > 0

    def update_magnet(
        self,
        note_id: int,
        magnet_link: str,
        filename: Optional[str] = None
    ) -> bool:
        """Update note's magnet link and filename"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE notes SET magnet_link = ?, filename = ? WHERE id = ?',
                (magnet_link, filename, note_id)
            )
            return cursor.rowcount > 0

    def toggle_favorite(self, note_id: int) -> bool:
        """Toggle note's favorite status"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE notes SET is_favorite = 1 - is_favorite WHERE id = ?',
                (note_id,)
            )
            if cursor.rowcount > 0:
                cursor.execute('SELECT is_favorite FROM notes WHERE id = ?', (note_id,))
                return bool(cursor.fetchone()[0])
            return False

    def get_sources(self, user_id: int) -> List[Tuple[str, str, int]]:
        """Get unique sources for a user"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT source_chat_id, source_name, COUNT(*) as count
                FROM notes
                WHERE user_id = ?
                GROUP BY source_chat_id, source_name
                ORDER BY count DESC
            ''', (user_id,))
            return [(row[0], row[1], row[2]) for row in cursor.fetchall()]

    def check_duplicate(
        self,
        user_id: int,
        source_chat_id: str,
        message_text: Optional[str],
        media_group_id: Optional[str] = None
    ) -> bool:
        """Check if note is a duplicate"""
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Check media group duplicate
            if media_group_id:
                cursor.execute(
                    '''SELECT 1 FROM notes
                       WHERE user_id = ? AND source_chat_id = ? AND media_group_id = ?
                       LIMIT 1''',
                    (user_id, source_chat_id, media_group_id)
                )
                if cursor.fetchone():
                    return True

            # Check message text duplicate within time window
            if message_text:
                cursor.execute('''
                    SELECT 1 FROM notes
                    WHERE user_id = ? AND source_chat_id = ? AND message_text = ?
                    AND datetime(timestamp) > datetime('now', ? || ' seconds')
                    LIMIT 1
                ''', (user_id, source_chat_id, message_text, f'-{AppConstants.Time.DB_DEDUP_WINDOW}'))
                if cursor.fetchone():
                    return True

            return False

    def _build_filter_conditions(
        self,
        filter_criteria: NoteFilter,
        include_search: bool = True,
    ) -> Tuple[List[str], List[Any]]:
        """Build SQL conditions from filter criteria"""
        conditions = []
        params = []

        if filter_criteria.user_id is not None:
            conditions.append('notes.user_id = ?')
            params.append(filter_criteria.user_id)

        if filter_criteria.source_chat_id is not None:
            conditions.append('notes.source_chat_id = ?')
            params.append(filter_criteria.source_chat_id)

        if filter_criteria.favorite_only:
            conditions.append('notes.is_favorite = 1')

        if filter_criteria.date_from:
            conditions.append('notes.timestamp >= ?')
            params.append(f'{filter_criteria.date_from} 00:00:00')

        if filter_criteria.date_to:
            conditions.append('notes.timestamp <= ?')
            params.append(f'{filter_criteria.date_to} 23:59:59')

        if include_search and filter_criteria.search_query:
            conditions.append('(notes.message_text LIKE ? OR notes.source_name LIKE ?)')
            pattern = f'%{filter_criteria.search_query}%'
            params.extend([pattern, pattern])

        return conditions, params

    @staticmethod
    def _notes_fts_exists(cursor: sqlite3.Cursor) -> bool:
        try:
            cursor.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='notes_fts' LIMIT 1"
            )
            return cursor.fetchone() is not None
        except Exception:
            return False

    @staticmethod
    def _build_fts_query(search_query: str) -> Optional[str]:
        """Build a safe FTS5 query string from user input.

        Goal:
        - Avoid user-supplied query syntax causing errors
        - Provide basic tokenization and AND semantics
        """
        tokens = re.findall(r"[0-9A-Za-z\u4e00-\u9fff]+", search_query)
        if not tokens:
            return None

        normalized: list[str] = []
        seen = set()
        for token in tokens:
            term = token.strip()
            if not term:
                continue
            key = term.lower()
            if key in seen:
                continue
            seen.add(key)
            normalized.append(term)

        if not normalized:
            return None

        terms = []
        for term in normalized:
            if len(term) >= 2:
                terms.append(f"{term}*")
            else:
                terms.append(term)

        # AND semantics: narrow results and keep query safe/deterministic.
        return " AND ".join(terms)

    def update_text(self, note_id: int, message_text: str) -> bool:
        """Update note's message text"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE notes SET message_text = ? WHERE id = ?',
                (message_text, note_id)
            )
            return cursor.rowcount > 0

    def get_all_sources(self) -> List[Tuple[str, Optional[str], int]]:
        """Get all unique sources across all users"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT source_chat_id, source_name, COUNT(*) as count
                FROM notes
                GROUP BY source_chat_id
                ORDER BY count DESC
            ''')
            return [(row[0], row[1], row[2]) for row in cursor.fetchall()]

    def _row_to_note(self, row: dict) -> Note:
        """Convert database row to Note entity"""
        # Parse media_paths JSON
        media_paths = []
        if row.get('media_paths'):
            try:
                media_paths = json.loads(row['media_paths'])
            except (json.JSONDecodeError, TypeError):
                pass

        # Fallback to single media_path
        if not media_paths and row.get('media_path'):
            media_paths = [row['media_path']]

        timestamp = parse_db_datetime(row.get("timestamp")) or datetime.now()

        return Note(
            id=row['id'],
            user_id=row['user_id'],
            source_chat_id=row['source_chat_id'],
            source_name=row.get('source_name'),
            message_text=row.get('message_text'),
            timestamp=timestamp,
            media_type=row.get('media_type'),
            media_path=row.get('media_path'),
            media_paths=media_paths,
            media_group_id=row.get('media_group_id'),
            magnet_link=row.get('magnet_link'),
            filename=row.get('filename'),
            is_favorite=bool(row.get('is_favorite', 0)),
        )
