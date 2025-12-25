"""
Database Module - Backward Compatible Interface

This module provides backward-compatible database functions
that delegate to the new layered architecture.

For new code, prefer using:
    from src.infrastructure.persistence.repositories import SQLiteNoteRepository
    from src.domain.entities import Note, NoteCreate
"""

import sqlite3
import bcrypt
import json
import os
import re
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from contextlib import contextmanager
from typing import Optional, Dict, Any, List

# Import from new architecture
from src.core.config import settings
from src.core.constants import AppConstants
from src.core.utils.datetime_utils import format_db_datetime
from src.infrastructure.persistence.sqlite.connection import get_db_connection
from src.infrastructure.persistence.sqlite.migrations import run_migrations

logger = logging.getLogger(__name__)

# China timezone
CHINA_TZ = ZoneInfo("Asia/Shanghai")

# Path constants for backward compatibility
DATA_DIR = str(settings.paths.data_dir)
DATABASE_FILE = str(settings.paths.data_dir / 'notes.db')


def init_database() -> None:
    """Initialize database - delegates to new architecture"""
    print("=" * 50)
    print("🔧 正在初始化数据库...")
    print(f"📁 数据目录: {DATA_DIR}")
    print(f"💾 数据库路径: {DATABASE_FILE}")

    run_migrations()

    print("✅ 数据库初始化完成！")
    print("=" * 50)


def _parse_media_paths(note: Dict[str, Any]) -> Dict[str, Any]:
    """Parse media paths from JSON string"""
    if note.get('media_paths'):
        try:
            note['media_paths'] = json.loads(note['media_paths'])
        except (json.JSONDecodeError, TypeError):
            note['media_paths'] = []
    else:
        note['media_paths'] = []

    if not note['media_paths'] and note.get('media_path'):
        note['media_paths'] = [note['media_path']]

    return note


def add_note(
    user_id: Any,
    source_chat_id: Any,
    source_name: Optional[str],
    message_text: Optional[str],
    media_type: Optional[str] = None,
    media_path: Optional[str] = None,
    media_paths: Optional[List[str]] = None,
    media_group_id: Optional[str] = None
) -> int:
    """Add a note record"""
    from bot.utils.magnet_utils import MagnetLinkParser

    # Validate parameters
    if user_id is None:
        raise ValueError("user_id cannot be None")
    if source_chat_id is None:
        raise ValueError("source_chat_id cannot be None")

    user_id = int(user_id)
    source_chat_id = str(source_chat_id)

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Check duplicates
        if media_group_id:
            cursor.execute(
                "SELECT id FROM notes WHERE user_id=? AND source_chat_id=? AND media_group_id=? LIMIT 1",
                (user_id, source_chat_id, media_group_id)
            )
            existing = cursor.fetchone()
            if existing:
                return existing[0]

        if message_text and not media_group_id:
            cursor.execute("""
                SELECT id FROM notes
                WHERE user_id=? AND source_chat_id=? AND message_text=?
                AND datetime(timestamp) > datetime('now', ? || ' seconds')
                LIMIT 1
            """, (user_id, source_chat_id, message_text, f'-{AppConstants.Time.DB_DEDUP_WINDOW}'))
            existing = cursor.fetchone()
            if existing:
                return existing[0]

        # Prepare data
        media_paths_json = None
        if media_paths:
            if media_path is None:
                media_path = media_paths[0]
            media_paths_json = json.dumps(media_paths, ensure_ascii=False)

        # Extract magnet link
        magnet_link = MagnetLinkParser.extract_magnet_from_text(message_text) if message_text else None

        # 只有在磁力链接没有dn参数时才提取filename（避免保存错误的dn参数）
        # 如果磁力链接已有dn参数，说明不需要校准，filename保持为None
        filename = None
        if magnet_link:
            from urllib.parse import parse_qs, urlparse
            try:
                parsed = urlparse(magnet_link)
                params = parse_qs(parsed.query)
                # 如果没有dn参数，才尝试从其他地方提取filename
                if not params.get('dn'):
                    # 可以从message_text的开头提取，或者保持为None让校准系统处理
                    pass  # 保持filename=None，让校准系统处理
            except Exception:
                pass

        # Insert record
        china_timestamp = format_db_datetime(datetime.now(CHINA_TZ))
        cursor.execute('''
            INSERT INTO notes (user_id, source_chat_id, source_name, message_text, timestamp,
                              media_type, media_path, media_paths, media_group_id, magnet_link, filename)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, source_chat_id, source_name, message_text, china_timestamp,
              media_type, media_path, media_paths_json, media_group_id, magnet_link, filename))

        note_id = cursor.lastrowid
        logger.info(f"✅ Note saved: id={note_id}")

    # Schedule calibration if needed
    _schedule_calibration_if_needed(note_id, message_text, magnet_link)

    return note_id


def _schedule_calibration_if_needed(note_id: int, message_text: Optional[str], magnet_link: Optional[str]) -> None:
    """Schedule calibration if magnet link present"""
    from bot.utils.magnet_utils import MagnetLinkParser

    has_magnet = bool(magnet_link) or bool(message_text and MagnetLinkParser.extract_all_magnets(message_text))

    if not has_magnet:
        return

    try:
        from bot.services.calibration_manager import get_calibration_manager
        import threading

        manager = get_calibration_manager()
        if manager.is_enabled():
            threading.Thread(
                target=manager.add_note_to_calibration_queue,
                args=(note_id,),
                daemon=True
            ).start()
    except Exception as e:
        logger.error(f"Failed to schedule calibration: {e}")


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
    """Get notes list"""
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
            pattern = f'%{search_query}%'
            params.extend([pattern, pattern])

        where_clause = ' AND '.join(conditions) if conditions else '1=1'
        query = f'SELECT * FROM notes WHERE {where_clause} ORDER BY timestamp DESC LIMIT ? OFFSET ?'
        params.extend([limit, offset])

        cursor.execute(query, params)
        return [_parse_media_paths(dict(row)) for row in cursor.fetchall()]


def get_note_count(
    user_id: Optional[int] = None,
    source_chat_id: Optional[str] = None,
    search_query: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    favorite_only: bool = False
) -> int:
    """Get notes count"""
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
            pattern = f'%{search_query}%'
            params.extend([pattern, pattern])

        where_clause = ' AND '.join(conditions) if conditions else '1=1'
        cursor.execute(f'SELECT COUNT(*) FROM notes WHERE {where_clause}', params)
        return cursor.fetchone()[0]


def get_sources(user_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Get all sources"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        query = 'SELECT DISTINCT source_chat_id, source_name FROM notes WHERE 1=1'
        params = []

        if user_id:
            query += ' AND user_id = ?'
            params.append(user_id)

        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


def get_note_by_id(note_id: int) -> Optional[Dict[str, Any]]:
    """Get note by ID"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM notes WHERE id = ?', (note_id,))
        row = cursor.fetchone()
        if row:
            return _parse_media_paths(dict(row))
        return None


def update_note(note_id: int, message_text: str) -> bool:
    """Update note content"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE notes SET message_text = ? WHERE id = ?', (message_text, note_id))
        return cursor.rowcount > 0


def update_magnet_link(note_id: int, magnet_link: str) -> bool:
    """Update magnet link"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE notes SET magnet_link = ? WHERE id = ?', (magnet_link, note_id))
        return cursor.rowcount > 0


def delete_note(note_id: int) -> bool:
    """Delete note"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

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
                        logger.warning(f"Failed to delete media: {media_path}")
                except Exception as e:
                    logger.warning(f"Failed to delete media: {media_path}, err={e}")
        except Exception as e:
            logger.warning(f"Failed to init storage manager for media cleanup: {e}")

    return affected > 0


def toggle_favorite(note_id: int) -> bool:
    """Toggle favorite status"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE notes SET is_favorite = 1 - is_favorite WHERE id = ?', (note_id,))
        return cursor.rowcount > 0


def verify_user(username: str, password: str) -> bool:
    """Verify user login"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT password_hash FROM users WHERE username = ?', (username,))
        result = cursor.fetchone()

        if result:
            return bcrypt.checkpw(password.encode('utf-8'), result[0].encode('utf-8'))
        return False


def update_password(username: str, new_password: str) -> None:
    """Update user password"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        cursor.execute('UPDATE users SET password_hash = ? WHERE username = ?', (password_hash, username))


# ==================== Calibration Functions ====================

def get_calibration_config() -> Optional[Dict[str, Any]]:
    """Get calibration config"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM auto_calibration_config WHERE id = 1')
        row = cursor.fetchone()
        return dict(row) if row else None


def update_calibration_config(config: Dict[str, Any]) -> bool:
    """Update calibration config"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE auto_calibration_config
            SET enabled = ?, filter_mode = ?, first_delay = ?,
                retry_delay_1 = ?, retry_delay_2 = ?, retry_delay_3 = ?,
                max_retries = ?, concurrent_limit = ?,
                timeout_per_magnet = ?, batch_timeout = ?
            WHERE id = 1
        ''', (
            config.get('enabled', 0),
            config.get('filter_mode', 'empty_only'),
            config.get('first_delay', 600),
            config.get('retry_delay_1', 3600),
            config.get('retry_delay_2', 14400),
            config.get('retry_delay_3', 28800),
            config.get('max_retries', 3),
            config.get('concurrent_limit', 5),
            config.get('timeout_per_magnet', 30),
            config.get('batch_timeout', 300)
        ))
        return cursor.rowcount > 0


def add_calibration_task(note_id: int, magnet_hash: str, delay_seconds: int = 600) -> Optional[int]:
    """Add calibration task (one task per magnet link)"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # 检查是否已存在该磁力链接的任务（以磁力链接为单位去重）
        cursor.execute('''
            SELECT id FROM calibration_tasks
            WHERE note_id = ? AND magnet_hash = ? AND status IN ('pending', 'retrying')
        ''', (note_id, magnet_hash))

        if cursor.fetchone():
            return None

        now = datetime.now(CHINA_TZ)
        next_attempt = now + timedelta(seconds=delay_seconds)

        cursor.execute('''
            INSERT INTO calibration_tasks (note_id, magnet_hash, status, next_attempt, created_at)
            VALUES (?, ?, 'pending', ?, ?)
        ''', (note_id, magnet_hash, format_db_datetime(next_attempt),
              format_db_datetime(now)))

        return cursor.lastrowid


def get_pending_calibration_tasks(limit: int = 100) -> List[Dict[str, Any]]:
    """Get pending calibration tasks"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        now = format_db_datetime(datetime.now(CHINA_TZ))

        cursor.execute('''
            SELECT * FROM calibration_tasks
            WHERE status IN ('pending', 'retrying')
            AND next_attempt <= ?
            ORDER BY next_attempt ASC
            LIMIT ?
        ''', (now, limit))

        return [dict(row) for row in cursor.fetchall()]


def update_calibration_task(
    task_id: int,
    status: str,
    error_message: Optional[str] = None,
    next_retry_seconds: Optional[int] = None
) -> bool:
    """Update calibration task"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        now = format_db_datetime(datetime.now(CHINA_TZ))

        if status == 'retrying' and next_retry_seconds:
            next_attempt = datetime.now(CHINA_TZ) + timedelta(seconds=next_retry_seconds)
            cursor.execute('''
                UPDATE calibration_tasks
                SET status = ?, retry_count = retry_count + 1,
                    last_attempt = ?, next_attempt = ?, error_message = ?
                WHERE id = ?
            ''', (status, now, format_db_datetime(next_attempt), error_message, task_id))
        else:
            cursor.execute('''
                UPDATE calibration_tasks
                SET status = ?, last_attempt = ?, error_message = ?
                WHERE id = ?
            ''', (status, now, error_message, task_id))

        return cursor.rowcount > 0


def get_calibration_stats() -> Dict[str, Any]:
    """Get calibration stats"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        stats = {}

        cursor.execute('SELECT COUNT(*) FROM calibration_tasks')
        stats['total'] = cursor.fetchone()[0]

        cursor.execute('''
            SELECT status, COUNT(*) as count
            FROM calibration_tasks
            GROUP BY status
        ''')
        stats['by_status'] = {row[0]: row[1] for row in cursor.fetchall()}

        now = format_db_datetime(datetime.now(CHINA_TZ))
        cursor.execute('''
            SELECT COUNT(*) FROM calibration_tasks
            WHERE status IN ('pending', 'retrying') AND next_attempt <= ?
        ''', (now,))
        stats['ready_to_process'] = cursor.fetchone()[0]

        return stats


def delete_calibration_task(task_id: int) -> bool:
    """Delete calibration task"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM calibration_tasks WHERE id = ?', (task_id,))
        return cursor.rowcount > 0


def delete_calibration_tasks_by_note_id(note_id: int) -> int:
    """Delete calibration tasks by note ID"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM calibration_tasks WHERE note_id = ?', (note_id,))
        return cursor.rowcount


def clear_completed_calibration_tasks(days: int = 7) -> int:
    """Clear completed calibration tasks"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cutoff = format_db_datetime(datetime.now(CHINA_TZ) - timedelta(days=days))

        cursor.execute('''
            DELETE FROM calibration_tasks
            WHERE status = 'success' AND created_at < ?
        ''', (cutoff,))

        return cursor.rowcount


def get_all_calibration_tasks(
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """Get all calibration tasks"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        query = 'SELECT * FROM calibration_tasks WHERE 1=1'
        params = []

        if status:
            query += ' AND status = ?'
            params.append(status)

        query += ' ORDER BY created_at DESC LIMIT ? OFFSET ?'
        params.extend([limit, offset])

        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


def update_note_with_calibrated_dn(note_id: int, new_magnet_link: str, filename: str) -> bool:
    """Update note with calibrated magnet link"""
    from urllib.parse import quote

    max_attempts = 3
    with get_db_connection() as conn:
        cursor = conn.cursor()

        for attempt in range(1, max_attempts + 1):
            cursor.execute('SELECT message_text, magnet_link, filename FROM notes WHERE id = ?', (note_id,))
            row = cursor.fetchone()
            if not row:
                return False

            message_text, old_magnet, old_filename = row
            updated_text = message_text

            if message_text:
                info_hash_match = re.search(r'xt=urn:btih:([a-zA-Z0-9]+)', new_magnet_link, re.IGNORECASE)
                if info_hash_match:
                    info_hash = info_hash_match.group(1)
                    text_magnet_base = re.sub(r'[&?]dn=[^&]*', '', new_magnet_link)
                    text_magnet = f"{text_magnet_base}&dn={filename}"
                    magnet_pattern = rf'magnet:\?xt=urn:btih:{re.escape(info_hash)}(?:[&?][^\n\r]*)?'
                    updated_text = re.sub(magnet_pattern, text_magnet, message_text, flags=re.IGNORECASE)

            cursor.execute(
                'UPDATE notes SET message_text = ?, magnet_link = ?, filename = ? '
                'WHERE id = ? AND message_text IS ? AND magnet_link IS ? AND filename IS ?',
                (updated_text, new_magnet_link, filename, note_id, message_text, old_magnet, old_filename)
            )

            if cursor.rowcount > 0:
                return True

            logger.debug(f"更新笔记 {note_id} 发生并发冲突，重试 {attempt}/{max_attempts}")

        logger.warning(f"⚠️ 更新笔记 {note_id} 失败：并发冲突超过最大重试次数")
        return False


def update_note_with_calibrated_dns(note_id: int, calibrated_results: List[Dict[str, Any]]) -> bool:
    """Update note with multiple calibrated magnet links"""
    from urllib.parse import quote
    from bot.utils.magnet_utils import MagnetLinkParser

    max_attempts = 3
    with get_db_connection() as conn:
        cursor = conn.cursor()

        for attempt in range(1, max_attempts + 1):
            cursor.execute('SELECT message_text, magnet_link, filename FROM notes WHERE id = ?', (note_id,))
            row = cursor.fetchone()
            if not row:
                return False

            message_text, old_magnet, old_filename = row
            updated_text = message_text

            if message_text:
                for result in calibrated_results:
                    if not result.get('success'):
                        continue

                    info_hash = result['info_hash']
                    filename = MagnetLinkParser.clean_filename(result.get('filename', ''))
                    new_magnet = f"magnet:?xt=urn:btih:{info_hash}&dn={filename}"
                    # 修复：使用前瞻断言确保在遇到下一个magnet:、换行或字符串结束时停止
                    magnet_pattern = rf'magnet:\?xt=urn:btih:\s*{re.escape(info_hash)}(?:[&?][^&\s\n]*?(?=(?:magnet:|$|[\s\n])))*'
                    updated_text = re.sub(magnet_pattern, new_magnet, updated_text, flags=re.IGNORECASE)

            new_magnet_link = old_magnet
            new_filename = old_filename
            for result in calibrated_results:
                if result.get('success'):
                    filename = MagnetLinkParser.clean_filename(result.get('filename', ''))
                    old_magnet_for_db = result['old_magnet']
                    # 移除旧的dn参数（[^&]*会匹配到下一个&之前的所有内容，包括空格）
                    new_magnet_base = re.sub(r'[&?]dn=[^&]*', '', old_magnet_for_db)
                    encoded_filename = quote(filename) if filename else ""
                    new_magnet_link = f"{new_magnet_base}&dn={encoded_filename}"
                    new_filename = filename
                    break

            cursor.execute(
                'UPDATE notes SET message_text = ?, magnet_link = ?, filename = ? '
                'WHERE id = ? AND message_text IS ? AND magnet_link IS ? AND filename IS ?',
                (updated_text, new_magnet_link, new_filename, note_id, message_text, old_magnet, old_filename)
            )

            if cursor.rowcount > 0:
                return True

            logger.debug(f"更新笔记 {note_id} 发生并发冲突，重试 {attempt}/{max_attempts}")

        logger.warning(f"⚠️ 更新笔记 {note_id} 失败：并发冲突超过最大重试次数")
        return False
