# Tasks: Objective Progress Tracking, Lifecycle Status & Theme Management

**Input**: Design documents from `/specs/915-objective-progress-tracking/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Mandatory for all ADP features (ART-IV). Test tasks appear before their implementation counterparts in every user-story phase and MUST be verified to fail before implementation begins.

**Organization**: Grouped by user story (spec.md) to enable independent implementation and testing of each.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 / US2 / US3, per spec.md's priorities (P1/P2/P3)

## Path Conventions

Single project, existing directories only — no new package (plan.md's Structure Decision):
- Backend: `src/adp/strategy/{models,store,router}.py`, `src/adp/store/migrations/versions/026_objective_progress_status.py`
- Backend tests: `tests/unit/strategy/`, `tests/contract/test_strategy_api_contract.py`
- Frontend: `web/src/api/strategy.ts`, `web/src/strategy/`

---

## Phase 1: Setup

- [X] T001 [P] Create migration skeleton `src/adp/store/migrations/versions/026_objective_progress_status.py` (revision header, `down_revision = "025"`, empty `upgrade()`/`downgrade()`)
- [X] T002 [P] Create empty test file stub `tests/unit/strategy/test_objective_status.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: No user story work can begin until this phase is complete — every story needs its columns/table to exist and the `status`/`status_reason` fields on the read models.

- [X] T003 Implement migration 026's `upgrade()` in `026_objective_progress_status.py`: `CREATE TABLE strategic_objective_progress` (composite PK `(objective_id, as_of_date)`, FK `objective_id -> strategic_objectives.id ON DELETE CASCADE`, per data-model.md), `ALTER TABLE strategic_themes ADD COLUMN description/owner/priority` + named CHECK on `priority` (research.md Decision 4), `ALTER TABLE strategic_objectives ADD COLUMN status/status_reason` + named CHECK restricting `status` to `NULL` or `'abandoned'` (research.md Decision 2) (depends on T001)
- [X] T004 Implement migration 026's `downgrade()`: drop the three additions in reverse order (depends on T003)
- [X] T005 [P] Add `ObjectiveStatus = Literal["proposed", "active", "at_risk", "achieved", "abandoned"]` to `src/adp/strategy/models.py`
- [X] T006 Extend `StrategicObjective` and `StrategicObjectiveSummary` read models in `src/adp/strategy/models.py` with `status: ObjectiveStatus` and `status_reason: str | None` (depends on T005)
- [X] T007 Run `alembic upgrade head` against local Postgres and confirm `strategic_objective_progress` exists and `strategic_themes`/`strategic_objectives` carry the new columns (depends on T003, T004)

**Checkpoint**: Foundation ready — user story implementation can now begin.

---

## Phase 3: User Story 1 - Record progress and see status update automatically (Priority: P1) 🎯 MVP

**Goal**: An owner records dated actual values against an objective's target; the objective's status (proposed / active / at_risk / achieved) computes itself from that history — never hand-set.

**Independent Test**: Record a sequence of progress entries across several dates for a targeted objective and confirm the displayed status moves through proposed → active/at_risk → achieved correctly as the values change (quickstart.md scenarios 2 and 4).

### Tests for User Story 1 (MANDATORY — ART-IV, write first, confirm failing)

- [X] T008 [P] [US1] Table-driven unit tests for `compute_status()` in `tests/unit/strategy/test_objective_status.py`: no target → `proposed`; zero entries → `proposed`; latest entry at/past target for each `direction` (`increase`/`decrease`/`reach`) → `achieved`; recent entries trending away from target (1, 2, and 3+ available entries) → `at_risk`; recent entries trending toward target → `active`
- [X] T009 [P] [US1] Unit tests for progress store functions in `tests/unit/strategy/test_strategy_store.py`: create succeeds, duplicate `as_of_date` raises a distinguishable error, edit updates `actual_value`/`note` in place without changing `as_of_date`, list returns entries ordered by `as_of_date` ascending, deleting the parent objective removes its progress rows (FR-016)
- [X] T010 [US1] Contract tests for progress endpoints in `tests/contract/test_strategy_api_contract.py`: `POST .../progress` 201/404 (objective)/409 (duplicate date); `GET .../progress` 200/404; `PATCH .../progress/{as_of_date}` 200/404; `GET`/list objective responses now carry a computed `status` field

### Implementation for User Story 1

- [X] T011 [P] [US1] Add `ObjectiveProgressEntry`, `ObjectiveProgressCreate`, `ObjectiveProgressUpdate`, `ObjectiveProgressListResponse` models to `src/adp/strategy/models.py` (data-model.md)
- [X] T012 [US1] Implement `compute_status()` pure function in `src/adp/strategy/store.py` per research.md Decision 1 — make T008 pass
- [X] T013 [US1] Implement `create_progress_entry` (409 on duplicate date), `update_progress_entry`, `list_progress_entries` in `src/adp/strategy/store.py`; wire `compute_status()` into `get_objective`/`list_objectives`/objective-summary reads — make T009 pass (depends on T011, T012)
- [X] T014 [US1] Implement `POST`/`GET /objectives/{id}/progress` and `PATCH /objectives/{id}/progress/{as_of_date}` in `src/adp/strategy/router.py`, with a structured `logger.info(...)` call on create/edit (ART-IX — plan.md Ground-Truth Correction 4, `adp.strategy`'s first logging convention) — make T010 pass (depends on T013)
- [X] T015 [P] [US1] Add `ObjectiveProgressEntry`/`-Create`/`-Update` types and `useObjectiveProgress`/`useCreateProgress`/`useUpdateProgress` hooks to `web/src/api/strategy.ts`; extend `StrategicObjective`/`StrategicObjectiveSummary` TS types with `status`/`status_reason`
- [X] T016 [P] [US1] Create `web/src/strategy/ObjectiveProgressForm.tsx` — record a new dated entry or edit an existing one
- [X] T017 [US1] Wire a status badge, the progress history list, and `ObjectiveProgressForm` into `web/src/strategy/ObjectiveDetail.tsx` (depends on T015, T016)
- [X] T018 [P] [US1] Component tests for `ObjectiveProgressForm.tsx` and the status-badge/history rendering in `ObjectiveDetail.test.tsx`

**Checkpoint**: User Story 1 fully functional and independently testable — quickstart.md scenarios 2, 4, 5.

---

## Phase 4: User Story 2 - Mark an objective as abandoned (Priority: P2)

**Goal**: An owner marks a no-longer-pursued objective abandoned with a required reason; its status honestly reflects that instead of a stale on-track/at-risk read.

**Independent Test**: Abandon any existing objective (with or without progress history) with a reason and confirm its status reads `abandoned` with the reason visible; confirm an abandon attempt with no reason is rejected; confirm nothing can set status to any other value directly (quickstart.md scenario 3).

### Tests for User Story 2 (MANDATORY — ART-IV)

- [X] T019 [P] [US2] Contract tests for `PATCH /objectives/{id}/abandon` in `tests/contract/test_strategy_api_contract.py`: 200 with a reason (status becomes `abandoned`, `status_reason` set), 400 with no reason, 404 unknown objective
- [X] T020 [P] [US2] Unit test in `tests/unit/strategy/test_objective_status.py`: `compute_status()` returns `abandoned` immediately once `status == "abandoned"`, regardless of what the progress trend would otherwise compute (FR-011)

### Implementation for User Story 2

- [X] T021 [P] [US2] Add `AbandonRequest` model (`status_reason: str`, min length 1, no `status` field at all — data-model.md) to `src/adp/strategy/models.py`
- [X] T022 [US2] Implement `abandon_objective` in `src/adp/strategy/store.py`, setting `status`/`status_reason` (depends on T021)
- [X] T023 [US2] Implement `PATCH /objectives/{id}/abandon` in `src/adp/strategy/router.py` with structured logging — make T019 pass (depends on T022)
- [X] T024 [P] [US2] Add `useAbandonObjective` hook to `web/src/api/strategy.ts`
- [X] T025 [US2] Add an "Abandon" action (with a required-reason prompt) to `web/src/strategy/ObjectiveDetail.tsx`, surfacing the reason wherever status is shown (depends on T024)
- [X] T026 [P] [US2] Component test for the abandon action and reason display in `ObjectiveDetail.test.tsx`

**Checkpoint**: User Stories 1 and 2 both independently functional.

---

## Phase 5: User Story 3 - Manage richer theme information (Priority: P3)

**Goal**: A strategy lead gives themes a description, owner, and priority, and can edit or retire one — completing the theme lifecycle (today only create + list exist).

**Independent Test**: Create a theme with description/owner/priority, edit each field, confirm deleting a theme with objectives attached is blocked (409) and deleting an unused one succeeds (204) — quickstart.md scenario 1. Independent of any progress/status work.

### Tests for User Story 3 (MANDATORY — ART-IV)

- [X] T027 [P] [US3] Contract tests in `tests/contract/test_strategy_api_contract.py`: `GET /themes/{id}` 200/404, `PATCH /themes/{id}` 200/404, `DELETE /themes/{id}` 204 (unused)/404/409 (referenced); `POST /themes` accepts optional `description`/`owner`/`priority`
- [X] T028 [P] [US3] Unit tests for theme store functions in `tests/unit/strategy/test_strategy_store.py`: update changes fields, delete succeeds when unreferenced, delete raises a distinguishable error when any objective references the theme

### Implementation for User Story 3

- [X] T029 [P] [US3] Add `StrategicThemeUpdate` model; extend `StrategicTheme`/`StrategicThemeCreate` with `description`/`owner`/`priority` (priority `Field(ge=1, le=5)`) in `src/adp/strategy/models.py`
- [X] T030 [US3] Implement `get_theme`, `update_theme`, `delete_theme` (blocked if referenced) in `src/adp/strategy/store.py` (depends on T029)
- [X] T031 [US3] Implement `GET`/`PATCH`/`DELETE /themes/{id}` in `src/adp/strategy/router.py` with structured logging — make T027 pass (depends on T030)
- [X] T032 [P] [US3] Extend `StrategicTheme` TS type (`description`/`owner`/`priority`) and add `useUpdateTheme`/`useDeleteTheme` hooks in `web/src/api/strategy.ts`
- [X] T033 [US3] Extend `web/src/strategy/ThemeList.tsx`: display/edit description, owner, priority; a delete action that surfaces the 409 "still referenced" message clearly (depends on T032)
- [X] T034 [P] [US3] Component tests for `ThemeList.tsx`'s new fields and actions

**Checkpoint**: All three user stories independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T035 [P] Confirm OpenAPI/schema regeneration is clean with the new endpoints/models (`adp-generate --check` if the target covers `adp.strategy`; otherwise confirm no drift by inspection)
- [X] T036 Run the full regression suite: `pytest tests/ --ignore=tests/integration -q` and `cd web && npx vitest run && npx tsc --noEmit`
- [X] T037 Manually walk through all 5 quickstart.md scenarios against a running local stack (`ADP_AUTH_ENABLED=false`)
- [X] T038 Replace the auto-generated `915-objective-progress-tracking` stub line in CLAUDE.md (and the matching AGENTS.md "Latest work"/"Prior work:" shift) with a proper hand-written narrative at commit time

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS every user story (all three need the migration's columns/table; US1 and US2 both need the `status`/`status_reason` model fields from T006).
- **User Stories (Phase 3–5)**: All depend on Foundational. US2 additionally relies on US1's `compute_status()` (T012) already existing and being extended to recognize `abandoned` (T020) — build US1 before US2. US3 has no dependency on US1 or US2 at all and could be built in parallel with either.
- **Polish (Phase 6)**: Depends on all three user stories being complete.

### Within Each User Story

- Tests written and confirmed failing before implementation (ART-IV).
- Models before store functions; store functions before router endpoints; backend endpoints before frontend hooks; hooks before UI wiring.

### Parallel Opportunities

- T001/T002 (Setup) in parallel.
- T005 in parallel with T001–T004 (different file).
- Within US1: T008/T009 in parallel (different test files); T011 in parallel with T008/T009; T015/T016 in parallel once T014 lands; T018 in parallel with nothing after it (last task in the story).
- Within US2/US3: the same test-then-model-then-store-then-router-then-frontend shape, with `[P]`-marked tasks as annotated above.
- US3's entire phase can run in parallel with US1+US2 by a second developer, since it touches no shared code path beyond the already-complete Foundational phase.

---

## Parallel Example: User Story 1

```bash
# Tests together:
Task: "Table-driven unit tests for compute_status() in tests/unit/strategy/test_objective_status.py"
Task: "Unit tests for progress store functions in tests/unit/strategy/test_strategy_store.py"

# Once tests are red, models + frontend scaffolding together:
Task: "Add ObjectiveProgressEntry/-Create/-Update/-ListResponse models to src/adp/strategy/models.py"
Task: "Add progress types/hooks to web/src/api/strategy.ts"
Task: "Create web/src/strategy/ObjectiveProgressForm.tsx"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 (Setup) → Phase 2 (Foundational) → Phase 3 (US1).
2. **STOP and VALIDATE**: quickstart.md scenarios 2, 4, 5 against a real local stack.
3. This alone answers the spec's central problem statement ("is this objective on track?") — genuinely shippable as an MVP.

### Incremental Delivery

1. Setup + Foundational → schema and shared model fields exist.
2. US1 → record progress, see computed status → demoable.
3. US2 → abandon action → demoable, builds on US1's status framework.
4. US3 → richer themes → demoable, independent of US1/US2.

### Notes

- `[P]` tasks touch different files with no unmet dependency.
- Verify each phase's tests fail before writing its implementation.
- Commit after each task or logical group; stop at any checkpoint to validate a story independently.
