"""
异步校准任务管理器（最小实现）

设计目标（KISS + YAGNI）：
- 使用标准库 ThreadPoolExecutor 执行阻塞型校准任务（subprocess 等）
- 任务状态存储在内存 Dict 中（进程重启即丢失，当前可接受）
- 已完成任务结果保留 1 小时（TTL），过期后自动清理
- 保留向后兼容：任务执行函数通过参数注入（DIP）
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

CalibrationResult = Tuple[Optional[Any], Optional[str]]


class TaskStatus(Enum):
    """任务状态"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class CalibrationTask:
    """任务元数据与结果（结果在内存中保留 TTL）"""

    task_id: str
    info_hash: str
    status: TaskStatus
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: float = 0.0
    completed_at: Optional[float] = None


class AsyncCalibrationManager:
    """异步校准任务管理器"""

    def __init__(
        self,
        max_workers: int = 5,
        task_ttl_seconds: int = 3600,
        time_fn: Callable[[], float] = time.time,
    ) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._tasks: Dict[str, CalibrationTask] = {}
        self._futures: Dict[str, Future] = {}
        self._task_ttl_seconds = task_ttl_seconds
        self._time_fn = time_fn
        self._lock = threading.RLock()

        logger.info("AsyncCalibrationManager initialized: max_workers=%s, ttl=%ss", max_workers, task_ttl_seconds)

    @property
    def max_workers(self) -> int:
        return self._executor._max_workers  # type: ignore[attr-defined]

    def submit_task(
        self,
        info_hash: str,
        calibration_func: Callable[..., CalibrationResult],
        *args: Any,
        **kwargs: Any,
    ) -> str:
        """
        提交异步校准任务，立即返回 task_id。

        Args:
            info_hash: 用于标识任务目标（通常是 info_hash；也可用于其他标识如 note:123）
            calibration_func: 返回 (result, error) 的函数
        """
        self.cleanup_old_tasks()

        task_id = str(uuid.uuid4())
        task = CalibrationTask(
            task_id=task_id,
            info_hash=info_hash,
            status=TaskStatus.PENDING,
            created_at=self._time_fn(),
        )

        with self._lock:
            self._tasks[task_id] = task
            future = self._executor.submit(self._execute_task, task_id, calibration_func, *args, **kwargs)
            self._futures[task_id] = future

        logger.info("Async calibration task submitted: task_id=%s info_hash=%s", task_id, info_hash)
        return task_id

    def get_task_status(self, task_id: str) -> Optional[CalibrationTask]:
        """查询任务状态（会先做一次过期清理）。"""
        self.cleanup_old_tasks()
        with self._lock:
            return self._tasks.get(task_id)

    def cleanup_old_tasks(self) -> None:
        """清理超过 TTL 的已完成任务结果（lazy 清理：在访问/提交时触发）。"""
        now = self._time_fn()
        with self._lock:
            expired_task_ids = [
                task_id
                for task_id, task in self._tasks.items()
                if task.completed_at is not None and (now - task.completed_at) > self._task_ttl_seconds
            ]

            for task_id in expired_task_ids:
                self._tasks.pop(task_id, None)
                self._futures.pop(task_id, None)

        if expired_task_ids:
            logger.info("Cleaned up expired async calibration tasks: count=%s", len(expired_task_ids))

    def shutdown(self, wait: bool = True) -> None:
        logger.info("Shutting down AsyncCalibrationManager")
        self._executor.shutdown(wait=wait)

    def _execute_task(
        self,
        task_id: str,
        calibration_func: Callable[..., CalibrationResult],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return
            task.status = TaskStatus.RUNNING

        try:
            result, error = calibration_func(*args, **kwargs)
            with self._lock:
                task = self._tasks.get(task_id)
                if not task:
                    return
                if result is not None:
                    task.status = TaskStatus.COMPLETED
                    task.result = result
                else:
                    task.status = TaskStatus.FAILED
                    task.error = error or "Unknown error"
        except Exception as e:
            logger.error("Async calibration task failed: task_id=%s error=%s", task_id, e, exc_info=True)
            with self._lock:
                task = self._tasks.get(task_id)
                if task:
                    task.status = TaskStatus.FAILED
                    task.error = str(e)
        finally:
            with self._lock:
                task = self._tasks.get(task_id)
                if task:
                    task.completed_at = self._time_fn()
                self._futures.pop(task_id, None)


_async_calibration_manager: Optional[AsyncCalibrationManager] = None


def get_async_calibration_manager() -> AsyncCalibrationManager:
    """获取全局异步校准管理器实例（进程内单例）。"""
    global _async_calibration_manager
    if _async_calibration_manager is None:
        _async_calibration_manager = AsyncCalibrationManager(max_workers=5, task_ttl_seconds=3600)
    return _async_calibration_manager

