"""
Datetime Utilities
=================

Small helpers for parsing/formatting datetimes stored in SQLite as strings.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo

DB_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

# Timestamps are stored as naive local-time strings. Any query that compares
# against "now" must use this same basis -- notably NOT SQLite's datetime('now'),
# which is always UTC and would therefore be offset by the zone's UTC offset.
DB_TIMEZONE = ZoneInfo("Asia/Shanghai")


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


def db_now() -> datetime:
    """Current time on the same basis used for stored timestamps."""
    return datetime.now(DB_TIMEZONE)


def db_cutoff(seconds_ago: float) -> str:
    """Storage-formatted timestamp ``seconds_ago`` before now.

    Use this for "within the last N seconds" comparisons instead of SQLite's
    ``datetime('now', '-N seconds')``, which evaluates in UTC and would widen
    the window by the storage timezone's UTC offset.
    """
    return format_db_datetime(db_now() - timedelta(seconds=seconds_ago))
