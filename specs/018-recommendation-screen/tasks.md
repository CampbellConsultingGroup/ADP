# Tasks: Architecture Recommendation Screen

**Input**: Design documents from `/specs/018-recommendation-screen/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: Tests are MANDATORY for all ADP features (ART-IV). Contract tests appear before their implementation tasks.

**Critical prerequisite**: T001 (audit ID bug fix in `materialize_option()`) MUST be completed before ANY accept endpoint can work without a UniqueViolationError.

---

## Phase 1: Setup

**Purpose**: Fix the blocking bug, create file skeletons, register router

- [X] T001 Fix audit ID generation in `src/adp/recommendation/orchestrator.py`: in `materialize_option()`, replace `audit_entry_id = f"AUD-{len(design.audit_log) + 1:03d}"` with `from adp.intake.orchestrator import _next_audit_id; audit_entry_id = _next_audit_id(design)` — same fix as ADP-SPEC-017; without this, any accept on a design with existing audit entries raises UniqueViolationError on `audit_entries` PK
- [X] T002 Create `src/adp/api/routers/recommend.py` with: all Pydantic v2 models (`RecommendRequest`, `RecommendStatusResponse`, `TradeOffEntryResponse`, `ProposedElementResponse`, `SolutionOptionResponse`, `AcceptOptionRequest`, `ElementSummaryResponse`, `AcceptOptionResponse` — all `extra="forbid"`); module-level `_recommend_store: dict[str, Any] = {}`; empty `router = APIRouter(prefix="/api/v1/designs", tags=["recommend"])`; `_make_stub_knowledge_retrieval()` that returns a stub `KnowledgeRetrieval` whose `hybrid_search()` returns `[]` (graceful degradation when pgvector not indexed); `_make_recommend_orchestrator(model: str | None = None)` that creates `RecommendationOrchestrator` with stub knowledge retrieval and `LLMClient` (same pattern as `_make_orchestrator()` in `intake.py`)
- [X] T003 [P] Create `web/src/api/recommend.ts` with all TypeScript interfaces from `data-model.md` (`RecommendStatus`, `OptionStatus`, `TradeOffStance`, `RecommendRequest`, `TradeOffEntry`, `ProposedElement`, `SolutionOption`, `RecommendStatusResponse`, `AcceptOptionRequest`, `ElementSummary`, `AcceptOptionResponse`) and three stub hook functions that throw `new Error("not implemented")`: `useStartRecommendation`, `useRecommendStatus`, `useAcceptOption`
- [X] T004 Register `recommend.router` in `src/adp/api/app.py`: add `from adp.api.routers import recommend` and `app.include_router(recommend.router)` after the existing routers
- [X] T005 [P] Create stub component files: `web/src/recommend/RecommendationPage.tsx`, `web/src/recommend/RequirementSelector.tsx`, `web/src/recommend/OptionCard.tsx`, `web/src/recommend/AcceptDialog.tsx` — each as a bare React stub returning `<div>placeholder</div>`

**Checkpoint**: `python3 -c "from adp.api.routers.recommend import router; print('ok')"` succeeds; `cd web && npm run tsc` passes with stubs

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: `_map_option_to_response()` converter — used by both US1 (status) and US2 (accept); no story tasks can begin without it

- [X] T006 Add `_map_option_to_response(opt)` helper to `src/adp/api/routers/recommend.py`: converts a `SolutionOption` dataclass to `SolutionOptionResponse` Pydantic model — maps `option_id`, `rank`, `title`, `rationale`, `advisory`, `satisfies`, `trade_offs` → `list[TradeOffEntryResponse]`, `proposed_elements` → `list[ProposedElementResponse]`, `grounded_on` as `[ref.item_id for ref in opt.grounded_on]`, `ranking_score`, `status`; also add `_get_design_store_dep()` async dependency and `_get_actor()` helper (same pattern as intake.py)

**Checkpoint**: `python3 -c "from adp.api.routers.recommend import _map_option_to_response; print('ok')"` succeeds

---

## Phase 3: User Story 1 — Request and View Recommendations (Priority: P1) 🎯 MVP

**Goal**: POST /recommend starts the pipeline; GET /recommend/{op_id} returns status and ranked options; RecommendationPage shows options with trade-off tables and proposed elements.

**Independent Test**: POST with valid requirement_ids → 202 with operation_id; GET → 200 with status.

### Tests for User Story 1 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T007 [P] [US1] Write failing `test_recommend_returns_202()` in `tests/contract/test_recommend_api.py`: mock DesignStore + mock KnowledgeRetrieval; POST `{"requirement_ids": ["REQ-001"]}` to `/api/v1/designs/D-001/recommend`; assert 202; assert response has `operation_id` (non-empty string) and `status == "pending"`
- [X] T008 [P] [US1] Write failing `test_recommend_status_returns_200()` in `tests/contract/test_recommend_api.py`: after a valid submit, GET `/api/v1/designs/D-001/recommend/{operation_id}`; assert 200; assert response has `status` in `("pending","running","completed","failed")` and `options` list
- [X] T009 [P] [US1] Write failing `test_recommend_empty_requirement_ids_returns_422()` in `tests/contract/test_recommend_api.py`: POST `{"requirement_ids": []}` (empty list); assert 422

### Implementation for User Story 1

- [X] T010 [US1] Implement `POST /api/v1/designs/{design_id}/recommend` in `src/adp/api/routers/recommend.py`: (1) validate `RecommendRequest` (Pydantic raises 422 on empty requirement_ids — add `@field_validator("requirement_ids")` that raises if empty); (2) verify design exists via `store.get(design_id)` (404 if DesignNotFoundError); (3) generate `operation_id = str(uuid.uuid4())`; (4) seed `_recommend_store[operation_id] = {"status": "pending", "design_id": design_id, "requirement_ids": request.requirement_ids, "options": {}, "result_summary": None, "error_description": None, "correlation_id": get_trace_id(), "created_at": datetime.now(timezone.utc)}`; (5) build orchestrator with stub knowledge retrieval and configured LLM; (6) `background_tasks.add_task(orchestrator.run, operation_id, design_id, request.requirement_ids, _recommend_store, correlation_id)`; (7) return 202 `RecommendStatusResponse`; verify T007 passes
- [X] T011 [US1] Implement `GET /api/v1/designs/{design_id}/recommend/{operation_id}` in `src/adp/api/routers/recommend.py`: look up `_recommend_store[operation_id]` (404 if missing); map stored options to `list[SolutionOptionResponse]` using `_map_option_to_response()`; sort by rank; return `RecommendStatusResponse`; verify T008 and T009 pass
- [X] T012 [US1] Implement `useStartRecommendation(designId: string)` in `web/src/api/recommend.ts`: `useMutation` that POSTs to `/api/v1/designs/${designId}/recommend`; on success, does NOT invalidate (the operation is polled separately)
- [X] T013 [US1] Implement `useRecommendStatus(designId: string, operationId: string | null)` in `web/src/api/recommend.ts`: `useQuery` with `enabled: !!operationId`; `refetchInterval: (q) => (!q.state.data?.status || q.state.data.status === "completed" || q.state.data.status === "failed") ? false : 2000`
- [X] T014 [US1] Create `web/src/recommend/OptionCard.tsx`: renders one `SolutionOption` with: (a) header row — rank badge (`#1`), title, ranking score as percentage, advisory badge (`⚠️ ADVISORY` in amber if `option.advisory`); (b) advisory warning box if advisory — "This option lacks full knowledge-base grounding. Additional review recommended."; (c) rationale paragraph; (d) trade-off table — three columns: Criterion | Stance (✅ meets / ⚠️ partially meets / ❌ does not meet) | Rationale; (e) proposed elements list — each shows `[kind]` badge + name + description; (f) "Grounded on: KI-001, KI-002" if `grounded_on` non-empty, "No knowledge citations (advisory)" otherwise; (g) "Accept this option" button (calls `onAccept` prop — wired in US2)
- [X] T015 [US1] Implement partial `web/src/recommend/RecommendationPage.tsx`: (a) layout with header (title "Architecture Recommendations" + design ID + "Go to Canvas" button); (b) `RequirementSelector` at top (stub for now — passes all requirement IDs via `onRequirementIdsChange`); (c) extraction status (spinner while running; error banner while failed); (d) renders `<OptionCard>` for each option when status=completed; (e) empty state: "No options generated — try again or check LLM settings" when completed with 0 options; `onAccept` on each OptionCard is a no-op placeholder (wired in US2)

**Checkpoint**: `pytest tests/contract/test_recommend_api.py::test_recommend_returns_202 tests/contract/test_recommend_api.py::test_recommend_status_returns_200 -v --no-cov` green; `RecommendationPage` renders at runtime with options (advisory in empty-KB env)

---

## Phase 4: User Story 2 — Accept a Recommendation (Priority: P1)

**Goal**: POST /accept materialises proposed elements into the design; confirmation dialog prevents accidental accept; advisory acknowledgement required for advisory options; navigates to canvas on success.

**Independent Test**: POST accept with valid `confirmation_id` → 200 with `elements_created`; assert design has new elements; assert audit entry written.

### Tests for User Story 2 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T016 [P] [US2] Write failing `test_accept_option_returns_200()` in `tests/contract/test_recommend_api.py`: seed `_recommend_store` with a mock operation containing one pending `SolutionOption`; POST `{"confirmation_id": "CONF-TEST", "advisory_acknowledged": false}` to accept endpoint; assert 200; assert response has `elements_created` (list) and `audit_entry_id`
- [X] T017 [P] [US2] Write failing `test_accept_blank_confirmation_id_returns_422()`: POST `{"confirmation_id": "", "advisory_acknowledged": false}`; assert 422
- [X] T018 [P] [US2] Write failing `test_accept_already_accepted_returns_409()`: seed with already-accepted option (status="accepted"); POST accept; assert 409
- [X] T019 [P] [US2] Write failing `test_accept_advisory_without_acknowledged_returns_422()`: seed with advisory=True option; POST `{"confirmation_id": "CONF-TEST", "advisory_acknowledged": false}`; assert 422

### Implementation for User Story 2

- [X] T020 [US2] Implement `POST /api/v1/designs/{design_id}/recommend/{operation_id}/options/{option_id}/accept` in `src/adp/api/routers/recommend.py`: (1) validate `AcceptOptionRequest` — `confirmation_id` non-empty (field_validator); (2) look up operation (404 if missing); (3) look up option (404 if missing); (4) 409 if option.status != "pending"; (5) if `option.advisory and not request.advisory_acknowledged` → 422 "advisory option requires advisory_acknowledged=true"; (6) call `await orchestrator.materialize_option(option_id, operation_id, actor, _recommend_store, design_id, advisory_acknowledged=request.advisory_acknowledged)`; (7) capture `audit_entry_id` from audit log; (8) return `AcceptOptionResponse`; verify T016–T019 pass
- [X] T021 [P] [US2] Implement `useAcceptOption(designId: string, operationId: string)` in `web/src/api/recommend.ts`: `useMutation`; on success: invalidate `["design", designId]` query (canvas will reload with new elements)
- [X] T022 [US2] Create `web/src/recommend/AcceptDialog.tsx`: modal dialog; props: `option: SolutionOption`, `onConfirm(req: AcceptOptionRequest)`, `onCancel()`; shows: (a) "Accept Recommendation" title; (b) option title and rank; (c) "This will add N elements to {designId}: [kind] Name" list; (d) if `option.advisory`: amber warning box + required checkbox "I understand this option lacks full knowledge-base grounding and accept additional review responsibility" that must be checked before confirm button is enabled; (e) "Cancel" and "Confirm Accept" buttons — Confirm disabled until advisory checkbox checked (if advisory) AND `useAcceptOption` not pending
- [X] T023 [US2] Wire accept in `web/src/recommend/OptionCard.tsx`: `onAccept` prop becomes `() => setShowDialog(true)`; render `<AcceptDialog>` when `showDialog=true`; on `onConfirm`: call `acceptMutation.mutate({optionId, ...req})`; on success: close dialog, show "✓ Accepted — navigating to canvas..." message; card shows "Accepted" status after mutation succeeds
- [X] T024 [US2] Update `web/src/recommend/RecommendationPage.tsx` to pass the `onNavigate` prop down to `OptionCard` as `onAcceptSuccess`; wire accept mutation success → call `onNavigate("canvas")` (I2 fix: was `onNavigateToCanvas()` / `onBack()` — now uses the single `onNavigate` interface established in T027)

**Checkpoint**: `pytest tests/contract/test_recommend_api.py -v --no-cov` all green; accept flow: dialog → confirm → elements appear on canvas when navigated there

---

## Phase 5: User Story 3 — Select Requirements for Recommendation (Priority: P2)

**Goal**: Checkbox list of confirmed requirements; all checked by default; "Get Recommendations" disabled when none checked; sends only selected IDs.

**Independent Test**: Load page with 3 requirements; all checked; uncheck 1; click Get Recommendations; assert only 2 IDs sent in request.

### Implementation for User Story 3

- [X] T025 [US3] Implement `web/src/recommend/RequirementSelector.tsx`: (a) call `useRequirements(designId)` to get confirmed requirements; (b) `useState<Set<string>>` initialised with ALL requirement IDs; (c) render checkbox per requirement: `[kind badge] REQ-ID  Title text`; (d) "Get Recommendations" button — disabled when `selectedIds.size === 0` or `isPending`; (e) passes `Array.from(selectedIds)` via `onSubmit(ids: string[])` prop when button clicked; (f) shows "Add requirements via the Intake screen to get recommendations" when requirements list is empty
- [X] T026 [US3] Update `web/src/recommend/RecommendationPage.tsx` to wire `RequirementSelector.onSubmit` → `startRecommendation.mutate({requirement_ids: ids, model: selectedModel})` — replace the placeholder from US1

**Checkpoint**: Uncheck a requirement; click Get Recommendations; only the selected IDs appear in the network request

---

## Phase 6: Polish & Three-View Navigation

**Purpose**: Wire the three-view nav across all pages; lint; E2E tests

- [X] T027 Update `web/src/App.tsx` (I1 fix — establishes single navigation interface): (a) change view state from `"canvas" | "intake"` to `"canvas" | "intake" | "recommend"`; (b) define `onNavigate = (view: "canvas" | "intake" | "recommend") => setView(view)` and pass it as `onNavigate` prop to ALL THREE page components — `IntakePage`, `Workspace`, and `RecommendationPage`; this single prop REPLACES the existing `onBack`, `onNavigateToIntake`, `onNavigateToIntake`, `onNavigateToRecommend` props (all pages now receive the same interface); (c) render `<RecommendationPage designId={designId} onNavigate={onNavigate} />` when `view === "recommend"`; (d) keep default view as `"intake"` (ADP-SPEC-016)
- [X] T028 [P] Update `web/src/intake/IntakePage.tsx` header (I1 fix — use `onNavigate` not `onBack`): update `IntakePageProps` to replace `onBack: () => void` with `onNavigate: (view: "canvas" | "intake" | "recommend") => void`; replace the single "Go to Canvas →" button with a three-button nav `[Intake (active)] [Recommendations] [Canvas]`; active button (Intake) uses solid blue background; clicking Recommendations → `onNavigate("recommend")`; clicking Canvas → `onNavigate("canvas")`
- [X] T029 [P] Update `web/src/canvas/Workspace.tsx` header (I1 fix — use `onNavigate` not `onNavigateToIntake`): update `WorkspaceProps` to replace `onNavigateToIntake?: () => void` with `onNavigate: (view: "canvas" | "intake" | "recommend") => void`; render three-button nav `[Intake] [Recommendations] [Canvas (active)]`; active button (Canvas) uses solid blue background; clicking Intake → `onNavigate("intake")`; clicking Recommendations → `onNavigate("recommend")`
- [X] T030 [P] Run `ruff check src/adp/api/routers/recommend.py src/adp/recommendation/orchestrator.py` — fix all lint errors
- [X] T031 [P] Run `cd web && npm run tsc` — zero TypeScript errors across all new recommend files and modified App.tsx, IntakePage.tsx, Workspace.tsx
- [X] T032 [P] Extend `web/tests/e2e/api.spec.ts` with recommend E2E tests: `test_recommend_returns_202()` (POST with requirement_ids → 202 + operation_id); `test_recommend_status_returns_200()` (GET status → 200 with status field); `test_accept_blank_confirmation_id_returns_422()` (POST accept with blank confirmation → 422)
- [X] T033 Run `pytest tests/ --ignore=tests/integration -q --no-cov` — all 350+ tests pass; fix any regressions
- [X] T034 [P] Write `tests/unit/test_recommend_performance.py` to satisfy SC-001 (E1 fix): `test_sc001_recommend_submit_returns_within_2s()` — POST to `/api/v1/designs/D-001/recommend` with mocked DesignStore; wrap in `time.perf_counter()`; assert elapsed ≤ 2.0 seconds (the POST is async/non-blocking — BackgroundTask starts and returns immediately, so 2s is very generous; SC-001's 60s is the pipeline total, not the HTTP response time)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — T001 (bug fix) is the most critical; must be first
- **Foundational (Phase 2)**: Depends on T002 (router file exists); T006 builds on it
- **US1 (Phase 3)**: Depends on T006 (`_map_option_to_response` exists); 🎯 MVP
- **US2 (Phase 4)**: Depends on US1 (operation store + orchestrator must be wired)
- **US3 (Phase 5)**: Depends on US1 (RecommendationPage must exist for RequirementSelector to plug into)
- **Polish (Phase 6)**: Depends on all user stories complete

### Parallel Opportunities

- T003, T005 (Setup): parallel — different files
- T007, T008, T009 (US1 tests): parallel — independent test functions
- T012, T013 (US1 hooks): sequential — same file
- T016, T017, T018, T019 (US2 tests): parallel
- T021 (US2 hook): parallel with T022, T023 (different files)
- T028, T029 (nav updates): parallel — different files
- T030, T031, T032, T034 (Polish checks + timing test): parallel — independent tools

---

## Implementation Strategy

### MVP First (US1 + US2)

1. T001–T006 → Bug fix + foundation
2. T007–T015 → Pipeline + view (US1)
3. T016–T024 → Accept flow (US2)
4. **VALIDATE**: Request recommendations → see options → accept → navigate to canvas → see elements

### Incremental Delivery

1. Setup + Foundational → router skeleton, models, bug fix
2. US1 → See recommendations (MVP — validates the full LLM pipeline end-to-end)
3. US2 → Accept flow (core value — materialises architecture)
4. US3 → Requirement selection (enhancement)
5. Polish → Three-view nav, tests, lint

---

## Notes

- [P] tasks = different files, no file conflicts
- **T001 is non-negotiable** — without the audit ID fix, ANY accept call on a design with existing audit entries will 500 with UniqueViolationError
- `_make_recommend_orchestrator()` must handle `KnowledgeRetrieval` stub gracefully — with an empty KB, all options will have `advisory=True`; this is correct and expected behaviour
- The `AcceptOptionRequest.confirmation_id` must use the same non-empty string validation as `ExportRequest` (ADP-SPEC-011) — a Pydantic `@field_validator` that raises on blank strings
- Navigation (I1 fix): ALL THREE pages (`IntakePage`, `Workspace`, `RecommendationPage`) receive a single `onNavigate: (view: "canvas" | "intake" | "recommend") => void` prop from `App.tsx`. T027 MUST be implemented first because T028, T029, and T024 all depend on this interface. The existing `onBack`/`onNavigateToIntake` props are REPLACED.
- After accept: `useAcceptOption.onSuccess` invalidates `["design", designId]` so the canvas reloads with the new elements when navigated there
