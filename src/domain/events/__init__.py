"""
Domain Events
=============

Events that represent significant domain occurrences.
Used for loose coupling between domain components.
"""

from src.domain.events.base import DomainEvent
from src.domain.events.note_events import (
    NoteCreated,
    NoteDeleted,
    NoteMagnetUpdated,
)

__all__ = [
    "DomainEvent",
    "NoteCreated",
    "NoteDeleted",
    "NoteMagnetUpdated",
]
