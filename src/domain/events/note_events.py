"""
Note Domain Events
==================

Events related to note operations.
"""

from dataclasses import dataclass
from typing import Optional

from src.domain.events.base import DomainEvent


@dataclass
class NoteCreated(DomainEvent):
    """Event raised when a note is created"""

    note_id: int = 0
    user_id: int = 0
    source_chat_id: str = ""
    has_media: bool = False
    has_magnet: bool = False


@dataclass
class NoteDeleted(DomainEvent):
    """Event raised when a note is deleted"""

    note_id: int = 0
    user_id: int = 0


@dataclass
class NoteMagnetUpdated(DomainEvent):
    """Event raised when a note's magnet link is updated"""

    note_id: int = 0
    info_hash: str = ""
    filename: Optional[str] = None
