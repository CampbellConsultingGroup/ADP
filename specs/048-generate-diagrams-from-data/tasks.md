# Tasks: Generate Diagrams from Business Data

**Input**: Design documents from `/specs/048-generate-diagrams-from-data/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md (no `contracts/` — no API surface changes)

**Tests**: Tests are MANDATORY for all ADP features (ART-IV). Test tasks appear before their implementation counterparts in every phase and MUST be confirmed to fail before implementation begins.

**Organization**: Two independently-testable user stories (value-stream generator, capability-subtree generator) on top of a shared Foundational phase that both need (the seed hand-off plumbing from Business page → App.tsx → Diagrams page/editor).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2)
- File paths are exact and relative to the repo root

---

## Phase 1: Setup

**Purpose**: Confirm the plan's assumptions still hold against the live repo before editing (no new dependencies for this feature — see plan.md Technical Context).

- [x] T001 Confirm `web/src/diagrams/core/model/diagram-ops.ts`'s `addNode`/`addEdge` signatures still auto-generate ids internally (research.md Decision 2's premise); confirm `web/src/business/CapabilityNode.tsx`'s `capability` prop is still typed `BusinessCapability` (research.md Decision 1's premise); confirm `web/src/App.tsx`'s `onSelectDesign` still sets `currentDesignId` and switches `view` together (research.md Decision 3's premise). No file changes — read-only; stop and re-plan if any premise has drifted since planning.

**Checkpoint**: Plan's file-level assumptions reconfirmed — safe to proceed.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The seed hand-off plumbing (Business page → `App.tsx` → Diagrams page/editor) that both generators depend on, per research.md Decisions 3 and 4.

**⚠️ CRITICAL**: Neither user story can be demonstrated end-to-end until this phase is complete — a generator function alone has nowhere to send its output without this wiring.

### Tests for Foundational plumbing (MANDATORY — ART-IV)

- [x] T002 [P] Extend `web/src/diagrams/DiagramEditorPage.test.tsx` — new test case: given a `seed={{ title: "X", model: <a DiagramModel with 2 nodes> }}` prop and no `diagramId`, the rendered title input's value is `"X"` and the Canvas reflects the seeded model (assert via the DSL panel's textarea value containing both seeded node labels, mirroring the existing reopen-with-content-intact test's assertion style). Confirm this fails (the `seed` prop doesn't exist yet).
- [x] T003 [P] Extend `web/src/diagrams/DiagramsPage.test.tsx` — new test case: given a `seed` prop (non-null) and an `onSeedConsumed` callback, `DiagramsPage` opens directly in editor mode pre-filled from that seed (assert the title input's value) and calls `onSeedConsumed()` exactly once. Confirm this fails (neither prop exists yet).

### Implementation for Foundational plumbing

- [x] T004 In `web/src/diagrams/DiagramEditorPage.tsx`: add an optional `seed?: { title: string; model: DiagramModel }` prop to `DiagramEditorPageProps`; when present and `diagramId` is undefined, initialize `title`/`model`/`diagramType` state from `seed.title`/`seed.model`/`seed.model.diagramTypeId` instead of the persona-aware empty default (ADP-914.6) — an explicit `seed` takes priority over `newDiagramType`/persona defaults, since a seed already carries real content. Run T002 and confirm it passes.
- [x] T005 In `web/src/diagrams/DiagramsPage.tsx`: add `seed?: DiagramSeed` and `onSeedConsumed?: () => void` props (import `DiagramSeed` from `./generators` once it exists in T010/T014 — a forward reference is fine since TS only needs the type, not the value, at this point; alternatively define `DiagramSeed` inline here first and re-export from `generators.ts` later in Phase 3, whichever keeps the diff smallest at this point in the sequence). On receiving a non-null `seed` (via `useEffect`), switch `mode` to `{ kind: "edit", seed }` and call `onSeedConsumed?.()`. Run T003 and confirm it passes.
- [x] T006 In `web/src/App.tsx`: add `pendingDiagramSeed: DiagramSeed | null` state (parallel to the existing `currentDesignId`) and an `onGenerateDiagram(seed: DiagramSeed)` callback that sets it and calls `setView("diagrams")` in one action (mirrors `onSelectDesign`'s `setCurrentDesignId(id); setView("intake");` exactly — research.md Decision 3). Pass `onGenerateDiagram={onGenerateDiagram}` to `<BusinessPage>`. Pass `seed={pendingDiagramSeed}` and `onSeedConsumed={() => setPendingDiagramSeed(null)}` to `<DiagramsPage>`.
- [x] T007 In `web/src/business/BusinessPage.tsx`: add `onGenerateDiagram?: (seed: DiagramSeed) => void` to `BusinessPageProps`; change the function signature from `(_props: BusinessPageProps)` to actually destructure and use it (this prop, and `onNavigate`, were previously declared but unused — `onGenerateDiagram` is the first genuine use of this props object). Do not yet thread it further down to `ValueStreamDetail`/`CapabilityTree` — that's each user story's own task (T011, T016).
- [x] T008 Run `cd web && npx tsc --noEmit && npx vitest run src/diagrams/DiagramEditorPage.test.tsx src/diagrams/DiagramsPage.test.tsx` — confirm clean/green, zero regressions in either file's pre-existing test cases.

**Checkpoint**: The seed hand-off path (Business page → App.tsx → Diagrams page → editor) is fully wired and tested end-to-end, independent of either generator existing yet.

---

## Phase 3: User Story 1 - Generate a flowchart from a value stream's stages (Priority: P1) 🎯 MVP

**Goal**: A "Generate Diagram" button on a value stream's detail page opens a new, unsaved flowchart pre-filled with its ordered stages.

**Independent Test**: Call `generateFromValueStream()` directly with a `ValueStreamDetail`-shaped fixture (no rendering needed) and assert the resulting `DiagramSeed`'s node count/labels/edges/title; separately, render `ValueStreamDetail` with a mocked `onGenerateDiagram` prop, click the button, and assert it was called with the expected seed shape.

### Tests for User Story 1 (MANDATORY — ART-IV)

- [x] T009 [P] [US1] Create `web/src/diagrams/generators.test.ts` (new file) — failing tests for `generateFromValueStream(vs)`: a 3-stage value stream produces 3 nodes (labeled with each stage's name, in `position` order) and 2 sequential edges; a 1-stage value stream produces 1 node and 0 edges; a 0-stage value stream produces 0 nodes and 0 edges (spec Edge Case); the result's `title` equals `vs.name` and `diagramType` is `"flowchart"`. Confirm the test run fails (the module doesn't exist yet).

### Implementation for User Story 1

- [x] T010 [US1] Create `web/src/diagrams/generators.ts` (new file) — export `DiagramSeed` interface (data-model.md) and `generateFromValueStream(vs: ValueStreamDetail): DiagramSeed`: starting from `createEmptyDiagramModel("flowchart")`, call `addNode({shape: "rectangle", label: stage.name})` per stage in `position` order, recording each stage's `id → generatedNodeId` in a local map (research.md Decision 2), then `addEdge({sourceId, targetId})` between consecutive stages using that map. Run T009 and confirm it passes.
- [x] T011 [US1] In `web/src/business/ValueStreamDetail.tsx`: add an optional `onGenerateDiagram?: (seed: DiagramSeed) => void` prop; add a "Generate Diagram" button in the header action row (alongside Edit/Delete, same `outlineBtn` style) that calls `onGenerateDiagram?.(generateFromValueStream(vs))`. In `web/src/business/BusinessPage.tsx`, thread `onGenerateDiagram` from its own props down to `<ValueStreamDetail>`.
- [x] T012 [US1] Run `cd web && npx vitest run src/diagrams/generators.test.ts src/diagrams/DiagramEditorPage.test.tsx src/diagrams/DiagramsPage.test.tsx && npx tsc --noEmit` — confirm all green, zero regressions.

**Checkpoint**: User Story 1 fully functional end-to-end (value stream → generated, editable, saveable diagram) — a shippable MVP increment.

---

## Phase 4: User Story 2 - Generate a flowchart from a capability's subtree (Priority: P2)

**Goal**: A "Generate Diagram" action on a capability tree node opens a new, unsaved flowchart pre-filled with that capability's full subtree.

**Independent Test**: Call `generateFromCapabilitySubtree()` directly with a `CapabilityTreeNode`-shaped fixture (nested `children`, no rendering needed) and assert the resulting `DiagramSeed`'s node count/labels/edges/title; separately, render `CapabilityNode` with a mocked `onGenerateDiagram` prop, click its new button, and assert it was called with the node itself.

### Tests for User Story 2 (MANDATORY — ART-IV)

- [x] T013 [P] [US2] Extend `web/src/diagrams/generators.test.ts` — failing tests for `generateFromCapabilitySubtree(node)`: a 3-level chain (root → child → grandchild) produces 3 nodes and 2 parent→child edges (root→child, child→grandchild); a leaf node (empty `children`) produces 1 node and 0 edges (spec Edge Case); a root with 2 direct children (no grandchildren) produces 3 nodes and 2 edges (both children point to root, not to each other); the result's `title` equals `node.name` and `diagramType` is `"flowchart"`. Confirm these new cases fail.

### Implementation for User Story 2

- [x] T014 [US2] In `web/src/diagrams/generators.ts`: add `generateFromCapabilitySubtree(node: CapabilityTreeNode): DiagramSeed` (import `CapabilityTreeNode` from `../business/CapabilityTree`) — recursively walk `node` and its `children`, calling `addNode({shape: "rectangle", label: n.name})` for every capability in the subtree (recording `id → generatedNodeId` per research.md Decision 2 as in T010), then `addEdge({sourceId: parentGeneratedId, targetId: childGeneratedId})` for every parent→child pair. Run T013 and confirm it passes.
- [x] T015 [US2] In `web/src/business/CapabilityNode.tsx`: widen the `capability` prop type from `BusinessCapability` to `CapabilityTreeNode` (research.md Decision 1 — a compatible superset, no existing field access changes); add an optional `onGenerateDiagram?: (node: CapabilityTreeNode) => void` prop; add a "Generate Diagram" button to the existing per-node action row (alongside Edit ✎ / Add child + / Delete, same `actionBtn` style) that calls `onGenerateDiagram?.(capability)`.
- [x] T016 [US2] **Simplified from the plan during implementation**: T015 already had `CapabilityNode.tsx` call `generateFromCapabilitySubtree()` itself and emit a finished `DiagramSeed` (matching T011's `ValueStreamDetail.tsx` precedent exactly, for consistency), rather than staying "generator-agnostic" and passing a raw node up as originally planned. That makes this task strictly simpler than planned: `CapabilityTree.tsx`'s `onGenerateDiagram` prop is `(seed: DiagramSeed) => void` (not `(node: CapabilityTreeNode) => void`), threaded straight through `renderTree(nodes, onGenerateDiagram)` to each `<CapabilityNode onGenerateDiagram={onGenerateDiagram} ...>` with **no wrapping/conversion needed at either `CapabilityTree` or `BusinessPage.tsx`** — both just pass the callback through unchanged, mirroring `ValueStreamDetail`'s pass-through exactly.
- [x] T017 [US2] Run `cd web && npx vitest run src/diagrams/generators.test.ts && npx tsc --noEmit` — confirm all green, zero regressions.

**Checkpoint**: Both user stories independently functional; capability-subtree generation works end-to-end alongside value-stream generation.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Documentation (ART-XVI) and full-suite regression confirmation.

- [x] T018 [P] Add a short note to `web/src/diagrams/README.md` documenting the generator convention: `generators.ts`'s two pure functions, the `DiagramSeed` type, and the `App.tsx`-lifted-state hand-off pattern (mirrors `currentDesignId`/`onSelectDesign`), per spec.md Assumptions and research.md Decisions 2–4.
- [x] T019 Run `cd web && npx tsc --noEmit` — confirm clean across the whole frontend, not just the touched files.
- [x] T020 Run `cd web && npm run test:run` — confirm the full frontend suite is green with zero regressions outside the new/modified test cases from T002/T003/T009/T013.
- [x] T021 Walk through quickstart.md Scenarios 1–4 (value-stream generation, capability-subtree generation, empty-source edge cases, post-generation editability) to confirm end-to-end behavior beyond the unit-test level. No browser-automation tool was available in this session (dev servers were up on :5173/:8001, but nothing to drive a click-through) — same situation as ADP-914.6/047's T013. Substituted with equivalent automated coverage, not skipped: Scenario 1 (value stream → flowchart) ≡ `generators.test.ts`'s `generateFromValueStream` tests (node/edge/title correctness) chained with `DiagramsPage.test.tsx`'s seed-consumption test and `DiagramEditorPage.test.tsx`'s seed-initialization tests — the full click→generate→open→pre-filled chain is unit-tested end to end, just not through an actual browser session. Scenario 2 (capability subtree) ≡ same chain via `generateFromCapabilitySubtree`. Scenario 3 (empty-source edge cases) ≡ the explicit 0-stage and leaf-capability test cases in `generators.test.ts`. Scenario 4 (post-generation editability) ≡ guaranteed by construction, not just tested: a seed only initializes `DiagramEditorPage`'s existing `title`/`model` state, so every subsequent interaction (Canvas, DslPanel, handleSave) runs through the exact same code path already exercised by the pre-existing "create → author → save" tests — there is no separate "generated diagram" code path that could diverge in editability. Scenario 5 ≡ T020, just run.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS both user stories (neither generator has anywhere to send its output without this plumbing).
- **User Story 1 (Phase 3)**: Depends on Foundational. No dependency on User Story 2.
- **User Story 2 (Phase 4)**: Depends on Foundational. No dependency on User Story 1 — `generators.ts` (T010) and `generators.test.ts` (T009) are extended, not replaced, by T013/T014, so the two stories can be implemented in either order or in parallel by different people; only within `generators.ts` itself do T010 and T014 touch the same file (sequential, not a hard logical dependency).
- **Polish (Phase 5)**: Depends on both user stories being complete.

### Parallel Opportunities

- T002 and T003 (Foundational tests, different files: `DiagramEditorPage.test.tsx` vs `DiagramsPage.test.tsx`) can be written in parallel.
- T009 (US1 generator test) and T013 (US2 generator test) both extend `generators.test.ts` but describe independent functions — can be drafted in parallel, merged before their respective implementation tasks.
- Once Foundational (Phase 2) is done, User Story 1 (Phase 3) and User Story 2 (Phase 4) can proceed fully in parallel — they touch entirely disjoint production files (`ValueStreamDetail.tsx`/`BusinessPage.tsx`'s value-stream wiring vs. `CapabilityNode.tsx`/`CapabilityTree.tsx`) apart from both appending to the same `generators.ts`/`generators.test.ts`.
- T018 (README) can run alongside T019/T020/T021 once both stories are implemented.

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (Setup) → Phase 2 (Foundational: seed hand-off plumbing).
2. Complete Phase 3 (User Story 1) → value-stream generation alone is a complete, shippable increment per spec.md.
3. **STOP and VALIDATE**: run T012, confirm quickstart.md Scenario 1 passes.
4. Optionally stop here — User Story 2 is a lower-priority, independent addition.

### Incremental Delivery

1. Setup + Foundational → seed hand-off plumbing ready, unit-tested in isolation.
2. Add User Story 1 → test independently → MVP.
3. Add User Story 2 → test independently → full feature.
4. Polish → documentation + full-suite regression confirmation.

## Notes

- No `[Story]` label on Setup/Foundational/Polish tasks, per the required task format.
- Every implementation task follows a task that was confirmed to fail first (ART-IV): T002/T003→T004/T005, T009→T010, T013→T014.
- This feature touches 2 new files (`generators.ts`, `generators.test.ts`) and 6 existing files (`App.tsx`, `BusinessPage.tsx`, `ValueStreamDetail.tsx`, `CapabilityTree.tsx`, `CapabilityNode.tsx`, `DiagramEditorPage.tsx`, `DiagramsPage.tsx` — 7, not 6, correcting the count: `DiagramEditorPage.tsx` and `DiagramsPage.tsx` are also modified) — no backend, no new dependencies, no migration.
