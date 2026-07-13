# Tasks: Business Architecture Traceability

**Input**: Design documents from `/specs/034-business-arch-traceability/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓, quickstart.md ✓

**Tests**: Tests are MANDATORY for all ADP features (ART-IV). Test tasks appear before their implementation counterparts in every user-story phase.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to
- Exact file paths included in all descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the Alembic migration for the two join tables. Nothing else can start until the schema exists.

- [X] T001 Write Alembic migration `src/adp/store/migrations/versions/008_business_traceability.py` — create `capability_design_links` table (composite PK `(capability_id, design_id)`, FK `capability_id` → `business_capabilities.id` ON DELETE CASCADE, FK `design_id` → `designs.id` ON DELETE CASCADE, `created_at` TIMESTAMPTZ); create `value_stream_design_links` table (composite PK `(value_stream_id, design_id)`, same FK pattern); add B-tree indexes on `design_id` column in each table for reverse lookups; `down_revision = "007"`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add shared Pydantic models, TypeScript interfaces, SQLAlchemy Table definitions, and error classes used across all user stories. Must be complete before any story phase starts.

- [X] T002 [P] Add shared Pydantic models to `src/adp/business/models.py` — add `DesignRef` (design_id, title, lifecycle_status), `CapabilityRef` (capability_id, name, level), `ValueStreamRef` (value_stream_id, name, stakeholder), `DesignLinkCreate` (design_id, blank-name validator), `LinkedDesignsResponse` (items: list[DesignRef]), `BusinessContextResponse` (design_id, capabilities: list[CapabilityRef], value_streams: list[ValueStreamRef]); all with `extra="forbid"`; add `DuplicateLinkError` and `LinkNotFoundError` exception classes

- [X] T003 [P] Add SQLAlchemy Core Table definitions for `capability_design_links` and `value_stream_design_links` to `src/adp/business/store.py` — use `sa.Table(...)` matching the data-model.md column definitions; these are needed by all link store functions

**Checkpoint**: `python3 -c "from adp.business.models import DesignLinkCreate, BusinessContextResponse; print('ok')"` succeeds.

---

## Phase 3: User Story 1 — Link Designs to Capabilities (Priority: P1) 🎯 MVP

**Goal**: Full add/remove/list CRUD for capability–design links. Inline "Linked Designs" expandable panel in the capability tree. 409 on duplicate.

**Independent Test**: Link two designs to a capability, verify both appear in list response, remove one, verify only the remaining design shows — passes Quickstart Scenarios 1 and 2.

### Tests for User Story 1 (MANDATORY — ART-IV)

> **Write these tests FIRST and confirm they FAIL before implementing T006+**

- [X] T004 [P] [US1] Write unit tests for `DesignLinkCreate` validation in `tests/unit/business/test_models.py` — test: blank `design_id` rejected; whitespace-only rejected; non-blank accepted; `extra="forbid"` on all new models

- [X] T005 [P] [US1] Write integration tests for the 3 capability–design endpoints in `tests/integration/test_business_api.py` — cover: POST link returns 201 with items list; GET list returns linked design; DELETE returns 204 and design is gone from list; POST duplicate returns 409; POST with nonexistent capability returns 404; POST with nonexistent design returns 404

### Implementation for User Story 1

- [X] T006 [P] [US1] Implement 3 capability–design store functions in `src/adp/business/store.py` — `list_capability_designs(capability_id, session) → list[DesignRef]` (JOIN `capability_design_links` with `designs` table to get title and lifecycle_status); `link_design_to_capability(capability_id, design_id, session) → None` (raises `DuplicateLinkError` on IntegrityError, raises `ValueError` if design not found via SELECT from designs); `unlink_design_from_capability(capability_id, design_id, session) → None` (raises `LinkNotFoundError` if no row deleted)

- [X] T007 [US1] Implement 3 capability–design endpoints in `src/adp/business/router.py` — `GET /capabilities/{capability_id}/designs` (returns LinkedDesignsResponse; 404 if capability not found); `POST /capabilities/{capability_id}/designs` (body: DesignLinkCreate; returns 201 + LinkedDesignsResponse; 404 if capability/design not found; 409 on DuplicateLinkError); `DELETE /capabilities/{capability_id}/designs/{design_id}` (returns 204; 404 on LinkNotFoundError or missing capability); all endpoints emit structured `logger.info()` with actor, capability_id, design_id, action

- [X] T008 [P] [US1] Add capability–design link hooks to `web/src/api/business.ts` — export TypeScript interfaces `DesignRef`, `LinkedDesignsResponse`; add hooks `useLinkedCapabilityDesigns(capabilityId: string)`, `useLinkDesignToCapability(capabilityId: string)`, `useUnlinkDesignFromCapability(capabilityId: string)`; also add `useDesigns()` hook that calls `GET /api/v1/designs?page_size=100` to populate the design picker dropdown (returns `DesignListResponse` shape: `{designs: Array<{id: string; title: string; lifecycle_status: string}>}`)

- [X] T009 [US1] Create `web/src/business/DesignLinkEditor.tsx` — reusable component for adding/removing design links; props: `entityType: "capability" | "value-stream"`, `entityId: string`; internally calls `useLinkedCapabilityDesigns` or `useLinkedValueStreamDesigns` based on `entityType` (using TanStack Query `enabled` option to avoid double-fetching); shows linked design list (each with a Remove button that calls `useUnlinkDesignFromCapability` or `useUnlinkDesignFromValueStream`); shows "Add Design" button that opens an inline dropdown populated by `useDesigns()`; selecting a design from the dropdown calls the appropriate link mutation; shows loading and error states; 409 conflict shown as inline error "Already linked"

- [X] T010 [US1] Modify `web/src/business/CapabilityNode.tsx` to add an expandable "Linked Designs" section — add a "Links" button (chain icon or "Links" text) to the capability row action bar; clicking it toggles a `showLinks` boolean state; when expanded, renders `<DesignLinkEditor entityType="capability" entityId={capability.id} />`; the links panel appears below the node header, indented to match the existing child indentation style

**Checkpoint**: Integration tests for capability–design pass. In browser, open Business → Capabilities, expand a capability's Links panel, add a design, verify it appears, remove it.

---

## Phase 4: User Story 2 — Link Designs to Value Streams (Priority: P2)

**Goal**: Full add/remove/list CRUD for value-stream–design links. "Supporting Designs" section in value stream detail view.

**Independent Test**: Link a design to a value stream, verify from both the value stream detail view and the design context response — passes Quickstart Scenario 4.

### Tests for User Story 2 (MANDATORY — ART-IV)

> **Write these tests FIRST and confirm they FAIL before implementing T012+**

- [X] T011 [P] [US2] Write integration tests for the 3 value-stream–design endpoints in `tests/integration/test_business_api.py` — cover: POST link returns 201; GET list returns linked design; DELETE returns 204; POST duplicate returns 409; POST with nonexistent value stream returns 404; cascade: delete value stream → design context shows no VS link

### Implementation for User Story 2

- [X] T012 [P] [US2] Implement 3 value-stream–design store functions in `src/adp/business/store.py` — `list_value_stream_designs(value_stream_id, session) → list[DesignRef]` (JOIN `value_stream_design_links` with `designs`); `link_design_to_value_stream(value_stream_id, design_id, session) → None` (raises `DuplicateLinkError` on IntegrityError; 404 if design not found); `unlink_design_from_value_stream(value_stream_id, design_id, session) → None` (raises `LinkNotFoundError` if no row deleted)

- [X] T013 [US2] Implement 3 value-stream–design endpoints in `src/adp/business/router.py` — `GET /value-streams/{value_stream_id}/designs`, `POST /value-streams/{value_stream_id}/designs` (body: DesignLinkCreate; 201 on success; 404/409 as spec), `DELETE /value-streams/{value_stream_id}/designs/{design_id}` (204); same structured logging pattern as T007

- [X] T014 [P] [US2] Add value-stream–design link hooks to `web/src/api/business.ts` — hooks `useLinkedValueStreamDesigns(valueStreamId: string)`, `useLinkDesignToValueStream(valueStreamId: string)`, `useUnlinkDesignFromValueStream(valueStreamId: string)`

- [X] T015 [US2] Modify `web/src/business/ValueStreamDetail.tsx` to add a "Supporting Designs" section — below the stages section, add a `<div>` with heading "Supporting Designs" and render `<DesignLinkEditor entityType="value-stream" entityId={vsId} />`; the section uses the same card styling as the existing stages container

**Checkpoint**: Integration tests for value-stream–design pass. In browser, open a value stream detail, use the Supporting Designs section to link and unlink a design.

---

## Phase 5: User Story 3 — Traceability Explorer (Priority: P3)

**Goal**: Reverse navigation — view all capabilities and value streams linked to a design from the design's intake view. "Business Context" panel in IntakePage.

**Independent Test**: Link a design to both a capability and a value stream, then call `GET /business/designs/{id}/context` — response contains both. Passes Quickstart Scenario 3 and 4 (context check).

### Tests for User Story 3 (MANDATORY — ART-IV)

> **Write these tests FIRST and confirm they FAIL before implementing T017+**

- [X] T016 [P] [US3] Write integration tests for `GET /api/v1/business/designs/{design_id}/context` in `tests/integration/test_business_api.py` — cover: design with no links returns empty lists; design linked to 1 capability returns it in `capabilities`; design linked to 1 value stream returns it in `value_streams`; design linked to both returns both; nonexistent design_id returns 404

### Implementation for User Story 3

- [X] T017 [P] [US3] Implement `get_design_business_context(design_id, session)` store function in `src/adp/business/store.py` — queries `capability_design_links` JOIN `business_capabilities` for CapabilityRef list (capability_id, name, level); queries `value_stream_design_links` JOIN `value_streams` for ValueStreamRef list (value_stream_id, name, stakeholder); verifies design exists in `designs` table (raises `ValueError` if not found); returns dict consumed by `BusinessContextResponse`

- [X] T018 [US3] Implement `GET /api/v1/business/designs/{design_id}/context` endpoint in `src/adp/business/router.py` — returns `BusinessContextResponse`; 404 if design not found; emits `logger.info()` on successful fetch for observability

- [X] T019 [P] [US3] Add `useDesignBusinessContext(designId: string)` hook and TypeScript interfaces to `web/src/api/business.ts` — export `CapabilityRef`, `ValueStreamRef`, `BusinessContextResponse`; hook calls `GET /api/v1/business/designs/{designId}/context`; enabled only when designId is truthy

- [X] T020 [US3] Create `web/src/business/BusinessContextPanel.tsx` — receives props `designId: string`, `onNavigate: (view: AppView) => void`; calls `useDesignBusinessContext(designId)`; renders a card with heading "Business Context"; if no capabilities and no value streams, shows empty state: "No business context linked. [Go to Business Architecture →]" button calls `onNavigate("business")`; otherwise renders two sections: "Capabilities" (list of CapabilityRef items) and "Value Streams" (list of ValueStreamRef items); each item is a clickable chip that calls `onNavigate("business")` with a visual indication of which entity to view; shows loading spinner while fetching

- [X] T021 [US3] Modify `web/src/intake/IntakePage.tsx` to add `<BusinessContextPanel>` — import `BusinessContextPanel` from `../business/BusinessContextPanel`; add `<BusinessContextPanel designId={designId} onNavigate={onNavigate} />` as a new section at the bottom of the intake page, below the existing requirements content and above any footer; import `type { AppView }` from `../shell` if not already imported

**Checkpoint**: Integration test for context endpoint passes. In browser, open a design's intake page — "Business Context" section is visible at the bottom. Link the design to a capability from Business page, return to intake — capability name now appears in the panel.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: End-to-end validation and documentation update.

- [X] T022 [P] Run Quickstart Scenarios 1–6 against the running API (`uvicorn` at `http://localhost:8001`) — execute all curl commands in `quickstart.md` and confirm expected HTTP status codes and response bodies; specifically verify the cascade delete scenario (Scenario 6)

- [X] T023 [P] Run Quickstart Scenarios 7–8 in the browser — verify the Business Context panel in IntakePage shows correctly; verify the capability tree's Linked Designs section adds and removes designs; confirm no regressions in existing Business page tabs, Portfolio, Governance, or design intake flows

- [X] T024 [P] Update `docs/solution-architecture.md` — add migration 008 (`capability_design_links`, `value_stream_design_links`) to the migration history table; add the 7 new endpoints to the Platform API router inventory table (or note "7 link endpoints" under the existing `/business` row); update the Business Architecture section to mention traceability links and the `BusinessContextPanel`; bump status from ADP-SPEC-033 to ADP-SPEC-034

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on T001 (migration must exist before SA Table defs); T002 and T003 can run in parallel after T001
- **US1 (Phase 3)**: Depends on Phase 2 complete; T004/T005/T006/T008 can run in parallel; T007 needs T006; T009 needs T008; T010 needs T009
- **US2 (Phase 4)**: Depends on Phase 2 complete AND T009 (DesignLinkEditor must exist); T011/T012/T014 can run in parallel; T013 needs T012; T015 needs T014
- **US3 (Phase 5)**: Depends on US1 and US2 complete (context endpoint aggregates both link types); T016/T017/T019 can run in parallel; T018 needs T017; T020 needs T019; T021 needs T020
- **Polish (Phase 6)**: Depends on US1, US2, US3 complete

### User Story Dependencies

- **US1 (P1)**: Can start after Phase 2 — T009 (DesignLinkEditor) is produced here and consumed by US2
- **US2 (P2)**: Depends on T009 (DesignLinkEditor from US1); otherwise parallel with US1 backend
- **US3 (P3)**: Logically depends on both US1 and US2 complete (needs link data from both); can start backend/context endpoint in parallel with US2

### Within Each User Story

- T004/T005 and T006/T008 are [P] — write simultaneously
- T006 (store) before T007 (router) — sequential
- T009 (DesignLinkEditor shared component) before T010 (CapabilityNode modification) — sequential
- T012 (store) before T013 (router) — sequential
- T015 (ValueStreamDetail mod) needs T014 (hooks) done first — sequential
- T017 (store) before T018 (router) — sequential
- T020 (BusinessContextPanel) before T021 (IntakePage mod) — sequential

---

## Parallel Execution Examples

### US1 in parallel (after Phase 2):

```text
[T004] Unit tests for models
[T005] Integration tests for cap-design endpoints
[T006] Store functions for cap-design links   → then T007
[T008] TanStack Query hooks                   → then T009 → T010
```

### US2 in parallel (after T009):

```text
[T011] Integration tests for VS-design endpoints
[T012] Store functions for VS-design links    → then T013
[T014] TanStack Query hooks                   → then T015
```

### US3 in parallel (after US1+US2):

```text
[T016] Integration test for context endpoint
[T017] get_design_business_context store fn   → then T018
[T019] useDesignBusinessContext hook          → then T020 → T021
```

---

## Implementation Strategy

**MVP = Phase 1 + Phase 2 + Phase 3 (US1)**. After US1, capability–design links are fully testable end-to-end.

**US2** adds value stream links; it reuses `DesignLinkEditor` from US1 — very low marginal effort.

**US3** adds the reverse navigation panel to IntakePage — purely additive, no changes to the link tables.

**Delivery order**: US1 → US2 → US3. Each phase is independently demoed and tested.

---

## Task Count Summary

| Phase | Tasks | Notes |
|-------|-------|-------|
| Setup | 1 | T001 |
| Foundational | 2 | T002–T003 |
| US1 (P1) | 7 | T004–T010 |
| US2 (P2) | 5 | T011–T015 |
| US3 (P3) | 6 | T016–T021 |
| Polish | 3 | T022–T024 |
| **Total** | **24** | |
