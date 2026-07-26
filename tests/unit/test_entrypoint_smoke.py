"""两个进程入口的启动冒烟测试（报告 §6.3「拆双向桥时」风险条）。

背景：``web/__init__.py`` → ``src.compat.database_compat.init_database`` → 根
``database.py`` 曾是一条跨三层的双向桥。Phase 2 拆桥时若拆错顺序，Web 进程直接起
不来；而现有单测全部运行在「模块已成功 import」的前提之下，天然捕捉不到「进程
能否启动」这件事。本文件把这个前提本身变成断言。

Phase 3 已删除整个 ``src/compat`` 包，桥的中段不复存在；断言随之改为守住**收敛
后的权威链路**（见 ``test_db_bootstrap_chain_is_resolvable``）。

隔离方案：
- 每个用例在**子进程**里 import，入口模块的 import 副作用（建库、跑迁移、初始化
  存储管理器、配置全局 logging）因此不会污染测试进程。
- 子进程的 ``DATA_DIR`` 指向 ``tmp_path``。``src/core/config/settings_paths.py``
  的 ``PathConfig.data_dir`` 在每次属性访问时读该环境变量，且 ``notes.db`` /
  ``config/`` / ``media/`` 全部由它派生，所以单个变量即可完成整体重定向——生产
  ``data/`` 不会被碰到，``test_web_entrypoint_imports_and_builds_app`` 用
  「tmp 目录下确实出现了 notes.db」反证这一点。
- ``import app`` 会真的执行 ``create_app()``，但不产生外部网络依赖：WebDAV 配置
  读的是 tmp 下不存在的 ``config/webdav_config.json``，``web/utils/storage.py``
  的 ``_init_webdav_storage`` 在未启用时直接返回 None，回落本地存储。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
IMPORT_TIMEOUT_SECONDS = 120


def _run_in_subprocess(snippet: str, data_dir: Path) -> subprocess.CompletedProcess:
    """在隔离的子进程中执行 snippet，数据目录重定向到 data_dir。"""
    env = dict(os.environ)
    env["DATA_DIR"] = str(data_dir)
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    return subprocess.run(
        [sys.executable, "-c", snippet],
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=IMPORT_TIMEOUT_SECONDS,
    )


def _assert_runs_clean(snippet: str, data_dir: Path) -> None:
    result = _run_in_subprocess(snippet, data_dir)
    assert result.returncode == 0, (
        f"入口冒烟失败 (exit={result.returncode})\n"
        f"--- snippet ---\n{snippet}\n"
        f"--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )


def test_bot_entrypoint_imports(tmp_path: Path) -> None:
    """Bot 进程入口 main.py 可被 import（模块图无断链）。"""
    _assert_runs_clean(
        "import main; assert callable(main.main)",
        tmp_path / "data",
    )


def test_web_entrypoint_imports_and_builds_app(tmp_path: Path) -> None:
    """Web 进程入口 app.py 可被 import，且 create_app() 能真正跑完。

    拆桥后这条链路已收敛为单向：app.py → web.create_app →
    src.infrastructure.persistence.init_database → 迁移，不再经由
    src.compat（已删除）与根 database.py。本用例守住的正是「收敛后仍能起进程」。
    链路符号本身的可解析性由 test_db_bootstrap_chain_is_resolvable 单独覆盖。
    """
    data_dir = tmp_path / "data"
    _assert_runs_clean(
        "import app; assert app.app is not None",
        data_dir,
    )
    # 反证隔离生效：库建在 tmp 而不是生产 data/
    assert (data_dir / "notes.db").exists()


def test_db_bootstrap_chain_is_resolvable(tmp_path: Path) -> None:
    """建库入口与 Web 工厂必须始终可从权威源解析。

    原断言取的是 ``src.compat.database_compat.init_database``（桥的中段）。Phase 3
    删除 ``src/compat`` 后改断言权威源 ``src.infrastructure.persistence``——
    这条才是 ``web/__init__.py`` 真正走的路径，也是拆桥时最先断掉的符号。
    """
    _assert_runs_clean(
        "from src.infrastructure.persistence import init_database\n"
        "from web import create_app\n"
        "assert callable(init_database) and callable(create_app)\n",
        tmp_path / "data",
    )


def test_compat_package_is_gone() -> None:
    """``src/compat`` 必须保持删除状态（§5.1「明确取消 src/compat」）。

    这是一条防回归断言：兼容层的历史教训是「新结构并存 + 双向桥」让迁移在最贵的
    地方停摆（报告 §3 P1-1 根因）。任何人重新引入这个包，本用例立即失败。
    """
    assert not (PROJECT_ROOT / "src" / "compat").exists()
