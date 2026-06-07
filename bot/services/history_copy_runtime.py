"""Runtime orchestration for copying Telegram chat history."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from bot.utils.logger import get_logger
from .history_copy_media_group import HistoryCopyMediaGroupMixin
from .history_copy_models import HistoryCopyFatalError, HistoryCopySettings, HistoryCopyStats
from .history_copy_queue import HistoryCopyMessageQueue
from .history_copy_resend import HistoryCopyMessageResender
from .history_copy_retry import HistoryCopyRetryMixin
from .history_copy_risk import HistoryCopyRiskController
from .history_copy_single import HistoryCopySingleMixin
from .history_copy_staging import HistoryCopyStagingMixin
from .history_copy_storage import HistoryCopyStateStore
from .history_copy_utils import coerce_chat_ref, message_id

logger = get_logger(__name__)

_UNSET = object()
_OPTION_NAMES = (
    "risk_controller",
    "progress_callback",
    "bot_client",
    "bot_staging_chat_id",
    "bot_staging_source_ref",
)


@dataclass(frozen=True)
class HistoryCopyRunnerOptions:
    risk_controller: HistoryCopyRiskController | None = None
    progress_callback: Callable[[HistoryCopyStats], None] | None = None
    bot_client: Any | None = None
    bot_staging_chat_id: str | None = None
    bot_staging_source_ref: str | None = None


class HistoryCopyRunner(
    HistoryCopyMediaGroupMixin,
    HistoryCopySingleMixin,
    HistoryCopyStagingMixin,
    HistoryCopyRetryMixin,
):
    """Copy message history from one chat to another."""

    def __init__(
        self,
        client: Any,
        settings: HistoryCopySettings,
        state_store: HistoryCopyStateStore,
        *runner_options,
        options: HistoryCopyRunnerOptions | None = None,
        **legacy_options,
    ) -> None:
        options = _resolve_runner_options(
            runner_options,
            options,
            legacy_options,
        )
        self._client = client
        self._bot_client = options.bot_client
        self._bot_staging_chat_id = options.bot_staging_chat_id
        self._bot_staging_source_ref = options.bot_staging_source_ref
        self._settings = settings
        self._state_store = state_store
        self._risk_controller = options.risk_controller or HistoryCopyRiskController.from_settings(settings)
        self._handled_media_groups: set[str] = set()
        self._progress_callback = options.progress_callback
        self._resender = HistoryCopyMessageResender(
            client,
            settings.source_chat_id,
            settings.dest_chat_id,
            lambda operation_name, operation: self._execute_with_retry(operation_name, operation),
            lambda operation_name, operation: self._execute_with_retry(
                operation_name,
                operation,
                is_outbound=True,
            ),
        )

    def run(self) -> HistoryCopyStats:
        self._verify_chat_access()
        stats = HistoryCopyStats()
        self._log_start()
        try:
            with HistoryCopyMessageQueue(self._settings.state_db_path) as message_queue:
                self._queue_history_messages(message_queue)
                for message in message_queue.iter_oldest_first():
                    self._process_message(message, stats)
        except HistoryCopyFatalError:
            raise
        except Exception as exc:
            raise HistoryCopyFatalError(
                f"历史遍历过程中发生致命错误: {type(exc).__name__}: {exc}"
            ) from exc

        self._log_finished(stats)
        return stats

    def _log_start(self) -> None:
        logger.info(
            "📚 开始历史复制: source=%s dest=%s batch_size=%s limit=%s state_db=%s",
            self._settings.source_chat_id,
            self._settings.dest_chat_id,
            self._settings.batch_size,
            self._settings.history_limit or "ALL",
            self._settings.state_db_path,
        )

    def _log_finished(self, stats: HistoryCopyStats) -> None:
        logger.info("✅ 历史复制完成: %s", stats.summary())
        logger.info("🛡️ 风控摘要: %s", self._risk_controller.summary())
        if stats.failed_message_ids:
            logger.warning("⚠️ 失败消息样本: %s", ",".join(map(str, stats.failed_message_ids)))

    def _verify_chat_access(self) -> None:
        try:
            self._client.get_chat(coerce_chat_ref(self._settings.source_chat_ref))
            self._client.get_chat(coerce_chat_ref(self._settings.dest_chat_ref))
        except Exception as exc:
            raise HistoryCopyFatalError(
                f"无法访问源或目标 chat: {type(exc).__name__}: {exc}"
            ) from exc

    def _queue_history_messages(self, message_queue: HistoryCopyMessageQueue) -> None:
        offset_id = 0
        queued_count = 0
        while True:
            request_limit = self._get_request_limit(queued_count)
            if request_limit <= 0:
                return
            batch = self._read_history_batch(request_limit, offset_id)
            if not batch:
                return
            offset_id = min(message_id(item) for item in batch)
            queued_count += len(batch)
            message_queue.add_batch(batch)

    def _read_history_batch(self, request_limit: int, offset_id: int) -> list[Any]:
        return self._execute_with_retry(
            "读取历史",
            lambda: list(
                self._client.get_chat_history(
                    int(self._settings.source_chat_id),
                    limit=request_limit,
                    offset_id=offset_id,
                )
            ),
        )

    def _get_request_limit(self, yielded: int) -> int:
        if self._settings.history_limit is None:
            return self._settings.batch_size
        remaining = self._settings.history_limit - yielded
        if remaining <= 0:
            return 0
        return min(self._settings.batch_size, remaining)

    def _process_message(self, message: Any, stats: HistoryCopyStats) -> None:
        current_message_id = message_id(message)
        if current_message_id <= 0:
            return
        stats.scanned_count += 1
        try:
            self._copy_or_skip_message(message, current_message_id, stats)
        finally:
            self._report_progress(stats)

    def _copy_or_skip_message(self, message: Any, current_message_id: int, stats: HistoryCopyStats) -> None:
        if self._is_message_copied(current_message_id):
            stats.skipped_count += 1
            return

        media_group_id = str(getattr(message, "media_group_id", "") or "")
        if not media_group_id:
            self._copy_single_entry(message, stats)
            return
        if media_group_id in self._handled_media_groups:
            stats.skipped_count += 1
            return
        self._handled_media_groups.add(media_group_id)
        self._copy_media_group_entry(message, stats)


def _resolve_runner_options(
    runner_options: tuple,
    options: HistoryCopyRunnerOptions | None,
    legacy_options: dict,
) -> HistoryCopyRunnerOptions:
    if options is not None:
        if runner_options or legacy_options:
            raise TypeError("HistoryCopyRunner received both options and legacy arguments")
        return options
    if len(runner_options) > len(_OPTION_NAMES):
        raise TypeError(f"HistoryCopyRunner expected at most {len(_OPTION_NAMES)} optional arguments")

    resolved = {name: None for name in _OPTION_NAMES}
    for name, value in zip(_OPTION_NAMES, runner_options):
        if name in legacy_options:
            raise TypeError(f"HistoryCopyRunner got multiple values for argument '{name}'")
        resolved[name] = value

    for name in _OPTION_NAMES:
        if name in legacy_options:
            resolved[name] = legacy_options.pop(name)
    if legacy_options:
        unknown = ", ".join(sorted(legacy_options))
        raise TypeError(f"HistoryCopyRunner got unexpected keyword argument(s): {unknown}")

    return HistoryCopyRunnerOptions(**resolved)
