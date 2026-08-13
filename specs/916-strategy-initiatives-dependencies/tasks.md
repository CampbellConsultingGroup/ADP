# Tasks: Strategy Execution Layer — Initiatives & Objective Dependencies

**Input**: Design documents from `/specs/916-strategy-initiatives-dependencies/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Mandatory for all ADP features (ART-IV). Test tasks appear before their implementation counterparts in every user-story phase and MUST be verified to fail before implementation begins.

**Organization**: Grouped by user story (spec.md) to enable independent implementation and testing of each.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 / US2, per spec.md's priorities (P1/P2)

## Path Conventions

Single project, one new backend submodule + existing directories — no new package (plan.md's Structure Decision):
- Backend: `src/adp/strategy/initiatives.py` (new), `src/adp/strategy/router.py` (extend), `src/adp/store/migrations/versions/027_strategy_initiatives.py` (new)
- Backend tests: `tests/unit/strategy/`, `tests/contract/test_strategy_api_contract.py`
- Frontend: `web/src/api/strategy.ts`, `web/src/strategy/`

---

## Phase 1: Setup

- [X] T001 [P] Create migration skeleton `src/adp/store/migrations/versions/027_strategy_initiatives.py` (revision header, `down_revision = "026"`, empty `upgrade()`/`downgrade()`)
- [X] T002 [P] Create module skeleton `src/adp/strategy/initiatives.py` (module docstring per research.md Decision 1, imports of `_now`/`_rowcount`/`DuplicateLinkError`/`LinkNotFoundError` from `adp.strategy.store`, no logic yet)
- [X] T003 [P] Create empty test file stub `tests/unit/strategy/test_dependency_cycles.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: No user story work can begin until this phase is complete — both stories need their tables to exist (one migration creates all three, per research.md Decision 5).

- [X] T004 Implement migration 027's `upgrade()` in `027_strategy_initiatives.py`: `CREATE TABLE strategy_initiatives` (id PK, name not null, description/owner nullable, status not null default `'planned'` + named CHECK on the 5-value set), `CREATE TABLE strategy_initiative_objective_links` (composite PK `(initiative_id, objective_id)`, both FK `ON DELETE CASCADE`, one index), `CREATE TABLE strategic_objective_dependencies` (composite PK `(objective_id, depends_on_objective_id)`, **both** columns FK `ON DELETE CASCADE` to `strategic_objectives.id` with distinct constraint names — research.md Decision 3) (depends on T001)
- [X] T005 Implement migration 027's `downgrade()`: drop the three tables in reverse order (depends on T004)
- [X] T006 Run `alembic upgrade head` against local Postgres and confirm all three tables exist with the expected columns/constraints (depends on T004, T005)

**Checkpoint**: Foundation ready — user story implementation can now begin. US1 and US2 touch entirely disjoint tables/models/store functions from this point and can proceed in parallel.

---

## Phase 3: User Story 1 - Track the program of work delivering an objective (Priority: P1) 🎯 MVP

**Goal**: A strategy lead creates initiatives and links each to the objective(s) it serves; both directions are visible (an initiative shows its objectives, an objective shows its initiatives).

**Independent Test**: Create an initiative, link it to one or more objectives, view it from both directions, unlink and delete (quickstart.md scenarios 1 and 2).

### Tests for User Story 1 (MANDATORY — ART-IV, write first, confirm failing)

- [X] T007 [P] [US1] Unit tests for initiative CRUD and link/unlink/reverse-lookup store functions in `tests/unit/strategy/test_initiatives_store.py`: create/get/list/update/delete round-trip, delete is unconditional even when links exist (FR-011), link succeeds and appears from both directions, duplicate link raises `DuplicateLinkError`, unlink removes only that link (a second, unrelated link on the same initiative survives), unlink-not-found raises `LinkNotFoundError`
- [X] T008 [P] [US1] Unit tests for initiative model validation in `tests/unit/strategy/test_initiatives_models.py`: blank name rejected, unknown fields rejected (`extra="forbid"`), status defaults to `"planned"`, status accepts each of the 5 valid values, invalid status value rejected
- [X] T009 [US1] Contract tests for initiative CRUD and link endpoints in `tests/contract/test_strategy_api_contract.py`: `POST/GET/GET-by-id/PATCH/DELETE /initiatives` full lifecycle incl. 404s; `POST/DELETE /initiatives/{id}/objectives/{objective_id}` 201/404 (either id)/409 (duplicate)/204/404; `GET /objectives/{id}/initiatives` 200/404 reverse lookup

### Implementation for User Story 1

- [X] T010 [P] [US1] Add `StrategyInitiative`, `StrategyInitiativeCreate`, `StrategyInitiativeUpdate`, `StrategyInitiativeListResponse` Pydantic models and `_initiatives`/`_initiative_objective_links` `sa.Table` defs to `src/adp/strategy/initiatives.py` (data-model.md) (depends on T002)
- [X] T011 [US1] Implement `create_initiative`, `get_initiative`, `list_initiatives`, `update_initiative`, `delete_initiative` in `src/adp/strategy/initiatives.py` — make T007's CRUD cases and T008 pass (depends on T010)
- [X] T012 [US1] Implement `link_initiative_objective`, `unlink_initiative_objective`, `list_objective_initiative_ids` (reverse lookup) in `src/adp/strategy/initiatives.py`, reusing `store.py`'s `DuplicateLinkError`/`LinkNotFoundError` — make T007's link cases pass (depends on T010)
- [X] T013 [US1] Implement `POST/GET/GET-by-id/PATCH/DELETE /strategy/initiatives(/{id})` in `src/adp/strategy/router.py`, importing from `initiatives.py`, with structured `logger.info(...)` calls on create/update/delete (ART-IX, plan.md Ground-Truth Correction 4) — make T009's CRUD cases pass (depends on T011)
- [X] T014 [US1] Implement `POST/DELETE /strategy/initiatives/{id}/objectives/{objective_id}` and `GET /strategy/objectives/{id}/initiatives` in `src/adp/strategy/router.py` — make T009's link cases pass (depends on T012)
- [X] T015 [P] [US1] Add `StrategyInitiative` types and `useInitiatives`/`useInitiative`/`useCreateInitiative`/`useUpdateInitiative`/`useDeleteInitiative`/`useLinkInitiativeObjective`/`useUnlinkInitiativeObjective`/`useObjectiveInitiatives` hooks to `web/src/api/strategy.ts`
- [X] T016 [P] [US1] Create `web/src/strategy/InitiativeList.tsx` — create/edit/delete initiatives, mirroring `ThemeList.tsx`'s established create-form + inline-edit + delete convention
- [X] T017 [US1] Wire a "Linked Initiatives" panel (list + link/unlink) into `web/src/strategy/ObjectiveDetail.tsx`, and a new "Initiatives" tab alongside Objectives/Themes in `web/src/strategy/StrategyPage.tsx` rendering `InitiativeList` (depends on T015, T016)
- [X] T018 [P] [US1] Component tests for `InitiativeList.tsx` and the linked-initiatives panel in `ObjectiveDetail.test.tsx`

**Checkpoint**: User Story 1 fully functional and independently testable — quickstart.md scenarios 1, 2.

---

## Phase 4: User Story 2 - Express and see what one objective depends on or blocks (Priority: P2)

**Goal**: A strategy lead records that one objective depends on another; both directions are visible on each objective; no cycle can ever be recorded.

**Independent Test**: Record a dependency, view it from both objectives, attempt direct/chained/self cycles and confirm each is rejected, remove the dependency (quickstart.md scenario 3).

### Tests for User Story 2 (MANDATORY — ART-IV)

- [X] T019 [P] [US2] Table-driven unit tests for the pure `_reaches(start, target, edges)` BFS in `tests/unit/strategy/test_dependency_cycles.py` — plain Python dicts, no session fixture, no async, mirroring `test_objective_status.py`'s dependency-free style: no edges → unreachable; direct 2-cycle shape reachable; 3-node chain reachable; a longer (5+ node) chain reachable; a non-cyclic branch correctly NOT reachable (depends on T003)
- [X] T020 [P] [US2] Contract tests for dependency endpoints in `tests/contract/test_strategy_api_contract.py`: `POST /objectives/{id}/depends-on` 201/404 (either id)/409 (duplicate)/400 (direct cycle)/400 (chained cycle)/400 (self-dependency); `GET /objectives/{id}/dependencies` 200 showing both `depends_on` and `blocks`/404; `DELETE /objectives/{id}/depends-on/{other_id}` 204/404

### Implementation for User Story 2

- [X] T021 [P] [US2] Add `ObjectiveDependencyCreate`, `ObjectiveDependenciesResponse` Pydantic models and `_objective_dependencies` `sa.Table` def to `src/adp/strategy/initiatives.py` (data-model.md) (depends on T002)
- [X] T022 [US2] Implement `_reaches()` (pure BFS) and `_would_create_cycle()` (async: self-check + fetch existing edges + delegate to `_reaches`) in `src/adp/strategy/initiatives.py` per research.md Decision 2 — make T019 pass (depends on T021)
- [X] T023 [US2] Implement `add_objective_dependency` (raises `CycleError`, new exception), `remove_objective_dependency` (raises `LinkNotFoundError`), `get_objective_dependencies` (both directions) in `src/adp/strategy/initiatives.py` — wire in `_would_create_cycle()` (depends on T021, T022)
- [X] T024 [US2] Implement `POST /strategy/objectives/{id}/depends-on`, `DELETE /strategy/objectives/{id}/depends-on/{other_id}`, `GET /strategy/objectives/{id}/dependencies` in `src/adp/strategy/router.py`, mapping `CycleError` to 400 with an explanatory detail message, with structured logging on add/remove — make T020 pass (depends on T023)
- [X] T025 [P] [US2] Add `ObjectiveDependenciesResponse` type and `useObjectiveDependencies`/`useAddObjectiveDependency`/`useRemoveObjectiveDependency` hooks to `web/src/api/strategy.ts`
- [X] T026 [US2] Add a "Depends on / Blocks" panel to `web/src/strategy/ObjectiveDetail.tsx` — both directions listed, an add-dependency control, a remove action per entry, and the cycle-rejection message surfaced clearly on a 400 (depends on T025)
- [X] T027 [P] [US2] Component test for the depends-on/blocks panel in `ObjectiveDetail.test.tsx`, including a mocked 400/cycle response rendering the explanatory message

**Checkpoint**: User Stories 1 and 2 both independently functional.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [X] T028 [P] Confirm OpenAPI/schema regeneration is clean with the new endpoints/models (`adp-generate --check`)
- [X] T029 Run the full regression suite: `pytest tests/ --ignore=tests/integration -q` and `cd web && npx vitest run && npx tsc --noEmit`
- [X] T030 Manually walk through all 4 quickstart.md scenarios against a running local stack (`ADP_AUTH_ENABLED=false`), including the direct/chained/self cycle-rejection cases in a real browser
- [X] T031 Replace the auto-generated `916-strategy-initiatives-dependencies` stub line in CLAUDE.md (and the matching AGENTS.md "Latest work"/"Prior work:" shift) with a proper hand-written narrative at commit time

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS every user story (both need their tables to exist; the migration creates all three in one revision per research.md Decision 5).
- **User Stories (Phase 3–4)**: Both depend on Foundational only. **US1 and US2 touch entirely disjoint tables, models, and store functions** (`_initiatives`/`_initiative_objective_links` vs. `_objective_dependencies`) within the same `initiatives.py` file — genuinely independent, no cross-story dependency, can be built in either order or in parallel by two developers.
- **Polish (Phase 5)**: Depends on both user stories being complete.

### Within Each User Story

- Tests written and confirmed failing before implementation (ART-IV).
- Models/table defs before store functions; store functions before router endpoints; backend endpoints before frontend hooks; hooks before UI wiring.

### Parallel Opportunities

- T001/T002/T003 (Setup) in parallel.
- Within US1: T007/T008 in parallel; T010 in parallel with nothing before it in-story but blocks T011/T012; T015/T016 in parallel once T013/T014 land; T018 last.
- Within US2: T019/T020 in parallel; T021 blocks T022/T023; T025/T026 sequential (hooks before UI); T027 last.
- **US1's entire phase (T007–T018) can run in parallel with US2's entire phase (T019–T027)** by two developers, since they share no file-level write beyond both appending to the same `initiatives.py`/`router.py`/`strategy.ts` (a merge concern, not a logical dependency) — this is a stronger parallelism guarantee than `915` had, where US2 (abandon) genuinely depended on US1's `compute_status()` already existing.

---

## Parallel Example: User Story 1

```bash
# Tests together:
Task: "Unit tests for initiative CRUD and link/unlink in tests/unit/strategy/test_initiatives_store.py"
Task: "Unit tests for initiative model validation in tests/unit/strategy/test_initiatives_models.py"

# Once tests are red, models + frontend scaffolding together:
Task: "Add StrategyInitiative(+Create/+Update/+ListResponse) models + table defs to src/adp/strategy/initiatives.py"
Task: "Add initiative types/hooks to web/src/api/strategy.ts"
Task: "Create web/src/strategy/InitiativeList.tsx"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 (Setup) → Phase 2 (Foundational) → Phase 3 (US1).
2. **STOP and VALIDATE**: quickstart.md scenarios 1, 2 against a real local stack.
3. This alone answers the feature's primary problem statement (representing the program of work delivering an objective) — genuinely shippable as an MVP.

### Incremental Delivery

1. Setup + Foundational → all three tables exist.
2. US1 → create/link initiatives → demoable.
3. US2 → record/view dependencies, cycles rejected → demoable, fully independent of US1.

### Notes

- `[P]` tasks touch different files (or, within `initiatives.py`, different top-level sections) with no unmet dependency.
- Verify each phase's tests fail before writing its implementation.
- Commit after each task or logical group; stop at any checkpoint to validate a story independently.
