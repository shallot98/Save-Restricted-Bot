"""SQLite implementation of the note repository."""

from __future__ import annotations

import re

from src.domain.repositories.note_repository import NoteRepository
from src.infrastructure.persistence.repositories.note_repository_calibration import (
    SQLiteNoteCalibrationMixin,
)
from src.infrastructure.persistence.repositories.note_repository_crud import SQLiteNoteCrudMixin
from src.infrastructure.persistence.repositories.note_repository_duplicates import (
    SQLiteNoteDuplicateMixin,
)
from src.infrastructure.persistence.repositories.note_repository_rows import SQLiteNoteRowMixin
from src.infrastructure.persistence.repositories.note_repository_search import SQLiteNoteSearchMixin
from src.infrastructure.persistence.sqlite.connection import get_db_connection


class SQLiteNoteRepository(
    SQLiteNoteCrudMixin,
    SQLiteNoteDuplicateMixin,
    SQLiteNoteSearchMixin,
    SQLiteNoteCalibrationMixin,
    SQLiteNoteRowMixin,
    NoteRepository,
):
    """SQLite-backed NoteRepository implementation."""

    @staticmethod
    def _get_db_connection():
        return get_db_connection()

    @staticmethod
    def _regex():
        return re
