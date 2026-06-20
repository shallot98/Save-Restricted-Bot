# brainstorm: refactor architecture hotspots

## Goal

Refactor the codebase according to the latest `archi` full-project architecture report, with emphasis on reducing cyclomatic-complexity hotspots and shrinking overly wide backend components without changing the current folder topology.

## What I already know

* `archi .` reports overall score `65.01`, structure `73.43`, governance/full `56.59`.
* The top five hotspots are `bot/workers/message_worker.py`, `web/routes/api.py`, `bot/handlers/watch_setup.py`, `database.py`, and `src/infrastructure/persistence/sqlite/migrations.py`.
* The dominant issue for all top-five hotspots is `cyclomatic_complexity`.
* Highest-risk components are `bot:handlers` (`91.65`) and `src:infrastructure` (`86.7`), both marked as `wide_component` and `hotspot_concentration`.
* Topology is not the main problem in this snapshot: `needs_folder_management=false`, `0` files to move, `0` folders to create.
* Current working tree is already dirty (`88` uncommitted changes), and all five hotspot files currently have local modifications.
* Current hotspot file sizes are large: `message_worker.py` 1074 lines, `api.py` 810, `watch_setup.py` 468, `database.py` 688, `migrations.py` 532.
* Long functions currently include `MessageWorker.run` (144 lines), `process_message` (106), `_handle_record_mode` (100), `download_note` (87), `batch_calibrate` (80), `complete_watch_setup` (80), `add_note` (87), and `_maybe_migrate_watch_config_from_json` (118).

## Assumptions (temporary)

* This should be treated as a backend-focused refactor, not a directory-reorganization task.
* The refactor should preserve current behavior and API contracts unless explicitly approved otherwise.
* Because all hotspot files are already modified, scope must be selected carefully to avoid high merge/conflict risk.

## Open Questions


## Requirements (evolving)

* Use the architecture report as the prioritization source.
* Scope for this session includes all five reported hotspots: `bot/workers/message_worker.py`, `web/routes/api.py`, `bot/handlers/watch_setup.py`, `database.py`, and `src/infrastructure/persistence/sqlite/migrations.py`.
* Prioritize complexity reduction over folder/layout changes.
* Freeze external contracts strictly: keep current HTTP routes, JSON response fields, bot callback behavior, and database schema unchanged.
* Internal call chains, private helpers, application services, use cases, and repository internals may be reorganized.
* Keep behavior stable unless contract changes are explicitly approved.
* Avoid broad churn across already-dirty files unless the scope justifies it.

## Acceptance Criteria (evolving)

* [x] Selected hotspot scope is explicitly defined as the top-five hotspot files from the architecture report.
* [ ] Refactor reduces complexity in the selected hotspot set.
* [ ] Existing behavior for the selected flows remains intact under strict external compatibility (HTTP routes/JSON, bot callbacks, DB schema unchanged).
* [ ] Relevant verification (tests or targeted checks) passes.

## Definition of Done (team quality bar)

* Tests added/updated (unit/integration where appropriate)
* Lint / typecheck / CI green
* Docs/notes updated if behavior changes
* Rollout/rollback considered if risky

## Technical Approach

* `bot/workers/message_worker.py`: extract message-processing orchestration into application-level worker/use-case collaborators while keeping queue semantics and return statuses (`success` / `skip` / `retry`) unchanged.
* `web/routes/api.py`: keep Flask routes and JSON payloads stable, but move calibration, qBittorrent interaction, and note-update orchestration into application services/use cases.
* `bot/handlers/watch_setup.py`: keep callback flow and rendered bot UX stable, but extract state parsing, duplicate-checking, task creation, and result message composition out of the handler entrypoints.
* `database.py`: preserve exported legacy functions and schema, but move cohesive note-update / calibration-related write logic behind clearer repository-oriented helpers.
* `src/infrastructure/persistence/sqlite/migrations.py`: keep migration behavior stable, but split watch-task migration, JSON import migration, FTS repair/rebuild, and index creation into smaller focused migration steps.

## Decision (ADR-lite)

**Context**: The architecture report shows hotspot concentration across five backend files, with complexity—not topology—as the main issue. The repo already has `src/application/services`, `src/application/use_cases`, and a DI container pattern that can absorb orchestration logic.
**Decision**: Refactor all five reported hotspots using aggressive layer tightening / service extraction, while freezing external contracts strictly.
**Consequences**: The design should become more modular and testable, but verification must focus on compatibility because structural churn is high and the working tree is already dirty.


## Out of Scope (explicit)

* Folder topology reorganization
* Expanding beyond the top-five hotspot files unless required by dependency containment
* Repository-wide rewrite without an explicit scope decision
* Intentional API or data contract changes without approval

## Technical Notes

* Architecture report artifacts: `.architec/architec-summary.md`, `.architec/architec-analysis.json`
* Relevant hotspot files inspected directly in repo.
* `git diff --stat` shows heavy existing edits in several hotspots, especially `bot/workers/message_worker.py` and `web/routes/api.py`.

## Decision (draft)

* Scope chosen: full reported range (top 5 hotspots).


## Research Notes

### Repo constraints and signals

* All five selected hotspot files already have local modifications, so conflict containment matters.
* The strongest architecture signal is complexity, not topology; therefore helper extraction / decision flattening should be prioritized over folder moves.
* `web/routes/api.py`, `database.py`, and `migrations.py` are boundary-heavy files, so contract preservation is important.
* The project guidance that is currently concrete and usable is mainly in `.trellis/spec/guides/code-reuse-thinking-guide.md` and `.trellis/spec/guides/cross-layer-thinking-guide.md`; backend detail guides are still placeholders.

### Feasible approaches here

**Approach A: Conservative in-file extraction**

* How it works: keep the same five files and public entry points, but extract large branches into private helper functions/classes inside the same file or immediately adjacent local helpers.
* Pros: lowest merge risk, easiest to verify, least likely to disturb current contracts.
* Cons: reduces complexity but may not shrink component width as much.

**Approach B: Adjacent module split** (Recommended)

* How it works: keep public APIs/routes/handlers stable, but move cohesive subflows into nearby modules (for example route helpers, watch setup view builders, migration steps, worker operation helpers).
* Pros: reduces file size and function complexity more materially, improves reuse, still preserves outward contracts.
* Cons: larger diff, moderate integration risk because imports and call paths change.

**Approach C: Layer tightening / service extraction** (Chosen)

* How it works: push logic out of routes/handlers/database helpers into new service/use-case layers and rebalance boundaries across components.
* Pros: strongest long-term architecture gain.
* Cons: highest risk, likely crosses contracts, and is less suitable in a dirty working tree.

## Decision (ADR-lite draft)

**Context**: The architecture report identifies cross-file complexity concentration and wide backend components across the top five hotspots.
**Decision**: Use aggressive layer tightening / service extraction for this session rather than only in-file helper extraction.
**Consequences**: This should yield stronger structural improvement, but raises contract and regression risk; explicit compatibility boundaries must be chosen before implementation.

### Existing architecture patterns to reuse

* `src/core/container.py` already exposes lazy singleton accessors such as `get_note_service()`, `get_watch_service()`, and `get_calibration_service()`.
* `src/application/services/` already contains orchestration services (`NoteService`, `WatchService`, `CalibrationService`).
* `src/application/use_cases/` already exists and shows a pattern for extracting focused business flows (`ForwardMessageUseCase`).
* Therefore, new logic should preferentially be extracted into `src/application/services/` or `src/application/use_cases/` instead of creating ad-hoc utility dumps.

## Implementation Plan (small PRs)

* PR1: Establish new application-service / use-case seams and migrate `message_worker.py` + `watch_setup.py` orchestration behind them.
* PR2: Refactor `web/routes/api.py` and `database.py` to preserve outward contracts while moving business flow into application/repository collaborators.
* PR3: Split `migrations.py`, add/adjust targeted tests or compatibility checks, and run lint/type/test verification.
