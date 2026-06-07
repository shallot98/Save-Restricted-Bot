"""Automatic magnet calibration task manager."""

from __future__ import annotations

import logging
from typing import Dict, Optional

from src.core.container import get_calibration_service

from database import (
    add_calibration_task,
    get_calibration_stats,
    get_pending_calibration_tasks,
    get_note_by_id,
    update_calibration_task,
    update_note_with_calibrated_dns,
)
from .calibration_note_filter import CalibrationNoteFilterMixin
from .calibration_queue import CalibrationQueueMixin
from .calibration_scripts import CalibrationScriptMixin
from .calibration_task_processor import CalibrationTaskProcessorMixin

logger = logging.getLogger(__name__)


class CalibrationManager(
    CalibrationNoteFilterMixin,
    CalibrationQueueMixin,
    CalibrationScriptMixin,
    CalibrationTaskProcessorMixin,
):
    """Manage automatic calibration tasks."""

    def __init__(self):
        self.config = None
        self._calibration_service = None
        self.reload_config()

    @property
    def calibration_service(self):
        if self._calibration_service is None:
            self._calibration_service = get_calibration_service()
        return self._calibration_service

    def reload_config(self) -> None:
        try:
            config_obj = self.calibration_service.get_config()
            self.config = config_obj.to_dict()
            if self.config:
                logger.info(
                    "📋 校准配置已加载: enabled=%s, filter_mode=%s",
                    self.config["enabled"],
                    self.config["filter_mode"],
                )
            else:
                logger.warning("⚠️ 无法加载校准配置")
        except Exception as exc:
            logger.error(f"❌ 加载校准配置失败: {exc}")
            self.config = None

    def is_enabled(self) -> bool:
        return self.calibration_service.is_enabled()

    def get_stats(self) -> Dict:
        return get_calibration_stats()

    @staticmethod
    def _get_note_by_id(note_id: int) -> Optional[Dict]:
        return get_note_by_id(note_id)

    @staticmethod
    def _add_calibration_task(note_id: int, magnet_hash: str, delay_seconds: int):
        return add_calibration_task(note_id, magnet_hash, delay_seconds)

    @staticmethod
    def _get_pending_calibration_tasks(limit: int):
        return get_pending_calibration_tasks(limit=limit)

    @staticmethod
    def _update_calibration_task(
        task_id: int,
        status: str,
        error_message=None,
        *legacy_args,
        retry_delay=None,
    ):
        if legacy_args:
            if len(legacy_args) > 1 or retry_delay is not None:
                raise TypeError("_update_calibration_task received conflicting retry delay arguments")
            retry_delay = legacy_args[0]
        return update_calibration_task(
            task_id,
            status,
            error_message,
            next_retry_seconds=retry_delay,
        )

    @staticmethod
    def _update_note_with_calibrated_dns(note_id: int, calibrated_results):
        return update_note_with_calibrated_dns(note_id, calibrated_results)


_calibration_manager = None


def get_calibration_manager() -> CalibrationManager:
    global _calibration_manager
    if _calibration_manager is None:
        _calibration_manager = CalibrationManager()
    return _calibration_manager
