"""
Data Transfer Objects
=====================

DTOs for transferring data between layers.
"""

from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime

from src.core.utils.datetime_utils import format_db_datetime


@dataclass
class NoteDTO:
    """Note data transfer object for API responses"""

    id: int
    user_id: int
    source_chat_id: str
    source_name: Optional[str]
    message_text: Optional[str]
    timestamp: str
    media_type: Optional[str]
    media_path: Optional[str]
    media_paths: List[str]
    magnet_link: Optional[str]
    filename: Optional[str]
    is_favorite: bool

    @classmethod
    def from_entity(cls, note) -> "NoteDTO":
        """Create DTO from Note entity"""
        timestamp_str = (
            format_db_datetime(note.timestamp)
            if isinstance(note.timestamp, datetime)
            else str(note.timestamp)
        )
        return cls(
            id=note.id,
            user_id=note.user_id,
            source_chat_id=note.source_chat_id,
            source_name=note.source_name,
            message_text=note.message_text,
            timestamp=timestamp_str,
            media_type=note.media_type,
            media_path=note.media_path,
            media_paths=note.media_paths or [],
            magnet_link=note.magnet_link,
            filename=note.filename,
            is_favorite=note.is_favorite,
        )


@dataclass
class PaginatedResult:
    """Paginated result wrapper"""

    items: List
    total: int
    page: int
    page_size: int

    @property
    def total_pages(self) -> int:
        return (self.total + self.page_size - 1) // self.page_size

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def has_prev(self) -> bool:
        return self.page > 1
