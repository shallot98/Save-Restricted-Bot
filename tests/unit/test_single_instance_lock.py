"""
Unit tests for single-instance lock behavior.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from src.core.utils.single_instance_lock import acquire_single_instance_lock


def _run_lock_attempt(lock_path: Path, cwd: Path) -> subprocess.CompletedProcess[str]:
    code = """
import sys
from pathlib import Path

from src.core.utils.single_instance_lock import acquire_single_instance_lock, SingleInstanceError

lock_path = Path(sys.argv[1])
try:
    handle = acquire_single_instance_lock(lock_path)
except SingleInstanceError:
    raise SystemExit(2)
else:
    handle.close()
    raise SystemExit(0)
""".strip()
    return subprocess.run(
        [sys.executable, "-c", code, str(lock_path)],
        capture_output=True,
        text=True,
        cwd=str(cwd),
        timeout=10,
    )


def test_single_instance_lock_blocks_second_process(tmp_path: Path) -> None:
    lock_path = tmp_path / "bot.lock"

    project_root = Path(__file__).resolve().parents[2]
    handle = acquire_single_instance_lock(lock_path)
    try:
        result = _run_lock_attempt(lock_path, cwd=project_root)
        assert result.returncode == 2
    finally:
        handle.close()

    result = _run_lock_attempt(lock_path, cwd=project_root)
    assert result.returncode == 0

