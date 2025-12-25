"""
SQLite Connection Management
============================

Database connection handling with context manager support.
"""

import os
import sqlite3
import logging
from contextlib import contextmanager
from typing import Generator, Optional

from src.core.config import settings
from src.core.exceptions import DatabaseError

logger = logging.getLogger(__name__)


def _configure_connection(conn: sqlite3.Connection, timeout_seconds: float) -> None:
    """配置连接级 PRAGMA（尽量提升并发与稳定性）。"""
    try:
        # 连接级设置（每次连接需要设置）
        conn.execute(f"PRAGMA busy_timeout={int(timeout_seconds * 1000)}")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA synchronous=NORMAL")

        # 数据库级设置（持久化到 DB 文件，重复执行成本较低）
        conn.execute("PRAGMA journal_mode=WAL")
    except sqlite3.Error as e:
        logger.warning(f"Failed to configure sqlite pragmas: {e}")


class DatabaseConnection:
    """
    SQLite database connection manager

    Provides connection pooling and transaction management.
    """

    _instance: Optional['DatabaseConnection'] = None

    def __new__(cls) -> 'DatabaseConnection':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return

        self._db_path = settings.paths.data_dir / 'notes.db'
        self._timeout = 30.0
        self._initialized = True

        # Ensure data directory exists
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def db_path(self) -> str:
        """Get database file path"""
        return str(self._db_path)

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Get database connection with automatic transaction management

        Yields:
            sqlite3.Connection: Database connection

        Raises:
            DatabaseError: On database operation failure
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=self._timeout)
            conn.row_factory = sqlite3.Row
            _configure_connection(conn, timeout_seconds=self._timeout)
            try:
                from src.infrastructure.monitoring.performance.db_tracer import get_db_tracer

                conn = get_db_tracer().enable(conn)
            except Exception:
                # 监控系统故障不应影响主流程
                pass
            yield conn
            conn.commit()
        except sqlite3.OperationalError as e:
            if conn:
                conn.rollback()
            logger.error(f"Database operational error: {e}")
            raise DatabaseError(f"Database operation failed: {e}", operation="connect")
        except sqlite3.IntegrityError as e:
            if conn:
                conn.rollback()
            logger.error(f"Database integrity error: {e}")
            raise DatabaseError(f"Data integrity violation: {e}", operation="integrity")
        except sqlite3.Error as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error: {e}")
            raise DatabaseError(f"Database error: {e}")
        finally:
            if conn:
                conn.close()


# Global connection manager instance
_connection_manager: Optional[DatabaseConnection] = None


def get_db_connection() -> Generator[sqlite3.Connection, None, None]:
    """
    Get database connection context manager

    Usage:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM notes")

    Yields:
        sqlite3.Connection: Database connection
    """
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = DatabaseConnection()
    return _connection_manager.get_connection()
