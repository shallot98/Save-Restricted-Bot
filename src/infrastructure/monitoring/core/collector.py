"""
指标收集器

以最小侵入的方式收集指标：写入内存队列，由后台线程批量提交给聚合器。
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Iterable, Optional, Protocol

from .aggregator import MetricAggregator
from .metrics import Metric

logger = logging.getLogger(__name__)


class MetricPersistStore(Protocol):
    def insert_metrics(self, metrics: Iterable[Metric]) -> None: ...


class MetricCollector:
    """指标收集器（异步批量）"""

    def __init__(
        self,
        aggregator: MetricAggregator,
        *,
        enabled: bool = True,
        batch_size: int = 200,
        flush_interval_seconds: float = 1.0,
        max_queue_size: int = 10_000,
        persist_store: Optional[MetricPersistStore] = None,
        persist_interval_seconds: float = 5.0,
        persist_batch_size: int = 1000,
        max_persist_batches: int = 2_000,
    ) -> None:
        self._aggregator = aggregator
        self._enabled = enabled
        self._batch_size = max(batch_size, 1)
        self._flush_interval_seconds = max(flush_interval_seconds, 0.01)
        self._queue: "queue.Queue[Metric]" = queue.Queue(maxsize=max_queue_size)
        self._stop_event = threading.Event()
        self._worker: Optional[threading.Thread] = None
        self._persist_store = persist_store
        self._persist_interval_seconds = max(float(persist_interval_seconds), 0.5)
        self._persist_batch_size = max(int(persist_batch_size), 1)
        self._persist_queue: "queue.Queue[list[Metric]]" = queue.Queue(maxsize=max(int(max_persist_batches), 1))
        self._persist_worker: Optional[threading.Thread] = None

        if self._enabled:
            self.start()

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def persistence_enabled(self) -> bool:
        return self._enabled and self._persist_store is not None

    def start(self) -> None:
        if self._worker and self._worker.is_alive():
            if self._persist_worker and self._persist_worker.is_alive():
                return

        self._stop_event.clear()
        self._worker = threading.Thread(target=self._run, name="metric-collector", daemon=True)
        self._worker.start()

        if self.persistence_enabled:
            if not (self._persist_worker and self._persist_worker.is_alive()):
                self._persist_worker = threading.Thread(target=self._run_persist, name="metric-persist", daemon=True)
                self._persist_worker.start()

    def stop(self, timeout_seconds: float = 2.0) -> None:
        self._stop_event.set()
        if self._worker:
            self._worker.join(timeout=timeout_seconds)
        if self._persist_worker:
            self._persist_worker.join(timeout=timeout_seconds)

    def collect(self, metric: Metric) -> None:
        if not self._enabled:
            return
        try:
            self._queue.put_nowait(metric)
        except queue.Full:
            logger.warning("监控指标队列已满，丢弃指标: %s", metric.name)

    def collect_many(self, metrics: Iterable[Metric]) -> None:
        if not self._enabled:
            return
        for metric in metrics:
            self.collect(metric)

    def flush(self) -> None:
        """尽力立即刷新队列中的指标（非阻塞）"""
        batch: list[Metric] = []
        while len(batch) < self._batch_size:
            try:
                batch.append(self._queue.get_nowait())
            except queue.Empty:
                break

        if batch:
            self._aggregator.add_batch(batch)
            self._enqueue_persist(batch)

    def _run(self) -> None:
        batch: list[Metric] = []
        last_flush = time.monotonic()

        while not self._stop_event.is_set():
            timeout = max(self._flush_interval_seconds - (time.monotonic() - last_flush), 0.01)
            try:
                metric = self._queue.get(timeout=timeout)
                batch.append(metric)
            except queue.Empty:
                pass

            now = time.monotonic()
            should_flush = len(batch) >= self._batch_size or (batch and (now - last_flush) >= self._flush_interval_seconds)
            if not should_flush:
                continue

            try:
                self._aggregator.add_batch(batch)
                self._enqueue_persist(batch)
            except Exception:
                logger.exception("指标批量提交失败（已忽略）")
            finally:
                batch = []
                last_flush = now

        # 退出前尽力 flush
        try:
            self._aggregator.add_batch(batch)
            self._enqueue_persist(batch)
        except Exception:
            logger.exception("指标退出刷新失败（已忽略）")

    def _enqueue_persist(self, metrics: list[Metric]) -> None:
        if not self.persistence_enabled or not metrics:
            return
        try:
            self._persist_queue.put_nowait(list(metrics))
        except queue.Full:
            logger.warning("指标持久化队列已满，丢弃 %d 条指标", len(metrics))

    def _run_persist(self) -> None:
        if not self._persist_store:
            return

        buffer: list[Metric] = []
        last_flush = time.monotonic()

        while not self._stop_event.is_set():
            timeout = max(self._persist_interval_seconds - (time.monotonic() - last_flush), 0.1)
            try:
                chunk = self._persist_queue.get(timeout=timeout)
                buffer.extend(chunk)
            except queue.Empty:
                pass

            now = time.monotonic()
            should_flush = bool(buffer) and (
                len(buffer) >= self._persist_batch_size or (now - last_flush) >= self._persist_interval_seconds
            )
            if not should_flush:
                continue

            try:
                self._persist_store.insert_metrics(buffer)
            except Exception:
                logger.exception("指标持久化失败（已忽略）")
            finally:
                buffer = []
                last_flush = now

        try:
            while True:
                buffer.extend(self._persist_queue.get_nowait())
        except queue.Empty:
            pass

        if buffer:
            try:
                self._persist_store.insert_metrics(buffer)
            except Exception:
                logger.exception("指标退出持久化失败（已忽略）")
