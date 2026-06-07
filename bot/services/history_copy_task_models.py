"""Persistent task models for history-copy keyboard workflows."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Optional

STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_INTERRUPTED = "interrupted"
FINAL_STATUSES = frozenset({STATUS_COMPLETED, STATUS_FAILED, STATUS_INTERRUPTED})
RESTARTABLE_STATUSES = frozenset({STATUS_FAILED, STATUS_INTERRUPTED})


def describe_history_limit(history_limit: Optional[int]) -> str:
    if history_limit is None:
        return "全部历史"
    return f"最近 {history_limit} 条"


def describe_task_status(status: str) -> str:
    labels = {
        STATUS_RUNNING: "🟡 运行中",
        STATUS_COMPLETED: "✅ 已完成",
        STATUS_FAILED: "❌ 执行失败",
        STATUS_INTERRUPTED: "⚠️ 已中断",
    }
    return labels.get(status, status)


@dataclass(frozen=True)
class HistoryCopyTaskNewRequest:
    task_id: str
    source_chat_ref: str
    source_name: str
    dest_chat_ref: str
    dest_name: str
    state_db_path: str
    history_limit: Optional[int]
    now: float | None = None


@dataclass(frozen=True)
class HistoryCopyTaskConfig:
    task_id: str
    source_chat_ref: str
    source_name: str
    dest_chat_ref: str
    dest_name: str
    state_db_path: str
    history_limit: Optional[int] = None
    status: str = STATUS_RUNNING
    status_message: str = ""
    error_message: str = ""
    source_chat_id: str = ""
    dest_chat_id: str = ""
    scanned_count: int = 0
    copied_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    created_at: float = 0.0
    started_at: float = 0.0
    finished_at: float = 0.0

    @classmethod
    def new(
        cls,
        request: HistoryCopyTaskNewRequest,
    ) -> "HistoryCopyTaskConfig":
        timestamp = float(request.now if request.now is not None else time.time())
        return cls(
            task_id=request.task_id,
            source_chat_ref=str(request.source_chat_ref).strip(),
            source_name=str(request.source_name).strip() or str(request.source_chat_ref).strip(),
            dest_chat_ref=str(request.dest_chat_ref).strip(),
            dest_name=str(request.dest_name).strip() or str(request.dest_chat_ref).strip(),
            state_db_path=str(request.state_db_path).strip(),
            history_limit=request.history_limit,
            status=STATUS_RUNNING,
            created_at=timestamp,
            started_at=timestamp,
        )

    @classmethod
    def from_dict(cls, task_id: str, data: dict[str, Any]) -> "HistoryCopyTaskConfig":
        history_limit_raw = data.get("history_limit")
        history_limit = None if history_limit_raw in (None, "") else max(int(history_limit_raw), 1)
        status = str(data.get("status") or STATUS_INTERRUPTED)
        if status not in {STATUS_RUNNING, STATUS_COMPLETED, STATUS_FAILED, STATUS_INTERRUPTED}:
            status = STATUS_INTERRUPTED
        return cls(
            task_id=str(task_id),
            source_chat_ref=str(data.get("source_chat_ref") or "").strip(),
            source_name=str(data.get("source_name") or "").strip(),
            dest_chat_ref=str(data.get("dest_chat_ref") or "").strip(),
            dest_name=str(data.get("dest_name") or "").strip(),
            state_db_path=str(data.get("state_db_path") or "").strip(),
            history_limit=history_limit,
            status=status,
            status_message=str(data.get("status_message") or "").strip(),
            error_message=str(data.get("error_message") or "").strip(),
            source_chat_id=str(data.get("source_chat_id") or "").strip(),
            dest_chat_id=str(data.get("dest_chat_id") or "").strip(),
            scanned_count=max(int(data.get("scanned_count", 0)), 0),
            copied_count=max(int(data.get("copied_count", 0)), 0),
            skipped_count=max(int(data.get("skipped_count", 0)), 0),
            failed_count=max(int(data.get("failed_count", 0)), 0),
            created_at=max(float(data.get("created_at", 0.0)), 0.0),
            started_at=max(float(data.get("started_at", 0.0)), 0.0),
            finished_at=max(float(data.get("finished_at", 0.0)), 0.0),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_chat_ref": self.source_chat_ref,
            "source_name": self.source_name,
            "dest_chat_ref": self.dest_chat_ref,
            "dest_name": self.dest_name,
            "state_db_path": self.state_db_path,
            "history_limit": self.history_limit,
            "status": self.status,
            "status_message": self.status_message,
            "error_message": self.error_message,
            "source_chat_id": self.source_chat_id,
            "dest_chat_id": self.dest_chat_id,
            "scanned_count": self.scanned_count,
            "copied_count": self.copied_count,
            "skipped_count": self.skipped_count,
            "failed_count": self.failed_count,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }
