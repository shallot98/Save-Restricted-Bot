"""
指标聚合器

提供轻量的内存时序聚合能力：保留最近窗口内的指标，并按 name+tags 进行统计聚合。
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, Iterable, List, Tuple

from .metrics import Metric


@dataclass(frozen=True)
class MetricKey:
    name: str
    tags: Tuple[Tuple[str, str], ...]


@dataclass
class MetricStats:
    count: int = 0
    total: float = 0.0
    min_value: float = 0.0
    max_value: float = 0.0

    def add(self, value: float) -> None:
        if self.count == 0:
            self.min_value = value
            self.max_value = value
        else:
            self.min_value = min(self.min_value, value)
            self.max_value = max(self.max_value, value)
        self.count += 1
        self.total += value

    @property
    def avg(self) -> float:
        if self.count == 0:
            return 0.0
        return self.total / self.count

    def to_dict(self) -> Dict[str, Any]:
        return {
            "count": self.count,
            "avg": self.avg,
            "min": self.min_value,
            "max": self.max_value,
            "total": self.total,
        }


class MetricAggregator:
    """内存聚合器（保留最近 retention_seconds 的原始指标）"""

    def __init__(self, *, retention_seconds: int = 3600) -> None:
        self._retention_seconds = max(int(retention_seconds), 60)
        self._lock = threading.RLock()
        self._metrics: Deque[Metric] = deque()

    def add(self, metric: Metric) -> None:
        with self._lock:
            self._metrics.append(metric)
            self._prune_locked(now_epoch=time.time())

    def add_batch(self, metrics: Iterable[Metric]) -> None:
        with self._lock:
            for metric in metrics:
                self._metrics.append(metric)
            self._prune_locked(now_epoch=time.time())

    def snapshot(self, *, window_seconds: int = 60) -> Dict[str, Any]:
        """返回最近窗口的聚合统计（按 name+tags 分组）"""
        window_seconds = max(int(window_seconds), 1)
        cutoff = time.time() - window_seconds

        with self._lock:
            self._prune_locked(now_epoch=time.time())
            stats: Dict[MetricKey, MetricStats] = defaultdict(MetricStats)
            for metric in self._metrics:
                if metric.timestamp.timestamp() < cutoff:
                    continue
                key = MetricKey(metric.name, tuple(sorted(metric.tags.items())))
                stats[key].add(metric.value)

        return {
            "window_seconds": window_seconds,
            "series": [
                {
                    "name": key.name,
                    "tags": dict(key.tags),
                    "stats": value.to_dict(),
                }
                for key, value in stats.items()
            ],
        }

    def recent(self, *, limit: int = 200) -> List[Dict[str, Any]]:
        """返回最近的原始指标（用于调试/展示）"""
        limit = max(int(limit), 1)
        with self._lock:
            self._prune_locked(now_epoch=time.time())
            items = list(self._metrics)[-limit:]
        return [m.to_dict() for m in items]

    def _prune_locked(self, *, now_epoch: float) -> None:
        cutoff = now_epoch - self._retention_seconds
        while self._metrics and self._metrics[0].timestamp.timestamp() < cutoff:
            self._metrics.popleft()

