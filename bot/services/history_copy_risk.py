"""Risk controls for Telegram history copy outbound actions."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable

from bot.utils.logger import get_logger

from .history_copy_models import HistoryCopySettings

MAX_RECENT_RISK_EVENTS = 20

logger = get_logger(__name__)


@dataclass(frozen=True)
class HistoryCopyRiskConfig:
    """Configurable risk policy for one history copy run."""

    min_send_interval_seconds: float
    hourly_send_budget: int
    budget_window_seconds: int
    failure_threshold: int
    failure_cooldown_seconds: float
    floodwait_buffer_seconds: float

    @classmethod
    def from_settings(cls, settings: HistoryCopySettings) -> "HistoryCopyRiskConfig":
        return cls(
            min_send_interval_seconds=settings.rate_limit_delay,
            hourly_send_budget=settings.hourly_send_budget,
            budget_window_seconds=settings.budget_window_seconds,
            failure_threshold=settings.failure_threshold,
            failure_cooldown_seconds=settings.failure_cooldown_seconds,
            floodwait_buffer_seconds=settings.floodwait_buffer_seconds,
        )


@dataclass
class _HistoryCopyRiskState:
    last_send_at: float | None = None
    cooldown_until: float = 0.0
    consecutive_failures: int = 0
    recent_send_timestamps: deque[float] = field(default_factory=deque)
    recent_events: deque[str] = field(
        default_factory=lambda: deque(maxlen=MAX_RECENT_RISK_EVENTS)
    )


class HistoryCopyRiskController:
    """Throttle outbound actions to reduce Telegram risk exposure."""

    def __init__(
        self,
        config: HistoryCopyRiskConfig,
        *,
        time_func: Callable[[], float] = time.monotonic,
        sleep_func: Callable[[float], None] = time.sleep,
    ) -> None:
        self._config = config
        self._state = _HistoryCopyRiskState()
        self._time = time_func
        self._sleep = sleep_func

    @classmethod
    def from_settings(cls, settings: HistoryCopySettings) -> "HistoryCopyRiskController":
        return cls(HistoryCopyRiskConfig.from_settings(settings))

    def wait_for_outbound_slot(self, operation_name: str, units: int = 1) -> None:
        pending_units = max(int(units), 1)
        waited = False
        while True:
            delay, reason = self._next_wait_reason(pending_units)
            if delay <= 0:
                if waited:
                    logger.info("🛡️ 风控冷却结束，恢复发送: operation=%s", operation_name)
                return
            waited = True
            self._remember_event(f"{reason}:{delay:.1f}s")
            logger.warning(
                "🛡️ 风控暂停发送: operation=%s reason=%s wait=%.1fs",
                operation_name,
                reason,
                delay,
            )
            self._sleep(delay)

    def record_success(self, operation_name: str, units: int = 1) -> None:
        now = self._time()
        self._trim_budget_window(now)
        for _ in range(max(int(units), 1)):
            self._state.recent_send_timestamps.append(now)
        self._state.last_send_at = now
        if self._state.consecutive_failures > 0:
            logger.info("🛡️ 发送恢复成功，清零连续失败: operation=%s", operation_name)
        self._state.consecutive_failures = 0

    def record_failure(self, operation_name: str, exc: Exception) -> None:
        if self._config.failure_threshold <= 0:
            return
        self._state.consecutive_failures += 1
        logger.warning(
            "🛡️ 记录连续失败: operation=%s failures=%s threshold=%s error=%s",
            operation_name,
            self._state.consecutive_failures,
            self._config.failure_threshold,
            type(exc).__name__,
        )
        if self._state.consecutive_failures < self._config.failure_threshold:
            return
        delay = max(self._config.failure_cooldown_seconds, 0.0)
        self._set_cooldown(delay)
        self._state.consecutive_failures = 0
        self._remember_event(f"failure_cooldown:{delay:.1f}s")
        logger.warning(
            "🛡️ 连续失败达到阈值，进入冷却: operation=%s cooldown=%.1fs",
            operation_name,
            delay,
        )

    def record_flood_wait(self, operation_name: str, wait_seconds: float) -> None:
        cooldown_seconds = max(float(wait_seconds), 1.0) + self._config.floodwait_buffer_seconds
        self._set_cooldown(cooldown_seconds)
        self._state.consecutive_failures = 0
        self._remember_event(f"floodwait:{cooldown_seconds:.1f}s")
        logger.warning(
            "🛡️ 捕获 FloodWait，交由风控层统一退避: operation=%s cooldown=%.1fs",
            operation_name,
            cooldown_seconds,
        )

    def summary(self) -> str:
        now = self._time()
        self._trim_budget_window(now)
        budget = "disabled"
        if self._config.hourly_send_budget > 0:
            budget = (
                f"{len(self._state.recent_send_timestamps)}/"
                f"{self._config.hourly_send_budget}"
            )
        cooldown_left = max(self._state.cooldown_until - now, 0.0)
        last_event = self._state.recent_events[-1] if self._state.recent_events else "none"
        return (
            f"budget={budget} consecutive_failures={self._state.consecutive_failures} "
            f"cooldown={cooldown_left:.1f}s last_event={last_event}"
        )

    def _next_wait_reason(self, units: int) -> tuple[float, str]:
        now = self._time()
        self._trim_budget_window(now)
        waits = [
            ("cooldown", max(self._state.cooldown_until - now, 0.0)),
            ("min_interval", self._min_interval_wait_seconds(now)),
            ("budget", self._budget_wait_seconds(now, units)),
        ]
        reason, delay = max(waits, key=lambda item: item[1])
        return delay, reason

    def _min_interval_wait_seconds(self, now: float) -> float:
        if self._state.last_send_at is None:
            return 0.0
        next_send_at = self._state.last_send_at + self._config.min_send_interval_seconds
        return max(next_send_at - now, 0.0)

    def _budget_wait_seconds(self, now: float, units: int) -> float:
        if self._config.hourly_send_budget <= 0:
            return 0.0
        required_units = min(max(units, 1), self._config.hourly_send_budget)
        available = self._config.hourly_send_budget - len(self._state.recent_send_timestamps)
        if available >= required_units:
            return 0.0
        over_budget_count = required_units - available
        expiration_index = min(
            max(over_budget_count - 1, 0),
            len(self._state.recent_send_timestamps) - 1,
        )
        expiration_at = (
            self._state.recent_send_timestamps[expiration_index]
            + self._config.budget_window_seconds
        )
        return max(expiration_at - now, 0.0)

    def _trim_budget_window(self, now: float) -> None:
        window = self._config.budget_window_seconds
        while self._state.recent_send_timestamps:
            oldest = self._state.recent_send_timestamps[0]
            if now - oldest < window:
                return
            self._state.recent_send_timestamps.popleft()

    def _set_cooldown(self, seconds: float) -> None:
        target = self._time() + max(seconds, 0.0)
        self._state.cooldown_until = max(self._state.cooldown_until, target)

    def _remember_event(self, event: str) -> None:
        self._state.recent_events.append(event)
