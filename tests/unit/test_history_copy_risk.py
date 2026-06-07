from __future__ import annotations

from bot.services.history_copy_risk import HistoryCopyRiskConfig, HistoryCopyRiskController


class _FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _make_controller(
    clock: _FakeClock,
    *,
    min_send_interval_seconds: float = 0.0,
    hourly_send_budget: int = 10,
    budget_window_seconds: int = 3600,
    failure_threshold: int = 3,
    failure_cooldown_seconds: float = 30.0,
    floodwait_buffer_seconds: float = 1.0,
) -> HistoryCopyRiskController:
    return HistoryCopyRiskController(
        HistoryCopyRiskConfig(
            min_send_interval_seconds=min_send_interval_seconds,
            hourly_send_budget=hourly_send_budget,
            budget_window_seconds=budget_window_seconds,
            failure_threshold=failure_threshold,
            failure_cooldown_seconds=failure_cooldown_seconds,
            floodwait_buffer_seconds=floodwait_buffer_seconds,
        ),
        time_func=clock.time,
        sleep_func=clock.sleep,
    )


def test_min_send_interval_forces_wait() -> None:
    clock = _FakeClock()
    controller = _make_controller(clock, min_send_interval_seconds=2.5)

    controller.wait_for_outbound_slot("复制消息")
    controller.record_success("复制消息")
    controller.wait_for_outbound_slot("复制消息")

    assert clock.sleeps == [2.5]


def test_hourly_budget_waits_until_window_recovers() -> None:
    clock = _FakeClock()
    controller = _make_controller(
        clock,
        hourly_send_budget=2,
        budget_window_seconds=60,
    )

    controller.record_success("复制消息")
    clock.advance(1)
    controller.record_success("复制消息")
    clock.advance(1)
    controller.wait_for_outbound_slot("复制消息")

    assert clock.sleeps == [58.0]


def test_failure_threshold_enters_cooldown() -> None:
    clock = _FakeClock()
    controller = _make_controller(
        clock,
        failure_threshold=2,
        failure_cooldown_seconds=30,
    )

    controller.record_failure("复制消息", RuntimeError("boom-1"))
    controller.record_failure("复制消息", RuntimeError("boom-2"))
    controller.wait_for_outbound_slot("复制消息")

    assert clock.sleeps == [30.0]


def test_floodwait_updates_cooldown_and_recovers() -> None:
    clock = _FakeClock()
    controller = _make_controller(clock, floodwait_buffer_seconds=2.0)

    controller.record_flood_wait("复制媒体组", 5)
    controller.wait_for_outbound_slot("复制媒体组")

    assert clock.sleeps == [7.0]


def test_success_resets_failure_streak() -> None:
    clock = _FakeClock()
    controller = _make_controller(
        clock,
        failure_threshold=2,
        failure_cooldown_seconds=15,
    )

    controller.record_failure("复制消息", RuntimeError("boom-1"))
    controller.record_success("复制消息")
    controller.record_failure("复制消息", RuntimeError("boom-2"))
    controller.wait_for_outbound_slot("复制消息")

    assert clock.sleeps == []
