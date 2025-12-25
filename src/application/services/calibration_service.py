"""
Calibration Application Service
===============================

Orchestrates magnet link calibration operations.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from zoneinfo import ZoneInfo

from src.domain.entities.calibration import (
    CalibrationTask,
    CalibrationConfig,
    CalibrationStatus,
    CalibrationResult,
)
from src.domain.repositories.calibration_repository import (
    CalibrationRepository,
    CalibrationConfigRepository,
)
from src.core.exceptions import NotFoundError, ValidationError

logger = logging.getLogger(__name__)

CHINA_TZ = ZoneInfo("Asia/Shanghai")


class CalibrationService:
    """
    Calibration application service

    Orchestrates magnet link calibration operations including
    task scheduling, execution, and result handling.
    """

    def __init__(
        self,
        task_repository: CalibrationRepository,
        config_repository: CalibrationConfigRepository
    ) -> None:
        """
        Initialize service

        Args:
            task_repository: Calibration task repository
            config_repository: Calibration config repository
        """
        self._task_repo = task_repository
        self._config_repo = config_repository

    def get_config(self) -> CalibrationConfig:
        """
        Get calibration configuration

        Returns:
            Current configuration
        """
        return self._config_repo.get_config()

    def update_config(self, config_data: Dict[str, Any]) -> CalibrationConfig:
        """
        Update calibration configuration

        Args:
            config_data: Configuration data dictionary

        Returns:
            Updated configuration
        """
        config = CalibrationConfig.from_dict(config_data)
        self._config_repo.save_config(config)
        logger.info(f"Calibration config updated: enabled={config.enabled}")
        return config

    def is_enabled(self) -> bool:
        """
        Check if calibration is enabled

        Returns:
            True if enabled
        """
        return self.get_config().enabled

    def schedule_calibration(
        self,
        note_id: int,
        magnet_hash: str,
        delay_seconds: Optional[int] = None
    ) -> Optional[CalibrationTask]:
        """
        Schedule a calibration task for a note

        Args:
            note_id: Note identifier
            magnet_hash: Magnet info hash
            delay_seconds: Delay before first attempt (uses config default if None)

        Returns:
            Created task or None if already exists
        """
        config = self.get_config()
        if not config.enabled:
            logger.debug("Calibration disabled, skipping schedule")
            return None

        delay = delay_seconds if delay_seconds is not None else config.first_delay
        next_attempt = datetime.now(CHINA_TZ) + timedelta(seconds=delay)

        task = self._task_repo.create(note_id, magnet_hash, next_attempt)
        if task:
            logger.info(f"Calibration scheduled: note_id={note_id}, delay={delay}s")
        return task

    def get_pending_tasks(self, limit: int = 10) -> List[CalibrationTask]:
        """
        Get tasks ready for processing

        Args:
            limit: Maximum number of tasks

        Returns:
            List of pending tasks
        """
        return self._task_repo.get_pending_tasks(limit=limit)

    def mark_success(self, task_id: int) -> bool:
        """
        Mark task as successful

        Args:
            task_id: Task identifier

        Returns:
            True if updated
        """
        return self._task_repo.update_status(
            task_id,
            CalibrationStatus.SUCCESS
        )

    def mark_failed(
        self,
        task_id: int,
        error_message: Optional[str] = None
    ) -> bool:
        """
        Mark task as failed

        Args:
            task_id: Task identifier
            error_message: Error description

        Returns:
            True if updated
        """
        return self._task_repo.update_status(
            task_id,
            CalibrationStatus.FAILED,
            error_message=error_message
        )

    def schedule_retry(self, task_id: int) -> bool:
        """
        Schedule a retry for a failed task

        Args:
            task_id: Task identifier

        Returns:
            True if retry scheduled, False if max retries exceeded
        """
        task = self._task_repo.get_by_id(task_id)
        if not task:
            raise NotFoundError(
                f"Calibration task not found: {task_id}",
                resource_type="CalibrationTask",
                resource_id=task_id
            )

        config = self.get_config()
        if task.retry_count >= config.max_retries:
            logger.info(f"Max retries exceeded for task {task_id}")
            return self.mark_failed(task_id, "Max retries exceeded")

        delay = config.get_retry_delay(task.retry_count + 1)
        next_attempt = datetime.now(CHINA_TZ) + timedelta(seconds=delay)

        return self._task_repo.increment_retry(task_id, next_attempt)

    def get_task_by_note(self, note_id: int) -> Optional[CalibrationTask]:
        """
        Get calibration task for a note

        Args:
            note_id: Note identifier

        Returns:
            Task if found
        """
        return self._task_repo.get_by_note_id(note_id)

    def delete_task(self, task_id: int) -> bool:
        """
        Delete a calibration task

        Args:
            task_id: Task identifier

        Returns:
            True if deleted
        """
        return self._task_repo.delete(task_id)

    def delete_tasks_for_note(self, note_id: int) -> int:
        """
        Delete all tasks for a note

        Args:
            note_id: Note identifier

        Returns:
            Number of deleted tasks
        """
        return self._task_repo.delete_by_note_id(note_id)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get calibration statistics

        Returns:
            Statistics dictionary
        """
        stats = self._task_repo.get_stats()
        config = self.get_config()
        stats['enabled'] = config.enabled
        stats['filter_mode'] = config.filter_mode.value
        return stats

    def process_result(
        self,
        task_id: int,
        result: CalibrationResult
    ) -> bool:
        """
        Process calibration result

        Args:
            task_id: Task identifier
            result: Calibration result

        Returns:
            True if processed successfully
        """
        if result.success:
            logger.info(f"Calibration success: task={task_id}, filename={result.filename}")
            return self.mark_success(task_id)
        else:
            logger.warning(f"Calibration failed: task={task_id}, error={result.error}")
            return self.schedule_retry(task_id)

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
        return self._task_repo.list_all(status=status, limit=limit, offset=offset)
