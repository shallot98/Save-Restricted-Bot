"""
Pyrogram Client 线程安全代理

目标：
- 将对同一个 Client 实例的调用串行化，降低并发调用导致的竞态风险
- 尽量保持调用方式不变（兼容现有代码）
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import queue
import threading
import time
from typing import Any, Optional, Callable


class ThreadSafeClientProxy:
    """为 Pyrogram Client 提供粗粒度互斥保护的代理。"""

    def __init__(self, client: Any, lock: Optional[threading.RLock] = None) -> None:
        object.__setattr__(self, "_client", client)
        object.__setattr__(self, "_lock", lock or threading.RLock())

    @property
    def client(self) -> Any:
        return object.__getattribute__(self, "_client")

    def __getattr__(self, name: str) -> Any:
        target = getattr(self.client, name)
        if not callable(target):
            return target

        def _wrapped(*args: Any, **kwargs: Any):
            lock = object.__getattribute__(self, "_lock")
            with lock:
                return target(*args, **kwargs)

        return _wrapped

    def __setattr__(self, name: str, value: Any) -> None:
        if name in {"_client", "_lock"}:
            object.__setattr__(self, name, value)
            return
        setattr(self.client, name, value)


class SingleThreadClientProxy:
    """将对 Client 的所有调用串行化到一个专用线程中。

    设计目标：
    - **单线程调度**：所有 API 调用都在同一线程内执行，避免多线程下各自创建 event loop 导致的隐患
    - **启动期兼容**：在主线程且主 event loop 未运行时，直接调用底层方法（用于启动阶段的 peer 预热等）
    - **运行期安全**：当主 event loop 正在运行时，专用线程中的调用会通过 Pyrogram 的 sync 包装调度到主 loop
    """

    _DIRECT_CALL_NAMES = {
        # Handler registration / lifecycle should be called directly.
        "on_message",
        "on_callback_query",
        "add_handler",
        "remove_handler",
        "start",
        "run",
        "idle",
    }

    def __init__(
        self,
        client: Any,
        loop: Optional[asyncio.AbstractEventLoop] = None,
        name: str = "pyrogram-client",
    ) -> None:
        object.__setattr__(self, "_client", client)
        object.__setattr__(self, "_loop", loop or self._try_get_event_loop())
        object.__setattr__(self, "_closed", False)
        object.__setattr__(self, "_queue", queue.Queue())
        thread = threading.Thread(
            target=self._worker,
            name=f"{name}-single-thread",
            daemon=True,
        )
        object.__setattr__(self, "_thread", thread)
        thread.start()

    @staticmethod
    def _try_get_event_loop() -> Optional[asyncio.AbstractEventLoop]:
        try:
            return asyncio.get_event_loop()
        except RuntimeError:
            return None

    @property
    def client(self) -> Any:
        return object.__getattribute__(self, "_client")

    def close(self, timeout: float = 5.0) -> None:
        if object.__getattribute__(self, "_closed"):
            return
        object.__setattr__(self, "_closed", True)
        q: queue.Queue = object.__getattribute__(self, "_queue")
        q.put(None)
        thread: threading.Thread = object.__getattribute__(self, "_thread")
        thread.join(timeout=timeout)

    def stop(self, *args: Any, **kwargs: Any) -> Any:
        try:
            return self.client.stop(*args, **kwargs)
        finally:
            self.close()

    def _wait_for_main_loop(self) -> None:
        loop: Optional[asyncio.AbstractEventLoop] = object.__getattribute__(self, "_loop")
        if loop is None:
            return

        while not loop.is_running() and not object.__getattribute__(self, "_closed"):
            time.sleep(0.05)

    def _worker(self) -> None:
        q: queue.Queue = object.__getattribute__(self, "_queue")
        while True:
            item = q.get()
            if item is None:
                return

            future, func, args, kwargs = item
            if future.cancelled():
                continue

            self._wait_for_main_loop()
            try:
                result = func(*args, **kwargs)
            except BaseException as e:
                future.set_exception(e)
            else:
                future.set_result(result)

    def __getattr__(self, name: str) -> Any:
        target = getattr(self.client, name)
        if not callable(target):
            return target

        if name in self._DIRECT_CALL_NAMES:
            return target

        def _wrapped(*args: Any, **kwargs: Any):
            if threading.current_thread() is object.__getattribute__(self, "_thread"):
                return target(*args, **kwargs)

            loop: Optional[asyncio.AbstractEventLoop] = object.__getattribute__(self, "_loop")
            if (
                threading.current_thread() is threading.main_thread()
                and loop is not None
                and not loop.is_running()
            ):
                return target(*args, **kwargs)

            if object.__getattribute__(self, "_closed"):
                raise RuntimeError("Client proxy is closed")

            future: concurrent.futures.Future = concurrent.futures.Future()
            q: queue.Queue = object.__getattribute__(self, "_queue")
            q.put((future, target, args, kwargs))
            return future.result()

        return _wrapped

    def __setattr__(self, name: str, value: Any) -> None:
        if name in {"_client", "_loop", "_closed", "_queue", "_thread"}:
            object.__setattr__(self, name, value)
            return
        setattr(self.client, name, value)
