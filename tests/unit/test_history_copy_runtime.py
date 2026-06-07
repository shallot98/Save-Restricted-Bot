from __future__ import annotations

from dataclasses import dataclass

from bot.services.history_copy_models import HistoryCopyFatalError, HistoryCopySettings
from bot.services.history_copy_risk import HistoryCopyRiskConfig, HistoryCopyRiskController
from bot.services.history_copy_runtime import HistoryCopyRunner
from bot.services.history_copy_storage import HistoryCopyStateStore


@dataclass
class _DummyChat:
    id: int


@dataclass
class _DummyMessage:
    id: int
    chat: _DummyChat
    media_group_id: str | None = None
    text: str | None = None
    entities: list | None = None
    caption: str | None = None
    caption_entities: list | None = None


@dataclass
class _DummyCopiedMessage:
    id: int
    chat: _DummyChat | None = None


@dataclass
class _DummyBotUser:
    id: int = 12345
    username: str = "copy_bot"


class _FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class _DummyClient:
    def __init__(
        self,
        messages: list[_DummyMessage],
        failures: dict[tuple[str, int], Exception] | None = None,
        copy_return_chat_ids: dict[int, int] | None = None,
    ) -> None:
        self._messages = sorted(messages, key=lambda item: item.id, reverse=True)
        for message in self._messages:
            if message.text is None:
                message.text = f"message-{message.id}"
        self._messages_by_id = {message.id: message for message in self._messages}
        self._media_groups = self._build_media_groups(self._messages)
        self._source_chat = _DummyChat(id=-100123)
        self._dest_chat = _DummyChat(id=-100999)
        self._failures = failures or {}
        self._copy_return_chat_ids = copy_return_chat_ids or {}
        self.copy_calls: list[int] = []
        self.copy_group_calls: list[int] = []
        self.copy_call_args: list[tuple[int, object, int]] = []
        self.copy_group_call_args: list[tuple[int, object, int]] = []
        self.send_calls: list[int] = []
        self.get_message_calls: list[int] = []
        self.deleted_messages: list[tuple[object, list[int]]] = []
        self._bot_dialog_messages: list[_DummyMessage] = []
        self._last_loaded_message_id: int | None = None

    @staticmethod
    def _build_media_groups(messages: list[_DummyMessage]) -> dict[str, list[_DummyMessage]]:
        groups: dict[str, list[_DummyMessage]] = {}
        for message in messages:
            if not message.media_group_id:
                continue
            groups.setdefault(message.media_group_id, []).append(message)
        for items in groups.values():
            items.sort(key=lambda item: item.id)
        return groups

    def get_chat(self, chat_ref):
        if chat_ref in {"source", "@public_source", self._source_chat.id, str(self._source_chat.id)}:
            return self._source_chat
        if chat_ref in {"dest", self._dest_chat.id, str(self._dest_chat.id)}:
            return self._dest_chat
        raise ValueError(f"unknown chat ref: {chat_ref}")

    def get_chat_history(self, _chat_id, limit: int, offset_id: int = 0):
        if _chat_id in {"@copy_bot", 12345, "12345"}:
            return sorted(self._bot_dialog_messages, key=lambda item: item.id, reverse=True)[:limit]
        messages = self._messages
        if offset_id:
            messages = [message for message in messages if message.id < offset_id]
        return messages[:limit]

    def get_media_group(self, _chat_id, message_id: int):
        message = self._messages_by_id[message_id]
        if not message.media_group_id:
            return [message]
        return list(self._media_groups[message.media_group_id])

    def get_messages(self, _chat_id, message_id: int):
        self.get_message_calls.append(message_id)
        self._last_loaded_message_id = message_id
        return self._messages_by_id[message_id]

    def send_message(self, _dest_chat_id, _text: str, entities=None):
        message_id = self._last_loaded_message_id or 0
        self.send_calls.append(message_id)
        failure = self._failures.get(("send_message", message_id))
        if failure is not None:
            raise failure
        return _DummyCopiedMessage(message_id)

    def copy_message(self, _dest_chat_id, _source_chat_id, message_id: int):
        self.copy_calls.append(message_id)
        self.copy_call_args.append((_dest_chat_id, _source_chat_id, message_id))
        failure = self._failures.get(("copy_message", message_id))
        if failure is not None:
            raise failure
        chat_id = self._copy_return_chat_ids.get(message_id, int(_dest_chat_id))
        return _DummyCopiedMessage(message_id, _DummyChat(chat_id))

    def copy_media_group(self, _dest_chat_id, _source_chat_id, message_id: int):
        self.copy_group_calls.append(message_id)
        self.copy_group_call_args.append((_dest_chat_id, _source_chat_id, message_id))
        failure = self._failures.get(("copy_media_group", message_id))
        if failure is not None:
            raise failure
        chat_id = self._copy_return_chat_ids.get(message_id, int(_dest_chat_id))
        return [_DummyCopiedMessage(message.id, _DummyChat(chat_id)) for message in self.get_media_group(0, message_id)]

    def add_bot_dialog_message(self, message_id: int, media_group_id: str | None = None) -> None:
        self._bot_dialog_messages.append(_DummyMessage(message_id, _DummyChat(12345), media_group_id))

    def delete_messages(self, chat_id, message_ids: list[int]) -> None:
        self.deleted_messages.append((chat_id, message_ids))
        delete_ids = set(message_ids)
        self._bot_dialog_messages = [
            message for message in self._bot_dialog_messages if message.id not in delete_ids
        ]


class _DummyBotClient:
    def __init__(
        self,
        failures: dict[tuple[str, int], Exception] | None = None,
        fail_dest_ids: set[int] | None = None,
        user_client: _DummyClient | None = None,
    ) -> None:
        self._failures = failures or {}
        self._fail_dest_ids = fail_dest_ids or set()
        self._user_client = user_client
        self.copy_calls: list[tuple[int, str, int]] = []
        self.copy_group_calls: list[tuple[int, str, int]] = []
        self.deleted_messages: list[tuple[int, list[int]]] = []

    def get_me(self) -> _DummyBotUser:
        return _DummyBotUser()

    def copy_message(self, dest_chat_id: int, source_chat_ref: str, message_id: int):
        self.copy_calls.append((dest_chat_id, source_chat_ref, message_id))
        if dest_chat_id in self._fail_dest_ids:
            raise ValueError(f"Peer id invalid: {dest_chat_id}")
        failure = self._failures.get(("copy_message", message_id))
        if failure is not None:
            raise failure
        if self._user_client is not None:
            self._user_client.add_bot_dialog_message(message_id + 2000)
        return _DummyCopiedMessage(message_id + 1000, _DummyChat(dest_chat_id))

    def copy_media_group(self, dest_chat_id: int, source_chat_ref: str, message_id: int):
        self.copy_group_calls.append((dest_chat_id, source_chat_ref, message_id))
        if dest_chat_id in self._fail_dest_ids:
            raise ValueError(f"Peer id invalid: {dest_chat_id}")
        failure = self._failures.get(("copy_media_group", message_id))
        if failure is not None:
            raise failure
        if self._user_client is not None:
            self._user_client.add_bot_dialog_message(message_id + 2000, "staged-group")
        return [_DummyCopiedMessage(message_id + 1000, _DummyChat(dest_chat_id))]

    def delete_messages(self, chat_id: int, message_ids: list[int]) -> None:
        self.deleted_messages.append((chat_id, message_ids))


def _make_settings(
    tmp_path,
    *,
    history_limit: int | None = None,
    source_chat_ref: str = "source",
) -> HistoryCopySettings:
    return HistoryCopySettings(
        source_chat_ref=source_chat_ref,
        dest_chat_ref="dest",
        source_chat_id="-100123",
        dest_chat_id="-100999",
        state_db_path=tmp_path / "history_copy_state.db",
        batch_size=2,
        history_limit=history_limit,
        max_flood_retries=1,
        rate_limit_delay=0.0,
    )


def test_state_store_marks_and_checks_messages(tmp_path) -> None:
    store = HistoryCopyStateStore(tmp_path / "copy_state.db")
    assert not store.is_copied("src", "dest", 1)
    store.mark_copied("src", "dest", 1)
    assert store.is_copied("src", "dest", 1)
    store.close()


def test_runner_copies_media_group_once_and_marks_all(tmp_path) -> None:
    source_chat = _DummyChat(id=-100123)
    client = _DummyClient(
        [
            _DummyMessage(id=4, chat=source_chat, media_group_id="grp-1"),
            _DummyMessage(id=3, chat=source_chat, media_group_id="grp-1"),
            _DummyMessage(id=2, chat=source_chat),
        ]
    )

    with HistoryCopyStateStore(tmp_path / "state.db") as store:
        stats = HistoryCopyRunner(client, _make_settings(tmp_path), store).run()
        assert store.is_copied("-100123", "-100999", 4)
        assert store.is_copied("-100123", "-100999", 3)
        assert store.is_copied("-100123", "-100999", 2)

    assert client.copy_group_calls == [3]
    assert client.copy_calls == [2]
    assert stats.copied_count == 3
    assert stats.skipped_count == 1


def test_runner_falls_back_to_individual_copy_for_partial_media_group_resume(tmp_path) -> None:
    source_chat = _DummyChat(id=-100123)
    client = _DummyClient(
        [
            _DummyMessage(id=4, chat=source_chat, media_group_id="grp-1"),
            _DummyMessage(id=3, chat=source_chat, media_group_id="grp-1"),
            _DummyMessage(id=2, chat=source_chat),
        ]
    )

    with HistoryCopyStateStore(tmp_path / "state.db") as store:
        store.mark_copied("-100123", "-100999", 3)
        stats = HistoryCopyRunner(client, _make_settings(tmp_path), store).run()

    assert client.copy_group_calls == []
    assert client.copy_calls == [2, 4]
    assert stats.copied_count == 2
    assert stats.skipped_count == 2


def test_runner_continues_after_nonfatal_message_failure(tmp_path) -> None:
    source_chat = _DummyChat(id=-100123)
    client = _DummyClient(
        [
            _DummyMessage(id=3, chat=source_chat),
            _DummyMessage(id=2, chat=source_chat),
            _DummyMessage(id=1, chat=source_chat),
        ],
        failures={("copy_message", 2): RuntimeError("boom")},
    )

    with HistoryCopyStateStore(tmp_path / "state.db") as store:
        stats = HistoryCopyRunner(client, _make_settings(tmp_path), store).run()

    assert client.copy_calls == [1, 2, 3]
    assert stats.copied_count == 2
    assert stats.failed_count == 1
    assert stats.failed_message_ids == [2]


def test_runner_uses_bot_copy_for_public_source_before_user_copy(tmp_path) -> None:
    source_chat = _DummyChat(id=-100123)
    client = _DummyClient([_DummyMessage(id=3, chat=source_chat)])
    bot_client = _DummyBotClient()

    with HistoryCopyStateStore(tmp_path / "state.db") as store:
        stats = HistoryCopyRunner(
            client,
            _make_settings(tmp_path, source_chat_ref="@public_source"),
            store,
            bot_client=bot_client,
        ).run()

    assert bot_client.copy_calls == [(-100999, "@public_source", 3)]
    assert client.copy_calls == []
    assert stats.copied_count == 1


def test_runner_falls_back_to_user_copy_when_bot_copy_fails(tmp_path) -> None:
    source_chat = _DummyChat(id=-100123)
    client = _DummyClient([_DummyMessage(id=3, chat=source_chat)])
    bot_client = _DummyBotClient(failures={("copy_message", 3): RuntimeError("bot denied")})

    with HistoryCopyStateStore(tmp_path / "state.db") as store:
        stats = HistoryCopyRunner(
            client,
            _make_settings(tmp_path, source_chat_ref="@public_source"),
            store,
            bot_client=bot_client,
        ).run()

    assert bot_client.copy_calls == [(-100999, "@public_source", 3)]
    assert client.copy_calls == [3]
    assert stats.copied_count == 1


def test_runner_uses_bot_staging_when_bot_cannot_write_destination(tmp_path) -> None:
    source_chat = _DummyChat(id=-100123)
    client = _DummyClient([_DummyMessage(id=3, chat=source_chat)])
    bot_client = _DummyBotClient(fail_dest_ids={-100999}, user_client=client)

    with HistoryCopyStateStore(tmp_path / "state.db") as store:
        stats = HistoryCopyRunner(
            client,
            _make_settings(tmp_path, source_chat_ref="@public_source"),
            store,
            bot_client=bot_client,
            bot_staging_chat_id="907446443",
            bot_staging_source_ref="@copy_bot",
        ).run()

    assert bot_client.copy_calls == [
        (-100999, "@public_source", 3),
        (907446443, "@public_source", 3),
    ]
    assert client.copy_call_args == [(-100999, "@copy_bot", 2003)]
    assert client.deleted_messages == [("@copy_bot", [2003])]
    assert stats.copied_count == 1


def test_runner_rejects_bot_staging_copy_to_wrong_destination(tmp_path) -> None:
    source_chat = _DummyChat(id=-100123)
    client = _DummyClient(
        [_DummyMessage(id=3, chat=source_chat)],
        failures={("copy_message", 3): RuntimeError("user copy denied")},
        copy_return_chat_ids={2003: 907446443},
    )
    bot_client = _DummyBotClient(fail_dest_ids={-100999}, user_client=client)

    with HistoryCopyStateStore(tmp_path / "state.db") as store:
        stats = HistoryCopyRunner(
            client,
            _make_settings(tmp_path, source_chat_ref="@public_source"),
            store,
            bot_client=bot_client,
            bot_staging_chat_id="907446443",
            bot_staging_source_ref="@copy_bot",
        ).run()

        assert not store.is_copied("-100123", "-100999", 3)

    assert client.copy_call_args == [
        (-100999, "@copy_bot", 2003),
        (-100999, -100123, 3),
    ]
    assert client.deleted_messages == [("@copy_bot", [2003])]
    assert stats.copied_count == 0
    assert stats.failed_count == 1


def test_runner_uses_bot_copy_for_public_media_group(tmp_path) -> None:
    source_chat = _DummyChat(id=-100123)
    client = _DummyClient(
        [
            _DummyMessage(id=4, chat=source_chat, media_group_id="grp-1"),
            _DummyMessage(id=3, chat=source_chat, media_group_id="grp-1"),
        ]
    )
    bot_client = _DummyBotClient()

    with HistoryCopyStateStore(tmp_path / "state.db") as store:
        stats = HistoryCopyRunner(
            client,
            _make_settings(tmp_path, source_chat_ref="@public_source"),
            store,
            bot_client=bot_client,
        ).run()

    assert bot_client.copy_group_calls == [(-100999, "@public_source", 3)]
    assert client.copy_group_calls == []
    assert stats.copied_count == 2


def test_runner_raises_on_fatal_copy_error(tmp_path) -> None:
    source_chat = _DummyChat(id=-100123)
    fatal_error_type = type("ChatWriteForbidden", (Exception,), {})
    client = _DummyClient(
        [_DummyMessage(id=3, chat=source_chat)],
        failures={("copy_message", 3): fatal_error_type("no write access")},
    )

    with HistoryCopyStateStore(tmp_path / "state.db") as store:
        try:
            HistoryCopyRunner(client, _make_settings(tmp_path), store).run()
        except HistoryCopyFatalError:
            return
        raise AssertionError("fatal error did not abort run")


def test_runner_falls_back_to_resend_for_protected_message(tmp_path) -> None:
    source_chat = _DummyChat(id=-100123)
    fatal_error_type = type("ChatForwardsRestricted", (Exception,), {})
    client = _DummyClient(
        [_DummyMessage(id=3, chat=source_chat)],
        failures={("copy_message", 3): fatal_error_type("protected content")},
    )

    with HistoryCopyStateStore(tmp_path / "state.db") as store:
        stats = HistoryCopyRunner(client, _make_settings(tmp_path), store).run()

    assert client.copy_calls == [3]
    assert client.get_message_calls == [3]
    assert client.send_calls == [3]
    assert stats.copied_count == 1
    assert stats.failed_count == 0


def test_runner_does_not_trigger_cooldown_for_protected_fallback(tmp_path) -> None:
    source_chat = _DummyChat(id=-100123)
    clock = _FakeClock()
    risk_controller = HistoryCopyRiskController(
        HistoryCopyRiskConfig(
            min_send_interval_seconds=0.0,
            hourly_send_budget=10,
            budget_window_seconds=3600,
            failure_threshold=1,
            failure_cooldown_seconds=300.0,
            floodwait_buffer_seconds=1.0,
        ),
        time_func=clock.time,
        sleep_func=clock.sleep,
    )
    fatal_error_type = type("ChatForwardsRestricted", (Exception,), {})
    client = _DummyClient(
        [_DummyMessage(id=3, chat=source_chat)],
        failures={("copy_message", 3): fatal_error_type("protected content")},
    )

    with HistoryCopyStateStore(tmp_path / "state.db") as store:
        stats = HistoryCopyRunner(
            client,
            _make_settings(tmp_path),
            store,
            risk_controller=risk_controller,
        ).run()

    assert stats.copied_count == 1
    assert clock.sleeps == []


def test_runner_uses_risk_controller_for_min_interval(tmp_path) -> None:
    source_chat = _DummyChat(id=-100123)
    clock = _FakeClock()
    risk_controller = HistoryCopyRiskController(
        HistoryCopyRiskConfig(
            min_send_interval_seconds=2.0,
            hourly_send_budget=10,
            budget_window_seconds=3600,
            failure_threshold=3,
            failure_cooldown_seconds=30.0,
            floodwait_buffer_seconds=1.0,
        ),
        time_func=clock.time,
        sleep_func=clock.sleep,
    )
    client = _DummyClient(
        [
            _DummyMessage(id=2, chat=source_chat),
            _DummyMessage(id=1, chat=source_chat),
        ]
    )

    with HistoryCopyStateStore(tmp_path / "state.db") as store:
        stats = HistoryCopyRunner(
            client,
            _make_settings(tmp_path),
            store,
            risk_controller=risk_controller,
        ).run()

    assert stats.copied_count == 2
    assert client.copy_calls == [1, 2]
    assert clock.sleeps == [2.0]


def test_runner_preserves_oldest_first_order_for_recent_history_limit(tmp_path) -> None:
    source_chat = _DummyChat(id=-100123)
    client = _DummyClient(
        [
            _DummyMessage(id=4, chat=source_chat),
            _DummyMessage(id=3, chat=source_chat),
            _DummyMessage(id=2, chat=source_chat),
            _DummyMessage(id=1, chat=source_chat),
        ]
    )

    with HistoryCopyStateStore(tmp_path / "state.db") as store:
        stats = HistoryCopyRunner(
            client,
            _make_settings(tmp_path, history_limit=3),
            store,
        ).run()

    assert stats.copied_count == 3
    assert client.copy_calls == [2, 3, 4]


def test_runner_reports_progress_during_processing(tmp_path) -> None:
    source_chat = _DummyChat(id=-100123)
    progress: list[str] = []
    client = _DummyClient(
        [
            _DummyMessage(id=3, chat=source_chat),
            _DummyMessage(id=2, chat=source_chat),
            _DummyMessage(id=1, chat=source_chat),
        ],
        failures={("copy_message", 2): RuntimeError("boom")},
    )

    with HistoryCopyStateStore(tmp_path / "state.db") as store:
        HistoryCopyRunner(
            client,
            _make_settings(tmp_path),
            store,
            progress_callback=lambda stats: progress.append(stats.summary()),
        ).run()

    assert progress == [
        "scanned=1 copied=1 skipped=0 failed=0",
        "scanned=2 copied=1 skipped=0 failed=1",
        "scanned=3 copied=2 skipped=0 failed=1",
    ]
