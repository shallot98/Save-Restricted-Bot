"""
Datetime Utilities
=================

Small helpers for parsing/formatting datetimes stored in SQLite as strings.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

DB_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def parse_db_datetime(value: Any) -> Optional[datetime]:
    """Parse a SQLite datetime field into a datetime.

    The project stores timestamps as text in the format ``YYYY-MM-DD HH:MM:SS``.
    Returns ``None`` when input is missing or invalid.
    """
    if value is None:
        return None

    if isinstance(value, datetime):
        return value

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return datetime.strptime(text, DB_DATETIME_FORMAT)
        except ValueError:
            pass

        try:
            normalized = f"{text[:-1]}+00:00" if text.endswith("Z") else text
            return datetime.fromisoformat(normalized)
        except ValueError:
            return None

    return None


def format_db_datetime(value: datetime) -> str:
    """Format datetime to the canonical SQLite storage string."""
    return value.strftime(DB_DATETIME_FORMAT)
