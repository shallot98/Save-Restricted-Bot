"""Owner allow-list enforcement for bot-side handlers.

These handlers drive the owner's personal Telegram account, so the important
property is the *deny* direction: an unresolvable owner must reject everything
rather than fall open.
"""

from __future__ import annotations

import asyncio
import inspect
from types import SimpleNamespace

import pytest

from bot.handlers import authorization
from bot.handlers.authorization import (
    build_owner_filter,
    parse_owner_ids,
    resolve_owner_ids,
)


def _match(owner_filter, sender_id) -> bool:
    """Evaluate the filter the way Pyrogram's dispatcher would.

    ``filters.create`` returns the predicate's value directly for a sync
    callable and a coroutine for an async one, so accept either.
    """
    from_user = None if sender_id is None else SimpleNamespace(id=sender_id)
    update = SimpleNamespace(from_user=from_user)
    result = owner_filter(None, update)
    if inspect.isawaitable(result):
        return asyncio.run(result)
    return result


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, frozenset()),
        ("", frozenset()),
        ("   ", frozenset()),
        ("123", frozenset({123})),
        ("123,456", frozenset({123, 456})),
        ("123 456; 789", frozenset({123, 456, 789})),
        (" 123 , 123 ", frozenset({123})),
        (456, frozenset({456})),
    ],
)
def test_parse_owner_ids_accepts_separator_variants(raw, expected) -> None:
    assert parse_owner_ids(raw) == expected


def test_parse_owner_ids_skips_unparsable_fragment_without_dropping_the_rest() -> None:
    assert parse_owner_ids("123, not-an-id, 456") == frozenset({123, 456})


def test_filter_accepts_only_listed_owners() -> None:
    owner_filter = build_owner_filter(frozenset({123, 456}))

    assert _match(owner_filter, 123) is True
    assert _match(owner_filter, 456) is True
    assert _match(owner_filter, 999) is False


def test_filter_without_owner_denies_everyone() -> None:
    """An unresolved owner must not leave the bot open."""
    owner_filter = build_owner_filter(frozenset())

    assert _match(owner_filter, 123) is False
    assert _match(owner_filter, 999) is False


def test_filter_denies_update_without_sender() -> None:
    owner_filter = build_owner_filter(frozenset({123}))

    assert _match(owner_filter, None) is False


def test_resolve_prefers_configured_owner_over_session(monkeypatch) -> None:
    monkeypatch.setattr(
        authorization, "_owner_ids_from_settings", lambda: frozenset({111})
    )
    acc = SimpleNamespace(get_me=lambda: SimpleNamespace(id=222))

    assert resolve_owner_ids(acc) == frozenset({111})


def test_resolve_falls_back_to_user_session_identity(monkeypatch) -> None:
    monkeypatch.setattr(authorization, "_owner_ids_from_settings", frozenset)
    acc = SimpleNamespace(get_me=lambda: SimpleNamespace(id=222))

    assert resolve_owner_ids(acc) == frozenset({222})


def test_resolve_returns_empty_when_nothing_is_configured(monkeypatch) -> None:
    monkeypatch.setattr(authorization, "_owner_ids_from_settings", frozenset)

    assert resolve_owner_ids(None) == frozenset()


def test_resolve_returns_empty_when_session_lookup_fails(monkeypatch) -> None:
    """A failing get_me() must deny rather than fall open."""
    monkeypatch.setattr(authorization, "_owner_ids_from_settings", frozenset)

    def _boom():
        raise RuntimeError("not connected")

    assert resolve_owner_ids(SimpleNamespace(get_me=_boom)) == frozenset()
