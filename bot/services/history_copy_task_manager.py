"""Manager for keyboard-triggered history-copy tasks."""
from __future__ import annotations
import hashlib
import threading
import time
import uuid
from dataclasses import replace
from pathlib import Path
from typing import Any, Optional
from src.core.config import settings
from .history_copy_models import HistoryCopyStats
from .history_copy_task_executor import (
    Clock,
    ExecutionResult,
    ProgressCallback,
    TaskExecutor,
    _resolve_bot_source_ref,
    default_history_copy_task_executor,
)
from .history_copy_task_models import (
    RESTARTABLE_STATUSES,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_INTERRUPTED,
    STATUS_RUNNING,
    HistoryCopyTaskConfig,
    HistoryCopyTaskNewRequest,
)
from .history_copy_task_requests import (
    HistoryCopyTaskCreateRequest,
    history_copy_task_create_request,
)
from .history_copy_task_storage import HistoryCopyTaskStorage
INTERRUPTED_MESSAGE = "机器人重启或异常退出导致任务中断，可重新创建任务继续；断点库会保留已复制进度"
class HistoryCopyTaskManager:
    """Manage one-shot history copy tasks launched from keyboard UI."""

    def __init__(
        self,
        storage: HistoryCopyTaskStorage | None = None,
        executor: TaskExecutor = default_history_copy_task_executor,
        clock: Clock = time.time,
    ) -> None:
        self._storage = storage or HistoryCopyTaskStorage()
        self._executor = executor
        self._clock = clock
        self._lock = threading.RLock()
        self._client: Any = None
        self._tasks = self._storage.load()
        self._workers: dict[str, threading.Thread] = {}
        self._mark_running_tasks_interrupted_locked()
    def bind_client(self, client: Any) -> None:
        with self._lock:
            self._client = client
    def shutdown(self) -> None:
        with self._lock:
            self._client = None
    def list_user_tasks(self, user_id: str) -> list[HistoryCopyTaskConfig]:
        with self._lock:
            tasks = self._tasks.get(str(user_id), {})
            return sorted(tasks.values(), key=lambda item: (-item.created_at, item.task_id))
    def get_user_task(self, user_id: str, task_id: str) -> Optional[HistoryCopyTaskConfig]:
        with self._lock:
            return self._tasks.get(str(user_id), {}).get(task_id)
    def add_task(
        self,
        request: HistoryCopyTaskCreateRequest | str | None = None,
        *legacy_args: Any,
        **legacy_fields: Any,
    ) -> HistoryCopyTaskConfig:
        request = history_copy_task_create_request(request, legacy_args, legacy_fields)
        with self._lock:
            if self._client is None:
                raise ValueError("当前未配置 String Session，无法执行历史复制")
            running = self._find_running_task_locked()
            if running is not None:
                raise ValueError(
                    f"已有历史复制任务正在运行：{running.source_name} → {running.dest_name}"
                )

            task = HistoryCopyTaskConfig.new(
                HistoryCopyTaskNewRequest(
                    task_id=uuid.uuid4().hex,
                    source_chat_ref=request.source_chat_ref,
                    source_name=request.source_name,
                    dest_chat_ref=request.dest_chat_ref,
                    dest_name=request.dest_name,
                    history_limit=request.history_limit,
                    state_db_path=str(self._build_state_db_path(
                        request.user_id,
                        request.source_chat_ref,
                        request.dest_chat_ref,
                    )),
                    now=self._clock(),
                )
            )
            user_tasks = self._tasks.setdefault(str(request.user_id), {})
            user_tasks[task.task_id] = task
            self._save_locked()
            self._start_task_locked(str(request.user_id), task, self._client)
            return task
    def restart_task(self, user_id: str, task_id: str) -> HistoryCopyTaskConfig:
        with self._lock:
            if self._client is None:
                raise ValueError("当前未配置 String Session，无法执行历史复制")
            task = self._require_task(str(user_id), task_id)
            if task.status == STATUS_RUNNING:
                raise ValueError("历史复制任务正在运行，无需重启")
            if task.status not in RESTARTABLE_STATUSES:
                raise ValueError("仅已失败或已中断的历史复制任务支持重启")
            running = self._find_running_task_locked()
            if running is not None:
                raise ValueError(
                    f"已有历史复制任务正在运行：{running.source_name} → {running.dest_name}"
                )

            restarted = replace(
                task,
                status=STATUS_RUNNING,
                status_message="",
                error_message="",
                scanned_count=0,
                copied_count=0,
                skipped_count=0,
                failed_count=0,
                started_at=self._clock(),
                finished_at=0.0,
            )
            self._tasks[str(user_id)][task_id] = restarted
            self._save_locked()
            self._start_task_locked(str(user_id), restarted, self._client)
            return restarted
    def remove_task(self, user_id: str, task_id: str) -> HistoryCopyTaskConfig:
        with self._lock:
            task = self._require_task(str(user_id), task_id)
            if task.status == STATUS_RUNNING:
                raise ValueError("运行中的历史复制任务暂不支持删除")
            del self._tasks[str(user_id)][task_id]
            if not self._tasks[str(user_id)]:
                del self._tasks[str(user_id)]
            self._save_locked()
            return task

    def count_user_tasks(self, user_id: str) -> int:
        with self._lock:
            return len(self._tasks.get(str(user_id), {}))

    def count_running_user_tasks(self, user_id: str) -> int:
        with self._lock:
            return sum(
                1
                for task in self._tasks.get(str(user_id), {}).values()
                if task.status == STATUS_RUNNING
            )

    def _run_task(self, user_id: str, task_id: str, client: Any) -> None:
        try:
            with self._lock:
                task = self._require_task(user_id, task_id)
            progress_callback = lambda current_stats: self._update_task_progress(user_id, task_id, current_stats)
            if self._executor is default_history_copy_task_executor:
                settings_obj, stats = self._executor(client, task, progress_callback, user_id=user_id)
            else:
                settings_obj, stats = self._executor(client, task, progress_callback)
            updated = replace(
                task,
                status=STATUS_COMPLETED,
                status_message=stats.summary(),
                source_chat_id=settings_obj.source_chat_id,
                dest_chat_id=settings_obj.dest_chat_id,
                scanned_count=stats.scanned_count,
                copied_count=stats.copied_count,
                skipped_count=stats.skipped_count,
                failed_count=stats.failed_count,
                finished_at=self._clock(),
            )
        except Exception as exc:
            with self._lock:
                task = self._require_task(user_id, task_id)
            updated = replace(
                task,
                status=STATUS_FAILED,
                error_message=f"{type(exc).__name__}: {exc}",
                finished_at=self._clock(),
            )

        with self._lock:
            user_tasks = self._tasks.setdefault(user_id, {})
            user_tasks[task_id] = updated
            self._workers.pop(task_id, None)
            self._save_locked()

    def _mark_running_tasks_interrupted_locked(self) -> None:
        changed = False
        for user_id, tasks in self._tasks.items():
            for task_id, task in list(tasks.items()):
                if task.status != STATUS_RUNNING:
                    continue
                tasks[task_id] = replace(
                    task,
                    status=STATUS_INTERRUPTED,
                    error_message=INTERRUPTED_MESSAGE,
                    finished_at=self._clock(),
                )
                changed = True
        if changed:
            self._save_locked()

    def _find_running_task_locked(self) -> Optional[HistoryCopyTaskConfig]:
        for tasks in self._tasks.values():
            for task in tasks.values():
                if task.status == STATUS_RUNNING:
                    return task
        return None

    def _require_task(self, user_id: str, task_id: str) -> HistoryCopyTaskConfig:
        task = self._tasks.get(user_id, {}).get(task_id)
        if task is None:
            raise ValueError("历史复制任务不存在")
        return task

    def _save_locked(self) -> None:
        self._storage.save(self._tasks)

    def _update_task_progress(
        self,
        user_id: str,
        task_id: str,
        stats: HistoryCopyStats,
    ) -> None:
        with self._lock:
            task = self._tasks.get(user_id, {}).get(task_id)
            if task is None or task.status != STATUS_RUNNING:
                return
            self._tasks[user_id][task_id] = replace(
                task,
                status_message=stats.summary(),
                scanned_count=stats.scanned_count,
                copied_count=stats.copied_count,
                skipped_count=stats.skipped_count,
                failed_count=stats.failed_count,
            )
            self._save_locked()

    def _start_task_locked(self, user_id: str, task: HistoryCopyTaskConfig, client: Any) -> None:
        worker = threading.Thread(
            target=self._run_task,
            args=(user_id, task.task_id, client),
            name=f"history-copy-{task.task_id[:8]}",
            daemon=True,
        )
        self._workers[task.task_id] = worker
        worker.start()

    def _build_state_db_path(self, user_id: str, source_chat_ref: str, dest_chat_ref: str) -> Path:
        digest = hashlib.sha1(
            f"{user_id}|{source_chat_ref.strip()}|{dest_chat_ref.strip()}".encode("utf-8")
        ).hexdigest()[:20]
        base_dir = settings.paths.data_dir / "history_copy_state"
        base_dir.mkdir(parents=True, exist_ok=True)
        return base_dir / f"{digest}.db"


_manager: HistoryCopyTaskManager | None = None


def get_history_copy_task_manager() -> HistoryCopyTaskManager:
    global _manager
    if _manager is None:
        _manager = HistoryCopyTaskManager()
    return _manager
