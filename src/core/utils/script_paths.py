"""Resolution of production runtime helper scripts (scripts/runtime/).

These scripts are launched via ``subprocess`` by the magnet calibration flows.
They are production components, not one-off tooling: a missing file must be
reported loudly instead of degrading into a silent ``None``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Set

logger = logging.getLogger(__name__)

# src/core/utils/script_paths.py -> repository root.
# Inside the container the same derivation yields /app (Dockerfile: COPY . .),
# so /app/scripts/runtime/<name> is resolved without a special case.
REPO_ROOT = Path(__file__).resolve().parents[3]
RUNTIME_SCRIPTS_DIR = REPO_ROOT / "scripts" / "runtime"

_missing_reported: Set[str] = set()


def resolve_runtime_script(script_name: str) -> Optional[Path]:
    """Return the absolute path of a runtime script, or None if it is missing.

    A missing script is logged at ERROR level once per script name (rate
    limited to avoid flooding the scheduler loop); the flag is cleared as soon
    as the file reappears.
    """
    path = RUNTIME_SCRIPTS_DIR / script_name
    if path.is_file():
        _missing_reported.discard(script_name)
        return path
    _report_missing(script_name, path)
    return None


def _report_missing(script_name: str, path: Path) -> None:
    if script_name in _missing_reported:
        logger.debug("运行时校准脚本仍然缺失: %s", path)
        return
    _missing_reported.add(script_name)
    logger.error(
        "❌ 运行时校准脚本缺失: %s（期望路径 %s）。"
        "该脚本是生产组件，缺失将导致磁力链校准持续失败，请勿归档或删除 scripts/runtime/。",
        script_name,
        path,
    )
