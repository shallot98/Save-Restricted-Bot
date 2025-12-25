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

from src.core.config import settings
from src.core.constants import AppConstants

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
    user_id: Optional[int] = None,
    source_chat_id: Optional[str] = None,
    search_query: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    favorite_only: bool = False,
    limit: int = 50,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """Get notes list with filters"""
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        conditions: List[str] = []
        params: List[Any] = []

        if user_id is not None:
            conditions.append('user_id = ?')
            params.append(user_id)

        if source_chat_id is not None:
            conditions.append('source_chat_id = ?')
            params.append(source_chat_id)

        if favorite_only:
            conditions.append('is_favorite = 1')

        if date_from:
            conditions.append("timestamp >= ?")
            params.append(f"{date_from} 00:00:00")

        if date_to:
            conditions.append("timestamp <= ?")
            params.append(f"{date_to} 23:59:59")

        if search_query:
            conditions.append('(message_text LIKE ? OR source_name LIKE ?)')
            search_pattern = f'%{search_query}%'
            params.extend([search_pattern, search_pattern])

        where_clause = ' AND '.join(conditions) if conditions else '1=1'
        query = f'SELECT * FROM notes WHERE {where_clause} ORDER BY timestamp DESC LIMIT ? OFFSET ?'
        params.extend([limit, offset])

        cursor.execute(query, params)
        notes = [_parse_media_paths(dict(row)) for row in cursor.fetchall()]
        return notes


def get_note_count(
    user_id: Optional[int] = None,
    source_chat_id: Optional[str] = None,
    search_query: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    favorite_only: bool = False
) -> int:
    """Get notes count with filters"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        conditions: List[str] = []
        params: List[Any] = []

        if user_id is not None:
            conditions.append('user_id = ?')
            params.append(user_id)

        if source_chat_id is not None:
            conditions.append('source_chat_id = ?')
            params.append(source_chat_id)

        if favorite_only:
            conditions.append('is_favorite = 1')

        if date_from:
            conditions.append("timestamp >= ?")
            params.append(f"{date_from} 00:00:00")

        if date_to:
            conditions.append("timestamp <= ?")
            params.append(f"{date_to} 23:59:59")

        if search_query:
            conditions.append('(message_text LIKE ? OR source_name LIKE ?)')
            search_pattern = f'%{search_query}%'
            params.extend([search_pattern, search_pattern])

        where_clause = ' AND '.join(conditions) if conditions else '1=1'
        query = f'SELECT COUNT(*) FROM notes WHERE {where_clause}'

        cursor.execute(query, params)
        return cursor.fetchone()[0]


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

        # Get note info for media cleanup
        cursor.execute('SELECT media_path, media_paths FROM notes WHERE id = ?', (note_id,))
        result = cursor.fetchone()

        media_files = set()
        if result:
            single_path, media_paths_json = result
            if single_path:
                media_files.add(single_path)
            if media_paths_json:
                try:
                    media_files.update(path for path in json.loads(media_paths_json) if path)
                except (json.JSONDecodeError, TypeError):
                    pass

        # Delete database record
        cursor.execute('DELETE FROM notes WHERE id = ?', (note_id,))
        affected = cursor.rowcount

    if media_files:
        try:
            from bot.storage.webdav_client import StorageManager, WebDAVClient

            webdav_config = settings.webdav_config
            webdav_client = None

            if webdav_config.get("enabled", False):
                url = (webdav_config.get("url") or "").strip()
                username = (webdav_config.get("username") or "").strip()
                password = (webdav_config.get("password") or "").strip()
                base_path = webdav_config.get("base_path") or "/telegram_media"

                if url and username and password:
                    try:
                        webdav_client = WebDAVClient(url, username, password, base_path)
                    except Exception as e:
                        logger.warning(f"WebDAV storage init failed, fallback to local: {e}")

            storage_manager = StorageManager(str(settings.paths.media_dir), webdav_client)

            for media_path in media_files:
                try:
                    if not storage_manager.delete_file(media_path):
                        logger.warning(f"Failed to delete media file: {media_path}")
                except Exception as e:
                    logger.warning(f"Failed to delete media file: {media_path}, err={e}")
        except Exception as e:
            logger.warning(f"Failed to init storage manager for media cleanup: {e}")

    return affected > 0


def toggle_favorite(note_id: int) -> bool:
    """Toggle note favorite status"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE notes SET is_favorite = 1 - is_favorite WHERE id = ?', (note_id,))
        return cursor.rowcount > 0
