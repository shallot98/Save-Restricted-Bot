"""
Database Module - Backward Compatible Interface

This module provides backward-compatible database functions
that delegate to the new layered architecture.

For new code, prefer using:
    from src.infrastructure.persistence.repositories import SQLiteNoteRepository
    from src.domain.entities import Note, NoteCreate
"""

import logging
from zoneinfo import ZoneInfo
from typing import Any, Optional

from database_auth import update_password as _update_password
from database_auth import verify_user as _verify_user
from database_calibration import (
    CalibrationDeps,
    CalibrationTaskCreate,
    CalibrationTaskQuery,
    CalibrationTaskUpdate,
)
from database_calibration import add_calibration_task as _add_calibration_task
from database_calibration import clear_completed_calibration_tasks as _clear_completed_calibration_tasks
from database_calibration import delete_calibration_task as _delete_calibration_task
from database_calibration import delete_calibration_tasks_by_note_id as _delete_calibration_tasks_by_note_id
from database_calibration import get_all_calibration_tasks as _get_all_calibration_tasks
from database_calibration import get_calibration_config as _get_calibration_config
from database_calibration import get_calibration_stats as _get_calibration_stats
from database_calibration import get_pending_calibration_tasks as _get_pending_calibration_tasks
from database_calibration import update_calibration_config as _update_calibration_config
from database_calibration import update_calibration_task as _update_calibration_task
from database_note_requests import legacy_note_create_request, legacy_note_query
from database_notes import LegacyNoteCreateRequest, LegacyNoteQuery, NoteCompatibilityDeps
from database_notes import _normalize_note_identity, _note_to_legacy_dict, _parse_media_paths
from database_notes import add_note as _add_note
from database_notes import apply_calibrated_magnet as _apply_calibrated_magnet
from database_notes import apply_calibrated_magnets as _apply_calibrated_magnets
from database_notes import delete_note as _delete_note
from database_notes import get_note_by_id as _get_note_by_id
from database_notes import get_note_count as _get_note_count
from database_notes import get_notes as _get_notes
from database_notes import get_sources as _get_sources
from database_notes import toggle_favorite as _toggle_favorite
from database_notes import update_magnet_link as _update_magnet_link
from database_notes import update_note as _update_note
from src.core.config import settings
from src.core.container import get_container, get_note_service
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


def _get_note_repository():
    """Access the concrete note repository behind the compatibility layer."""
    return get_container().note_repository


def _note_deps() -> NoteCompatibilityDeps:
    return NoteCompatibilityDeps(
        note_repository_factory=_get_note_repository,
        note_service_factory=get_note_service,
    )


def _calibration_deps() -> CalibrationDeps:
    return CalibrationDeps(
        db_connection_factory=get_db_connection,
        timezone=CHINA_TZ,
    )


def add_note(
    request: LegacyNoteCreateRequest | Any = None,
    *legacy_args,
    **legacy_kwargs,
) -> int:
    """Add a note record via the application service while preserving legacy semantics."""
    return _add_note(_note_deps(), legacy_note_create_request(request, legacy_args, legacy_kwargs))


def get_notes(
    query: LegacyNoteQuery | Any = None,
    *legacy_args,
    **legacy_kwargs,
) -> list[dict[str, Any]]:
    """Get notes list via the concrete repository while preserving legacy payload shape."""
    return _get_notes(_note_deps(), legacy_note_query(query, legacy_args, legacy_kwargs))


def get_note_count(
    query: LegacyNoteQuery | Any = None,
    *legacy_args,
    **legacy_kwargs,
) -> int:
    """Get notes count with the same filter semantics as the application layer."""
    return _get_note_count(_note_deps(), legacy_note_query(query, legacy_args, legacy_kwargs))


def get_sources(user_id: Optional[int] = None) -> list[dict[str, Any]]:
    """Get all sources"""
    return _get_sources(get_db_connection, user_id)


def get_note_by_id(note_id: int) -> Optional[dict[str, Any]]:
    """Get note by ID through the concrete repository."""
    return _get_note_by_id(_note_deps(), note_id)


def update_note(note_id: int, message_text: str) -> bool:
    """Update note content via NoteService."""
    return _update_note(_note_deps(), note_id, message_text)


def update_magnet_link(note_id: int, magnet_link: str) -> bool:
    """Update magnet link through the concrete repository."""
    return _update_magnet_link(_note_deps(), note_id, magnet_link)


def delete_note(note_id: int) -> bool:
    """Delete note via NoteService while preserving legacy bool semantics."""
    return _delete_note(_note_deps(), note_id)


def toggle_favorite(note_id: int) -> bool:
    """Toggle favorite status"""
    return _toggle_favorite(get_db_connection, note_id)


def verify_user(username: str, password: str) -> bool:
    """Verify user login"""
    return _verify_user(get_db_connection, username, password)


def update_password(username: str, new_password: str) -> None:
    """Update user password"""
    return _update_password(get_db_connection, username, new_password)


# ==================== Calibration Functions ====================

def get_calibration_config() -> Optional[dict[str, Any]]:
    """Get calibration config"""
    return _get_calibration_config(_calibration_deps())


def update_calibration_config(config: dict[str, Any]) -> bool:
    """Update calibration config"""
    return _update_calibration_config(_calibration_deps(), config)


def add_calibration_task(note_id: int, magnet_hash: str, delay_seconds: int = 600) -> Optional[int]:
    """Add calibration task (one task per magnet link)"""
    task = CalibrationTaskCreate(note_id, magnet_hash, delay_seconds)
    return _add_calibration_task(_calibration_deps(), task)


def get_pending_calibration_tasks(limit: int = 100) -> list[dict[str, Any]]:
    """Get pending calibration tasks"""
    return _get_pending_calibration_tasks(_calibration_deps(), limit)


def update_calibration_task(
    task_id: int,
    status: str,
    error_message: Optional[str] = None,
    *legacy_args: Any,
    next_retry_seconds: Optional[int] = None
) -> bool:
    """Update calibration task"""
    if legacy_args:
        if len(legacy_args) > 1 or next_retry_seconds is not None:
            raise TypeError("update_calibration_task received conflicting retry delay arguments")
        next_retry_seconds = legacy_args[0]
    update = CalibrationTaskUpdate(task_id, status, error_message, next_retry_seconds)
    return _update_calibration_task(_calibration_deps(), update)


def get_calibration_stats() -> dict[str, Any]:
    """Get calibration stats"""
    return _get_calibration_stats(_calibration_deps())


def delete_calibration_task(task_id: int) -> bool:
    """Delete calibration task"""
    return _delete_calibration_task(_calibration_deps(), task_id)


def delete_calibration_tasks_by_note_id(note_id: int) -> int:
    """Delete calibration tasks by note ID"""
    return _delete_calibration_tasks_by_note_id(_calibration_deps(), note_id)


def clear_completed_calibration_tasks(days: int = 7) -> int:
    """Clear completed calibration tasks"""
    return _clear_completed_calibration_tasks(_calibration_deps(), days)


def get_all_calibration_tasks(status: Optional[str] = None, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    """Get all calibration tasks"""
    query = CalibrationTaskQuery(status=status, limit=limit, offset=offset)
    return _get_all_calibration_tasks(_calibration_deps(), query)


def update_note_with_calibrated_dn(note_id: int, new_magnet_link: str, filename: str) -> bool:
    """Update note with calibrated magnet link through NoteService."""
    return _apply_calibrated_magnet(_note_deps(), note_id, new_magnet_link, filename)


def update_note_with_calibrated_dns(note_id: int, calibrated_results: list[dict[str, Any]]) -> bool:
    """Update note with multiple calibrated magnet links through NoteService."""
    return _apply_calibrated_magnets(_note_deps(), note_id, calibrated_results)
