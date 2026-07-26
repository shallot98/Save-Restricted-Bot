"""数据库启动初始化（原仓库根 ``database.init_database``）。

这里是 ``init_database`` 的唯一实现。此前它住在根 ``database.py``，而
``src/compat/database_compat.py`` 又反向 ``from database import init_database``，
构成 ``web → src.compat → 根 database.py → src.infrastructure`` 的三层跨越
兼双向桥（报告 §2.2 / §6.3）。实现下沉后桥的中段变成薄壳，Phase 3 已随整个
``src/compat`` 包删除；现在 ``web/__init__.py`` 直连本模块。
"""

from __future__ import annotations

from src.core.config import settings
from src.infrastructure.persistence.sqlite.migrations import run_migrations


def init_database() -> None:
    """建库 + 跑迁移。两个进程入口（Bot / Web）都会调用，迁移自身是幂等的。"""
    data_dir = str(settings.paths.data_dir)
    database_file = str(settings.paths.data_dir / "notes.db")

    print("=" * 50)
    print("🔧 正在初始化数据库...")
    print(f"📁 数据目录: {data_dir}")
    print(f"💾 数据库路径: {database_file}")

    run_migrations()

    print("✅ 数据库初始化完成！")
    print("=" * 50)
