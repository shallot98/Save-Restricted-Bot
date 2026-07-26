"""
Calibration Scheduler Interface
===============================

Narrow port for the magnet calibration scheduler.

`src.application` 只需要「排队校准」这一小片能力，实现位于 `bot/services/
calibration_manager.py`。这里只声明被真实调用到的三个方法，不搬运实现类的
完整方法面（见 docs/ARCHITECTURE_REFACTOR_REPORT_2026-07-26.md §5.2）。
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Protocol, runtime_checkable


@runtime_checkable
class CalibrationScheduler(Protocol):
    """Port for scheduling magnet calibration work."""

    def is_enabled(self) -> bool:
        """Whether automatic calibration is currently enabled."""
        ...

    def should_calibrate_note(self, note: Dict[str, Any]) -> bool:
        """Whether the given note payload qualifies for calibration."""
        ...

    def add_note_to_calibration_queue(self, note_id: int, force: bool = False) -> bool:
        """Enqueue a note for calibration. Returns True when queued."""
        ...


#: 组合根注入的惰性提供者：未装配时返回 None，调用方必须显式处理。
CalibrationSchedulerProvider = Callable[[], Optional[CalibrationScheduler]]
