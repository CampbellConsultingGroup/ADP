# Tasks: Regulatory Framework Tags for Application Risk & Compliance

**Input**: Design documents from `/specs/932-regulatory-framework-tags/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓, quickstart.md ✓

**Tests**: Mandatory (ART-IV, per `.specify/templates/tasks-template.md`). Test tasks appear before
their implementation counterparts in every user-story phase and must be written and verified to
fail first.

**Organization**: Tasks grouped by user story (US1 = tag an application, P1, MVP; US2 = display the
real framework name, P2; US3 = a deleted framework never leaves a broken tag, P3). All three share
one table (`application_framework_tags`) and the read-only `regulatory_frameworks` mirror
(Foundational phase) — a single simple link, like 927's own `theme_framework_links`, not disjoint
per-story tables. US3 is almost entirely verification: the `ON DELETE CASCADE` FK built in Phase 1
does the actual work, matching 927's own precedent where cascade-delete was proven only by a
Docker-gated integration test, never a SQLite contract test (SQLite doesn't enforce FK/CASCADE
without pragmas this project's fixtures don't set).

**Scope note**: Full-stack (backend + frontend) — unlike 927, this feature's spec explicitly
describes UI interaction ("the picker", "the Risk & Compliance tab") as part of every user story,
so `web/` files are in scope for US1/US2. No framework→application reverse-lookup endpoint is
built (research.md D7) — out of scope, filed as a follow-on if wanted.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 / US2 / US3, per spec.md's priorities (P1/P2/P3)

## Path Conventions

Single project (existing monorepo), existing packages/files only except one new migration and new
test files — no new package (plan.md Structure Decision):
- Backend: `src/adp/application/{models,store,router}.py` (all exist, extended); one new migration
  `src/adp/store/migrations/versions/041_application_framework_tags.py`
- Backend tests: `tests/unit/application/test_application_risk_framework_tags.py` (new),
  `tests/contract/test_apm_risk_api.py` (exists, extended),
  `tests/integration/test_application_framework_tags.py` (new, Docker-gated)
- Export fixtures (no production code change): `tests/unit/export/test_application_arch_*.py`,
  `tests/integration/test_application_arch_export_cycle.py` (exist, fixtures updated)
- Frontend: `web/src/api/compliance.ts` (exists, extended), `web/src/application/RiskPanel.tsx`
  (exists, extended), `web/src/application/RiskPanel.test.tsx` (new)

---

## Phase 1: Setup (Migration)

**Purpose**: Database schema every user story depends on.

- [X] T001 Create Alembic migration `src/adp/store/migrations/versions/041_application_framework_tags.py` (`revision = "041"`, `down_revision = "040"`): `upgrade()` creates table `application_framework_tags` per data-model.md — `application_id` VARCHAR(36) FK→`applications.id` ON DELETE CASCADE (part of composite PK), `framework_id` VARCHAR(36) FK→`regulatory_frameworks.id` ON DELETE CASCADE (part of composite PK), `created_at` TIMESTAMPTZ NOT NULL server_default now(); creates index `ix_aft_framework_id` on `framework_id`; drops column `application_risk.regulatory_tags` (research.md D6). `downgrade()` re-adds `application_risk.regulatory_tags` as a nullable JSON column, drops the index, drops the table.

**Checkpoint**: Migration applies cleanly (`alembic upgrade head` then `alembic downgrade -1` then `alembic upgrade head` again).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The read-only `regulatory_frameworks` mirror, the new link table object, and the
shared diff/validate helpers every user story's logic calls.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 [P] In `src/adp/application/store.py` (extends this package's existing cross-domain mirror idiom — none existed here before this feature, so this transplants `adp.strategy.store`'s `_regulatory_frameworks`/`framework_exists` precedent verbatim, research.md D1): add `_regulatory_frameworks` read-only mirror `sa.Table("regulatory_frameworks", _metadata, sa.Column("id", sa.String(36), primary_key=True), sa.Column("name", sa.Text(), nullable=False), sa.Column("status", sa.Text(), nullable=False))`; add `class UnknownFrameworkError(Exception)` and `class FrameworkNotSelectableError(Exception)` (mirrors `DuplicateLinkError`/`LinkNotFoundError`'s precedent of small, purpose-named exception classes); add `async def _framework_record(framework_id: str, session: AsyncSession) -> dict | None` returning `{"id", "name", "status"}` or `None` if not found.
- [X] T003 [P] In `src/adp/application/store.py`: add `_application_framework_tags` DML-only `sa.Table("application_framework_tags", _metadata, sa.Column("application_id", sa.String(36), nullable=False), sa.Column("framework_id", sa.String(36), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))` — no Python-level PK/FK, matching this package's existing table-definition convention; constraints live in T001's migration. Add `async def _linked_framework_ids(app_id: str, session: AsyncSession) -> list[str]`: `SELECT framework_id FROM application_framework_tags WHERE application_id = ? ORDER BY framework_id`.
- [X] T004 [P] Unit tests in `tests/unit/application/test_application_risk_framework_tags.py` for T002/T003, against a seeded SQLite fixture (mirrors `tests/unit/strategy/test_theme_framework_links.py`'s own `astore._metadata.create_all()`-style setup, extended to also create the new mirror + link tables, seeding one `in_force`, one `amended`, and one `repealed` framework row): `_framework_record()` returns the right dict for each seeded id and `None` for an unknown id; `_linked_framework_ids()` returns `[]` for an application with no tags.

**Checkpoint**: Mirror table, link table object, and the shared read helpers available; unit tests pass.

---

## Phase 3: User Story 1 - Tag an application with real regulatory frameworks (Priority: P1) 🎯 MVP

**Goal**: A user with write access can select zero or more `in_force`/`amended` regulatory
frameworks for an application from a governed picker, replacing free-text entry; an unknown or
newly-selected non-selectable framework id is rejected outright; duplicates are structurally
impossible; the selection persists and survives reload.

**Independent Test**: Open an application's Risk & Compliance tab, select frameworks from the
picker, save, reload, confirm the same frameworks are shown as selected (spec.md US1 Acceptance
Scenarios 1–3; quickstart.md Scenarios 1, 2, 3, 4, 7, 8).

### Tests for User Story 1 (write first — ART-IV)

- [X] T005 [P] [US1] Extend `tests/contract/test_apm_risk_api.py`: update the fixture to also `create_all` the two new tables from T002/T003 and seed two `in_force` frameworks (`FRM-1`, `FRM-2`) plus one `repealed` framework (`FRM-3`) directly into the `_regulatory_frameworks` mirror (mirrors `tests/contract/test_theme_framework_links_api.py`'s seeding convention); update the two existing tests that currently PUT `regulatory_tags: ["SOX", "GDPR"]` to instead use `["FRM-1", "FRM-2"]`; add new tests: PUT with an unknown id → 422, whole write rejected; PUT with `FRM-1` plus a duplicate `FRM-1` in the same list → 200, persisted exactly once; PUT replacing `[FRM-1, FRM-2]` with just `[FRM-2]` → only `FRM-2` remains; PUT with `[]` after having tags → `regulatory_tags == []`; PUT including `FRM-3` (repealed) as a **newly-added** id → 422, and `FRM-1` in the same request is *not* partially saved.
- [X] T006 [P] [US1] Unit tests in `tests/unit/application/test_application_risk_framework_tags.py` (same file as T004) for the reconciliation logic in isolation: diffing a submitted set against the currently-linked set correctly separates "newly added" from "already present"; an already-linked id is never re-validated against its current `status` (the Edge Case — seed it `in_force`, link it, flip its mirror row to `repealed`, re-submit the same full set unchanged, confirm no exception is raised and the link survives).

### Implementation for User Story 1

- [X] T007 [US1] In `src/adp/application/store.py`: rewrite `_row_to_risk` to no longer read a `regulatory_tags` column (removed in T001) — accept the already-fetched linked-id list as a parameter instead, populating `ApplicationRisk.regulatory_tags` from it; rewrite `upsert_application_risk` to (a) de-duplicate the submitted `body.regulatory_tags` list, (b) fetch the currently-linked set via `_linked_framework_ids`, (c) diff: ids only in the new set are "to add", ids only in the old set are "to remove", (d) for each "to add" id call `_framework_record`; raise `UnknownFrameworkError` if `None`, raise `FrameworkNotSelectableError` if `status not in ("in_force", "amended")`; only after every "to add" id passes, (e) in one transaction: `DELETE` the "to remove" rows from `application_framework_tags`, `INSERT` the "to add" rows, then upsert the rest of the risk record exactly as today, then re-read the linked set and return via `_row_to_risk` (depends on T002, T003).
- [X] T008 [US1] In `src/adp/application/router.py`: catch `UnknownFrameworkError`/`FrameworkNotSelectableError` from `put_application_risk` and raise `HTTPException(422, ...)` with a message naming the offending framework id and reason (depends on T007).
- [X] T009 [P] [US1] In `web/src/api/compliance.ts`: add `status: "in_force" | "amended" | "repealed" | "not_yet_applicable";` to the `RegulatoryFramework` interface (the one field missing from this pre-existing, otherwise-complete 926-era type, research.md D8).
- [X] T010 [US1] In `web/src/application/RiskPanel.tsx`: replace the free-text "Regulatory Tags" `<input>` with a checkbox list sourced from `useFrameworks()` (from `../api/compliance`), filtered to `status === "in_force" || status === "amended"`; local state becomes `selectedFrameworkIds: string[]` initialized from `risk.regulatory_tags` on load; on Save, submit `regulatory_tags: selectedFrameworkIds` in the existing batched `ApplicationRiskUpdate` body exactly as today (no new save button, no new endpoint — depends on T009).
- [X] T011 [P] [US1] New `web/src/application/RiskPanel.test.tsx`: picker renders one checkbox per `in_force`/`amended` framework from a mocked `useFrameworks()`, excludes `repealed`/`not_yet_applicable` ones; toggling checkboxes and clicking Save calls the update mutation with the expected `regulatory_tags` array; an application loaded with a pre-existing selection shows the matching checkboxes pre-checked.

**Checkpoint**: User Story 1 fully functional and independently testable — an application can be tagged with real, validated frameworks and the selection survives reload.

---

## Phase 4: User Story 2 - See which real regulation a tag refers to (Priority: P2)

**Goal**: Every displayed tag shows the framework's real name, with enough detail to disambiguate
two frameworks that happen to share a name.

**Independent Test**: View an application tagged with a known framework and confirm its real name
(not a raw id) is shown; seed two frameworks with the same name and confirm both render
distinguishably (spec.md US2 Acceptance Scenarios 1–2; quickstart.md Scenario 8).

### Tests for User Story 2 (write first — ART-IV)

- [X] T012 [P] [US2] Extend `web/src/application/RiskPanel.test.tsx`: a checked framework renders its `name` (not its id); given two mocked frameworks sharing the same `name` but different `jurisdiction`/`version`, both render with distinguishing text visible (not just the bare shared name twice).

### Implementation for User Story 2

- [X] T013 [US2] In `web/src/application/RiskPanel.tsx`: render each selected framework's label as its `name`, appending `" (" + jurisdiction + ", " + version + ")"` whenever another framework in the same `useFrameworks()` result shares its `name` (depends on T010 — `name`/`jurisdiction`/`version` are already present on the frontend `RegulatoryFramework` type, no further type change needed per research.md D8).

**Checkpoint**: User Stories 1 and 2 both work independently — tags are both selectable and unambiguously identifiable.

---

## Phase 5: User Story 3 - A deleted framework never leaves a broken tag behind (Priority: P3)

**Goal**: Deleting a `RegulatoryFramework` automatically removes it from every application that had
it tagged.

**Independent Test**: Tag an application with a framework, delete that framework via the real
Compliance API, reopen the application's Risk & Compliance tab and confirm the tag is gone and
nothing is broken (spec.md US3 Acceptance Scenario 1; quickstart.md Scenario 6).

### Tests for User Story 3 (write first — ART-IV)

- [X] T014 [US3] New `tests/integration/test_application_framework_tags.py` (Docker-gated via `testcontainers`, mirrors `tests/integration/test_theme_framework_links_api.py`'s fixture exactly — real Postgres, both `adp.application.router` and `adp.compliance.router` mounted against the same `db_url`): `test_delete_framework_cascades_the_tag` — create a real Application and a real Framework via their actual APIs, PUT the tag, delete the Framework via `DELETE /api/v1/compliance/frameworks/{id}`, GET the application's risk and confirm the id is absent; `test_delete_application_cascades_the_tag` — same setup, delete the Application instead, confirm the row is gone (no orphaned FK, confirmed via a direct row-count query since there's no "get a deleted application's risk" endpoint to call).

**Checkpoint**: All three user stories independently functional. The cascade itself was already structurally guaranteed by T001's `ON DELETE CASCADE`; this phase's task is verification against a real database, matching 927's own precedent that this specific class of behavior is never trustworthy from a SQLite contract fixture alone.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Keep already-existing consumers and quality gates in sync; no new user-facing behavior.

- [X] T015 [P] Update `tests/unit/export/test_application_arch_serialize.py`, `tests/unit/export/test_application_arch_reconciliation.py`, `tests/unit/export/test_application_arch_io.py`, and `tests/integration/test_application_arch_export_cycle.py`: replace fixture values like `regulatory_tags=["PCI"]` with a real seeded framework id. **Ground-Truth Correction found while doing this task, not anticipated by research.md D8 as originally written**: three of these files `.insert().values(..., regulatory_tags=...)` directly against `astore._application_risk`, which fails outright now that the column is dropped (T001) — fixed by removing the kwarg from those inserts and, for the one file that asserts a non-empty tag, seeding `_regulatory_frameworks` + `_application_framework_tags` directly instead. Separately, `adp.export.application_arch._fetch_all`'s own bulk-fetch path called `astore._row_to_risk(row)` directly against a raw `_application_risk` row (bypassing `get_application_risk`'s join) — this broke the moment `_row_to_risk` gained a required second parameter (T007); fixed with one additional bulk query grouping `_application_framework_tags` by `app_id`, preserving `_fetch_all`'s own stated no-N+1 invariant (research.md D8, revised).
- [X] T016 [P] Run `ruff check src/`, `mypy src/`, and `cd web && npx tsc --noEmit` across every file touched by T001–T015; fix any reported issue.
- [X] T017 Run every scenario in `quickstart.md` (1–7 via `curl` against a local dev stack, Scenario 8 via a live Playwright walkthrough) and confirm each matches its stated expectation; clean up any scratch data created.
- [X] T018 Append a dated entry to `CLAUDE.md`'s "Recent Changes" section summarizing this feature (bead ADP-bkg), following the established format of the entries immediately above it.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Phase 1 (needs the real tables to exist for its own tests' `create_all`, though the Python table *objects* in T002/T003 can be written before T001 lands — the unit tests in T004 are what actually require the migration's shape to be final). BLOCKS all user stories.
- **User Stories (Phase 3+)**: All depend on Foundational phase completion.
  - US1 (P1) can start immediately after Phase 2.
  - US2 (P2) depends on US1's T010 (it extends the same `RiskPanel.tsx` rendering code) — not independent at the file level, though independently *testable* once US1 has landed.
  - US3 (P3) depends only on Phase 1 (the FK) and the existence of a real Application + Framework + tag to delete — independent of US1/US2's frontend work, can proceed in parallel with Phase 4.
- **Polish (Phase 6)**: Depends on all desired user stories being complete.

### Parallel Opportunities

- T002 and T003 (different concerns, same file — safe to co-author but not literally concurrent edits; treat as sequential-in-practice despite the `[P]` marker reflecting "no logical dependency between them").
- T005 and T006 (different files) in parallel.
- T009 and T011 (different files) can be drafted in parallel with T007/T008 (backend); T010 depends on T009 landing first.
- T015 and T016 in parallel; both depend on Phases 3–5 being complete.
- US3 (Phase 5) can proceed in parallel with Phase 4 (US2) once Phase 3 (US1) is done, since neither touches the other's files.

---

## Parallel Example: User Story 1

```bash
# Launch both test tasks for User Story 1 together:
Task: "Extend tests/contract/test_apm_risk_api.py per T005"
Task: "Add reconciliation unit tests to tests/unit/application/test_application_risk_framework_tags.py per T006"

# Backend and frontend type work can proceed in parallel once tests are red:
Task: "Rewrite store.py reconciliation logic per T007"
Task: "Add status field to web/src/api/compliance.ts per T009"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (migration).
2. Complete Phase 2: Foundational (mirror table, link table, shared helpers).
3. Complete Phase 3: User Story 1.
4. **STOP and VALIDATE**: Run quickstart.md Scenarios 1–4, 7, 8 (US1-relevant subset) independently.
5. Deploy/demo if ready — tags are already real and validated, even before US2's name-resolution polish lands.

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. US1 → test independently → deploy/demo (MVP — frameworks are selectable and persisted, shown by id if US2 hasn't landed yet).
3. US2 → test independently → deploy/demo (tags now show real names, disambiguated).
4. US3 → test independently → deploy/demo (deletion safety confirmed against real Postgres).
5. Polish → export fixtures, lint/type gates, full quickstart pass, changelog entry.

---

## Notes

- [P] tasks = different files, no dependency on an incomplete task.
- [Story] label maps task to specific user story for traceability.
- Verify every test in T005/T006/T012/T014 fails before its corresponding implementation task lands.
- Commit after each task or logical group.
- No new `ActionType`, no `PERMISSIONS_VERSION` bump, no new endpoint anywhere in this task list
  (research.md D1/D2/D4) — every task extends an existing route, table, or component.
