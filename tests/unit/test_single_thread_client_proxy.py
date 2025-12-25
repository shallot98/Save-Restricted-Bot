"""
Unit tests for SingleThreadClientProxy.
"""

from __future__ import annotations

import threading

from bot.utils.threadsafe_client import SingleThreadClientProxy


class _LoopAlwaysRunning:
    def is_running(self) -> bool:  # pragma: no cover
        return True


class _FakeClient:
    def do_work(self) -> str:
        return threading.current_thread().name

    def on_message(self) -> str:
        return threading.current_thread().name


def test_proxy_runs_calls_in_single_thread() -> None:
    client = _FakeClient()
    proxy = SingleThreadClientProxy(client, loop=_LoopAlwaysRunning(), name="test-client")
    try:
        thread_name = proxy.do_work()
        assert thread_name == "test-client-single-thread"
    finally:
        proxy.close()


def test_direct_call_names_bypass_proxy_thread() -> None:
    client = _FakeClient()
    proxy = SingleThreadClientProxy(client, loop=_LoopAlwaysRunning(), name="test-client")
    try:
        assert proxy.on_message() == threading.current_thread().name
    finally:
        proxy.close()

