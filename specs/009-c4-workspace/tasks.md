# Tasks: C4 Visual Design Workspace

**Input**: Design documents from `/specs/009-c4-workspace/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: Tests are MANDATORY for all ADP features (ART-IV). This is a TypeScript/React project — unit/component tests use Vitest + React Testing Library; E2E tests use Playwright. Tests MUST appear before their implementation counterparts in every user-story phase.

**Note**: This is a web application (`web/` directory, TypeScript/React). File paths are relative to the `web/` directory unless otherwise noted. Python changes are in `src/adp/`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no file conflicts)
- **[Story]**: Which user story this task belongs to (US1–US4)
- Include exact file paths in every description

---

## Phase 1: Setup (Web Project Initialization)

**Purpose**: Initialize the `web/` TypeScript/React project with Vite, install all dependencies, establish build and test toolchains

- [X] T001 Create `web/package.json` with dependencies: `react@18`, `react-dom@18`, `@xyflow/react@^12` (React Flow v12 — NOTE: use `@xyflow/react`, NOT `reactflow`; the former is v12 with the updated API; mixing these will cause import failures), `@tanstack/react-query@^5`, `zustand@^4`; devDependencies: `vite@^5`, `typescript@^5`, `@vitejs/plugin-react`, `vitest`, `@vitest/ui`, `@testing-library/react`, `@testing-library/user-event`, `jsdom`, `playwright@^1.4`, `tsd@^0.31`
- [X] T002 [P] Create `web/tsconfig.json` with strict TypeScript config: `"strict": true`, `"jsx": "react-jsx"`, path alias `"@/*": ["src/*"]`; create `web/vite.config.ts` configuring React plugin, Vitest test environment (`jsdom`), and path aliases
- [X] T003 [P] Create `web/index.html` with root div and script tag; create `web/src/main.tsx` rendering `<App />` with `QueryClientProvider` and `ReactFlowProvider` wrappers; create `web/src/App.tsx` as the routing entry point
- [X] T004 Create `web/src/` directory structure: `api/`, `canvas/`, `canvas/nodes/`, `canvas/edges/`, `inspection/`, `theme/`, `store/`; create empty index files so TypeScript can resolve imports
- [X] T005 Add the new layout endpoints to ADP-SPEC-003 by creating `src/adp/api/routers/layouts.py`: FastAPI router with `GET /api/v1/designs/{design_id}/layout/{level}` and `PUT /api/v1/designs/{design_id}/layout/{level}`; in-process dict storage per contracts/layout-api-contract.md; register router in `src/adp/api/app.py`; require `architect` role for PUT
- [X] T005b Create theme stub endpoint in `src/adp/api/routers/theme.py`: FastAPI router with `GET /api/v1/theme/c4` returning the baseline theme JSON from `contracts/theme-contract.md` as a static response (no database needed); register router in `src/adp/api/app.py`; this is a development/test shim until ADP-SPEC-010 is implemented; mark with a `# TODO(ADP-SPEC-010): replace stub with real theme store` comment
- [X] T006 Verify: `cd web && npm install && npm run build` succeeds with zero TypeScript errors; verify `npm test` runs the (currently empty) test suite without error

**Checkpoint**: `cd web && npm run dev` starts Vite dev server; `cd web && npm test` passes; `python3 -c "from adp.api.routers import layouts; print('ok')"` succeeds

---

## Phase 2: Foundational (Shared Infrastructure)

**Purpose**: API client, auth, state management, theme — MUST be complete before any user story

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T007 Create `web/src/api/client.ts`: typed `fetch` wrapper that reads bearer token from `localStorage["adp_token"]`; SECURITY NOTE: localStorage-based token storage is vulnerable to XSS attacks — add a `// v1 security debt: migrate to httpOnly cookies before production (ADP-SPEC-004)` comment at the top of the file; exports `apiGet<T>(path) -> Promise<T>` and `apiMutation<T, B>(method, path, body) -> Promise<T>`; throws typed `ApiError` on non-2xx including status code
- [X] T008 [P] Create `web/src/api/designs.ts`: TanStack Query hooks — `useDesign(designId)` fetching `GET /api/v1/designs/{id}`; `useLayout(designId, level)` fetching `GET /api/v1/designs/{id}/layout/{level}`; `useSaveLayout()` mutation for `PUT /api/v1/designs/{id}/layout/{level}`; `usePlaceElement()` mutation stub; `useDrawRelationship()` mutation stub — all with the optimistic update pattern from contracts/api-client-contract.md
- [X] T009 [P] Create `web/src/api/theme.ts`: `useC4Theme()` hook fetching `GET /api/v1/theme/c4`; cached 1 hour (`staleTime: 3600000`); returns `C4Theme` typed object per contracts/theme-contract.md
- [X] T010 Create `web/src/store/workspace-store.ts`: Zustand store with `activeLevel: C4Level` (default `"container"`), `selectedElementId: string | null` (default `null`), `inspectionPanelOpen: boolean` (default `false`), `designId: string`; actions: `setActiveLevel`, `selectElement`, `clearSelection`, `togglePanel`
- [X] T011 [P] Create `web/src/theme/c4-theme.ts`: `getElementStyle(kind: ElementKind, theme: C4Theme) -> C4ElementStyle`; the ONLY function that converts element kind → visual style; validates theme is not null; exports `C4ElementStyle` interface

**Checkpoint**: `cd web && npm test -- --run unit` passes all unit tests (initially empty); imports resolve correctly

---

## Phase 3: User Story 1 — Build a Design on the C4 Canvas (Priority: P1) 🎯 MVP

**Goal**: Architect can place elements and draw relationships on the canvas; each action sends a typed mutation to the API and the canvas reflects the result; invalid mutations roll back visually.

**Independent Test**: Mount `<C4Canvas>` with a mock API that records mutations; simulate placing an element; assert the mock received a `POST /api/v1/designs/{id}` with correct `kind` and `name`; simulate drawing a relationship; assert a second mutation was sent with correct `source` and `target`.

### Tests for User Story 1 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T012 [P] [US1] Write failing `test_place_element_sends_api_mutation()` in `web/tests/component/C4Canvas.test.tsx`: mock `usePlaceElement` to capture calls; simulate clicking "Add Element" → selecting "Container" → typing "API Gateway" → confirming; assert mutation was called with `{kind: "container", name: "API Gateway"}`
- [X] T013 [P] [US1] Write failing `test_draw_relationship_sends_api_mutation()` in `web/tests/component/C4Canvas.test.tsx`: mount canvas with 2 existing elements; simulate connecting them by triggering the React Flow `onConnect` callback; assert `useDrawRelationship` mutation was called with correct `source` and `target` element ids
- [X] T014 [P] [US1] Write failing `test_invalid_mutation_rolls_back()` in `web/tests/component/C4Canvas.test.tsx`: mock `usePlaceElement` to reject with status 422; simulate placing element; assert the optimistic element is NOT present in the canvas after the error

### Implementation for User Story 1

- [X] T015 [US1] Implement `usePlaceElement()` fully in `web/src/api/designs.ts`: mutation `PUT /api/v1/designs/{id}` with the updated `ArchitectureDescription` (new element appended to the `elements` list — NO position field; positions are NOT part of the canonical model API); immediately after a successful element mutation, call `useSaveLayout()` to record the drop position via `PUT /api/v1/designs/{id}/layout/{level}`; remove `position` from `PlaceElementInput` type; optimistic update adds the element to the cached design; on 409 calls `notifyConflict()`; on any error reverts to cached snapshot
- [X] T016 [US1] Implement `useDrawRelationship()` fully in `web/src/api/designs.ts`: mutation `PUT /api/v1/designs/{id}` extending the relationships list; same optimistic update pattern; on error reverts
- [X] T017 [US1] Create `web/src/canvas/nodes/C4ElementNode.tsx`: custom React Flow node component that renders a C4 element using ONLY `data.style` (from theme) — no `style` props accepted from outside; displays element name and kind label; selection state changes border width; exports `C4NodeTypes` for React Flow registration
- [X] T018 [US1] Create `web/src/canvas/edges/C4RelationshipEdge.tsx`: custom React Flow edge; renders with theme relationship style (stroke, width, arrow); displays relationship label if present; exports `C4EdgeTypes`
- [X] T019 [US1] Create `web/src/canvas/C4Canvas.tsx`: React Flow canvas component; converts `ArchitectureDescription.elements` → React Flow nodes using current filter + positions from layout; converts `relationships` → React Flow edges; handles `onNodeDragStop` (saves position update); handles `onConnect` (calls `useDrawRelationship`); provides "Add Element" UI that calls `usePlaceElement`
- [X] T020 [US1] Create `web/src/canvas/Workspace.tsx`: top-level workspace component; wraps `<C4Canvas>`, `<InspectionPanel>`, and level toggle; reads `designId` from route params; fetches design + layout + theme; passes them to canvas; verify T012–T014 all pass

**Checkpoint**: `cd web && npm test -- --run component` green; developer can open the workspace, place elements, and draw relationships with optimistic updates

---

## Phase 4: User Story 2 — Multi-Level C4 Projection (Priority: P1)

**Goal**: Switching the C4 level toggle re-derives the canvas view from the same canonical model — no separate diagram source; elements at the wrong level are hidden, not deleted.

**Independent Test**: Call `filterElementsForLevel` with a mixed-kind array and each of the three levels; assert only the correct element kinds are returned for each level.

### Tests for User Story 2 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T021 [P] [US2] Write failing `test_c4_filter_context_level()`, `test_c4_filter_container_level()`, `test_c4_filter_component_level()` in `web/tests/unit/c4-filter.test.ts`: create arrays of elements with all four kinds; assert `filterElementsForLevel(elements, "context")` returns only person + system elements; assert container returns system + container; assert component returns container + component
- [X] T022 [P] [US2] Write failing `test_relationship_filter_hides_cross_level_edges()` in `web/tests/unit/c4-filter.test.ts`: create a relationship where source is person and target is container; at context level, this relationship should be hidden (both endpoints must be visible at the active level)
- [X] T023 [P] [US2] Write failing `test_level_switch_does_not_create_new_diagram()` in `web/tests/component/C4Canvas.test.tsx`: switch level from container to context; assert the `useDesign` hook was NOT called again (same model used); assert the canvas nodes change but no additional API calls were made

### Implementation for User Story 2

- [X] T024 [US2] Create `web/src/canvas/c4-filter.ts`: `filterElementsForLevel(elements: Element[], level: C4Level): Element[]`; `filterRelationshipsForLevel(relationships: Relationship[], visibleElementIds: Set<string>): Relationship[]`; `C4_LEVEL_KINDS` constant map per data-model.md; verify T021–T022 pass
- [X] T025 [US2] Add level toggle UI to `web/src/canvas/Workspace.tsx`: three-tab toggle `[Context] [Container] [Component]`; clicking updates `workspaceStore.setActiveLevel()`; C4Canvas reads `activeLevel` from store and passes it to `filterElementsForLevel`; verify T023 passes
- [X] T026 [US2] Ensure layout positions persist per level: when `activeLevel` changes, `useLayout(designId, newLevel)` is called; layout is saved on node drag stop with the current active level in the PUT request body

**Checkpoint**: Level toggle works; switching between context/container/component shows different subsets of elements from the SAME model; no extra API calls on level switch

---

## Phase 5: User Story 3 — Element Traceability Inspection (Priority: P2)

**Goal**: Clicking an element slides open the inspection panel showing satisfied requirements (ids + titles) and element provenance (manual or AI recommendation).

**Independent Test**: Mount `<InspectionPanel>` with a mock element that has `satisfies=["REQ-001"]` and `provenance="opt-007"`; assert the panel renders "REQ-001" (and its title from the design's requirements list) and shows "Accepted from recommendation OPT-007".

### Tests for User Story 3 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T027 [P] [US3] Write failing `test_inspection_panel_shows_satisfies()` in `web/tests/component/InspectionPanel.test.tsx`: render panel with element having `satisfies=["REQ-001"]` and a design containing `Requirement(id="REQ-001", title="Stateless handling")`; assert the text "Stateless handling" appears in the panel
- [X] T028 [P] [US3] Write failing `test_inspection_panel_shows_provenance()` in `web/tests/component/InspectionPanel.test.tsx`: render panel with `provenance="opt-001"`; assert text containing "recommendation" and "OPT-001" appears
- [X] T029 [P] [US3] Write failing `test_inspection_panel_shows_no_requirements_message()` in `web/tests/component/InspectionPanel.test.tsx`: render with empty `satisfies=[]`; assert a message like "No requirements satisfied" appears (not an error or empty screen)
- [X] T030 [P] [US3] Write failing `test_clicking_element_opens_panel()` in `web/tests/component/C4Canvas.test.tsx`: mount canvas; simulate clicking on a node; assert `workspaceStore.inspectionPanelOpen` becomes `true` and `selectedElementId` is set

### Implementation for User Story 3

- [X] T031 [US3] Create `web/src/inspection/InspectionPanel.tsx`: receives `elementId` and `design`; renders selected element name and kind; maps `element.satisfies` ids to requirement objects from `design.requirements`; renders each requirement title; renders `element.provenance` as human-readable (null → "Manually placed"; option id → "Accepted from recommendation {id}"); verify T027–T029 pass
- [X] T032 [US3] Wire inspection panel into `web/src/canvas/Workspace.tsx`: React Flow's `onNodeClick` calls `workspaceStore.selectElement(node.id)` and `workspaceStore.togglePanel(true)`; `InspectionPanel` renders to the right of the canvas when `inspectionPanelOpen=true`; clicking canvas background calls `workspaceStore.clearSelection()`; verify T030 passes

**Checkpoint**: `cd web && npm test -- --run component` green; clicking any element shows its satisfied requirements and provenance within 1 second

---

## Phase 6: User Story 4 — Locked Theme Enforcement (Priority: P2)

**Goal**: All elements of the same kind have identical styling derived from the locked theme; zero styling controls exposed in the UI; theme update from ADP-SPEC-010 automatically reflects on all elements.

**Independent Test**: Call `getElementStyle("container", mockTheme)` and assert it returns exactly the fill/stroke/color from the theme; mount two Container-kind elements and assert their rendered colors are identical; inspect the `C4ElementNode` component's prop types and assert no color/style props exist.

### Tests for User Story 4 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T033 [P] [US4] Write failing `test_theme_style_by_kind()` in `web/tests/unit/c4-theme.test.ts`: call `getElementStyle("container", mockTheme)` with a known theme JSON; assert returned style has exactly `fill="#438DD5"`, `stroke="#3C7FC0"`, `color="#ffffff"`
- [X] T034 [P] [US4] Write failing `test_two_containers_have_identical_style()` in `web/tests/component/C4Canvas.test.tsx`: render canvas with two Container elements; assert both have the same background color in their rendered DOM; assert neither has any inline style that differs from the theme
- [X] T035 [P] [US4] Write failing `test_no_style_controls_in_element_node()` in `web/tests/unit/c4-element-node.test-d.tsx` (using `tsc --noEmit` with `@ts-expect-error` comments): assert that `<C4ElementNode data={...} color="red" />` fails to compile; verify TypeScript rejects `color`, `fill`, `stroke`, `backgroundColor`, `customStyle` props on `C4ElementNode`
- [X] T036 [P] [US4] Write failing `test_no_style_controls_in_workspace()` in `web/tests/component/C4Canvas.test.tsx`: mount `<Workspace>` and search for all form inputs, color pickers, and select elements within the properties panel; assert zero are found (QG-17 / ART-XII)

### Implementation for User Story 4

- [X] T037 [US4] Implement `getElementStyle()` fully in `web/src/theme/c4-theme.ts`; verify it handles missing theme gracefully (fallback to a default style rather than crashing); add TypeScript assertion that `C4ElementNode` props type has no style override fields; verify T033–T034 pass
- [X] T038 [US4] Audit `web/src/canvas/nodes/C4ElementNode.tsx` to confirm: (a) only `data.element` and `data.style` props accepted; (b) style applied ONLY from `data.style`; (c) no style override controls rendered; add a comment block marking the "NO OVERRIDE" zone; verify T035–T036 pass

**Checkpoint**: `cd web && npm test -- --run unit` green for theme tests; same-kind elements are visually identical; zero styling controls in the workspace UI

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: E2E tests, layout persistence, conflict notification, and backend integration

- [X] T039 [P] Write Playwright E2E test `web/tests/e2e/workspace.spec.ts`: first ensure `web/playwright.config.ts` exists with `baseURL: process.env.ADP_TEST_URL || 'http://localhost:8000'`; add a `beforeAll` fixture that creates a test design via `apiPost('/api/v1/designs', {schema_version: '1.0.0', id: 'E2E-001', title: 'E2E Test', created_at: ..., updated_at: ...})` and stores its id; then navigate to workspace for the test design; place a "container" element named "Test Gateway"; assert element appears on canvas; verify by calling `GET /api/v1/designs/{id}` and asserting the element is in the model (requires running ADP backend — mark `@slow`)
- [X] T040 [P] Implement layout auto-save in `web/src/canvas/C4Canvas.tsx`: debounce 500ms on React Flow `onNodeDragStop` and `onNodesChange`; call `useSaveLayout()` with current positions; show a subtle "Saving..." indicator during save
- [X] T041 [P] Implement conflict notification in `web/src/api/designs.ts`: when any mutation returns 409, call `notifyConflict()` which displays a toast/banner: "Design updated by another user. Your change was not saved." with a "Reload" button that calls `queryClient.invalidateQueries(['design', designId])`; the notification MUST also include a "Dismiss" button; auto-dismisses after 30 seconds if the architect takes no action (`setTimeout(dismiss, 30_000)`); implement as a `web/src/canvas/ConflictNotification.tsx` component
- [X] T042 [P] Run `cd web && npx tsc --noEmit` and ensure zero TypeScript errors; run `cd web && npm run lint` (add eslint config if missing); fix all issues
- [X] T043 [P] Run `cd web && npm test -- --run` with coverage; assert coverage ≥ 80% for `src/api/`, `src/canvas/`, `src/theme/`, `src/store/`; add targeted tests for uncovered branches (layout save debounce, theme fallback, error states)
- [X] T043b [P] Write timing assertion in `web/tests/component/C4Canvas.test.tsx`: use `vi.useFakeTimers()` and a mock API responding after 50ms delay; simulate element drag-and-drop; assert the optimistic element appears in the canvas DOM within 100ms (before the API responds); advance timers by 50ms; assert `isSuccess` on the mutation; total simulated time is < 200ms — verifies SC-003 / NFR-001 with mocked network timing
- [X] T044 Verify the new Python layout router integration: run `pytest src/` to ensure `layouts.py` has ≥ 85% coverage; run `adp-generate --check` to confirm ADP-SPEC-001 schema unchanged; run `ruff check src/adp/api/routers/layouts.py` and fix issues

- [X] T044b [P] Write `tests/api/test_layouts.py` for the new layout router: `GET /api/v1/designs/D-001/layout/container` returns `{"design_id": "D-001", "level": "container", "positions": {}}` for a new design; `PUT` with positions then `GET` returns those positions; assert 401 on unauthenticated requests; assert 403 on Viewer role; run with `pytest tests/api/test_layouts.py --no-cov` (no Docker needed — in-process store)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories; API client + state store must exist
- **US1 (Phase 3)**: Depends on Foundational — 🎯 MVP; canvas editing demonstrates the core model-backing
- **US2 (Phase 4)**: Depends on US1's `C4Canvas` component existing; level filter is independently testable
- **US3 (Phase 5)**: Depends on US1 (elements must exist to inspect); inspection panel is independently testable
- **US4 (Phase 6)**: Depends on Foundational (theme hook exists); theme tests are fully independent of US1–US3
- **Polish (Phase 7)**: Depends on all user stories complete

### User Story Dependencies

- **US1 (P1)**: Can start after Phase 2 — no dependencies on other stories
- **US2 (P1)**: Depends on US1's `C4Canvas` component; filter logic (T024) can be tested independently from Phase 2
- **US3 (P2)**: Depends on US1 (canvas exists); `InspectionPanel` component is independently testable from Phase 2
- **US4 (P2)**: Can start after Phase 2 (theme hook exists); fully independent of US1–US3

### Parallel Opportunities

- T002, T003, T004 (Setup): parallel — different files
- T008, T009, T010, T011 (Foundational): parallel — different files
- T012, T013, T014 (US1 tests): parallel — independent test functions
- T021, T022, T023 (US2 tests): parallel — independent test functions/files
- T027, T028, T029, T030 (US3 tests): parallel — independent test functions
- T033, T034, T035, T036 (US4 tests): parallel — independent test functions/files
- T039, T040, T041, T042, T043 (Polish): parallel — independent tools/concerns

---

## Implementation Strategy

### MVP First (US1 + US2)

1. Phase 1 + 2 → web project scaffolded, API client + state ready
2. Write US4 theme tests T033–T036 (pure unit tests, no canvas needed — can run from Phase 2)
3. Phase 3 (US1) → canvas editing with model backing
4. Phase 4 (US2) → level projection
5. **STOP and VALIDATE**: Open workspace in browser; place elements; switch levels; all operations produce model records

### Incremental Delivery

1. Phase 1 + 2 → Infrastructure ready
2. Phase 3 (US1) → Working canvas (MVP — ART-II compliance demonstrated)
3. Phase 4 (US2) → Multi-level projection
4. Phase 5 (US3) → Traceability surfacing (ART-XI)
5. Phase 6 (US4) → Theme enforcement audit (ART-XII / QG-17)
6. Phase 7 → E2E + layout persistence + Polish

---

## Notes

- [P] tasks = different files or independent test functions; no file conflict
- Tests MUST fail before implementation; commit failing tests first (ART-IV)
- TypeScript strict mode prevents style override props at compile time (enforces ART-XII)
- The `web/` project is a SEPARATE package from the Python monorepo; it has its own `npm` build chain
- The only Python change in this spec is `src/adp/api/routers/layouts.py` (new) and `src/adp/api/app.py` (register router)
- Constitution gates: QG-03, QG-16, QG-17
- `adp-generate --check` must remain exit 0 — no changes to ADP-SPEC-001 model
