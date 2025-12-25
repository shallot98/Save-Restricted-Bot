"""
Note Entity
===========

Domain entity representing a saved message/note.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List

from src.core.utils.datetime_utils import parse_db_datetime


@dataclass
class Note:
    """
    Note entity representing a saved message

    Attributes:
        id: Unique identifier
        user_id: Owner user ID
        source_chat_id: Source chat/channel ID
        source_name: Source chat name
        message_text: Message text content
        timestamp: Creation timestamp
        media_type: Type of media (photo, video, document, etc.)
        media_path: Primary media file path
        media_paths: List of media paths for media groups
        media_group_id: Telegram media group ID
        magnet_link: Associated magnet link
        filename: Extracted filename from magnet
        is_favorite: Favorite flag
    """

    id: int
    user_id: int
    source_chat_id: str
    source_name: Optional[str]
    message_text: Optional[str]
    timestamp: datetime
    media_type: Optional[str] = None
    media_path: Optional[str] = None
    media_paths: List[str] = field(default_factory=list)
    media_group_id: Optional[str] = None
    magnet_link: Optional[str] = None
    filename: Optional[str] = None
    is_favorite: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> "Note":
        """Create Note from dictionary"""
        parsed_timestamp = parse_db_datetime(data.get("timestamp"))
        return cls(
            id=data["id"],
            user_id=data["user_id"],
            source_chat_id=data["source_chat_id"],
            source_name=data.get("source_name"),
            message_text=data.get("message_text"),
            timestamp=parsed_timestamp or datetime.now(),
            media_type=data.get("media_type"),
            media_path=data.get("media_path"),
            media_paths=data.get("media_paths", []),
            media_group_id=data.get("media_group_id"),
            magnet_link=data.get("magnet_link"),
            filename=data.get("filename"),
            is_favorite=bool(data.get("is_favorite", 0)),
        )

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "source_chat_id": self.source_chat_id,
            "source_name": self.source_name,
            "message_text": self.message_text,
            "timestamp": self.timestamp,
            "media_type": self.media_type,
            "media_path": self.media_path,
            "media_paths": self.media_paths,
            "media_group_id": self.media_group_id,
            "magnet_link": self.magnet_link,
            "filename": self.filename,
            "is_favorite": self.is_favorite,
        }

    @property
    def has_media(self) -> bool:
        """Check if note has media"""
        return bool(self.media_path or self.media_paths)

    @property
    def has_magnet(self) -> bool:
        """Check if note has magnet link"""
        return bool(self.magnet_link)


@dataclass
class NoteCreate:
    """
    Data transfer object for creating a new note

    Separates creation data from entity to follow
    Command Query Responsibility Segregation (CQRS).
    """

    user_id: int
    source_chat_id: str
    source_name: Optional[str]
    message_text: Optional[str]
    media_type: Optional[str] = None
    media_path: Optional[str] = None
    media_paths: Optional[List[str]] = None
    media_group_id: Optional[str] = None


@dataclass
class NoteFilter:
    """
    Filter criteria for querying notes

    Supports pagination and various filter options.
    """

    user_id: Optional[int] = None
    source_chat_id: Optional[str] = None
    search_query: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    favorite_only: bool = False
    limit: int = 50
    offset: int = 0
