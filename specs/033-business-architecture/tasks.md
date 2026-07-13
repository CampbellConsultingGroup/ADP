# Tasks: Business Architecture — Capability Model and Value Streams

**Input**: Design documents from `/specs/033-business-architecture/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓, quickstart.md ✓

**Tests**: Tests are MANDATORY for all ADP features (ART-IV). Test tasks appear before their implementation counterparts in every user-story phase.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to
- Exact file paths included in all descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the new `adp.business` package and the Alembic migration. Nothing else can proceed until these exist.

- [X] T001 Create `src/adp/business/__init__.py` (empty package marker) and `tests/unit/business/__init__.py`
- [X] T002 Write Alembic migration `alembic/versions/007_business_architecture.py` — create tables `business_capabilities` (id, name, description, level CHECK(1-3), parent_id FK self-referential, position, created_at, updated_at), `value_streams` (id, name, description, stakeholder, position, created_at, updated_at), `value_stream_stages` (id, value_stream_id FK CASCADE, name, description, position); add B-tree indexes on parent_id, (parent_id, position), (value_stream_id, position)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Register the new router in the application so endpoints are reachable. MUST be done before any endpoint tests can pass.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T003 Register business router in `src/adp/api/app.py` — import `from adp.business.router import router as business_router` and add `app.include_router(business_router)` alongside the existing 16 routers; create stub `src/adp/business/router.py` with `router = APIRouter(prefix="/api/v1/business", tags=["business"])` so the import resolves

**Checkpoint**: Migration file exists; router registered; application starts without error.

---

## Phase 3: User Story 1 — Business Capability Model (Priority: P1) 🎯 MVP

**Goal**: Full CRUD for the 3-level capability hierarchy — create, read, edit, delete with child-deletion guard. Expandable tree UI on a new "Business" nav destination.

**Independent Test**: Create a 3-level hierarchy (L1 → L2 → L3), edit L3's name, attempt to delete L2 (blocked), delete L3 then L2 then L1 — passes Quickstart Scenarios 1 and 2.

### Tests for User Story 1 (MANDATORY — ART-IV)

> **Write these tests FIRST and confirm they FAIL before implementing T006+**

- [X] T004 [P] [US1] Write failing unit tests for `BusinessCapabilityCreate` validation (level/parent_id consistency, depth limit, empty-name rejection) in `tests/unit/business/test_models.py`
- [X] T005 [P] [US1] Write failing integration tests for all 5 capability endpoints covering Quickstart Scenarios 1, 2, and 3 (create hierarchy, delete guard, parent-level mismatch) in `tests/integration/test_business_api.py`

### Implementation for User Story 1

- [X] T006 [P] [US1] Implement all BusinessCapability Pydantic v2 models in `src/adp/business/models.py` — `BusinessCapability`, `BusinessCapabilityCreate` (with `@model_validator` enforcing level/parent_id consistency), `BusinessCapabilityUpdate`; set `extra="forbid"` on all models
- [X] T007 [US1] Implement capability store methods in `src/adp/business/store.py` — async functions `list_capabilities(session)`, `get_capability(id, session)`, `create_capability(data, session)`, `update_capability(id, data, session)`, `delete_capability(id, session)` (raises `ChildCapabilitiesExist` if children found); use SQLAlchemy 2 async ORM with `adp.business.db_models.BusinessCapabilityRow` mapped class
- [X] T008 [US1] Implement all 5 capability endpoints in `src/adp/business/router.py` — `GET /capabilities` (flat list), `POST /capabilities`, `GET /capabilities/{id}`, `PUT /capabilities/{id}`, `DELETE /capabilities/{id}` (returns 409 with child count message on `ChildCapabilitiesExist`); wire to store functions from T007
- [X] T009 [US1] Add `AuditEntry` logging for capability mutations in `src/adp/business/router.py` — write audit entry (actor, action, affected_entity, summary) on create, update, and delete using existing `adp.audit.writer` patterns
- [X] T010 [P] [US1] Implement TanStack Query hooks for capabilities in `web/src/api/business.ts` — `useCapabilities()`, `useCapability(id)`, `useCreateCapability()`, `useUpdateCapability(id)`, `useDeleteCapability()`; use `apiGet` and `apiMutation` from `web/src/api/client.ts`; export `BusinessCapability` and `BusinessCapabilityCreate` TypeScript interfaces
- [X] T011 [P] [US1] Create `web/src/business/CapabilityNode.tsx` — renders a single capability row with its name, level badge (L1/L2/L3), Edit button (inline name/description form via `useUpdateCapability`), Add Child button (shown only when level < 3, opens `CapabilityForm`), and Delete button (calls `useDeleteCapability`, shows 409 error message if blocked)
- [X] T012 [P] [US1] Create `web/src/business/CapabilityForm.tsx` — inline form for creating a new capability; props: `parentId: string | null`, `level: 1 | 2 | 3`, `onDone: () => void`; calls `useCreateCapability()`; validates name non-empty before submit
- [X] T013 [US1] Create `web/src/business/CapabilityTree.tsx` — accepts flat `BusinessCapability[]` from `useCapabilities()`; contains `buildTree(items)` helper that groups by `parent_id` and sorts by `position`; renders `CapabilityNode` for Level 1 roots with expand/collapse toggle; Level 2 and 3 children rendered indented under their parents; shows empty state with "Create your first capability" CTA when list is empty
- [X] T014 [US1] Create `web/src/business/BusinessPage.tsx` — top-level page with two tabs ("Capabilities" and "Value Streams"); Capabilities tab renders `CapabilityTree`; Value Streams tab shows placeholder "Coming soon" for now; receives `onNavigate` and `designId` props matching existing page conventions
- [X] T015 [US1] Add "Business" navigation to `web/src/shell.tsx` and `web/src/App.tsx` — add `"business"` to the `AppView` union type in `shell.tsx`; add "Business" button to `NavBar` between existing items; add `case "business": return <BusinessPage .../>` to `App.tsx` render switch

**Checkpoint**: `pytest tests/integration/test_business_api.py -k capability` passes. Open the app, click "Business", create a 3-level hierarchy, edit and delete nodes — all work correctly.

---

## Phase 4: User Story 2 — Value Streams (Priority: P2)

**Goal**: Full CRUD for value streams with ordered stages — create/edit/delete value streams, add/edit/delete/reorder stages. Value Streams tab in BusinessPage.

**Independent Test**: Create "Order to Cash" with 3 stages, reorder stages via up/down, delete one stage, delete the value stream — all stages removed (Quickstart Scenarios 4 and 5).

### Tests for User Story 2 (MANDATORY — ART-IV)

> **Write these tests FIRST and confirm they FAIL before implementing T018+**

- [X] T016 [P] [US2] Write failing unit tests for `ValueStreamCreate` and `ValueStreamStageCreate` Pydantic validation (empty name rejection, position defaults) in `tests/unit/business/test_models.py`
- [X] T017 [P] [US2] Write failing integration tests for value stream and stage endpoints covering Quickstart Scenarios 4 and 5 (full lifecycle, cascade delete) in `tests/integration/test_business_api.py`

### Implementation for User Story 2

- [X] T018 [P] [US2] Add ValueStream and ValueStreamStage Pydantic models to `src/adp/business/models.py` — `ValueStream`, `ValueStreamDetail` (with `stages: list[ValueStreamStage]`), `ValueStreamStage`, `ValueStreamCreate`, `ValueStreamUpdate`, `ValueStreamStageCreate`, `ValueStreamStageUpdate`, `ValueStreamStagesReorder` (with `stages: list[StageReorderItem]` where each item has id, name, description); `extra="forbid"` on all
- [X] T019 [US2] Implement value stream store methods in `src/adp/business/store.py` — `list_value_streams(session)`, `get_value_stream(id, session)` (with stages), `create_value_stream(data, session)`, `update_value_stream(id, data, session)`, `delete_value_stream(id, session)` (CASCADE to stages via FK), `add_stage(vs_id, data, session)`, `update_stage(vs_id, stage_id, data, session)`, `delete_stage(vs_id, stage_id, session)`, `reorder_stages(vs_id, ordered_stages, session)` (deletes stages not in list, updates positions 0..n-1 in a single transaction)
- [X] T020 [US2] Implement all 9 value stream and stage endpoints in `src/adp/business/router.py` — `GET /value-streams`, `POST /value-streams`, `GET /value-streams/{id}`, `PUT /value-streams/{id}`, `DELETE /value-streams/{id}`, `POST /value-streams/{id}/stages`, `PUT /value-streams/{id}/stages/{stage_id}`, `DELETE /value-streams/{id}/stages/{stage_id}`, `PUT /value-streams/{id}/stages` (bulk reorder); return 404 when value stream or stage not found
- [X] T021 [US2] Add `AuditEntry` logging for value stream mutations in `src/adp/business/router.py` — audit entry on value stream create, update, delete (single entry per value stream operation, not per-stage)
- [X] T022 [P] [US2] Add TanStack Query hooks for value streams and stages to `web/src/api/business.ts` — `useValueStreams()`, `useValueStream(id)`, `useCreateValueStream()`, `useUpdateValueStream(id)`, `useDeleteValueStream()`, `useAddStage(vsId)`, `useUpdateStage(vsId, stageId)`, `useDeleteStage(vsId)`, `useReorderStages(vsId)`; export TypeScript interfaces `ValueStream`, `ValueStreamDetail`, `ValueStreamStage`
- [X] T023 [P] [US2] Create `web/src/business/ValueStreamForm.tsx` — form for creating and editing a value stream's metadata (name, description, stakeholder); used in both create and edit modes; calls `useCreateValueStream()` or `useUpdateValueStream(id)` accordingly
- [X] T024 [P] [US2] Create `web/src/business/ValueStreamStageEditor.tsx` — renders the ordered list of stages for a value stream; each stage has an inline Edit button (name + description), Delete button, and Up/Down arrow buttons that call `useReorderStages`; an "Add Stage" button at the bottom appends a new stage via `useAddStage`; shows stage position numbers
- [X] T025 [US2] Create `web/src/business/ValueStreamDetail.tsx` — full detail view for a single value stream; shows name, description, stakeholder badge; renders `ValueStreamStageEditor` for the stage list; includes Edit button for metadata (shows `ValueStreamForm` inline) and Delete button with confirmation; navigates back to list on delete
- [X] T026 [US2] Create `web/src/business/ValueStreamList.tsx` — list of value stream summary cards; each card shows name, stakeholder, stage count; clicking a card navigates to `ValueStreamDetail`; "Create Value Stream" button opens `ValueStreamForm`; shows empty state with CTA when list is empty
- [X] T027 [US2] Replace "Coming soon" placeholder with `ValueStreamList` in the Value Streams tab of `web/src/business/BusinessPage.tsx`; manage `selectedValueStreamId` state to switch between list view and detail view within the tab

**Checkpoint**: `pytest tests/integration/test_business_api.py -k value_stream` passes. In the app, create a value stream with 3 stages, reorder them, delete one, then delete the value stream — no orphan stages remain.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Frontend unit tests, full integration validation, and documentation.

- [X] T028 [P] Add Vitest unit test for `buildTree` helper in `web/src/business/CapabilityTree.test.tsx` — test: empty input returns `[]`; flat L1-only list; 3-level tree assembled correctly; orphan nodes (invalid parent_id) handled gracefully
- [X] T029 Run all 7 quickstart.md integration scenarios against the running app (`uvicorn` + Vite) — verify Scenarios 1–5 via API curl and Scenarios 6–7 via browser; confirm no regressions in existing Knowledge and Design screens
- [X] T030 [P] Update `docs/solution-architecture.md` to document the Business Architecture module — add "Business Architecture" to the capability list, update the router inventory table with the new `/api/v1/business/` routes, add the 3 new tables to the migration history table

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on T001 (package must exist before router import resolves)
- **US1 (Phase 3)**: Depends on Phase 2 complete; T005 (integration tests) need T003 (router registered)
- **US2 (Phase 4)**: Depends on Phase 2 complete; independent of US1 (different tables, different endpoints)
- **Polish (Phase 5)**: Depends on US1 and US2 complete

### User Story Dependencies

- **US1 (P1)**: Can start after Foundational — no dependency on US2
- **US2 (P2)**: Can start after Foundational — no dependency on US1; `BusinessPage.tsx` must exist (T014) before T027 can extend it

### Within Each User Story

- T004/T005 and T010/T011/T012 are all [P] — write them concurrently
- T006 (models) before T007 (store) before T008 (endpoints) — sequential
- T013 (tree) depends on T011 (node) and T012 (form)
- T014 (page) depends on T013 (tree)
- T015 (nav) depends on T014 (page)

---

## Parallel Example: User Story 1

```bash
# Write together (all [P]):
T004: Unit tests for BusinessCapability models
T005: Integration tests for capability endpoints
T010: TanStack Query hooks in web/src/api/business.ts
T011: CapabilityNode component
T012: CapabilityForm component
T006: BusinessCapability Pydantic models

# Then sequentially:
T007: BusinessStore capability methods (needs T006)
T008: Capability endpoints (needs T007)
T009: Audit logging (needs T008)
T013: CapabilityTree (needs T011, T012)
T014: BusinessPage (needs T013)
T015: Nav + routing (needs T014)
```

## Parallel Example: User Story 2

```bash
# Write together (all [P]):
T016: Unit tests for ValueStream models
T017: Integration tests for value stream endpoints
T018: ValueStream Pydantic models
T022: TanStack Query hooks for value streams
T023: ValueStreamForm component
T024: ValueStreamStageEditor component

# Then sequentially:
T019: Store methods (needs T018)
T020: Endpoints (needs T019)
T021: Audit logging (needs T020)
T025: ValueStreamDetail (needs T024)
T026: ValueStreamList (needs T023, T025)
T027: BusinessPage tab update (needs T026, T014)
```

---

## Implementation Strategy

### MVP First (US1 Only — Capability Model)

1. Complete Phase 1: Setup (T001–T002)
2. Complete Phase 2: Foundational (T003)
3. Write US1 tests (T004–T005) — confirm they FAIL
4. Implement US1 backend (T006–T009) — confirm tests PASS
5. Implement US1 frontend (T010–T015)
6. **STOP and VALIDATE**: Full capability tree UI works end-to-end
7. Demo: Enterprise Architect can manage a 3-level capability hierarchy

### Incremental Delivery

1. Setup + Foundational → package and migration ready
2. US1 complete → Capability tree live (MVP, independently demoed)
3. US2 complete → Value streams live (both tabs functional)
4. Polish → Tests, docs, full scenario validation

### Parallel Team Strategy (2 developers after Phase 2)

- **Developer A**: US1 backend (T004–T009) then US1 frontend (T010–T015)
- **Developer B**: US2 backend (T016–T021) then US2 frontend (T022–T027)
- Merge: T027 extends T014 (BusinessPage) — coordinate on that single file

---

## Notes

- [P] tasks touch different files and have no dependency on incomplete tasks in the same phase
- Test tasks (T004, T005, T016, T017) MUST be written before implementation and MUST be verified to FAIL first (ART-IV)
- The `buildTree` helper in `CapabilityTree.tsx` is pure TypeScript — test it in Vitest (T028) without mounting the full component
- Stage reorder (T019, T024) sends the full ordered list to `PUT /api/v1/business/value-streams/{id}/stages` — not individual position patches
- The audit logging (T009, T021) uses existing `AuditEntry` + `next_audit_id` from `adp.audit.writer` — no new audit infrastructure needed
- `web/src/App.tsx` switch case for "business" added in T015 — T027 only touches the tab content inside `BusinessPage.tsx`
