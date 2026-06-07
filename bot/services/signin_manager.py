"""定时签到脚本管理器。"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, replace
from typing import Any, Callable, Optional

from .signin_models import (
    ScheduledSigninTaskConfig,
    normalize_interval_spec,
    normalize_message_text,
)
from .signin_runtime import ScheduledSigninRuntime
from .signin_storage import ScheduledSigninStorage


RuntimeFactory = Callable[[Any, ScheduledSigninTaskConfig], ScheduledSigninRuntime]
_CREATE_FIELD_NAMES = (
    "chat_id",
    "chat_name",
    "chat_ref",
    "message_text",
    "interval_spec",
)


@dataclass(frozen=True)
class ScheduledSigninTaskCreateRequest:
    user_id: str
    chat_id: str
    chat_name: str
    chat_ref: str
    message_text: str
    interval_spec: str


def default_runtime_factory(client: Any, task: ScheduledSigninTaskConfig) -> ScheduledSigninRuntime:
    return ScheduledSigninRuntime(client, task)


class ScheduledSigninManager:
    """管理定时签到脚本的持久化配置和运行时实例。"""

    def __init__(
        self,
        storage: ScheduledSigninStorage | None = None,
        runtime_factory: RuntimeFactory = default_runtime_factory,
    ) -> None:
        self._storage = storage or ScheduledSigninStorage()
        self._runtime_factory = runtime_factory
        self._lock = threading.RLock()
        self._client: Any = None
        self._tasks = self._storage.load()
        self._runtimes: dict[str, ScheduledSigninRuntime] = {}

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

    def list_user_tasks(self, user_id: str) -> list[ScheduledSigninTaskConfig]:
        with self._lock:
            tasks = self._tasks.get(str(user_id), {})
            return sorted(tasks.values(), key=lambda item: (item.chat_name, item.task_id))

    def get_user_task(self, user_id: str, task_id: str) -> Optional[ScheduledSigninTaskConfig]:
        with self._lock:
            return self._tasks.get(str(user_id), {}).get(task_id)

    def add_task(
        self,
        request: ScheduledSigninTaskCreateRequest | str | None = None,
        *legacy_args: Any,
        **legacy_fields: Any,
    ) -> ScheduledSigninTaskConfig:
        request = _signin_task_create_request(request, legacy_args, legacy_fields)
        with self._lock:
            normalized_message = normalize_message_text(request.message_text)
            normalized_interval = normalize_interval_spec(request.interval_spec)
            self._ensure_unique_task(str(request.user_id), request.chat_id, normalized_message)

            task = ScheduledSigninTaskConfig(
                task_id=uuid.uuid4().hex,
                chat_id=str(request.chat_id),
                chat_name=str(request.chat_name).strip() or str(request.chat_id),
                chat_ref=str(request.chat_ref).strip() or str(request.chat_id),
                message_text=normalized_message,
                interval_spec=normalized_interval,
                enabled=True,
            )

            user_tasks = self._tasks.setdefault(str(request.user_id), {})
            user_tasks[task.task_id] = task
            self._save_locked()
            self._start_task_locked(task)
            return task

    def toggle_task(self, user_id: str, task_id: str) -> ScheduledSigninTaskConfig:
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

    def update_message_text(self, user_id: str, task_id: str, message_text: str) -> ScheduledSigninTaskConfig:
        with self._lock:
            task = self._require_task(str(user_id), task_id)
            normalized_message = normalize_message_text(message_text)
            self._ensure_unique_task(str(user_id), task.chat_id, normalized_message, exclude_task_id=task_id)
            updated = replace(task, message_text=normalized_message)
            self._tasks[str(user_id)][task_id] = updated
            self._restart_task_locked(updated)
            return updated

    def update_interval_spec(self, user_id: str, task_id: str, interval_spec: str) -> ScheduledSigninTaskConfig:
        with self._lock:
            task = self._require_task(str(user_id), task_id)
            updated = replace(task, interval_spec=normalize_interval_spec(interval_spec))
            self._tasks[str(user_id)][task_id] = updated
            self._restart_task_locked(updated)
            return updated

    def remove_task(self, user_id: str, task_id: str) -> ScheduledSigninTaskConfig:
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

    def _ensure_unique_task(
        self,
        user_id: str,
        chat_id: str,
        message_text: str,
        *,
        exclude_task_id: str | None = None,
    ) -> None:
        for task in self._tasks.get(user_id, {}).values():
            if exclude_task_id is not None and task.task_id == exclude_task_id:
                continue
            if task.chat_id == str(chat_id) and task.message_text == message_text:
                raise ValueError("该群聊下相同消息内容的签到脚本已存在")

    def _require_task(self, user_id: str, task_id: str) -> ScheduledSigninTaskConfig:
        task = self._tasks.get(user_id, {}).get(task_id)
        if task is None:
            raise ValueError("签到脚本不存在")
        return task

    def _save_locked(self) -> None:
        self._storage.save(self._tasks)

    def _restart_task_locked(self, task: ScheduledSigninTaskConfig) -> None:
        self._save_locked()
        self._stop_task_locked(task.task_id)
        if task.enabled:
            self._start_task_locked(task)

    def _start_enabled_tasks_locked(self) -> None:
        for tasks in self._tasks.values():
            for task in tasks.values():
                if task.enabled:
                    self._start_task_locked(task)

    def _start_task_locked(self, task: ScheduledSigninTaskConfig) -> None:
        if self._client is None or task.task_id in self._runtimes or not task.enabled:
            return

        try:
            from bot.services.peer_cache import cache_peer_if_needed

            cache_peer_if_needed(self._client, int(task.chat_id), "签到脚本目标")
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


_manager: ScheduledSigninManager | None = None


def get_scheduled_signin_manager() -> ScheduledSigninManager:
    global _manager
    if _manager is None:
        _manager = ScheduledSigninManager()
    return _manager


def _signin_task_create_request(
    request: ScheduledSigninTaskCreateRequest | str | None,
    legacy_args: tuple[Any, ...],
    legacy_fields: dict[str, Any],
) -> ScheduledSigninTaskCreateRequest:
    if isinstance(request, ScheduledSigninTaskCreateRequest):
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
    return ScheduledSigninTaskCreateRequest(user_id=str(request), **values)
