# Tasks: Multi-Select Capabilities → Generate Diagram

**Input**: Design documents from `/specs/920-capability-diagram-select/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md (no contracts/ — no API change)

**Tests**: Mandatory for all ADP features (ART-IV). Test tasks appear before their implementation
counterparts in every user-story phase and MUST be verified to fail before implementation begins.

**Organization**: Grouped by user story (spec.md) to enable independent implementation and testing of each.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 / US2, per spec.md's priorities (P1/P2)

## Path Conventions

Entirely frontend, no backend file touched, no migration (plan.md's Structure Decision):
- `web/src/diagrams/generators.ts` (extend), `generators.test.ts` (extend)
- `web/src/business/CapabilityNode.tsx` (extend), `CapabilityNode.test.tsx` (new — first render test for
  this component)
- `web/src/business/CapabilityTree.tsx` (extend), `CapabilityTree.test.tsx` (extend)

---

## Phase 1: Setup

- [X] T001 Run `cd web && npx vitest run` to confirm a clean, fully-green baseline before any change (no
  code changes in this task)

---

## Phase 2: Foundational

**Not applicable** — no backend change, no migration, no shared blocking infrastructure. The one real
sequencing note: **US2 builds directly on the `selectedIds` state US1 introduces** in `CapabilityTree.tsx`
(mirrors `043-capability-heat-map`'s own US1-must-land-first note for the same reason — a shared new piece
of state, not shared files in the abstract).

---

## Phase 3: User Story 1 - Select capabilities across the tree and generate one diagram (Priority: P1) 🎯 MVP

**Goal**: Checkboxes replace the old per-row "Generate Diagram" button; a toolbar action generates one
diagram from the checked set, with hierarchy edges only between checked parent-child pairs.

**Independent Test**: seed a capability tree spanning multiple branches, check capabilities from at least
two branches (including one parent-and-child pair), trigger "Generate Diagram from Selected," confirm the
opened diagram contains exactly the checked capabilities with an edge only between the checked pair
(quickstart.md scenario 1).

### Tests for User Story 1 (MANDATORY — ART-IV, write first, confirm failing)

- [X] T002 [P] [US1] Unit tests for `generateFromCapabilities()` in `web/src/diagrams/generators.test.ts`:
  one node per selected capability; an edge only between two selected capabilities with a direct
  parent-child relationship; no edge to/from an unselected or unrelated capability; a single-capability
  selection produces the same shape (one node, no edges, titled with its name) `generateFromCapabilitySubtree()`
  already produces for a leaf (research.md Decisions 2–4); a multi-capability selection's title is the
  generic `"Capabilities Diagram"`
- [X] T003 [P] [US1] New `web/src/business/CapabilityNode.test.tsx` (first render-based test for this
  component — mirrors `renderWithQueryClient()` from `CapabilityTree.test.tsx` since this component also
  calls hooks needing a `QueryClientProvider`): a checkbox reflects the `selected` prop; clicking it calls
  `onToggleSelect(capability.id)`; the old "⛶ Generate Diagram" button/`onGenerateDiagram` per-row call no
  longer exists (FR-006)
- [X] T004 [US1] Extend `CapabilityTree.test.tsx`: "Generate Diagram from Selected" is disabled/absent when
  nothing is selected; checking capabilities from different branches and triggering it calls the tree's
  `onGenerateDiagram` prop with a seed built from exactly the checked set

### Implementation for User Story 1

- [X] T005 [P] [US1] Implement `generateFromCapabilities(selected: BusinessCapability[]): DiagramSeed` in
  `web/src/diagrams/generators.ts` — one `addNode` per selected capability (building an id map), then one
  `addEdge` for each selected capability whose `parent_id` is also in the selected set (research.md Decision
  3), with the title logic from Decision 4 — make T002 pass (depends on T002 being red)
- [X] T006 [US1] In `CapabilityNode.tsx`: replace the "⛶ Generate Diagram" button (and its
  `generateFromCapabilitySubtree` call) with a checkbox; add `selected: boolean` and
  `onToggleSelect: (id: string) => void` props — make T003 pass (depends on T003 being red)
- [X] T007 [US1] In `CapabilityTree.tsx`: add `selectedIds` (`Set<string>`) state and a toggle function;
  thread `selected`/`onToggleSelect` through `renderTree()` down to each `CapabilityNode`, mirroring how
  `focusCapabilityId`/`orphanIds` are already threaded (depends on T006)
- [X] T008 [US1] Add a "Generate Diagram from Selected" button to `CapabilityTree.tsx`'s existing toolbar,
  disabled when `selectedIds` is empty, calling `onGenerateDiagram?.(generateFromCapabilities(selected))`
  with the selected capabilities resolved from `selectedIds` — make T004 pass (depends on T005, T007)

**Checkpoint**: User Story 1 fully functional and independently testable — quickstart.md scenario 1.

---

## Phase 4: User Story 2 - See and manage the current selection (Priority: P2)

**Goal**: A visible count of currently-selected capabilities, and a "Clear selection" action.

**Independent Test**: check several capabilities, confirm a visible count reflects the selection size, use
"Clear selection," confirm every row returns to unchecked and the count returns to zero (quickstart.md
scenario 2).

### Tests for User Story 2 (MANDATORY — ART-IV)

- [X] T009 [P] [US2] Extend `CapabilityTree.test.tsx`: a selection-count indicator reflects the current
  number of checked capabilities; a "Clear selection" action appears once at least one is checked and
  unchecks every row (and updates the count back to zero) when used

### Implementation for User Story 2

- [X] T010 [US2] Add the selection count display and "Clear selection" button to `CapabilityTree.tsx`'s
  toolbar, next to the "Generate Diagram from Selected" action added in US1 — make T009 pass (depends on
  T007, T009 being red)

**Checkpoint**: User Stories 1 and 2 both independently functional — quickstart.md scenario 2.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [X] T011 Run the full frontend regression suite: `cd web && npx vitest run && npx tsc --noEmit`
- [X] T012 [P] Confirm `adp-generate --check` remains clean (this feature touches no backend model/schema at
  all) and run the backend suite unchanged as a no-op sanity check: `pytest tests/ --ignore=tests/integration -q`
- [X] T013 Manually walk through all quickstart.md scenarios (multi-branch selection + generation,
  single-selection parity with the old button's behavior, selection count/clear-all, the unchecked-ancestor
  edge case, selection resetting on tab switch) against a running local stack in a real browser
- [X] T014 Replace the auto-generated `920-capability-diagram-select` stub line in `CLAUDE.md` (and the
  matching `AGENTS.md` "Latest work"/"Prior work:" shift) with a proper hand-written narrative at commit
  time

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — a single baseline-verification task, no code change.
- **Foundational (Phase 2)**: Not applicable — no schema change, nothing blocks US1 from starting.
- **User Stories (Phase 3–4)**: US2's toolbar additions (T010) depend on US1's `selectedIds` state (T007)
  already existing — US1 must land first in practice, even though both stories deliver independently
  testable, separately valuable increments once each lands.
- **Polish (Phase 5)**: Depends on both user stories being complete.

### Within Each User Story

- Tests written and confirmed failing before implementation (ART-IV).
- Generator logic (US1) and checkbox prop plumbing (US1) can proceed in parallel; the toolbar button that
  ties them together (T008) depends on both.

### Parallel Opportunities

- Within US1: T002/T003 in parallel; T005 depends on T002 (red); T006 depends on T003 (red); T007 depends
  on T006; T008 depends on T005 and T007 — the last integration point.
- Within US2: T009 alone; T010 depends on T007 (already landed) and T009 (red).
- **T002 (the generator) and T003 (the checkbox component test) are fully independent of each other** —
  different files, no shared state — the clearest parallel pair in this feature.

---

## Parallel Example: User Story 1's two independent tracks

```bash
# Track A — the generator (no UI dependency):
Task: "Unit tests for generateFromCapabilities() in web/src/diagrams/generators.test.ts"
Task: "Implement generateFromCapabilities() in web/src/diagrams/generators.ts"

# Track B — the checkbox (no generator dependency):
Task: "New CapabilityNode.test.tsx covering the checkbox/onToggleSelect behavior"
Task: "Replace the Generate Diagram button with a checkbox in CapabilityNode.tsx"

# Both tracks converge only at T007/T008 (CapabilityTree.tsx's selection state + toolbar button).
```

## Implementation Strategy

**MVP = User Story 1 only** (T001–T008): checkbox-based multi-select plus the "Generate Diagram from
Selected" action, fully standalone and independently demoable — delivers the entire stated value of the
feature. User Story 2 (selection count + clear-all) is a smaller, independent UX increment that can ship
right after, or be deferred without weakening US1's own value.
