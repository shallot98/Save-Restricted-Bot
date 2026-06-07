"""Row conversion helpers for SQLite notes."""

from __future__ import annotations

import json
from datetime import datetime

from src.core.utils.datetime_utils import parse_db_datetime
from src.domain.entities.note import Note


class SQLiteNoteRowMixin:
    def _row_to_note(self, row: dict) -> Note:
        media_paths = self._parse_media_paths(row)
        timestamp = parse_db_datetime(row.get("timestamp")) or datetime.now()
        return Note(
            id=row["id"],
            user_id=row["user_id"],
            source_chat_id=row["source_chat_id"],
            source_name=row.get("source_name"),
            message_text=row.get("message_text"),
            timestamp=timestamp,
            media_type=row.get("media_type"),
            media_path=row.get("media_path"),
            media_paths=media_paths,
            media_group_id=row.get("media_group_id"),
            magnet_link=row.get("magnet_link"),
            filename=row.get("filename"),
            is_favorite=bool(row.get("is_favorite", 0)),
        )

    @staticmethod
    def _parse_media_paths(row: dict) -> list[str]:
        media_paths = []
        if row.get("media_paths"):
            try:
                media_paths = json.loads(row["media_paths"])
            except (json.JSONDecodeError, TypeError):
                pass
        if not media_paths and row.get("media_path"):
            media_paths = [row["media_path"]]
        return media_paths

    @staticmethod
    def _media_paths_json(media_paths) -> str | None:
        if not media_paths:
            return None
        return json.dumps(media_paths, ensure_ascii=False)
