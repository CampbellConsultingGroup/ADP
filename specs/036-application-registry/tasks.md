# Tasks: Application Registry (ADP-SPEC-036)

**Input**: Design documents from `/specs/036-application-registry/`
**Prerequisites**: plan.md ✓ spec.md ✓ research.md ✓ data-model.md ✓ contracts/ ✓ quickstart.md ✓

**Tests**: Tests are MANDATORY for all ADP features (ART-IV). Test tasks appear before their implementation counterparts in every user-story phase. Write tests, verify they FAIL, then implement.

**Organization**: 7 user stories (P1–P7) + Setup + Foundational + Polish = 10 phases, 43 tasks total.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: Which user story (US1–US7) or phase (no label for Setup/Foundational/Polish)

---

## Phase 1: Setup (Module Init)

**Purpose**: Create the new `adp.application` module skeleton before any code is written.

- [X] T001 Create empty `src/adp/application/__init__.py` to initialize the new module

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Migration, Pydantic models, SA Table definitions, and router scaffolding that ALL user stories depend on. Nothing in US1–US7 can begin until this phase is complete.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 Write Alembic migration 010 in `src/adp/store/migrations/versions/010_application_registry.py` — 8 tables: `applications`, `technical_capabilities`, `application_capability_links`, `application_tech_cap_links`, `application_stage_links`, `application_domain_integrations`, `application_integrations`, `application_design_links`; `down_revision = "009"`; see data-model.md for full SQL (CHECK constraints, composite PKs, all FK behaviors)
- [X] T003 Write all Pydantic v2 models and error classes in `src/adp/application/models.py` — 30+ models: Application, ApplicationCreate, ApplicationUpdate, ApplicationListResponse; TechnicalCapability, TechnicalCapabilityCreate, TechnicalCapabilityUpdate, TechCapListResponse; ApplicationCapabilityLink/Create/Update/LinksResponse; ApplicationTechCapLink/Create/LinksResponse; ApplicationStageLink/Create/StageLinksResponse; ApplicationDomainIntegration/Create/IntegrationsResponse; ApplicationIntegration/Create/Update/ListResponse; ApplicationDesignLink/Create/DesignLinksResponse; error classes (TechCapHasChildrenError, TechCapDepthError, DuplicateAppCapLinkError, DuplicateAppTechCapLinkError, DuplicateAppStageLinkError, DuplicateAppDesignLinkError); all with `extra="forbid"`, Annotated[int, Field(ge=1, le=5)] for fit_score/health_score
- [X] T004 Write unit tests for all Pydantic models in `tests/unit/application/test_models.py` — cover: blank name → error; invalid TIME/R-strategy/pace_layer → error; health_score 0 → error; health_score 6 → error; fit_score 0 → error; fit_score 6 → error; source == target in ApplicationIntegrationCreate → error; blank integration_type in ApplicationDomainIntegrationCreate → error; invalid direction → error; valid full creates; run `pytest tests/unit/application/ -q` and verify all pass
- [X] T005 Write SA Table definitions and async engine/session factory in `src/adp/application/store.py` — define all 8 SA Tables (_applications, _tech_caps, _app_cap_links, _app_tech_cap_links, _app_stage_links, _app_domain_integrations, _app_integrations, _app_design_links) using same `sa.MetaData()` pattern as `adp.business.store`; create `_engine` and `_session_factory` using `ADP_DATABASE_URL` env var; no store functions yet
- [X] T006 Create FastAPI router scaffolding in `src/adp/application/router.py` — three APIRouter instances with prefixes `/api/v1/applications`, `/api/v1/technical-capabilities`, `/api/v1/integrations`; empty placeholder for each router; import models and store
- [X] T007 Register all three application routers in `src/adp/api/app.py` — `app.include_router(applications_router)`, `app.include_router(tech_caps_router)`, `app.include_router(integrations_router)`; verify `uvicorn adp.api.app:app` starts without errors after `alembic upgrade head`

**Checkpoint**: Migration applied, models unit-tested, routers registered, server starts. US1–US7 can now begin.

---

## Phase 3: User Story 1 — Application Core CRUD (Priority: P1) 🎯 MVP

**Goal**: Architect can create, list, retrieve, update, and delete applications. All strategic classification fields (TIME, R-strategy, pace layer, health score) are persisted and validated.

**Independent Test**: `pytest tests/integration/test_application_api.py::test_application_create_201 tests/integration/test_application_api.py::test_application_list_ordered tests/integration/test_application_api.py::test_application_delete_204 -q`

### Tests for User Story 1 (MANDATORY — ART-IV)

> **Write these tests FIRST. Run them. Verify they FAIL before implementing T009/T010.**

- [X] T008 [US1] Write US1 integration tests in `tests/integration/test_application_api.py` — add helper `_create_app(client, **kwargs)` that POSTs to `/api/v1/applications` and returns id; add tests: `test_application_create_201` (all fields returned, UUID id), `test_application_list_ordered` (Zorro + Alpha → Alpha first), `test_application_get_200`, `test_application_update_200` (PATCH vendor → updated), `test_application_delete_204` (DELETE → 204; GET → 404), `test_application_blank_name_422`, `test_application_invalid_time_422` (time="Spend" → 422), `test_application_health_score_0_422`, `test_application_health_score_6_422`, `test_application_health_score_5_201`, `test_application_not_found_404`

### Implementation for User Story 1

- [X] T009 [US1] Implement US1 store functions in `src/adp/application/store.py` — `list_applications(session)`, `get_application(app_id, session)`, `create_application(body, session)`, `update_application(app_id, body, session)`, `delete_application(app_id, session)`; log create/update/delete via `logger.info()`; use `uuid.uuid4()` for id; ORDER BY name in list; run T008 tests and verify they pass
- [X] T010 [US1] Implement US1 router endpoints in `src/adp/application/router.py` — `GET /`, `POST /` (→201), `GET /{app_id}`, `PATCH /{app_id}`, `DELETE /{app_id}` (→204); map DuplicateAppCapLinkError/TechCapHasChildrenError to appropriate HTTP codes; run T008 tests and verify they pass

- [X] T011 [P] [US1] Write TS interfaces + TanStack Query hooks for applications in `web/src/api/application.ts` — Application, ApplicationCreate, ApplicationUpdate, ApplicationListResponse interfaces; `useApplications()`, `useApplication(id)`, `useCreateApplication()`, `useUpdateApplication(id)`, `useDeleteApplication()` hooks using `useSuspenseQuery` / `useMutation` from `@tanstack/react-query`
- [X] T012 [P] [US1] Create ApplicationList.tsx in `web/src/application/ApplicationList.tsx` — list of Application cards: name, vendor, TIME badge (colour-coded: Invest=green, Migrate=amber, Eliminate=red, Tolerate=grey), health_score dots, "Add Application" button; onClick → selectedAppId prop
- [X] T013 [P] [US1] Create ApplicationForm.tsx in `web/src/application/ApplicationForm.tsx` — create/edit form: name (required), description, vendor, primary_owner free-text inputs; TIME select (Tolerate/Invest/Migrate/Eliminate + empty); R-strategy select (7 options + empty); pace_layer select (3 options + empty); health_score number input (1–5); submit calls useCreateApplication or useUpdateApplication
- [X] T014 [US1] Create ApplicationPage.tsx and ApplicationDetail.tsx scaffold in `web/src/application/` — ApplicationPage.tsx: renders ApplicationList with selectedAppId state + ApplicationDetail panel; ApplicationDetail.tsx: shows application fields + placeholder sections for links; wire to App.tsx `/applications` route and add "Applications" item to NavBar.tsx

**Checkpoint**: User Story 1 fully functional — create/list/get/update/delete applications with TIME/R-strategy/pace/health validation. MVP deliverable.

---

## Phase 4: User Story 2 — Business Capability Linkage with Fit Score (Priority: P2)

**Goal**: Architect links applications to business capabilities with fit scores (1–5). Links are listed, updated, and removed.

**Independent Test**: Create app + biz cap → link with fit_score=3 → verify list → update score to 5 → delete → verify empty.

### Tests for User Story 2 (MANDATORY — ART-IV)

- [X] T015 [US2] Write US2 integration tests in `tests/integration/test_application_api.py` — tests: `test_app_cap_link_create_201` (POST link → 201, capability_name in response), `test_app_cap_link_list_includes_name`, `test_app_cap_link_update_score` (PATCH fit_score=5 → 200), `test_app_cap_link_duplicate_409`, `test_app_cap_link_fit_score_0_422`, `test_app_cap_link_fit_score_6_422`, `test_app_cap_link_delete_204` (DELETE → 204; list → empty); create a business capability using `/api/v1/business/capabilities` in the helper or fixture

### Implementation for User Story 2

- [X] T016 [US2] Implement US2 store functions in `src/adp/application/store.py` — `list_app_capability_links(app_id, session)`, `create_app_capability_link(app_id, body, session)` (raises DuplicateAppCapLinkError on duplicate; check app + cap existence → 404), `update_app_capability_link(app_id, cap_id, body, session)`, `delete_app_capability_link(app_id, cap_id, session)`; JOIN `business_capabilities` for capability_name in list result
- [X] T017 [US2] Implement US2 router endpoints in `src/adp/application/router.py` — sub-prefix `/{app_id}/capability-links`: `GET /`, `POST /` (→201), `PATCH /{capability_id}`, `DELETE /{capability_id}` (→204); DuplicateAppCapLinkError → 409; run T015 tests and verify they pass
- [X] T018 [US2] Create CapabilityLinksEditor.tsx in `web/src/application/CapabilityLinksEditor.tsx` — list of linked capabilities with fit_score badge; picker (useCapabilities hook from business.ts, filtered to show unlinked ones); fit_score number input (1–5); "Link" button → useCreateAppCapLink mutation; "Remove" × per row → useDeleteAppCapLink; 409 → "Already linked" toast; extend ApplicationDetail.tsx with "Business Capabilities" section

**Checkpoint**: User Stories 1 + 2 both functional independently.

---

## Phase 5: User Story 3 — Technical Capability Hierarchy (Priority: P3)

**Goal**: Architect creates and manages a user-defined 3-level technical capability tree. Depth is enforced; deleting a parent with children is blocked.

**Independent Test**: Create L1 → L2 under L1 → L3 under L2 → attempt L4 (expect 422) → delete L3 (204) → attempt delete L2-with-now-gone-L3 (204) → L1 survives.

### Tests for User Story 3 (MANDATORY — ART-IV)

- [X] T019 [US3] Write US3 integration tests in `tests/integration/test_application_api.py` — tests: `test_tech_cap_create_l1_201` (no parent → level=1), `test_tech_cap_create_l2_201` (parent=L1 → level=2), `test_tech_cap_create_l3_201` (parent=L2 → level=3), `test_tech_cap_depth_exceeded_422` (parent=L3 → 422), `test_tech_cap_list_returns_hierarchy`, `test_tech_cap_delete_leaf_204`, `test_tech_cap_delete_with_children_409`, `test_tech_cap_parent_not_found_404`

### Implementation for User Story 3

- [X] T020 [US3] Implement US3 store functions in `src/adp/application/store.py` — `list_technical_capabilities(session)`, `get_technical_capability(tc_id, session)`, `create_technical_capability(body, session)` (validates parent exists; SELECT parent.level → if level=3 raise TechCapDepthError; derived level = parent_level+1 or 1 if no parent), `update_technical_capability(tc_id, body, session)`, `delete_technical_capability(tc_id, session)` (SELECT COUNT children → if >0 raise TechCapHasChildrenError)
- [X] T021 [US3] Implement US3 router endpoints in `/api/v1/technical-capabilities` in `src/adp/application/router.py` — `GET /`, `POST /` (→201), `GET /{tc_id}`, `PATCH /{tc_id}`, `DELETE /{tc_id}` (→204); TechCapDepthError → 422; TechCapHasChildrenError → 409; run T019 tests and verify they pass
- [X] T022 [US3] Create TechCapTree.tsx and TechCapForm.tsx in `web/src/application/` — TechCapTree.tsx: indented tree view (L1 → L2 → L3); "Add child" button at each node (disabled on L3); "Delete" button only on leaf nodes; TechCapForm.tsx: name + description inputs + optional parent_id (hidden, passed via button); hooks: useTechCaps(), useCreateTechCap(), useDeleteTechCap(); add "Technical Capabilities" page or tab reachable from ApplicationPage or NavBar

**Checkpoint**: User Stories 1–3 all functional independently.

---

## Phase 6: User Story 4 — Application–Technical Capability Links (Priority: P4)

**Goal**: Architect declares an application "provides" or "consumes" a technical capability. The same app can both provide and consume the same tech cap (different usage_type).

**Independent Test**: Create app + L3 tech cap → add "provides" link → add "consumes" link (same tech cap) → list → 2 links with distinct usage_type → delete "provides" link → 1 link remains.

### Tests for User Story 4 (MANDATORY — ART-IV)

- [X] T023 [US4] Write US4 integration tests in `tests/integration/test_application_api.py` — tests: `test_app_tech_cap_provides_201`, `test_app_tech_cap_consumes_201`, `test_app_tech_cap_both_same_cap_allowed` (provides+consumes same tech_cap → 201+201), `test_app_tech_cap_duplicate_409` (third POST same tuple → 409), `test_app_tech_cap_invalid_type_422` (usage_type="reads" → 422), `test_app_tech_cap_list_includes_tech_cap_name`, `test_app_tech_cap_delete_204`

### Implementation for User Story 4

- [X] T024 [US4] Implement US4 store functions in `src/adp/application/store.py` — `list_app_tech_cap_links(app_id, session)`, `create_app_tech_cap_link(app_id, body, session)` (check app + tech_cap existence; INSERT with composite PK (app_id, tech_cap_id, usage_type); ON CONFLICT raise DuplicateAppTechCapLinkError), `delete_app_tech_cap_link(app_id, tc_id, usage_type, session)`; JOIN technical_capabilities for tech_cap_name
- [X] T025 [US4] Implement US4 router endpoints in `src/adp/application/router.py` — sub-prefix `/{app_id}/technical-capability-links`: `GET /`, `POST /` (→201), `DELETE /{tc_id}/{usage_type}` (→204); DuplicateAppTechCapLinkError → 409; run T023 tests and verify they pass
- [X] T026 [US4] Create TechCapLinkEditor.tsx in `web/src/application/TechCapLinkEditor.tsx` — list of linked tech caps with provides/consumes badge (green/blue); picker (useTechCaps hook); usage_type radio button ("provides" / "consumes"); "Link" button; "Remove" × per row; 409 → "Already linked" toast; extend ApplicationDetail.tsx with "Technical Capabilities" section

**Checkpoint**: User Stories 1–4 all functional independently.

---

## Phase 7: User Story 5 — Value Stream Stage and Domain Linkage (Priority: P5)

**Goal**: Architect links applications to value stream stages and to business domains with integration direction. Cascade deletes on stage/domain removal.

**Independent Test**: Create app + VS + stage → link stage (201) → duplicate (409) → delete link (204). Create app + domain → domain integration (201, direction=inbound) → delete domain → link gone.

### Tests for User Story 5 (MANDATORY — ART-IV)

- [X] T027 [US5] Write US5 integration tests in `tests/integration/test_application_api.py` — tests: `test_app_stage_link_create_201` (stage_name in response), `test_app_stage_link_duplicate_409`, `test_app_stage_link_delete_204`, `test_app_stage_cascade_delete_stage` (delete VS stage → GET stage-links → empty), `test_app_domain_integration_create_201` (domain_name in response), `test_app_domain_integration_invalid_direction_422`, `test_app_domain_integration_delete_204`, `test_app_domain_integration_cascade_delete_domain` (delete domain → GET domain-integrations → empty)

### Implementation for User Story 5

- [X] T028 [US5] Implement US5 store functions in `src/adp/application/store.py` — stage-links: `list_app_stage_links(app_id, session)`, `create_app_stage_link(app_id, body, session)` (raises DuplicateAppStageLinkError), `delete_app_stage_link(app_id, stage_id, session)`; domain integrations: `list_app_domain_integrations(app_id, session)`, `create_app_domain_integration(app_id, body, session)`, `delete_app_domain_integration(app_id, link_id, session)`; LEFT JOIN business_domains for domain_name; LEFT JOIN value_stream_stages for stage_name
- [X] T029 [US5] Implement US5 router endpoints in `src/adp/application/router.py` — stage-links sub-prefix `/{app_id}/stage-links`: `GET /`, `POST /` (→201), `DELETE /{stage_id}` (→204); domain-integrations sub-prefix `/{app_id}/domain-integrations`: `GET /`, `POST /` (→201), `DELETE /{link_id}` (→204); DuplicateAppStageLinkError → 409; run T027 tests and verify they pass
- [X] T030 [US5] Create StageLinkEditor.tsx and DomainIntegrationEditor.tsx in `web/src/application/` — StageLinkEditor.tsx: linked stages list + VS/stage picker from useValueStreams hook; DomainIntegrationEditor.tsx: linked domain integrations list with direction badge (inbound=blue, outbound=green, bidirectional=purple); direction select; integration_type free-text input; extend ApplicationDetail.tsx with "Value Stream Stages" and "Domain Integrations" sections

**Checkpoint**: User Stories 1–5 all functional independently.

---

## Phase 8: User Story 6 — Application Integration Registry (Priority: P6)

**Goal**: Architect registers point-to-point integrations between applications (first-class entities with UUIDs). Self-integration rejected. Bidirectional (A→B + B→A) permitted. Cascade-delete when either endpoint is deleted.

**Independent Test**: Create app A + B → integration A→B type=API (201) → list by app_id → get by id → update description → reject self-loop → create B→A (201, bidirectional ok) → delete A → integration A→B gone.

### Tests for User Story 6 (MANDATORY — ART-IV)

- [X] T031 [US6] Write US6 integration tests in `tests/integration/test_application_api.py` — tests: `test_integration_create_201` (source/target names in response), `test_integration_self_422`, `test_integration_invalid_type_422`, `test_integration_list_by_app_id` (GET /integrations?app_id=A → A→B appears), `test_integration_bidirectional_permitted` (B→A after A→B → 201), `test_integration_get_200`, `test_integration_update_description` (PATCH → 200), `test_integration_delete_204`, `test_integration_cascade_source_delete` (delete source app → integration gone), `test_integration_cascade_target_delete`

### Implementation for User Story 6

- [X] T032 [US6] Implement US6 store functions in `src/adp/application/store.py` — `list_integrations(app_id_filter, session)` (WHERE source_app_id=? OR target_app_id=?; JOIN applications twice aliased for source_app_name and target_app_name), `get_integration(int_id, session)`, `create_integration(body, session)` (validate source + target exist; source≠target already checked by Pydantic model_validator), `update_integration(int_id, body, session)` (description only), `delete_integration(int_id, session)`
- [X] T033 [US6] Implement US6 router endpoints in `/api/v1/integrations` in `src/adp/application/router.py` — `GET /` (optional `?app_id` query param), `POST /` (→201), `GET /{int_id}`, `PATCH /{int_id}`, `DELETE /{int_id}` (→204); run T031 tests and verify they pass
- [X] T034 [P] [US6] Create IntegrationList.tsx and IntegrationForm.tsx in `web/src/application/` — IntegrationList.tsx: table with source app name → target app name → type badge → description; filter by selected application; IntegrationForm.tsx: source app select, target app select, integration_type select (API/event/file/database/messaging/other), description textarea; hooks: useIntegrations(appId), useCreateIntegration(), useUpdateIntegration(id), useDeleteIntegration(); add "Integrations" tab or sub-page in ApplicationDetail.tsx

**Checkpoint**: User Stories 1–6 all functional independently.

---

## Phase 9: User Story 7 — Design Linkage (Priority: P7)

**Goal**: Architect links applications to ADP Designs for registry-to-model traceability. Non-existent design_id returns 404. Duplicate link returns 409.

**Independent Test**: Create app + get valid design_id → link (201) → list → design_id present → duplicate (409) → delete (204) → list empty. Non-existent design_id → 404.

### Tests for User Story 7 (MANDATORY — ART-IV)

- [X] T035 [US7] Write US7 integration tests in `tests/integration/test_application_api.py` — tests: `test_app_design_link_create_201` (create a design first via /api/v1/designs; link to app → 201), `test_app_design_link_nonexistent_design_404`, `test_app_design_link_duplicate_409`, `test_app_design_link_list`, `test_app_design_link_delete_204`

### Implementation for User Story 7

- [X] T036 [US7] Implement US7 store functions in `src/adp/application/store.py` — `list_app_design_links(app_id, session)`, `create_app_design_link(app_id, body, session)` (SELECT from designs WHERE id=design_id; if not found raise ValueError "design not found" → 404; INSERT; ON CONFLICT raise DuplicateAppDesignLinkError → 409), `delete_app_design_link(app_id, design_id, session)`
- [X] T037 [US7] Implement US7 router endpoints in `src/adp/application/router.py` — sub-prefix `/{app_id}/design-links`: `GET /`, `POST /` (→201), `DELETE /{design_id}` (→204); run T035 tests and verify they pass
- [X] T038 [US7] Create DesignLinkEditor.tsx in `web/src/application/DesignLinkEditor.tsx` — list of linked designs (design_id as label); input field for design_id or picker from existing designs list; "Link" button; "Remove" × per row; 404 → "Design not found" toast; 409 → "Already linked" toast; extend ApplicationDetail.tsx with "Linked Designs" section

**Checkpoint**: All 7 user stories fully functional and independently testable.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Cross-cutting test, documentation, and quickstart validation.

- [X] T039 Write cascade-delete test in `tests/integration/test_application_api.py` — `test_application_delete_cascades_all_links`: create app; add biz-cap link, tech-cap link, stage link, domain integration, integration (as source), integration (as target), design link; DELETE app → 204; verify each link table returns empty for that app_id; verify integrations where app was source/target are gone
- [X] T040 [P] Update `docs/solution-architecture.md` — add ADP-SPEC-036 entry to the spec status table; add migration 010 row to the migration history table; add application registry section describing the 8 new tables and 3 router prefixes
- [X] T041 Run quickstart.md scenarios 1–21 against a live API server — verify each scenario produces the documented response code; record any deviations and fix before marking complete

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 — **BLOCKS all user stories**
- **Phase 3 (US1)**: Depends on Phase 2 only
- **Phase 4 (US2)**: Depends on Phase 2; also requires a business_capabilities row (from ADP-SPEC-033 already deployed) — no code dependency on US1
- **Phase 5 (US3)**: Depends on Phase 2 only; independent of US1/US2
- **Phase 6 (US4)**: Depends on Phase 2 + Phase 5 (tech_caps must exist in DB)
- **Phase 7 (US5)**: Depends on Phase 2; requires value_stream_stages and business_domains rows (from ADP-SPEC-033/035 already deployed) — no code dependency on US1
- **Phase 8 (US6)**: Depends on Phase 2 + Phase 3 (needs application rows to create integrations, though code only requires Phase 2)
- **Phase 9 (US7)**: Depends on Phase 2; requires a designs row (from ADP-SPEC-002 already deployed)
- **Phase 10 (Polish)**: Depends on all desired user stories being complete

### User Story Dependencies

| Story | Depends On | Blocks |
|---|---|---|
| US1 Application CRUD | Phase 2 | US6 (needs apps to exist) |
| US2 Biz Cap Links | Phase 2 | — |
| US3 Tech Cap Hierarchy | Phase 2 | US4 |
| US4 Tech Cap Links | Phase 2, US3 | — |
| US5 Stage+Domain Links | Phase 2 | — |
| US6 Integration Registry | Phase 2 (US1 for test data) | — |
| US7 Design Links | Phase 2 | — |

### Parallel Opportunities

Within Phase 2 (once T002 migration is applied):
- T003 (models) and T004 (unit tests) can be written in parallel — T004 reads T003
- T005 (store Tables) and T006 (router scaffold) can be written in parallel with T003

Within each user story phase, tests and TypeScript tasks can run in parallel:
- T008 (tests) can be written by one developer while T011/T012/T013 (frontend) are written by another
- T015 (US2 tests) + T011–T013 (US1 frontend) can overlap if US1 store/router is done

---

## Parallel Example: User Story 1

```bash
# After T002+T003+T005+T006+T007 complete, these US1 tasks can run in parallel:
Task T008: "Write US1 integration tests in tests/integration/test_application_api.py"
Task T011: "Write TS interfaces + hooks in web/src/api/application.ts"
Task T012: "Create ApplicationList.tsx and ApplicationForm.tsx"

# After T008+T009, these can run in parallel:
Task T010: "Implement US1 router endpoints in src/adp/application/router.py"
Task T013: "Create ApplicationPage.tsx and ApplicationDetail.tsx scaffold"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Module init
2. Complete Phase 2: Foundational (migration + models + unit tests + store Tables + router scaffold + register)
3. Complete Phase 3: User Story 1 (Application CRUD — backend + frontend)
4. **STOP and VALIDATE**: Run T008 tests; demo create/list/update/delete in browser
5. Deploy/demo if ready — this is a fully useful MVP

### Incremental Delivery

Each subsequent user story adds a slice of linkage without breaking US1:
- US2 adds business capability fit scores (most critical for future ADP-SPEC-037 heat maps)
- US3 adds the technical capability tree (prerequisite for US4)
- US4 adds tech cap provides/consumes links
- US5 adds stage + domain contextualisation
- US6 adds integration topology
- US7 adds design traceability (closes the loop between registry and C4 model)

---

## Notes

- Always run `alembic upgrade head` before integration tests
- `ADP_DATABASE_URL` must be set; integration tests use `testcontainers` (see `tests/integration/conftest.py`)
- SA Core only — no ORM mapper; follow the pattern in `src/adp/business/store.py`
- All mutations: emit `logger.info(actor=..., entity=..., id=..., action=...)` (ART-IX via ART-VI)
- `extra="forbid"` on all Pydantic models (ART-XIII)
- Tests MUST be committed and verified to fail before implementation tasks are started (ART-IV)
