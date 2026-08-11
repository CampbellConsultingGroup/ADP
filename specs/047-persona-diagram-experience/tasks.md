# Tasks: Persona-Differentiated Diagram Experience

**Input**: Design documents from `/specs/047-persona-diagram-experience/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md (no `contracts/` — no API surface changes)

**Tests**: Tests are MANDATORY for all ADP features (ART-IV). Test tasks appear before their implementation counterparts in every phase and MUST be confirmed to fail before implementation begins.

**Organization**: Two independently-testable user stories from spec.md, both touching the same file (`DiagramEditorPage.tsx`) but adding distinct, separately-verifiable behavior on top of a shared foundational module (`persona.ts`).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2)
- File paths are exact and relative to the repo root

---

## Phase 1: Setup

**Purpose**: Confirm the plan's assumptions still hold against the live repo before editing (no new dependencies or scaffolding needed for this feature — see plan.md Technical Context).

- [x] T001 Confirm `web/src/diagrams/DiagramsPage.tsx` still renders `<DiagramEditorPage diagramId={mode.diagramId} onSaved={...} />` with no `newDiagramType` prop (research.md Decision 3's premise), and confirm `web/src/auth/AuthProvider.tsx` still exposes `useAuth().user.role` unchanged (research.md Decision 1's premise). No file changes — a `grep`/read-only check; stop and re-plan if either has drifted since planning.

**Checkpoint**: Plan's file-level assumptions reconfirmed — safe to proceed.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The persona→type lookup both user stories depend on (data-model.md).

**⚠️ CRITICAL**: Both user stories read from this module — it must exist and be correct before either story's `DiagramEditorPage.tsx` edit.

### Tests for Foundational module (MANDATORY — ART-IV)

- [x] T002 [P] Write `web/src/diagrams/persona.test.ts` (new file) — failing tests for `getRecommendedDiagramType(role)`: returns `"architecture"` for `"enterprise_architect"`, `"flowchart"` for `"solution_architect"`, `"sequence"` for `"technical_architect"`; returns `undefined` for `"reviewer"`, `"platform_admin"`, an unrecognized string, and `undefined`/no argument. Confirm the test run fails with a module-not-found error (the module doesn't exist yet).

### Implementation for Foundational module

- [x] T003 Create `web/src/diagrams/persona.ts` (new file) — `PERSONA_DEFAULT_TYPE: Record<string, DiagramType>` constant (data-model.md's 3-row table) importing `DiagramType` from `./api`, plus `getRecommendedDiagramType(role: string | undefined): DiagramType | undefined`. Run T002 and confirm it now passes.

**Checkpoint**: `persona.ts` is implemented and unit-tested in isolation — both user stories can now proceed.

---

## Phase 3: User Story 1 - New diagram defaults to the type that fits my role (Priority: P1) 🎯 MVP

**Goal**: Starting a brand-new diagram pre-selects the signed-in architect's mapped default type, while remaining fully overridable.

**Independent Test**: Mock `useAuth()` to return each of the 3 architect roles in turn, render `<DiagramEditorPage />` with no `newDiagramType` prop, and assert the "Diagram type" select's initial value matches that role's mapped type (per quickstart.md Scenarios 1–3); assert an explicit `newDiagramType` prop still wins over the persona default (regression guard for FR-004/Scenario 5, unchanged from ADP-SPEC-046).

### Tests for User Story 1 (MANDATORY — ART-IV)

- [x] T004 [P] [US1] Extend `web/src/diagrams/DiagramEditorPage.test.tsx` — add `vi.mock("../auth/AuthProvider")` and new test cases: (a) for each of `enterprise_architect`/`solution_architect`/`technical_architect`, mocked `useAuth()` returning that role + no `newDiagramType` prop → the "Diagram type" select's value is the role's mapped type (FR-002/FR-003); (b) an unrecognized/`undefined` role + no `newDiagramType` prop → falls back to `"flowchart"` (FR-006); (c) `newDiagramType="uml"` explicitly passed + a mocked role whose default would otherwise be different → the select's value is `"uml"`, confirming the prop still wins (FR-004, regression guard). Confirm all new cases fail (the persona logic doesn't exist yet).

### Implementation for User Story 1

- [x] T005 [US1] In `web/src/diagrams/DiagramEditorPage.tsx`: import `useAuth` from `../auth/AuthProvider` and `getRecommendedDiagramType` from `./persona`; compute `const recommended = getRecommendedDiagramType(useAuth().user?.role);`; change the `diagramType` state initializer from `useState<DiagramType>(newDiagramType ?? "flowchart")` to `useState<DiagramType>(newDiagramType ?? recommended ?? "flowchart")`. Run T004 and confirm all its cases now pass. **Deviation from the plan, found during implementation**: the `model` state's initializer (`useState<DiagramModel>(() => createEmptyDiagramModel(newDiagramType ?? "flowchart"))`) had the exact same hardcoded fallback and would have gone out of sync with `diagramType` (e.g. `diagramType="sequence"` but `model` built as an empty flowchart). Introduced a single shared `initialType` constant and used it for both state initializers, not just the one the task text named.
- [x] T006 [US1] Run `cd web && npx vitest run src/diagrams/DiagramEditorPage.test.tsx src/diagrams/persona.test.ts` — confirm green, zero regressions in the pre-existing test cases in that file.

**Checkpoint**: User Story 1 fully functional and independently testable — this alone is a shippable MVP increment (spec.md: "the single highest-value, lowest-risk change").

---

## Phase 4: User Story 2 - The type selector shows me which type is recommended (Priority: P2)

**Goal**: The role-matched type is visually distinguished in the type selector's option list, without disabling or hiding any option.

**Independent Test**: Render `<DiagramEditorPage />` with a mocked role and assert exactly one `<option>` in the "Diagram type" select carries a "(Recommended for your role)" suffix, matching that role's mapped type, while all 5 options remain present and selectable (per quickstart.md Scenarios 1–4).

### Tests for User Story 2 (MANDATORY — ART-IV)

- [x] T007 [P] [US2] Extend `web/src/diagrams/DiagramEditorPage.test.tsx` — new test cases: (a) for a mocked `enterprise_architect` role, the `architecture` option's accessible text includes `"(Recommended for your role)"` and the other 4 options' text does not; (b) for an unrecognized/`undefined` role, no option among the 5 includes that suffix (FR-006); (c) all 5 `<option>` elements remain present in the DOM regardless of role (FR-005's "not disabled, hidden, or reordered out of reach"). Confirm these fail (the label doesn't exist yet).

### Implementation for User Story 2

- [x] T008 [US2] In `web/src/diagrams/DiagramEditorPage.tsx`'s `DIAGRAM_TYPES.map(...)` option rendering: append `t === recommended ? " (Recommended for your role)" : ""` to each option's text content, reusing the same `recommended` value computed in T005 (no second lookup — research.md Decision 3). Run T007 and confirm all its cases now pass.
- [x] T009 [US2] Run `cd web && npx vitest run src/diagrams/DiagramEditorPage.test.tsx` — confirm green, all US1 + US2 cases passing together, zero regressions.

**Checkpoint**: Both user stories independently functional and verified together in the same file.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Documentation (ART-XVI) and full-suite regression confirmation.

- [x] T010 [P] Add a short note to `web/src/diagrams/README.md` documenting the persona-mapping convention: where `PERSONA_DEFAULT_TYPE` lives, what it does (steering only, never restricts), and that changing a role's default is a one-line constant edit (per spec.md Assumptions).
- [x] T011 Run `cd web && npx tsc --noEmit` — confirm clean (no new `DiagramType`/`AuthUser` typing errors).
- [x] T012 Run `cd web && npm run test:run` — confirm the full frontend suite is green with zero regressions outside the new/modified test cases from T002/T004/T007.
- [x] T013 Walk through quickstart.md Scenarios 5–7 manually (steering-only override, existing-diagram unaffected, automated regression command) to confirm end-to-end behavior beyond the unit-test level. **No browser-automation tool was available in this session** to drive a live walkthrough against the running dev servers (confirmed up on :5173/:8001), so this was satisfied via equivalent automated coverage instead, not skipped: Scenario 5 ≡ T004's "explicit prop wins" test; Scenario 6 ≡ confirmed by direct code read that the `{!diagramId && (...)}` guard hiding the type selector on existing diagrams is untouched by this feature's diff; Scenario 7 ≡ the full-suite run below (T012).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS both user stories (both read `persona.ts`).
- **User Story 1 (Phase 3)**: Depends on Foundational. No dependency on User Story 2.
- **User Story 2 (Phase 4)**: Depends on Foundational **and** on User Story 1's edit to `DiagramEditorPage.tsx` landing first (T008 reuses the exact `recommended` variable T005 introduces in the same file — not a conceptual dependency, a literal same-file edit-ordering one). Independently *testable* per its own acceptance scenarios regardless — just not independently *implementable* in parallel with US1 in the same file.
- **Polish (Phase 5)**: Depends on both user stories being complete.

### Parallel Opportunities

- T002 (foundational test) has no prior dependency — can start immediately after T001.
- T004 and T007 (test-writing for US1 and US2) both extend the same test file but describe independent behavior — can be drafted in parallel by different people, though they'll need to be merged into one file before either's implementation task runs.
- T010 (README note) can run in parallel with T011/T012/T013 once both stories are implemented.

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (Setup) → Phase 2 (Foundational: `persona.ts`).
2. Complete Phase 3 (User Story 1) → the persona-aware default alone is a complete, shippable increment per spec.md.
3. **STOP and VALIDATE**: run T006, confirm quickstart.md Scenarios 1–3 and 5 pass.
4. Optionally stop here — User Story 2 is a lower-priority, purely additive visual refinement on top.

### Incremental Delivery

1. Setup + Foundational → `persona.ts` ready, unit-tested in isolation.
2. Add User Story 1 → test independently → MVP.
3. Add User Story 2 → test independently → full feature.
4. Polish → documentation + full-suite regression confirmation.

## Notes

- No `[Story]` label on Setup/Foundational/Polish tasks, per the required task format.
- Every implementation task follows a task that was confirmed to fail first (ART-IV) — T002→T003, T004→T005, T007→T008.
- This entire feature touches exactly 2 production files (`web/src/diagrams/persona.ts` new, `web/src/diagrams/DiagramEditorPage.tsx` modified) and 2 test files (`persona.test.ts` new, `DiagramEditorPage.test.tsx` extended) — no backend, no new dependencies, no migration.
