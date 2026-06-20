## Relevant Specs
- `.trellis/spec/backend/index.md`: backend guideline index required by workflow.
- `.trellis/spec/backend/database-guidelines.md`: relevant because scope includes `database.py` and sqlite migrations, though content is still placeholder.
- `.trellis/spec/backend/error-handling.md`: relevant because routes/worker/database all expose or translate errors; actual repo convention must be inferred from code.
- `.trellis/spec/backend/logging-guidelines.md`: relevant because worker/routes/database/migrations emit logs and refactor must preserve observability.
- `.trellis/spec/backend/quality-guidelines.md`: general backend quality checklist, currently placeholder.
- `.trellis/spec/guides/cross-layer-thinking-guide.md`: concrete guidance for API ↔ service ↔ repository ↔ storage boundaries in this task.
- `.trellis/spec/guides/code-reuse-thinking-guide.md`: concrete guidance because refactor will extract shared orchestration instead of duplicating logic.

## Code-Spec Depth Check
- External contracts frozen: HTTP routes, JSON response fields, bot callback behavior, and DB schema must remain unchanged.
- No new public API signatures or schema changes are planned.
- Validation/error matrix to preserve:
  - API invalid input -> current 400/404/500 patterns remain unchanged.
  - Worker processing -> `success` / `skip` / `retry` semantics remain unchanged.
  - Watch setup -> duplicate-task and invalid-source/dest behaviors remain unchanged.
  - DB note calibration updates -> same return booleans and concurrency retry semantics remain unchanged.
- Good/Base/Bad cases to verify:
  - Good: normal note/message/watch flow still succeeds.
  - Base: duplicate watch/note remains handled as before.
  - Bad: invalid input / missing note / invalid peer still returns existing failure mode.

## Code Patterns Found
- Dependency injection via container: `src/core/container.py` exposes lazy service accessors and is the preferred seam for new orchestration.
- Application orchestration pattern: `src/application/services/note_service.py`, `watch_service.py`, `calibration_service.py` already own business flow above repositories.
- Focused use-case extraction pattern: `src/application/use_cases/forward_message.py` shows a small single-purpose orchestration class.
- Legacy compatibility wrapper pattern: `database.py` coexists with `src/infrastructure/persistence/repositories/*`; compatibility can be preserved while delegating internals.
- Watch config persistence pattern: `src/infrastructure/persistence/repositories/watch_repository.py` and `src/application/services/watch_service.py` already support `get_all_configs_dict()` / `save_config_dict()`.

## Files to Modify
- `bot/workers/message_worker.py`: slim worker orchestration; delegate record/forward/media decision flows.
- `web/routes/api.py`: slim route handlers; delegate calibration/download orchestration.
- `bot/handlers/watch_setup.py`: slim bot handler entrypoints; delegate watch setup orchestration/message composition.
- `database.py`: preserve exports while delegating note/calibration persistence logic into clearer helpers/repositories.
- `src/infrastructure/persistence/sqlite/migrations.py`: split migration steps into focused helpers.
- `src/application/services/` and/or `src/application/use_cases/`: new orchestration modules for worker/api/watch setup flows.
- Possibly `src/core/container.py`: register newly extracted service(s) if needed.
