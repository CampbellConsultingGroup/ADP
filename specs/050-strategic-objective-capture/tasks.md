# Tasks: Capture Strategic Objectives

**Input**: Design documents from `/specs/050-strategic-objective-capture/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/strategy-api.md, quickstart.md

**Tests**: Tests are MANDATORY for all ADP features (ART-IV). Test tasks appear before their implementation counterparts in every phase and MUST be confirmed to fail before implementation begins.

**Organization**: Three independently-testable user stories (create an objective, link it to capabilities/value streams, browse/edit/delete) on top of a shared Foundational phase (migration, Pydantic models, package scaffolding) all three need.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- File paths are exact and relative to the repo root

---

## Phase 1: Setup

**Purpose**: Confirm the plan's assumptions still hold against the live repo before editing.

- [x] T001 Confirm `src/adp/business/store.py`'s `get_capability(cap_id, session)`/`get_value_stream(vs_id, session)` still exist with those exact signatures (research.md Decision 2's premise); confirm `src/adp/business/router.py`'s `_require_write_business_arch(user)` helper pattern is still current (research.md Decision 3's premise); confirm `web/src/business/DesignLinkEditor.tsx`'s filtered-dropdown structure is still current (research.md Decision 4's premise); confirm `024` is still the latest applied migration. No file changes — read-only; stop and re-plan if any premise has drifted.

**Checkpoint**: Plan's file-level assumptions reconfirmed — safe to proceed.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The migration, typed models, and package scaffolding every user story needs before any CRUD function can exist.

**⚠️ CRITICAL**: No user story's store/router functions can be written until the tables and Pydantic models they operate on exist.

- [x] T002 Create `src/adp/store/migrations/versions/025_strategic_objectives.py` (`down_revision="024"`) — all 4 tables per data-model.md: `strategic_themes`, `strategic_objectives` (with the `direction`/`period` `CHECK` constraints), `strategic_objective_capabilities`, `strategic_objective_value_streams` (both join tables mirroring migration 008's exact shape — composite PK, `ON DELETE CASCADE` both legs, one index each, `created_at`).
- [x] T003 Run `alembic upgrade head` against real dev Postgres — verify all 4 tables and their constraints exist as specified, matching this project's established migration-verification convention (no dedicated pytest for schema creation itself, per specs 046/048/049's own precedent).
- [x] T004 [P] Create `tests/unit/strategy/__init__.py` and `tests/unit/strategy/test_strategy_models.py` (new) — failing tests for `src/adp/strategy/models.py`: `StrategicObjectiveCreate` rejects a blank `owner`/`statement`; rejects a partially-filled metric group (e.g. `metric_name` set but `target_unit` missing — data-model.md's all-or-nothing rule); accepts a fully-populated metric group; accepts no metric group at all (all four fields absent); rejects an invalid `direction`/`period` value outside the `Literal` sets. Confirm all fail (the module doesn't exist yet).
- [x] T005 Create `src/adp/strategy/__init__.py` and `src/adp/strategy/models.py` — `ObjectiveDirection`, `ObjectivePeriod` (`Literal` type aliases per data-model.md), `StrategicTheme`, `StrategicThemeCreate`, `StrategicObjective`, `StrategicObjectiveCreate`, `StrategicObjectiveUpdate` (all fields optional), `StrategicObjectiveSummary`, `StrategicObjectiveListResponse` — all `extra="forbid"`, with the all-or-nothing metric-group validator. Run T004 and confirm it passes.
- [x] T006 Create `src/adp/strategy/store.py` (SQLAlchemy Core `Table()` definitions for all 4 tables, matching `adp.business.store`'s own metadata/table-definition convention, plus a module-level session-factory seam mirroring `adp.diagrams.store`'s established pattern) and `src/adp/strategy/router.py` (`APIRouter(prefix="/api/v1/strategy", tags=["strategy"])` skeleton, `_require_write_business_arch(user)` helper mirrored from `adp.business.router`, no endpoints yet). Register the router in `src/adp/api/app.py`. No dedicated test for pure scaffolding — each user story's own contract tests exercise it once endpoints exist (T009, T019, T027 below).
- [x] T007 Run `pytest tests/unit/strategy/ -q` and `cd web && npx tsc --noEmit` — confirm the Foundational phase alone is clean, zero regressions.

**Checkpoint**: Tables exist, models are typed and validated in isolation, the package/router skeleton is registered — no user story's actual behavior exists yet.

---

## Phase 3: User Story 1 - Capture a new strategic objective (Priority: P1) 🎯 MVP

**Goal**: An architect can create a strategic theme (if none exist yet) and a strategic objective with its core fields, and read it back with every field discrete and typed.

**Independent Test**: Create a theme, then an objective referencing it with all fields filled in; reload; confirm every field reads back exactly as entered as separate, typed values — not concatenated text (spec.md's own Independent Test for this story).

### Tests for User Story 1 (MANDATORY — ART-IV)

- [x] T008 [P] [US1] Create `tests/unit/strategy/test_strategy_store.py` (new) — failing tests: `create_theme` + `get_theme`/`list_themes` round-trip; `create_objective` (with and without the optional metric group) + `get_objective` round-trip, confirming every field (including `theme_id`, `fiscal_year`, `period`) reads back unchanged. Confirm all fail (`store.py` has no CRUD functions yet).
- [x] T009 [P] [US1] Create `tests/contract/test_strategy_api_contract.py` (new) — failing tests: `POST /api/v1/strategy/themes` → 201; `POST .../themes` with a duplicate name → 409; `GET /api/v1/strategy/themes` lists it; `POST /api/v1/strategy/objectives` with all core fields → 201 with every field present in the response; `POST .../objectives` with blank `owner`/`statement` → 422 (spec.md Acceptance Scenario 2); `GET /api/v1/strategy/objectives/{id}` reads it back. Confirm all fail (no endpoints exist yet).

### Implementation for User Story 1

- [x] T010 [US1] In `src/adp/strategy/store.py`: implement `create_theme`, `get_theme`, `list_themes`, `create_objective`, `get_objective`. Run T008 and confirm it passes.
- [x] T011 [US1] In `src/adp/strategy/router.py`: implement `POST/GET /themes`, `POST /objectives`, `GET /objectives/{id}`, gated by `_require_write_business_arch` on the two POSTs. Run T009 and confirm it passes.
- [x] T012 [US1] Run `pytest tests/unit/strategy/ tests/contract/test_strategy_api_contract.py -q` — confirm all green.
- [x] T013 [P] [US1] Create `web/src/api/strategy.test.ts` (new) — failing tests for new hooks in `web/src/api/strategy.ts` (mirroring `web/src/api/business.ts`'s existing hook-testing conventions where present, or `web/src/api/chat.test.ts`'s `fetch`-mocking convention otherwise): `useCreateTheme`, `useThemes`, `useCreateObjective` each call the expected endpoint with the expected body. Confirm all fail (the module doesn't exist yet).
- [x] T014 [US1] Create `web/src/api/strategy.ts` — typed interfaces (`StrategicTheme`, `StrategicObjective`, etc., matching `models.py`) and `useCreateTheme`/`useThemes`/`useCreateObjective` hooks via `apiGet`/`apiMutation` (mirroring `web/src/api/business.ts`'s established convention exactly). Run T013 and confirm it passes.
- [x] T015 [P] [US1] Create `web/src/strategy/ThemeList.test.tsx` and `web/src/strategy/ObjectiveForm.test.tsx` (new) — failing tests: `ThemeList` renders existing themes and supports creating a new one (mirrors `DomainList.tsx`'s convention); `ObjectiveForm` rejects submission with a blank owner/statement, and submits a fully-populated metric group correctly when provided. Confirm all fail (neither component exists yet).
- [x] T016 [US1] Create `web/src/strategy/ThemeList.tsx` (mirrors `DomainList.tsx`) and `web/src/strategy/ObjectiveForm.tsx` (core fields: theme select, owner, statement, optional metric/target/unit/direction group, fiscal year + period). Run T015 and confirm it passes.
- [x] T017 [US1] Run `cd web && npx vitest run src/api/strategy.test.ts src/strategy/ThemeList.test.tsx src/strategy/ObjectiveForm.test.tsx && npx tsc --noEmit` — confirm all green, zero regressions.

**Checkpoint**: User Story 1 fully functional and independently testable — themes and objectives can be created and read back with every field discrete and typed. Shippable MVP increment.

---

## Phase 4: User Story 2 - Link an objective to capabilities and value streams (Priority: P2)

**Goal**: An architect can link a saved objective to real business capabilities and value streams (never free text), and remove a link without affecting the underlying record.

**Independent Test**: Open a saved objective, link it to an existing capability and an existing value stream, reload, confirm both persist and reference the real records; attempt to link a nonexistent id and confirm it's rejected (spec.md's own Independent Test for this story).

### Tests for User Story 2 (MANDATORY — ART-IV)

- [x] T018 [P] [US2] Extend `tests/unit/strategy/test_strategy_store.py` — failing tests: `link_capability`/`unlink_capability` round-trip against a real capability id; `link_capability` against a nonexistent capability id raises (research.md Decision 2's validation); `link_value_stream`/`unlink_value_stream` same shape; deleting an objective (once `delete_objective` exists in US3 — for now, deleting the underlying row directly in the test) cascades to remove its links, confirmed via `data-model.md`'s cascade behavior. Confirm all fail.
- [x] T019 [P] [US2] Extend `tests/contract/test_strategy_api_contract.py` — failing tests: `POST .../objectives/{id}/capabilities` → 201 with the updated linked list; 404 when the capability id doesn't exist; 409 when already linked; `DELETE .../objectives/{id}/capabilities/{cap_id}` → 204, and the capability itself (`GET /api/v1/business/capabilities/{cap_id}`) is unaffected (spec.md Acceptance Scenario 3); same shape for `.../value-streams`. Confirm all fail.

### Implementation for User Story 2

- [x] T020 [US2] In `src/adp/strategy/store.py`: implement `link_capability`/`unlink_capability`/`link_value_stream`/`unlink_value_stream`, each validating the target id via a direct call to `adp.business.store.get_capability`/`get_value_stream` (research.md Decision 2) before writing. Run T018 and confirm it passes.
- [x] T021 [US2] In `src/adp/strategy/router.py`: implement `POST/DELETE /objectives/{id}/capabilities[/{capability_id}]` and `POST/DELETE /objectives/{id}/value-streams[/{value_stream_id}]`, translating a `None` return from the validation call into 404. Run T019 and confirm it passes.
- [x] T022 [US2] Run `pytest tests/unit/strategy/ tests/contract/test_strategy_api_contract.py -q` — confirm all green, zero regressions in User Story 1's cases.
- [x] T023 [P] [US2] Create `web/src/strategy/ObjectiveCapabilityLinkEditor.test.tsx` and `web/src/strategy/ObjectiveValueStreamLinkEditor.test.tsx` (new — no existing `DesignLinkEditor.tsx` test file to mirror directly, confirmed absent during Setup; follow this codebase's general RTL conventions instead, e.g. `DiagramsPage.test.tsx`'s mocked-hook style) — failing tests: each editor lists currently-linked items with a Remove action, offers a filtered dropdown excluding already-linked ones, and calls the expected link/unlink hook. Confirm all fail.
- [x] T024 [US2] Create `web/src/strategy/ObjectiveCapabilityLinkEditor.tsx` and `web/src/strategy/ObjectiveValueStreamLinkEditor.tsx` (near-verbatim mirrors of `DesignLinkEditor.tsx`'s structure per research.md Decision 4, adapted for capability/value-stream targets) and `web/src/strategy/ObjectiveDetail.tsx` (renders an objective's core fields plus both link editors). Add the corresponding `useLinkCapability`/`useUnlinkCapability`/`useLinkValueStream`/`useUnlinkValueStream` hooks to `web/src/api/strategy.ts` (mirroring `useLinkDesignToCapability`'s exact shape). Run T023 and confirm it passes.
- [x] T025 [US2] Run `cd web && npx vitest run src/strategy/ObjectiveCapabilityLinkEditor.test.tsx src/strategy/ObjectiveValueStreamLinkEditor.test.tsx && npx tsc --noEmit` — confirm all green, zero regressions.

**Checkpoint**: Both user stories independently functional — an objective can be created (US1) and linked to real capabilities/value streams (US2), with zero possibility of a free-text or orphaned link (SC-002/SC-003).

---

## Phase 5: User Story 3 - Browse, edit, and remove strategic objectives (Priority: P3)

**Goal**: An architect can see all captured objectives, edit one, and delete one (cascading its links).

**Independent Test**: Create two objectives, confirm both appear in a list view; edit one's owner and confirm it persists; delete the other and confirm it's gone (spec.md's own Independent Test for this story).

### Tests for User Story 3 (MANDATORY — ART-IV)

- [x] T026 [P] [US3] Extend `tests/unit/strategy/test_strategy_store.py` — failing tests: `list_objectives` returns summary-shaped rows (not full detail, per FR-008/data-model.md) for multiple objectives; `update_objective` persists a partial field change; `delete_objective` removes the row and cascades both join tables (completing T018's deferred cascade case using the real `delete_objective` function). Confirm all fail.
- [x] T027 [P] [US3] Extend `tests/contract/test_strategy_api_contract.py` — failing tests: `GET /api/v1/strategy/objectives` lists multiple objectives with summary fields; `PUT /api/v1/strategy/objectives/{id}` persists an edit, 404 if not found; `DELETE /api/v1/strategy/objectives/{id}` → 204 then a subsequent `GET` → 404; confirm its links are gone too (cross-checked against the capabilities/value-streams link endpoints from US2). Confirm all fail.

### Implementation for User Story 3

- [x] T028 [US3] In `src/adp/strategy/store.py`: implement `list_objectives` (summary projection), `update_objective`, `delete_objective` (relies on the schema's own `ON DELETE CASCADE` for link cleanup — no explicit join-table deletes needed in application code). Run T026 and confirm it passes.
- [x] T029 [US3] In `src/adp/strategy/router.py`: implement `GET /objectives` (list), `PUT /objectives/{id}`, `DELETE /objectives/{id}`. Run T027 and confirm it passes.
- [x] T030 [US3] Run `pytest tests/unit/strategy/ tests/contract/test_strategy_api_contract.py -q` — confirm all green, zero regressions in US1/US2's cases.
- [x] T031 [P] [US3] Create `web/src/strategy/ObjectiveList.test.tsx` (new) and extend `web/src/strategy/ObjectiveDetail.test.tsx` (from T023, adding edit/delete cases) — failing tests: `ObjectiveList` renders multiple objectives with summary info (mirrors `ValueStreamList.tsx`'s convention); `ObjectiveDetail` supports editing a field and deleting the objective. Confirm all fail.
- [x] T032 [US3] Create `web/src/strategy/ObjectiveList.tsx` (mirrors `ValueStreamList.tsx`) and extend `ObjectiveDetail.tsx` with edit/delete; create `web/src/strategy/StrategyPage.tsx` (top-level tab container: Themes / Objectives, mirrors `BusinessPage.tsx`'s tab-bar convention). Run T031 and confirm it passes.
- [x] T033 [US3] Wire a new `"strategy"` `AppView` into `web/src/shell/index.ts`, a nav entry into `web/src/ui/AppShell.tsx`, and a render case into `web/src/App.tsx` — mirrors ADP-914.5's exact "diagrams" nav-entry precedent (new top-level section, not nested under Business Architecture, since strategic objectives are a distinct entity with their own lifecycle per plan.md's Structure Decision).
- [x] T034 [US3] Run `cd web && npx vitest run src/strategy/ && npx tsc --noEmit && npm run test:run` — confirm all green, zero regressions across the whole frontend.

**Checkpoint**: All three user stories independently functional — objectives can be created, linked, browsed, edited, and deleted, reachable from the app's own navigation.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation (ART-XVI) and full-suite regression confirmation, backend and frontend.

- [x] T035 [P] Add a `web/src/strategy/README.md` (mirrors `web/src/diagrams/README.md`'s documentation convention) documenting the module's structure and its two near-verbatim `DesignLinkEditor.tsx` mirrors; add a short module docstring to `src/adp/strategy/__init__.py` explaining the package's relationship to `adp.business` (research.md Decision 1).
- [x] T036 Run `pytest tests/ --ignore=tests/integration -q`, `ruff check src/`, `mypy src/`, `adp-generate --check` — confirm all clean, zero regressions across the whole backend.
- [x] T037 Run `cd web && npx tsc --noEmit` and `npm run test:run` — confirm clean/green across the whole frontend.
- [x] T038 Walk through quickstart.md Scenarios 1–5 to confirm end-to-end behavior beyond the unit-test level (Scenario 6 is T036/T037, just run). If no browser-automation tool is available in-session (as was the case for ADP-914.6/914.7/914.8), the curl-based scenarios in quickstart.md can be run directly against a local `uvicorn` instance instead of requiring a browser — substitute with equivalent automated/API-level coverage and document exactly which test covers which scenario if even that isn't feasible, rather than skipping silently.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all three user stories (none can write a CRUD function against tables/models that don't exist yet).
- **User Story 1 (Phase 3)**: Depends on Foundational. No dependency on User Stories 2 or 3.
- **User Story 2 (Phase 4)**: Depends on Foundational **and** on User Story 1's `create_objective`/`POST /objectives` existing (a link needs an objective to attach to) — not independently implementable in parallel with US1, though independently *testable* per its own acceptance scenarios once US1 exists.
- **User Story 3 (Phase 5)**: Depends on Foundational and, for its own contract tests, on US1's create endpoint (something to list/edit/delete) and benefits from US2 existing (to verify cascade deletes real links, not just an empty set) — sequenced last to reuse both.
- **Polish (Phase 6)**: Depends on all three user stories being complete.

### Parallel Opportunities

- T004 (Foundational model tests) has no prior dependency beyond T002/T003 (schema exists) — can proceed as soon as the migration is applied.
- Within each user story, the backend test task(s) and frontend test task(s) touch entirely disjoint files and can be drafted in parallel (e.g. T008/T009 alongside T013, though T013's own hooks depend on T011's endpoints existing to be meaningfully implemented against — tests can still be *written* in parallel, just not *passed* until the backend lands).
- T035 (README/docstrings) can run alongside T036/T037 once all three stories are implemented.

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (Setup) → Phase 2 (Foundational: migration, models, scaffolding).
2. Complete Phase 3 (User Story 1) → capturing a structured objective alone is a complete, shippable increment per spec.md (the core payoff of "structured, not a text blob").
3. **STOP and VALIDATE**: run T017, confirm quickstart.md Scenarios 1–2 pass.
4. Optionally stop here — User Stories 2 and 3 add traceability and ongoing management on top, independently valuable but not required for the core capture capability to exist.

### Incremental Delivery

1. Setup + Foundational → schema and typed models ready, unit-tested in isolation.
2. Add User Story 1 → test independently → MVP.
3. Add User Story 2 → test independently → traceability to real architecture data.
4. Add User Story 3 → test independently → full CRUD lifecycle, reachable from app navigation.
5. Polish → documentation + full-suite regression confirmation, backend and frontend.

## Notes

- No `[Story]` label on Setup/Foundational/Polish tasks, per the required task format.
- Every implementation task follows a task confirmed to fail first (ART-IV): T004→T005, T008→T010, T009→T011, T013→T014, T015→T016, T018→T020, T019→T021, T023→T024, T026→T028, T027→T029, T031→T032.
- This feature touches 1 new backend package (`adp.strategy`, 3 files + `__init__.py`), 1 new migration, 1 new frontend module (`web/src/strategy/`, ~7 files), 1 modified frontend API client (`web/src/api/strategy.ts`, new file actually — no existing file modified there), and 3 modified frontend files for nav wiring (`App.tsx`, `shell/index.ts`, `AppShell.tsx`) — zero changes to any existing `adp.business` file, per FR-012.
