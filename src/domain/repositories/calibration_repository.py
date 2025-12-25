"""
Calibration Repository Interface
================================

Abstract interface for calibration task persistence.
"""

from abc import ABC, abstractmethod
from typing import Optional, List
from datetime import datetime

from src.domain.entities.calibration import (
    CalibrationTask,
    CalibrationConfig,
    CalibrationStatus,
)


class CalibrationRepository(ABC):
    """
    Calibration repository interface

    Defines the contract for calibration task persistence.
    """

    @abstractmethod
    def get_by_id(self, task_id: int) -> Optional[CalibrationTask]:
        """
        Get calibration task by ID

        Args:
            task_id: Task identifier

        Returns:
            CalibrationTask if found, None otherwise
        """
        pass

    @abstractmethod
    def get_by_note_id(self, note_id: int) -> Optional[CalibrationTask]:
        """
        Get calibration task by note ID

        Args:
            note_id: Note identifier

        Returns:
            CalibrationTask if found, None otherwise
        """
        pass

    @abstractmethod
    def get_pending_tasks(
        self,
        limit: int = 10,
        before: Optional[datetime] = None
    ) -> List[CalibrationTask]:
        """
        Get pending calibration tasks

        Args:
            limit: Maximum number of tasks
            before: Only tasks scheduled before this time

        Returns:
            List of pending tasks
        """
        pass

    @abstractmethod
    def create(
        self,
        note_id: int,
        magnet_hash: str,
        next_attempt: datetime
    ) -> CalibrationTask:
        """
        Create a new calibration task

        Args:
            note_id: Associated note ID
            magnet_hash: Magnet info hash
            next_attempt: Scheduled attempt time

        Returns:
            Created task
        """
        pass

    @abstractmethod
    def update_status(
        self,
        task_id: int,
        status: CalibrationStatus,
        error_message: Optional[str] = None,
        next_attempt: Optional[datetime] = None
    ) -> bool:
        """
        Update task status

        Args:
            task_id: Task identifier
            status: New status
            error_message: Error message if failed
            next_attempt: Next scheduled attempt

        Returns:
            True if updated
        """
        pass

    @abstractmethod
    def increment_retry(
        self,
        task_id: int,
        next_attempt: datetime
    ) -> bool:
        """
        Increment retry count and schedule next attempt

        Args:
            task_id: Task identifier
            next_attempt: Next scheduled attempt

        Returns:
            True if updated
        """
        pass

    @abstractmethod
    def delete(self, task_id: int) -> bool:
        """
        Delete calibration task

        Args:
            task_id: Task identifier

        Returns:
            True if deleted
        """
        pass

    @abstractmethod
    def get_stats(self) -> dict:
        """
        Get calibration statistics

        Returns:
            Dictionary with status counts
        """
        pass

    @abstractmethod
    def list_all(
        self,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[CalibrationTask]:
        """
        List all calibration tasks with optional filtering

        Args:
            status: Filter by status (optional)
            limit: Maximum number of tasks
            offset: Pagination offset

        Returns:
            List of calibration tasks
        """
        pass


class CalibrationConfigRepository(ABC):
    """
    Calibration configuration repository interface
    """

    @abstractmethod
    def get_config(self) -> CalibrationConfig:
        """
        Get calibration configuration

        Returns:
            Current configuration
        """
        pass

    @abstractmethod
    def save_config(self, config: CalibrationConfig) -> None:
        """
        Save calibration configuration

        Args:
            config: Configuration to save
        """
        pass
