"""
告警规则引擎（轻量）

当前用于表达阈值与速率规则，供上层根据指标/事件结果触发告警。
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, Optional, Protocol


class AlertRule(Protocol):
    def should_alert(self) -> bool:
        ...


@dataclass(frozen=True)
class ThresholdRule:
    """阈值规则：value >= threshold 触发"""

    value: float
    threshold: float

    def should_alert(self) -> bool:
        return self.value >= self.threshold


class RateRule:
    """
    速率规则：在窗口内事件数 >= threshold_count 触发

    典型用法：
        rule = RateRule(window_seconds=60, threshold_count=10)
        rule.record()
        if rule.should_alert(): ...
    """

    def __init__(self, *, window_seconds: int, threshold_count: int) -> None:
        self._window_seconds = max(int(window_seconds), 1)
        self._threshold_count = max(int(threshold_count), 1)
        self._events: Deque[float] = deque()

    def record(self, *, at_epoch: Optional[float] = None) -> None:
        now = time.time() if at_epoch is None else float(at_epoch)
        self._events.append(now)
        self._prune(now_epoch=now)

    def should_alert(self) -> bool:
        now = time.time()
        self._prune(now_epoch=now)
        return len(self._events) >= self._threshold_count

    def _prune(self, *, now_epoch: float) -> None:
        cutoff = now_epoch - self._window_seconds
        while self._events and self._events[0] < cutoff:
            self._events.popleft()

