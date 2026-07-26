"""
Narrow-port injection tests for the calibration scheduler.

覆盖报告 §3 P1-1 / 路线图 #19：`src.application` 不再 import `bot.services.
calibration_manager`，而是通过 `src.core.interfaces.CalibrationScheduler`
端口 + 组合根注入的 provider 取得实现。
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import pytest

from src.application.services.calibration_workflow_service import (
    CalibrationWorkflowService,
)
from src.application.services.note_service import NoteService
from src.core.exceptions import ConfigurationError
from src.core.interfaces import CalibrationScheduler
from src.domain.entities.note import Note, NoteCreate

MAGNET_TEXT = "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567&dn=demo"


@dataclass
class FakeCalibrationScheduler:
    """Minimal stand-in satisfying the CalibrationScheduler port."""

    enabled: bool = True
    calibrate_decision: bool = True
    queue_result: bool = True
    queued: List[tuple] = field(default_factory=list)
    filtered: List[Dict[str, Any]] = field(default_factory=list)
    queued_event: threading.Event = field(default_factory=threading.Event)

    def is_enabled(self) -> bool:
        return self.enabled

    def should_calibrate_note(self, note: Dict[str, Any]) -> bool:
        self.filtered.append(note)
        return self.calibrate_decision

    def add_note_to_calibration_queue(self, note_id: int, force: bool = False) -> bool:
        self.queued.append((note_id, force))
        self.queued_event.set()
        return self.queue_result


class FakeNoteRepository:
    def __init__(self, created: Note) -> None:
        self.created = created

    def check_duplicate(self, **_kwargs: Any) -> bool:
        return False

    def create(self, _note_data: NoteCreate) -> Note:
        return self.created


def _make_note(note_id: int = 7, text: str = MAGNET_TEXT) -> Note:
    return Note(
        id=note_id,
        user_id=1,
        source_chat_id="source-1",
        source_name="Source 1",
        message_text=text,
        timestamp=datetime.now(),
    )


def _make_note_create(text: str = MAGNET_TEXT) -> NoteCreate:
    return NoteCreate(
        user_id=1,
        source_chat_id="source-1",
        source_name="Source 1",
        message_text=text,
    )


def _build_note_service(
    note: Note,
    scheduler: Optional[FakeCalibrationScheduler],
) -> NoteService:
    service = NoteService(
        FakeNoteRepository(note),  # type: ignore[arg-type]
        calibration_scheduler_provider=lambda: scheduler,
    )
    service._invalidate_note_caches = lambda *_args, **_kwargs: None  # type: ignore[method-assign]
    return service


class TestNoteServiceCalibrationInjection:
    def test_fake_scheduler_satisfies_port(self) -> None:
        assert isinstance(FakeCalibrationScheduler(), CalibrationScheduler)

    def test_magnet_note_is_queued_through_injected_scheduler(self) -> None:
        scheduler = FakeCalibrationScheduler()
        service = _build_note_service(_make_note(), scheduler)

        service.create_note(_make_note_create())

        assert scheduler.queued_event.wait(timeout=2.0), "calibration was never scheduled"
        assert scheduler.queued == [(7, False)]

    def test_plain_note_is_not_queued(self) -> None:
        scheduler = FakeCalibrationScheduler()
        service = _build_note_service(_make_note(text="no magnet here"), scheduler)

        service.create_note(_make_note_create(text="no magnet here"))

        assert scheduler.queued == []

    def test_disabled_scheduler_is_not_queued(self) -> None:
        scheduler = FakeCalibrationScheduler(enabled=False)
        service = _build_note_service(_make_note(), scheduler)

        service.create_note(_make_note_create())

        assert scheduler.queued == []

    def test_unwired_provider_warns_and_skips(self, caplog: pytest.LogCaptureFixture) -> None:
        service = _build_note_service(_make_note(), None)

        with caplog.at_level("WARNING"):
            service.create_note(_make_note_create())

        assert "Calibration scheduler unavailable" in caplog.text


class FakePaginatedNotes:
    def __init__(self, items: List[Any]) -> None:
        self.items = items


class FakeNoteServiceForBatch:
    def __init__(self, items: List[Any]) -> None:
        self.items = items

    def get_notes(self, page: int, page_size: int) -> FakePaginatedNotes:
        return FakePaginatedNotes(self.items[:page_size])


@dataclass
class FakeNoteRow:
    id: int
    message_text: str = MAGNET_TEXT


class TestCalibrationWorkflowSchedulerInjection:
    def test_batch_schedule_uses_injected_scheduler(self) -> None:
        scheduler = FakeCalibrationScheduler()
        workflow = CalibrationWorkflowService(
            FakeNoteServiceForBatch([FakeNoteRow(1), FakeNoteRow(2)]),  # type: ignore[arg-type]
            None,  # type: ignore[arg-type]
            lambda: scheduler,
        )

        payload = workflow.batch_schedule_recent_notes(count=10, force=False)

        assert payload["added"] == 2
        assert payload["skipped"] == 0
        assert scheduler.queued == [(1, False), (2, False)]
        assert len(scheduler.filtered) == 2

    def test_batch_schedule_force_skips_filter(self) -> None:
        scheduler = FakeCalibrationScheduler(calibrate_decision=False)
        workflow = CalibrationWorkflowService(
            FakeNoteServiceForBatch([FakeNoteRow(3)]),  # type: ignore[arg-type]
            None,  # type: ignore[arg-type]
            lambda: scheduler,
        )

        payload = workflow.batch_schedule_recent_notes(count=10, force=True)

        assert payload["added"] == 1
        assert scheduler.filtered == []
        assert scheduler.queued == [(3, True)]

    def test_batch_schedule_without_wiring_raises(self) -> None:
        workflow = CalibrationWorkflowService(
            FakeNoteServiceForBatch([FakeNoteRow(1)]),  # type: ignore[arg-type]
            None,  # type: ignore[arg-type]
            None,
        )

        with pytest.raises(ConfigurationError):
            workflow.batch_schedule_recent_notes(count=10, force=False)
