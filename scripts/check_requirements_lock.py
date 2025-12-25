#!/usr/bin/env python3
"""
检查 requirements.lock 是否覆盖 requirements.runtime.txt（可选覆盖 requirements.dev.txt）。

用法：
  python3 scripts/check_requirements_lock.py
  python3 scripts/check_requirements_lock.py --include-dev
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


_NAME_SPLIT_RE = re.compile(r"[<=>!~;\\[]", re.IGNORECASE)


def _normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name.strip()).lower()


def _parse_requirement_names(path: Path) -> list[str]:
    names: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("-r") or line.startswith("--requirement"):
            continue
        if line.startswith("-c") or line.startswith("--constraint"):
            continue
        name = _NAME_SPLIT_RE.split(line, maxsplit=1)[0].strip()
        if not name:
            continue
        names.append(_normalize_name(name))
    return names


def _parse_lock_names(path: Path) -> set[str]:
    names: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "==" not in line:
            continue
        name = line.split("==", 1)[0].strip()
        if not name:
            continue
        names.add(_normalize_name(name))
    return names


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--include-dev", action="store_true", help="同时检查 requirements.dev.txt")
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[1]
    runtime_path = repo_root / "requirements.runtime.txt"
    dev_path = repo_root / "requirements.dev.txt"
    lock_path = repo_root / "requirements.lock"

    missing: list[str] = []
    lock_names = _parse_lock_names(lock_path)

    for name in _parse_requirement_names(runtime_path):
        if name not in lock_names:
            missing.append(name)

    if args.include_dev:
        for name in _parse_requirement_names(dev_path):
            if name not in lock_names:
                missing.append(name)

    if missing:
        missing_sorted = sorted(set(missing))
        print("requirements.lock 缺少以下依赖的 pinned 版本：", file=sys.stderr)
        for name in missing_sorted:
            print(f"- {name}", file=sys.stderr)
        return 1

    print("OK: requirements.lock 已覆盖 requirements.runtime.txt" + (" + requirements.dev.txt" if args.include_dev else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

