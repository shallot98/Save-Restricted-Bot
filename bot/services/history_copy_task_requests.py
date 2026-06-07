"""Request parsing for history-copy task manager."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


_CREATE_FIELD_NAMES = (
    "source_chat_ref",
    "source_name",
    "dest_chat_ref",
    "dest_name",
    "history_limit",
)


@dataclass(frozen=True)
class HistoryCopyTaskCreateRequest:
    user_id: str
    source_chat_ref: str
    source_name: str
    dest_chat_ref: str
    dest_name: str
    history_limit: int | None


def history_copy_task_create_request(
    request: HistoryCopyTaskCreateRequest | str | None,
    legacy_args: tuple[Any, ...],
    legacy_fields: dict[str, Any],
) -> HistoryCopyTaskCreateRequest:
    if isinstance(request, HistoryCopyTaskCreateRequest):
        if legacy_args or legacy_fields:
            raise TypeError("add_task received both request object and legacy arguments")
        return request

    fields = dict(legacy_fields)
    if request is None:
        if "user_id" not in fields:
            raise TypeError("add_task requires user_id")
        request = fields.pop("user_id")
    if len(legacy_args) > len(_CREATE_FIELD_NAMES):
        raise TypeError("add_task received too many positional arguments")

    values = dict(zip(_CREATE_FIELD_NAMES, legacy_args))
    values.update(fields)
    return HistoryCopyTaskCreateRequest(user_id=str(request), **values)
