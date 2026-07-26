"""
Composition-root wiring tests.

容器把「实现提供者」以晚绑定方式交给服务：先构建服务、后注册实现也必须生效。
"""

from __future__ import annotations

from typing import Iterator

import pytest

from composition.container import get_container


@pytest.fixture
def container() -> Iterator[object]:
    """Yield the singleton container, restoring its wiring afterwards."""
    instance = get_container()
    original_calibration = instance._calibration_scheduler_provider
    original_media = instance._media_storage_provider
    instance.reset()
    try:
        yield instance
    finally:
        instance._calibration_scheduler_provider = original_calibration
        instance._media_storage_provider = original_media
        instance.reset()


class _FakeScheduler:
    def is_enabled(self) -> bool:
        return True

    def should_calibrate_note(self, note: dict) -> bool:
        return True

    def add_note_to_calibration_queue(self, note_id: int, force: bool = False) -> bool:
        return True


class _FakeMediaStorage:
    def delete_file(self, storage_location: str) -> bool:
        return True


def test_resolvers_return_none_when_not_wired(container) -> None:
    container._calibration_scheduler_provider = None
    container._media_storage_provider = None

    assert container._resolve_calibration_scheduler() is None
    assert container._resolve_media_storage() is None


def test_wiring_after_service_construction_still_applies(container) -> None:
    container._calibration_scheduler_provider = None
    container._media_storage_provider = None

    note_service = container.note_service  # built before wiring
    scheduler = _FakeScheduler()
    storage = _FakeMediaStorage()
    container.set_calibration_scheduler_provider(lambda: scheduler)
    container.set_media_storage_provider(lambda: storage)

    assert note_service._calibration_scheduler_provider() is scheduler
    assert note_service._media_storage_provider() is storage


def test_workflow_service_receives_scheduler_provider(container) -> None:
    scheduler = _FakeScheduler()
    container.set_calibration_scheduler_provider(lambda: scheduler)

    workflow = container.calibration_workflow_service

    assert workflow._calibration_scheduler_provider() is scheduler


def test_configure_runtime_implementations_registers_providers(container) -> None:
    from composition.wiring import configure_runtime_implementations

    container._calibration_scheduler_provider = None
    container._media_storage_provider = None

    configure_runtime_implementations(container)

    assert container._calibration_scheduler_provider is not None
    assert container._media_storage_provider is not None


# ---------------------------------------------------------------------------
# 基础设施侧端口（缓存 / 可观测性）的装配
#
# 与上面几条的区别：校准与媒体存储的实现在 `bot/`，只能在启动期由
# `composition/wiring.py` 注册；缓存与监控的实现就在 `src.infrastructure`，
# 容器本来就允许直接 import，所以在构造服务时一次性传入。
# 忘了传的后果是服务静默降级成 NullCache（生产表现为缓存全失效），
# 因此这三条把「provider 确实传进去了」钉死。
# ---------------------------------------------------------------------------


def test_note_service_receives_cache_provider(container) -> None:
    from composition.container import _note_cache_provider

    assert container.note_service._cache_provider is _note_cache_provider


def test_watch_service_receives_cache_provider(container) -> None:
    from composition.container import _config_cache_provider

    assert container.watch_service._cache_provider is _config_cache_provider


def test_message_worker_service_receives_observability_providers(container) -> None:
    service = container.message_worker_service

    assert service._metrics_provider is not None
    assert service._error_tracker_provider is not None
