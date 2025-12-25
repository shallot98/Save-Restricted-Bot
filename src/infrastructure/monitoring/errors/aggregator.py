"""
错误聚合器

按 (error_type + stack_hash) 聚合错误，维护计数与时间分布，用于后续趋势分析和告警去重。
"""

from __future__ import annotations

import hashlib
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional, Tuple


def _hash_stack(stacktrace: str) -> str:
    normalized = (stacktrace or "").strip().encode("utf-8", errors="ignore")
    return hashlib.sha256(normalized).hexdigest()


@dataclass
class ErrorGroup:
    fingerprint: str
    error_type: str
    stack_hash: str
    first_seen_epoch: float
    last_seen_epoch: float
    count: int = 0
    last_message: str = ""
    last_context: Dict[str, Any] = field(default_factory=dict)
    last_stacktrace: str = ""
    occurrences: Deque[float] = field(default_factory=deque)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fingerprint": self.fingerprint,
            "error_type": self.error_type,
            "stack_hash": self.stack_hash,
            "count": self.count,
            "first_seen_epoch": self.first_seen_epoch,
            "last_seen_epoch": self.last_seen_epoch,
            "last_message": self.last_message,
            "last_context": self.last_context,
        }


class ErrorAggregator:
    """错误聚合器（线程安全）"""

    def __init__(self, *, aggregation_window_seconds: int = 300, retention_seconds: int = 3600) -> None:
        self._aggregation_window_seconds = max(int(aggregation_window_seconds), 1)
        self._retention_seconds = max(int(retention_seconds), self._aggregation_window_seconds)
        self._lock = threading.RLock()
        self._groups: Dict[str, ErrorGroup] = {}
        self._events: Deque[Tuple[float, str]] = deque()

    @property
    def aggregation_window_seconds(self) -> int:
        return self._aggregation_window_seconds

    @property
    def retention_seconds(self) -> int:
        return self._retention_seconds

    def add(
        self,
        *,
        error_type: str,
        error_message: str,
        stacktrace: str,
        context: Optional[Dict[str, Any]] = None,
        at_epoch: Optional[float] = None,
    ) -> ErrorGroup:
        now = time.time() if at_epoch is None else float(at_epoch)
        context = context or {}
        stack_hash = _hash_stack(stacktrace)
        fingerprint = hashlib.sha256(f"{error_type}|{stack_hash}".encode("utf-8")).hexdigest()

        with self._lock:
            self._prune_locked(now_epoch=now)
            group = self._groups.get(fingerprint)
            if group is None or (now - group.last_seen_epoch) > self._aggregation_window_seconds:
                group = ErrorGroup(
                    fingerprint=fingerprint,
                    error_type=error_type,
                    stack_hash=stack_hash,
                    first_seen_epoch=now,
                    last_seen_epoch=now,
                    count=0,
                )
                self._groups[fingerprint] = group

            group.count += 1
            group.last_seen_epoch = now
            group.last_message = (error_message or "")[:500]
            group.last_context = context
            group.last_stacktrace = stacktrace
            group.occurrences.append(now)

            self._events.append((now, fingerprint))
            self._prune_locked(now_epoch=now)
            return group

    def get_group(self, fingerprint: str) -> Optional[ErrorGroup]:
        with self._lock:
            return self._groups.get(fingerprint)

    def groups(self) -> List[ErrorGroup]:
        with self._lock:
            self._prune_locked(now_epoch=time.time())
            return list(self._groups.values())

    def recent_events(self, *, window_seconds: int = 300) -> List[Tuple[float, str]]:
        window_seconds = max(int(window_seconds), 1)
        cutoff = time.time() - window_seconds
        with self._lock:
            self._prune_locked(now_epoch=time.time())
            return [(ts, fp) for ts, fp in self._events if ts >= cutoff]

    def _prune_locked(self, *, now_epoch: float) -> None:
        cutoff = now_epoch - self._retention_seconds
        while self._events and self._events[0][0] < cutoff:
            self._events.popleft()

        stale_groups = [fp for fp, g in self._groups.items() if g.last_seen_epoch < cutoff]
        for fp in stale_groups:
            self._groups.pop(fp, None)

        # 修剪每个组的 occurrences
        for group in self._groups.values():
            while group.occurrences and group.occurrences[0] < cutoff:
                group.occurrences.popleft()

