import sqlite3

from src.infrastructure.persistence.sqlite.notes_fts_migrations import create_or_rebuild_notes_fts
from src.infrastructure.persistence.sqlite.watch_task_migrations import apply_watch_task_schema_updates


def test_apply_watch_task_schema_updates_adds_watch_id_and_index() -> None:
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE watch_tasks (
            user_id TEXT NOT NULL,
            watch_key TEXT NOT NULL,
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
    cursor.execute(
        "INSERT INTO watch_tasks (user_id, watch_key, source_id) VALUES (?, ?, ?)",
        ("u1", "src|dst", "src"),
    )

    apply_watch_task_schema_updates(cursor)

    cursor.execute("PRAGMA table_info(watch_tasks)")
    columns = {row[1] for row in cursor.fetchall()}
    assert "watch_id" in columns
    cursor.execute("SELECT watch_id FROM watch_tasks")
    assert cursor.fetchone()[0]
    cursor.execute("PRAGMA index_list(watch_tasks)")
    index_names = {row[1] for row in cursor.fetchall()}
    assert "idx_watch_tasks_watch_id" in index_names


def test_create_or_rebuild_notes_fts_creates_triggers() -> None:
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            source_chat_id TEXT NOT NULL,
            source_name TEXT,
            message_text TEXT
        )
        """
    )

    create_or_rebuild_notes_fts(cursor)

    cursor.execute("SELECT name FROM sqlite_master WHERE type='trigger'")
    triggers = {row[0] for row in cursor.fetchall()}
    assert {"notes_fts_ai", "notes_fts_ad", "notes_fts_au"}.issubset(triggers)
