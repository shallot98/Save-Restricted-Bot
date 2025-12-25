"""
Unit tests for FilterService.extract_content.
"""

from __future__ import annotations

from src.domain.entities.watch import WatchTask
from src.domain.services.filter_service import FilterService


class TestFilterServiceExtractContent:
    def test_returns_original_when_no_patterns(self) -> None:
        task = WatchTask(source="s", dest=None, extract_patterns=[])
        assert FilterService.extract_content(task, "hello") == "hello"

    def test_flattens_capturing_groups(self) -> None:
        task = WatchTask(source="s", dest=None, extract_patterns=[r"(a)(b)"])
        assert FilterService.extract_content(task, "ab") == "a\nb"

    def test_deduplicates_preserving_order(self) -> None:
        task = WatchTask(source="s", dest=None, extract_patterns=[r"[ab]"])
        assert FilterService.extract_content(task, "aab") == "a\nb"

    def test_does_not_append_dn_to_magnet(self) -> None:
        text = "Some title\nmagnet:?xt=urn:btih:ABCDEF1234567890ABCDEF1234567890ABCDEF12"
        task = WatchTask(source="s", dest=None, extract_patterns=[r"magnet:\?xt=urn:btih:[A-Za-z0-9]{40}"])
        extracted = FilterService.extract_content(task, text)
        assert extracted is not None
        assert "&dn=" not in extracted

