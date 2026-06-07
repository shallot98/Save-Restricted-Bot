"""Parameter objects for watch setup handlers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WatchSetupTarget:
    chat_id: int
    message_id: int
    user_id: str


@dataclass(frozen=True)
class WatchFilterOptions:
    whitelist: list[str]
    blacklist: list[str]
    whitelist_regex: list[str]
    blacklist_regex: list[str]


@dataclass(frozen=True)
class ForwardModeChoiceOptions:
    filters: WatchFilterOptions
    preserve_source: bool


@dataclass(frozen=True)
class ForwardWatchSetupOptions:
    filters: WatchFilterOptions
    preserve_source: bool
    forward_mode: str
    extract_patterns: list[str]
