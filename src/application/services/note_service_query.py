"""Query helpers for NoteService."""

from __future__ import annotations

import logging
from dataclasses import dataclass, fields
from typing import Optional

from src.application.dto import NoteDTO, PaginatedResult
from src.core.exceptions import NotFoundError
from src.domain.entities.note import Note, NoteFilter

logger = logging.getLogger(__name__)

NOTE_QUERY_OPTION_NAMES = (
    "user_id",
    "source_chat_id",
    "search_query",
    "date_from",
    "date_to",
    "favorite_only",
    "page",
    "page_size",
)


@dataclass(frozen=True)
class NoteQueryOptions:
    user_id: Optional[int] = None
    source_chat_id: Optional[str] = None
    search_query: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    favorite_only: bool = False
    page: int = 1
    page_size: int = 50

    @property
    def search_normalized(self) -> str:
        return (self.search_query or "").strip()

    def to_filter(self, *, include_pagination: bool = True) -> NoteFilter:
        limit = self.page_size if include_pagination else 50
        offset = (self.page - 1) * self.page_size if include_pagination else 0
        return NoteFilter(
            user_id=self.user_id,
            source_chat_id=self.source_chat_id,
            search_query=self.search_normalized or None,
            date_from=self.date_from,
            date_to=self.date_to,
            favorite_only=self.favorite_only,
            limit=limit,
            offset=offset,
        )


class NoteServiceQueryMixin:
    def get_note(self, note_id: int) -> NoteDTO:
        return NoteDTO.from_entity(self._require_note(note_id))

    def get_note_entity(self, note_id: int) -> Note:
        return self._require_note(note_id)

    def get_notes(self, *args, query: NoteQueryOptions | None = None, **filters) -> PaginatedResult:
        options = _resolve_note_query_options(args, query, filters)
        cache_key = self._note_list_cache_key(options)
        if cache_key:
            cached_result = self._get_cache().get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit: notes list page={options.page}")
                return cached_result

        result = self._search_note_dtos(options)
        if cache_key:
            self._get_cache().set(cache_key, result, ttl=300.0)
            logger.debug(f"Cache set: notes list page={options.page}")
        return result

    def get_note_entities(self, *args, query: NoteQueryOptions | None = None, **filters) -> list[Note]:
        options = _resolve_note_query_options(args, query, filters)
        notes, _total = self._repository.search(options.to_filter())
        return notes

    def count_notes(self, *args, query: NoteQueryOptions | None = None, **filters) -> int:
        options = _resolve_note_query_options(args, query, filters)
        filter_criteria = options.to_filter(include_pagination=False)
        if hasattr(self._repository, "count"):
            return self._repository.count(filter_criteria)
        notes, total = self._repository.search(filter_criteria)
        return total if total else len(notes)

    def _require_note(self, note_id: int) -> Note:
        note = self._repository.get_by_id(note_id)
        if note:
            return note
        raise NotFoundError(
            f"Note not found: {note_id}",
            resource_type="Note",
            resource_id=note_id,
        )

    def _note_list_cache_key(self, options: NoteQueryOptions) -> str | None:
        if not _should_cache_note_query(options):
            return None
        user_part = str(options.user_id) if options.user_id is not None else "all"
        source_part = options.source_chat_id or "all"
        favorite_part = "fav" if options.favorite_only else "all"
        return f"list:{user_part}:v2:{source_part}:{favorite_part}:{options.page}:{options.page_size}"

    def _search_note_dtos(self, options: NoteQueryOptions) -> PaginatedResult:
        notes, total = self._repository.search(options.to_filter())
        return PaginatedResult(
            items=[NoteDTO.from_entity(note) for note in notes],
            total=total,
            page=options.page,
            page_size=options.page_size,
        )


def _resolve_note_query_options(args, query, filters) -> NoteQueryOptions:
    if query is not None and (args or filters):
        raise TypeError("query cannot be combined with positional or keyword filters")
    if isinstance(query, NoteQueryOptions):
        return query
    if query is not None:
        raise TypeError("query must be a NoteQueryOptions instance")
    return _build_note_query_options(args, filters)


def _build_note_query_options(args, filters) -> NoteQueryOptions:
    if len(args) > len(NOTE_QUERY_OPTION_NAMES):
        raise TypeError(f"expected at most {len(NOTE_QUERY_OPTION_NAMES)} positional filters")
    values = {field.name: field.default for field in fields(NoteQueryOptions)}
    for name, value in zip(NOTE_QUERY_OPTION_NAMES, args):
        if name in filters:
            raise TypeError(f"got multiple values for argument '{name}'")
        values[name] = value
    unknown = set(filters) - set(values)
    if unknown:
        raise TypeError(f"unknown note query filter: {sorted(unknown)[0]}")
    values.update(filters)
    return NoteQueryOptions(**values)


def _should_cache_note_query(options: NoteQueryOptions) -> bool:
    return (
        not options.search_normalized
        and not options.date_from
        and not options.date_to
        and 1 <= options.page <= 10
    )
