"""Temporary disk-backed queue for oldest-first history copy iteration."""

from __future__ import annotations

import os
import sqlite3
import tempfile
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator

from .history_copy_utils import message_id


@dataclass(frozen=True)
class HistoryCopyQueuedChat:
    """Minimal chat reference required by the history copy runtime."""

    id: int


@dataclass(frozen=True)
class HistoryCopyQueuedMessage:
    """Minimal message projection required by the history copy runtime."""

    id: int
    chat: HistoryCopyQueuedChat
    media_group_id: str | None = None


class HistoryCopyMessageQueue:
    """Persist fetched history on disk and replay it in oldest-first order."""

    def __init__(self, state_db_path: Path) -> None:
        queue_dir = Path(state_db_path).parent
        queue_dir.mkdir(parents=True, exist_ok=True)
        file_descriptor, raw_path = tempfile.mkstemp(
            prefix="history_copy_queue_",
            suffix=".sqlite3",
            dir=queue_dir,
        )
        os.close(file_descriptor)
        self._db_path = Path(raw_path)
        self._conn = sqlite3.connect(self._db_path)
        self._init_schema()

    def __enter__(self) -> "HistoryCopyMessageQueue":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def _init_schema(self) -> None:
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE queued_messages (
                    message_id INTEGER PRIMARY KEY,
                    chat_id INTEGER NOT NULL,
                    media_group_id TEXT
                )
                """
            )

    def add_batch(self, messages: Iterable[Any]) -> None:
        payload = [self._build_payload(message) for message in messages if message_id(message) > 0]
        if not payload:
            return
        with self._conn:
            self._conn.executemany(
                """
                INSERT OR REPLACE INTO queued_messages (
                    message_id,
                    chat_id,
                    media_group_id
                ) VALUES (?, ?, ?)
                """,
                payload,
            )

    def iter_oldest_first(self) -> Iterator[HistoryCopyQueuedMessage]:
        cursor = self._conn.execute(
            """
            SELECT message_id, chat_id, media_group_id
            FROM queued_messages
            ORDER BY message_id ASC
            """
        )
        for message_id_value, chat_id_value, media_group_id_value in cursor:
            yield HistoryCopyQueuedMessage(
                id=int(message_id_value),
                chat=HistoryCopyQueuedChat(id=int(chat_id_value)),
                media_group_id=media_group_id_value or None,
            )

    def close(self) -> None:
        self._conn.close()
        with suppress(FileNotFoundError):
            self._db_path.unlink()

    @staticmethod
    def _build_payload(message: Any) -> tuple[int, int, str | None]:
        current_message_id = message_id(message)
        chat_id = int(getattr(getattr(message, "chat", None), "id", 0) or 0)
        media_group_id = str(getattr(message, "media_group_id", "") or "") or None
        return current_message_id, chat_id, media_group_id
