"""
Unit tests for legacy user_states proxy behavior.
"""

from __future__ import annotations

import pytest


class TestUserStatesProxy:
    def test_user_states_updates_updated_at_on_mutation(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import bot.utils.state_manager as sm

        tick = {"t": 0.0}

        def _fake_time() -> float:
            tick["t"] += 1.0
            return tick["t"]

        monkeypatch.setattr(sm.time, "time", _fake_time)

        sm._state_manager = sm.UserStateManager(ttl_seconds=3600, cleanup_interval=0, max_states=100)

        user_id = "u1"
        sm.user_states[user_id]["k"] = "v1"
        first = sm.get_state_manager()._states[user_id].updated_at

        sm.user_states[user_id]["k"] = "v2"
        second = sm.get_state_manager()._states[user_id].updated_at

        assert second > first

