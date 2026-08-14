# Tasks: Capability Heat Map

**Input**: Design documents from `/specs/043-capability-heat-map/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md (no contracts/ — no API change)

**Tests**: Mandatory for all ADP features (ART-IV). Test tasks appear before their implementation
counterparts in every user-story phase and MUST be verified to fail before implementation begins.

**Organization**: Grouped by user story (spec.md) to enable independent implementation and testing of each.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 / US2 / US3, per spec.md's priorities (P1/P2/P3)

## Path Conventions

Entirely frontend, entirely inside `web/src/business/` — no backend file touched, no migration (plan.md's
Structure Decision):
- `web/src/business/CapabilityHeatMap.tsx` (new), `CapabilityHeatMap.test.tsx` (new)
- `web/src/business/CapabilityTree.tsx` (extend — new `focusCapabilityId` prop), `CapabilityTree.test.tsx`
  (extend)
- `web/src/business/CapabilityNode.tsx` (extend — row id + scroll/highlight-on-focus)
- `web/src/business/BusinessPage.tsx` (extend — new "Heat Map" tab)

---

## Phase 1: Setup

- [X] T001 Run `cd web && npx vitest run` to confirm a clean, fully-green baseline before any change (no
  code changes in this task)

---

## Phase 2: Foundational

**Not applicable** — no backend change, no migration, no shared blocking infrastructure (plan.md's
Ground-Truth Research: this feature reuses the existing `useCapabilities()` hook and the already-exported
`buildTree()`/`CapabilityTreeNode` from `CapabilityTree.tsx` as-is). The one real sequencing note: **US2 and
US3 both extend the component US1 creates** (`CapabilityHeatMap.tsx`), so — unlike 918/919's more
independent stories — US1 must land first; US2 and US3 can then proceed in either order against files that
barely overlap (US2 touches only `CapabilityHeatMap.tsx`; US3 touches `CapabilityTree.tsx`/
`CapabilityNode.tsx`/`BusinessPage.tsx`).

---

## Phase 3: User Story 1 - See the whole capability portfolio color-coded by maturity at a glance (Priority: P1) 🎯 MVP

**Goal**: A new "Heat Map" tab shows every business capability in its L1/L2/L3 hierarchy, each cell shaded
by maturity level (default), with a legend and a way to see a cell's exact value without leaving the view.

**Independent Test**: Seed capabilities across different maturity levels (including some unclassified), open
the Heat Map tab, confirm every capability's cell color corresponds to its actual maturity level with
unclassified capabilities visually distinct (quickstart.md scenario 1).

### Tests for User Story 1 (MANDATORY — ART-IV, write first, confirm failing)

- [X] T002 [P] [US1] Component test for `CapabilityHeatMap.tsx` in a new
  `web/src/business/CapabilityHeatMap.test.tsx` (mocking `../api/business`'s `useCapabilities`, mirroring
  `ApplicationsHeatMap.test.tsx`'s convention): renders every capability exactly once in hierarchy order,
  cells shaded by `maturity_level`, an unscored capability rendered with a distinct "unclassified"
  treatment, a legend is present, selecting/hovering a cell surfaces its full name and exact value, and an
  empty-state message renders when there are zero capabilities

### Implementation for User Story 1

- [X] T003 [US1] Create `web/src/business/CapabilityHeatMap.tsx`: fetch via the existing
  `useCapabilities()` hook, build the hierarchy via the already-exported `buildTree()` (research.md Decision
  2), render each node as a colored cell indented by `level` (flat L1/L2/L3, FR-002), shaded by
  `maturity_level` using a 5-step swatch palette (reusing `ApplicationsHeatMap.tsx`'s existing `FIVE_STEP`
  pattern), a legend explaining the shades, an unclassified treatment for `maturity_level === null`, a
  hover/click affordance showing the capability's full name + exact value, and an empty state for zero
  capabilities — make T002 pass (depends on T002 being red)
- [X] T004 [US1] Add a "Heat Map" tab to `web/src/business/BusinessPage.tsx`'s tab bar (alongside
  Capabilities/Value Streams/Domains), rendering `CapabilityHeatMap` — mirrors `StrategyPage.tsx`'s tab
  pattern from 918-strategy-rollups (depends on T003)

**Checkpoint**: User Story 1 fully functional and independently testable — quickstart.md scenario 1.

---

## Phase 4: User Story 2 - Switch the color-coding metric to strategic relevance (Priority: P2)

**Goal**: A metric selector lets the user recolor the same grid by strategic relevance instead of maturity,
client-side, with no navigation and no re-fetch (the same `useCapabilities()` data already covers both
fields).

**Independent Test**: With the same seeded capabilities, switch the metric selector to "Strategic relevance"
and confirm every cell's shade updates accordingly, with a capability unclassified for one metric but
classified for the other updating correctly (quickstart.md scenario 2).

### Tests for User Story 2 (MANDATORY — ART-IV)

- [X] T005 [P] [US2] Extend `CapabilityHeatMap.test.tsx`: selecting "Strategic relevance" from the metric
  selector recolors every cell to reflect `strategic_relevance` instead of `maturity_level`, the legend
  updates to match, and a capability unclassified for one metric but classified for the other reflects that
  correctly per metric

### Implementation for User Story 2

- [X] T006 [US2] Add a metric selector to `CapabilityHeatMap.tsx`, extending its single-metric rendering to
  switch between `maturity_level` (existing 5-step palette) and `strategic_relevance` (a new, dedicated
  3-step subset of the same swatch tokens — research.md Decision 4) — make T005 pass (depends on T003, T005
  being red)

**Checkpoint**: User Stories 1 and 2 both independently functional — quickstart.md scenario 2.

---

## Phase 5: User Story 3 - Drill from the heat map into a capability's detail (Priority: P3)

**Goal**: Clicking a heat-map cell switches to the Capabilities tab and scrolls that capability's existing
(always-expanded) row into view with a brief highlight — research.md Decision 3's resolved "existing detail
view" interpretation, since no separate capability detail screen exists anywhere in the platform today.

**Independent Test**: From the Heat Map tab, click a capability's cell (one that is off-screen in the tree);
confirm the view switches to the Capabilities tab and that row scrolls into view and is briefly highlighted
(quickstart.md scenario 3).

### Tests for User Story 3 (MANDATORY — ART-IV)

- [X] T007 [P] [US3] Extend `CapabilityTree.test.tsx`: passing a `focusCapabilityId` prop matching a
  rendered node calls that node's `scrollIntoView` (jsdom-mockable) and applies the highlight treatment;
  passing a non-matching or `null` id does neither
- [X] T008 [P] [US3] Extend `CapabilityHeatMap.test.tsx`: clicking a cell invokes the component's
  `onDrillThrough(capabilityId)` callback prop with the clicked capability's id

### Implementation for User Story 3

- [X] T009 [US3] Add a `focusCapabilityId?: string | null` prop to `CapabilityTree.tsx`'s
  `CapabilityTreeProps`, threaded through `renderTree()` down to `CapabilityNode.tsx` (mirrors how
  `orphanIds`/`onGenerateDiagram` are already threaded) (depends on T007 being red)
- [X] T010 [US3] In `CapabilityNode.tsx`: add a stable DOM id per row (`` `cap-${capability.id}` ``) and a
  `useEffect` that calls `scrollIntoView` plus applies a brief highlight style when this node's id matches
  the incoming `focusCapabilityId` — make T007 pass (depends on T009)
- [X] T011 [US3] Add an `onDrillThrough?: (capabilityId: string) => void` prop to `CapabilityHeatMap.tsx`,
  invoked when a cell is clicked — make T008 pass (depends on T003)
- [X] T012 [US3] Wire `BusinessPage.tsx`: a new `focusCapabilityId` state, passed to `CapabilityTree`; the
  Heat Map tab's `CapabilityHeatMap` receives `onDrillThrough` set to switch `tab` to `"capabilities"` and
  set that state (depends on T004, T009, T011)

**Checkpoint**: All three user stories independently functional — quickstart.md scenario 3 + full browser
walkthrough.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T013 Run the full frontend regression suite: `cd web && npx vitest run && npx tsc --noEmit`
- [X] T014 [P] Confirm `adp-generate --check` remains clean (this feature touches no backend model/schema at
  all, but the CI gate must still be re-verified unaffected) and run the backend suite unchanged as a
  no-op sanity check: `pytest tests/ --ignore=tests/integration -q`
- [X] T015 Manually walk through all quickstart.md scenarios (default maturity view, metric switch, drill-
  through scroll/highlight, empty state, deep/wide hierarchy scrolling) against a running local stack in a
  real browser
- [X] T016 Replace the auto-generated `043-capability-heat-map` stub line in `CLAUDE.md` (and the matching
  `AGENTS.md` "Latest work"/"Prior work:" shift) with a proper hand-written narrative at commit time

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — a single baseline-verification task, no code change.
- **Foundational (Phase 2)**: Not applicable — no schema change, no shared infra.
- **User Stories (Phase 3–5)**: **US1 must land first** — US2 and US3 both extend the component `CapabilityHeatMap.tsx`
  that US1 creates (unlike 918/919, where stories were more file-independent). Once US1 lands, US2
  (`CapabilityHeatMap.tsx` only) and US3 (`CapabilityTree.tsx`/`CapabilityNode.tsx`/`BusinessPage.tsx`, plus
  one small addition back to `CapabilityHeatMap.tsx` for T011) touch almost entirely disjoint files and can
  proceed in either order.
- **Polish (Phase 6)**: Depends on all three user stories being complete.

### Within Each User Story

- Tests written and confirmed failing before implementation (ART-IV).
- Data hook (existing, reused) → tree construction (existing, reused) → new component → tab wiring.

### Parallel Opportunities

- Within US1: T002 alone; T003 depends on T002 (red); T004 depends on T003.
- Within US2: T005 alone; T006 depends on T003 (already landed) and T005 (red).
- Within US3: T007/T008 in parallel; T009 depends on T007 (red); T010 depends on T009; T011 depends on T003
  (already landed) and T008 (red); T012 depends on T004, T009, T011.
- **US2 (T005–T006) and US3 (T007–T012) can proceed fully in parallel with each other** once US1 lands — US2
  touches only `CapabilityHeatMap.tsx`'s metric logic, US3 touches `CapabilityTree.tsx`/`CapabilityNode.tsx`/
  `BusinessPage.tsx` plus one small, additive prop on `CapabilityHeatMap.tsx` (T011) that doesn't conflict
  with US2's metric-selector edit to the same file in practice (different functions/props), though as with
  918's US1/US3 note, safe to interleave rather than run as two literally-simultaneous edits to the same file
  without a merge step.

---

## Parallel Example: User Story 3 (mostly independent of US2 once US1 lands)

```bash
# Tests:
Task: "Extend CapabilityTree.test.tsx for focusCapabilityId scroll/highlight behavior"
Task: "Extend CapabilityHeatMap.test.tsx for the onDrillThrough callback"

# Once red, implementation:
Task: "Add focusCapabilityId prop to CapabilityTree.tsx, threaded to CapabilityNode.tsx"
Task: "Add scroll-into-view + highlight effect in CapabilityNode.tsx"
Task: "Add onDrillThrough prop to CapabilityHeatMap.tsx"
Task: "Wire BusinessPage.tsx: tab switch + focusCapabilityId state"
```

## Implementation Strategy

**MVP = User Story 1 only** (T001–T004): a maturity-shaded capability heat map, fully standalone and
independently demoable — delivers the core "scan the whole portfolio at a glance" value (spec.md's own P1
rationale) even without the metric selector (US2) or drill-through (US3), both smaller, independent
increments that can ship in either order afterward.
