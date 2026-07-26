"""Background scheduler that periodically runs monitored-source catch-up scans."""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Optional

from bot.services.watch_catchup_scanner import WatchCatchupScanner

logger = logging.getLogger(__name__)

DEFAULT_INTERVAL_SECONDS = 30

_scheduler: Optional["WatchCatchupScheduler"] = None


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def catchup_enabled() -> bool:
    raw = (os.environ.get("WATCH_CATCHUP_ENABLED") or "1").strip().lower()
    return raw not in {"0", "false", "off", "no"}


def catchup_interval_seconds() -> int:
    return max(10, min(_env_int("WATCH_CATCHUP_INTERVAL", DEFAULT_INTERVAL_SECONDS), 600))


class WatchCatchupScheduler:
    def __init__(
        self,
        acc: Any,
        message_queue: Any,
        *,
        watch_service: Any = None,
        interval: Optional[int] = None,
        run_immediately: bool = True,
    ) -> None:
        self._acc = acc
        self._message_queue = message_queue
        self.interval = interval if interval is not None else catchup_interval_seconds()
        self._run_immediately = run_immediately
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self._scanner = WatchCatchupScanner(acc, message_queue, watch_service=watch_service)

    def start(self) -> None:
        if not catchup_enabled():
            logger.info("watch catch-up disabled via WATCH_CATCHUP_ENABLED")
            return
        if self._acc is None or self._message_queue is None:
            logger.warning("watch catch-up skipped: missing user client or queue")
            return
        if self.running:
            logger.warning("watch catch-up scheduler already running")
            return

        self.running = True
        self.thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="WatchCatchupScheduler",
        )
        self.thread.start()
        logger.info("watch catch-up scheduler started (interval=%ss)", self.interval)

    def stop(self) -> None:
        if not self.running:
            return
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("watch catch-up scheduler stopped")

    def _run(self) -> None:
        if self._run_immediately:
            # Short settle delay after peer-cache/startup finishes.
            self._sleep_interruptible(3)
            self._safe_scan("startup")

        while self.running:
            self._sleep_interruptible(self.interval)
            if not self.running:
                break
            self._safe_scan("interval")

    def _safe_scan(self, reason: str) -> None:
        try:
            result = self._scanner.scan_once()
            logger.debug(
                "watch catch-up (%s): scanned=%s enqueued=%s init=%s errors=%s",
                reason,
                result.sources_scanned,
                result.messages_enqueued,
                result.sources_initialized,
                result.errors,
            )
        except Exception:
            logger.exception("watch catch-up scan crashed (%s)", reason)

    def _sleep_interruptible(self, seconds: float) -> None:
        end = time.time() + max(0.0, seconds)
        while self.running and time.time() < end:
            time.sleep(min(0.5, end - time.time()))


def start_watch_catchup_scheduler(
    acc: Any,
    message_queue: Any,
    *,
    watch_service: Any = None,
    interval: Optional[int] = None,
) -> None:
    """``watch_service`` 由 ``main.py`` 从 ``BotServices`` 取出后传入。"""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        return
    _scheduler = WatchCatchupScheduler(
        acc, message_queue, watch_service=watch_service, interval=interval
    )
    _scheduler.start()


def stop_watch_catchup_scheduler() -> None:
    global _scheduler
    if _scheduler is None:
        return
    _scheduler.stop()
    _scheduler = None
