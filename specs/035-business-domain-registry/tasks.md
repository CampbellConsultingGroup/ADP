# Tasks: Business Domain Registry and Stage-Capability Mapping (ADP-SPEC-035)

**Input**: Design documents from `/specs/035-business-domain-registry/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓, quickstart.md ✓

**Tests**: Mandatory (ART-IV). Integration test tasks appear before their implementation counterparts in each user-story phase.

**Organization**: Tasks grouped by user story (US1=Domain CRUD, US2=Capability-Domain Assignment, US3=Stage-Capability Mapping). Each story is independently testable.

---

## Phase 1: Setup (Migration + Foundational Models)

**Purpose**: Database schema and Pydantic models that all three user stories depend on. Must complete before any user story work begins.

- [X] T001 Create Alembic migration 009 in `src/adp/store/migrations/versions/009_business_domain_registry.py`: CREATE TABLE `business_domains` (id VARCHAR(36) PK, name VARCHAR(255) NOT NULL, scope_statement TEXT, classification TEXT NOT NULL CHECK IN ('strategic','differentiating','commodity'), org_unit VARCHAR(255), risk_flags TEXT[] NOT NULL DEFAULT '{}', created_at/updated_at TIMESTAMPTZ NOT NULL); index ix_business_domains_name; ALTER TABLE business_capabilities ADD COLUMN domain_id VARCHAR(36) REFERENCES business_domains(id) ON DELETE SET NULL; index ix_business_capabilities_domain_id; CREATE TABLE value_stream_stage_capabilities (stage_id VARCHAR(36) FK→value_stream_stages CASCADE, capability_id VARCHAR(36) FK→business_capabilities CASCADE, PRIMARY KEY(stage_id,capability_id)); index ix_vssc_capability_id on capability_id

- [X] T002 Extend `src/adp/business/models.py` with all new ADP-SPEC-035 types: `DomainClassification = Literal["strategic","differentiating","commodity"]`; BusinessDomain (id, name, scope_statement, classification, org_unit, risk_flags: list[str], created_at, updated_at — extra="forbid"); DomainSummary (same minus scope_statement, plus capability_count: int); DomainDetail(BusinessDomain) with `capabilities: list[CapabilityRef]`; DomainListResponse(items: list[DomainSummary], total: int); BusinessDomainCreate (name not-blank validator, risk_flags blank-entry check + dedup via dict.fromkeys); BusinessDomainUpdate (all fields optional, same validators); extend BusinessCapability with `domain_id: str | None = None` and `domain_name: str | None = None`; CapabilityDomainAssign(domain_id: str | None, extra="forbid"); StageCapabilityRef(capability_id, name, level, domain_id, domain_name — extra="forbid"); StageCapabilityLinkCreate(capability_id — not-blank validator, strip whitespace); StageCapabilitiesResponse(items: list[StageCapabilityRef]); DuplicateStageCapError(Exception); StageCapNotFoundError(Exception)

- [X] T003 [P] Add unit tests for new Pydantic models in `tests/unit/business/test_models.py`: TestBusinessDomainCreate — blank name→ValidationError, blank risk_flag entry→ValidationError, duplicate risk_flags deduplicated (["PII","PII"]→["PII"]), invalid classification "premium"→ValidationError, extra fields→ValidationError, valid full create; TestBusinessDomainUpdate — empty update valid, blank name→error, blank risk_flag→error; TestCapabilityDomainAssign — null domain_id accepted (clear), valid uuid string accepted, extra fields→error; TestStageCapabilityLinkCreate — blank→error, whitespace-only→error, "  cap-001  " stripped to "cap-001"; verify all existing tests still pass

---

## Phase 2: US1 — Domain CRUD

**Goal**: Architects can create, read, update, and delete business domains with all attributes (name, scope, classification, org_unit, risk_flags). Domain list shows capability counts. Domain detail shows assigned L1 capability list.

**Independent Test**: Create three domains, list them (verify ordering by name and capability_count=0), update one's scope_statement, GET detail (verify capabilities=[]), delete one, verify surviving capabilities unchanged.

### Tests for US1 (write first — ART-IV)

- [X] T004 [P] [US1] Add domain CRUD integration tests to `tests/integration/test_business_api.py`: helper `_create_domain(client, **kwargs)` that POSTs to `/api/v1/business/domains`; test_domain_create_201 — POST with all fields, assert 201, id present, risk_flags=["PII","GDPR"]; test_domain_list_ordered — create "Zeta" then "Alpha" domains, GET /domains, assert items ordered by name; test_domain_list_capability_count — create domain + assign L1 cap later (placeholder for now: assert capability_count=0 for new domain); test_domain_detail_200 — GET /domains/{id}, assert scope_statement and capabilities=[]; test_domain_update_200 — PUT with new scope_statement, assert response updated; test_domain_delete_204 — DELETE, assert 204; GET after delete → 404; test_domain_404 — GET/PUT/DELETE nonexistent id → 404; test_domain_invalid_classification — POST with classification="premium" → 422; test_domain_blank_name — POST with name="" → 422

### Implementation for US1

- [X] T005 [US1] Extend `src/adp/business/store.py`: add `_domains` SA Table definition (id, name, scope_statement, classification, org_unit, risk_flags ARRAY(Text()), created_at, updated_at); add `domain_id` column to existing `_capabilities` SA Table definition; extend `_row_to_capability()` to LEFT JOIN `business_domains` on `domain_id` and populate `domain_id` and `domain_name` on the BusinessCapability object; implement `list_domains(session) → list[DomainSummary]` (SELECT domains LEFT JOIN COUNT(cap.id) WHERE cap.domain_id=dom.id, GROUP BY dom.id, ORDER BY dom.name); implement `get_domain(domain_id, session) → DomainDetail | None` (SELECT domain + SELECT caps WHERE domain_id=id ordered by name); implement `create_domain(body: BusinessDomainCreate, session) → BusinessDomain`; implement `update_domain(domain_id, body: BusinessDomainUpdate, session) → BusinessDomain | None`; implement `delete_domain(domain_id, session) → bool`

- [X] T006 [US1] Add domain CRUD endpoints to `src/adp/business/router.py`: update imports to include BusinessDomain, DomainSummary, DomainDetail, DomainListResponse, BusinessDomainCreate, BusinessDomainUpdate; add `GET /domains` → DomainListResponse; `POST /domains` → 201 BusinessDomain, 422 on validation failure; `GET /domains/{domain_id}` → DomainDetail, 404; `PUT /domains/{domain_id}` → BusinessDomain, 404, 422; `DELETE /domains/{domain_id}` → 204, 404; all mutation endpoints emit `logger.info()` with actor/domain_id/action

- [X] T007 [P] [US1] Add domain TS interfaces and TanStack Query hooks to `web/src/api/business.ts`: export type `DomainClassification = "strategic" | "differentiating" | "commodity"`; export interfaces BusinessDomain, DomainSummary (extends Omit<BusinessDomain,"scope_statement"> + capability_count), DomainDetail (extends BusinessDomain + capabilities: CapabilityRef[]), DomainCreate, DomainUpdate, DomainListResponse; hooks: `useDomains()` (queryKey ["business-domains"]), `useDomain(id: string | null)` (enabled: !!id), `useCreateDomain()` (invalidates ["business-domains"]), `useUpdateDomain(id: string)` (invalidates ["business-domains"] + ["business-domain", id]), `useDeleteDomain()` (invalidates ["business-domains"])

- [X] T008 [P] [US1] Create `web/src/business/DomainForm.tsx`: props `existing?: BusinessDomain; onDone: () => void; onCancel: () => void`; controlled form with: name input (required), scope_statement textarea (optional), classification select (strategic/differentiating/commodity), org_unit input, risk_flags text input with helper "comma-separated, e.g. PII, GDPR" → split on comma, trim, filter blank on submit; uses `useCreateDomain()` or `useUpdateDomain(existing.id)` depending on whether `existing` is set; shows inline error on mutation failure

- [X] T009 [US1] Create `web/src/business/DomainList.tsx`: calls `useDomains()`; shows loading/error states; renders each DomainSummary as a card row: name, classification badge (strategic=blue #1168BD, differentiating=green #047857, commodity=grey #6B7280), org_unit (if set), risk_flags as small chips, capability_count badge; "Add Domain" button opens inline DomainForm; clicking a domain row calls `onSelectDomain(id)`; delete button with confirm dialog calls `useDeleteDomain()`; props: `onSelectDomain: (id: string) => void`

- [X] T010 [US1] Create `web/src/business/DomainDetail.tsx`: props `domainId: string; onBack: () => void`; calls `useDomain(domainId)`; shows domain metadata (name, scope_statement, classification badge, org_unit, risk_flags chips); edit button → inline DomainForm; "Assigned Capabilities" section: list of CapabilityRefs (name + level badge) — assignment panel deferred to US2; back button calls `onBack`

- [X] T011 [US1] Extend `web/src/business/BusinessPage.tsx`: add `"domains"` to BusinessTab union type; add "Domains" tab button in tab bar (between Value Streams and any future tabs); add `selectedDomainId: string | null` state; render logic: tab==="domains" && !selectedDomainId → `<DomainList onSelectDomain={setSelectedDomainId} />`; tab==="domains" && selectedDomainId → `<DomainDetail domainId={selectedDomainId} onBack={() => setSelectedDomainId(null)} />`

**Checkpoint**: Domain CRUD fully functional. `GET /api/v1/business/domains` returns ordered list with counts. Domain detail shows full attributes. UI Domains tab create/view/edit/delete all work.

---

## Phase 3: US2 — Capability-Domain Assignment

**Goal**: Architects can assign L1 capabilities to domains, establishing ownership boundaries. L2/L3 assignment is rejected. The capability tree shows domain name badges on L1 nodes. Domain detail shows its assigned capabilities.

**Independent Test**: Create a domain + two L1 caps. PATCH each to the domain. Verify domain detail shows both. Reassign one to a second domain. Verify each domain's cap list is correct. PATCH with null to clear. Verify no domain shows it.

### Tests for US2 (write first — ART-IV)

- [X] T012 [P] [US2] Add capability-domain assignment integration tests to `tests/integration/test_business_api.py`: test_assign_l1_to_domain — PATCH /capabilities/{cap_id}/domain with domain_id, assert 200 + domain_id + domain_name on cap; test_assign_clears_previous — L1 in domain A, PATCH to domain B, GET domain A → cap not in list, GET domain B → cap in list; test_assign_l2_rejected — PATCH L2 cap → 422 with message about L1 only; test_assign_nonexistent_domain — PATCH valid L1 with fake domain_id → 404; test_clear_domain — PATCH with domain_id=null → 200, domain_id null; test_domain_detail_shows_caps — after assigning, GET /domains/{id} capability_count=1 and capabilities list contains the cap; test_delete_domain_nulls_cap — assign cap to domain, DELETE domain 204, GET cap → domain_id null

### Implementation for US2

- [X] T013 [US2] Extend `src/adp/business/store.py`: implement `assign_capability_domain(cap_id: str, domain_id: str, session) → BusinessCapability`: check cap exists (raises ValueError "Capability not found"); check cap.level == 1 (raises ValueError "Only L1 capabilities can be assigned to a domain"); check domain exists (raises ValueError "Domain not found"); UPDATE capabilities SET domain_id=domain_id; return updated cap with domain_name populated via JOIN; implement `clear_capability_domain(cap_id: str, session) → BusinessCapability`: check cap exists; UPDATE SET domain_id=null; return updated cap

- [X] T014 [US2] Add `PATCH /capabilities/{cap_id}/domain` endpoint to `src/adp/business/router.py`: import CapabilityDomainAssign; 404 if cap not found; if body.domain_id is not None → call `assign_capability_domain`, catch ValueError and map to 404 (not found) or 422 (level constraint); if body.domain_id is None → call `clear_capability_domain`; emit logger.info with actor/cap_id/domain_id/action; return 200 BusinessCapability

- [X] T015 [P] [US2] Add `useAssignCapabilityDomain(capId: string)` hook to `web/src/api/business.ts`: PATCH mutation to `/api/v1/business/capabilities/${capId}/domain` with body `{domain_id: string | null}`; on success invalidate queryKeys ["business-capabilities"], ["business-capability", capId], and ["business-domains"] (so domain capability_count updates)

- [X] T016 [P] [US2] Extend `web/src/business/CapabilityNode.tsx`: for level=1 capabilities, show domain badge when `capability.domain_name` is set — small pill badge after the capability name; colour by classification: needs DomainClassification context or just use neutral blue (#1168BD) since CapabilityNode doesn't receive domain detail; badge text = capability.domain_name; no badge if domain_name is null

- [X] T017 [US2] Extend `web/src/business/DomainDetail.tsx` with full assignment panel: import `useCapabilities` and `useAssignCapabilityDomain`; "Assigned Capabilities" section: list assigned caps (from domain.capabilities) with "Remove" button per cap (calls PATCH with domain_id=null + invalidates useDomain); "Add Capability" section: picker dropdown of unassigned L1 caps (filter useCapabilities() items where level===1 && domain_id===null); selecting + clicking "Assign" calls useAssignCapabilityDomain with selected cap id; show 404 error if domain lookup fails

**Checkpoint**: PATCH /capabilities/{cap_id}/domain works for assign and clear. L2/L3 rejected 422. L1 badge appears in capability tree. Domain detail shows assigned caps with add/remove controls.

---

## Phase 4: US3 — Stage-Capability Mapping

**Goal**: Architects can link business capabilities to value stream stages (many-to-many). The stage editor in ValueStreamDetail shows linked capabilities and a picker to add/remove them. Deleting a stage or capability cascades the links.

**Independent Test**: Create value stream + stage + two capabilities. POST link cap1→stage. GET stage capabilities → [cap1]. POST duplicate → 409. DELETE link → GET returns []. DELETE stage → links gone. Delete capability → links gone.

### Tests for US3 (write first — ART-IV)

- [X] T018 [P] [US3] Add stage-capability integration tests to `tests/integration/test_business_api.py`: helpers `_create_vs_with_stage(client)`, `_create_cap(client)`; test_link_cap_to_stage_201 — POST /value-streams/{vs}/stages/{stage}/capabilities with cap_id → 201 StageCapabilitiesResponse with cap in items; test_duplicate_link_409 — POST same pair again → 409; test_get_stage_caps — GET endpoint returns correct items; test_unlink_204 — DELETE link → 204; GET → empty items; test_link_nonexistent_stage — POST to fake stage_id → 404; test_link_nonexistent_cap — POST with fake cap_id → 404; test_cascade_on_stage_delete — link cap, DELETE stage, GET stage → 404 (stage gone + links gone); test_cascade_on_cap_delete — link cap to stage, DELETE cap, GET stage caps → empty

### Implementation for US3

- [X] T019 [US3] Extend `src/adp/business/store.py`: add `_stage_caps` SA Table (stage_id String(36), capability_id String(36)); implement `list_stage_capabilities(stage_id: str, session) → list[StageCapabilityRef]`: SELECT caps + LEFT JOIN business_domains for domain_id/domain_name WHERE vssc.stage_id=stage_id; implement `link_stage_capability(stage_id: str, cap_id: str, session)`: check stage exists (raises ValueError "Stage not found"); check cap exists (raises ValueError "Capability not found"); INSERT; on UniqueViolation raise DuplicateStageCapError; implement `unlink_stage_capability(stage_id: str, cap_id: str, session)`: DELETE WHERE stage_id AND cap_id; if rowcount==0 raise StageCapNotFoundError

- [X] T020 [US3] Add stage-capability endpoints to `src/adp/business/router.py`: import StageCapabilityRef, StageCapabilitiesResponse, StageCapabilityLinkCreate, DuplicateStageCapError, StageCapNotFoundError; `GET /value-streams/{vs_id}/stages/{stage_id}/capabilities`: verify VS exists (404), verify stage belongs to VS (404), call list_stage_capabilities → StageCapabilitiesResponse; `POST /value-streams/{vs_id}/stages/{stage_id}/capabilities`: 404 for VS/stage; call link_stage_capability; catch DuplicateStageCapError→409, ValueError→404; on success return 201 + list_stage_capabilities; `DELETE /value-streams/{vs_id}/stages/{stage_id}/capabilities/{cap_id}`: catch StageCapNotFoundError→404; emit logger.info for all mutations

- [X] T021 [P] [US3] Add stage-cap TS interfaces and hooks to `web/src/api/business.ts`: export interfaces StageCapabilityRef (capability_id, name, level, domain_id, domain_name), StageCapabilitiesResponse, StageCapabilityLinkCreate; export `useStageCapabilities(vsId: string | null, stageId: string | null)` (enabled: !!(vsId && stageId), queryKey ["stage-caps", vsId, stageId]); `useLinkStageCap(vsId: string, stageId: string)` mutation (POST, invalidates ["stage-caps",vsId,stageId] on success); `useUnlinkStageCap(vsId: string, stageId: string)` mutation (DELETE, invalidates same)

- [X] T022 [US3] Create `web/src/business/StageCapsEditor.tsx`: props `vsId: string; stageId: string`; calls `useStageCapabilities(vsId, stageId)` and `useCapabilities()`; shows loading spinner; renders linked caps list — each row: capability name + level badge + domain_name chip (if set) + "Remove" button; "Add Capability" picker: dropdown of all capabilities not already linked (filter by capability_id not in linked set); "Link" button calls `useLinkStageCap`; on 409 error show "Already linked" inline; on success picker resets to empty; analogous to DesignLinkEditor pattern from ADP-SPEC-034

- [X] T023 [US3] Extend `web/src/business/ValueStreamStageEditor.tsx`: import StageCapsEditor; add `showCaps: Record<string, boolean>` state (keyed by stage.id); add "Capabilities" toggle button on each stage row (similar to existing edit/delete buttons); when toggled open, render `<StageCapsEditor vsId={vsId} stageId={stage.id} />` in an expandable panel below the stage row

**Checkpoint**: Stage-capability links fully functional. POST/GET/DELETE all work. 409 on duplicate. CASCADE verified. StageCapsEditor renders in stage editor UI.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [X] T024 Run quickstart.md API scenarios 1–9 via curl against running API server; verify all expected status codes and response shapes match contracts
- [X] T025 Manually verify browser scenarios 10–11 from quickstart.md: Domains tab on Business page (create domain, assign cap, verify badge); stage-capability mapping in ValueStreamDetail (link cap, verify domain badge, remove, verify empty)
- [X] T026 Update `docs/solution-architecture.md`: change status to ADP-SPEC-035; add migration 009 row to migrations table; extend Business Architecture section with: domain entity description (classification, risk_flags, ON DELETE SET NULL); stage-capability join table description; update router endpoint count

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — complete T001 before T002; T003 runs in parallel with T002
- **Phase 2 (US1 Domain CRUD)**: T004 (tests) written first; T005 (store) before T006 (router); T007/T008 parallel with backend; T009/T010 after T007; T011 after T009/T010
- **Phase 3 (US2 Assignment)**: T012 (tests) first; T013 (store) before T014 (router); T015/T016 parallel; T017 after T015 + T016
- **Phase 4 (US3 Stage-Caps)**: T018 (tests) first; T019 (store) before T020 (router); T021 parallel with backend; T022 after T021; T023 after T022
- **Phase 5 (Polish)**: All user stories complete

### User Story Dependencies

- **US1**: Depends on Phase 1 only. Delivers standalone domain CRUD.
- **US2**: Depends on Phase 1 + US1 store (needs domains to exist for assignment). Frontend can start parallel.
- **US3**: Depends on Phase 1 only (stage-cap links don't require domains). Can start after Phase 1 completes in parallel with US1/US2.

### Parallel Opportunities

- T003 (model unit tests) runs in parallel with T002 (model writing) after T001
- T007/T008 (frontend hooks + form) run in parallel with T005/T006 (backend)
- T015/T016 (assignment hook + node badge) run in parallel
- T021 (stage-cap hooks) runs in parallel with T019/T020 (backend)
- US3 (Phase 4) can start in parallel with US2 (Phase 3) once Phase 1 is complete

---

## Implementation Strategy

### MVP First (US1 Only)

1. Complete Phase 1 (T001–T003)
2. Complete Phase 2/US1 (T004–T011) — Domain CRUD with UI
3. **STOP and VALIDATE**: Three domains created, classified, listed ordered, deleted. Domains tab functional.

### Incremental Delivery

1. Phase 1 → Foundation ready (migration applied, models importable)
2. Phase 2/US1 → Domain registry live (create/browse/manage domains)
3. Phase 3/US2 → Capability ownership map live (L1 caps assigned to domains, tree badges visible)
4. Phase 4/US3 → Value stream analysis live (stage-capability links, horizontal-thread-meets-vertical-blocks)
5. Phase 5 → Verified and documented
