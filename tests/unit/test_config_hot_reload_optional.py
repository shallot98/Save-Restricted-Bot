"""配置热重载可选依赖（watchdog）的回归测试。

背景：报告 §3 P1-8 末段 / §4 Phase 3 ③。热重载链路
(`settings_hot_reload -> hot_reload -> watcher -> watchdog`) 只被
`tests/integration/test_hot_reload.py` 使用，生产入口从不启用；此前
`settings.py` 在模块加载时就把整条链拉起来，watchdog 因此成为强制运行时依赖。

这里钉住三条不变量：
1. 导入 settings 不会加载 watchdog（真实解释器进程实测，不是读源码推断）；
2. watchdog 缺席时 Settings 的常规读写照常工作；
3. 缺席时显式启用热重载抛带安装提示的明确错误，而不是静默降级。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from src.core.config import settings
from src.core.config.exceptions import HotReloadUnavailableError
from src.core.config.settings_hot_reload import load_hot_reload_manager_cls

PROJECT_ROOT = Path(__file__).resolve().parents[2]

_WATCHDOG_SENTINEL = "watchdog"


class _ImportBlocker:
    """meta_path finder：让指定前缀的模块导入失败，模拟依赖缺席。"""

    def __init__(self, blocked_prefix: str):
        self._blocked_prefix = blocked_prefix

    def find_spec(self, fullname, path=None, target=None):  # noqa: D401 - importlib 协议
        if fullname == self._blocked_prefix or fullname.startswith(self._blocked_prefix + "."):
            raise ModuleNotFoundError(f"No module named {fullname!r}", name=fullname)
        return None


def _block_module(monkeypatch: pytest.MonkeyPatch, prefix: str) -> None:
    """在当前测试范围内让 ``prefix`` 及其子模块不可导入。

    已缓存的模块必须一并从 ``sys.modules`` 移除，否则按需导入会命中缓存而不会
    真正走 finder。monkeypatch 在测试结束后会把它们原样放回。
    """
    for name in list(sys.modules):
        if name == prefix or name.startswith(prefix + "."):
            monkeypatch.delitem(sys.modules, name, raising=False)
    # 这两个模块在模块级 import watchdog，必须重新执行才能观察到缺席。
    for name in ("src.core.config.watcher", "src.core.config.hot_reload"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    monkeypatch.setattr(sys, "meta_path", [_ImportBlocker(prefix)] + list(sys.meta_path))


@pytest.fixture
def watchdog_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    _block_module(monkeypatch, _WATCHDOG_SENTINEL)
    # 单例状态防护：确保用例从「未启用热重载」开始，且退出后不残留。
    monkeypatch.setattr(settings, "_hot_reload_manager", None, raising=False)


def test_importing_settings_does_not_load_watchdog(tmp_path: Path) -> None:
    """真实进程实测：settings 的导入链不得触碰 watchdog。"""
    code = (
        "import sys\n"
        "from src.core.config import settings\n"
        "assert settings.main_config is not None\n"
        "print('watchdog' in sys.modules)\n"
    )
    env = dict(os.environ, DATA_DIR=str(tmp_path / "data"), PYTHONPATH=str(PROJECT_ROOT))
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines()[-1] == "False", (
        "导入 settings 时加载了 watchdog，可选依赖被重新变成强制依赖"
    )


def test_settings_reads_and_writes_work_without_watchdog(watchdog_absent: None) -> None:
    """watchdog 缺席时，Settings 的常规读写路径必须照常工作。"""
    assert settings.main_config is not None
    assert isinstance(settings.watch_config, dict)
    assert isinstance(settings.monitored_sources, set)
    assert settings.get("__definitely_missing_key__", "fallback") == "fallback"
    # 读取型重载（不依赖热重载子系统）同样不得被 watchdog 缺席影响
    assert isinstance(settings.reload_monitored_sources(), set)


def test_enable_hot_reload_without_watchdog_raises_actionable_error(
    watchdog_absent: None,
) -> None:
    """显式启用热重载时必须报明确错误（含安装提示），不许静默降级。"""
    with pytest.raises(HotReloadUnavailableError) as excinfo:
        settings.enable_hot_reload()

    message = str(excinfo.value)
    assert "watchdog" in message
    assert "pip install" in message
    # 失败后不得留下半启用状态
    assert settings._hot_reload_manager is None


def test_subscribe_without_watchdog_raises_actionable_error(watchdog_absent: None) -> None:
    """subscribe() 是第二个入口，同样要求 watchdog，且报同一个明确错误。"""
    with pytest.raises(HotReloadUnavailableError):
        settings.subscribe(lambda *args, **kwargs: None)

    assert settings._hot_reload_manager is None


def test_unrelated_import_error_is_not_masked_as_missing_watchdog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """非 watchdog 引起的 ImportError 必须原样抛出，不能被伪装成「缺 watchdog」。"""
    _block_module(monkeypatch, "src.core.config.notifier")

    with pytest.raises(ImportError) as excinfo:
        load_hot_reload_manager_cls()

    assert not isinstance(excinfo.value, HotReloadUnavailableError)
    assert "notifier" in str(excinfo.value)


def test_hot_reload_manager_loads_when_watchdog_present() -> None:
    """按需加载在依赖齐备时必须真的能拿到类（否则可选化会静默废掉功能）。"""
    pytest.importorskip("watchdog")

    from src.core.config.hot_reload import HotReloadManager

    assert load_hot_reload_manager_cls() is HotReloadManager
