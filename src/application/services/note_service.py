"""Note application service."""

from __future__ import annotations

from src.application.services.note_service_cache import NoteServiceCacheMixin
from src.application.services.note_service_media import NoteServiceMediaMixin
from src.application.services.note_service_query import NoteServiceQueryMixin
from src.application.services.note_service_sources import NoteServiceSourcesMixin
from src.application.services.note_service_writes import NoteServiceWritesMixin
from src.domain.repositories.note_repository import NoteRepository


class NoteService(
    NoteServiceQueryMixin,
    NoteServiceWritesMixin,
    NoteServiceSourcesMixin,
    NoteServiceMediaMixin,
    NoteServiceCacheMixin,
):
    """Orchestrate note operations between presentation and domain layers."""

    def __init__(self, note_repository: NoteRepository) -> None:
        self._repository = note_repository
        self._cache = None
        self._storage_manager = None
