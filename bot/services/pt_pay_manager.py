"""PT 支付监控管理器。"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, replace
from typing import Any, Callable, Optional

from .pt_pay_models import PTPayTaskConfig, derive_target_bot_ref, normalize_trigger_delay_spec
from .pt_pay_runtime import PtPayMonitor
from .pt_pay_storage import PTPayMonitorStorage


RuntimeFactory = Callable[[Any, PTPayTaskConfig], PtPayMonitor]
_CREATE_FIELD_NAMES = (
    "source_chat_id",
    "source_name",
    "target_bot_id",
    "target_bot_name",
    "target_bot_ref",
)


@dataclass(frozen=True)
class PTPayTaskCreateRequest:
    user_id: str
    source_chat_id: str
    source_name: str
    target_bot_id: int
    target_bot_name: str
    target_bot_ref: str | None = None


def default_runtime_factory(client: Any, task: PTPayTaskConfig) -> PtPayMonitor:
    return PtPayMonitor(client, task.to_monitor_settings())


class PTPayMonitorManager:
    """管理 PT 支付脚本的持久化配置和运行时实例。"""

    def __init__(
        self,
        storage: PTPayMonitorStorage | None = None,
        runtime_factory: RuntimeFactory = default_runtime_factory,
    ) -> None:
        self._storage = storage or PTPayMonitorStorage()
        self._runtime_factory = runtime_factory
        self._lock = threading.RLock()
        self._client: Any = None
        self._tasks = self._storage.load()
        self._runtimes: dict[str, PtPayMonitor] = {}

    def bind_client(self, client: Any) -> None:
        with self._lock:
            if client is self._client:
                return
            self._stop_all_locked()
            self._client = client
            if self._client is not None:
                self._start_enabled_tasks_locked()

    def shutdown(self) -> None:
        with self._lock:
            self._stop_all_locked()
            self._client = None

    def dispatch_message(self, message: Any) -> None:
        with self._lock:
            runtimes = list(self._runtimes.values())

        for runtime in runtimes:
            runtime.handle_message(message)

    def list_user_tasks(self, user_id: str) -> list[PTPayTaskConfig]:
        with self._lock:
            tasks = self._tasks.get(str(user_id), {})
            return sorted(tasks.values(), key=lambda item: (item.source_name, item.target_bot_name, item.task_id))

    def get_user_task(self, user_id: str, task_id: str) -> Optional[PTPayTaskConfig]:
        with self._lock:
            return self._tasks.get(str(user_id), {}).get(task_id)

    def add_task(
        self,
        request: PTPayTaskCreateRequest | str | None = None,
        *legacy_args: Any,
        **legacy_fields: Any,
    ) -> PTPayTaskConfig:
        request = _pt_pay_task_create_request(request, legacy_args, legacy_fields)
        with self._lock:
            self._ensure_unique_task(str(request.user_id), request.source_chat_id, request.target_bot_id)
            task = PTPayTaskConfig(
                task_id=uuid.uuid4().hex,
                source_chat_id=str(request.source_chat_id),
                source_name=str(request.source_name).strip() or str(request.source_chat_id),
                target_bot_id=int(request.target_bot_id),
                target_bot_name=str(request.target_bot_name).strip() or str(request.target_bot_id),
                target_bot_ref=derive_target_bot_ref(
                    request.target_bot_ref,
                    str(request.target_bot_name),
                    int(request.target_bot_id),
                ),
                enabled=True,
            )

            user_tasks = self._tasks.setdefault(str(request.user_id), {})
            user_tasks[task.task_id] = task
            self._save_locked()
            self._start_task_locked(task)
            return task

    def toggle_task(self, user_id: str, task_id: str) -> PTPayTaskConfig:
        with self._lock:
            task = self._require_task(str(user_id), task_id)
            updated = replace(task, enabled=not task.enabled)
            self._tasks[str(user_id)][task_id] = updated
            self._save_locked()
            if updated.enabled:
                self._start_task_locked(updated)
            else:
                self._stop_task_locked(task_id)
            return updated

    def update_delay_spec(self, user_id: str, task_id: str, delay_spec: str) -> PTPayTaskConfig:
        with self._lock:
            task = self._require_task(str(user_id), task_id)
            updated = replace(task, trigger_delay_spec=normalize_trigger_delay_spec(delay_spec))
            self._tasks[str(user_id)][task_id] = updated
            self._save_locked()
            self._stop_task_locked(task_id)
            if updated.enabled:
                self._start_task_locked(updated)
            return updated

    def remove_task(self, user_id: str, task_id: str) -> PTPayTaskConfig:
        with self._lock:
            task = self._require_task(str(user_id), task_id)
            self._stop_task_locked(task_id)
            del self._tasks[str(user_id)][task_id]
            if not self._tasks[str(user_id)]:
                del self._tasks[str(user_id)]
            self._save_locked()
            return task

    def count_user_tasks(self, user_id: str) -> int:
        with self._lock:
            return len(self._tasks.get(str(user_id), {}))

    def count_enabled_user_tasks(self, user_id: str) -> int:
        with self._lock:
            return sum(1 for task in self._tasks.get(str(user_id), {}).values() if task.enabled)

    def _ensure_unique_task(self, user_id: str, source_chat_id: str, target_bot_id: int) -> None:
        for task in self._tasks.get(user_id, {}).values():
            if task.source_chat_id == str(source_chat_id) and task.target_bot_id == int(target_bot_id):
                raise ValueError("该群聊到目标对象的脚本已存在")

    def _require_task(self, user_id: str, task_id: str) -> PTPayTaskConfig:
        task = self._tasks.get(user_id, {}).get(task_id)
        if task is None:
            raise ValueError("脚本任务不存在")
        return task

    def _save_locked(self) -> None:
        self._storage.save(self._tasks)

    def _start_enabled_tasks_locked(self) -> None:
        for tasks in self._tasks.values():
            for task in tasks.values():
                if task.enabled:
                    self._start_task_locked(task)

    def _start_task_locked(self, task: PTPayTaskConfig) -> None:
        if self._client is None or task.task_id in self._runtimes or not task.enabled:
            return

        try:
            from bot.services.peer_cache import cache_peer_if_needed

            cache_peer_if_needed(self._client, int(task.source_chat_id), "脚本源群")
        except Exception:
            pass

        runtime = self._runtime_factory(self._client, task)
        runtime.start()
        self._runtimes[task.task_id] = runtime

    def _stop_task_locked(self, task_id: str) -> None:
        runtime = self._runtimes.pop(task_id, None)
        if runtime is not None:
            runtime.stop()

    def _stop_all_locked(self) -> None:
        for task_id in list(self._runtimes.keys()):
            self._stop_task_locked(task_id)


_manager: PTPayMonitorManager | None = None


def get_pt_pay_monitor_manager() -> PTPayMonitorManager:
    global _manager
    if _manager is None:
        _manager = PTPayMonitorManager()
    return _manager


def _pt_pay_task_create_request(
    request: PTPayTaskCreateRequest | str | None,
    legacy_args: tuple[Any, ...],
    legacy_fields: dict[str, Any],
) -> PTPayTaskCreateRequest:
    if isinstance(request, PTPayTaskCreateRequest):
        if legacy_args or legacy_fields:
            raise TypeError("add_task received both request object and legacy arguments")
        return request
    if request is None:
        if "user_id" not in legacy_fields:
            raise TypeError("add_task requires user_id")
        request = legacy_fields.pop("user_id")
    if len(legacy_args) > len(_CREATE_FIELD_NAMES):
        raise TypeError("add_task received too many positional arguments")

    values = dict(zip(_CREATE_FIELD_NAMES, legacy_args))
    values.update(legacy_fields)
    return PTPayTaskCreateRequest(user_id=str(request), **values)
