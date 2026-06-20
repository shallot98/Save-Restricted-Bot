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
