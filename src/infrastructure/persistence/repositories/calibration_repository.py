"""
SQLite Calibration Repository
==============================

SQLite implementation of CalibrationRepository interface.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from zoneinfo import ZoneInfo

from src.domain.entities.calibration import (
    CalibrationTask,
    CalibrationConfig,
    CalibrationStatus,
)
from src.domain.repositories.calibration_repository import (
    CalibrationRepository,
    CalibrationConfigRepository,
)
from src.infrastructure.persistence.sqlite.connection import get_db_connection
from src.core.utils.datetime_utils import format_db_datetime

logger = logging.getLogger(__name__)

CHINA_TZ = ZoneInfo("Asia/Shanghai")


class SQLiteCalibrationRepository(CalibrationRepository):
    """SQLite implementation of CalibrationRepository"""

    def get_by_id(self, task_id: int) -> Optional[CalibrationTask]:
        """Get calibration task by ID"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM calibration_tasks WHERE id = ?', (task_id,))
            row = cursor.fetchone()
            if row:
                return CalibrationTask.from_dict(dict(row))
            return None

    def get_by_note_id(self, note_id: int) -> Optional[CalibrationTask]:
        """Get calibration task by note ID"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM calibration_tasks WHERE note_id = ? ORDER BY id DESC LIMIT 1',
                (note_id,)
            )
            row = cursor.fetchone()
            if row:
                return CalibrationTask.from_dict(dict(row))
            return None

    def get_pending_tasks(
        self,
        limit: int = 10,
        before: Optional[datetime] = None
    ) -> List[CalibrationTask]:
        """Get pending calibration tasks"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            now = before or datetime.now(CHINA_TZ)
            now_str = format_db_datetime(now)

            cursor.execute('''
                SELECT * FROM calibration_tasks
                WHERE status IN ('pending', 'retrying')
                AND next_attempt <= ?
                ORDER BY next_attempt ASC
                LIMIT ?
            ''', (now_str, limit))

            return [CalibrationTask.from_dict(dict(row)) for row in cursor.fetchall()]

    def create(
        self,
        note_id: int,
        magnet_hash: str,
        next_attempt: datetime
    ) -> CalibrationTask:
        """Create a new calibration task"""
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Check for existing pending task
            cursor.execute('''
                SELECT id FROM calibration_tasks
                WHERE note_id = ? AND status IN ('pending', 'retrying')
            ''', (note_id,))

            if cursor.fetchone():
                logger.debug(f"Task already exists for note {note_id}")
                return self.get_by_note_id(note_id)

            now = datetime.now(CHINA_TZ)
            cursor.execute('''
                INSERT INTO calibration_tasks (note_id, magnet_hash, status, next_attempt, created_at)
                VALUES (?, ?, 'pending', ?, ?)
            ''', (
                note_id,
                magnet_hash,
                format_db_datetime(next_attempt),
                format_db_datetime(now),
            ))

            task_id = cursor.lastrowid
            logger.info(f"Created calibration task: id={task_id}, note_id={note_id}")

            return self.get_by_id(task_id)

    def update_status(
        self,
        task_id: int,
        status: CalibrationStatus,
        error_message: Optional[str] = None,
        next_attempt: Optional[datetime] = None
    ) -> bool:
        """Update task status"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            now = format_db_datetime(datetime.now(CHINA_TZ))

            if status == CalibrationStatus.RETRYING and next_attempt:
                cursor.execute('''
                    UPDATE calibration_tasks
                    SET status = ?, retry_count = retry_count + 1,
                        last_attempt = ?, next_attempt = ?, error_message = ?
                    WHERE id = ?
                ''', (
                    status.value,
                    now,
                    format_db_datetime(next_attempt),
                    error_message,
                    task_id
                ))
            else:
                cursor.execute('''
                    UPDATE calibration_tasks
                    SET status = ?, last_attempt = ?, error_message = ?
                    WHERE id = ?
                ''', (status.value, now, error_message, task_id))

            return cursor.rowcount > 0

    def increment_retry(self, task_id: int, next_attempt: datetime) -> bool:
        """Increment retry count and schedule next attempt"""
        return self.update_status(
            task_id,
            CalibrationStatus.RETRYING,
            next_attempt=next_attempt
        )

    def delete(self, task_id: int) -> bool:
        """Delete calibration task"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM calibration_tasks WHERE id = ?', (task_id,))
            return cursor.rowcount > 0

    def delete_by_note_id(self, note_id: int) -> int:
        """Delete all tasks for a note"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM calibration_tasks WHERE note_id = ?', (note_id,))
            return cursor.rowcount

    def get_stats(self) -> dict:
        """Get calibration statistics"""
        with get_db_connection() as conn:
            cursor = conn.cursor()

            stats = {}

            cursor.execute('SELECT COUNT(*) FROM calibration_tasks')
            stats['total'] = cursor.fetchone()[0]

            cursor.execute('''
                SELECT status, COUNT(*) as count
                FROM calibration_tasks
                GROUP BY status
            ''')
            stats['by_status'] = {row[0]: row[1] for row in cursor.fetchall()}

            now = format_db_datetime(datetime.now(CHINA_TZ))
            cursor.execute('''
                SELECT COUNT(*) FROM calibration_tasks
                WHERE status IN ('pending', 'retrying') AND next_attempt <= ?
            ''', (now,))
            stats['ready_to_process'] = cursor.fetchone()[0]

            return stats

    def list_all(
        self,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[CalibrationTask]:
        """List all calibration tasks with optional filtering"""
        with get_db_connection() as conn:
            cursor = conn.cursor()

            query = 'SELECT * FROM calibration_tasks WHERE 1=1'
            params = []

            if status:
                query += ' AND status = ?'
                params.append(status)

            query += ' ORDER BY created_at DESC LIMIT ? OFFSET ?'
            params.extend([limit, offset])

            cursor.execute(query, params)
            return [CalibrationTask.from_dict(dict(row)) for row in cursor.fetchall()]


class SQLiteCalibrationConfigRepository(CalibrationConfigRepository):
    """SQLite implementation of CalibrationConfigRepository"""

    def get_config(self) -> CalibrationConfig:
        """Get calibration configuration"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM auto_calibration_config WHERE id = 1')
            row = cursor.fetchone()
            if row:
                return CalibrationConfig.from_dict(dict(row))
            return CalibrationConfig()

    def save_config(self, config: CalibrationConfig) -> None:
        """Save calibration configuration"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            data = config.to_dict()
            cursor.execute('''
                UPDATE auto_calibration_config
                SET enabled = ?, filter_mode = ?, first_delay = ?,
                    retry_delay_1 = ?, retry_delay_2 = ?, retry_delay_3 = ?,
                    max_retries = ?, concurrent_limit = ?,
                    timeout_per_magnet = ?, batch_timeout = ?
                WHERE id = 1
            ''', (
                data['enabled'],
                data['filter_mode'],
                data['first_delay'],
                data['retry_delay_1'],
                data['retry_delay_2'],
                data['retry_delay_3'],
                data['max_retries'],
                data['concurrent_limit'],
                data['timeout_per_magnet'],
                data['batch_timeout'],
            ))
