"""Default executor for history-copy task manager."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from src.core.config import settings

from .history_copy import (
    HistoryCopyRunner,
    HistoryCopyStateStore,
    resolve_history_copy_settings,
)
from .history_copy_models import HistoryCopySettings, HistoryCopyStats
from .history_copy_task_models import HistoryCopyTaskConfig

ExecutionResult = tuple[HistoryCopySettings, object]
ProgressCallback = Callable[[HistoryCopyStats], None]
TaskExecutor = Callable[[Any, HistoryCopyTaskConfig, ProgressCallback | None], ExecutionResult]
Clock = Callable[[], float]


def default_history_copy_task_executor(
    client: Any,
    task: HistoryCopyTaskConfig,
    progress_callback: ProgressCallback | None = None,
    *,
    user_id: str | None = None,
) -> ExecutionResult:
    from bot.handlers.instances import get_bot_instance

    bot_client = get_bot_instance()
    staging_chat_id = str(user_id or settings.get("OWNER_ID", "") or "").strip() or None
    staging_source_ref = _resolve_bot_source_ref(bot_client) if staging_chat_id else None
    settings_obj = resolve_history_copy_settings(
        client,
        task.source_chat_ref,
        task.dest_chat_ref,
        state_db_path=Path(task.state_db_path),
        history_limit=task.history_limit,
    )
    with HistoryCopyStateStore(settings_obj.state_db_path) as state_store:
        stats = HistoryCopyRunner(
            client,
            settings_obj,
            state_store,
            progress_callback=progress_callback,
            bot_client=bot_client,
            bot_staging_chat_id=staging_chat_id,
            bot_staging_source_ref=staging_source_ref,
        ).run()
    return settings_obj, stats


def _resolve_bot_source_ref(bot_client: Any | None) -> str | None:
    if bot_client is None:
        return None
    bot_user = bot_client.get_me()
    username = str(getattr(bot_user, "username", "") or "").strip()
    if username:
        return username if username.startswith("@") else f"@{username}"
    bot_id = str(getattr(bot_user, "id", "") or "").strip()
    return bot_id or None
