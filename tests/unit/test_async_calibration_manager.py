import threading
import time

from bot.services.async_calibration_manager import AsyncCalibrationManager, TaskStatus


class FakeClock:
    def __init__(self, start: float = 0.0):
        self._now = start
        self._lock = threading.Lock()

    def now(self) -> float:
        with self._lock:
            return self._now

    def advance(self, seconds: float) -> None:
        with self._lock:
            self._now += seconds


def _wait_until(predicate, timeout: float = 2.0, interval: float = 0.01) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(interval)
    raise AssertionError("Timed out waiting for condition")


def test_submit_task_completes_success():
    manager = AsyncCalibrationManager(max_workers=2, task_ttl_seconds=3600)
    try:
        def do_work(x):
            return f"ok:{x}", None

        task_id = manager.submit_task("ABC123", do_work, "ABC123")
        assert task_id

        _wait_until(lambda: manager.get_task_status(task_id) is not None and manager.get_task_status(task_id).status in {TaskStatus.COMPLETED, TaskStatus.FAILED})

        task = manager.get_task_status(task_id)
        assert task is not None
        assert task.status == TaskStatus.COMPLETED
        assert task.result == "ok:ABC123"
        assert task.error is None
        assert task.completed_at is not None
    finally:
        manager.shutdown(wait=True)


def test_task_failure_sets_error():
    manager = AsyncCalibrationManager(max_workers=2, task_ttl_seconds=3600)
    try:
        def do_work_fail():
            return None, "Calibration failed"

        task_id = manager.submit_task("ABC123", do_work_fail)
        _wait_until(lambda: manager.get_task_status(task_id) is not None and manager.get_task_status(task_id).status in {TaskStatus.COMPLETED, TaskStatus.FAILED})

        task = manager.get_task_status(task_id)
        assert task is not None
        assert task.status == TaskStatus.FAILED
        assert task.result is None
        assert task.error == "Calibration failed"
        assert task.completed_at is not None
    finally:
        manager.shutdown(wait=True)


def test_task_result_ttl_cleanup():
    clock = FakeClock(start=1000.0)
    manager = AsyncCalibrationManager(max_workers=1, task_ttl_seconds=3600, time_fn=clock.now)
    try:
        def do_work():
            return "done", None

        task_id = manager.submit_task("ABC123", do_work)
        _wait_until(lambda: manager.get_task_status(task_id) is not None and manager.get_task_status(task_id).status in {TaskStatus.COMPLETED, TaskStatus.FAILED})

        assert manager.get_task_status(task_id) is not None

        clock.advance(3600.1)
        assert manager.get_task_status(task_id) is None
    finally:
        manager.shutdown(wait=True)


def test_max_concurrency_respected():
    manager = AsyncCalibrationManager(max_workers=5, task_ttl_seconds=3600)
    try:
        start_event = threading.Event()
        release_event = threading.Event()
        lock = threading.Lock()
        active = 0
        max_active = 0

        def blocking_work(i):
            nonlocal active, max_active
            start_event.wait()
            with lock:
                active += 1
                if active > max_active:
                    max_active = active
            release_event.wait()
            with lock:
                active -= 1
            return i, None

        task_ids = [manager.submit_task(f"task:{i}", blocking_work, i) for i in range(10)]
        start_event.set()

        _wait_until(lambda: max_active >= 1, timeout=2.0)
        _wait_until(lambda: max_active <= 5, timeout=2.0)

        # 让所有任务完成
        release_event.set()
        _wait_until(
            lambda: all(
                (manager.get_task_status(tid) is not None and manager.get_task_status(tid).status in {TaskStatus.COMPLETED, TaskStatus.FAILED})
                for tid in task_ids
            ),
            timeout=5.0,
        )

        assert max_active <= 5
    finally:
        manager.shutdown(wait=True)

