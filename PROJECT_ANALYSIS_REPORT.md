# 项目分析报告（Save-Restricted-Bot）

> 本报告整合两轮审读结果：第一轮聚焦整体结构/技术栈/核心模块（High），第二轮下钻隐藏技术债、性能/并发风险与可扩展性（XHigh）。  
> 审读范围：仓库代码与文档（以当前工作区为准），不包含线上运行环境与真实业务数据。

## 0) 落地进度（对照本报告）

> 截至 2025-12-24：本仓库已落地多项 P0/P1 “止血项/结构性优化”。本节用于标注哪些结论已被实现修复、哪些仍建议推进。

**已落地（摘要）**
- 配置：新增 `getenv_optional` 并在 client 初始化侧按“缺失/空值=未配置”处理 `STRING`，避免误初始化 User Client。
- Watch：监控配置已迁移到 SQLite（`watch_tasks` 表）作为单一真相；提供从 `data/config/watch_config.json` 的一次性 best-effort 迁移；WatchRepository 保留 `source -> tasks` 索引，auto_forward 仍按 source 取任务避免 O(N) 扫描。
- Worker：重试按需重新获取消息（不依赖被清理的 message 对象）；使用延迟队列替代阻塞 sleep；队列引入 `MESSAGE_QUEUE_MAXSIZE` 与满队列丢弃策略。
- 媒体：`StorageManager` 对 `storage_location` 做类型/文件名校验并限制路径；Range 响应改为流式读取；路径穿越风险已修复。
- 并发：peer 缓存与 `user_states` 代理补齐锁与 TTL 语义，降低竞态窗口。
- 校准：`process_pending_tasks` 使用线程池并发处理待执行任务；笔记更新引入并发冲突重试，避免多任务更新同一笔记时丢更新。
- 交付：Docker 基础镜像与 mypy 目标版本对齐到 Python 3.10；entrypoint 补齐进程托管与信号传播；新增 GitHub Actions 最小 CI（pytest unit + mypy）。
- Web 安全：已引入 CSRF（不依赖 Flask-WTF）、默认安全响应头（含 CSP）与登录限流；默认 admin/admin 登录后强制首次改密；HTML 响应默认 `Cache-Control: no-store`；CSP 的 `script-src` 已启用 nonce（不再使用 `'unsafe-inline'`），并禁用 inline 脚本属性（`script-src-attr 'none'`）且移除模板 inline handler；登录页已移除 Alpine 依赖并按路由禁用 `unsafe-eval`；会话 Cookie 安全属性默认更严格。
- 依赖：已引入 `requirements.runtime.txt`/`requirements.dev.txt` 拆分；Docker 仅安装 runtime（以 `requirements.lock` 作为 constraints），CI 安装 runtime+dev（同样受 constraints 约束）。

**仍建议推进**
- 搜索：已引入 SQLite FTS5（best-effort）并在不可用时回退到 LIKE；已补齐基础查询语义（分词/AND 语义、bm25 排序、Web 多 token 高亮）；规模进一步增长仍建议外部检索。
- 扩容：peer/cache/队列等仍是进程内状态，多实例下需要外部化或明确单实例约束。

## 1) 项目概述

**定位**
- 一个自托管的 Telegram 工具集：以 **Pyrogram Bot + Pyrogram User Client** 组合实现“保存/转发受限内容”；并提供一个 **Flask Web** 用于“记录模式（Record Mode）”的笔记浏览、媒体访问与管理后台。

**核心价值点**
- 通过 User Client 拉取受限消息（含媒体）并由 Bot 重新发送，从而绕过“转发保护/受限内容”带来的限制。
- 监控频道（/watch）自动处理新消息；支持过滤、提取模式、链式转发。
- 将消息记录为可检索的 Web 笔记，并提供 WebDAV 远程媒体存储与媒体代理（含 Range）。
- 内置监控与错误追踪基础设施（指标聚合 + SQLite 持久化 + Web 仪表盘）。

**运行入口与部署形态**
- Bot：`main.py`
- Web：`app.py`（Flask 应用工厂位于 `web/__init__.py`）
- 初始化配置：`setup.py`（交互式生成 `.env` 与 `data/config/config.json`）
- 进程声明：`Procfile`（`worker: python3 main.py` / `web: python3 app.py`）
- Docker：`Dockerfile` + `docker-compose.yml`（同容器内同时启动 Web 与 Bot）

**数据与配置**
- 运行数据默认落在 `data/`（可通过 `DATA_DIR` 指定），配置位于 `data/config/*.json`，媒体位于 `data/media/`。
- 环境变量：`.env`（或运行环境注入）提供 `TOKEN/HASH/ID/STRING`、`ADMIN_PASSWORD`、`FLASK_SECRET_KEY`、`TZ` 等；`DATA_DIR` 用于覆盖数据目录位置。
- 仓库通过 `.gitignore` 排除 `data/`、`*.db`、`.env`、`*.session` 等敏感或体积文件，目标是“代码更新不覆盖数据”。

## 2) 架构分析

### 2.1 总体架构（组件视图）

**消息处理主链路（Bot）**
- Pyrogram Bot Client：处理用户指令、链接转发、交互 UI（回调/菜单）。
- Pyrogram User Client（可选）：用于访问私有/受限消息、监听监控源消息（incoming/outgoing）。
- 消息队列 + Worker 线程：将自动监控的消息入队，统一执行转发/记录、限流与重试逻辑。

**Web（Flask）**
- 笔记列表/编辑/删除/收藏：基于 SQLite 中 `notes` 表。
- 管理后台：密码、WebDAV、观看链接配置、校准配置、任务队列查看。
- 媒体路由：本地文件服务或 WebDAV 代理（支持 Range）。
- 监控仪表盘：内存指标快照 + SQLite 持久化指标查询。

**持久化**
- `notes.db`：笔记、用户、校准任务与校准配置（同库）。
- `monitoring.db`：监控指标与错误事件（独立库，WAL + NORMAL）。
- `watch_tasks`：监控任务配置（SQLite 表；保留 `watch_config.json` 仅用于历史/迁移来源）。

### 2.2 分层架构现状：`src/` 新架构与旧模块并存

项目明确引入了“新分层架构”（`src/`）：
- `src/core/`：配置（Settings/热重载）、常量、异常、容器（简易 DI）。
- `src/domain/`：领域实体与领域服务（如过滤逻辑）。
- `src/application/`：应用服务与用例（NoteService/WatchService/CalibrationService）。
- `src/infrastructure/`：SQLite 连接/迁移、缓存、监控、WebDAV 等基础设施。
- `src/compat/`：兼容层（为旧模块提供向后兼容函数/常量）。

但运行入口仍主要依赖旧模块：
- Bot handler 仍在 `bot/handlers/*`，核心 worker 在 `bot/workers/message_worker.py`。
- Web app 工厂与路由仍在 `web/*`（虽已部分接入 `src` service）。

**结论**：当前处于迁移过渡期，“逻辑上想要分层”与“实际运行路径”尚未对齐，导致重复实现与边界模糊（详见第 6 节）。

### 2.3 配置与依赖注入

**Settings（配置中心）**
- `src/core/config/settings.py` 提供线程安全（RLock）的配置读写、原子落盘（临时文件 + `os.replace`）、监控源集合重建、热重载（watchdog）。
- 兼容层 `src/compat/config_compat.py` 将旧接口委托给 `settings`。

**ServiceContainer（DI 容器）**
- `src/core/container.py` 以单例 + 懒加载方式提供 repository/service 实例，降低模块耦合。
- 但仍存在“旧模块直接 import 兼容接口/直接 SQL”的路径，导致 DI 的收益被部分稀释。

### 2.4 可观测性（监控/错误追踪）
- `monitor_performance` 装饰器与 `db_tracer` 支持慢操作/慢查询检测，并可触发告警（告警系统实现为可选、失败不影响主流程）。
- `MetricCollector` 使用队列 + 后台线程批量聚合，并可周期性持久化到 `monitoring.db`。
- Web 侧 `/monitoring/*` 提供 dashboard 与 API（内存最近窗口 + DB 最近数据）。

### 2.5 数据模型（SQLite：notes.db / monitoring.db）

**notes.db（业务库）**
- `notes`：消息/媒体/磁力信息主表（`message_text`、`source_chat_id/source_name`、`timestamp`、`media_path/media_paths/media_group_id`、`magnet_link/filename`、`is_favorite`）。
- `users`：Web 管理后台账号（`username`、`password_hash`）。
- `calibration_tasks`：磁力校准任务队列（`status/next_attempt/retry_count/error_message` 等），外键关联 `notes(id)`。
- `auto_calibration_config`：自动校准策略（延迟/重试/并发/超时等；固定单行 `id=1`）。
- `watch_tasks`：watch 配置单一真相（复合主键 `user_id+watch_key`；white/black list 与 regex、extract_patterns 以 JSON 字段落库）。
- `watch_tasks`：watch 配置单一真相（复合主键 `user_id+watch_key`；新增 `watch_id` 作为稳定标识；white/black list 与 regex、extract_patterns 以 JSON 字段落库）。
- 检索与索引：best-effort 启用 FTS5（`notes_fts` 外部内容表 + 触发器同步；不可用时回退到 LIKE）；热点索引包含 `idx_notes_user_source_time`、`idx_watch_tasks_source`、`idx_calibration_status` 等。

**monitoring.db（可观测性库）**
- `metrics`：指标明细（`ts_epoch/name/metric_type/value/tags_json/metadata_json`）。
- `errors`：错误事件（`ts_epoch/fingerprint/error_type/message/stacktrace/context_json`）。
- 数据保留：通过 `MONITORING_DB_RETENTION_DAYS` 定期清理（默认 30 天）。

### 2.6 Web 入口与权限模型（会话/CSRF/CSP）

**认证与会话**
- Web 认证基于 Flask session：`web/auth.py` 提供 `login_required`（页面）与 `api_login_required`（JSON API）装饰器，统一校验 `session["username"]`。
- 默认弱口令治理：当以 `admin/admin` 登录时会设置 `session["must_change_password"]=True`，页面侧强制跳转到 `/admin`，API 侧返回 403，直至改密完成。

**CSRF**
- `web/security/csrf.py` 默认对所有非安全方法（POST/PUT/PATCH/DELETE）做 token 校验；支持 Header（`X-CSRFToken`/`X-CSRF-Token`）、Form（`csrf_token`）、JSON（`csrf_token`）。
- 模板通过 `csrf_token()` 注入隐藏字段；这意味着前端调用 JSON API 也需要显式携带 CSRF token。

**CSP 与安全响应头**
- `web/security/headers.py` 统一追加安全响应头；CSP 默认启用 nonce 并禁用 inline handler（`script-src-attr 'none'`），同时支持按路由通过 `g.csp_allow_unsafe_eval` 收紧/放开 `'unsafe-eval'`（登录页默认禁用）。

**迁移状态提示**
- 当前实际 Web 入口以 `web/routes/*` 为准；`src/presentation/web/*` 仍处于迁移阶段未接入主路由，应避免继续扩散“同名但不同语义”的重复实现。

## 3) 技术栈

**语言与运行时**
- Python 为主（Docker 基础镜像为 3.10；mypy 配置目标 3.10，版本对齐）。

**核心依赖（运行时）**
- Telegram：`pyrogram`、`tgcrypto`
- Web：`flask`（认证/CSRF/安全头/登录限流为自实现的 `web/*` 轻量组件）
- 可收敛依赖：已从运行时依赖移除 `flask-login`/`flask-wtf`/`flask-limiter`；Web 安全以 `web/security/*` 为单一入口（`bot/utils/security.py` 为遗留模块，未接入 Web 入口链路，后续可删除或迁移）
- 存储：`sqlite3`（标准库）、`bcrypt`
- 媒体/图片：`pillow`
- 远程存储：`webdavclient3`（webdav3）
- 网络：`requests`
- 校准相关：`libtorrent`（以及脚本调用 qBittorrent/Telegram bot）
- 配置：`pydantic>=2`、`pydantic-settings>=2`
- 热重载：`watchdog>=3`

**开发/构建与测试**
- 测试：`pytest`、`pytest-playwright`、`playwright`
- 类型检查：`mypy`、`types-requests`
- 前端资产压缩：Node 工具链（`terser`、`postcss`、`cssnano`）仅用于压缩静态文件（`build/*`）。

**依赖锁定**
- 已进一步收敛：`requirements.lock` 作为 constraints 已覆盖 runtime 直依赖，并提供 `scripts/check_requirements_lock.py` 校验覆盖度；仍建议补齐 dev 工具链（如 mypy/types）对应的 pinned 版本并形成固定升级流程。

## 4) 核心功能（实现与链路）

### 4.1 手动链接转发（受限内容保存）
- 用户发送 `https://t.me/...` 链接后，Bot 解析消息范围（支持 `from-to`）并按公开/私有/bot 链接类型处理。
- 私有/受限内容：User Client 拉取并下载媒体，再由 Bot 重新上传发送（规避“转发保护”）。

### 4.2 /watch 自动监控与队列处理
- User Client 监听监控源的消息；做早期过滤（是否监控源）、Peer 缓存与去重；将任务入队。
- Worker 线程从队列取出任务，执行：
  - 过滤（关键词/正则）
  - 转发（保留来源 forward / 隐藏来源 copy）
  - 提取模式（extract_patterns 提取后只发送提取内容）
  - 记录模式（Record Mode：落库 notes + 下载/存储媒体）
  - FloodWait/超时重试、退避与链式转发触发

### 4.3 Record Mode（Web 笔记）
- 将监控消息以“笔记”形式落库，Web UI 支持分页、来源过滤、搜索、日期过滤、收藏、编辑与删除。
- 媒体存储支持本地与 WebDAV（远程存储）；Web 可代理 WebDAV 资源并支持 Range 播放。

### 4.4 磁力链接校准（dn/filename）
- 数据库包含校准任务表与配置表；调度器定期扫描待处理任务。
- 校准实现通过 subprocess 调用脚本（qBittorrent API / Telegram bot）获取 filename，并回写笔记。
- Web API 提供同步/异步校准与任务队列管理。

### 4.5 可观测性
- 性能指标、DB 查询耗时、错误追踪写入内存聚合与 SQLite；Web 提供仪表盘查询。

## 5) 代码质量评估（工程视角）

### 5.1 优点（可复用的工程能力）
- 有明确的“目标架构”与迁移策略：`src/*` 分层 + `src/compat/*` 兼容层，降低一次性重构风险。
- 配置中心具备原子落盘与热重载能力，具备向成熟服务化演进的基础。
- 监控/错误追踪采用“尽力而为、失败降级”的策略，避免可观测性反噬主链路。
- 测试目录结构完整（unit/integration/mobile），覆盖面具备扩展潜力。

### 5.2 主要问题（影响长期可维护性）
- 新旧并存导致重复实现、边界模糊、语义漂移（watch key/过滤/缓存/持久化都存在）。
- 关键链路曾存在明显 bug 与不一致行为（watch_setup 残留、worker 重试载荷、session string 判定等已修复）；仍需持续用单元测试防回归。
- Docker 进程模型已支持分服务部署（`docker-compose.yml` 的 `web`/`bot`）；同容器多进程仅作为 `RUN_MODE=all` 兼容模式保留。
- 安全基线已补齐 CSRF/安全头/登录限流，并对默认 admin/admin 增加强制首次改密；HTML 响应默认 no-store；CSP 已禁用 inline handler（`script-src-attr 'none'`）且 `script-src` 采用 nonce（不含 `'unsafe-inline'`）；已支持按路由禁用 `unsafe-eval`（登录页已落地），仍建议逐步收敛 Alpine 依赖以扩大覆盖范围。
- 依赖策略仍需收敛：已引入 CI 与 Docker 的 lock+txt 安装，但 lock 覆盖度与 runtime/dev 拆分仍需明确。

## 6) 隐藏的架构问题和技术债务（XHigh 下钻）

### 6.1 双配置源与一致性风险（高优先级）
- 已进一步收敛：watch 配置以 SQLite `watch_tasks` 表为单一真相，并提供从 `watch_config.json` 的一次性迁移，避免“双写/双读”语义漂移。
- 写入侧通过事务保证一致性；读路径保留 in-memory `source_index` 以维持热路径性能。

### 6.2 watch key 语义漂移（架构债核心）
- 仍保留 `source|dest` 复合 key 以支持“一源多目标”，并通过 `_resolve_watch_key` 兼容旧 key 语义，降低历史数据/旧调用的破坏性。
- 引入 `source_index -> [watch_task]` 并在 `get_tasks_for_source` 使用索引，使 auto_forward 从 O(N) 全量扫描降到 O(k)（k=该源的任务数）。
- 后续建议：逐步以 `watch_id` 作为对外唯一标识，降低对 `watch_key` 的解析/兼容路径依赖（最终可删除旧 key 兼容，进一步降低维护成本）。

### 6.3 “移除功能不彻底”导致行为分裂
- watch_setup 已清理 DN 补全残留与未定义变量引用，避免“提示失败但实际写入已生效”的不一致状态。
- 提取逻辑已统一到 domain `FilterService.extract_content`；DN 补全相关逻辑已移除并有单元测试覆盖。

### 6.4 重复基础设施栈（DRY 违背）
- 缓存：`bot/utils/cache.py` 与 `src/infrastructure/cache/*` 并存。
- 过滤：`bot/filters/*` 已收敛为 `FilterService` 的薄包装（兼容层），实际业务逻辑统一在 `src/domain/services/filter_service.py`。
- 持久化：`database.py`（兼容层）与 `SQLiteNoteRepository` 并存；record mode 写入已迁移到 `NoteService`，但旧直连 SQL 仍存在，建议继续收敛为单一仓储入口。
- Web 安全：Web 入口链路已以 `web/security/*` 为单一入口；`bot/utils/security.py` 仍为遗留模块（未接入链路且包含 TODO），建议后续删除或迁移以避免误用与依赖面扩大。
- 结果：开发者难以判断“修复应落在哪一层”，容易出现补丁分叉。

### 6.5 类型边界不严与隐性运行时风险
- 风险已部分缓解：Repository 层已引入时间解析工具（如 `parse_db_datetime`）以保证 domain 层类型稳定；仍建议对所有入站/落库边界统一序列化策略并补齐测试。

### 6.6 原子写入策略不一致
- 已统一：WatchRepository 写入迁移至 SQLite 事务提交，避免文件落盘策略差异带来的损坏风险。

## 7) 潜在性能瓶颈（XHigh 下钻）

### 7.1 auto_forward 热路径 O(N) 扫描
- 已修复：auto_forward 改为 `get_tasks_for_source(source_chat_id)`，并依赖 watch repository 的 `source_index` 进行 O(k) 查询。

### 7.2 单 worker 串行 + 阻塞 sleep（吞吐上限明显）
- `MessageWorker` 单线程处理所有转发/下载/上传/存储。
- 已缓解：重试改为“延迟队列 + 计划执行时间”，避免 `sleep` 阻塞整个 worker。
- 已引入背压：消息队列支持 `MESSAGE_QUEUE_MAXSIZE`，入队使用非阻塞写入并在队列满时丢弃（记录指标/日志），避免无界内存增长。

### 7.3 搜索与统计双查询 + LIKE
- 已部分缓解：搜索改为单次扫描（`COUNT(*) OVER()` 窗口函数）避免双查询；但 `%LIKE%` 在大数据量下仍会退化（见第 10 节“检索能力”建议）。

### 7.4 Range 响应一次性读入内存
- 已修复：Range 分支改为生成器流式读取，避免一次性读入内存。

### 7.5 校准调度器“伪并发”
- `max_concurrent` 仅限制拉取数量，实际处理串行执行 subprocess（`bot/services/calibration_manager.py:506`），慢任务会拖慢全局。
- 已修复：`process_pending_tasks` 使用线程池并发处理；笔记更新侧增加并发冲突重试，避免并发写入导致的丢更新。

## 8) 并发/线程安全问题（XHigh 下钻）

### 8.1 Pyrogram client 跨线程共享（高风险）
- 已落地：引入 `SingleThreadClientProxy` 将对同一 Client 的调用统一调度到单线程，并通过 Pyrogram sync 的主 event loop 执行，避免多线程各自创建 event loop 带来的不确定行为。

### 8.2 Peer 缓存无锁
- 已修复：peer 缓存读写已加锁（RLock），并以 LRU + 冷却时间控制重试节奏。

### 8.3 user_states 代理绕过锁与 TTL 机制
- 已修复：`user_states[user_id]` 返回受控的可变视图，所有读写持锁并更新 `updated_at`，避免 TTL 清理误删与竞态写入。

### 8.4 配置热重载线程与读写竞争
- 已修复：热重载回调路径已纳入 Settings 的读写锁，降低竞态窗口。

### 8.5 SQLite 锁竞争与 WAL 策略不一致
- 已修复：notes.db 连接侧已启用 WAL 与 busy_timeout 等 PRAGMA，降低多线程写锁冲突概率。

## 9) 边界条件与异常处理缺陷（XHigh 下钻）

### 9.1 Session String 缺失判定错误（会导致错误初始化）
- 已修复：引入 `getenv_optional`（缺失/空白返回 None），并在 `initialize_clients` 侧按“None=未配置”判断是否初始化 user client；setup 写入空字符串不再触发误判。

### 9.2 watch_setup 未定义变量导致不一致写入
- 已修复：清理 `append_dn` 残留与相关分支，避免运行时异常与不一致写入。

### 9.3 worker 重试对象被提前清理（致命逻辑缺陷）
- 已修复：重试时按需重新获取消息（存储 `chat_id/message_id`），并避免对重试任务清理关键载荷。

### 9.4 媒体路由路径穿越 / 任意文件读取（高危）
- 已修复：`StorageManager` 对 `storage_location` 进行解析与白名单校验（仅允许 local/webdav + 安全文件名），并确保本地路径落在媒体目录内；Range 响应改为流式读取。

### 9.5 异常吞噬导致排障困难
- 多处 `except Exception: pass`（指标/错误上报等）会隐藏关键错误；建议至少记录摘要并带上上下文。
- 已部分缓解：在关键链路（auto_forward/message_worker 等）将监控/错误追踪失败从静默 `pass` 调整为 `debug` 级日志，保留上下文且不影响主流程。

## 10) 可扩展性限制

**Watch 规模**
- 已迁移到 SQLite `watch_tasks` 并建立索引；规模进一步增长时仍建议进一步收敛对外标识（以 `watch_id` 为主）并完善数据模型（例如 UI/配置展示层结构化），以降低长期维护成本。

**吞吐与延迟**
- 仍为单 worker 串行处理；已移除阻塞 sleep 并引入队列 maxsize/丢弃策略降低内存型故障概率，更高吞吐需多 worker 或统一 I/O 调度模型。

**多实例扩容**
- 异步校准任务、缓存、peer 状态均为进程内内存态；横向扩容后状态割裂，行为不可预测。
- 已部分缓解：Bot 启动时获取 `data/bot.lock`（基于 `DATA_DIR`），同一数据目录下的重复实例将拒绝启动，从机制上明确“单实例约束”。

**检索能力**
- 已引入 SQLite FTS5（best-effort）替代 `%LIKE%`；并补齐基础查询语义（分词/AND 语义、bm25 排序、Web 多 token 高亮）；在运行时不支持 FTS5 的场景会自动回退到 LIKE（功能可用但性能受限）。

## 11) 详细重构路线图（分阶段、可回滚）

> 目标：在不破坏现有功能的前提下，逐步收敛到“单一真相”（Single Source of Truth）、提升吞吐与可靠性、降低安全风险。

### Phase 0（P0：止血与基线修复，优先级最高）
- 修复 `STRING` 缺失/空字符串判定语义：确保未配置时 user client 不初始化；同时修正 `getenv` 行为（返回 `None` 或显式区分“缺失/空值”）。（已落地）
- 修复 `append_dn` 残留与相关死代码路径，避免运行时异常与行为分裂。（已落地）
- 修复 worker 重试：确保重试任务仍具备可重放的最小载荷（建议改为存储 `chat_id/message_id`，重试时重新 fetch，而不是持有 message 对象）。（已落地）
- 修复媒体路由安全：强制仅接受 `local:<filename>` / `webdav:<filename>`；对 filename 做 `basename` + 白名单字符校验；彻底禁止 `..` 与路径分隔符；Range 改为流式读取。（已落地）
- 为上述关键行为补齐单元测试（至少覆盖：STRING 判定、watch_setup、worker 重试、media 路由安全）。（已落地）

### Phase 1（P0/P1：配置与 Watch 单一真相）
- watch 配置迁移到 SQLite `watch_tasks` 作为单一真相，并提供一次性迁移来源 `watch_config.json`。（已落地）
- 保存后统一触发缓存失效（减少多处手动 reload）。（已落地）

### Phase 2（P1：重建 Watch 数据模型与索引）
- 引入显式 `watch_id`（或将 key 结构化为 `{source, dest}`），避免 “key=source” 的历史假设。（已落地：`watch_tasks.watch_id` + bot 回调基于 watch_id）
- 建立 `source_index -> [watch_task]`，让 auto_forward 从 O(N) 扫描降到 O(k)（k=该源的任务数）。（已落地）
- 修订/重写 `WatchRepository.get_tasks_for_source`、`remove_task`、`get_task` 的语义与测试。（已落地：兼容旧 key 并引入 key 解析）

### Phase 3（P1：过滤/提取统一到 domain）
- 将所有过滤/提取逻辑统一到 `src/domain/services/filter_service.py`；旧 `bot/filters/*` 仅保留薄 wrapper（或删除）。（已落地：过滤/提取均由 `FilterService` 承载，bot 侧仅保留兼容包装）
- 明确“DN 补全”是否保留：若已废弃则彻底移除，避免不同路径行为不一致。（已落地）

### Phase 4（P1：持久化统一与类型边界修复）
- record mode 写入从旧直连 SQL 迁移到 `NoteService`，逐步裁剪 `database.py` 的直连 SQL。（已落地）
- 统一时间字段序列化/反序列化（datetime <-> string），在 repository 层完成解析，domain 层保持类型稳定。（已落地：读写统一收敛到 `datetime_utils`，并兼容 ISO 8601 历史格式）
- notes.db 启用 WAL 与合理 PRAGMA（参考 `monitoring.db`），降低多线程写锁冲突。（已落地）

### Phase 5（P1/P2：并发模型与背压）
- 评估 Pyrogram 的线程安全假设：避免跨线程共享 client；或将所有 Telegram I/O 统一调度到单线程/单 event loop。（已落地：`SingleThreadClientProxy` 统一调度）
- 为队列设置 maxsize，提供丢弃/降级策略（例如只记录、跳过媒体、或暂停某些源）。（已落地）
- 将 `sleep` 型退避改为“重入队 + 计划执行时间”（时间轮/延迟队列），避免阻塞 worker。（已落地）

### Phase 6（P2：Web 侧性能与安全完善）
- Range 服务改为生成器流式输出，避免一次性读入内存。（已落地）
- 搜索引入 SQLite FTS5（或外部搜索）；列表缓存策略收敛并控制 key 维度，防止缓存键爆炸。（已落地：SQLite FTS5 + token 化查询 + bm25 排序 + 自动回退；notes 列表缓存仅在低基数过滤条件下启用并限制页数，避免 key 爆炸）
- 默认 admin/admin 改为强制首次改密或部署期注入。（已落地：默认密码登录后强制改密）
- 统一 CSRF、登录限流与安全响应头策略。（已落地）

### Phase 7（P2：交付一致性与质量门禁）
- 对齐 Python 版本（Docker 与 mypy 配置一致）。（已落地）
- 运行镜像使用锁定依赖（`requirements.lock` 作为 constraints）并拆分 runtime/dev 依赖。（已落地：Docker=runtime only；CI=runtime+dev；后续建议补齐 lock 覆盖度并收敛升级流程）
- 增加 CI：pytest（unit）+ mypy 为最小门禁；integration/mobile 分工作流按需执行。（已落地：`.github/workflows/ci.yml`）
- Docker 进程模型改为分服务（bot/web 分容器）或引入进程管理器，确保信号传播与健康检查语义可靠。（已落地：`docker-compose.yml` 拆分 `web`/`bot` 服务，web 使用 `/health` 健康检查）

---

### 附：配置与环境变量速查

**基础路径/运行入口**
- `DATA_DIR`：覆盖数据目录（默认 `./data`），影响 `notes.db`、`monitoring.db`、媒体与配置文件位置。
- `PORT`：Web 端口（本地 `app.py` 默认 5000；Docker `docker/entrypoint.sh` 默认 10000）。
- `RUN_MODE`：容器启动模式（`all|web|bot`，默认 `all`）。
- `ENV`：环境标识；当 `ENV=production` 时，配置模型会对主配置字段做“不能为空”校验（当前包含 `STRING/OWNER_ID`，可能与“可选 user client”的运行语义不完全一致，需按实际部署策略取舍）。

**Telegram（Bot/User Client）**
- `TOKEN`：Bot token（必填）。
- `ID`/`HASH`：Telegram API ID/Hash（必填）。
- `STRING`：User Client session string（可选；空/缺失视为未配置）。
- `OWNER_ID`：所有者 ID（可选，用于权限/提示类逻辑）。

**Web 安全与会话**
- `ADMIN_PASSWORD`：首次初始化 admin 密码（缺省则创建 `admin/admin`，并强制首次改密）。
- `FLASK_SECRET_KEY`：Flask session secret（生产必须显式设置）。
- `SESSION_COOKIE_SECURE` / `SESSION_COOKIE_SAMESITE`：Cookie 安全属性。
- `TZ`：时区（默认 `Asia/Shanghai`，主要影响日志/时间展示）。

**WebDAV / Viewer（可选）**
- `WEBDAV_*`：WebDAV 配置（也可通过 `data/config/webdav_config.json` 管理，Web 后台可写入）。
- `VIEWER_*`：外部 viewer 配置（也可通过 `data/config/viewer_config.json` 管理，Web 后台可写入）。

**CSP/HSTS**
- `CSP_SCRIPT_NONCE` / `CSP_ALLOW_UNSAFE_INLINE` / `CSP_ALLOW_UNSAFE_EVAL`：控制 CSP 的 nonce 与兼容选项（建议逐步收敛 `unsafe-eval` 的覆盖面）。
- `ENABLE_HSTS`：仅 HTTPS 场景启用 HSTS。

**登录限流**
- `LOGIN_RATE_LIMIT_MAX` / `LOGIN_RATE_LIMIT_WINDOW_SECONDS`：登录尝试滑动窗口限流参数。

**队列/背压**
- `MESSAGE_QUEUE_MAXSIZE`：消息队列上限；满时丢弃并记录指标/日志，避免无界内存增长。

**校准（qBittorrent/机器人）**
- `QBT_URL` / `QBT_USERNAME` / `QBT_PASSWORD`：qBittorrent Web API 连接参数（用于 `calibrate_qbt_helper.py`）。
- `CALIBRATE_BOT_USERNAME`：Telegram 校准机器人用户名（用于 `calibrate_bot_helper.py`）。

**可观测性**
- `MONITORING_ENABLED`：总开关。
- `MONITORING_DASHBOARD_ENABLED` / `MONITORING_DASHBOARD_REFRESH_SECONDS` / `MONITORING_DASHBOARD_WINDOW_SECONDS`：仪表盘与刷新窗口。
- `MONITORING_PERSIST_ENABLED` / `MONITORING_PERSIST_BATCH_SIZE` / `MONITORING_DB_RETENTION_DAYS`：持久化与保留策略。
- `SLOW_OPERATION_THRESHOLD_MS` / `SLOW_API_THRESHOLD_MS`：慢操作/慢 API 阈值。
- `DB_MONITORING_ENABLED` / `SLOW_QUERY_THRESHOLD_MS` / `SLOW_QUERY_LOG_QUERY` / `SLOW_QUERY_ALERT_ENABLED`：慢查询追踪与告警。
- `ERROR_TRACKING_ENABLED` / `ERROR_MAX_STACKTRACE_LENGTH` / `ERROR_AGGREGATION_WINDOW_SECONDS` / `ERROR_RETENTION_SECONDS` / `ERROR_TREND_WINDOW_SECONDS` / `ERROR_ALERT_ENABLED`：错误聚合与保留策略。
- `ALERTING_ENABLED` / `ALERT_SUPPRESSION_WINDOW_MINUTES` / `ALERT_MAX_ALERTS_PER_WINDOW` / `ALERT_DEDUP_WINDOW_SECONDS`：告警系统节流与去重。
- `BUSINESS_METRICS_ENABLED` / `BUSINESS_METRICS_REPORT_INTERVAL_SECONDS`：业务指标上报开关与周期。

### 附：Web 路由与 API 速查

**公开端点**
- `/`：根据 session 重定向到 `/notes` 或 `/login`。
- `/health`：健康检查（数据库/配置/存储）。
- `/login`（GET/POST）：登录（带登录限流；POST 受 CSRF 保护）。
- `/logout`：登出（清理 session）。

**页面端点（需登录）**
- `/notes`：笔记列表（分页/过滤/搜索/日期/收藏）。
- `/edit_note/<id>`（GET/POST）：编辑笔记（POST 受 CSRF 保护）。
- `/admin`：管理后台首页（改密、统计）。
- `/admin/webdav`：WebDAV 配置与连通性测试。
- `/admin/viewer`：外部 viewer URL 配置。
- `/admin/calibration`：自动校准配置。
- `/admin/calibration/queue`：校准任务队列。
- `/media/<storage_location>`：媒体访问（本地或 WebDAV 代理，支持 Range）。
- `/monitoring/dashboard` / `/monitoring/`：监控仪表盘。

**JSON API（需登录；非 GET 默认受 CSRF 保护）**
- `/delete_note/<id>`（POST）：删除笔记（JSON）。
- `/toggle_favorite/<id>`（POST）：切换收藏（JSON）。
- `/api/edit_note/<id>`（POST）：编辑笔记（JSON）。
- `/api/calibrate/<note_id>`（POST）：同步校准并更新笔记。
- `/api/calibrate/async`（POST）与 `/api/calibrate/status/<task_id>`（GET）：异步校准提交与轮询。
- `/api/calibrate/batch`（POST）：批量加入自动校准队列。
- `/api/calibration/task/<task_id>/retry`（POST）：手动重试任务。
- `/api/calibration/task/<task_id>/delete`（POST）：删除任务。
- `/monitoring/api/summary`（GET）与 `/monitoring/api/db/recent`（GET）：仪表盘数据接口（内存汇总/SQLite 最近持久化）。

### 附：关键文件索引（便于快速定位）
- 入口：`main.py`、`app.py`、`setup.py`
- Bot：`bot/handlers/auto_forward.py`、`bot/workers/message_worker.py`
- 配置中心：`src/core/config/settings.py`、`src/compat/config_compat.py`
- 配置模型与示例：`src/core/config/models.py`、`.env.example`
- Watch 存储：`src/infrastructure/persistence/repositories/sqlite_watch_repository.py`
- Notes 存储：`src/infrastructure/persistence/repositories/note_repository.py`
- DB 迁移：`src/infrastructure/persistence/sqlite/migrations.py`
- 校准：`bot/services/calibration_manager.py`、`src/application/services/calibration_service.py`
- 媒体：`web/routes/media.py`、`bot/storage/webdav_client.py`
- Web 安全：`web/security/csrf.py`、`web/security/headers.py`、`web/security/rate_limit.py`
- 监控：`src/infrastructure/monitoring/*`、`web/routes/monitoring.py`
- 交付：`docker/entrypoint.sh`、`.github/workflows/ci.yml`
