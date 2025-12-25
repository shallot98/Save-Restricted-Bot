"""
Database Migrations
===================

Schema migrations and initialization.
"""

import sqlite3
import logging
import os
import json
import bcrypt
from pathlib import Path
from typing import List, Callable

from src.infrastructure.persistence.sqlite.connection import get_db_connection

logger = logging.getLogger(__name__)


def run_migrations() -> None:
    """
    Run all database migrations

    Creates tables and applies schema updates.
    """
    logger.info("Running database migrations...")

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Create tables
        _create_notes_table(cursor)
        _create_users_table(cursor)
        _create_calibration_tables(cursor)
        _create_watch_tables(cursor)

        # Apply migrations
        _apply_column_migrations(cursor)

        # Full-text search index (best-effort; falls back to LIKE when unavailable)
        _create_notes_fts(cursor)

        # Create indexes
        _create_indexes(cursor)

        # One-time best-effort migration for legacy JSON watch config
        _maybe_migrate_watch_config_from_json(cursor)

        # Apply schema updates/backfills for watch_tasks after potential data migration.
        _apply_watch_tasks_migrations(cursor)

        # Create default admin user
        _create_default_admin(cursor)

        conn.commit()

    logger.info("Database migrations completed")


def _create_notes_table(cursor: sqlite3.Cursor) -> None:
    """Create notes table"""
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            source_chat_id TEXT NOT NULL,
            source_name TEXT,
            message_text TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            media_type TEXT,
            media_path TEXT,
            media_paths TEXT,
            media_group_id TEXT,
            magnet_link TEXT,
            filename TEXT,
            is_favorite INTEGER DEFAULT 0
        )
    ''')
    logger.debug("Notes table created/verified")


def _create_users_table(cursor: sqlite3.Cursor) -> None:
    """Create users table"""
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    ''')
    logger.debug("Users table created/verified")


def _create_calibration_tables(cursor: sqlite3.Cursor) -> None:
    """Create calibration-related tables"""
    # Calibration tasks table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS calibration_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            note_id INTEGER NOT NULL,
            magnet_hash TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            retry_count INTEGER DEFAULT 0,
            last_attempt DATETIME,
            next_attempt DATETIME NOT NULL,
            error_message TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE CASCADE
        )
    ''')

    # Auto-calibration config table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS auto_calibration_config (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            enabled BOOLEAN DEFAULT 0,
            filter_mode TEXT DEFAULT 'empty_only',
            first_delay INTEGER DEFAULT 600,
            retry_delay_1 INTEGER DEFAULT 3600,
            retry_delay_2 INTEGER DEFAULT 14400,
            retry_delay_3 INTEGER DEFAULT 28800,
            max_retries INTEGER DEFAULT 3,
            concurrent_limit INTEGER DEFAULT 5,
            timeout_per_magnet INTEGER DEFAULT 30,
            batch_timeout INTEGER DEFAULT 300
        )
    ''')

    # Insert default config
    cursor.execute('''
        INSERT OR IGNORE INTO auto_calibration_config (id, enabled, filter_mode)
        VALUES (1, 0, 'empty_only')
    ''')

    logger.debug("Calibration tables created/verified")


def _create_watch_tables(cursor: sqlite3.Cursor) -> None:
    """Create watch/monitoring configuration tables."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS watch_tasks (
            user_id TEXT NOT NULL,
            watch_key TEXT NOT NULL,
            watch_id TEXT,
            source_id TEXT NOT NULL,
            dest_id TEXT,
            record_mode INTEGER NOT NULL DEFAULT 0,
            whitelist_json TEXT NOT NULL DEFAULT '[]',
            blacklist_json TEXT NOT NULL DEFAULT '[]',
            whitelist_regex_json TEXT NOT NULL DEFAULT '[]',
            blacklist_regex_json TEXT NOT NULL DEFAULT '[]',
            preserve_forward_source INTEGER NOT NULL DEFAULT 0,
            forward_mode TEXT NOT NULL DEFAULT 'full',
            extract_patterns_json TEXT NOT NULL DEFAULT '[]',
            PRIMARY KEY (user_id, watch_key)
        )
        """
    )
    logger.debug("Watch tables created/verified")


def _apply_watch_tasks_migrations(cursor: sqlite3.Cursor) -> None:
    """Apply schema updates for watch_tasks table.

    Currently:
    - Add explicit watch_id column (best-effort, backfill existing rows)
    - Create unique index for watch_id lookups
    """
    try:
        cursor.execute("PRAGMA table_info(watch_tasks)")
        existing_columns = {col[1] for col in cursor.fetchall()}
    except sqlite3.Error as e:
        logger.warning(f"Skip watch_tasks migrations (table unavailable): {e}")
        return

    if "watch_id" not in existing_columns:
        try:
            cursor.execute("ALTER TABLE watch_tasks ADD COLUMN watch_id TEXT")
            logger.info("Added column: watch_tasks.watch_id")
        except sqlite3.Error as e:
            logger.warning(f"Failed to add watch_tasks.watch_id: {e}")
            return

    try:
        cursor.execute(
            "SELECT watch_id FROM watch_tasks WHERE watch_id IS NOT NULL AND TRIM(watch_id) != ''"
        )
        existing_ids = {str(row[0]) for row in cursor.fetchall()}

        cursor.execute(
            "SELECT user_id, watch_key FROM watch_tasks WHERE watch_id IS NULL OR TRIM(watch_id) = ''"
        )
        missing_rows = cursor.fetchall()
    except sqlite3.Error as e:
        logger.warning(f"Skip watch_id backfill (query failed): {e}")
        return

    if missing_rows:
        import uuid

        for row in missing_rows:
            user_id = str(row[0])
            watch_key = str(row[1])

            # Generate a short stable ID; collisions are extremely unlikely, but guard anyway.
            while True:
                watch_id = uuid.uuid4().hex
                if watch_id not in existing_ids:
                    existing_ids.add(watch_id)
                    break

            try:
                cursor.execute(
                    "UPDATE watch_tasks SET watch_id = ? WHERE user_id = ? AND watch_key = ?",
                    (watch_id, user_id, watch_key),
                )
            except sqlite3.Error as e:
                logger.warning(f"Failed to backfill watch_id for {user_id}:{watch_key}: {e}")

        logger.info(f"Backfilled watch_id for watch_tasks rows: {len(missing_rows)}")

    try:
        cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_watch_tasks_watch_id ON watch_tasks(watch_id)"
        )
    except sqlite3.Error as e:
        logger.warning(f"Failed to create idx_watch_tasks_watch_id: {e}")


def _maybe_migrate_watch_config_from_json(cursor: sqlite3.Cursor) -> None:
    """Best-effort migration from legacy watch_config.json into watch_tasks."""
    try:
        cursor.execute("SELECT 1 FROM watch_tasks LIMIT 1")
        if cursor.fetchone() is not None:
            return
    except sqlite3.Error as e:
        logger.warning(f"Skip watch config migration (watch_tasks unavailable): {e}")
        return

    try:
        from src.core.config import settings
    except Exception as e:
        logger.warning(f"Skip watch config migration (settings unavailable): {e}")
        return

    watch_file: Path = settings.paths.watch_file
    if not watch_file.exists():
        return

    try:
        raw = json.loads(watch_file.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"Skip watch config migration (invalid json): {e}")
        return

    if not isinstance(raw, dict) or not raw:
        return

    rows = []
    for user_id, user_data in raw.items():
        if not isinstance(user_data, dict):
            continue
        for watch_key, watch_data in user_data.items():
            source_id = ""
            dest_id = None
            record_mode = 0
            whitelist = []
            blacklist = []
            whitelist_regex = []
            blacklist_regex = []
            preserve_forward_source = 0
            forward_mode = "full"
            extract_patterns = []

            if isinstance(watch_data, dict):
                source_id = str(watch_data.get("source") or "").strip()
                if not source_id:
                    source_id = str(str(watch_key).split("|")[0] if "|" in str(watch_key) else watch_key).strip()
                dest_id = watch_data.get("dest")
                record_mode = 1 if bool(watch_data.get("record_mode", False)) else 0
                whitelist = watch_data.get("whitelist", []) or []
                blacklist = watch_data.get("blacklist", []) or []
                whitelist_regex = watch_data.get("whitelist_regex", []) or []
                blacklist_regex = watch_data.get("blacklist_regex", []) or []
                preserve_forward_source = 1 if bool(watch_data.get("preserve_forward_source", False)) else 0
                forward_mode = str(watch_data.get("forward_mode", "full") or "full")
                extract_patterns = watch_data.get("extract_patterns", []) or []
            else:
                source_id = str(str(watch_key).split("|")[0] if "|" in str(watch_key) else watch_key).strip()
                dest_id = watch_data
                record_mode = 0

            canonical_key = str(watch_key)
            if "|" not in canonical_key:
                if record_mode:
                    canonical_key = f"{source_id}|record"
                elif dest_id is not None:
                    canonical_key = f"{source_id}|{dest_id}"
                else:
                    canonical_key = source_id or canonical_key

            if not source_id:
                continue

            rows.append(
                (
                    str(user_id),
                    canonical_key,
                    source_id,
                    None if dest_id is None else str(dest_id),
                    record_mode,
                    json.dumps(list(whitelist), ensure_ascii=False),
                    json.dumps(list(blacklist), ensure_ascii=False),
                    json.dumps(list(whitelist_regex), ensure_ascii=False),
                    json.dumps(list(blacklist_regex), ensure_ascii=False),
                    preserve_forward_source,
                    forward_mode,
                    json.dumps(list(extract_patterns), ensure_ascii=False),
                )
            )

    if not rows:
        return

    try:
        cursor.executemany(
            """
            INSERT INTO watch_tasks (
                user_id,
                watch_key,
                source_id,
                dest_id,
                record_mode,
                whitelist_json,
                blacklist_json,
                whitelist_regex_json,
                blacklist_regex_json,
                preserve_forward_source,
                forward_mode,
                extract_patterns_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        logger.info(f"Migrated watch config from json: users={len(raw)} tasks={len(rows)}")
    except sqlite3.Error as e:
        logger.warning(f"Failed to migrate watch config from json: {e}")


def _apply_column_migrations(cursor: sqlite3.Cursor) -> None:
    """Apply column migrations for existing databases"""
    # Get existing columns
    cursor.execute("PRAGMA table_info(notes)")
    existing_columns = {col[1] for col in cursor.fetchall()}

    # Columns to add if missing
    migrations = [
        ("media_paths", "TEXT"),
        ("media_group_id", "TEXT"),
        ("magnet_link", "TEXT"),
        ("filename", "TEXT"),
        ("is_favorite", "INTEGER DEFAULT 0"),
    ]

    for column_name, column_type in migrations:
        if column_name not in existing_columns:
            cursor.execute(f"ALTER TABLE notes ADD COLUMN {column_name} {column_type}")
            logger.info(f"Added column: {column_name}")


def _create_notes_fts(cursor: sqlite3.Cursor) -> None:
    """Create and (optionally) rebuild notes FTS index.

    Notes:
    - Uses SQLite FTS5 if available.
    - If FTS5 is not available in the runtime sqlite, migrations continue without failing.
    """
    cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='notes_fts' LIMIT 1"
    )
    has_fts = cursor.fetchone() is not None

    try:
        cursor.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
                message_text,
                source_name,
                content='notes',
                content_rowid='id',
                tokenize='unicode61'
            )
            """
        )
    except sqlite3.OperationalError as e:
        logger.warning(f"SQLite FTS5 unavailable, skip notes_fts: {e}")
        return

    # Keep external content FTS table in sync.
    cursor.execute(
        """
        CREATE TRIGGER IF NOT EXISTS notes_fts_ai
        AFTER INSERT ON notes
        BEGIN
            INSERT INTO notes_fts(rowid, message_text, source_name)
            VALUES (new.id, new.message_text, new.source_name);
        END
        """
    )
    cursor.execute(
        """
        CREATE TRIGGER IF NOT EXISTS notes_fts_ad
        AFTER DELETE ON notes
        BEGIN
            INSERT INTO notes_fts(notes_fts, rowid, message_text, source_name)
            VALUES('delete', old.id, old.message_text, old.source_name);
        END
        """
    )
    cursor.execute(
        """
        CREATE TRIGGER IF NOT EXISTS notes_fts_au
        AFTER UPDATE OF message_text, source_name ON notes
        BEGIN
            INSERT INTO notes_fts(notes_fts, rowid, message_text, source_name)
            VALUES('delete', old.id, old.message_text, old.source_name);
            INSERT INTO notes_fts(rowid, message_text, source_name)
            VALUES (new.id, new.message_text, new.source_name);
        END
        """
    )

    if not has_fts:
        try:
            cursor.execute("INSERT INTO notes_fts(notes_fts) VALUES('rebuild')")
        except sqlite3.OperationalError as e:
            logger.warning(f"Failed to rebuild notes_fts: {e}")
            return

        logger.info("notes_fts created and rebuilt")


def _create_indexes(cursor: sqlite3.Cursor) -> None:
    """Create database indexes for performance"""
    indexes = [
        # Notes table indexes
        ("idx_notes_user_id", "notes(user_id)"),
        ("idx_notes_source_chat_id", "notes(source_chat_id)"),
        ("idx_notes_timestamp", "notes(timestamp DESC)"),
        ("idx_notes_user_source_time", "notes(user_id, source_chat_id, timestamp DESC)"),
        ("idx_notes_favorite", "notes(user_id, is_favorite) WHERE is_favorite = 1"),
        ("idx_notes_search", "notes(user_id, source_chat_id, message_text)"),
        # Calibration indexes
        ("idx_calibration_status", "calibration_tasks(status, next_attempt)"),
        ("idx_calibration_note", "calibration_tasks(note_id)"),
        # Watch indexes
        ("idx_watch_tasks_user", "watch_tasks(user_id)"),
        ("idx_watch_tasks_source", "watch_tasks(source_id)"),
    ]

    for index_name, index_def in indexes:
        try:
            cursor.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON {index_def}")
        except sqlite3.OperationalError:
            # Index might already exist with different definition
            pass

    logger.debug("Database indexes created/verified")


def _create_default_admin(cursor: sqlite3.Cursor) -> None:
    """Create default admin user if not exists"""
    try:
        password = os.environ.get("ADMIN_PASSWORD") or "admin"
        password_hash = bcrypt.hashpw(
            password.encode('utf-8'),
            bcrypt.gensalt()
        ).decode('utf-8')

        cursor.execute(
            'INSERT INTO users (username, password_hash) VALUES (?, ?)',
            ('admin', password_hash)
        )
        if password == "admin":
            logger.warning(
                "Default admin user created (admin/admin); "
                "请尽快在管理后台修改密码，或通过环境变量 ADMIN_PASSWORD 设置初始密码"
            )
        else:
            logger.info("Default admin user created (admin/<from ADMIN_PASSWORD>)")
    except sqlite3.IntegrityError:
        # Admin already exists
        pass
