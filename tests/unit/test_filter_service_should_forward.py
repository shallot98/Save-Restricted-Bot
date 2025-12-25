"""
Unit tests for FilterService.should_forward.
"""

from __future__ import annotations

from src.domain.entities.watch import WatchTask
from src.domain.services.filter_service import FilterService


class TestFilterServiceShouldForward:
    def test_forwards_when_no_filters(self) -> None:
        task = WatchTask(source="s", dest=None)
        assert FilterService.should_forward(task, "hello") is True

    def test_whitelist_requires_match(self) -> None:
        task = WatchTask(source="s", dest=None, whitelist=["foo"])
        assert FilterService.should_forward(task, "foo bar") is True
        assert FilterService.should_forward(task, "bar") is False

    def test_blacklist_blocks_match(self) -> None:
        task = WatchTask(source="s", dest=None, blacklist=["spam"])
        assert FilterService.should_forward(task, "this is spam") is False
        assert FilterService.should_forward(task, "this is fine") is True

    def test_blacklist_takes_precedence_over_whitelist(self) -> None:
        task = WatchTask(source="s", dest=None, whitelist=["ok"], blacklist=["bad"])
        assert FilterService.should_forward(task, "ok but bad") is False

    def test_whitelist_regex_requires_match(self) -> None:
        task = WatchTask(source="s", dest=None, whitelist_regex=[r"\d+\s+USD"])
        assert FilterService.should_forward(task, "price 100 USD") is True
        assert FilterService.should_forward(task, "price unknown") is False

    def test_blacklist_regex_blocks_match(self) -> None:
        task = WatchTask(source="s", dest=None, blacklist_regex=[r"forbidden"])
        assert FilterService.should_forward(task, "forbidden content") is False
        assert FilterService.should_forward(task, "allowed") is True

    def test_invalid_whitelist_regex_causes_no_match(self) -> None:
        task = WatchTask(source="s", dest=None, whitelist_regex=["("])
        assert FilterService.should_forward(task, "anything") is False

    def test_invalid_blacklist_regex_is_ignored(self) -> None:
        task = WatchTask(source="s", dest=None, blacklist_regex=["("])
        assert FilterService.should_forward(task, "anything") is True

    def test_empty_message_text_blocks_when_whitelist_present(self) -> None:
        task = WatchTask(source="s", dest=None, whitelist=["a"])
        assert FilterService.should_forward(task, "") is False
