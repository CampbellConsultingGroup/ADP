# Tasks: Control Mappings (Traceability Links) — COMPLY-02

**Input**: Design documents from `/specs/922-control-mappings/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓, quickstart.md ✓

**Tests**: Mandatory (ART-IV, per `.specify/templates/tasks-template.md`). Test tasks appear before their
implementation counterparts in every user-story phase and must be written and verified to fail first.

**Organization**: Tasks grouped by user story (US1 = Map a control to the entity it governs, US2 = Update a
mapping's assessment over time, US3 = Trace compliance coverage from either direction). Each story is
independently testable, per the FR-to-acceptance-scenario mapping confirmed against spec.md — US2 needs no
new endpoints at all (its acceptance scenarios exercise the same `PUT` routes US1 creates, per D3's upsert
design), and US3's four reverse-lookup routes are additive reads with no write-path dependency on US1/US2
beyond mapping rows existing to look up.

**A pre-existing naming collision, confirmed by direct reads before task-writing, not assumed**: two other
"compliance" concepts already exist in this codebase and MUST NOT be conflated with this spec's
`RegulatoryFramework`/`Control` domain — (1) `governance/ComplianceTab.tsx` shows LLM-as-Judge *validation
exception* findings (reserved for COMPLY-04's future rollup, a different concept); (2) `ApplicationDetail.tsx`'s
existing "Risk & Compliance" tab (`RiskPanel.tsx`) is APM's `risk_compliance_contribution` self-reported
score field (ADP-SPEC-038 US3), unrelated to regulatory-framework mapping. Task T028 below names the new
Application tab "Regulatory Compliance" specifically to avoid this collision.

---

## Phase 1: Setup (Migration)

**Purpose**: Database schema every user story depends on.

- [X] T001 Create Alembic migration in `src/adp/store/migrations/versions/033_control_mappings.py` (`revision = "033"`, `down_revision = "032"` — confirmed head, research.md D8): five tables per data-model.md — `control_capability_mapping` (control_id VARCHAR(36) FK→controls.id ON DELETE CASCADE, capability_id VARCHAR(36) FK→business_capabilities.id ON DELETE CASCADE, compliance_status TEXT NOT NULL DEFAULT 'not_assessed', evidence_ref TEXT nullable, assessed_at DATE nullable, assessed_by TEXT nullable, created_at TIMESTAMPTZ NOT NULL DEFAULT now(), PK(control_id, capability_id), CHECK `ck_ccm_status`); `control_application_mapping` (same shape, application_id VARCHAR(36) FK→applications.id, CHECK `ck_cam_status`); `control_design_mapping` (same shape, design_id **TEXT** FK→designs.id — matches designs.id's actual column type, CHECK `ck_cdm_status`); `control_pattern_mapping` (same shape, pattern_id **VARCHAR unbounded** FK→knowledge_items.id — matches knowledge_items.id's actual column type, CHECK `ck_cpm_status`); `control_organization_mapping` (control_id VARCHAR(36) FK→controls.id ON DELETE CASCADE **single-column PK**, compliance_status/evidence_ref/assessed_at/assessed_by/created_at as above, CHECK `ck_com_status`); indexes `ix_ccm_capability_id`, `ix_cam_application_id`, `ix_cdm_design_id`, `ix_cpm_pattern_id` on each table's non-control_id FK leg; `downgrade()` drops all five tables in reverse order

**Checkpoint**: Migration applies cleanly (`alembic upgrade head` then `alembic downgrade -1` then `alembic upgrade head` again).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Typed models, store table definitions, and existence-check helpers every user story's endpoints depend on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 [P] Extend `src/adp/compliance/models.py` (data-model.md) with: `ComplianceStatus(StrEnum)` (`COMPLIANT`, `PARTIAL`, `NON_COMPLIANT`, `NOT_ASSESSED`, `NOT_APPLICABLE`); `MappingTargetType(StrEnum)` (`CAPABILITY`, `APPLICATION`, `DESIGN`, `PATTERN`, `ORGANIZATION`); `ControlMapping` (read model: `control_id`, `target_type`, `target_id: str | None`, `compliance_status`, `evidence_ref: str | None`, `assessed_at: date | None`, `assessed_by: str | None`, `created_at`); `ControlMappingWrite` (`compliance_status` default `NOT_ASSESSED`, other three fields optional default `None`); `ControlMappingListResponse` (`items: list[ControlMapping]`, `total: int`); typed exceptions `ControlNotFoundError`, `MappingTargetNotFoundError(target_type, target_id)`, `InvalidPatternTargetError(target_id, actual_kind)`, `MappingNotFoundError` — every model `extra="forbid"` per ART-XIII
- [X] T003 [P] In `src/adp/compliance/store.py`: five DML-only `sa.Table()` definitions mirroring T001's schema exactly (`_control_capability_mapping`, `_control_application_mapping`, `_control_design_mapping`, `_control_pattern_mapping`, `_control_organization_mapping`); plus four narrow mirror `sa.Table()` definitions for existence/kind validation (research.md D4) — `_capabilities_mirror` (id only), `_applications_mirror` (id only), `_designs_mirror` (id only, `sa.Text()`), `_knowledge_items_mirror` (id + kind) — none of the four mirror tables duplicate columns beyond what validation needs
- [X] T004 In `src/adp/compliance/store.py`: `get_control(control_id: str, session) -> Control | None` (new — COMPLY-01 never needed a standalone getter outside `get_framework_detail`'s tree assembly); `capability_exists(capability_id: str, session) -> bool`, `application_exists(application_id: str, session) -> bool`, `design_exists(design_id: str, session) -> bool` (mirrors `adp.strategy.store`'s identical-shape helpers exactly); `get_knowledge_item_kind(pattern_id: str, session) -> str | None` (returns the row's `kind`, or `None` if the id doesn't exist — feeds both existence and the D5 kind check in one query) (depends on T002, T003)
- [X] T005 [P] Unit tests in `tests/unit/compliance/test_mapping_models.py`: `ControlMappingWrite()` with no args is valid and defaults `compliance_status` to `not_assessed`; an invalid `compliance_status` string raises `ValidationError`; extra field on `ControlMapping`/`ControlMappingWrite` → `ValidationError` (extra="forbid"); `ControlMapping` with `target_type="organization"` and `target_id=None` is valid; `MappingTargetNotFoundError`/`InvalidPatternTargetError` construct with the expected `.args`/message content used by router error translation (depends on T002)

**Checkpoint**: Models import cleanly; store tables + mirror tables + existence helpers available; unit tests pass.

---

## Phase 3: User Story 1 - Map a control to the entity it governs (Priority: P1) 🎯 MVP

**Goal**: An authorized user can map a `Control` to a Capability, Application, Design, Pattern, or the
estate-wide scope, recording a compliance status and optional evidence, and retrieve that mapping from the
Control's own side.

**Independent Test**: Map a Control to an Application with a `compliant` status and evidence reference,
then confirm the mapping is retrievable from `GET /compliance/controls/{control_id}/mappings` — delivers
value on its own as a queryable compliance record, even before any reverse lookup or update-in-place
behavior is exercised.

### Tests for User Story 1 (write first — ART-IV)

- [X] T006 [P] [US1] Contract test in `tests/contract/test_compliance_mappings_api.py`: `PUT .../mappings/capabilities/{id}` response validates against `ControlMapping` with `target_type == "capability"`; same shape check for `.../applications/{id}`, `.../designs/{id}`, `.../patterns/{id}`, `.../organization` (`target_id is None`); `GET .../controls/{control_id}/mappings` validates against `ControlMappingListResponse`; a `PUT` without `WRITE_COMPLIANCE` → 403 (writer-role fixture reused from `tests/authz/`)
- [X] T007 [P] [US1] Integration test in `tests/integration/test_compliance_mappings_api.py`: `test_map_control_to_capability_201` (Acceptance Scenario 1 variant); `test_map_without_evidence_ok` — PUT with only `compliance_status`, assert 200 and `evidence_ref is None` (FR-004, Acceptance Scenario 2); `test_map_organization_wide` — PUT `.../organization` with a status and evidence, assert `target_type == "organization"` and `target_id is None` (FR-002, Acceptance Scenario 3); `test_map_same_control_two_applications_independent` — map to two different Applications, assert both appear independently with their own statuses (FR-006, Acceptance Scenario 4); `test_map_nonexistent_control_404`; `test_map_nonexistent_target_404` (each of the four entity-targeted shapes); `test_map_pattern_wrong_kind_422` — target a `knowledge_items` row with `kind != "pattern"` → 422 (research.md D5); `test_map_invalid_status_422` — `compliance_status: "bogus"` → 422

### Implementation for User Story 1

- [X] T008 [US1] In `src/adp/compliance/store.py`: `upsert_capability_mapping`, `upsert_application_mapping`, `upsert_design_mapping`, `upsert_pattern_mapping(control_id: str, target_id: str, data: ControlMappingWrite, session) -> ControlMapping` — each: raises `ControlNotFoundError` if `get_control(control_id)` is `None`; raises `MappingTargetNotFoundError(target_type, target_id)` if the corresponding `*_exists`/`get_knowledge_item_kind` check fails; `upsert_pattern_mapping` additionally raises `InvalidPatternTargetError` if the knowledge item exists but `kind != "pattern"` (research.md D5); then a shared `_upsert_entity_mapping` select-then-branch upsert (research.md D3, revised during implementation — SQLite-contract-test-portable, mirrors `DesignStore.save()`'s own idiom, NOT the originally-planned Postgres-only `ON CONFLICT DO UPDATE`) keyed on the table's composite PK; returns the resulting row as a `ControlMapping` with `target_type` set accordingly (depends on T004)
- [X] T009 [US1] In `src/adp/compliance/store.py`: `upsert_organization_mapping(control_id: str, data: ControlMappingWrite, session) -> ControlMapping` — same validation/upsert shape as T008 but keyed on the single-column `control_id` PK, no target existence check beyond `get_control`, returns `target_type="organization"`, `target_id=None` (depends on T004)
- [X] T010 [US1] In `src/adp/compliance/store.py`: `list_mappings_for_control(control_id: str, session) -> list[ControlMapping]` — raises `ControlNotFoundError` if the control doesn't exist; otherwise queries all five tables filtered by `control_id`, tagging each row with its `target_type`, and returns the concatenated list (depends on T008, T009)
- [X] T011 [US1] In `src/adp/compliance/router.py`: `PUT /controls/{control_id}/mappings/capabilities/{capability_id}`, `.../applications/{application_id}`, `.../designs/{design_id}`, `.../patterns/{pattern_id}`, `.../organization` — each calls the matching T008/T009 store function inside a shared internal helper (avoids duplicating the exception→HTTP-status translation five times): `ControlNotFoundError`→404, `MappingTargetNotFoundError`→404, `InvalidPatternTargetError`→422; every route requires `WRITE_COMPLIANCE` (already covered by the existing `/api/v1/compliance/` prefix rule — no `enforcement.py` change); each emits `logger.info()` with actor/control_id/target_type/target_id, matching `adp/compliance/router.py`'s existing logging convention (depends on T008, T009)
- [X] T012 [US1] In `src/adp/compliance/router.py`: `GET /controls/{control_id}/mappings` → 200 `ControlMappingListResponse`, 404 if the control doesn't exist; after calling `list_mappings_for_control`, filters out any `target_type == "application"` row when the caller lacks `READ_APPLICATION_GOVERNANCE` (research.md D2 — checked via `is_permitted(user.role, ActionType.READ_APPLICATION_GOVERNANCE)` inline, mirroring `adp.chat.tools.get_application_cost`'s existing inline-check precedent, NOT a blanket `require_action_dep` on the whole route, since non-Application rows must stay visible); `total` reflects the post-filter count; open read otherwise (depends on T010)
- [X] T013 [P] [US1] Extend `web/src/api/compliance.ts`: TypeScript types `ComplianceStatus`, `MappingTargetType`, `ControlMapping`, `ControlMappingWrite`, `ControlMappingListResponse` (mirrors the Python models); `useControlMappings(controlId: string | null)` query (queryKey `["control-mappings", controlId]`, enabled `!!controlId`); `useUpsertMapping(controlId: string)` mutation taking `{ targetType, targetId, data }` and PUT-ing to the correct route per `targetType` (`targetId` omitted for `"organization"`), invalidates `["control-mappings", controlId]`
- [X] T014 [US1] Create `web/src/compliance/ControlMappingsEditor.tsx`: props `controlId: string`; calls `useControlMappings(controlId)`; renders existing mappings as a list (target type + id, status badge, evidence, assessed_by/at); "Add Mapping" form — target-type selector (capability/application/design/pattern/organization), target-id input (a simple text/select input in this pass; hidden entirely when target type is "organization"), `compliance_status` dropdown (all 5 values), `evidence_ref`/`assessed_at`/`assessed_by` optional fields — submits via `useUpsertMapping(controlId)` (depends on T013)
- [X] T015 [US1] Wire into `web/src/compliance/ControlTree.tsx`: add a "Mappings" action per control row (mirrors the existing inline "Add Control"/edit actions' toggle-a-panel pattern) that renders `<ControlMappingsEditor controlId={control.id} />` (depends on T014)

**Checkpoint**: Core mapping creation and Control-side lookup fully functional end to end — a Control can
be mapped to any of its five target shapes via API and UI, and every mapping is retrievable from the
Control's own side. Independently demonstrable as the MVP.

---

## Phase 4: User Story 2 - Update a mapping's assessment over time (Priority: P2)

**Goal**: An authorized user can revisit an existing mapping and update its status/evidence/assessment
fields in place, without ever creating a duplicate record for the same (Control, target) pair.

**Independent Test**: Create a mapping with `non_compliant` status, then re-map the same (Control, target)
pair with `compliant` status and new evidence, and confirm exactly one mapping exists for that pair
reflecting only the latest values.

### Tests for User Story 2 (write first — ART-IV)

- [X] T016 [P] [US2] Integration tests in `tests/integration/test_compliance_mappings_api.py`: `test_remap_updates_not_duplicates` — PUT the same (control_id, application_id) pair twice with different `compliance_status`, GET the control's mappings, assert exactly one row for that pair reflecting the second call's values (FR-007/FR-008, SC-005); `test_remap_updates_only_evidence_ref` — PUT once with `compliance_status="non_compliant"`, then PUT again with the same status but a different `evidence_ref`, assert `compliance_status` unchanged and `evidence_ref` updated (Acceptance Scenario 2)

### Implementation for User Story 2

- [X] T017 [US2] Extend `web/src/compliance/ControlMappingsEditor.tsx`: each existing mapping row in the list gets an inline "Edit" action opening the same add-mapping form pre-filled with that row's current values (target type/id fixed, not editable — only status/evidence/assessed fields), submitting through the same `useUpsertMapping(controlId)` mutation from T013/T014 (depends on T014)

**Checkpoint**: Re-mapping updates in place is confirmed both at the API (T016) and in the UI (T017) — User
Stories 1 AND 2 both work independently.

---

## Phase 5: User Story 3 - Trace compliance coverage from either direction (Priority: P3)

**Goal**: Anyone with appropriate read access can see, from a Capability/Application/Design/Pattern's own
side, every Control mapped to it and each one's status.

**Independent Test**: Map several Controls to one Application with varying statuses, confirm that
Application's full set of mapped Controls is retrievable via `GET /applications/{id}/compliance-mappings`,
and separately confirm the same data is visible from the Control's own side (already proven in US1).

### Tests for User Story 3 (write first — ART-IV)

- [X] T018 [P] [US3] Contract test in `tests/contract/test_compliance_mappings_api.py`: `GET /business/capabilities/{cap_id}/compliance-mappings`, `GET /applications/{app_id}/compliance-mappings`, `GET /designs/{design_id}/compliance-mappings`, `GET /knowledge/{item_id}/compliance-mappings` each validate against `ControlMappingListResponse`
- [X] T019 [P] [US3] Integration tests in `tests/integration/test_compliance_mappings_api.py`: `test_capability_reverse_lookup` — map 2 Controls to a Capability, GET its mappings, assert both present (Acceptance Scenario 1); `test_application_reverse_lookup_requires_governance_read` — a role lacking `READ_APPLICATION_GOVERNANCE` gets 403 on `GET /applications/{id}/compliance-mappings` (US3 Acceptance Scenario 3; exercised via a role-overridden `TestClient`, matching COMPLY-01's own established pattern since no dev-mode `X-Role` header exists); `test_design_reverse_lookup`; `test_knowledge_item_reverse_lookup` (target a real `kind="pattern"` item); `test_control_forward_lookup_shows_all_target_types` — map one Control to a Capability, an Application, and the organization scope, GET the control's mappings, assert all three appear labeled correctly (Acceptance Scenario 2); `test_control_forward_lookup_filters_application_rows_without_governance_read` — same setup, a role lacking `READ_APPLICATION_GOVERNANCE` sees the Capability/organization rows but not the Application row, and `total` reflects the filtered count, not a 403 on the whole response (SC-006, research.md D2)

### Implementation for User Story 3

- [X] T020 [US3] In `src/adp/compliance/store.py`: `list_mappings_for_capability`, `list_mappings_for_application`, `list_mappings_for_design`, `list_mappings_for_pattern(target_id: str, session) -> list[ControlMapping]` — each queries its one table filtered by the target id, tagging every row with the matching `target_type` (depends on T003)
- [X] T021 [US3] In `src/adp/business/router.py`: `GET /capabilities/{cap_id}/compliance-mappings` → 200 `ControlMappingListResponse`, 404 if the capability doesn't exist; imports `adp.compliance.store` and uses a compliance-scoped session (mirrors `/capabilities/{cap_id}/designs`'s existing reverse-lookup shape in the same file); open read (depends on T020)
- [X] T022 [US3] In `src/adp/application/router.py`: `GET /applications/{app_id}/compliance-mappings` → 200 `ControlMappingListResponse`, 404 if the application doesn't exist, `dependencies=[Depends(_require_governance_read)]` (existing dependency from APM US7, reused not redefined); imports `adp.compliance.store` (depends on T020)
- [X] T023 [US3] In `src/adp/api/routers/designs.py`: `GET /{design_id}/compliance-mappings` → 200 `ControlMappingListResponse`, 404 if the design doesn't exist; add a `_get_compliance_session()` helper mirroring the file's existing `_get_strategy_session()` pattern; open read (depends on T020)
- [X] T024 [US3] In `src/adp/api/routers/knowledge.py`: `GET /{item_id}/compliance-mappings` → 200 `ControlMappingListResponse`, 404 if the knowledge item doesn't exist; open read (depends on T020)
- [X] T025 [P] [US3] Extend `web/src/api/compliance.ts`: `useCapabilityComplianceMappings(capId: string | null)`, `useApplicationComplianceMappings(appId: string | null)` query hooks (queryKeys `["capability-compliance-mappings", capId]` / `["application-compliance-mappings", appId]`), each `enabled` on a non-null id (depends on T013)
- [X] T026 [US3] Extend `web/src/business/CapabilityNode.tsx`: in the expanded row, alongside the existing `<DesignLinkEditor .../>`, add a read-only "Mapped Controls" list from `useCapabilityComplianceMappings(capability.id)` (control code/title if resolvable, status badge) — no separate detail screen exists for Capability (043-capability-heat-map research.md Decision 3 precedent), so this row is its home (depends on T025)
- [X] T027 [US3] Extend `web/src/application/ApplicationDetail.tsx`: add a new tab `{ id: "compliance-mappings", label: "Regulatory Compliance" }` (deliberately distinct from the existing `{ id: "risk", label: "Risk & Compliance" }` tab — a different, pre-existing APM concept, `RiskPanel.tsx`'s `risk_compliance_contribution` field, confirmed by direct read, not to be conflated) rendering the mapped-controls list from `useApplicationComplianceMappings(appId)` when `section === "compliance-mappings"` (depends on T025)

**Note (not a task — scope decision recorded here per plan.md's "Open decision carried into `/speckit.tasks`")**:
Design and Pattern reverse-lookup ship **API-only** in this pass (T023, T024) — neither domain has an
established single-entity detail screen to embed a UI into (Design has no page beyond the diagram editor's
element-level `InspectionPanel.tsx`; Pattern/knowledge items have only `KnowledgeItemRow.tsx` in a flat
list). Building a new detail screen for either is a materially larger scope increase than the confirmed UI
ask and risks scope creep into the actively-evolving diagram editor surface. Their UI is a reasonable
follow-on once either domain gets its own detail screen for other reasons — flag as a follow-on bead at
session close rather than building a page here solely to host this feature's own reverse-lookup.

**Checkpoint**: All four reverse-lookup directions are readable via API; Capability and Application have UI
coverage; Design and Pattern are API-complete with UI explicitly deferred. All user stories now
independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: CRUD completeness (research.md D6), full-database integration coverage, and authz completeness
across everything the prior phases built.

- [X] T028 [P] In `src/adp/compliance/store.py`: `delete_capability_mapping`, `delete_application_mapping`, `delete_design_mapping`, `delete_pattern_mapping(control_id: str, target_id: str, session) -> None`, `delete_organization_mapping(control_id: str, session) -> None` — each raises `MappingNotFoundError` if no row matched the delete (research.md D6)
- [X] T029 In `src/adp/compliance/router.py`: `DELETE /controls/{control_id}/mappings/{capabilities|applications|designs|patterns}/{target_id}` and `DELETE /controls/{control_id}/mappings/organization` → 204, `MappingNotFoundError`→404; requires `WRITE_COMPLIANCE` (existing prefix rule); logs per the existing convention (depends on T028)
- [X] T030 [P] Extend `web/src/api/compliance.ts`: `useDeleteMapping(controlId: string)` mutation mirroring `useUpsertMapping`'s target-type routing, invalidates `["control-mappings", controlId]` (depends on T013)
- [X] T031 Extend `web/src/compliance/ControlMappingsEditor.tsx`: each mapping row gets a "Remove" action wired to `useDeleteMapping(controlId)` from T030 (depends on T030)
- [X] T032 [P] Integration tests (testcontainers PostgreSQL) in `tests/integration/test_compliance_mappings_api.py`: `test_delete_control_cascades_all_five_mapping_tables` — map a Control to all five target shapes, delete the Control, assert every mapping is gone; `test_delete_target_entity_cascades_its_mapping` (Capability and Application — Design has no delete endpoint and knowledge-item delete is soft-delete only, so neither ever triggers the FK cascade via the API; confirmed by reading both routers, a scoping decision not a gap); `test_manual_delete_mapping_204_then_404` — DELETE a mapping, assert 204, DELETE again, assert 404 (T029)
- [X] T033 [P] Extend `tests/authz/test_enforcement.py`: `test_reviewer_denied_compliance_mapping_write` (403 for a REVIEWER-role PUT, mirroring the existing `test_reviewer_denied_compliance_write` shape from COMPLY-01); `test_application_mapping_read_requires_governance_permission` (403 for a role lacking `READ_APPLICATION_GOVERNANCE` on the Application reverse-lookup route); the third check (`test_control_forward_lookup_filters_for_non_governance_role`, 200 with Application rows filtered out) needs real mapping data to assert which rows survive, so it lives in the Docker-gated integration suite instead (`test_control_forward_lookup_filters_application_rows_without_governance_read`, T019/T032) — consistent with this file's own DB-free design, not an omission
- [X] T034 [P] Vitest coverage: `web/src/compliance/ControlMappingsEditor.test.tsx` (create/edit/delete flows, target-type switching hides the target-id field for "organization"); extended `CapabilityNode.test.tsx` for the new "Compliance" toggle/list; no pre-existing `ApplicationDetail.test.tsx` was found (confirmed by direct search), so the new `ApplicationComplianceMappings.tsx` panel got its own dedicated test file instead of a from-scratch full-component suite — a proportionate scoping call
- [X] T035 Ran every API scenario in `quickstart.md` live against a running local backend + real local Postgres: map/evidence/organization-wide/re-mapping-updates-in-place/forward-lookup-all-3-types/capability-and-application-reverse-lookup/pattern-kind-422/manual-delete-204-then-404/cascade-on-target-delete/cascade-on-control-delete/nonexistent-control-and-target-404 — every check passed, test data cleaned up afterward. Scenario 6's REVIEWER-role 403 check is instead covered by `tests/authz/test_enforcement.py` (5 passing tests, incl. the two new COMPLY-02 ones) since no dev-mode `X-Role` header exists to drive it via plain curl, matching COMPLY-01's own established precedent. Full-stack live UI walkthrough (clicking through ControlTree/CapabilityNode/ApplicationDetail in a browser) was not attempted this pass — API-level live verification plus the passing Vitest component suite cover the same logic paths.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories.
- **User Stories (Phase 3+)**: All depend on Foundational phase completion.
  - US1 (Phase 3) has no dependency on US2/US3.
  - US2 (Phase 4) depends on US1's `ControlMappingsEditor.tsx` (T014) existing to extend, and on the same
    `PUT` routes T011 already built — no new backend endpoint of its own.
  - US3 (Phase 5) depends only on Foundational (T003's table definitions) for its store/router work, though
    its integration tests (T019) are most naturally written after US1 mapping data exists to look up.
- **Polish (Phase 6)**: Depends on all three user stories being complete (deletes every shape US1–US3 created).

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) — no dependency on other stories.
- **User Story 2 (P2)**: Can start after Foundational, but its one implementation task (T017) extends T014
  from US1 — sequence after US1's `ControlMappingsEditor.tsx` exists.
- **User Story 3 (P3)**: Can start after Foundational — independently testable against directly-seeded
  mapping rows even before US1/US2 ship, though in practice it's demonstrated most naturally using mappings
  US1 already created.

### Within Each User Story

- Tests MUST be written and FAIL before implementation (ART-IV).
- Store functions before router endpoints before frontend hooks before frontend components.
- Story complete before moving to next priority.

### Parallel Opportunities

- T002 and T003 (Foundational) can run in parallel — different files, no dependency between them.
- T005 (unit tests) can run in parallel with T003/T004 once T002 lands.
- T006/T007 (US1 tests) can run in parallel with each other.
- T008/T009 write to the same file (`store.py`) but touch disjoint functions — sequential within one PR is
  simplest, though a team could split them.
- T018/T019 (US3 tests) can run in parallel with each other.
- T020's four `list_mappings_for_*` functions can be written together, then T021–T024 (one file each) can
  proceed in parallel once T020 lands.
- T028, T030, T032, T033, T034 (Polish) can each proceed in parallel — different files.

---

## Parallel Example: User Story 1

```bash
# Launch both US1 tests together:
Task: "Contract test for mapping PUT/GET routes in tests/contract/test_compliance_mappings_api.py"
Task: "Integration test for map/evidence/organization/duplicate-target scenarios in tests/integration/test_compliance_mappings_api.py"

# Frontend API layer can proceed in parallel with backend router work once store functions (T008/T009) land:
Task: "Extend web/src/api/compliance.ts with mapping types and hooks"
```

## Parallel Example: User Story 3

```bash
# Once T020 (store list functions) lands, all four reverse-lookup router tasks are independent files:
Task: "GET /capabilities/{cap_id}/compliance-mappings in src/adp/business/router.py"
Task: "GET /applications/{app_id}/compliance-mappings in src/adp/application/router.py"
Task: "GET /{design_id}/compliance-mappings in src/adp/api/routers/designs.py"
Task: "GET /{item_id}/compliance-mappings in src/adp/api/routers/knowledge.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (migration).
2. Complete Phase 2: Foundational (models, store tables, existence helpers).
3. Complete Phase 3: User Story 1 (map + Control-side lookup, API + UI).
4. **STOP and VALIDATE**: Run quickstart.md Scenarios 1–4 against a live stack.
5. Deploy/demo if ready — a Control can already be mapped to any of its five target shapes.

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. Add US1 → test independently → deploy/demo (MVP!).
3. Add US2 → test independently → deploy/demo (re-mapping now safe to rely on).
4. Add US3 → test independently → deploy/demo (reverse traceability now visible from Capability/Application;
   Design/Pattern API-complete, UI deferred per the Phase 5 note).
5. Add Polish → manual delete + full cascade/authz coverage.

### Parallel Team Strategy

With multiple developers, once Foundational is done: Developer A takes US1 (the critical path — US2 and
Polish's delete work both extend what US1 builds); Developer B can start US3's store/router work in
parallel (T020–T024 have no dependency on US1's endpoints, only on Foundational's table definitions);
Developer C can prepare Polish's test scaffolding (T032/T033 structure) once US1's shapes are known, filling
in assertions as each story lands.

---

## Notes

- [P] tasks = different files, no dependencies.
- [Story] label maps task to specific user story for traceability.
- Verify tests fail before implementing (ART-IV).
- Commit after each task or logical group.
- Stop at any checkpoint to validate story independently.
- No `PERMISSIONS_VERSION` bump and no `enforcement.py` change are needed anywhere in this task list — every
  write route lands under the `/api/v1/compliance/` prefix COMPLY-01 already gated, and the one new
  sensitive-read gate (`READ_APPLICATION_GOVERNANCE`) is an existing `ActionType` reused via an existing
  dependency helper, not a new grant.
