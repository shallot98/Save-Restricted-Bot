"""Legacy note helpers for the root database compatibility module."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Callable, Optional

from src.core.exceptions import NotFoundError, ValidationError
from src.core.utils.datetime_utils import format_db_datetime
from src.domain.entities.note import Note, NoteCreate, NoteFilter

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NoteCompatibilityDeps:
    note_repository_factory: Callable[[], Any]
    note_service_factory: Callable[[], Any]


@dataclass(frozen=True)
class LegacyNoteCreateRequest:
    user_id: Any
    source_chat_id: Any
    source_name: Optional[str]
    message_text: Optional[str]
    media_type: Optional[str] = None
    media_path: Optional[str] = None
    media_paths: Optional[list[str]] = None
    media_group_id: Optional[str] = None


@dataclass(frozen=True)
class LegacyNoteQuery:
    user_id: Optional[int] = None
    source_chat_id: Optional[str] = None
    search_query: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    favorite_only: bool = False
    limit: int = 50
    offset: int = 0


def _parse_media_paths(note: dict[str, Any]) -> dict[str, Any]:
    if note.get("media_paths"):
        try:
            note["media_paths"] = json.loads(note["media_paths"])
        except (json.JSONDecodeError, TypeError):
            note["media_paths"] = []
    else:
        note["media_paths"] = []

    if not note["media_paths"] and note.get("media_path"):
        note["media_paths"] = [note["media_path"]]

    return note


def _normalize_note_identity(user_id: Any, source_chat_id: Any) -> tuple[int, str]:
    if user_id is None:
        raise ValueError("user_id cannot be None")
    if source_chat_id is None:
        raise ValueError("source_chat_id cannot be None")
    return int(user_id), str(source_chat_id)


def _note_to_legacy_dict(note: Note) -> dict[str, Any]:
    payload = note.to_dict()
    payload["timestamp"] = format_db_datetime(note.timestamp)
    payload["media_paths"] = list(note.media_paths or [])
    return payload


def add_note(deps: NoteCompatibilityDeps, request: LegacyNoteCreateRequest) -> int:
    from bot.utils.magnet_utils import MagnetLinkParser

    normalized_user_id, normalized_source_chat_id = _normalize_note_identity(
        request.user_id,
        request.source_chat_id,
    )
    note_repository = deps.note_repository_factory()
    duplicate_id = note_repository.find_duplicate_id(
        normalized_user_id,
        normalized_source_chat_id,
        request.message_text,
        request.media_group_id,
    )
    if duplicate_id is not None:
        return duplicate_id

    magnet_link = (
        MagnetLinkParser.extract_magnet_from_text(request.message_text)
        if request.message_text
        else None
    )
    note_dto = _create_note(deps, request, normalized_user_id, normalized_source_chat_id)
    _update_magnet_if_needed(deps, note_dto.id, magnet_link)
    logger.info(f"✅ Note saved: id={note_dto.id}")
    return note_dto.id


def _create_note(
    deps: NoteCompatibilityDeps,
    request: LegacyNoteCreateRequest,
    user_id: int,
    source_chat_id: str,
):
    note_service = deps.note_service_factory()
    try:
        return note_service.create_note(
            NoteCreate(
                user_id=user_id,
                source_chat_id=source_chat_id,
                source_name=request.source_name,
                message_text=request.message_text,
                media_type=request.media_type,
                media_path=request.media_path,
                media_paths=request.media_paths,
                media_group_id=request.media_group_id,
            )
        )
    except ValidationError:
        duplicate_id = deps.note_repository_factory().find_duplicate_id(
            user_id,
            source_chat_id,
            request.message_text,
            request.media_group_id,
        )
        if duplicate_id is not None:
            return type("LegacyDuplicateNote", (), {"id": duplicate_id})()
        raise


def _update_magnet_if_needed(
    deps: NoteCompatibilityDeps,
    note_id: int,
    magnet_link: Optional[str],
) -> None:
    if not magnet_link:
        return
    try:
        deps.note_service_factory().update_magnet(note_id, magnet_link, filename=None)
    except Exception as exc:
        logger.warning(f"Failed to update note magnet after create: {exc}")


def get_notes(deps: NoteCompatibilityDeps, query: LegacyNoteQuery) -> list[dict[str, Any]]:
    notes, _total = deps.note_repository_factory().search(_to_note_filter(query))
    return [_note_to_legacy_dict(note) for note in notes]


def get_note_count(deps: NoteCompatibilityDeps, query: LegacyNoteQuery) -> int:
    return deps.note_service_factory().count_notes(
        user_id=query.user_id,
        source_chat_id=query.source_chat_id,
        search_query=query.search_query,
        date_from=query.date_from,
        date_to=query.date_to,
        favorite_only=query.favorite_only,
    )


def _to_note_filter(query: LegacyNoteQuery) -> NoteFilter:
    search_query = (query.search_query or "").strip() or None
    return NoteFilter(
        user_id=query.user_id,
        source_chat_id=query.source_chat_id,
        search_query=search_query,
        date_from=query.date_from,
        date_to=query.date_to,
        favorite_only=query.favorite_only,
        limit=query.limit,
        offset=query.offset,
    )


def get_note_by_id(deps: NoteCompatibilityDeps, note_id: int) -> Optional[dict[str, Any]]:
    note = deps.note_repository_factory().get_by_id(note_id)
    return _note_to_legacy_dict(note) if note else None


def update_note(deps: NoteCompatibilityDeps, note_id: int, message_text: str) -> bool:
    try:
        return deps.note_service_factory().update_text(note_id, message_text)
    except (NotFoundError, ValidationError):
        return False


def update_magnet_link(deps: NoteCompatibilityDeps, note_id: int, magnet_link: str) -> bool:
    return deps.note_repository_factory().update_magnet(note_id, magnet_link, filename=None)


def delete_note(deps: NoteCompatibilityDeps, note_id: int) -> bool:
    try:
        return deps.note_service_factory().delete_note(note_id)
    except NotFoundError:
        return False


def apply_calibrated_magnet(
    deps: NoteCompatibilityDeps,
    note_id: int,
    new_magnet_link: str,
    filename: str,
) -> bool:
    try:
        return deps.note_service_factory().apply_calibrated_magnet(
            note_id,
            new_magnet_link,
            filename,
        )
    except NotFoundError:
        return False


def apply_calibrated_magnets(
    deps: NoteCompatibilityDeps,
    note_id: int,
    calibrated_results: list[dict[str, Any]],
) -> bool:
    try:
        return deps.note_service_factory().apply_calibrated_magnets(
            note_id,
            calibrated_results,
        )
    except NotFoundError:
        return False


def get_sources(db_connection_factory: Callable[[], Any], user_id: Optional[int]) -> list[dict[str, Any]]:
    with db_connection_factory() as conn:
        cursor = conn.cursor()
        query = "SELECT DISTINCT source_chat_id, source_name FROM notes WHERE 1=1"
        params = []
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


def toggle_favorite(db_connection_factory: Callable[[], Any], note_id: int) -> bool:
    with db_connection_factory() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE notes SET is_favorite = 1 - is_favorite WHERE id = ?", (note_id,))
        return cursor.rowcount > 0
