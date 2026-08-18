# Tasks: Compliance Framework & Control Registry (COMPLY-01)

**Input**: Design documents from `/specs/921-compliance-framework-registry/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓, quickstart.md ✓

**Tests**: Mandatory (ART-IV, per `.specify/templates/tasks-template.md`). Test tasks appear before their
implementation counterparts in every user-story phase and must be written and verified to fail first.

**Organization**: Tasks grouped by user story (US1 = Register a framework, US2 = Build out a control
catalog, US3 = Browse and maintain, incl. cascading delete). Each story is independently testable, per the
FR-to-acceptance-scenario mapping confirmed directly against spec.md (delete endpoints map to US3's
acceptance scenarios, not US1/US2's — neither story's own acceptance scenarios exercise delete).

---

## Phase 1: Setup (Migration + Package Skeleton)

**Purpose**: Database schema and package/router scaffolding every user story depends on.

- [X] T001 Create Alembic migration in `src/adp/store/migrations/versions/032_compliance_framework_registry.py` (`revision = "032"`, `down_revision = "031"` — confirmed head, research.md D7): `CREATE TABLE regulatory_frameworks` (id VARCHAR(36) PK, name VARCHAR(255) NOT NULL, jurisdiction VARCHAR(255) NOT NULL, authority VARCHAR(255) NOT NULL, version VARCHAR(100) NOT NULL, effective_date DATE nullable, source_url TEXT nullable, created_at/updated_at TIMESTAMPTZ NOT NULL DEFAULT now()); `CREATE TABLE controls` (id VARCHAR(36) PK, framework_id VARCHAR(36) NOT NULL REFERENCES regulatory_frameworks(id) ON DELETE CASCADE, parent_id VARCHAR(36) nullable REFERENCES controls(id) ON DELETE CASCADE, code VARCHAR(100) NOT NULL, title VARCHAR(255) NOT NULL, description TEXT nullable, position INTEGER NOT NULL DEFAULT 0, created_at/updated_at TIMESTAMPTZ NOT NULL DEFAULT now(), UNIQUE(framework_id, code)); index `ix_controls_framework_id` on `framework_id`; index `ix_controls_framework_parent_position` on `(framework_id, parent_id, position)`; `downgrade()` drops `controls` then `regulatory_frameworks`
- [X] T002 [P] Create package skeleton `src/adp/compliance/__init__.py` (empty, mirrors `adp/business/__init__.py`)
- [X] T003 Register an empty `APIRouter(prefix="/api/v1/compliance", tags=["compliance"])` in `src/adp/compliance/router.py` and add `app.include_router(compliance_router_module.router)` to `src/adp/api/app.py` alongside the other domain routers (endpoints are added to this router in later phases, not here)

**Checkpoint**: Migration applies cleanly (`alembic upgrade head` then `alembic downgrade -1` then `alembic upgrade head` again); package importable; router mounted with zero routes.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Typed models and authorization plumbing every user story's endpoints depend on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T004 [P] Create `src/adp/compliance/models.py` with ALL Pydantic v2 models for both entities (`extra="forbid"` on every model, per ART-XIII — see data-model.md for the exact field list): `RegulatoryFramework` (read model), `RegulatoryFrameworkDetail(RegulatoryFramework)` with `controls: list["ControlNode"] = []`, `RegulatoryFrameworkCreate` (name/jurisdiction/authority/version required + non-blank validator, effective_date/source_url optional), `RegulatoryFrameworkUpdate` (all fields optional), `RegulatoryFrameworkListResponse`; `Control` (read model), `ControlNode(Control)` with `children: list["ControlNode"] = []`, `ControlCreate` (parent_id optional, code/title/description required + non-blank validator, position default 0), `ControlUpdate` (all fields optional, code/title non-blank validator when provided); typed exceptions `DuplicateControlCodeError`, `CyclicParentError`, `CrossFrameworkParentError`, `ParentNotFoundError`; call `RegulatoryFrameworkDetail.model_rebuild()` / `ControlNode.model_rebuild()` as needed for the forward references between the two classes
- [X] T005 [P] Add `ActionType.WRITE_COMPLIANCE = "write_compliance"` to `src/adp/authz/roles.py` (with a comment referencing Clarification Session 2026-08-17 Q1 and research.md D4, matching the existing comment style for `WRITE_DIAGRAM`)
- [X] T006 In `src/adp/authz/permissions.py`: add changelog entry `1.9.0 — added ActionType.WRITE_COMPLIANCE (COMPLY-01), granted to Solution/Technical Architect; Enterprise Architect and Platform Admin receive it via their existing wildcard grants — no change to either entry`; bump `PERMISSIONS_VERSION = "1.9.0"`; add `ActionType.WRITE_COMPLIANCE` to both `PersonaRole.SOLUTION_ARCHITECT` and `PersonaRole.TECHNICAL_ARCHITECT`'s grant sets (depends on T005)
- [X] T007 Add `("/api/v1/compliance/", ActionType.WRITE_COMPLIANCE)` to the route-prefix table in `src/adp/authz/enforcement.py`, in the same block as the `/api/v1/business/` and `/api/v1/applications` prefix rules (depends on T005)
- [X] T008 [P] Add unit tests for the new models in `tests/unit/compliance/test_models.py`: blank `name`/`jurisdiction`/`authority`/`version` on `RegulatoryFrameworkCreate` → `ValidationError`; blank `code`/`title`/`description` on `ControlCreate` → `ValidationError`; extra field on any model → `ValidationError` (extra="forbid"); valid full create for both; `RegulatoryFrameworkCreate` with only required fields (no `effective_date`/`source_url`) is valid (depends on T004)
- [X] T009 [P] Extend `tests/authz/test_enforcement.py`'s completeness check to cover the new `/api/v1/compliance/` prefix rule and add `test_write_compliance_requires_permission` / `test_reviewer_denied_compliance_write` (mirroring the existing `test_reviewer_denied_governance_write` shape) (depends on T005, T006, T007)

**Checkpoint**: Models import cleanly with no forward-reference errors; `PERMISSIONS_VERSION` is `1.9.0`; authz completeness test passes with the new prefix mapped.

---

## Phase 3: User Story 1 - Register a regulatory framework (Priority: P1) 🎯 MVP

**Goal**: An authorized user can create, list, view, and edit a `RegulatoryFramework` record.

**Independent Test**: Create a framework record with its identifying fields and confirm it appears,
correctly, in the list of tracked frameworks — delivers value on its own as a system-of-record for "which
frameworks are we tracking," even before any controls are entered.

### Tests for User Story 1 (write first — ART-IV)

- [X] T010 [P] [US1] Contract test in `tests/contract/test_compliance_registry_api.py`: `POST /api/v1/compliance/frameworks` response validates against `RegulatoryFramework`; `GET /api/v1/compliance/frameworks` validates against `RegulatoryFrameworkListResponse`; `GET /api/v1/compliance/frameworks/{id}` validates against `RegulatoryFrameworkDetail` (with `controls: []`); `PATCH` response validates against `RegulatoryFramework`; a write request without `WRITE_COMPLIANCE` → 403 (writer-role fixture reused from `tests/authz/`)
- [X] T011 [P] [US1] Integration test in `tests/integration/test_compliance_api.py`: `test_framework_create_201` — POST with all fields, assert 201 + id present; `test_framework_create_no_effective_date` — POST omitting `effective_date`/`source_url`, assert 201 and both null (Edge Case: perpetually-current framework is not an error); `test_framework_list_shows_created` — create two frameworks, GET list, assert both present with correct fields; `test_framework_detail_empty_controls` — GET by id on a framework with no controls yet, assert `controls == []`; `test_framework_update_200` — PATCH `authority`/`source_url`, assert updated values, assert unrelated fields unchanged; `test_framework_404` — GET/PATCH nonexistent id → 404; `test_framework_blank_field_422` — POST with blank `name` → 422; `test_framework_duplicate_name_allowed` — two frameworks with the same `name` but different `version` both succeed (Edge Case)

### Implementation for User Story 1

- [X] T012 [US1] In `src/adp/compliance/store.py`: SQLAlchemy Core `_frameworks` Table definition (mirrors `_capabilities`'s shape in `adp/business/store.py`); `_controls` Table definition (needed now for the detail-fetch JOIN, even though no create/update/delete Control functions exist until Phase 4); `create_framework(data: RegulatoryFrameworkCreate, session) -> RegulatoryFramework`; `list_frameworks(session) -> list[RegulatoryFramework]`; `get_framework_detail(framework_id: str, session) -> RegulatoryFrameworkDetail | None` — fetches the framework row plus every control row where `framework_id` matches, assembles the `parent_id`-nested `ControlNode` tree ordered by `position` (correctly returns `controls: []` when the controls table has no matching rows, which is every case until Phase 4 populates it — this function does not need revisiting in Phase 4); `update_framework(framework_id: str, data: RegulatoryFrameworkUpdate, session) -> RegulatoryFramework | None` (uses `model_fields_set` to distinguish an omitted field from an explicit-null, same pattern as `update_capability`)
- [X] T013 [US1] In `src/adp/compliance/router.py`: `POST /frameworks` → 201 `RegulatoryFramework`, 422 on validation failure, requires `WRITE_COMPLIANCE`; `GET /frameworks` → 200 `RegulatoryFrameworkListResponse`, open read; `GET /frameworks/{framework_id}` → 200 `RegulatoryFrameworkDetail`, 404, open read; `PATCH /frameworks/{framework_id}` → 200 `RegulatoryFramework`, 404, 422, requires `WRITE_COMPLIANCE`; each mutating endpoint emits `logger.info()` with actor/framework_id/action, matching `adp/business/router.py`'s existing logging convention
- [X] T014 [P] [US1] Create `web/src/api/compliance.ts`: TypeScript interfaces `RegulatoryFramework`, `RegulatoryFrameworkDetail` (extends with `controls: ControlNode[]`), `RegulatoryFrameworkCreate`, `RegulatoryFrameworkUpdate`, `RegulatoryFrameworkListResponse`, `Control`, `ControlNode` (extends `Control` with `children: ControlNode[]`) — mirrors `web/src/api/business.ts`'s interface shape; hooks `useFrameworks()` (queryKey `["compliance-frameworks"]`), `useFramework(id: string | null)` (enabled `!!id`, queryKey `["compliance-framework", id]`), `useCreateFramework()` (invalidates `["compliance-frameworks"]`), `useUpdateFramework(id: string)` (invalidates `["compliance-frameworks"]` + `["compliance-framework", id]`)
- [X] T015 [US1] Create `web/src/compliance/CompliancePage.tsx`: calls `useFrameworks()`; loading/error states; renders each framework as a card row (name, jurisdiction, authority, version); "Add Framework" button opens an inline create form (name/jurisdiction/authority/version required, effective_date/source_url optional) using `useCreateFramework()`; clicking a row calls `onSelectFramework(id)` (props: `onSelectFramework: (id: string) => void`)
- [X] T016 [US1] Create `web/src/compliance/FrameworkDetail.tsx`: props `frameworkId: string; onBack: () => void`; calls `useFramework(frameworkId)`; shows framework metadata (name, jurisdiction, authority, version, effective_date, source_url) with an edit button opening an inline `useUpdateFramework(frameworkId)` form; renders a "Controls" section showing "No controls yet" when `controls` is empty (control tree UI itself lands in Phase 4); back button calls `onBack`
- [X] T017 [US1] Add `"compliance"` to the `AppView` union in `web/src/shell/index.ts`; add `{ view: "compliance", label: "Compliance", icon: "shield", hue: "biz" }` to the nav item list in `web/src/ui/AppShell.tsx` (near `governance`, per the source doc's framing of Compliance as governance-adjacent); add the `case "compliance":` branch in `web/src/App.tsx`'s view switch rendering `<CompliancePage onSelectFramework={...} />` / `<FrameworkDetail ... />` following the same selected-id-in-state pattern as `BusinessPage`'s domain tab (T009–T011 in the 035 precedent)

**Checkpoint**: Framework CRUD (minus delete) fully functional end to end — create/list/view/edit all work via API and UI. This is independently demonstrable as the MVP.

---

## Phase 4: User Story 2 - Build out a framework's control catalog (Priority: P2)

**Goal**: An authorized user can add controls (top-level or nested) under a framework, with framework-scoped
code uniqueness and sibling ordering.

**Independent Test**: Add a mix of top-level and nested controls under an existing framework and confirm
each appears with the correct code, title, description, and position in the hierarchy.

### Tests for User Story 2 (write first — ART-IV)

- [X] T018 [P] [US2] Contract test in `tests/contract/test_compliance_registry_api.py`: `POST /api/v1/compliance/frameworks/{id}/controls` response validates against `Control`; `PATCH /api/v1/compliance/controls/{id}` response validates against `Control`; both require `WRITE_COMPLIANCE`
- [X] T019 [P] [US2] Integration test in `tests/integration/test_compliance_api.py`, reproducing the GDPR granularity example from the source doc: `test_control_create_top_level_201`; `test_control_create_nested_child` — create "Art. 5" then six children "Art. 5(1)(a)"–"(f)", GET framework detail, assert `art5.children` has exactly 6 entries in `position` order and "Art. 33" (created separately) has `children == []`; `test_control_duplicate_code_same_framework_409` — POST a second control with an already-used `code` under the same `framework_id` → 409; `test_control_same_code_different_framework_201` — same `code` under a *different* framework succeeds; `test_control_cyclic_parent_422` — PATCH a control's `parent_id` to itself → 422; `test_control_cross_framework_parent_422` — PATCH a control's `parent_id` to a control belonging to a different framework → 422; `test_control_parent_not_found_404` — POST with a nonexistent `parent_id` → 404; `test_control_reposition` — PATCH `position` on siblings, GET framework detail, assert children ordered per the new positions; `test_control_blank_field_422` — POST with blank `code`/`title`/`description` → 422

### Implementation for User Story 2

- [X] T020 [US2] In `src/adp/compliance/store.py`: `create_control(framework_id: str, data: ControlCreate, session) -> Control` — if `data.parent_id` is set: fetch the parent, raise `ParentNotFoundError` if missing, raise `CrossFrameworkParentError` if `parent.framework_id != framework_id` (research.md D5); insert row, catching the DB's `UNIQUE(framework_id, code)` `IntegrityError` and re-raising as `DuplicateControlCodeError` (research.md D6, mirrors `DuplicateLinkError`'s existing translation pattern in `adp.business.store`); `update_control(control_id: str, data: ControlUpdate, session) -> Control | None` — when `parent_id` is being changed: re-run the same `ParentNotFoundError`/`CrossFrameworkParentError` checks as create, PLUS a cycle check that walks up from the proposed new parent toward the root, raising `CyclicParentError` if the control being updated is encountered (research.md D5); when `code` is being changed: re-run the same uniqueness check as create (research.md D6); uses `model_fields_set` for optional-field semantics, same pattern as `update_capability`/`update_framework`
- [X] T021 [US2] In `src/adp/compliance/router.py`: `POST /frameworks/{framework_id}/controls` → 201 `Control`, catch `ParentNotFoundError`→404, `CrossFrameworkParentError`/`CyclicParentError`→422, `DuplicateControlCodeError`→409, requires `WRITE_COMPLIANCE`; `PATCH /controls/{control_id}` → 200 `Control`, same exception→status mapping, 404 if the control itself doesn't exist, requires `WRITE_COMPLIANCE`; both emit `logger.info()` per the existing convention
- [X] T022 [P] [US2] Extend `web/src/api/compliance.ts`: `ControlCreate`, `ControlUpdate` interfaces; `useCreateControl(frameworkId: string)` mutation (invalidates `["compliance-framework", frameworkId]`); `useUpdateControl(controlId: string, frameworkId: string)` mutation (invalidates `["compliance-framework", frameworkId]`)
- [X] T023 [US2] Create `web/src/compliance/ControlTree.tsx`: props `frameworkId: string; controls: ControlNode[]`; recursively renders each control (code, title, description, indented by depth) with its `children`; "Add Control" action per node (and one at the framework's top level) opens an inline form (code/title/description required, parent pre-filled from context) using `useCreateControl(frameworkId)`; inline edit action per node opens a form (title/description/position, `useUpdateControl`) — mirrors `CapabilityTree.tsx`'s recursive-render shape
- [X] T024 [US2] Wire `ControlTree` into `web/src/compliance/FrameworkDetail.tsx`: replace the "No controls yet" placeholder with `<ControlTree frameworkId={frameworkId} controls={framework.controls} />` when `controls.length > 0`, keep the empty-state message otherwise

**Checkpoint**: Control catalog build-out fully functional — top-level and nested controls, framework-scoped uniqueness, cycle/cross-framework rejection, sibling ordering all work via API and UI.

---

## Phase 5: User Story 3 - Browse and maintain the control catalog (Priority: P3)

**Goal**: An authorized user can browse a framework's full control hierarchy end to end, and delete
frameworks/controls with the deletion's scope (cascading descendants) disclosed before it happens.

**Independent Test**: Browse an existing framework's control tree end-to-end, edit a control's title, and
delete a leaf control, then confirm the catalog reflects each change correctly.

### Tests for User Story 3 (write first — ART-IV)

- [X] T025 [P] [US3] Contract test in `tests/contract/test_compliance_registry_api.py`: `DELETE /api/v1/compliance/frameworks/{id}` → 204, requires `WRITE_COMPLIANCE`; `DELETE /api/v1/compliance/controls/{id}` → 204, requires `WRITE_COMPLIANCE`
- [X] T026 [P] [US3] Integration test in `tests/integration/test_compliance_api.py`: `test_delete_control_cascades_to_descendants` — build a 3-level control chain (grandparent→parent→child) under a framework, DELETE the grandparent, GET framework detail, assert none of the 3 codes remain (verifies the self-referencing `ON DELETE CASCADE` recurses through multiple generations, not just one level); `test_delete_control_leaf_only` — delete a leaf control, assert its siblings and ancestors are unaffected; `test_delete_framework_cascades_to_all_controls` — build a multi-level hierarchy, DELETE the framework, assert 404 on the framework and (via a direct store-level check, since the framework itself is gone) that no orphaned control rows remain; `test_delete_framework_404` / `test_delete_control_404` — deleting a nonexistent id → 404; `test_browse_full_hierarchy` — build the GDPR Art. 5 (6 children) + Art. 33 (leaf) shape from Phase 4, GET framework detail, assert the full nested structure round-trips correctly in one read
- [X] T027 [P] [US3] Frontend test in `web/src/compliance/ControlTree.test.tsx` and `web/src/compliance/FrameworkDetail.test.tsx`: deleting a control with children shows a confirmation naming the descendant count computed from the already-fetched tree (research.md D3) before calling the delete mutation; deleting a framework with controls shows the equivalent confirmation; cancelling the confirmation issues no API call

### Implementation for User Story 3

- [X] T028 [US3] In `src/adp/compliance/store.py`: `delete_framework(framework_id: str, session) -> bool` (plain `DELETE FROM regulatory_frameworks WHERE id = ...`; cascading to `controls` is handled entirely by the migration's `ON DELETE CASCADE`, confirmed by T026 — no application-layer recursion needed, research.md D2); `delete_control(control_id: str, session) -> bool` (same shape, cascading to descendant controls via the self-referencing `ON DELETE CASCADE`)
- [X] T029 [US3] In `src/adp/compliance/router.py`: `DELETE /frameworks/{framework_id}` → 204, 404, requires `WRITE_COMPLIANCE`; `DELETE /controls/{control_id}` → 204, 404, requires `WRITE_COMPLIANCE`; both emit `logger.info()` per the existing convention
- [X] T030 [P] [US3] Extend `web/src/api/compliance.ts`: `useDeleteFramework()` mutation (invalidates `["compliance-frameworks"]`); `useDeleteControl(frameworkId: string)` mutation (invalidates `["compliance-framework", frameworkId]`)
- [X] T031 [US3] Add delete actions with client-side scope disclosure (research.md D3 — no new backend endpoint): in `web/src/compliance/ControlTree.tsx`, a "Delete" action per node that recursively counts descendants from the already-fetched `children` array and shows a confirm dialog ("Deleting '{code}' will also remove N descendant control(s). Continue?") before calling `useDeleteControl`; in `web/src/compliance/FrameworkDetail.tsx`, a "Delete Framework" action that counts every control in the already-fetched tree (flattened) and shows the equivalent confirmation before calling `useDeleteFramework()` and `onBack()`

**Checkpoint**: All three user stories independently functional. Full browse, edit, and cascading delete (with scope disclosure) work end to end via API and UI.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T032 Run `adp-generate --check` and confirm it is a no-op (this registry is not part of the `ArchitectureDescription`/`generate.py` pipeline — plan.md's Constitution Check flags this as worth confirming rather than assuming)
- [X] T033 Run quickstart.md scenarios 1–6 via curl against a running local API server; verify all expected status codes and response shapes match `contracts/compliance-api.md`
- [ ] T034 [P] **BLOCKED** — Manually verify the browser flow via Playwright/webapp-testing: register a framework, build a nested control catalog (Art. 5 + 6 children, Art. 33 standalone), edit a control's title, delete a leaf control (confirm dialog shows correct count), delete the framework (confirm dialog shows total descendant count) — against a running local stack. Attempted; blocked by a pre-existing Playwright browser-profile lock (`SingletonLock` pointing to a Windows-host process) outside this session's control — left un-run rather than force-clearing a lock that might belong to a real session. `tsc` (clean), the full Vitest suite (489 passing, incl. 6 new tests covering the exact confirm-dialog logic this scenario would exercise), and direct live-API verification of every backend behavior these UI actions trigger substitute in the interim. Re-run this task once a browser session is free.
- [X] T035 Update `docs/solution-architecture.md`: add migration `032` row to the migrations table; add a new "Compliance" section describing `RegulatoryFramework`/`Control`, the framework-scoped uniqueness constraint, the unbounded self-referencing hierarchy, and the cascade-delete behavior (contrasted with Business Capability's reject-on-children precedent); note `WRITE_COMPLIANCE` in the permissions table (`PERMISSIONS_VERSION` 1.9.0)
- [X] T036 Update `CLAUDE.md`'s "Recent Changes" section with a COMPLY-01 entry following the established narrative-changelog format (package placement decision, delete-semantics deviation from Business Capability, new `WRITE_COMPLIANCE` permission, explicit note that COMPLY-02–05 remain unimplemented)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — T001 before T003 (router registration doesn't strictly need the migration, but is sequenced after it for a clean single "foundation applied" checkpoint); T002 parallel with T001
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all user stories. T004 and T005 are parallel with each other; T006/T007 depend on T005; T008 depends on T004; T009 depends on T005–T007
- **User Stories (Phase 3–5)**: All depend on Phase 2 completion
  - US1 (Phase 3): No dependency on US2/US3
  - US2 (Phase 4): Depends on US1's `_controls` table definition already existing in `store.py` (T012) and the `get_framework_detail` tree-assembly function it introduced — in practice, sequence Phase 4 after Phase 3
  - US3 (Phase 5): Depends on US1's frameworks existing (T012/T013) and US2's controls existing (T020/T021) to have anything meaningful to browse/delete — sequence after Phase 4
- **Polish (Phase 6)**: Depends on all three user stories being complete

### User Story Dependencies

- **US1 (P1)**: Can start after Phase 2. No dependency on US2/US3. Independently shippable as the MVP (framework catalog alone).
- **US2 (P2)**: Builds directly on US1's store/router file structure and the `_controls` table definition introduced in T012 — not parallelizable with US1 in practice, despite both nominally only depending on Phase 2, because they share `store.py`/`router.py`.
- **US3 (P3)**: Builds on both US1 and US2 — delete/browse operations need frameworks and controls to already exist. Sequence last.

### Parallel Opportunities

- T002 (package skeleton) runs in parallel with T001 (migration)
- T004 (models) and T005 (new ActionType) run in parallel in Phase 2
- T008 (model unit tests) runs in parallel with T006/T007 once T004/T005 land
- Within each user story phase, the two test tasks (contract + integration) marked [P] run in parallel with each other, and the frontend hook/type task marked [P] runs in parallel with backend store/router work once the API contract shape is settled
- T030 (frontend delete hooks) runs in parallel with T028 (backend delete store functions)

---

## Parallel Example: User Story 1

```bash
# Launch both tests for User Story 1 together:
Task: "Contract test for framework endpoints in tests/contract/test_compliance_registry_api.py"
Task: "Integration test for framework CRUD in tests/integration/test_compliance_api.py"

# Frontend types/hooks can start in parallel with backend store/router work:
Task: "Create web/src/api/compliance.ts with Framework types + hooks"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (T001–T003)
2. Complete Phase 2 (T004–T009) — models + authz, blocking but fast
3. Complete Phase 3 / US1 (T010–T017) — framework register/list/view/edit, with a reachable nav entry
4. **STOP and VALIDATE**: Register three frameworks (including one with no `effective_date`), confirm they list correctly, edit one, confirm the change persists.

### Incremental Delivery

1. Phase 1 + Phase 2 → Foundation ready (migration applied, models importable, `WRITE_COMPLIANCE` wired)
2. Phase 3 / US1 → Framework catalog live (MVP)
3. Phase 4 / US2 → Control catalog build-out live (the GDPR Art. 5/Art. 33 granularity scenario works end to end)
4. Phase 5 / US3 → Full browse + cascading delete with scope disclosure live
5. Phase 6 → Verified against a live stack and documented

### Note on Delete Endpoints

`DELETE /frameworks/{id}` and `DELETE /controls/{id}` are deliberately placed in Phase 5 (US3), not Phase 3
(US1) or Phase 4 (US2) — confirmed directly against spec.md: neither US1's nor US2's acceptance scenarios
exercise delete at all; US3's acceptance scenarios 3 and 4 are specifically the cascading-delete cases. This
keeps each phase's implementation matched exactly to what that story's own acceptance scenarios test, rather
than front-loading delete endpoints a story doesn't actually call for.
