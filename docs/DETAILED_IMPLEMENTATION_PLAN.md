# Save-Restricted-Bot 详细实施方案

**项目**：Save-Restricted-Bot（受限内容 Telegram 转发 + 笔记归档机器人）  
**版本**：基于 2026-07-26 架构报告 + 当前代码基线  
**日期**：2026-08-10  
**状态**：**Phase 0 / 1 / 2 已执行完成**

## 阶段状态

| 阶段 | 状态 | 说明 |
|------|------|------|
| Phase 0 止血 | ✅ 完成 | Web 密钥、OWNER 鉴权、去重时区、monitoring 停用、凭据清理 |
| Phase 1 结构收口 | ✅ 完成 | magnet 下沉、组合根、import-linter、mypy 基线、一次性脚本归档 |
| Phase 2 移动 + 性能 | ✅ 完成 | 移动导航安全区/触控、列表缓存 TTL、校准线程池、LOG_LEVEL |

## Phase 2 本次落地

1. **移动端**
   - `templates/components/mobile_nav.html`：补 `pb-safe`（iOS safe-area）、44px 触控目标、`touch-action: manipulation`、`aria-label`
2. **性能**
   - 笔记列表缓存 TTL：`300s` → `60s`（`note_service_query.py`）
   - 校准调度：无限 `Thread().start()` → 有界 `ThreadPoolExecutor(max_workers=2)`（`note_service_writes.py`）
3. **日志**
   - `setup_logging` 支持环境变量 `LOG_LEVEL`（默认 INFO）
   - `docker-compose.yml` web/bot 注入 `LOG_LEVEL=${LOG_LEVEL:-INFO}`
4. **工程修正**
   - 恢复被误归档的 `setup.py` / `run_all_tests.sh` / `run_mobile_tests.sh` 到仓库根
   - 一次性运维脚本保留在 `scripts/oneoff/`
   - 删除无效的 `.importlinter.yaml`（正式契约仍为 `.importlinter`）

## 验收清单

- [x] Web 端口 `127.0.0.1:10000`，密钥不再使用固定明文默认值
- [x] Bot handler 经 `OwnerFilter` 白名单
- [x] 笔记列表缓存 60s；校准任务有界线程池
- [x] 移动底栏 safe-area + 44px 触控
- [x] `setup.py` 仍在根目录（文档与 dockerignore 一致）
- [x] 正式 import-linter 契约：`.importlinter`

## 后续可选（非阻塞）

- 安装 dev 依赖后跑 `pytest tests/unit` 与 `lint-imports`
- 合并/推送 `feat/mobile-responsive-optimization-v2`
- 生产 `.env` 设置强 `FLASK_SECRET_KEY` / `ADMIN_PASSWORD` / `OWNER_ID`

---

**作者**：Grok（xAI）  
**建议**：部署前 `docker compose up -d --force-recreate`，并确认 `.env` 中密钥与口令已替换。
