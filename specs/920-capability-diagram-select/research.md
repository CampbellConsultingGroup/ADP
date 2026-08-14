# Research: Multi-Select Capabilities → Generate Diagram

No `[NEEDS CLARIFICATION]` markers remain in `spec.md` (the one candidate question was resolved via a real
`AskUserQuestion` call before the spec was written). This document records the implementation-level
decisions made while translating the spec into a plan.

## Decision 1: Selection state lives in `CapabilityTree.tsx`, not `BusinessPage.tsx`

**Decision**: A new `selectedIds: Set<string>` (plus a toggle function) is component-local state inside
`CapabilityTree.tsx`, passed down to each `CapabilityNode` alongside the existing `orphanIds`/
`focusCapabilityId` pattern.

**Rationale**: plan.md's Ground-Truth Research confirms `CapabilityTree.tsx`'s own toolbar (where the new
"Generate Diagram from Selected" button and selection count/clear-all belong) already lives inside
`CapabilityTree.tsx` itself, not `BusinessPage.tsx` — so the state the toolbar reads belongs in the same
component. This also gets the "selection resets on tab switch" edge case for free: `BusinessPage.tsx`
conditionally unmounts `CapabilityTree` on tab switch, discarding component-local state automatically.

**Alternatives considered**:
- *Lift selection to `BusinessPage.tsx`* (mirroring `043-capability-heat-map`'s `focusCapabilityId`
  pattern): rejected — that state was lifted specifically because it needed to survive a tab switch (the
  Heat Map tab sets it, then switches to the Capabilities tab to consume it). Selection has no such
  cross-tab requirement; keeping it local is simpler and avoids threading two new props through
  `BusinessPage.tsx` for no benefit.

## Decision 2: The new generator reuses `generateFromCapabilitySubtree()` for the single-selection case

**Decision**: `generateFromCapabilities(selected: BusinessCapability[])` is a new function in
`web/src/diagrams/generators.ts`. When `selected.length === 1`, it is implemented by finding that
capability's node in the tree and delegating to the existing `generateFromCapabilitySubtree()` — actually,
since the multi-select flow only has the flat `BusinessCapability[]` (not a `CapabilityTreeNode` with its own
`.children`), the single-selection case is handled as a special case of the same general algorithm (Decision
3) rather than a literal delegated call, but produces an identical result: one node, no edges, titled with
that capability's own name — matching spec.md's SC-004 exact-parity requirement.

**Rationale**: `generateFromCapabilitySubtree()`'s existing behavior for a leaf capability with no children
(the common case when exactly one arbitrary capability is selected) is already just "one node, no edges,
titled with its name" — the new general algorithm naturally produces the same output for a
single-capability selection without needing a literal code branch that calls the old function.

**Alternatives considered**:
- *Keep `generateFromCapabilitySubtree()` as the single-selection path via an explicit branch*: considered,
  but the general multi-root algorithm (Decision 3) already subsumes this case exactly — an explicit branch
  would be redundant code for zero behavioral difference.
- *Delete `generateFromCapabilitySubtree()` entirely once the button is removed*: rejected — spec.md's
  SC-004 needs a documented "produces the same result" claim, which is easiest to verify by keeping the
  function and its existing test coverage (`generators.test.ts`) as the authoritative reference for what
  "the same result" means, even though nothing calls it directly anymore after this feature ships. Confirmed
  via search this is its only caller today, so removing the button does make it currently-uncalled — flagged
  as a candidate cleanup for a future bead, not addressed in this feature (out of scope; spec.md doesn't ask
  for it).

## Decision 3: Edge-inclusion algorithm — flat scan for `parent_id` membership, not a tree walk

**Decision**: `generateFromCapabilities()` operates on the flat `BusinessCapability[]` list (already filtered
to the selected ids), not a `CapabilityTreeNode` tree. For each selected capability, add one node; then, for
each selected capability whose `parent_id` is *also* in the selected set, add one edge from the parent's
generated node id to the child's.

**Rationale**: `spec.md`'s resolved Clarification only requires an edge when a direct parent-child
relationship exists *between two selected capabilities* — a flat id-membership check (`parent_id in
selectedIds`) expresses that rule directly and correctly, without needing to reconstruct or walk the full
hierarchy tree at all. Simpler than adapting `buildTree()`/a recursive walk for what is a flat, one-hop
check.

**Alternatives considered**:
- *Reuse `buildTree()` and walk the resulting tree, filtering to selected nodes*: rejected — more code for
  the same result, since only direct parent-child pairs matter (spec.md's Assumption: no automatic ancestor
  inclusion), not multi-level descent.

## Decision 4: Multi-selection diagram title

**Decision**: When exactly one capability is selected, the diagram title is that capability's own name
(SC-004 parity). When more than one is selected, the title is the generic `"Capabilities Diagram"`.

**Rationale**: `generateFromCapabilitySubtree()`'s existing title convention is the capability's own name —
there is no single natural "name" for an arbitrary multi-capability selection, so a fixed, generic title is
the simplest correct default; spec.md does not ask for anything more specific (e.g. a user-provided title),
and the diagram editor already lets a user rename a diagram after opening it.

**Alternatives considered**:
- *Join selected capability names* (e.g. `"Risk Assessment, Financial Management, ..."`): rejected —
  unbounded length for a large selection, no real benefit over a generic title the user can immediately
  rename.
