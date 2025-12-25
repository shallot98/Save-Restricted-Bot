"""
SQLite 持久化存储

用于将监控指标/错误事件写入独立数据库文件，避免污染业务数据库。
"""

from __future__ import annotations

import os
import sqlite3
import threading
import time
from typing import Any, Dict, Iterable, Optional

from src.core.config import settings
from src.infrastructure.monitoring.core.metrics import Metric

_sqlite_store: Optional["SQLiteStore"] = None


def _env_int(key: str, default: int) -> int:
    value = os.environ.get(key)
    if value is None:
        return default
    try:
        return int(value.strip())
    except ValueError:
        return default


class SQLiteStore:
    def __init__(self, *, db_path: Optional[str] = None) -> None:
        self._db_path = db_path or str(settings.paths.data_dir / "monitoring.db")
        self._lock = threading.RLock()
        self._init_schema()

    @property
    def db_path(self) -> str:
        return self._db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ts_epoch REAL NOT NULL,
                        name TEXT NOT NULL,
                        metric_type TEXT NOT NULL,
                        value REAL NOT NULL,
                        tags_json TEXT,
                        metadata_json TEXT
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_metrics_ts ON metrics(ts_epoch)
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_metrics_name_ts ON metrics(name, ts_epoch)
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS errors (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ts_epoch REAL NOT NULL,
                        fingerprint TEXT NOT NULL,
                        error_type TEXT NOT NULL,
                        message TEXT NOT NULL,
                        stacktrace TEXT,
                        context_json TEXT
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_errors_ts ON errors(ts_epoch)
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_errors_fp_ts ON errors(fingerprint, ts_epoch)
                    """
                )

    def insert_metric(self, metric: Metric) -> None:
        import json

        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO metrics (ts_epoch, name, metric_type, value, tags_json, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        metric.timestamp.timestamp(),
                        metric.name,
                        metric.metric_type.value,
                        float(metric.value),
                        json.dumps(metric.tags, ensure_ascii=False),
                        json.dumps(metric.metadata, ensure_ascii=False, default=str),
                    ),
                )

    def insert_metrics(self, metrics: Iterable[Metric]) -> None:
        import json

        rows = [
            (
                m.timestamp.timestamp(),
                m.name,
                m.metric_type.value,
                float(m.value),
                json.dumps(m.tags, ensure_ascii=False),
                json.dumps(m.metadata, ensure_ascii=False, default=str),
            )
            for m in metrics
        ]
        if not rows:
            return

        with self._lock:
            with self._connect() as conn:
                conn.executemany(
                    """
                    INSERT INTO metrics (ts_epoch, name, metric_type, value, tags_json, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )

    def insert_error(
        self,
        *,
        fingerprint: str,
        error_type: str,
        message: str,
        stacktrace: str,
        context: Dict[str, Any],
        at_epoch: Optional[float] = None,
    ) -> None:
        import json

        ts_epoch = time.time() if at_epoch is None else float(at_epoch)
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO errors (ts_epoch, fingerprint, error_type, message, stacktrace, context_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        ts_epoch,
                        fingerprint,
                        error_type,
                        message[:500],
                        stacktrace[:2000],
                        json.dumps(context, ensure_ascii=False, default=str),
                    ),
                )

    def cleanup(self, *, retention_days: Optional[int] = None) -> None:
        retention_days = retention_days if retention_days is not None else _env_int("MONITORING_DB_RETENTION_DAYS", 30)
        retention_days = max(int(retention_days), 1)
        cutoff = time.time() - retention_days * 86400

        with self._lock:
            with self._connect() as conn:
                conn.execute("DELETE FROM metrics WHERE ts_epoch < ?", (cutoff,))
                conn.execute("DELETE FROM errors WHERE ts_epoch < ?", (cutoff,))


def get_sqlite_store() -> SQLiteStore:
    global _sqlite_store
    if _sqlite_store is None:
        _sqlite_store = SQLiteStore()
    return _sqlite_store

