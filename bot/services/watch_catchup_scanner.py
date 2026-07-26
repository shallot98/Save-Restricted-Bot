"""Scan monitored sources for missed updates and re-enqueue them."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Callable, Iterable, List, Optional, Sequence

from bot.services.watch_catchup_store import (
    advance_cursor,
    ensure_cursor_initialized,
    get_cursor,
)

logger = logging.getLogger(__name__)

DEFAULT_LOOKBACK = 50
DEFAULT_MAX_ENQUEUE_PER_SOURCE = 20


@dataclass(frozen=True, kw_only=True)
class CatchupScanResult:
    sources_scanned: int = 0
    messages_enqueued: int = 0
    sources_initialized: int = 0
    errors: int = 0


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def catchup_lookback() -> int:
    return max(5, min(_env_int("WATCH_CATCHUP_LOOKBACK", DEFAULT_LOOKBACK), 200))


def catchup_max_enqueue_per_source() -> int:
    return max(1, min(_env_int("WATCH_CATCHUP_MAX_ENQUEUE", DEFAULT_MAX_ENQUEUE_PER_SOURCE), 100))


class WatchCatchupScanner:
    """Pull recent history for monitored chats and feed missed messages into auto-forward."""

    def __init__(
        self,
        acc: Any,
        message_queue: Any,
        *,
        watch_service: Any = None,
        process_message: Optional[Callable[[Any, Any], Any]] = None,
        get_monitored_sources: Optional[Callable[[], Iterable[str]]] = None,
        lookback: Optional[int] = None,
        max_enqueue_per_source: Optional[int] = None,
    ) -> None:
        """``watch_service`` 由调度器从 ``BotServices`` 传入（组合根装配）。

        显式传 ``process_message`` / ``get_monitored_sources`` 的调用方（单测）
        不需要它；两个默认实现取用时缺失会立刻抛错，不回落到全局容器。
        """
        self._acc = acc
        self._message_queue = message_queue
        self._watch_service = watch_service
        self._process_message = process_message or self._default_process_message
        self._get_monitored_sources = get_monitored_sources or self._default_monitored_sources
        self._lookback = lookback if lookback is not None else catchup_lookback()
        self._max_enqueue = (
            max_enqueue_per_source
            if max_enqueue_per_source is not None
            else catchup_max_enqueue_per_source()
        )

    def _require_watch_service(self) -> Any:
        if self._watch_service is None:
            raise RuntimeError(
                "WatchCatchupScanner 未注入 WatchService；"
                "请检查 main.py → start_watch_catchup_scheduler 的装配路径"
            )
        return self._watch_service

    def _default_process_message(self, message: Any, message_queue: Any) -> Any:
        # 延迟 import：bot.handlers.auto_forward_pipeline 反向依赖 bot.services，
        # 顶层导入会成环。
        from bot.handlers.auto_forward_pipeline import process_auto_forward_message

        return process_auto_forward_message(
            message, message_queue, watch_service=self._require_watch_service()
        )

    def _default_monitored_sources(self) -> List[str]:
        return list(self._require_watch_service().get_monitored_sources())

    def scan_once(self) -> CatchupScanResult:
        if self._acc is None or self._message_queue is None:
            return CatchupScanResult()

        sources = [str(s) for s in self._get_monitored_sources() if s]
        if not sources:
            return CatchupScanResult()

        scanned = 0
        enqueued = 0
        initialized = 0
        errors = 0

        for source in sources:
            try:
                result = self._scan_source(source)
            except Exception:
                logger.exception("catch-up scan failed for source=%s", source)
                errors += 1
                continue
            scanned += 1
            enqueued += result.messages_enqueued
            initialized += result.sources_initialized
            errors += result.errors

        if enqueued or initialized:
            logger.info(
                "catch-up finished: sources=%s enqueued=%s initialized=%s errors=%s",
                scanned,
                enqueued,
                initialized,
                errors,
            )
        return CatchupScanResult(
            sources_scanned=scanned,
            messages_enqueued=enqueued,
            sources_initialized=initialized,
            errors=errors,
        )

    def _scan_source(self, source_chat_id: str) -> CatchupScanResult:
        history = self._fetch_history(source_chat_id)
        if not history:
            return CatchupScanResult(sources_scanned=1)

        latest_id = max(int(msg.id) for msg in history if getattr(msg, "id", None) is not None)
        cursor = get_cursor(source_chat_id)
        if cursor is None or not cursor.initialized:
            ensure_cursor_initialized(source_chat_id, latest_id)
            logger.info(
                "catch-up initialized source=%s last_seen_id=%s (no backfill)",
                source_chat_id,
                latest_id,
            )
            return CatchupScanResult(sources_scanned=1, sources_initialized=1)

        candidates = self._select_candidates(history, cursor.last_seen_id)
        if not candidates:
            # Keep high-water mark moving when history has newer service/empty gaps.
            if latest_id > cursor.last_seen_id:
                advance_cursor(source_chat_id, latest_id)
            return CatchupScanResult(sources_scanned=1)

        enqueued = 0
        for message in candidates[: self._max_enqueue]:
            progress = self._process_message(message, self._message_queue)
            if not self._progress_allows_cursor_advance(progress):
                # 候选按 message_id 升序，停在第一条未处理成功的消息上即可保证
                # 它以及其后的消息都仍在游标之后，下一轮补扫会重新投递。
                logger.warning(
                    "catch-up 停止推进游标：消息未成功入队，等待下轮补扫重投: "
                    "source=%s message_id=%s",
                    source_chat_id,
                    message.id,
                )
                break
            advance_cursor(source_chat_id, int(message.id))
            enqueued += 1
            logger.info(
                "catch-up enqueued missed message: source=%s message_id=%s",
                source_chat_id,
                message.id,
            )

        return CatchupScanResult(sources_scanned=1, messages_enqueued=enqueued)

    @staticmethod
    def _progress_allows_cursor_advance(progress: Any) -> bool:
        """Read the auto-forward pipeline's progress contract (``MessageProgress``).

        The durable cursor may only move past a message the pipeline reports as
        handled. Anything that does not report progress blocks the cursor: a
        silently advanced cursor means the message is never re-scanned.
        """
        may_advance = getattr(progress, "cursor_may_advance", None)
        if isinstance(may_advance, bool):
            return may_advance

        logger.warning(
            "catch-up 处理器未上报入队进度（返回 %s），保守起见不推进游标",
            type(progress).__name__,
        )
        return False

    def _fetch_history(self, source_chat_id: str) -> List[Any]:
        chat_id = self._coerce_chat_id(source_chat_id)
        try:
            return self._read_history(chat_id)
        except (ValueError, KeyError) as exc:
            if not self._is_peer_error(exc):
                raise
            logger.warning(
                "catch-up peer miss for %s (%s); warming dialogs and retrying",
                source_chat_id,
                exc,
            )
            self._warm_dialogs([chat_id])
            return self._read_history(chat_id)

    def _read_history(self, chat_id) -> List[Any]:
        messages: List[Any] = []
        history = self._acc.get_chat_history(chat_id, limit=self._lookback)
        for message in history:
            if message is None or getattr(message, "empty", False):
                continue
            if getattr(message, "id", None) is None:
                continue
            if getattr(message, "service", None):
                # Skip pure service messages (joins, title changes, etc.)
                continue
            messages.append(message)
        return messages

    def _warm_dialogs(self, chat_ids: Sequence[Any]) -> None:
        wanted = {self._coerce_chat_id(cid) for cid in chat_ids}
        found = set()
        try:
            for dialog in self._acc.get_dialogs(limit=80):
                chat = getattr(dialog, "chat", None)
                if chat is None:
                    continue
                cid = getattr(chat, "id", None)
                if cid in wanted:
                    found.add(cid)
                if found >= wanted:
                    break
        except Exception as exc:
            logger.debug("catch-up dialog warm failed: %s", exc)

    @staticmethod
    def _is_peer_error(exc: BaseException) -> bool:
        text = str(exc)
        return (
            "Peer id invalid" in text
            or "ID not found" in text
            or "PEER_ID_INVALID" in text
        )

    @staticmethod
    def _select_candidates(history: Sequence[Any], last_seen_id: int) -> List[Any]:
        newer = [msg for msg in history if int(msg.id) > int(last_seen_id)]
        newer.sort(key=lambda msg: int(msg.id))
        return newer

    @staticmethod
    def _coerce_chat_id(source_chat_id: str):
        if source_chat_id == "me":
            return "me"
        try:
            return int(source_chat_id)
        except (TypeError, ValueError):
            return source_chat_id
