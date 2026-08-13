# Tasks: Objective ↔ Design/Application Traceability

**Input**: Design documents from `/specs/917-objective-design-traceability/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Mandatory for all ADP features (ART-IV). Test tasks appear before their implementation
counterparts in every user-story phase and MUST be verified to fail before implementation begins.

**Organization**: Grouped by user story (spec.md) to enable independent implementation and testing of
each.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 / US2, per spec.md's priorities (P1/P2)

## Path Conventions

Extends three existing files, no new package/submodule (plan.md's Structure Decision):
- Backend: `src/adp/strategy/{models,store,router}.py` (extend), `src/adp/api/routers/designs.py`
  (extend), `src/adp/application/router.py` (extend),
  `src/adp/store/migrations/versions/028_objective_design_application_links.py` (new)
- Backend tests: `tests/unit/strategy/{test_strategy_store,test_strategy_models}.py` (extend),
  `tests/contract/{test_strategy_api_contract,test_designs_api,test_application_registry_api}.py`
  (extend)
- Frontend: `web/src/api/strategy.ts` (extend), `web/src/strategy/` (new editors),
  `web/src/canvas-v2/C4DesignView.tsx` (extend), `web/src/application/` (new panel)

---

## Phase 1: Setup

- [X] T001 Create migration skeleton
  `src/adp/store/migrations/versions/028_objective_design_application_links.py` (revision header,
  `down_revision = "027"`, empty `upgrade()`/`downgrade()`)

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: No user story work can begin until this phase is complete — both stories need their
tables to exist (one migration creates both, per research.md Decision 5).

- [X] T002 Implement migration 028's `upgrade()`: `CREATE TABLE objective_design_links`
  (composite PK `(objective_id, design_id)`, `objective_id` FK → `strategic_objectives.id`
  `ON DELETE CASCADE`, `design_id TEXT` FK → `designs.id` `ON DELETE CASCADE` — matching
  `capability_design_links.design_id`'s exact type from migration 008, one index on `design_id`),
  `CREATE TABLE objective_application_links` (composite PK `(objective_id, application_id)`, both
  columns FK `ON DELETE CASCADE` — `application_id VARCHAR(36)` matching `applications.id`'s type —
  one index on `application_id`) (depends on T001)
- [X] T003 Implement migration 028's `downgrade()`: drop both tables in reverse order (depends on T002)
- [X] T004 Run `alembic upgrade head` against local Postgres and confirm both tables exist with the
  expected columns/constraints (depends on T002, T003)

**Checkpoint**: Foundation ready — user story implementation can now begin. US1 and US2 touch entirely
disjoint tables/store-functions/router-endpoints and can proceed in parallel.

---

## Phase 3: User Story 1 - Link a design to the objective(s) it realizes (Priority: P1) 🎯 MVP

**Goal**: A strategy lead links a design to an objective from the objective's detail view; the link is
visible from both sides (the objective's linked-designs list, and a "Traceability" section on the
design's C4 Design View).

**Independent Test**: Link an existing design to an objective, confirm it appears on both sides, attempt
a duplicate link and an unknown-design link (both rejected), then unlink and confirm removal from both
sides (quickstart.md scenario 1).

### Tests for User Story 1 (MANDATORY — ART-IV, write first, confirm failing)

- [X] T005 [P] [US1] Unit tests for `design_exists`, `link_objective_design`, `unlink_objective_design`,
  `list_objectives_for_design` in `tests/unit/strategy/test_strategy_store.py`: design exists/doesn't
  exist against the new `_designs` mirror table (seeded manually in the test fixture, mirroring
  `adp.business.store`'s own `_designs` fixture precedent), link succeeds and appears in
  `get_objective()`'s `design_ids`, duplicate link raises `DuplicateLinkError`, unlink removes only that
  link (a second, unrelated design link on the same objective survives), unlink-not-found raises
  `LinkNotFoundError`, `list_objectives_for_design` returns every objective linked to a given design
- [X] T006 [US1] Contract tests for `POST/DELETE /api/v1/strategy/objectives/{id}/designs(/{design_id})`
  in `tests/contract/test_strategy_api_contract.py`: 201 with updated `design_ids` list, 404 unknown
  objective, 404 unknown design, 409 duplicate, 204 unlink, 404 unlink-not-found
- [X] T007 [US1] Contract test for `GET /api/v1/designs/{id}/objectives` in
  `tests/contract/test_designs_api.py`: 200 with `StrategicObjectiveListResponse` shape reflecting real
  links (extend the existing fixture with a new `_get_strategy_session` override wired to a real
  in-memory-SQLite strategy session, alongside the existing mocked `DesignStore`), 404 unknown design
  (reusing `elements.py`'s established `store.get(design_id)` / `DesignNotFoundError` → 404 pattern,
  replicated locally in `designs.py` rather than cross-imported)

### Implementation for User Story 1

- [X] T008 [P] [US1] Add `ObjectiveDesignLinkCreate` Pydantic model and `design_ids: list[str] = []`
  field on `StrategicObjective` to `src/adp/strategy/models.py` (data-model.md) (depends on T005 being
  red)
- [X] T009 [US1] Add `_objective_design_links` and `_designs` (lightweight read-only mirror, id + title
  only, matching `adp.business.store`'s own `_designs` precedent) `sa.Table` defs to
  `src/adp/strategy/store.py` (depends on T008)
- [X] T010 [US1] Implement `design_exists`, `link_objective_design`, `unlink_objective_design`,
  `list_objectives_for_design` in `src/adp/strategy/store.py`; extend `get_objective()`'s existing
  SELECT to also populate `design_ids` — make T005 pass (depends on T009)
- [X] T011 [US1] Implement `POST/DELETE /strategy/objectives/{id}/designs(/{design_id})` in
  `src/adp/strategy/router.py`, adding a new `_get_store_session` dependency (second, `adp.store`-scoped
  session, mirroring the existing `_get_business_session` pattern) used only to call `design_exists`,
  with structured `logger.info(...)` on link/unlink (ART-IX) — make T006 pass (depends on T010)
- [X] T012 [US1] Implement `GET /api/v1/designs/{id}/objectives` in `src/adp/api/routers/designs.py`,
  adding a new `_get_strategy_session` dependency (opens a session against
  `adp.strategy.store`'s session factory) that calls `list_objectives_for_design` — make T007 pass
  (depends on T010)
- [X] T013 [P] [US1] Add `design_ids` to the `StrategicObjective` TS type, plus
  `useLinkObjectiveDesign`/`useUnlinkObjectiveDesign`/`useDesignObjectives` hooks to
  `web/src/api/strategy.ts`
- [X] T014 [P] [US1] Create `web/src/strategy/ObjectiveDesignLinkEditor.tsx` — near-verbatim mirror of
  `ObjectiveCapabilityLinkEditor.tsx`, substituting designs (fetched via the existing `useDesigns()`-
  equivalent list hook) as the link target
- [X] T015 [US1] Wire `ObjectiveDesignLinkEditor` into `web/src/strategy/ObjectiveDetail.tsx` as a new
  "Linked Designs" section (depends on T013, T014)
- [X] T016 [US1] Add a small collapsible "Traceability" section to `web/src/canvas-v2/C4DesignView.tsx`
  showing the linked objectives for the currently-open design, read-only (per the resolved
  Clarification — the only design-scoped screen that exists today) (depends on T013)
- [X] T017 [P] [US1] Component tests for `ObjectiveDesignLinkEditor.tsx` in a new
  `web/src/strategy/ObjectiveDesignLinkEditor.test.tsx`, and for the new Traceability section in
  `web/src/canvas-v2/C4DesignView.test.tsx`

**Checkpoint**: User Story 1 fully functional and independently testable — quickstart.md scenario 1.

---

## Phase 4: User Story 2 - Link an application to the objective(s) it realizes (Priority: P2)

**Goal**: Same capability as User Story 1, for applications — visible from the objective's detail view
and from the application's own detail screen (which already has real sectioned panels, unlike designs).

**Independent Test**: Link an existing application to an objective, confirm it appears on both sides
(objective detail + application detail's new section), attempt a duplicate and an unknown-application
link (both rejected), then unlink and confirm removal from both sides (quickstart.md scenario 2).

### Tests for User Story 2 (MANDATORY — ART-IV)

- [X] T018 [P] [US2] Unit tests for `application_exists`, `link_objective_application`,
  `unlink_objective_application`, `list_objectives_for_application` in
  `tests/unit/strategy/test_strategy_store.py`, mirroring T005's design-side cases exactly
- [X] T019 [US2] Contract tests for
  `POST/DELETE /api/v1/strategy/objectives/{id}/applications(/{application_id})` in
  `tests/contract/test_strategy_api_contract.py`, mirroring T006's design-side cases exactly
- [X] T020 [US2] Contract test for `GET /api/v1/applications/{id}/objectives` in
  `tests/contract/test_application_registry_api.py`: 200 with `StrategicObjectiveListResponse`
  reflecting real links (extend the existing real-session fixture with a new `_get_strategy_session`
  override), 404 unknown application (reusing `application/router.py`'s existing
  `astore.get_application(app_id, session) is None` → 404 pattern)

### Implementation for User Story 2

- [X] T021 [P] [US2] Add `ObjectiveApplicationLinkCreate` Pydantic model and
  `application_ids: list[str] = []` field on `StrategicObjective` to `src/adp/strategy/models.py`
  (depends on T018 being red)
- [X] T022 [US2] Add `_objective_application_links` and `_applications` (lightweight read-only mirror,
  id + name) `sa.Table` defs to `src/adp/strategy/store.py` (depends on T021)
- [X] T023 [US2] Implement `application_exists`, `link_objective_application`,
  `unlink_objective_application`, `list_objectives_for_application` in `src/adp/strategy/store.py`;
  extend `get_objective()`'s SELECT to also populate `application_ids` — make T018 pass (depends on
  T022)
- [X] T024 [US2] Implement `POST/DELETE /strategy/objectives/{id}/applications(/{application_id})` in
  `src/adp/strategy/router.py`, reusing T011's `_get_store_session` (extended to also validate
  `application_id` via `application_exists`), with structured `logger.info(...)` on link/unlink — make
  T019 pass (depends on T023)
- [X] T025 [US2] Implement `GET /api/v1/applications/{id}/objectives` in
  `src/adp/application/router.py`, adding a `_get_strategy_session` dependency (same shape as T012's)
  that calls `list_objectives_for_application` — make T020 pass (depends on T023)
- [X] T026 [P] [US2] Add `application_ids` to the `StrategicObjective` TS type, plus
  `useLinkObjectiveApplication`/`useUnlinkObjectiveApplication`/`useApplicationObjectives` hooks to
  `web/src/api/strategy.ts`
- [X] T027 [P] [US2] Create `web/src/strategy/ObjectiveApplicationLinkEditor.tsx` — near-verbatim mirror
  of `ObjectiveCapabilityLinkEditor.tsx`, substituting applications as the link target
- [X] T028 [US2] Wire `ObjectiveApplicationLinkEditor` into `web/src/strategy/ObjectiveDetail.tsx` as a
  new "Linked Applications" section (depends on T026, T027)
- [X] T029 [US2] Create `web/src/application/ObjectiveLinksPanel.tsx` — mirrors
  `CapabilityLinksEditor.tsx`'s read+link pattern, showing/linking/unlinking objectives for the current
  application — and wire it into `web/src/application/ApplicationDetail.tsx` as a new "Objectives
  Realized" section (depends on T026)
- [X] T030 [P] [US2] Component tests for `ObjectiveApplicationLinkEditor.tsx` (new
  `.test.tsx` sibling) and `ObjectiveLinksPanel.tsx` (new `.test.tsx` sibling)

**Checkpoint**: User Stories 1 and 2 both independently functional.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [X] T031 [P] Confirm OpenAPI/schema regeneration is clean with the new endpoints/models
  (`adp-generate --check`)
- [X] T032 Run the full regression suite: `pytest tests/ --ignore=tests/integration -q` and
  `cd web && npx vitest run && npx tsc --noEmit`
- [X] T033 Manually walk through all 4 quickstart.md scenarios against a running local stack
  (`ADP_AUTH_ENABLED=false`), including a real browser check of the C4 Design View's Traceability
  section and the Application detail screen's Objectives Realized section
- [X] T034 Replace the auto-generated `917-objective-design-traceability` stub line in CLAUDE.md (and
  the matching AGENTS.md "Latest work"/"Prior work:" shift) with a proper hand-written narrative at
  commit time

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS every user story (both need their tables to
  exist; the migration creates both in one revision per research.md Decision 5).
- **User Stories (Phase 3–4)**: Both depend on Foundational only. **US1 and US2 touch entirely
  disjoint tables, store functions, and router endpoints** — genuinely independent, can be built in
  either order or in parallel by two developers, mirroring ADP-d8u.6's own US1/US2 independence.
- **Polish (Phase 5)**: Depends on both user stories being complete.

### Within Each User Story

- Tests written and confirmed failing before implementation (ART-IV).
- Models/table defs before store functions; store functions before router endpoints (both the
  forward-link endpoints in `adp.strategy.router` and the reverse-lookup endpoint in the owning
  package's router); backend endpoints before frontend hooks; hooks before UI wiring.

### Parallel Opportunities

- Within US1: T005 alone (T006/T007 depend on implementation existing to be meaningfully red against a
  running app, though they can be *written* in parallel with T005); T008 blocks T009→T010→(T011‖T012);
  T013/T014 in parallel once T011/T012 land; T017 last.
- Within US2: same shape as US1, one-for-one.
- **US1's entire phase (T005–T017) can run in parallel with US2's entire phase (T018–T030)** by two
  developers, since they share no file-level write beyond both appending to the same
  `store.py`/`router.py`/`strategy.ts`/`ObjectiveDetail.tsx` (a merge concern, not a logical dependency)
  — matching ADP-d8u.6's own stronger-than-usual parallelism guarantee.

---

## Parallel Example: User Story 1

```bash
# Tests together:
Task: "Unit tests for design link store functions in tests/unit/strategy/test_strategy_store.py"
Task: "Contract tests for design link endpoints in tests/contract/test_strategy_api_contract.py"

# Once tests are red, models + frontend scaffolding together:
Task: "Add ObjectiveDesignLinkCreate model + design_ids field to src/adp/strategy/models.py"
Task: "Add design_ids type + hooks to web/src/api/strategy.ts"
Task: "Create web/src/strategy/ObjectiveDesignLinkEditor.tsx"
```

## Implementation Strategy

**MVP = User Story 1 only** (T001–T017): closes the single most-cited open-frontier traceability gap
(objective→design) end to end, independently shippable and demoable without User Story 2 existing.
User Story 2 (applications) is a same-shape, lower-priority increment layered on afterward — the two
share no runtime coupling, so US2 can be deferred indefinitely without weakening US1's value.
