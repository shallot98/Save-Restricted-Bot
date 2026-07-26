"""
Database Module - 纯兼容外观，零实现，计划 Phase 4 删除

Phase 3 收尾后本模块已不含任何实现体。四组旧 API 的实现全部住在
``src.infrastructure.persistence``：

- ``init_database``            → ``...persistence.sqlite.bootstrap``
- note 侧（add_note 等）        → ``...persistence.legacy.note_facade``
- auth 侧（verify_user 等）     → ``...persistence.legacy.auth``
- calibration 侧               → ``...persistence.legacy.calibration``

对应的根模块 ``database_notes.py`` / ``database_note_requests.py`` /
``database_auth.py`` / ``database_calibration.py`` 均已删除。这里只剩「旧 import
路径 → 新位置」的转接与位置参数适配。

**为什么还没删**：仍有 8 个生产消费方（``main.py``、``web/routes/{admin,auth,
media_cache}.py``、``web/utils/storage.py``、``bot/services/{calibration_manager,
calibration_scheduler}.py``、``bot/utils/media_cleanup.py``）。逐个改到权威源属
Phase 4，且其中 3 个在 ``web/routes/`` 下——本轮有并行改动，不宜同时动。

拆桥时一并删除的零引用函数（全仓 rg 复核）：``get_note_count`` /
``get_sources`` / ``update_note`` / ``update_magnet_link`` / ``delete_note`` /
``toggle_favorite`` / ``update_note_with_calibrated_dn``。现役调用方全部走
``NoteService`` 上的同名方法。

For new code, prefer using:
    from src.infrastructure.persistence.repositories import SQLiteNoteRepository
    from src.domain.entities import Note, NoteCreate
"""

import logging
from typing import Any, Optional

from src.core.config import settings
from composition.container import get_container, get_note_service
from src.core.utils.datetime_utils import DB_TIMEZONE
from src.infrastructure.persistence.legacy import (
    CalibrationDeps,
    CalibrationTaskCreate,
    CalibrationTaskQuery,
    CalibrationTaskUpdate,
    LegacyNoteCreateRequest,
    LegacyNoteQuery,
    NoteCompatibilityDeps,
    legacy_note_create_request,
    legacy_note_query,
)
from src.infrastructure.persistence.legacy import add_calibration_task as _add_calibration_task
from src.infrastructure.persistence.legacy import (
    clear_completed_calibration_tasks as _clear_completed_calibration_tasks,
)
from src.infrastructure.persistence.legacy import delete_calibration_task as _delete_calibration_task
from src.infrastructure.persistence.legacy import (
    delete_calibration_tasks_by_note_id as _delete_calibration_tasks_by_note_id,
)
from src.infrastructure.persistence.legacy import get_all_calibration_tasks as _get_all_calibration_tasks
from src.infrastructure.persistence.legacy import get_calibration_config as _get_calibration_config
from src.infrastructure.persistence.legacy import get_calibration_stats as _get_calibration_stats
from src.infrastructure.persistence.legacy import get_pending_calibration_tasks as _get_pending_calibration_tasks
from src.infrastructure.persistence.legacy import update_calibration_config as _update_calibration_config
from src.infrastructure.persistence.legacy import update_calibration_task as _update_calibration_task
from src.infrastructure.persistence.legacy import update_password as _update_password
from src.infrastructure.persistence.legacy import verify_user as _verify_user
from src.infrastructure.persistence.legacy.note_facade import (  # noqa: F401  (兼容再导出)
    _normalize_note_identity,
    _note_to_legacy_dict,
    _parse_media_paths,
)
from src.infrastructure.persistence.legacy.note_facade import add_note as _add_note
from src.infrastructure.persistence.legacy.note_facade import (
    apply_calibrated_magnets as _apply_calibrated_magnets,
)
from src.infrastructure.persistence.legacy.note_facade import get_note_by_id as _get_note_by_id
from src.infrastructure.persistence.legacy.note_facade import get_notes as _get_notes
from src.infrastructure.persistence.sqlite.bootstrap import init_database as _init_database
from src.infrastructure.persistence.sqlite.connection import get_db_connection

logger = logging.getLogger(__name__)

# China timezone -- single source of truth lives in datetime_utils.DB_TIMEZONE.
CHINA_TZ = DB_TIMEZONE

# Path constants for backward compatibility
DATA_DIR = str(settings.paths.data_dir)
DATABASE_FILE = str(settings.paths.data_dir / 'notes.db')


def init_database() -> None:
    """Initialize database - delegates to src.infrastructure.persistence."""
    _init_database()


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


def get_note_by_id(note_id: int) -> Optional[dict[str, Any]]:
    """Get note by ID through the concrete repository."""
    return _get_note_by_id(_note_deps(), note_id)


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


def update_note_with_calibrated_dns(note_id: int, calibrated_results: list[dict[str, Any]]) -> bool:
    """Update note with multiple calibrated magnet links through NoteService."""
    return _apply_calibrated_magnets(_note_deps(), note_id, calibrated_results)
