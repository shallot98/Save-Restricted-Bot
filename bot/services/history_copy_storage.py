"""Persistent resume/dedup storage for Telegram history copy."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Iterable


class HistoryCopyStateStore:
    """Persist successful copy state for resume/dedup."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path)
        self._init_schema()

    def __enter__(self) -> "HistoryCopyStateStore":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def _init_schema(self) -> None:
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS copied_messages (
                    source_chat_id TEXT NOT NULL,
                    dest_chat_id TEXT NOT NULL,
                    message_id INTEGER NOT NULL,
                    copied_at INTEGER NOT NULL,
                    PRIMARY KEY (source_chat_id, dest_chat_id, message_id)
                )
                """
            )

    def is_copied(self, source_chat_id: str, dest_chat_id: str, message_id: int) -> bool:
        cursor = self._conn.execute(
            """
            SELECT 1
            FROM copied_messages
            WHERE source_chat_id = ? AND dest_chat_id = ? AND message_id = ?
            LIMIT 1
            """,
            (source_chat_id, dest_chat_id, int(message_id)),
        )
        return cursor.fetchone() is not None

    def mark_copied(self, source_chat_id: str, dest_chat_id: str, message_id: int) -> None:
        self.mark_copied_many(source_chat_id, dest_chat_id, [message_id])

    def mark_copied_many(
        self,
        source_chat_id: str,
        dest_chat_id: str,
        message_ids: Iterable[int],
    ) -> None:
        payload = [
            (source_chat_id, dest_chat_id, int(message_id), int(time.time()))
            for message_id in message_ids
        ]
        if not payload:
            return
        with self._conn:
            self._conn.executemany(
                """
                INSERT OR IGNORE INTO copied_messages (
                    source_chat_id,
                    dest_chat_id,
                    message_id,
                    copied_at
                ) VALUES (?, ?, ?, ?)
                """,
                payload,
            )

    def close(self) -> None:
        self._conn.close()
