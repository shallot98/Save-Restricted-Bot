"""Models for Telegram history copy runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

DEFAULT_BATCH_SIZE = 100
DEFAULT_SESSION_NAME = "history_copy"
DEFAULT_STATE_DB_PATH = Path("data/history_copy_state.db")
DEFAULT_MAX_FLOOD_RETRIES = 3
DEFAULT_RATE_LIMIT_DELAY = 1.0
DEFAULT_HOURLY_SEND_BUDGET = 1800
DEFAULT_BUDGET_WINDOW_SECONDS = 3600
DEFAULT_FAILURE_THRESHOLD = 3
DEFAULT_FAILURE_COOLDOWN_SECONDS = 300.0
DEFAULT_FLOODWAIT_BUFFER_SECONDS = 1.0
MAX_FAILURE_DETAILS = 50


@dataclass(frozen=True)
class HistoryCopySettings:
    """Resolved configuration for one history copy run."""

    source_chat_ref: str
    dest_chat_ref: str
    source_chat_id: str
    dest_chat_id: str
    state_db_path: Path = DEFAULT_STATE_DB_PATH
    batch_size: int = DEFAULT_BATCH_SIZE
    history_limit: Optional[int] = None
    max_flood_retries: int = DEFAULT_MAX_FLOOD_RETRIES
    rate_limit_delay: float = DEFAULT_RATE_LIMIT_DELAY
    hourly_send_budget: int = DEFAULT_HOURLY_SEND_BUDGET
    budget_window_seconds: int = DEFAULT_BUDGET_WINDOW_SECONDS
    failure_threshold: int = DEFAULT_FAILURE_THRESHOLD
    failure_cooldown_seconds: float = DEFAULT_FAILURE_COOLDOWN_SECONDS
    floodwait_buffer_seconds: float = DEFAULT_FLOODWAIT_BUFFER_SECONDS


@dataclass
class HistoryCopyStats:
    """Runtime counters for one copy run."""

    scanned_count: int = 0
    copied_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    failed_message_ids: list[int] = field(default_factory=list)

    def record_failure(self, message_id: int) -> None:
        self.failed_count += 1
        if len(self.failed_message_ids) < MAX_FAILURE_DETAILS:
            self.failed_message_ids.append(message_id)

    def summary(self) -> str:
        return (
            f"scanned={self.scanned_count} copied={self.copied_count} "
            f"skipped={self.skipped_count} failed={self.failed_count}"
        )


class HistoryCopyFatalError(RuntimeError):
    """Abort the whole history copy run."""
