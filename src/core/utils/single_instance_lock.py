"""
Single Instance Lock
====================

Best-effort process-level lock to prevent multiple instances operating on the same
DATA_DIR concurrently.

This is primarily to make the project's current single-instance constraint explicit
without introducing external shared state.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TextIO


class SingleInstanceError(RuntimeError):
    """Raised when a single-instance lock cannot be acquired."""


def acquire_single_instance_lock(lock_path: Path) -> TextIO:
    """
    Acquire a non-blocking exclusive lock on a file.

    The returned file handle must be kept open for the lock to remain held.
    Closing it (or process exit) releases the lock.
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    lock_file = open(lock_path, "a+", encoding="utf-8")
    try:
        if sys.platform == "win32":
            import msvcrt

            try:
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as e:
                raise SingleInstanceError(f"Failed to acquire lock: {lock_path}") from e
        else:
            import fcntl

            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as e:
                raise SingleInstanceError(f"Another instance is already running (lock: {lock_path})") from e
            except OSError as e:
                raise SingleInstanceError(f"Failed to acquire lock: {lock_path}") from e

        lock_file.seek(0)
        lock_file.truncate(0)
        lock_file.write(str(os.getpid()))
        lock_file.flush()
        return lock_file
    except Exception:
        lock_file.close()
        raise

