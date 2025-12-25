"""
SQLite 持久化存储（v2）

用于将监控指标/错误事件写入独立数据库文件，支持简单查询用于仪表盘展示。
"""

from __future__ import annotations

import os
import logging
import sqlite3
import threading
import time
from typing import Any, Dict, Iterable, List, Optional

from src.core.config import settings
from src.infrastructure.monitoring.core.metrics import Metric

logger = logging.getLogger(__name__)

_sqlite_store2: Optional["SQLiteStore2"] = None


def _env_int(key: str, default: int) -> int:
    value = os.environ.get(key)
    if value is None:
        return default
    try:
        return int(value.strip())
    except ValueError:
        return default


class SQLiteStore2:
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
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
        except Exception as e:
            logger.debug("monitoring sqlite PRAGMA 失败，已忽略: %s", e, exc_info=True)
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
                conn.execute("CREATE INDEX IF NOT EXISTS idx_metrics_ts ON metrics(ts_epoch)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_metrics_name_ts ON metrics(name, ts_epoch)")
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
                conn.execute("CREATE INDEX IF NOT EXISTS idx_errors_ts ON errors(ts_epoch)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_errors_fp_ts ON errors(fingerprint, ts_epoch)")

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

    def metrics_recent(
        self,
        *,
        limit: int = 200,
        name: Optional[str] = None,
        since_epoch: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        import json

        limit = max(int(limit), 1)
        clauses: List[str] = []
        params: List[Any] = []

        if name:
            clauses.append("name = ?")
            params.append(name)
        if since_epoch is not None:
            clauses.append("ts_epoch >= ?")
            params.append(float(since_epoch))

        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = f"""
            SELECT ts_epoch, name, metric_type, value, tags_json, metadata_json
            FROM metrics
            {where}
            ORDER BY ts_epoch DESC
            LIMIT ?
        """
        params.append(limit)

        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(sql, params).fetchall()

        items: List[Dict[str, Any]] = []
        for row in rows:
            try:
                tags = json.loads(row["tags_json"] or "{}")
            except Exception:
                tags = {}
            try:
                metadata = json.loads(row["metadata_json"] or "{}")
            except Exception:
                metadata = {}
            items.append(
                {
                    "ts_epoch": float(row["ts_epoch"]),
                    "name": row["name"],
                    "metric_type": row["metric_type"],
                    "value": float(row["value"]),
                    "tags": tags,
                    "metadata": metadata,
                }
            )
        return items

    def cleanup(self, *, retention_days: Optional[int] = None) -> None:
        retention_days = retention_days if retention_days is not None else _env_int("MONITORING_DB_RETENTION_DAYS", 30)
        retention_days = max(int(retention_days), 1)
        cutoff = time.time() - retention_days * 86400

        with self._lock:
            with self._connect() as conn:
                conn.execute("DELETE FROM metrics WHERE ts_epoch < ?", (cutoff,))
                conn.execute("DELETE FROM errors WHERE ts_epoch < ?", (cutoff,))


def get_sqlite_store2() -> SQLiteStore2:
    global _sqlite_store2
    if _sqlite_store2 is None:
        _sqlite_store2 = SQLiteStore2()
    return _sqlite_store2
