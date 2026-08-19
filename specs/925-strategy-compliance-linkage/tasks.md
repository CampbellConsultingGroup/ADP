# Tasks: Strategy Domain Linkage — COMPLY-05

**Input**: Design documents from `/specs/925-strategy-compliance-linkage/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓, quickstart.md ✓

**Tests**: Mandatory (ART-IV, per `.specify/templates/tasks-template.md`). Test tasks appear before their
implementation counterparts in every user-story phase and must be written and verified to fail first.

**Organization**: Tasks grouped by user story (US1 = remediation loop / `InitiativeControlMapping`, P1
🎯 MVP; US2 = why-an-objective-exists / `ObjectiveControlMapping`, P2). The two link types touch disjoint
files on the Strategy side (`initiatives.py` vs. `models.py`/`store.py`) and disjoint new routes on both
`adp.strategy.router` and `adp.compliance.router` — independently implementable and testable, sharing only
the migration (Phase 1) and the read-only compliance-schema mirrors (Phase 2).

**A note on what the source bundle got wrong, resolved before any task below** (research.md D1): the
bundle described `InitiativeControlMapping` as referencing one `control_mapping_id`. COMPLY-02 actually
has no such column — `ControlMapping` is five separate physical tables with composite PKs. Every US1 task
below reflects the corrected five-parallel-tables design, not the bundle's original text.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 / US2, per spec.md's priorities (P1/P2)

## Path Conventions

Single project, existing packages/files only — no new package (plan.md Structure Decision):
- Backend: `src/adp/strategy/{models,store,initiatives,router}.py` (all exist, extended);
  `src/adp/compliance/router.py` (exists, extended); one new migration
- Backend tests: `tests/unit/strategy/test_control_links.py` (new), `tests/contract/test_strategy_compliance_links_api.py` (new)
- Frontend: `web/src/api/strategy.ts`, `web/src/strategy/ObjectiveDetail.tsx`, `web/src/strategy/InitiativeList.tsx`, `web/src/compliance/ControlTree.tsx` (all exist, extended); two new editor components

---

## Phase 1: Setup (Migration)

**Purpose**: Database schema every user story depends on.

- [X] T001 Create Alembic migration in `src/adp/store/migrations/versions/034_strategy_compliance_links.py` (`revision = "034"`, `down_revision = "033"`): six tables per data-model.md — `objective_control_links` (`objective_id` VARCHAR(36) FK→`strategic_objectives.id` ON DELETE CASCADE, `control_id` VARCHAR(36) FK→`controls.id` ON DELETE CASCADE, composite PK, `created_at` TIMESTAMPTZ NOT NULL DEFAULT now(), index `ix_ocl_control_id`); five `initiative_control_{capability,application,design,pattern,organization}_mapping` tables, each with `initiative_id` VARCHAR(36) FK→`strategy_initiatives.id` ON DELETE CASCADE (part of the composite PK), the matching target column(s) (`capability_id`/`application_id`/`design_id` **TEXT**/`pattern_id` **VARCHAR unbounded**, or none for `organization`), `created_at`, a **composite** `ForeignKeyConstraint` against the corresponding `control_*_mapping` table's own composite PK (`control_id` + target column, or `control_id` alone for `organization`) with `ondelete="CASCADE"`, and an index on the target-side columns for the reverse-lookup direction; `downgrade()` drops all six tables in reverse order

**Checkpoint**: Migration applies cleanly (`alembic upgrade head` then `alembic downgrade -1` then `alembic upgrade head` again).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Read-only mirrors of the Compliance schema inside `adp.strategy`, and the cross-package
session dependency both stories' reverse-lookup routes need.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 [P] In `src/adp/strategy/store.py` (extends the existing `_designs`/`_applications` mirror-table idiom, ADP-d8u.2): `_controls_mirror` (read-only `sa.Table("controls", ...)`, columns `id`, `code`, `title`, `framework_id`); five read-only mirror `sa.Table()`s of `control_capability_mapping`/`control_application_mapping`/`control_design_mapping`/`control_pattern_mapping`/`control_organization_mapping`, each carrying `control_id` + the target column + `compliance_status`/`evidence_ref`/`assessed_at` (**not** just key columns — research.md D3, needed for live-status JOINs in US1); `control_exists(control_id: str, session) -> bool`
- [X] T003 [P] In `src/adp/compliance/router.py`: `_get_strategy_session()` async dependency generator, mirroring `adp/api/routers/designs.py`'s existing `_get_strategy_session()` verbatim (`from adp.strategy import store as sstore` inside the function; `factory = sstore._get_session_factory()`; `async with factory() as session: yield session`) — used by both US1's and US2's reverse-lookup routes below
- [X] T004 [P] Unit tests in `tests/unit/strategy/test_control_links.py` for T002: `control_exists()` returns `True`/`False` correctly against a seeded SQLite fixture (mirrors `test_compliance_status.py`'s own SQLite-fixture-with-`cstore._metadata.create_all()`-style setup, extended to also `create_all()` the new mirror tables against `sstore._metadata`)

**Checkpoint**: Mirror tables and existence helper available; cross-package session dependency in place; unit tests pass.

---

## Phase 3: User Story 1 - Trace remediation work back to a compliance gap (Priority: P1) 🎯 MVP

**Goal**: An authorized user can link a Strategy Initiative to a specific, already-assessed `ControlMapping`
(a Control in the context of one target), with **no** Strategic Objective required at any point, and see
that link — and its always-live `compliance_status` — from both the Initiative's own side and the
compliance gap's own side.

**Independent Test**: Create an Initiative with zero linked Objectives, link it directly to an existing
`non_compliant` `ControlMapping`, confirm the link shows from both sides, then update the underlying
mapping's status and confirm the change is reflected through the link with no separate write
(spec.md US1 Acceptance Scenarios; quickstart.md Scenarios 1–5, 7 (Initiative-side case), 8 (Control
delete case)).

### Tests for User Story 1 (write first — ART-IV)

- [X] T005 [P] [US1] Unit tests in `tests/unit/strategy/test_control_links.py`: `link_initiative_control_mapping()` raises `ControlMappingNotFoundError` when no `ControlMapping` row exists yet for the given `(control_id, target_type, target_id)`; raises `DuplicateLinkError` on a repeat link; `unlink_initiative_control_mapping()` raises `LinkNotFoundError` when the pair isn't linked; `_linked_control_mappings()` returns `compliance_status` read live from the mirror table — updating the underlying mirrored row's status (simulating a COMPLY-02 write) and re-calling `_linked_control_mappings()` returns the new value with zero writes to the link table itself (FR-008, research.md D3)
- [X] T006 [P] [US1] Contract tests in `tests/contract/test_strategy_compliance_links_api.py` (SQLite fixture wiring `sstore._metadata`+`sinit`'s tables+`cstore`'s tables together, mirroring `tests/contract/test_compliance_mappings_api.py`'s own two-domain fixture precedent): `POST /initiatives/{id}/control-mappings/applications/{control_id}/{app_id}` → 201, response validates as `StrategyInitiative` with one `ControlMappingRef` in `control_mappings`; repeat → 409; against a `(control_id, app_id)` with no `ControlMapping` row → 404; `DELETE` the same path → 204, then 404 on repeat; `GET /compliance/controls/{control_id}/mappings/applications/{app_id}/initiatives` → 200 `StrategyInitiativeListResponse` containing the linked initiative

### Implementation for User Story 1

- [X] T007 [US1] In `src/adp/strategy/initiatives.py`: `ControlMappingRef` model (`control_id`, `target_type: MappingTargetType`, `target_id: str | None`, `compliance_status: ComplianceStatus`, `evidence_ref: str | None`, `assessed_at: date | None`, `extra="forbid"` — importing `MappingTargetType`/`ComplianceStatus` from `adp.compliance.models`, a type-only cross-package import, data-model.md); `ControlMappingNotFoundError(control_id, target_type, target_id)` exception; `StrategyInitiative` gains `control_mappings: list[ControlMappingRef] = []` (mirrors `objective_ids`'s own established convention). No request-body model — the link/unlink routes address the target entirely via path params (`control_id`/`target_type`/`target_id`), mirroring `link_initiative_objective`'s own path-param-only shape, not a JSON-body shape
- [X] T008 [US1] In `src/adp/strategy/initiatives.py`: five DML-only `sa.Table()` definitions — `_initiative_control_capability_mapping`, `_initiative_control_application_mapping`, `_initiative_control_design_mapping`, `_initiative_control_pattern_mapping`, `_initiative_control_organization_mapping` — matching T001's migration schema exactly (no PK/FK in Python, per this package's existing convention)
- [X] T009 [US1] In `src/adp/strategy/initiatives.py`: `link_initiative_control_mapping(initiative_id: str, control_id: str, target_type: MappingTargetType, target_id: str | None, session) -> None` — dispatches to the matching one of T008's five tables by `target_type`; raises `ControlMappingNotFoundError` if a `SELECT` against T002's corresponding mirror table for `(control_id, target_id)` (or `control_id` alone for `organization`) finds no row; inserts, catching a unique-violation → `DuplicateLinkError` (mirrors `link_initiative_objective`'s existing catch shape) (depends on T002, T007, T008)
- [X] T010 [US1] In `src/adp/strategy/initiatives.py`: `unlink_initiative_control_mapping(initiative_id, control_id, target_type, target_id, session) -> None` — deletes from the matching table, raises `LinkNotFoundError` if no row matched (depends on T008)
- [X] T011 [US1] In `src/adp/strategy/initiatives.py`: `_linked_control_mappings(initiative_id: str, session) -> list[ControlMappingRef]` — for each of the five link tables, `SELECT` rows for this `initiative_id` JOINed to T002's matching mirror table (live `compliance_status`/`evidence_ref`/`assessed_at`), tag with the corresponding `MappingTargetType`, concatenate; wire the result into `get_initiative()`'s existing `StrategyInitiative(...)` construction as `control_mappings=await _linked_control_mappings(initiative_id, session)` alongside the existing `objective_ids=await _linked_objective_ids(...)` line (depends on T002, T007, T008)
- [X] T012 [US1] In `src/adp/strategy/initiatives.py`: `list_initiatives_for_control_mapping(control_id: str, target_type: MappingTargetType, target_id: str | None, session) -> StrategyInitiativeListResponse` — reverse lookup (called from `adp.compliance.router`, mirrors `list_objectives_for_design`'s exact docstring/shape convention): looks up linked `initiative_id`s from the matching one of T008's tables, then `get_initiative()` each (depends on T008, T011)
- [X] T013 [US1] In `src/adp/strategy/router.py`: `POST /initiatives/{initiative_id}/control-mappings/{target_type}/{control_id}` and `POST .../control-mappings/{target_type}/{control_id}/{target_id}` (the `organization` shape omits `target_id`) — 404 if `sinit.get_initiative(initiative_id)` is `None`; calls `sinit.link_initiative_control_mapping`; `ControlMappingNotFoundError`→404, `DuplicateLinkError`→409; on success returns the full updated `StrategyInitiative` (mirrors `link_initiative_objective`'s exact response shape, `strategy/router.py:532-551` — **not** the Objective-side bare-list convention); `DELETE` counterpart → 204, `LinkNotFoundError`→404; both under the existing `WRITE_BUSINESS_ARCH` prefix rule (no `enforcement.py` change); logs per the file's existing convention (depends on T009, T010)
- [X] T014 [US1] In `src/adp/compliance/router.py`: `GET /controls/{control_id}/mappings/{target_type}/{target_id}/initiatives` and `GET /controls/{control_id}/mappings/organization/initiatives` — `strategy_session: AsyncSession = Depends(_get_strategy_session)` (T003) plus `user: AuthenticatedUser = Depends(get_current_user)`; if `target_type == "application"` and `not is_permitted(user.role, ActionType.READ_APPLICATION_GOVERNANCE)` → 403 (spec.md FR-013 — a single-target 403, **not** the multi-row partial-filter T014-of-922's own forward-lookup uses, since this route is always scoped to one target already); else `sstore.control_exists(control_id)` → 404 if missing, then calls T012's `list_initiatives_for_control_mapping` (depends on T003, T012)
- [X] T015 [P] [US1] Extend `web/src/api/strategy.ts`: TS type `ControlMappingRef`; `StrategyInitiative` type gains `control_mappings: ControlMappingRef[]`; `useLinkInitiativeControlMapping(initiativeId)` / `useUnlinkInitiativeControlMapping(initiativeId)` mutations (POST/DELETE to T013's routes), invalidating the initiatives query
- [X] T016 [US1] Create `web/src/strategy/InitiativeControlMappingEditor.tsx`: props `initiative: StrategyInitiative`; uses `useLinkFeedback` (mirrors `InitiativeObjectiveLinkEditor.tsx`'s exact shape); renders each linked `ControlMappingRef` with a `compliance_status` badge + target description + "Remove"; a link form — Control search/select + target-type + target-id inputs — calling T015's link hook (depends on T015)
- [X] T017 [US1] Wire `InitiativeControlMappingEditor` into `web/src/strategy/InitiativeList.tsx`'s `InitiativeEditForm`, alongside the existing `InitiativeObjectiveLinkEditor` (no dedicated Initiative detail page exists — 916's own precedent) (depends on T016)
- [X] T018 [P] [US1] Extend `web/src/compliance/ControlMappingsEditor.tsx`: each rendered mapping row gains a read-only "Linked Initiatives" line (`GET .../mappings/{target_type}/{target_id}/initiatives`, T014), hidden if empty
- [X] T019 [P] [US1] Vitest coverage: `web/src/strategy/InitiativeControlMappingEditor.test.tsx` (link/unlink flow, status badge renders live value); extended `InitiativeList.test.tsx` for the new editor's presence in edit mode

**Checkpoint**: An Initiative can be linked directly to a compliance gap with zero Objective involvement,
the link is visible and status-live from both sides, and unlinking/duplicate/missing-target error paths all
behave per spec.md. Independently demonstrable as the MVP.

---

## Phase 4: User Story 2 - See why an objective exists (Priority: P2)

**Goal**: An authorized user can link a Strategic Objective to one or more Controls, recording that the
objective is regulatory-driven, visible from both the Objective's own side and the Control's own side.

**Independent Test**: Link one Objective to two different Controls (from different Frameworks), confirm
both links are visible from the Objective's side and each Control's own side, then unlink one and confirm
only that link disappears (spec.md US2 Acceptance Scenarios; quickstart.md Scenario 6, 7 (Objective-side
case)).

### Tests for User Story 2 (write first — ART-IV)

- [X] T020 [P] [US2] Unit tests in `tests/unit/strategy/test_control_links.py`: `link_objective_control()` raises `DuplicateLinkError` on a repeat link; `unlink_objective_control()` raises `LinkNotFoundError` when the pair isn't linked
- [X] T021 [P] [US2] Contract tests in `tests/contract/test_strategy_compliance_links_api.py`: `POST /objectives/{id}/controls` → 201, body is the updated `control_ids` list; repeat → 409; unknown `objective_id`/`control_id` → 404; `DELETE /objectives/{id}/controls/{control_id}` → 204, then 404 on repeat; `GET /compliance/controls/{control_id}/objectives` → 200 `StrategicObjectiveListResponse` containing the linked objective; unknown `control_id` → 404

### Implementation for User Story 2

- [X] T022 [P] [US2] In `src/adp/strategy/models.py`: `ObjectiveControlLinkCreate` model (`control_id: str`, `extra="forbid"`); `StrategicObjective` gains `control_ids: list[str] = []` (mirrors `design_ids`/`application_ids`'s own established convention)
- [X] T023 [US2] In `src/adp/strategy/store.py`: `_objective_control_links` DML-only `sa.Table()` (matches T001's migration schema); `link_objective_control(objective_id, control_id, session) -> None` (mirrors `link_objective_design`'s exact insert-and-catch shape, `DuplicateLinkError` on conflict); `unlink_objective_control(objective_id, control_id, session) -> None` (mirrors `unlink_objective_design`, `LinkNotFoundError` if no row matched); `_linked_control_ids(objective_id, session) -> list[str]`, wired into the existing objective-row-assembly function alongside `_linked_design_ids`/`_linked_application_ids` (depends on T022)
- [X] T024 [US2] In `src/adp/strategy/store.py`: `list_objectives_for_control(control_id: str, session) -> StrategicObjectiveListResponse` — reverse lookup (called from `adp.compliance.router`, mirrors `list_objectives_for_design`'s exact shape) (depends on T023)
- [X] T025 [US2] In `src/adp/strategy/router.py`: `POST /objectives/{objective_id}/controls` — 404 if `sstore.get_objective` is `None`; 404 if `sstore.control_exists` (T002) is `False`; calls `sstore.link_objective_control`, `DuplicateLinkError`→409; returns the updated `objective.control_ids` (mirrors `link_objective_design`'s exact bare-list response shape); `DELETE /objectives/{objective_id}/controls/{control_id}` → 204, `LinkNotFoundError`→404; both under the existing `WRITE_BUSINESS_ARCH` prefix rule (depends on T002, T023)
- [X] T026 [US2] In `src/adp/compliance/router.py`: `GET /controls/{control_id}/objectives` — `strategy_session: AsyncSession = Depends(_get_strategy_session)` (T003); 404 if `sstore.control_exists(control_id)` is `False`; else `sstore.list_objectives_for_control(control_id, strategy_session)` — ungated beyond general platform read access (an abstract Control carries no target-entity sensitivity of its own, unlike T014's route) (depends on T003, T024)
- [X] T027 [P] [US2] Extend `web/src/api/strategy.ts`: `StrategicObjective` type gains `control_ids: string[]`; `useLinkObjectiveControl(objectiveId)` / `useUnlinkObjectiveControl(objectiveId)` mutations (POST/DELETE to T025's routes)
- [X] T028 [US2] Create `web/src/strategy/ObjectiveControlLinkEditor.tsx`: mirrors `ObjectiveDesignLinkEditor.tsx`'s exact shape (`useLinkFeedback`, Control search/select, linked-list + "Remove") (depends on T027)
- [X] T029 [US2] Wire `ObjectiveControlLinkEditor` into `web/src/strategy/ObjectiveDetail.tsx`, as a sixth "Linked Controls" section alongside the existing five (Capabilities/Value Streams/Designs/Applications/Initiatives) (depends on T028)
- [X] T030 [P] [US2] Extend `web/src/compliance/ControlTree.tsx`: each control row gains a read-only "Linked Objectives" line (`GET .../controls/{id}/objectives`, T026), hidden if empty, alongside the existing `ControlMappingsEditor`
- [X] T031 [P] [US2] Vitest coverage: `web/src/strategy/ObjectiveControlLinkEditor.test.tsx` (link/unlink flow); extended `ObjectiveDetail.test.tsx` for the new section's presence

**Checkpoint**: Both user stories independently functional — an Objective's regulatory driver is visible
from both sides, and an Initiative's remediation work is visible from both sides with always-live status.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [X] T032 [P] Extend `tests/authz/test_enforcement.py`: `test_reviewer_denied_strategy_control_link_write` (403 for a REVIEWER-role POST to either T013's or T025's routes, mirroring COMPLY-01's own `test_reviewer_denied_compliance_write` shape); `test_application_targeted_initiative_lookup_requires_governance_permission` (403 for a role lacking `READ_APPLICATION_GOVERNANCE` on T014's route when `target_type == "application"`, role-overridden `TestClient` — no dev-mode `X-Role` header exists, matching 921/922's own established verification approach)
- [X] T033 [P] Integration tests (testcontainers PostgreSQL) in `tests/integration/test_strategy_compliance_links_api.py`: `test_delete_control_cascades_objective_link_and_all_initiative_mapping_tables` (delete a `Control` that has both an `ObjectiveControlMapping` and, via an existing `ControlMapping`, an `InitiativeControlMapping` — assert both are gone, Objective and Initiative themselves survive); `test_delete_control_mapping_cascades_only_its_own_initiative_link` (delete one `ControlMapping` row directly — via COMPLY-02's existing `delete_*_mapping` — assert only the `InitiativeControlMapping` referencing that specific `(control_id, target)` pair is gone, a sibling link on a *different* target for the same Control survives); `test_delete_objective_or_initiative_cascades_its_own_links_only`
- [X] T034 Manually run quickstart.md's 8 scenarios against a running local stack (`ADP_AUTH_ENABLED=false`); Scenario 4's `READ_APPLICATION_GOVERNANCE` 403 case is exercised via `tests/authz` (T032) rather than curl, matching this session's own established precedent (no dev-mode `X-Role` header exists)
- [X] T035 Run the full regression suite: `pytest tests/ --ignore=tests/integration -q`, `ruff check src/`, `mypy src/`, `cd web && npx vitest run && npx tsc --noEmit` — confirm no regressions and no new lint/type errors
- [X] T036 Confirm `adp-generate --check` is clean (schema drift gate — `ArchitectureDescription`'s own schema is untouched by this feature, but the gate must still pass)
- [X] T037 Replace the auto-generated `925-strategy-compliance-linkage: Added ...` stub entries in `CLAUDE.md` (Active Technologies + Recent Changes) with a proper hand-written implementation narrative at commit time, mirroring `specs/924-compliance-rollup-reporting/tasks.md`'s own T027 precedent

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup (needs the physical `control_*_mapping`/`controls` tables to
  mirror against, and `strategy_initiatives`/`strategic_objectives` for the FK targets) — BLOCKS both user
  stories.
- **User Stories (Phase 3–4)**: Both depend on Foundational only. **US1 and US2 are independent of each
  other** — different Strategy-side files (`initiatives.py` vs. `models.py`/`store.py`), different new
  routes on both `adp.strategy.router` and `adp.compliance.router`, different frontend components. Either
  can be built first, or both in parallel by different contributors — priority order (P1 → P2) is a
  delivery-sequencing choice here, not a code-level dependency.
- **Polish (Phase 5)**: Depends on both user stories being complete (cascade tests exercise both link
  shapes together).

### Within Each User Story

- Tests written and confirmed failing (`ImportError`, or wrong/missing behavior) before implementation (ART-IV).
- Store/module-level functions before router endpoints; backend endpoint before the frontend hook that
  calls it; hook before the component that uses it; component before its own test.

### Parallel Opportunities

- T002 and T003 (Foundational) can run in parallel — different files.
- T004 depends on T002 landing first (needs the mirror tables to seed against).
- T005/T006 (US1 tests) can run in parallel with each other.
- T007–T012 all touch `initiatives.py` — sequential within one contributor, though T007 (models) unblocks
  T008 (tables) which unblocks T009–T012, so a team could still split model-writing from function-writing.
- T015 (frontend types/hooks) can be drafted in parallel with T009–T014 once T007's `ControlMappingRef`
  shape is settled, since it only needs the *contract*, not the running backend.
- T018 (compliance-side UI) and T015–T017 (strategy-side UI) are different files — parallel.
- T020/T021 (US2 tests) can run in parallel with each other, and with all of Phase 3 (US1) once
  Foundational is done.
- T027 (frontend types/hooks) can run in parallel with T023–T026 once T022's model shape is settled.
- T030 (compliance-side UI) and T027–T029 (strategy-side UI) are different files — parallel.
- T032, T033 (Polish) can run in parallel with each other — different files.

---

## Parallel Example: Foundational Phase

```bash
# Different files, no dependency between them:
Task: "Read-only compliance-schema mirrors + control_exists() in src/adp/strategy/store.py"
Task: "_get_strategy_session() dependency in src/adp/compliance/router.py"
```

## Parallel Example: User Story 1 + User Story 2 Together (post-Foundational)

```bash
# Two contributors, or one contributor working both in sequence without cross-dependency:
Task: "US1 — Initiative remediation loop: T005/T006 tests, then T007–T019 implementation"
Task: "US2 — Objective regulatory driver: T020/T021 tests, then T022–T031 implementation"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (migration).
2. Complete Phase 2: Foundational (compliance-schema mirrors, cross-package session dependency).
3. Complete Phase 3: User Story 1 (Initiative ↔ ControlMapping, both directions, API + UI).
4. **STOP and VALIDATE**: Run quickstart.md Scenarios 1–5 against a live stack.
5. Deploy/demo if ready — the highest-value link in the bundle (the remediation loop) already works
   end to end, with zero Objective involvement required.

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. Add US1 → test independently → deploy/demo (MVP!).
3. Add US2 → test independently → deploy/demo (audit-narrative "why does this objective exist" now
   answerable directly).
4. Add Polish → full cascade coverage across both link shapes + authz completeness.

### Parallel Team Strategy

With multiple developers, once Foundational is done: Developer A takes US1 (five parallel link tables, the
larger surface); Developer B takes US2 (one link table, smaller surface) — the two share no file beyond the
already-complete Foundational phase, so both can proceed fully in parallel with no coordination beyond
merge order.

---

## Notes

- [P] tasks = different files, no dependencies.
- [Story] label maps task to specific user story for traceability.
- Verify tests fail before implementing.
- Commit after each task or logical group.
- Stop at either checkpoint to validate that story independently.
- `ThemeFrameworkMapping` (the bundle's third, deferred link) has **no task in this file** — tracked
  separately as bead `ADP-1ox`, per the 2026-08-19 clarification recorded in spec.md.
