"""遗留 note API 的实现（原仓库根 ``database_notes.py``）。

只保留仍有调用方的函数。以下函数在移入时经全仓 rg 复核为零引用，直接删除而非搬运：
``get_note_count`` / ``get_sources`` / ``update_note`` / ``update_magnet_link`` /
``delete_note`` / ``toggle_favorite`` / ``apply_calibrated_magnet``（单数版）。
它们的现役等价物是 ``NoteService`` 上的同名方法，Web 与 Bot 均已直接调用后者。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Callable, Optional, cast

from src.core.exceptions import NotFoundError, ValidationError
from src.core.utils.datetime_utils import format_db_datetime
from src.domain.entities.note import Note, NoteCreate, NoteFilter
from src.domain.magnet import MagnetLinkParser

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NoteCompatibilityDeps:
    """旧 API 所需依赖的显式注入点（避免在本模块内做服务定位）。"""

    # 工厂返回值保持 Any：容器在 composition/ 里构造，这里不反向依赖组合根的具体类型。
    # 因此下方几处返回值用 cast 把仓储/服务的契约（int / bool）显式写回，
    # 而不是让 Any 顺着 `warn_return_any` 漏出去。
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
        return cast(int, duplicate_id)

    magnet_link = (
        MagnetLinkParser.extract_magnet_from_text(request.message_text)
        if request.message_text
        else None
    )
    note_dto = _create_note(deps, request, normalized_user_id, normalized_source_chat_id)
    _update_magnet_if_needed(deps, note_dto.id, magnet_link)
    logger.info(f"✅ Note saved: id={note_dto.id}")
    return cast(int, note_dto.id)


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


def apply_calibrated_magnets(
    deps: NoteCompatibilityDeps,
    note_id: int,
    calibrated_results: list[dict[str, Any]],
) -> bool:
    try:
        return cast(
            bool,
            deps.note_service_factory().apply_calibrated_magnets(note_id, calibrated_results),
        )
    except NotFoundError:
        return False
