"""
Unit tests for peer cache helpers.
"""

from __future__ import annotations

from bot.utils import peer


class TestPeerCacheHelpers:
    def setup_method(self) -> None:
        peer.cached_dest_peers.clear()
        peer.failed_peers.clear()

    def test_mark_dest_cached_sets_and_clears_failed(self) -> None:
        peer.mark_peer_failed("123")
        assert peer.should_retry_peer("123") is False

        peer.mark_dest_cached("123")
        assert peer.is_dest_cached("123") is True
        assert peer.should_retry_peer("123") is True

