"""
Calibration Entity
==================

Domain entities for magnet link calibration.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum

from src.core.utils.datetime_utils import parse_db_datetime


class CalibrationStatus(str, Enum):
    """Calibration task status"""

    PENDING = "pending"
    RETRYING = "retrying"
    SUCCESS = "success"
    FAILED = "failed"


class FilterMode(str, Enum):
    """Calibration filter mode"""

    EMPTY_ONLY = "empty_only"
    ALL = "all"


@dataclass
class CalibrationTask:
    """
    Calibration task entity

    Represents a single magnet link calibration task.

    Attributes:
        id: Unique identifier
        note_id: Associated note ID
        magnet_hash: Magnet link info hash
        status: Current task status
        retry_count: Number of retry attempts
        last_attempt: Last attempt timestamp
        next_attempt: Scheduled next attempt
        error_message: Last error message
        created_at: Task creation timestamp
    """

    id: int
    note_id: int
    magnet_hash: str
    status: CalibrationStatus
    retry_count: int = 0
    last_attempt: Optional[datetime] = None
    next_attempt: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None

    @classmethod
    def from_dict(cls, data: dict) -> "CalibrationTask":
        """Create CalibrationTask from dictionary"""
        return cls(
            id=data["id"],
            note_id=data["note_id"],
            magnet_hash=data["magnet_hash"],
            status=CalibrationStatus(data["status"]),
            retry_count=data.get("retry_count", 0),
            last_attempt=parse_db_datetime(data.get("last_attempt")),
            next_attempt=parse_db_datetime(data.get("next_attempt")),
            error_message=data.get("error_message"),
            created_at=parse_db_datetime(data.get("created_at")),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "note_id": self.note_id,
            "magnet_hash": self.magnet_hash,
            "status": self.status.value,
            "retry_count": self.retry_count,
            "last_attempt": self.last_attempt,
            "next_attempt": self.next_attempt,
            "error_message": self.error_message,
            "created_at": self.created_at,
        }

    @property
    def can_retry(self) -> bool:
        """Check if task can be retried"""
        return self.status in (CalibrationStatus.PENDING, CalibrationStatus.RETRYING)


@dataclass
class CalibrationConfig:
    """
    Auto-calibration configuration

    Configures the automatic magnet link calibration behavior.
    """

    enabled: bool = False
    filter_mode: FilterMode = FilterMode.EMPTY_ONLY
    first_delay: int = 600  # seconds
    retry_delay_1: int = 3600
    retry_delay_2: int = 14400
    retry_delay_3: int = 28800
    max_retries: int = 3
    concurrent_limit: int = 5
    timeout_per_magnet: int = 30
    batch_timeout: int = 300

    @classmethod
    def from_dict(cls, data: dict) -> "CalibrationConfig":
        """Create CalibrationConfig from dictionary"""
        return cls(
            enabled=bool(data.get("enabled", 0)),
            filter_mode=FilterMode(data.get("filter_mode", "empty_only")),
            first_delay=data.get("first_delay", 600),
            retry_delay_1=data.get("retry_delay_1", 3600),
            retry_delay_2=data.get("retry_delay_2", 14400),
            retry_delay_3=data.get("retry_delay_3", 28800),
            max_retries=data.get("max_retries", 3),
            concurrent_limit=data.get("concurrent_limit", 5),
            timeout_per_magnet=data.get("timeout_per_magnet", 30),
            batch_timeout=data.get("batch_timeout", 300),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage"""
        return {
            "enabled": int(self.enabled),
            "filter_mode": self.filter_mode.value,
            "first_delay": self.first_delay,
            "retry_delay_1": self.retry_delay_1,
            "retry_delay_2": self.retry_delay_2,
            "retry_delay_3": self.retry_delay_3,
            "max_retries": self.max_retries,
            "concurrent_limit": self.concurrent_limit,
            "timeout_per_magnet": self.timeout_per_magnet,
            "batch_timeout": self.batch_timeout,
        }

    def get_retry_delay(self, retry_count: int) -> int:
        """Get delay for specific retry count"""
        delays = [
            self.first_delay,
            self.retry_delay_1,
            self.retry_delay_2,
            self.retry_delay_3,
        ]
        index = min(retry_count, len(delays) - 1)
        return delays[index]


@dataclass
class CalibrationResult:
    """
    Result of a single magnet calibration

    Represents the outcome of calibrating a magnet link.
    """

    info_hash: str
    old_magnet: str
    filename: Optional[str] = None
    success: bool = False
    error: Optional[str] = None

    @property
    def has_filename(self) -> bool:
        """Check if filename was extracted"""
        return bool(self.filename)
