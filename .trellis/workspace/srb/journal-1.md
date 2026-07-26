# Journal - srb (Part 1)

> AI development session journal
> Started: 2026-03-30

---


## 2026-07-26 P0 安全整改（续前会话）

- 任务 `07-26-p0-security-owner-auth-dedup-tz` 设为当前任务（planning → in_progress）。
- 前会话已完成实现：`bot/handlers/authorization.py`（OWNER_ID 白名单过滤器，解析失败方向为拒绝）、`datetime_utils.db_cutoff` 修复去重窗口 UTC/UTC+8 错配、判重分支记录被丢弃内容预览、watch catch-up（store/scanner/scheduler + migrations + main.py 接线）。
- 本会话验证：新建 venv（仓库 .venv 不可用），`pytest tests/unit` → **313 passed**（基线 289 + 新增 24），新模块导入冒烟通过。
- 未提交：全局规则禁止 git commit，27 处改动仍在工作区，等待用户自行提交。

## 2026-07-26 重构路线图 Phase 0/1 落地（任务 refactor-roadmap-phase01）

- 9 个 Opus 5 实现代理 + 1 个 trellis-check 收口，完成报告 §7 任务 #5-#16：monitoring 停用、迁移竞态、connection 回滚缺口、magnet 下沉（src/ 顶层反向依赖 3→0）、calibrate helper → scripts/runtime、mypy 683 条基线 + CI 比对、CI 依赖锁检查、坏测试删除、根 config.json 备份至 data/、白名单 .dockerignore（构建上下文 1.1G→2.9M）、7 个吞错点失败方向修正、死回调路由与 44 个前端死资产删除、根目录 19 脚本/28 test_*.py/79 md 归档、游标推进后置（live + 补扫双路径闭合）、MessageWorker 关闭路径 stop+join。
- 最终状态：370 passed / mypy 新增 0 / 双入口冒烟 ok / 255 文件 +2768/−10204，全部留在工作区未提交（Git 只读规则）。
- **P0 事故与修复**：单测经 `_sync_to_json` 的函数内惰性 import 覆写了生产 data/config/watch_config.json；已加 conftest autouse 拦截并从 notes.db 恢复 4 条任务；教训已写入 spec/backend/quality-guidelines.md。
- 遗留（按严重度）：watch JSON 双写整体覆盖（结构性，待 §6.2 Q2 确认）、database_compat 里一处 live db_tracer.enable 未 no-op、auto_forward_pipeline.py 404 行超标、magnet shim 零引用可删、5 处 CHINA_TZ 副本、CRLF 规整噪音建议单独提交。
- 报告一处被实证推翻：mode_handler 的 extract_custom/extract_magnet 是 live 路由（fwdmode_ 链路），未删。

## 2026-07-26（续）遗留清单处理完毕

- watch JSON 双写删除（HEAD 本无 `_sync_to_json`，系在途改动引入；生产 JSON 现零写入方，含真实写盘替身的防复活测试）。
- tracer 启用方全仓清零（database_compat live 路径 + media_cleanup + 自查出的 db_security 第三处）。
- auto_forward_pipeline 拆分 404→282 行，进度契约独立成 auto_forward_progress.py（163 行），断言零改动。
- magnet shim 删除、5 处 CHINA_TZ 统一、package.json 4 条断链 scripts 删除。
- 行尾噪音逐行恢复 HEAD 风格（14 文件约 2360 行幻影 diff 消除），全仓归一化 + .gitattributes 留作提交后的独立格式 commit。
- 终态：371 passed / mypy 683 新增 0 / 双入口冒烟 ok / 269 文件 +1738/−9195，未提交。

## 2026-07-26（续二）Phase 2（#17-#20）完成

- Wave A：DI 容器 git mv 至 composition/（src/core 反向 import 清零，Docker 实建验证入镜像）；双入口冒烟测试上岗；JSONWatchRepository 死实现删（发现 P1-5 #1 修复曾打在死代码上，回归用例改钉生产 parse_config_dict）。中途登录过期打断两代理，SendMessage 续跑无损失。
- Wave B：src→bot 生产反向依赖清零。新端口 CalibrationScheduler / MediaStorage（src/core/interfaces），装配收 composition/wiring.py（启动期而非 import 期，避免经根 database.py 的导入环），+17 注入测试。
- Wave C：compat 双向桥拆除。database_notes/note_requests 下沉 src/infrastructure/persistence/legacy/，web/__init__ 直连 infrastructure，compat 586→332 行，7 个零引用薄包装删除；calibration_manager 服务定位改构造注入（单例工厂上移 composition/calibration.py）。
- Wave D：import-linter 4 契约 CI error 级（豁免仅 1 条），反证探针 4/4 broken 验证有效；锁定版本组合（click 8.3.1）主会话复验通过。
- 终检 PASS + 重要修复：check_mypy_baseline.py 存在假绿路径（mypy 夭折 → 解析 0 错误 → exit 0，会复现 P1-2 历史故障），已加完整性校验 + 4 条门禁自测；教训写入 spec。
- 终态：390 passed / integration 113+2（既有）/ lint-imports 4 kept / mypy 基线 670 新增 0。全部未提交。
- Phase 3 候选：bot/web 16 处 get_xxx() 服务定位、src.application→infrastructure 5 处函数内 import、compat 与根薄壳删除、test_optimization 2 条断言随薄壳删、integration 坏文件 collect_ignore、create_app() 依赖注入（#21）、watchdog 可选化（#22）。

## 2026-07-26（续三）Phase 3 完成，重构全程收官

- Wave E：watchdog 移出运行时依赖（真实无 watchdog venv 冒烟）；application→infrastructure 5 处清零（4 新端口，契约收紧为 application|infrastructure 独立兄弟层，发现 import-linter `:`/`|` 语义陷阱）；integration 树从 INTERNALERROR 修到 114 全绿（另修 5 个 return 式假绿用例）。
- Wave F：bot/web 16 处服务定位全消（BotServices/WebServices DTO，保留 0 处），composition 入契约层序顶端；顺手根治 /api/calibrate/async kwargs 双包 bug。
- Wave G：web/routes 覆盖 0%→84%（+117 用例），web/__init__ 开 WebInfrastructure 注入缝；盘出 6 个未修 bug（/health 泄内部路径、api.py 四处异常回显等，均有测试钉现状）。
- Wave H：src/compat 整包删除（防复活断言）、根兼容模块 9→3（auth/calibration 下沉 legacy/，migrations/optimization 死代码删）、契约豁免清零，净 −649 行。
- 终检 PASS + 3 项一致性修复（基线棘轮 670→659、2 处失真注释）。函数内延迟 import 94→69。
- 终态：548 unit + 114 integration 全绿 / lint-imports 4 kept 0 豁免 / mypy 659 新增 0 / web/routes 84%。全部未提交。
- 未达成（范围决策）：integration 入 CI、配置入口完全收敛（setup.py 直写 + pt_pay/signin 独立 store + src/core/config 2331 行）。中断插曲：登录过期×1，SendMessage 续跑无损失。
