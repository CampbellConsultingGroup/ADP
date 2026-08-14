# Feature Specification: Multi-Select Capabilities → Generate Diagram

**Feature Branch**: `920-capability-diagram-select`
**Created**: 2026-08-14
**Status**: Draft
**Input**: User description: "ADP-3up.2 — on the business screen, business capability diagram should be
multi-select — capabilities should come over to the diagram tool with the relationships. This will mean
the current option to select will become a checkbox and a menu item will be needed to generate the
diagram."

## Ground-Truth Corrections

Verified against the actual codebase before writing this spec, per this session's established discipline:

1. **The existing single-capability mechanism already exists and was read directly.**
   `CapabilityNode.tsx`'s per-row "⛶" button calls `generateFromCapabilitySubtree(capability)`
   (`web/src/diagrams/generators.ts`), which walks that one capability's own descendant subtree and
   produces a `flowchart`-type `DiagramSeed`: one node per capability, with a parent→child edge for each
   hierarchy relationship — never any other relationship type. This is the mechanism this feature extends
   to a multi-root selection, not a mechanism built from scratch.
2. **Business capabilities have no relationship concept beyond parent/child today.** No
   capability-to-capability relationship table or field exists anywhere in the data model. `ADP-3up`'s own
   epic explicitly lists "capability dependency/relationship graph" as pattern #5 — a *separate, unbuilt*
   pattern requiring new relationship data, distinct from what this feature scopes (resolved via
   clarification below).
3. **The diagram-editor integration point already exists and needs no change.** `App.tsx`'s
   `onGenerateDiagram`/`pendingDiagramSeed` state, consumed by `DiagramsPage` via its `seed`/`onSeedConsumed`
   props, is the same path a single-capability-generated diagram already uses today — this feature's
   multi-select generator reuses it unchanged.
4. **`CapabilityTree.tsx` already has a toolbar action-button pattern** (Chat, Review Portfolio, +Add
   Strategic Capability) — the precedent this feature's new "Generate Diagram from Selected" action follows,
   rather than inventing a new UI convention.

## Clarifications

### Session 2026-08-14

- Q: What should "the relationships between them" mean when generating a diagram from multiple selected
  capabilities? → A: Parent-child hierarchy only — extends the existing single-capability generator
  (`generateFromCapabilitySubtree`) to an arbitrary multi-root selection: whatever hierarchy edges already
  exist among the selected capabilities appear in the diagram, and only those. No new capability
  relationship concept is introduced — that remains `ADP-3up`'s separate, unbuilt pattern #5. This keeps the
  feature a pure frontend change: no new backend data model, no migration.

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: this document, plus `/speckit-plan`/`/speckit-tasks` before any code.
- **ART-II** — The Model is the Single Source of Truth: the generated diagram is a client-side projection
  built from already-fetched `BusinessCapability` data at the moment of generation — no new persisted
  artifact, and the selection itself is transient, unpersisted UI state.
- **ART-IV** — Test-Driven Development: new selection-state and multi-root-generator logic gets failing
  tests before implementation.
- **ART-VII** — Grounded AI Only: not applicable — no AI-generated content anywhere in this feature.

## Threat Model *(mandatory — ART-V)*

**Assets at risk**: None beyond what is already exposed — capability names and hierarchy are already
readable by any authenticated user via the existing capability tree (Ground-Truth Correction, `043-capability-heat-map`'s own threat model reached the same conclusion for this identical data).

**Trust boundaries crossed**: None new — this feature performs no new read (reuses the already-fetched
capability list) and no write at all; diagram generation happens entirely client-side.

**Abuse cases**: None specific to this feature — no new write path, no new data exposure. The only
user-visible effect is which already-open capability names/relationships a generated diagram contains.

**Residual risk**: None beyond the platform's existing baseline for reading business capability data.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Select capabilities across the tree and generate one diagram (Priority: P1)

An architect browsing the Capabilities tab checks the boxes next to several capabilities — possibly from
different branches of the hierarchy — then uses a "Generate Diagram from Selected" menu action to produce a
single diagram containing exactly those capabilities and the hierarchy relationships between them, opened
in the diagram editor ready to refine further.

**Why this priority**: this is the entire value of the feature — today a diagram can only be generated from
one capability's own subtree at a time; this lets an architect assemble a diagram spanning capabilities that
don't share a single parent.

**Independent Test**: seed a capability tree spanning multiple branches, check capabilities from at least
two different branches (including a parent-and-child pair from one branch), trigger the generate action, and
confirm the opened diagram contains exactly the checked capabilities, with a hierarchy edge present only
between the checked parent-child pair.

**Acceptance Scenarios**:

1. **Given** the Capabilities tab is open, **When** an architect checks three capabilities from different
   branches, **Then** each checked row shows as selected and unchecked rows remain unaffected.
2. **Given** at least one capability is checked, **When** the architect chooses "Generate Diagram from
   Selected," **Then** the diagram editor opens with a diagram containing exactly the checked capabilities.
3. **Given** two checked capabilities have a parent-child relationship in the hierarchy, **When** the
   diagram is generated, **Then** an edge appears between them; **Given** two checked capabilities have no
   hierarchy relationship to each other, **When** the diagram is generated, **Then** no edge connects them.
4. **Given** exactly one capability is checked, **When** the diagram is generated, **Then** the result
   matches what generating a diagram for that single capability's own subtree already produces today.
5. **Given** zero capabilities are checked, **When** the architect looks for the generate action, **Then**
   it is disabled (or otherwise unavailable), since there is nothing to generate.

---

### User Story 2 - See and manage the current selection (Priority: P2)

While checking capabilities, an architect can see at a glance how many are currently selected, and can
clear the entire selection in one action rather than unchecking each row individually.

**Why this priority**: supporting UX for User Story 1 — the core generate flow works without it, but
managing a selection of more than a couple of items is impractical without a count and a clear-all action.

**Independent Test**: check several capabilities, confirm a visible count reflects the current selection
size, then use a "Clear selection" action and confirm every row returns to unchecked.

**Acceptance Scenarios**:

1. **Given** capabilities are checked, **When** the architect looks at the Capabilities tab, **Then** a
   visible indicator shows how many are currently selected.
2. **Given** one or more capabilities are checked, **When** the architect uses "Clear selection," **Then**
   every checked row becomes unchecked and the count returns to zero.

---

### Edge Cases

- What happens when a capability whose parent is *not* checked is checked on its own? It still appears in
  the generated diagram, simply with no incoming hierarchy edge (its unchecked ancestor is not
  automatically pulled in) — the diagram reflects exactly the checked set, never more.
- What happens when the architect navigates away from the Capabilities tab (e.g. to Heat Map or Value
  Streams) with capabilities still checked? The selection is transient view state and resets — returning to
  the Capabilities tab starts with nothing checked, consistent with how this session's own recent
  `focusCapabilityId` highlight state already resets on tab switch (`043-capability-heat-map`).
- What happens with a very large selection (most or all capabilities in the portfolio checked at once)?
  The diagram generates with exactly that many nodes and their real hierarchy edges — no artificial cap for
  v1, consistent with every other feature this session confirming demo-scale seeded data.
- What happens if a checked capability is deleted (e.g. by another architect) before "Generate Diagram from
  Selected" is used? It is simply no longer present in the capability list the selection is built from, so
  it drops out of the selection automatically — no stale/broken reference reaches the generator.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST let users select multiple business capabilities via a checkbox on each capability
  row in the Capabilities tab.
- **FR-002**: Users MUST be able to select capabilities from different branches and levels of the hierarchy
  within the same selection — selection is not constrained to one subtree.
- **FR-003**: System MUST provide a menu action that generates a single diagram from the currently selected
  capabilities, available only when at least one capability is selected.
- **FR-004**: The generated diagram MUST contain exactly the selected capabilities as nodes, plus a
  parent-child edge between any two selected capabilities where that relationship exists in the capability
  hierarchy — no other capabilities and no other relationship type are added (Clarification, Session
  2026-08-14).
- **FR-005**: The generated diagram MUST open in the existing diagram editor, the same way a
  single-capability-generated diagram already opens today.
- **FR-006**: The checkbox-and-menu-action mechanism MUST replace the existing per-row single-capability
  generate action, such that generating a diagram for one capability remains possible (select just that
  one, then use the menu action) without a separate, parallel control.
- **FR-007**: System MUST show the user how many capabilities are currently selected.
- **FR-008**: Users MUST be able to clear the entire selection in one action.
- **FR-009**: Selecting or deselecting a capability MUST NOT alter any persisted data — selection is
  transient, view-only state.

### Key Entities

- No new entities. This feature is a client-side selection state layered over the existing
  `BusinessCapability` data and the existing `DiagramSeed`/`DiagramModel` diagram-generation output — it
  defines no new entity, field, or relationship type.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can select capabilities spanning multiple branches and generate a single diagram
  containing all of them and their real hierarchy relationships in under 10 seconds.
- **SC-002**: 100% of generated multi-select diagrams contain exactly the selected capabilities — zero
  extra capabilities silently included, zero silently omitted.
- **SC-003**: A user can tell at a glance how many capabilities are currently selected, and clear the
  selection in a single action.
- **SC-004**: Generating a diagram from exactly one selected capability produces the same result the
  previous single-capability mechanism already produced — no loss of existing functionality.

## Assumptions

- **Diagram type stays `flowchart`**, matching the existing single-capability generator's own output type —
  this feature does not introduce a new diagram type.
- **No automatic ancestor inclusion**: checking a capability whose parent is not also checked does not pull
  that parent in automatically — the diagram reflects exactly the checked set (see Edge Cases).
- **Selection is per-visit, not persisted**: it lives only in the Capabilities tab's own view state and
  resets on navigating away, consistent with this session's own `043-capability-heat-map` precedent for
  similar transient tree-view state.
- **A minimum of one capability must be selected** to enable the generate action — there is no
  zero-capability diagram to generate.
- **No new backend endpoint or data model** — `useCapabilities()`'s existing, already-fetched data is
  sufficient (Ground-Truth Correction 1–2; Clarification, Session 2026-08-14).
