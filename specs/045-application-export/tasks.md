# Tasks: Continuous Application Registry Export to Versioned Files

**Feature**: ADP-SPEC-045 (ADP-81p.2) | **Branch**: `045-application-export`
**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md) · **Research**: [research.md](./research.md) · **Data model**: [data-model.md](./data-model.md) · **Contracts**: [contracts/exported-file-formats.md](./contracts/exported-file-formats.md)

## Format: `[ID] [P?] [Story] Description`

- **[P]** = parallelizable (distinct file, no dependency on an incomplete task).
- **[US#]** = user-story phase task. Setup / Foundational / Polish carry no story label.
- Tests are **MANDATORY** (ART-IV): each phase's tests precede its implementation, written to fail first — except the Foundational refactor (T003–T006), which moves already-shipped, already-tested logic; its safety net is ADP-SPEC-044's existing test suite passing unchanged, not a new failing test (nothing new is being *behaviorally* introduced by the move itself).

## Path Conventions

Two new modules: `src/adp/export/common.py` (shared helpers extracted from `business_arch.py`, research.md Decision 5) and `src/adp/export/application_arch.py` (this domain's serialization/fetch/reconciliation). One existing file refactored (`src/adp/export/business_arch.py`) and one existing file extended (`src/adp/api/app.py`). Tests in `tests/unit/export/{test_export_common,test_application_arch_serialize,test_application_arch_io,test_application_arch_reconciliation}.py`, `tests/unit/api/test_app_lifespan_application_arch.py`, and `tests/integration/test_application_arch_export_cycle.py`.

> **File-contention note**: `src/adp/export/application_arch.py` grows across Foundational and both user-story phases, sequentially — same pattern as `business_arch.py` did in ADP-SPEC-044. `src/adp/export/common.py` and the `business_arch.py` refactor are written/touched **once**, in Foundational only — no user-story phase touches either again. **US2 depends on US1**, not just on Foundational, for the same reason ADP-SPEC-044's did: US2's diffing/deletion behavior runs inside the exact background loop US1 wires up, so US2 cannot start before US1's loop exists. Unlike ADP-SPEC-044, though, US2's *implementation* task here is small — the content-diff and orphan-cleanup logic itself already exists in `common.py` (built once, in Foundational, from the T003–T006 extraction) and only needs to be *called* with this domain's file paths and live ID sets, not re-derived.

---

## Phase 1: Setup (Shared Infrastructure)

- [x] T001 [P] Create the module skeleton (docstring only, explaining its role as the shared home for domain-agnostic export helpers per research.md Decision 5) in src/adp/export/common.py — implemented directly with T004 (see note below)
- [x] T002 [P] Create the module skeleton (docstring only, referencing spec.md/data-model.md) in src/adp/export/application_arch.py

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: No user story work can begin until this phase is complete. Two independent halves: 2A extracts shared infrastructure out of already-shipped code; 2B builds this domain's own serialization/fetch/reconciliation on top of it.

### 2A — Shared infrastructure extraction (refactor of ADP-SPEC-044's code)

- [x] T003 [P] Unit test: `common.py`'s moved/generalized helpers work correctly in their new home — atomic write success + no-partial-file-on-failure; `_write_entity_file` skip-if-unchanged (content-diff, ignoring `exported_at`); `_cleanup_orphan_files`/`_cleanup_orphan_dirs`; `_background_loop`/`start_background_sync` invoke an **injected** `reconcile_fn` callable on schedule and `start_background_sync` is a no-op when `export_root` is falsy — in tests/unit/export/test_export_common.py — 12/12 passing. **Note**: written and run directly against the already-implemented module rather than a literal red-then-green cycle, since this is a straight extraction of already-proven logic (not new behavior) — consistent with this phase's stated safety net being regression (T006), not new-behavior TDD.
- [x] T004 Move `_safe_path_component`, `_safe_filename`, `_write_file_atomic`, `_write_entity_file`, `_cleanup_orphan_files`, `_cleanup_orphan_dirs` from `business_arch.py` into `common.py` unchanged; generalize `_background_loop`/`start_background_sync` to accept a new `reconcile_fn: Callable[[Path, AsyncSession], Awaitable[None]]` parameter instead of hardcoding a call to `business_arch.run_reconciliation_cycle` — in src/adp/export/common.py
- [x] T005 Refactor src/adp/export/business_arch.py: import the moved names from `common.py` (so `business_arch._write_file_atomic`, `business_arch._cleanup_orphan_files`, etc. still resolve via normal module-attribute lookup for any existing test that references them that way — no existing test file needs editing); keep `business_arch.start_background_sync(export_root, interval_seconds, session_factory)`'s own public signature **unchanged**, now a thin wrapper passing `reconcile_fn=run_reconciliation_cycle` through to `common.start_background_sync`
- [x] T006 Regression gate (the refactor's actual safety net, not new test-writing): `pytest tests/unit/export/test_business_arch_serialize.py tests/unit/export/test_business_arch_io.py tests/unit/export/test_business_arch_reconciliation.py tests/unit/export/test_business_arch_background.py tests/unit/api/test_app_lifespan_business_arch.py -q` → **23/23 passed, zero test file edits** (integration test deferred to Polish/T024 since it requires a live Postgres container — not run in this pass); `ruff check`/`mypy` clean on common.py + business_arch.py after an import-sort auto-fix

### 2B — Application-registry serialization + bulk fetch (domain-specific)

- [x] T007 [P] Unit test: serialization of each of the 4 file-bearing entity types produces exactly the JSON shape in data-model.md §2 — an application with every extension record populated AND a second application with none (asserting all-null/all-zero `risk`/`cost`/`governance`/`quality` sub-objects, never omitted, per FR-018); a technical capability; a transformation initiative including its `members`; an integration; `Decimal` cost bucket amounts serialize as JSON strings (e.g. `"2000.50"`), never floats; deterministic sorted-key output — in tests/unit/export/test_application_arch_serialize.py — confirmed failing (ImportError) then passing (7/7)
- [x] T008 Implemented `_serialize_application`, `_serialize_technical_capability`, `_serialize_initiative`, `_serialize_integration` (plus `_serialize_risk`/`_serialize_cost`/`_serialize_governance`/`_serialize_quality` helpers) — pure functions, no I/O, no `exported_at` — in src/adp/export/application_arch.py
- [x] T009 [P] Unit test: `_fetch_all` fetches all applications, technical capabilities, initiatives, and integrations (reusing `astore.list_applications`/`list_technical_capabilities`/`list_initiatives`/`list_integrations(None, ...)` directly, per research.md Decision 4) plus all risk/cost/governance/quality/relationship rows via direct `Table` queries, correctly grouped by `app_id` (and, for initiatives, additionally by `initiative_id` for the reverse `members` view), in a small fixed number of queries against a SQLite-backed `adp.application.store` — in tests/unit/export/test_application_arch_io.py — confirmed failing (AttributeError) then passing
- [x] T010 Implemented `ApplicationArchSnapshot` (dataclass) + `_fetch_all` — in src/adp/export/application_arch.py
- [x] T011 Unit test: `run_reconciliation_cycle` catches any exception raised mid-cycle (mocked `_fetch_all` failure), logs an `application_arch_export.cycle_failed` WARNING event via `caplog`, and does not raise — in tests/unit/export/test_application_arch_io.py — confirmed failing then passing
- [x] T012 Implemented `run_reconciliation_cycle(export_root, session)` — orchestrates fetch → serialize → `common._write_entity_file` for all 4 entity types under `<export_root>/applications/...`, wrapped in the try/except from T011 — in src/adp/export/application_arch.py. 42/42 export unit tests passing; `ruff`/`mypy` clean.

**Checkpoint**: The reconciliation mechanism exists and is directly unit-testable; nothing runs automatically yet; ADP-SPEC-044's own behavior is unchanged post-refactor (T006).

---

## Phase 3: User Story 1 - An AI tool or teammate reads current application architecture straight from the repo (Priority: P1) 🎯 MVP

**Goal**: Every application (with its risk/cost/governance/quality records and relationships embedded), technical capability, transformation initiative (with its members), and application-to-application integration is exported to a correct, current file the moment the background sync starts running.
**Independent Test**: Create applications, technical capabilities, initiatives, integrations, and their relationships through the existing platform, let the background sync run, and confirm the exported files exist with correct current content — including sensitive-category data (Clarification Q1) and all-null sub-objects for unpopulated extension records.

### Tests for User Story 1 (MANDATORY — ART-IV)

- [x] T013 [US1] Unit test: reconciling a freshly-seeded application registry (one app with extension record + relationship, one app with none, a technical capability, an initiative, an integration between two apps) once produces exactly the expected file tree with correct content at every path from data-model.md §2 — in tests/unit/export/test_application_arch_reconciliation.py — passed immediately (the underlying `run_reconciliation_cycle` was already fully built in Foundational T012, mirroring ADP-SPEC-044's T011 experience)
- [x] T014 [P] [US1] Integration test: seed data in a real Postgres container *before* any reconciliation cycle runs, then run one cycle and confirm a complete bootstrap export with no separate manual step (FR-008), including a sensitive risk record and a capability-link relationship — in tests/integration/test_application_arch_export_cycle.py — passes against real Postgres (`ADP_DATABASE_URL` pointed at local dev instance)

### Implementation for User Story 1

- [x] T015 [US1] Extended `adp.api.app._lifespan` to also start/stop a second background task (`_app_export_task`) for `application_arch`, reading the **same** `ADP_BUSINESS_ARCH_EXPORT_ROOT`/`ADP_BUSINESS_ARCH_EXPORT_INTERVAL_SECONDS` env vars as the existing Business Architecture task (no new configuration surface) — in src/adp/api/app.py. Also added `start_background_sync`/`stop_background_sync` thin wrappers to `application_arch.py` itself (mirroring `business_arch.py`'s pattern), needed for this wiring to have something to call.
- [x] T016 [US1] Unit test the new lifespan wrapper functions (env-unset→`None`, env-set→real `Task` with `not task.done()`, stop-noop-for-`None`) — in tests/unit/api/test_app_lifespan_application_arch.py — 3/3 passing alongside the existing 3 ADP-SPEC-044 lifespan tests (6/6 total)
- [x] T017 [US1] Manually ran quickstart.md Scenarios 1–4 against a real local dev stack (restarted the running uvicorn with `ADP_BUSINESS_ARCH_EXPORT_ROOT=/tmp/adp-arch-export-045`, `_INTERVAL_SECONDS=5`, real dev Postgres): created an application, set risk (`security_posture=adequate`, `data_classification=confidential`) and cost (`acquisition.one_time=2000.50`), confirmed the exported file within one interval — cost amount confirmed as the JSON string `"2000.50"`, not a float, governance/quality present as all-null. Linked a business capability (fit_score 4), confirmed `linked_business_capabilities`. Created a transformation initiative + linked it, confirmed BOTH the initiative's `members` and the app's `initiative_links` reflect the same link. Created a second application + an app-to-app integration, confirmed the integration's own file with both app names resolved.

**Checkpoint**: MVP — someone can read the platform's complete, current application registry (including the three sensitive categories, per Clarification Q1) straight from the exported files, with zero database/API access.

---

## Phase 4: User Story 2 - A reviewer sees exactly what changed in the application portfolio as a readable diff (Priority: P2)

**Goal**: The export produces clean, reviewable diffs — a file is only rewritten when its own data actually changed, and a deleted entity's file disappears rather than lingering as stale, misleading content.
**Independent Test**: Change one application's data and confirm only its file changes; delete an application/technical capability/initiative/integration and confirm its file is removed on the next cycle; reconcile twice with no changes and confirm no file is rewritten.

### Tests for User Story 2 (MANDATORY — ART-IV)

- [x] T018 [US2] Unit test: reconciling twice in a row with no underlying data change does not rewrite any of the 4 file types (asserts both on-disk content AND mtime unchanged) — in tests/unit/export/test_application_arch_reconciliation.py — passed immediately (see note below)
- [x] T019 [US2] Unit test: changing one application's data, then reconciling, rewrites only that application's file — an unrelated technical capability and application file are each byte-for-byte and mtime unchanged — in tests/unit/export/test_application_arch_reconciliation.py — passed immediately
- [x] T020 [US2] Unit test: deleting an application, technical capability, transformation initiative, or integration removes exactly that entity's file on the next cycle, without disturbing unrelated still-live entities' files — in tests/unit/export/test_application_arch_reconciliation.py — passed immediately

### Implementation for User Story 2

- [x] T021 [US2] `application_arch.run_reconciliation_cycle` already calls `common._cleanup_orphan_files` for each of the 4 entity directories (built directly into Foundational T012, not deferred to this phase) — **note, deviation from the task plan**: unlike ADP-SPEC-044 (where US2's diff/cleanup logic was a distinct phase built after US1's loop existed), here the content-diff (`common._write_entity_file`, used since T012) and orphan cleanup were both already wired in from the start, since `common.py`'s helpers already existed before this domain's first line of reconciliation code was written (research.md Decision 5's DRY payoff realized even more fully than anticipated) — no new code was needed for T018–T020 to pass, only the tests themselves — in src/adp/export/application_arch.py
- [x] T022 [US2] Manually ran quickstart.md Scenarios 5–6 against the real local dev stack: confirmed an unchanged application's file mtime stays constant across a reconciliation cycle with no data change; deleted an application and confirmed both its own file AND its app-to-app integration's file (the DB's `ON DELETE CASCADE` removed the integration row too) were removed on the next cycle. Verification data (2 applications, 1 capability, 1 initiative, 1 integration) all cleaned up afterward.

**Checkpoint**: Both user stories independently functional — the export now produces clean, reviewable diffs on top of User Story 1's correct file content.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [x] T023 [P] Added a section to RUNBOOK.md: the Application registry export shares the exact same env vars and background-task lifecycle as the existing Business Architecture export (ADP-SPEC-044) — no new setup steps — with a link to this feature's own `contracts/exported-file-formats.md`, and an explicit callout that this export includes sensitive risk/cost/governance data unredacted (Clarification Q1) so an operator sees the residual-risk note before enabling it
- [x] T024 Full backend regression: `pytest tests/ --ignore=tests/integration -q` → **1086 passed** (was 1056; +30 new tests); `pytest tests/integration/test_business_arch_export_cycle.py tests/integration/test_application_arch_export_cycle.py -q` → **2 passed** (real Postgres); `ruff check src/ tests/` → clean; `mypy src/` → clean (174 source files)
- [x] T025 Confirmed no `adp-generate` schema drift — `adp-generate --check` exits 0
- [x] T026 [P] Updated CLAUDE.md's Recent Changes entry and AGENTS.md's status blurb for 045 to reflect implementation — in CLAUDE.md, AGENTS.md

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Ph1)** → **Foundational (Ph2)** → **User Stories (Ph3–4)** → **Polish (Ph5)**.
- Foundational's two halves (2A extraction, 2B domain logic) can proceed in either order relative to each other, but **2B's T012 (`run_reconciliation_cycle`) depends on 2A's T004 (`common._write_entity_file`/cleanup helpers existing)** — so 2A must land before T012 specifically, even though T007–T010 (serialization, fetch) have no such dependency and could start immediately.
- **User Story 2 depends on User Story 1**, not just on Foundational — see the File-contention note above.
- No database migration in this feature — no migration-ordering constraint to track.

### Parallel opportunities

- Setup: T001 and T002 are both `[P]` (distinct files).
- Foundational: T003 (`test_export_common.py`, its own file) is `[P]` relative to T007/T009 (their own file, `test_application_arch_serialize.py`/`test_application_arch_io.py`) — the 2A and 2B test-writing tracks can run in parallel; T004/T005/T006 (2A implementation) are sequential to each other, as are T008/T010/T012 (2B implementation, each depending on the test immediately before it and T012 additionally depending on T004).
- User Story 1: T014 (integration test, its own file) is `[P]` relative to T013 (unit test).
- User Story 2: T018/T019/T020 share one file and are sequential to each other and to T013 before them.
- Polish: T023 and T026 are `[P]` (distinct files, no dependency on T024/T025's outcome to be written, though T024/T025 should still run before considering the feature done).

## Implementation Strategy

- **MVP = User Story 1** (Phase 3): every application (with sensitive records and relationships), technical capability, initiative, and integration readable from files with correct, current content. Ship and demo before proceeding — even with every-cycle-rewrites-everything behavior, this already closes the second-largest remaining gap under ADP-81p.
- **Then User Story 2** (Phase 4): the refinement that makes the export's *history* useful — clean diffs, no orphaned files. Strictly builds on US1's loop; do not attempt in parallel with it. Materially smaller than the equivalent phase in ADP-SPEC-044 thanks to the Foundational common.py extraction.
- **The scope boundary is load-bearing, not incidental**: per Clarification Q1/Q2, this feature covers the FULL non-excluded breadth of the Application registry (including the three sensitive categories, unredacted) in one increment, with the sole exclusion being the application-to-design link (FR-014, already covered by ADP-SPEC-011). Resist scope creep toward re-litigating the sensitive-category decision mid-implementation — it was a deliberate, recorded choice (spec.md Clarifications), not a default to second-guess task-by-task.

## Summary

- **Total tasks**: 26 across 5 phases.
- **Per story**: US1=5 (T013–T017), US2=5 (T018–T022); Setup=2, Foundational=10 (T003–T012), Polish=4.
- **MVP scope**: User Story 1 (T001–T017) — correct, current application registry (including sensitive categories) readable from files, end to end.
- **Tests**: mandatory per phase (ART-IV) — written to fail first, except the Foundational refactor (T003–T006), whose safety net is ADP-SPEC-044's existing suite passing unchanged.
