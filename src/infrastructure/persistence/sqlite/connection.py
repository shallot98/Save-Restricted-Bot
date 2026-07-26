"""
SQLite Connection Management
============================

Database connection handling with context manager support.
"""

import os
import sqlite3
import logging
from contextlib import AbstractContextManager, contextmanager
from typing import Generator, Optional

from src.core.config import settings
from src.core.exceptions import DatabaseError

logger = logging.getLogger(__name__)


def _rollback(conn: Optional[sqlite3.Connection]) -> None:
    """回滚未提交事务；回滚本身失败只记录，不掩盖原始异常。"""
    if conn is None:
        return
    try:
        conn.rollback()
    except sqlite3.Error as e:
        logger.error(f"Rollback failed: {e}")


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
            # NOTE: monitoring 子系统已停用，此处不再包装 db_tracer
            # （db.query.duration_ms 曾占 monitoring.db 写入量的 68.8%）。
            yield conn
            conn.commit()
        except sqlite3.OperationalError as e:
            _rollback(conn)
            logger.error(f"Database operational error: {e}")
            raise DatabaseError(f"Database operation failed: {e}", operation="connect")
        except sqlite3.IntegrityError as e:
            _rollback(conn)
            logger.error(f"Database integrity error: {e}")
            raise DatabaseError(f"Data integrity violation: {e}", operation="integrity")
        except sqlite3.Error as e:
            _rollback(conn)
            logger.error(f"Database error: {e}")
            raise DatabaseError(f"Database error: {e}")
        except Exception:
            # 非 sqlite 异常此前会跳过 commit 直奔 close()：无回滚、无日志。
            # 这里显式回滚并记录后原样抛出，不做任何吞错。
            _rollback(conn)
            logger.exception("Non-sqlite error in database transaction; transaction rolled back")
            raise
        finally:
            if conn:
                conn.close()


# Global connection manager instance
_connection_manager: Optional[DatabaseConnection] = None


def get_db_connection() -> AbstractContextManager[sqlite3.Connection]:
    """
    Get database connection context manager

    Usage:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM notes")

    Returns:
        AbstractContextManager[sqlite3.Connection]: 进入 ``with`` 后得到数据库连接。

    注意：本函数**不是**生成器函数，它返回 ``@contextmanager`` 装饰过的
    ``DatabaseConnection.get_connection()`` 的调用结果（一个上下文管理器）。
    早先标注为 ``Generator[...]`` 与运行时不符，导致所有调用方的 ``with`` 语句
    被判为访问不存在的 ``__enter__``/``__exit__``（40+ 处连锁误报）。
    """
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = DatabaseConnection()
    return _connection_manager.get_connection()
