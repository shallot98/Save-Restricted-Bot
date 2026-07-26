# 重构路线图 Phase 0/1 落地

依据：`docs/ARCHITECTURE_REFACTOR_REPORT_2026-07-26.md` §4 路线图 + §7 任务清单。

## 本任务范围（清单 #5–#16，纯代码侧）

| # | 项 | 关键文件 |
|---|---|---|
| 5 | 停用 monitoring 子系统（代码侧 no-op，不删数据文件） | `src/infrastructure/persistence/sqlite/connection.py`、`src/infrastructure/monitoring/` |
| 6 | 删根 `config.json`（含活凭据、零代码读取）+ 补白名单式 `.dockerignore` | 仓库根 |
| 7 | magnet 模块簇下沉 `bot/utils` → `src/domain/magnet/`，删平行死实现，消 7 条反向边 | `bot/utils/magnet_*.py`、16 处引用方 |
| 8 | mypy 范围收敛 + 消模块重名 + 错误基线 | `mypy.ini`、CI |
| 9 | 删 `test_config_priority.py`（破坏性副作用）、修 `test_config_persistence.py` 空断言 | `tests/unit/` |
| 10 | CI 加 `check_requirements_lock.py --include-dev` | `.github/workflows/` |
| 11 | `calibrate_{qbt,bot}_helper.py` → `scripts/runtime/` + 包内路径解析；删零引用 `calibrate_helper.py` | `bot/services/calibration_scripts.py` 等 |
| 12 | 根目录 19 个一次性脚本 → `scripts/oneoff/`、81 个 md → `docs/archive/`、根 32 个 test_*.py（4 个迁入其余删）、AI 工具目录 gitignore | 仓库根 |
| 13 | 误导性死代码：死回调路由分支、前端零引用资产（避开 07-21 filter-bar 在途改动的 notes.html/notes.js） | `bot/handlers/callback_handlers/`、`static/` |
| 14 | 8 个高危吞错点修复 + 各一条断言测试（失败方向改为拒绝/告警） | 见报告 P1-5 表 |
| 15 | 迁移竞态：ALTER try/except + `BEGIN IMMEDIATE` | `migrations.py` |
| 16 | catch-up 游标推进后置到入队成功之后；关闭路径调用 `MessageWorker.stop()+join` | `auto_forward_pipeline.py`、`main.py`、`bot/core/queue.py` |

## 明确不做（本任务）

- 线上基础设施操作：ufw、docker 重建、删 `data/monitoring.db`、轮换密钥（用户手动执行）
- Phase 2 结构重排（import-linter、容器迁移、compat 拆桥）与 Phase 3
- `git commit`（全局 Git 只读规则，改动留在工作区由用户分批提交）

## 验收

- `pytest tests/unit` ≥ 313 passed（原基线）+ 新增测试全绿
- `mypy`（收敛范围后）有明确基线且退出码可控
- `src/` 内 `from bot.` 顶层导入减少 ≥3 条
- 两个入口模块可被 import（冒烟）

## 测试环境

`/tmp/claude-0/-root-Save-Restricted-Bot/c5e0a896-f14e-4ab5-b4f6-2bedcdb13e0e/scratchpad/venv/bin/python -m pytest tests/unit -q`
