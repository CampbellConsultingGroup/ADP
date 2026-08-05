# Tasks: Continuous Business Architecture Export to Versioned Files

**Feature**: ADP-SPEC-044 (ADP-81p.1) | **Branch**: `044-business-arch-export`
**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md) · **Research**: [research.md](./research.md) · **Data model**: [data-model.md](./data-model.md) · **Contracts**: [contracts/exported-file-formats.md](./contracts/exported-file-formats.md)

## Format: `[ID] [P?] [Story] Description`

- **[P]** = parallelizable (distinct file, no dependency on an incomplete task).
- **[US#]** = user-story phase task. Setup / Foundational / Polish carry no story label.
- Tests are **MANDATORY** (ART-IV): each phase's tests precede its implementation, written to fail first.

## Path Conventions

Everything lives in one new module, `src/adp/export/business_arch.py`, plus one wiring change to `src/adp/api/app.py`. Tests in `tests/unit/export/{test_business_arch_serialize,test_business_arch_io,test_business_arch_reconciliation}.py` and `tests/integration/test_business_arch_export_cycle.py`.

> **File-contention note**: `src/adp/export/business_arch.py` grows across every phase (Foundational builds the pure helpers, US1 wires them into a running loop, US2 adds diffing/deletion on top of that same loop) — sequential, not `[P]`, across phases, exactly like `adp.business.agent_review.py` grew across ADP-SPEC-039's four stories. `tests/unit/export/test_business_arch_io.py` similarly accumulates three related test groups (atomic write, bulk read, failure isolation) within Foundational and is therefore internally sequential too — only `test_business_arch_serialize.py` (a distinct file) is genuinely parallel to it. US1 and US2 are **not** independent of each other the way, say, two different suggestion types were in ADP-SPEC-039: US2's diffing/deletion logic runs inside the exact loop US1 creates, so US2 cannot start before US1's loop exists — this is called out explicitly because it's a real, load-bearing dependency, not an artifact of file layout.

---

## Phase 1: Setup (Shared Infrastructure)

- [x] T001 [P] Document `ADP_BUSINESS_ARCH_EXPORT_ROOT` (unset = feature disabled) and `ADP_BUSINESS_ARCH_EXPORT_INTERVAL_SECONDS` (default 60) in .env.example
- [x] T002 [P] Create the module skeleton (docstring, `_safe_filename()` path-safety helper per the Threat Model's path-traversal mitigation) in src/adp/export/business_arch.py

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: No user story work can begin until this phase is complete — both stories build on the same serialization, atomic-write, bulk-read, and failure-isolation primitives.

- [x] T003 Unit test: each of the 4 serialization functions produces exactly the JSON shape in data-model.md §2 — nullable fields (`domain_id`, `strategic_relevance`, `maturity_level`) present as explicit `null` (never omitted), `linked_capability_ids` sorted and `[]` (never omitted) when empty, deterministic sorted-key output so two calls over identical input produce byte-identical text — in tests/unit/export/test_business_arch_serialize.py — confirmed failing (functions didn't exist) then passing (7/7)
- [x] T004 Implemented `_serialize_capability`, `_serialize_domain`, `_serialize_value_stream`, `_serialize_stage` — pure functions, no I/O. **Refinement from the task description**: `exported_at` is stamped separately at write time (`_write_entity_file`, T006/T010), not by these functions themselves — keeping the serialize functions' output exactly the comparable "data portion" that research.md Decision 2's content-diffing needs, with no timestamp noise to strip out later — in src/adp/export/business_arch.py
- [x] T005 [P] Unit test: `_write_file_atomic(path, content)` writes via temp-file-then-`os.replace`, and a simulated failure mid-write (mock `os.replace` to raise) leaves no partial file and does not corrupt any pre-existing file at that path — in tests/unit/export/test_business_arch_io.py — confirmed failing then passing
- [x] T006 Implemented `_write_file_atomic` — in src/adp/export/business_arch.py
- [x] T007 Unit test: `_fetch_all` fetches all capabilities, domains, value streams, and stages-with-linked-capability-ids in a small fixed number of queries against a SQLite-backed `adp.business.store` — in tests/unit/export/test_business_arch_io.py — confirmed failing then passing
- [x] T008 Implemented `BusinessArchSnapshot` + `_fetch_all` — reuses `bstore.list_capabilities`/`list_domains_full`/`list_value_streams` (existing functions, not reinvented) plus direct unfiltered reads of `bstore._stages`/`_stage_caps` (no existing function lists stages across every value stream at once) — in src/adp/export/business_arch.py
- [x] T009 Unit test: `run_reconciliation_cycle` catches any exception raised mid-cycle (mocked `_fetch_all` failure), logs a `business_arch_export.cycle_failed` WARNING event via `caplog`, and does not raise — in tests/unit/export/test_business_arch_io.py — confirmed failing then passing
- [x] T010 Implemented `run_reconciliation_cycle(export_root, session)` — orchestrates fetch → serialize → `_write_entity_file` (stamps `exported_at`) for all 4 entity types, wrapped in the try/except from T009 — in src/adp/export/business_arch.py. 12/12 tests pass across both foundational test files; `ruff`/`mypy` clean.

**Checkpoint**: The reconciliation mechanism exists and is directly unit-testable; nothing runs automatically yet.

---

## Phase 3: User Story 1 - An AI tool or teammate reads current business architecture straight from the repo (Priority: P1) 🎯 MVP

**Goal**: Every business capability, value stream, value stream stage (with linked capabilities), and business domain is exported to a correct, current file the moment the background sync starts running — readable with zero database/API access.
**Independent Test**: Create capabilities/value-streams/stages/domains through the existing platform, let the background sync run, and confirm the exported files exist with correct current content (including unclassified fields as explicit `null`).

### Tests for User Story 1 (MANDATORY — ART-IV)

- [x] T011 [US1] Unit test: reconciling a freshly-seeded business architecture (capabilities including one unclassified, a domain, a value stream with a linked-capability stage) once produces exactly the expected file tree with correct content at every path from data-model.md §2 — in tests/unit/export/test_business_arch_reconciliation.py — passed immediately (the underlying `run_reconciliation_cycle` was already fully built in Foundational T010; this test is what actually proves it end to end rather than just via mocks)
- [x] T012 [P] [US1] Integration test: seed data in a real Postgres container *before* any reconciliation cycle runs, then run one cycle and confirm a complete bootstrap export with no separate manual step (FR-008) — in tests/integration/test_business_arch_export_cycle.py — passes against a real Postgres container

### Implementation for User Story 1

- [x] T013 [US1] `start_background_sync(export_root, interval_seconds, session_factory)` / `stop_background_sync(task)` — an `asyncio` task looping `run_reconciliation_cycle` on the configured interval; `start_background_sync` is a no-op (returns `None`, no task created) when `export_root` is falsy; the caller owns the returned `Task` (no module-global state) — in src/adp/export/business_arch.py — 3 tests added (tests/unit/export/test_business_arch_background.py), all passing
- [x] T014 [US1] Wired `start_business_arch_export()`/`stop_business_arch_export()` (thin env-var-reading wrappers around T013, using `bstore._get_session_factory()`) into `adp.api.app._lifespan`, alongside the existing stale-operations-cleanup task — in src/adp/api/app.py. 3 tests added (tests/unit/api/test_app_lifespan_business_arch.py), all passing (3 consecutive runs, no flakiness); full backend suite 1032/1032 passing; `ruff`/`mypy` clean
- [x] T015 [US1] Manually ran quickstart.md Scenario 1 (bootstrap) and Scenario 5 (stage-capability links) against a real local dev stack (`ADP_BUSINESS_ARCH_EXPORT_ROOT`/`_INTERVAL_SECONDS=5` set, real uvicorn + real dev Postgres): created a capability via the API, confirmed its file appeared within one interval with all fields (including `null` unclassified fields) correct; created a value stream + stage + second capability, linked them, confirmed the stage's file showed `linked_capability_ids` correctly. Verification data cleaned up afterward.

**Checkpoint**: MVP — someone can read the platform's complete, current business architecture straight from the exported files, with zero database/API access. (Every cycle still rewrites every file, and deleted entities' files aren't yet cleaned up — that's User Story 2.)

---

## Phase 4: User Story 2 - A reviewer sees exactly what changed in business architecture as a readable diff (Priority: P2)

**Goal**: The export produces clean, reviewable diffs — a file is only rewritten when its own data actually changed, and a deleted entity's file disappears rather than lingering as stale, misleading content.
**Independent Test**: Change one capability's classification and confirm only its file changes; delete a capability/value-stream/stage/domain and confirm its file is removed on the next cycle; reconcile twice with no changes and confirm no file is rewritten.

### Tests for User Story 2 (MANDATORY — ART-IV)

- [x] T016 [US2] Unit test: reconciling twice in a row with no underlying data change does not rewrite any file (asserts both on-disk content AND mtime are unchanged after the second cycle) — in tests/unit/export/test_business_arch_reconciliation.py — confirmed failing then passing
- [x] T017 [US2] Unit test: changing one capability's `maturity_level`, then reconciling, rewrites only that capability's file — every other already-written file (an unrelated capability, the domain) is byte-for-byte unchanged AND has an unchanged mtime — in tests/unit/export/test_business_arch_reconciliation.py — confirmed failing then passing
- [x] T018 [US2] Unit test: deleting a capability, a domain, and a stage each removes exactly that entity's file (an un-deleted capability is untouched); a separate test confirms deleting a value stream removes its whole directory (`value-stream.json` plus its `stages/` subtree) in one step, per data-model.md §3 step 5 — in tests/unit/export/test_business_arch_reconciliation.py — confirmed failing then passing

### Implementation for User Story 2

- [x] T019 [US2] Added content-comparison-before-write to `_write_entity_file` — reads the current on-disk file (if any), strips `exported_at` from both sides, and skips the write entirely (no `_write_file_atomic` call, no mtime change) if they match — in src/adp/export/business_arch.py
- [x] T020 [US2] Added `_cleanup_orphan_files` (capabilities, domains, and each still-live value stream's own stages) and `_cleanup_orphan_dirs` (a whole deleted value stream's directory removed in one step) — in src/adp/export/business_arch.py. 20/20 export tests pass; `ruff`/`mypy` clean.
- [x] T021 [US2] Manually ran quickstart.md Scenarios 2, 3, 4, and 6 against a real local dev stack. **Found and fixed a real quickstart.md documentation bug along the way**: Scenario 2 used `PATCH` for the capability update endpoint, which is actually `PUT` (405 Method Not Allowed) — not a bug in the feature itself (confirmed via a direct GET that the PATCH attempt never touched the DB at all), but a wrong example in the doc; corrected to `PUT` and re-verified successfully. Also verified recovery: after Scenario 6's induced failure (chmod 000 the export root) and restoring permissions, the next scheduled cycle picked back up and exported a newly-created capability normally — the background loop survives a transient failure, not just logs it once and stops.

**Checkpoint**: Both user stories independently functional — the export now produces clean, reviewable diffs on top of User Story 1's correct file content.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [x] T022 [P] Documented the two new environment variables in RUNBOOK.md's "Starting the stack → Backend API" section, alongside the existing optional `ADP_AUTH_ENABLED`/Keycloak exports, plus a short note on what the export produces and where to find the file-format contract
- [x] T023 Full backend regression: `pytest tests/ --ignore=tests/integration -q` → **1039 passed**; `pytest tests/integration/test_business_arch_export_cycle.py tests/integration/test_migration_023.py` → **2 passed** (real Postgres container); `ruff check src/ tests/` → clean; `mypy src/` → clean. **Drive-by fix**: found and fixed 7 pre-existing `ruff` violations (import sorting + 3 long lines) in three already-merged ADP-SPEC-042 test files — these were never actually caught by CI last session because the `pytest` step failed first (on the unrelated `test_knowledge_api.py` issue, ADP-s3j) and short-circuited the job before the `ruff` step ever ran; left in place, this PR's own CI would have shown an unrelated `ruff` failure. Out of scope for 044 itself but small, mechanical, and confusing to leave broken.
- [x] T024 Confirmed no `adp-generate` schema drift — `adp-generate --check` exits 0
- [x] T025 [P] Updated CLAUDE.md's Recent Changes entry and AGENTS.md's Project Status ("Latest work") for 044 to reflect implementation (both user stories, all verification results) — in CLAUDE.md, AGENTS.md

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Ph1)** → **Foundational (Ph2)** → **User Stories (Ph3–4)** → **Polish (Ph5)**.
- Foundational (T003–T010) blocks both stories — neither story has anything to build on without the serialization/write/read/failure-isolation primitives.
- **User Story 2 depends on User Story 1**, not just on Foundational — see the File-contention note above. This is the one place in this feature where stories are not independently orderable (US2 cannot start before US1's background loop exists), even though each story remains independently *testable* and independently *valuable* once reached.
- No database migration in this feature — no migration-ordering constraint to track.

### Parallel opportunities

- Setup: T001 and T002 are both `[P]` (distinct files).
- Foundational: T003 (own file) is `[P]` relative to the T005/T007/T009 group (all in `test_business_arch_io.py`, sequential to each other); the T004/T006/T008/T010 implementation tasks are inherently sequential (each depends on the test immediately before it, and T010 depends on all three helpers).
- User Story 1: T012 (integration test, its own file) is `[P]` relative to T011 (unit test).
- User Story 2: T016/T017/T018 share one file and are sequential to each other and to T011 before them.
- Polish: T022 and T025 are `[P]` (distinct files, no dependency on T023/T024's outcome to be written, though T023/T024 should still run before considering the feature done).

## Implementation Strategy

- **MVP = User Story 1** (Phase 3): every business capability, value stream, stage, and domain readable from files with correct, current content. Ship and demo before proceeding — even with every-cycle-rewrites-everything behavior, this already closes the ADP-81p gap this feature exists to address.
- **Then User Story 2** (Phase 4): the refinement that makes the export's *history* (not just its current snapshot) actually useful — clean diffs, no orphaned files. Strictly builds on US1's loop; do not attempt in parallel with it.
- **The scope boundary is load-bearing, not incidental**: this feature deliberately stops at business capabilities/value-streams/stages/domains (plus the one stage↔capability link) and explicitly excludes applications and the two design-linking join tables (spec.md Assumptions) — resist scope creep back toward "just add applications too" without a fresh spec increment under ADP-81p, per that epic's own stated "one domain at a time" philosophy.

## Summary

- **Total tasks**: 25 across 5 phases.
- **Per story**: US1=5, US2=6; Setup=2, Foundational=8, Polish=4.
- **MVP scope**: User Story 1 (T001–T015) — correct, current business architecture readable from files, end to end.
- **Tests**: mandatory per phase (ART-IV) — written to fail first; Foundational's own helper-level tests (T003, T005, T007, T009) precede their implementations exactly as the user-story tests do.
