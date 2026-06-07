"""Request objects for watch service mutations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class WatchTaskCreateRequest:
    user_id: str
    source_id: str
    dest_id: Optional[str] = None
    whitelist: Optional[list[str]] = None
    blacklist: Optional[list[str]] = None
    whitelist_regex: Optional[list[str]] = None
    blacklist_regex: Optional[list[str]] = None
    forward_mode: str = "full"
    record_mode: bool = False


def watch_task_create_request(
    request: WatchTaskCreateRequest | str | None,
    legacy_args: tuple,
    legacy_kwargs: dict,
) -> WatchTaskCreateRequest:
    if isinstance(request, WatchTaskCreateRequest):
        if legacy_args or legacy_kwargs:
            raise TypeError("add_watch_task received both request object and legacy arguments")
        return request

    if request is None:
        if "user_id" not in legacy_kwargs:
            raise TypeError("add_watch_task requires user_id")
        request = legacy_kwargs.pop("user_id")

    names = [
        "source_id",
        "dest_id",
        "whitelist",
        "blacklist",
        "whitelist_regex",
        "blacklist_regex",
        "forward_mode",
        "record_mode",
    ]
    if len(legacy_args) > len(names):
        raise TypeError("add_watch_task received too many positional arguments")

    values = dict(zip(names, legacy_args))
    values.update(legacy_kwargs)
    if "source_id" not in values:
        raise TypeError("add_watch_task requires source_id")
    return WatchTaskCreateRequest(user_id=str(request), **values)
