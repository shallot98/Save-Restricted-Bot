"""
Database Migrations
===================

Schema migrations and initialization.
"""

import sqlite3
import logging
import os
import bcrypt

from src.infrastructure.persistence.sqlite.connection import get_db_connection
from src.infrastructure.persistence.sqlite.notes_fts_migrations import create_or_rebuild_notes_fts
from src.infrastructure.persistence.sqlite.watch_task_migrations import (
    apply_watch_task_schema_updates,
    migrate_watch_config_from_json,
)

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
    """Apply schema updates for watch_tasks table."""
    apply_watch_task_schema_updates(cursor)


def _maybe_migrate_watch_config_from_json(cursor: sqlite3.Cursor) -> None:
    """Best-effort migration from legacy watch_config.json into watch_tasks."""
    migrate_watch_config_from_json(cursor)


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
    """Create and repair notes_fts with dedicated migration helpers."""
    create_or_rebuild_notes_fts(cursor)


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
