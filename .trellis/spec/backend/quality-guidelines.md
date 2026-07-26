# Quality Guidelines

> Code quality standards for backend development.

---

## Overview

Backend service and worker code should keep public call sites stable while moving bulky parameter sets into explicit request/options/context objects. This project has many long-lived handlers and tests that still call service methods with legacy positional or keyword arguments, so signature cleanup must preserve those paths unless the caller set is updated in the same change.

---

## Scenario: Request Object Compatibility

### 1. Scope / Trigger

- Trigger: a function or method exceeds 5 business parameters, or carries a repeated group such as filters, runtime options, cache query fields, or persistence record fields.
- Applies to backend service, worker, cache, monitoring, and callback-helper code under `bot/`, `src/`, `web/`, and `scripts/`.
- Do not use this pattern for framework-required external callback signatures unless the helper is internal to the project.

### 2. Signatures

Preferred shape:

```python
@dataclass(frozen=True)
class ExampleCreateRequest:
    user_id: str
    source_id: str
    dest_id: str | None = None


def create_item(
    request: ExampleCreateRequest | str | None = None,
    *legacy_args: Any,
    **legacy_fields: Any,
) -> Item:
    request = example_create_request(request, legacy_args, legacy_fields)
    ...
```

For options-only APIs:

```python
@dataclass(frozen=True)
class ExampleOptions:
    enabled: bool = True
    batch_size: int = 200


def run_task(options: ExampleOptions | None = None, **legacy_options: Any) -> None:
    options = example_options(options, legacy_options)
    ...
```

### 3. Contracts

- Request/options/context dataclasses must be `frozen=True`.
- New code should call the request/options/context form.
- Existing callers using legacy positional or keyword arguments must keep working until intentionally migrated.
- If a request/options object is provided together with legacy fields, raise `TypeError`.
- If an unknown legacy keyword is provided, raise `TypeError`; do not silently ignore it.
- Parser helpers should live close to the service or in a focused `*_requests.py` module when keeping them inline would push a file above 300 lines.

### 4. Validation & Error Matrix

| Case | Required behavior |
| --- | --- |
| Request object only | Use it directly |
| Legacy keyword fields only | Convert to the request/options object |
| Legacy positional fields only | Convert using a named field list |
| Request object plus legacy fields | Raise `TypeError` |
| Missing required legacy field | Raise `TypeError` from parser or dataclass construction |
| Unknown legacy keyword | Raise `TypeError` naming the unknown key |

### 5. Good/Base/Bad Cases

Good:

```python
request = WatchTaskCreateRequest(user_id="1", source_id="-100", dest_id="-200")
service.add_watch_task(request)
```

Base compatibility:

```python
service.add_watch_task(user_id="1", source_id="-100", dest_id="-200")
```

Bad:

```python
service.add_watch_task(request, source_id="-100")
```

### 6. Tests Required

- Run `python -m compileall -q` for changed backend modules.
- Run unit tests covering both the new object path and the legacy path when the old call style is externally visible.
- For cache/service compatibility changes, include the relevant unit tests, for example:
  - `tests/unit/test_cache_interface.py`
  - `tests/unit/test_message_worker_service.py`
  - `tests/unit/test_watch_setup_service.py`
  - `tests/unit/test_history_copy_task_manager.py`

### 7. Wrong vs Correct

#### Wrong

```python
def cache_note_list(query: NoteListCacheQuery, notes: list[dict]) -> None:
    ...
```

This breaks existing calls such as `cache_note_list(user_id=1, source="channel", search=None, page=1, notes=notes)`.

#### Correct

```python
def cache_note_list(
    query: NoteListCacheQuery | int | None = None,
    *legacy_args: Any,
    notes: Any = _UNSET,
    ttl: float | None = None,
    **legacy_fields: Any,
) -> None:
    query, notes = _note_list_cache_write(query, legacy_args, notes, legacy_fields)
    ...
```

---

## Forbidden Patterns

- Do not add mock or fake success paths to satisfy tests.
- Do not swallow unknown legacy keyword arguments.
- Do not move business logic into compatibility parsers; parsers should only normalize input shape.

---

## Required Patterns

- Keep request/options/context objects immutable with `frozen=True`.
- Keep parser helpers deterministic and side-effect free.
- Prefer explicit field-name tuples for legacy positional parsing.
- Keep runtime verification as the source of truth; compile and unit tests must pass after compatibility changes.

---

## Testing Requirements

- Backend unit tests must run with `timeout 60`.
- At minimum, run targeted tests for touched behavior before the full unit suite.
- Final backend verification should include:

```bash
/tmp/save-restricted-bot-venv/bin/python -m compileall -q main.py app.py database.py config.py constants.py bot src web scripts
timeout 60 /tmp/save-restricted-bot-venv/bin/python -m pytest tests/unit
```

---

## Code Review Checklist

- New object-style APIs preserve documented legacy call paths.
- Parser helpers reject mixed request and legacy fields.
- Unknown legacy fields fail explicitly.
- No changed runtime file exceeds 300 lines and no changed function exceeds 50 lines.
- Tests prove both object and legacy paths when both are supported.

---

## Test Isolation: 禁止触碰生产配置与数据（2026-07-26 教训）

背景：`SQLiteWatchRepository._sync_to_json` 在**方法体内**惰性 `from src.core.config import settings`，模块级 monkeypatch 拦不住，单测运行时把测试夹具整体覆盖写入了生产 `data/config/watch_config.json`（真实任务丢失，事后从 `data/notes.db` 权威后端恢复）。

规则：

- 任何测试不得读写 `data/` 下的真实文件；涉及仓储/配置的测试必须注入临时路径或拦截落盘入口。
- `tests/unit/conftest.py` 已有 autouse fixture 拦截 `settings.save_watch_config`（保留 payload 供断言）——新增落盘入口时必须同步扩展该 fixture。
- 生产代码新增「函数内延迟 import 全局单例」会绕过测试替身，属债务信号（同 §5.3 禁止函数内 import 规避循环依赖），评审时重点看。
- 双写镜像（SQLite → JSON 全量覆盖）是本次事故根因，报告 §6.2 Q2 待产品确认后应降级只读或删除，不要再加同类整体覆盖式落盘。

维护提示：测试环境 venv 路径会变（/tmp 定期清空），当前可用环境见 memory `srb-test-venv-path`；上文 `/tmp/save-restricted-bot-venv` 为历史路径，以实际存在者为准。

---

## 门禁脚本必须防「假绿」（2026-07-26 教训 #2）

背景：`scripts/check_mypy_baseline.py` 只解析带行号的错误行。mypy 因模块重名等原因以退出码 2 夭折时，输出一行无行号错误 → 解析结果「当前 0 / 新增 0」→ 门禁 exit 0。叠加 CI 的 `|| true`，完整复现了架构报告 P1-2 记录的「类型检查自诞生起从未检查过一行代码」。

规则：

- 任何「比对式门禁」（基线 diff、覆盖率阈值、契约检查）必须先验证**被度量的工具跑完了完整一轮**（如 mypy 的收尾统计行），跑不完就 fail，而不是把空输出当零错误。
- 门禁脚本本身要有单测钉住三种场景：正常通过 / 工具夭折 / 空输入（后两者必须非 0 退出）。参见 `tests/unit/test_mypy_baseline_gate.py`。
- CI 步骤里对门禁上游命令使用 `|| true` 时，必须确保下游校验器能区分「无错误」与「没跑」。

## 依赖方向契约（Phase 2 起生效）

- `.importlinter` 4 条契约在 CI error 级：src 不得 import bot/web/根模块；src 不得 import composition；core/domain 为最内层；层序 web → bot → src.application → src.domain。
- 新代码如需跨层，先看 `src/core/interfaces/` 有无端口可复用，装配一律进 `composition/`（wiring 在启动期调用，不在 import 期）。
- 已知豁免仅 1 条（`src.compat.config_compat → composition.container`，Phase 3 随 compat 删除）。新增豁免需在 `.importlinter` 内注释理由。

---

## 依赖注入约定（Phase 3 起生效，2026-07-26）

- 表现层（bot/web）不得 `from composition.container import get_xxx()`：bot 经 `BotServices` DTO（`composition/bot_runtime.py` 构建）注入 handler/worker；web 经 `WebServices` + `create_app(*, services)`（必填，无默认值——有测试钉住）注入路由。
- application 层缓存/指标走 `src/core/interfaces/`（NoteCache/ConfigCache/BusinessMetricsRecorder/ErrorTracker 端口），装配唯一入口是 `composition/`。启动序固定为「先 `configure_runtime_implementations()` 后构造服务」。
- `src/compat` 已整包删除且有防复活断言（`test_compat_package_is_gone`）；根 `config.py/constants.py/database.py` 是仅存的薄外观（Phase 4 删除目标），新代码禁止 import 它们。
- import-linter 契约（`.importlinter`）零豁免：`composition → web → bot → (src.application | src.infrastructure) → src.domain`。注意 layers 语法陷阱：`|` 才是独立兄弟层，`:` 是允许互相 import 的同层（与直觉相反，配置内有注释）。
- web 测试模式：fake services + `WebInfrastructure` 注入缝建 app（参考 `tests/unit/web_route_fakes.py`），不真建库不连 WebDAV。
