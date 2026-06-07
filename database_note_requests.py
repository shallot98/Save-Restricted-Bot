"""Compatibility argument parsing for legacy note database functions."""

from __future__ import annotations

from typing import Any

from database_notes import LegacyNoteCreateRequest, LegacyNoteQuery


_CREATE_FIELDS = [
    "source_chat_id",
    "source_name",
    "message_text",
    "media_type",
    "media_path",
    "media_paths",
    "media_group_id",
]

_QUERY_FIELDS = [
    "source_chat_id",
    "search_query",
    "date_from",
    "date_to",
    "favorite_only",
    "limit",
    "offset",
]


def legacy_note_create_request(
    request: LegacyNoteCreateRequest | Any,
    legacy_args: tuple,
    legacy_kwargs: dict,
) -> LegacyNoteCreateRequest:
    if isinstance(request, LegacyNoteCreateRequest):
        if legacy_args or legacy_kwargs:
            raise TypeError("add_note received both request object and legacy arguments")
        return request

    if request is None:
        if "user_id" not in legacy_kwargs:
            raise TypeError("add_note requires user_id")
        request = legacy_kwargs.pop("user_id")

    if len(legacy_args) > len(_CREATE_FIELDS):
        raise TypeError("add_note received too many positional arguments")
    values = dict(zip(_CREATE_FIELDS, legacy_args))
    values.update(legacy_kwargs)
    return LegacyNoteCreateRequest(user_id=request, **values)


def legacy_note_query(
    query: LegacyNoteQuery | Any = None,
    legacy_args: tuple = (),
    legacy_kwargs: dict | None = None,
) -> LegacyNoteQuery:
    legacy_kwargs = legacy_kwargs or {}
    if isinstance(query, LegacyNoteQuery):
        if legacy_args or legacy_kwargs:
            raise TypeError("query function received both query object and legacy arguments")
        return query

    values = {}
    if query is not None:
        values["user_id"] = query
    elif "user_id" in legacy_kwargs:
        values["user_id"] = legacy_kwargs.pop("user_id")

    if len(legacy_args) > len(_QUERY_FIELDS):
        raise TypeError("query function received too many positional arguments")
    values.update(dict(zip(_QUERY_FIELDS, legacy_args)))
    values.update(legacy_kwargs)
    return LegacyNoteQuery(**values)
