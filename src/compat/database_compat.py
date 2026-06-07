"""
Database Compatibility Layer
============================

Provides backward-compatible database functions that delegate to the new architecture.
"""

import sqlite3
import json
import logging
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from contextlib import contextmanager
from typing import Optional, Dict, Any, List

from database_note_requests import legacy_note_query
from database_notes import LegacyNoteQuery
from src.core.config import settings
from src.core.constants import AppConstants
from src.compat.database_media_cleanup import cleanup_media_files, collect_note_media_files

logger = logging.getLogger(__name__)

# China timezone
CHINA_TZ = ZoneInfo("Asia/Shanghai")

# Database path
DATABASE_FILE = str(settings.paths.data_dir / 'notes.db')
DATA_DIR = str(settings.paths.data_dir)


def init_database():
    """Initialize database - delegates to database module

    This is a compatibility wrapper that calls the original init_database
    from the database module.
    """
    from database import init_database as _init_database
    return _init_database()


@contextmanager
def get_db_connection():
    """Database connection context manager

    Yields:
        sqlite3.Connection: Database connection object

    Raises:
        sqlite3.Error: Database operation error
    """
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_FILE, timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            from src.infrastructure.monitoring.performance.db_tracer import get_db_tracer

            conn = get_db_tracer().enable(conn)
        except Exception as e:
            logger.debug("db_tracer 启用失败，已忽略: %s", e, exc_info=True)
        yield conn
        conn.commit()
    except sqlite3.OperationalError as e:
        if conn:
            conn.rollback()
        logger.error(f"Database operational error: {e}")
        raise
    except sqlite3.IntegrityError as e:
        if conn:
            conn.rollback()
        logger.error(f"Database integrity error: {e}")
        raise
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        logger.error(f"Database error: {e}")
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Unexpected error: {e}")
        raise
    finally:
        if conn:
            conn.close()


def _parse_media_paths(note: Dict[str, Any]) -> Dict[str, Any]:
    """Parse media paths from JSON string"""
    if note.get('media_paths'):
        try:
            note['media_paths'] = json.loads(note['media_paths'])
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Failed to parse media_paths: {e}")
            note['media_paths'] = []
    else:
        note['media_paths'] = []

    # Fallback: if media_paths is empty but media_path exists
    if not note['media_paths'] and note.get('media_path'):
        note['media_paths'] = [note['media_path']]

    return note


def get_notes(
    query: LegacyNoteQuery | Any = None,
    *legacy_args,
    **legacy_kwargs,
) -> List[Dict[str, Any]]:
    """Get notes list with filters"""
    query_options = legacy_note_query(query, legacy_args, legacy_kwargs)
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        where_clause, params = _notes_where_clause(query_options)
        sql = f'SELECT * FROM notes WHERE {where_clause} ORDER BY timestamp DESC LIMIT ? OFFSET ?'
        params.extend([query_options.limit, query_options.offset])

        cursor.execute(sql, params)
        notes = [_parse_media_paths(dict(row)) for row in cursor.fetchall()]
        return notes


def get_note_count(
    query: LegacyNoteQuery | Any = None,
    *legacy_args,
    **legacy_kwargs,
) -> int:
    """Get notes count with filters"""
    query_options = legacy_note_query(query, legacy_args, legacy_kwargs)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        where_clause, params = _notes_where_clause(query_options)
        sql = f'SELECT COUNT(*) FROM notes WHERE {where_clause}'

        cursor.execute(sql, params)
        return cursor.fetchone()[0]


def _notes_where_clause(query: LegacyNoteQuery) -> tuple[str, List[Any]]:
    conditions: List[str] = []
    params: List[Any] = []

    if query.user_id is not None:
        conditions.append('user_id = ?')
        params.append(query.user_id)
    if query.source_chat_id is not None:
        conditions.append('source_chat_id = ?')
        params.append(query.source_chat_id)
    if query.favorite_only:
        conditions.append('is_favorite = 1')
    if query.date_from:
        conditions.append("timestamp >= ?")
        params.append(f"{query.date_from} 00:00:00")
    if query.date_to:
        conditions.append("timestamp <= ?")
        params.append(f"{query.date_to} 23:59:59")
    if query.search_query:
        conditions.append('(message_text LIKE ? OR source_name LIKE ?)')
        search_pattern = f'%{query.search_query}%'
        params.extend([search_pattern, search_pattern])

    return ' AND '.join(conditions) if conditions else '1=1', params


def get_note_by_id(note_id: int) -> Optional[Dict[str, Any]]:
    """Get single note by ID"""
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM notes WHERE id = ?', (note_id,))
        row = cursor.fetchone()

        if row:
            return _parse_media_paths(dict(row))
        return None


def get_sources(user_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Get all unique sources"""
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = 'SELECT DISTINCT source_chat_id, source_name FROM notes WHERE 1=1'
        params = []

        if user_id:
            query += ' AND user_id = ?'
            params.append(user_id)

        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


def delete_note(note_id: int) -> bool:
    """Delete note by ID"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        media_files = collect_note_media_files(cursor, note_id)
        cursor.execute('DELETE FROM notes WHERE id = ?', (note_id,))
        affected = cursor.rowcount

    if media_files:
        cleanup_media_files(media_files, settings=settings, logger=logger)

    return affected > 0


def toggle_favorite(note_id: int) -> bool:
    """Toggle note favorite status"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE notes SET is_favorite = 1 - is_favorite WHERE id = ?', (note_id,))
        return cursor.rowcount > 0
