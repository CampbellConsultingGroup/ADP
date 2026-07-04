# Tasks: Requirements Intake HTTP API and Web Screen

**Input**: Design documents from `/specs/014-requirements-intake-ui/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: Tests are MANDATORY for all ADP features (ART-IV). Python contract tests appear before their corresponding implementation tasks. TypeScript component tests appear in the Polish phase.

**Note**: Zero new dependencies. Python backend is a thin HTTP adapter over the existing `adp.intake.ExtractionOrchestrator`. TypeScript frontend uses existing TanStack Query + React. The key constitutional constraint is ART-VIII: **no auto-confirm** — every proposal requires a per-proposal explicit action.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no file conflicts)
- **[Story]**: US1–US4 mapping
- Include exact file paths in every description

---

## Phase 1: Setup

**Purpose**: Create file skeletons and directory structure

- [X] T001 Create `src/adp/api/routers/intake.py` with module docstring, imports, module-level `_intake_store: dict[str, Any] = {}`, and an empty `router = APIRouter(prefix="/api/v1/designs", tags=["intake"])`
- [X] T002 [P] Create `web/src/intake/` directory with empty index files: `web/src/intake/IntakePage.tsx`, `web/src/intake/IntakeTextForm.tsx`, `web/src/intake/StructuredForm.tsx`, `web/src/intake/ProposalCard.tsx`, `web/src/intake/ProposalsList.tsx`, `web/src/intake/RequirementsList.tsx` — each as a bare React component stub returning `<div>placeholder</div>`
- [X] T003 [P] Create `web/src/api/intake.ts` with all TypeScript interfaces from `data-model.md` and stub hook functions that throw `new Error("not implemented")` — `useSubmitIntake`, `useIntakeStatus`, `useConfirmProposal`, `useRejectProposal`, `useAddRequirement`, `useRequirements`

**Checkpoint**: `python3 -c "from adp.api.routers.intake import router; print('ok')"` succeeds; `cd web && npm run tsc` passes with stubs

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: All Pydantic API models and TypeScript interfaces — every user story depends on them

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 Add all Pydantic v2 models to `src/adp/api/routers/intake.py` (all `extra="forbid"`):
  - `IntakeSubmitRequest(mode: Literal["bulk_text","structured_form"], text: str, kind: RequirementKind | None = None)` with `@field_validator("text")` raising if `mode=="bulk_text"` and `len(text) < 20`; and `@model_validator` ensuring `kind` is required when `mode=="structured_form"`
  - `IntakeSubmitResponse(operation_id: str, design_id: str, mode: str, status: str)`
  - `ProposalResponse(proposal_id: str, draft_statement: str, kind: str, source_excerpt: str, confidence: float, verification_status: str, status: str, confirmed_statement: str | None = None)`
  - `IntakeStatusResponse(operation_id: str, design_id: str, status: str, proposals: list[ProposalResponse], result_summary: str | None = None, error_description: str | None = None)`
  - `ConfirmProposalRequest(edited_statement: str | None = None)`
  - `ConfirmProposalResponse(requirement_id: str, title: str, description: str, kind: str, proposal_id: str | None = None)` — `proposal_id` is `None` when the requirement was added via structured form (T030); non-null when confirmed from an extracted proposal (I1 fix: was `str`, caused runtime Pydantic error on direct-add path)
  - `DirectRequirementRequest(statement: str, kind: RequirementKind, description: str | None = None)` with `@field_validator("statement")` requiring `len >= 10`
  - `RequirementItem(id: str, title: str, description: str, kind: str, satisfies: list[str])`
  - `RequirementListResponse(design_id: str, requirements: list[RequirementItem], total: int)`
  - Import `RequirementKind` from `adp.intake.models`

- [X] T005 [P] Update `web/src/api/intake.ts` with all TypeScript interfaces from `data-model.md` (replacing the stubs): `IntakeMode`, `OperationStatus`, `ProposalStatus`, `RequirementKind`, `IntakeSubmitRequest`, `IntakeSubmitResponse`, `ProposalResponse`, `IntakeStatusResponse`, `ConfirmProposalRequest`, `ConfirmProposalResponse`, `DirectRequirementRequest`, `RequirementItem`, `RequirementListResponse` — all typed as in `data-model.md`

- [X] T006 Register `intake.router` in `src/adp/api/app.py`: add `from adp.api.routers import intake` and `app.include_router(intake.router)` alongside the existing routers

**Checkpoint**: `python3 -c "from adp.api.routers.intake import IntakeSubmitRequest, IntakeStatusResponse; print('models ok')"` succeeds; `adp-generate --check` exits 0

---

## Phase 3: User Story 1 — Submit Text and Receive Proposals (Priority: P1) 🎯 MVP

**Goal**: POST /intake starts extraction in background, returns operation_id; GET /intake/{op_id} returns status and proposals; web IntakeTextForm submits text and shows extraction status.

**Independent Test**: POST valid bulk_text to `/api/v1/designs/D-001/intake`; assert 202 with `operation_id`; GET status; assert 200 with `status` field.

### Tests for User Story 1 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T007 [P] [US1] Write failing `test_submit_intake_bulk_text_returns_202()` in `tests/contract/test_intake_api.py`: POST `{"mode": "bulk_text", "text": "The system must handle 10000 concurrent users without degradation."}` to `/api/v1/designs/D-001/intake` via TestClient; assert 202; assert response has `operation_id` (non-empty string) and `status == "pending"`
- [X] T008 [P] [US1] Write failing `test_get_intake_status_returns_200()` in `tests/contract/test_intake_api.py`: after a valid submit, GET `/api/v1/designs/D-001/intake/{operation_id}`; assert 200; assert response has `status` field in `("pending","running","completed","failed")`
- [X] T009 [P] [US1] Write failing `test_submit_short_text_returns_422()` in `tests/contract/test_intake_api.py`: POST `{"mode": "bulk_text", "text": "too short"}` (< 20 chars); assert 422; assert error mentions text length
- [X] T010 [P] [US1] Write failing `test_get_nonexistent_operation_returns_404()` in `tests/contract/test_intake_api.py`: GET `/api/v1/designs/D-001/intake/nonexistent-id`; assert 404

### Implementation for User Story 1

- [X] T011 [US1] Implement `POST /api/v1/designs/{design_id}/intake` in `src/adp/api/routers/intake.py`: (1) validate `IntakeSubmitRequest` (Pydantic handles 422); (2) call `await _get_design_or_raise_404(design_id)` to verify design exists (import from deps); (3) generate `operation_id = str(uuid.uuid4())`; (4) store initial entry in `_intake_store[operation_id] = {"status": "pending", "design_id": design_id, "proposals": {}, "created_at": datetime.now(timezone.utc), "correlation_id": get_trace_id()}`; (5) build `IntakeSubmission` (mode, text, submitted_by from X-Actor header, submitted_at, operation_id); (6) create `LLMClient` or stub if `ADP_LLM_ENDPOINT` env var is absent (stub returns empty response); (7) add background task `background_tasks.add_task(orchestrator.run, submission, _intake_store)`; (8) `del submission` is called inside orchestrator.run() — do NOT store the text further; (9) return 202 `IntakeSubmitResponse`; verify T007 passes
- [X] T012 [US1] Implement `GET /api/v1/designs/{design_id}/intake/{operation_id}` in `src/adp/api/routers/intake.py`: look up `_intake_store[operation_id]`; if missing return 404; map stored proposals to `list[ProposalResponse]` (convert `ExtractedProposal` dataclass fields); return `IntakeStatusResponse`; verify T008 and T010 pass
- [X] T013 [US1] Implement `useSubmitIntake(designId: string)` in `web/src/api/intake.ts`: `useMutation` that POSTs to `/api/v1/designs/${designId}/intake`; returns `IntakeSubmitResponse` (D1 fix: removed [P] — T013 and T014 both modify the same file and must run sequentially)
- [X] T014 [US1] Implement `useIntakeStatus(designId: string, operationId: string | null)` in `web/src/api/intake.ts`: `useQuery` that GETs `/api/v1/designs/${designId}/intake/${operationId}`; `enabled: !!operationId`; `refetchInterval: (data) => (!data?.data?.status || data.data.status === "completed" || data.data.status === "failed") ? false : 2000` (D1 fix: removed [P] — must run after T013)
- [X] T015 [US1] Implement `web/src/intake/IntakeTextForm.tsx`: textarea (placeholder "Paste requirements, user stories, or notes..."; `minLength={20}`); security notice: `<p className="text-amber-600">⚠ Source text is not stored after extraction</p>`; "Extract Requirements" button (disabled when `isPending` or status is `"running"`); on submit: call `submitIntake.mutate({ mode: "bulk_text", text })` and pass `operation_id` up via `onOperationCreated(op.operation_id)` callback prop
- [X] T016 [US1] Implement partial `web/src/intake/IntakePage.tsx`: tab switcher (Bulk Text | Form); tab state via `useState`; `operationId` state; renders `<IntakeTextForm onOperationCreated={setOperationId} />`; reads `useIntakeStatus(designId, operationId)` and renders: spinner + "Extracting..." when status running; error banner when failed; nothing extra when completed (proposals in US2); `<RequirementsList>` stub on right panel (US4 fills it)

**Checkpoint**: `pytest tests/contract/test_intake_api.py -v --no-cov` green for T007–T010; intake screen renders at `/designs/DESIGN-001/intake` with text area and Extract button

---

## Phase 4: User Story 2 — Review and Confirm Proposals (Priority: P1)

**Goal**: Confirm and reject endpoints write to/skip the canonical model; ProposalCard shows source excerpt and offers three actions; ART-VIII: zero auto-confirms.

**Independent Test**: After extraction, POST confirm → assert design has new requirement + audit entry; POST reject → assert no requirement added.

### Tests for User Story 2 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T017 [P] [US2] Write failing `test_confirm_proposal_creates_requirement()` in `tests/contract/test_intake_api.py`: seed `_intake_store` with a mock operation containing one pending `ExtractedProposal`; POST to confirm endpoint; assert 200 with `requirement_id`; verify `design.requirements` has the new entry via a subsequent GET /requirements call
- [X] T018 [P] [US2] Write failing `test_reject_proposal_returns_200_no_requirement()` in `tests/contract/test_intake_api.py`: same setup; POST reject; assert 200; verify `design.requirements` is unchanged
- [X] T019 [P] [US2] Write failing `test_confirm_already_confirmed_returns_409()`: confirm a proposal that's already `confirmed`; assert 409
- [X] T020 [P] [US2] Write failing `test_confirm_with_edited_statement()`: POST `{"edited_statement": "Edited requirement text here"}` to confirm; assert 200; assert `description` in response matches the edited text

### Implementation for User Story 2

- [X] T021 [US2] Implement `POST /api/v1/designs/{design_id}/intake/{operation_id}/proposals/{proposal_id}/confirm` in `src/adp/api/routers/intake.py`: get operation from `_intake_store` (404 if missing); get proposal from `op["proposals"]` (404 if missing); if proposal status is not `PENDING` return 409; call `await orchestrator.confirm_proposal(proposal_id, operation_id, actor, request.edited_statement, _intake_store, design_store, design_id)`; return `ConfirmProposalResponse`; `orchestrator` is created with `LLMClient` stub or real client; verify T017, T019, T020 pass
- [X] T022 [US2] Implement `POST /api/v1/designs/{design_id}/intake/{operation_id}/proposals/{proposal_id}/reject` in `src/adp/api/routers/intake.py`: same operation/proposal lookup; if not PENDING return 409; call `await orchestrator.reject_proposal(proposal_id, operation_id, actor, _intake_store, design_store, design_id)`; return `{"proposal_id": proposal_id, "status": "rejected"}`; verify T018 passes
- [X] T023 [P] [US2] Implement `useConfirmProposal(designId: string, operationId: string)` and `useRejectProposal(designId: string, operationId: string)` in `web/src/api/intake.ts`: `useMutation` calls; on success invalidate `useRequirements` queryKey
- [X] T024 [US2] Implement `web/src/intake/ProposalCard.tsx`: renders (a) kind badge with colour — functional=blue, non_functional=purple, constraint=orange, driver=green; (b) confidence bar `<progress value={confidence} max={1} aria-valuenow={confidence} aria-valuemax={1} />`; (c) statement text — static unless edit mode is active; (d) source excerpt in `<blockquote role="blockquote" className="bg-gray-100 ...">` — ALWAYS visible (SC-005); (e) three action buttons: "Confirm" → `confirmProposal.mutate({proposal_id, edited_statement: null})`; "Edit & Confirm" → set `editing=true`, show `<textarea>` pre-filled with draft, on confirm → `confirmProposal.mutate({proposal_id, edited_statement: editedText})`; "Reject" → `rejectProposal.mutate({proposal_id})`; (f) after action: card shows confirmed/rejected state (muted, no action buttons, checkmark/cross icon)
- [X] T025 [US2] Implement `web/src/intake/ProposalsList.tsx`: when `proposals.length === 0`: show "No requirements could be extracted — try the structured form"; otherwise render `<ProposalCard key={p.proposal_id} proposal={p} />` for each; on any confirm action, invalidate `useRequirements(designId)` to refresh the sidebar
- [X] T026 [US2] Update `web/src/intake/IntakePage.tsx` to render `<ProposalsList proposals={statusData?.proposals ?? []} />` below the text form when `status === "completed"`

**Checkpoint**: `pytest tests/contract/test_intake_api.py -v --no-cov` all passing for T017–T020; ProposalCard renders with source excerpt visible and three action buttons

---

## Phase 5: User Story 3 — Structured Form Direct Entry (Priority: P2)

**Goal**: POST /requirements writes a Requirement directly to the canonical model (no LLM, no proposal); StructuredForm web component handles the fast path.

**Independent Test**: POST `{"statement": "...", "kind": "functional"}` to `/requirements`; assert 201 with `requirement_id`; assert design has new requirement.

### Tests for User Story 3 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T027 [P] [US3] Write failing `test_add_requirement_direct_returns_201()` in `tests/contract/test_intake_api.py`: POST `{"statement": "The API must be stateless and handle 100 RPS", "kind": "non_functional"}` to `/api/v1/designs/D-001/requirements`; assert 201; assert `requirement_id` starts with "REQ-"; assert no `proposal_id` returned (null)
- [X] T028 [P] [US3] Write failing `test_add_requirement_missing_statement_returns_422()`: POST `{"kind": "functional"}` (no statement); assert 422
- [X] T029 [P] [US3] Write failing `test_add_requirement_short_statement_returns_422()`: POST `{"statement": "too short", "kind": "functional"}` (< 10 chars); assert 422

### Implementation for User Story 3

- [X] T030 [US3] Implement `POST /api/v1/designs/{design_id}/requirements` in `src/adp/api/routers/intake.py`: validate `DirectRequirementRequest`; await `design_store.get(design_id)`; generate `REQ-NNN` ID; create `Requirement(id=req_id, title=statement[:120], description=description or statement)`; create `AuditEntry` with `action="add-requirement"`, `origin="human"`; append both to design; `await design_store.save(design, actor=actor)`; return 201 with `ConfirmProposalResponse(requirement_id=req_id, ..., proposal_id=None)`; verify T027–T029 pass
- [X] T031 [P] [US3] Implement `useAddRequirement(designId: string)` in `web/src/api/intake.ts`: `useMutation` that POSTs to `/api/v1/designs/${designId}/requirements`; on success invalidate `useRequirements(designId)`
- [X] T032 [US3] Implement `web/src/intake/StructuredForm.tsx`: statement `<input>` (required, minLength=10); kind `<select>` with options functional/non_functional/constraint/driver; "Add Requirement" `<button>` (disabled while mutating); on submit → `addRequirement.mutate({statement, kind})`; on success: reset form, show success toast "Requirement REQ-NNN added"
- [X] T033 [US3] Update `web/src/intake/IntakePage.tsx` to render `<StructuredForm designId={designId} />` in the "Form" tab

**Checkpoint**: `pytest tests/contract/test_intake_api.py::test_add_requirement_direct_returns_201 -v --no-cov` green; StructuredForm adds requirement via form without LLM

---

## Phase 6: User Story 4 — View Requirements List (Priority: P2)

**Goal**: GET /requirements returns all requirements; RequirementsList sidebar always shows confirmed requirements.

**Independent Test**: GET `/api/v1/designs/DESIGN-001/requirements`; assert 200 with `requirements` array and `total`.

### Tests for User Story 4 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T034 [P] [US4] Write failing `test_list_requirements_returns_200()` in `tests/contract/test_intake_api.py`: GET `/api/v1/designs/D-001/requirements`; assert 200; assert response has `requirements` (list), `total` (int), `design_id`
- [X] T035 [P] [US4] Write failing `test_list_requirements_empty_design_returns_empty()`: GET for a design with no requirements; assert 200; assert `requirements == []` and `total == 0`

### Implementation for User Story 4

- [X] T036 [US4] Implement `GET /api/v1/designs/{design_id}/requirements` in `src/adp/api/routers/intake.py`: `await design_store.get(design_id)` (404 if not found); map `design.requirements` → `list[RequirementItem]` (populate `satisfies` from `[e.id for e in design.elements if req.id in e.satisfies]`); return `RequirementListResponse(design_id, requirements, total=len(requirements))`; verify T034 and T035 pass
- [X] T037 [P] [US4] Implement `useRequirements(designId: string)` in `web/src/api/intake.ts`: `useQuery` that GETs `/api/v1/designs/${designId}/requirements`; `staleTime: 0` (always refetch after mutations)
- [X] T038 [US4] Implement `web/src/intake/RequirementsList.tsx`: renders `<RequirementListResponse>` from `useRequirements(designId)`; when empty: "No requirements yet — use the intake form above"; otherwise render each as `<div>`: id badge (REQ-001), kind badge (colour-coded matching ProposalCard), title text; satisfies list if non-empty as small grey text
- [X] T039 [US4] Update `web/src/intake/IntakePage.tsx` to render `<RequirementsList designId={designId} />` in the right panel sidebar (always visible, not tab-gated)

**Checkpoint**: `pytest tests/contract/test_intake_api.py -v --no-cov` all 9 tests green; RequirementsList sidebar updates after each confirm or direct add

---

## Phase 7: Navigation and Polish

**Purpose**: Wire screen into the app, add component tests, extend Playwright E2E, final checks

- [X] T040 Update `web/src/App.tsx` to support in-app view switching (C1 fix): add `const [view, setView] = useState<"canvas" | "intake">("canvas")`; pass `setView` to `<Workspace onNavigateToIntake={() => setView("intake")} />`; conditionally render `{view === "intake" ? <IntakePage designId={designId} onBack={() => setView("canvas")} /> : <Workspace ... />}`; the `IntakePage` receives an `onBack` prop that renders a "← Back to Canvas" button in its header; this keeps both views in the same React tree so TanStack Query cache and trace IDs persist across the switch
- [X] T041 [P] Add "Requirements" nav button to `web/src/canvas/Workspace.tsx` header: (C1 fix: do NOT use `window.location.href` — that causes a hard navigation that discards the TanStack Query cache and breaks the ADP-SPEC-012 trace_id correlation chain via the ContextVar / ART-VI) Instead: lift a `view: "canvas" | "intake"` state into `web/src/App.tsx` alongside `designId`; pass `setView` down to `Workspace` as a prop; the "Requirements" button calls `setView("intake")` → App renders `<IntakePage>` in-place without any navigation; the "Back to Canvas" button in `IntakePage` calls `setView("canvas")`; this preserves TanStack Query cache, trace IDs, and Zustand store state across the view switch
- [X] T042 [P] Write `web/tests/component/IntakePage.test.tsx` with: `test_intake_page_renders_text_form_tab()` (renders textarea and Extract button); `test_extract_button_disabled_when_text_too_short()` (< 20 chars disables button); `test_proposal_card_shows_source_excerpt()` (source excerpt always visible per SC-005); `test_reject_button_does_not_show_requirement()` (click reject, assert no requirement added to list) — mock `useSubmitIntake`, `useIntakeStatus`, `useConfirmProposal`, `useRejectProposal` hooks
- [X] T043 [P] Extend `web/tests/e2e/api.spec.ts` with intake API tests (no browser, just API): `test_intake_submit_returns_operation_id()` (POST to /intake, assert 202 + operation_id); `test_intake_list_requirements_returns_200()` (GET /requirements, assert 200 + total field); `test_intake_structured_form_adds_requirement()` (POST /requirements, assert 201)
- [X] T044 [P] Run `pytest tests/contract/test_intake_api.py tests/unit/ --ignore=tests/integration -q --no-cov` — all tests pass; fix any regressions in the 335 existing tests
- [X] T045 [P] Run `ruff check src/adp/api/routers/intake.py` — fix all lint issues
- [X] T046 [P] Run `adp-generate --check` — confirm zero schema drift
- [X] T047 Run `cd web && npm run tsc` — zero TypeScript errors in all new intake files
- [X] T048 [P] Write `tests/unit/test_intake_performance.py` to satisfy SC-001 and SC-006 (E1 fix): (a) `test_sc001_submit_returns_operation_id_within_2s()` — POST to `/api/v1/designs/D-001/intake` via TestClient; wrap in `time.perf_counter()`; assert elapsed ≤ 2.0 seconds (the endpoint returns immediately because extraction is a background task, so 2s is very generous); (b) `test_sc006_direct_add_requirement_within_2s()` — POST to `/api/v1/designs/D-001/requirements` via TestClient with a mocked async DesignStore; assert elapsed ≤ 2.0 seconds; run with `pytest tests/unit/test_intake_performance.py -v --no-cov`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories; models must exist for all endpoints
- **US1 (Phase 3)**: Depends on Foundational — 🎯 MVP; establishes the submit→poll pipeline
- **US2 (Phase 4)**: Depends on US1 (proposals must exist to confirm/reject); operation store + proposals list must be working
- **US3 (Phase 5)**: Depends on Foundational only — independently testable; no dependency on US1/US2
- **US4 (Phase 6)**: Depends on Foundational only — independently testable; refreshed by US2 and US3 actions
- **Polish (Phase 7)**: Depends on all user stories complete

### User Story Dependencies

- **US1 (P1)**: Core pipeline — text → extraction → proposals available
- **US2 (P1)**: Depends on US1 (needs proposals in store); web depends on US1's `operationId` state
- **US3 (P2)**: Independent — structured form needs no extraction
- **US4 (P2)**: Independent — requirements list reads from design store

### Parallel Opportunities

- T002, T003 (Setup): parallel — different directories
- T005 (TypeScript interfaces): parallel with T004 (Pydantic models) — different files
- T007, T008, T009, T010 (US1 tests): parallel — independent test functions
- T013 → T014 (US1 hooks): sequential — same file (`web/src/api/intake.ts`); D1 fix: [P] removed
- T017, T018, T019, T020 (US2 tests): parallel
- T023 (US2 hooks): parallel with T024, T025 (different files)
- T027, T028, T029 (US3 tests): parallel
- T031, T032 (US3 hook + form): parallel — different files
- T034, T035 (US4 tests): parallel
- T037, T038 (US4 hook + list): parallel — different files
- T041, T042, T043, T044, T045, T046, T047 (Polish): parallel — independent tools/files

---

## Implementation Strategy

### MVP First (US1 + US2)

1. Phase 1 + 2 → File skeletons, models, register router
2. Phase 3 (US1) → Submit text, get operation_id, poll status, show proposals
3. Phase 4 (US2) → Confirm/reject each proposal
4. **STOP and VALIDATE**: open `/designs/DESIGN-001/intake`, paste text, extract, confirm proposals → requirements appear

### Incremental Delivery

1. Setup + Foundational → API models and file skeletons
2. US1 → Text submission + extraction status + text form (MVP)
3. US2 → Proposals review panel (completes the ART-VIII human-in-loop flow)
4. US3 → Structured form (fast path for known requirements)
5. US4 → Requirements sidebar (always-visible summary)
6. Polish → Nav link, component tests, E2E extension, lint

---

## Notes

- [P] tasks = different files, no file conflicts between them
- Tests MUST fail before implementation (ART-IV); commit failing tests first
- `ExtractionOrchestrator` constructor requires `LLMClient` — stub when `ADP_LLM_ENDPOINT` not set (return empty proposals, no error)
- `DesignStore.get()` is async — use `await` everywhere (learned from ADP-SPEC-014 analysis of prior async/sync bugs)
- ART-VIII: the confirm endpoint is per-proposal only; there is NO `/confirm-all` endpoint; SC-004 test in T042 verifies this
- SC-005: source excerpt MUST be visible in `ProposalCard` at all times — not hidden behind a toggle
- Source text must be deleted after extraction per ADP-SPEC-006 policy: `ExtractionOrchestrator.run()` already calls `del submission` at the end — do NOT store `submission.text` anywhere in the router
- `ConfirmProposalResponse.proposal_id` is `str | None = None` (I1 fix): null for direct-add (T030), non-null for proposal confirmation (T021)
- Navigation between canvas and intake uses in-app `view` state in `App.tsx`, NOT `window.location.href` (C1 fix / ART-VI): hard navigation breaks the ADP-SPEC-012 ContextVar trace ID and discards the TanStack Query cache
- T040 and T041 must coordinate: `App.tsx` manages `view` state; `Workspace` receives `onNavigateToIntake` prop; `IntakePage` receives `onBack` prop
