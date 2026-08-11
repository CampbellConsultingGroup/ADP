# Phase 0 Research: Generate Diagrams from Business Data

No `NEEDS CLARIFICATION` markers remain (spec.md's own clarify pass found no unresolved
ambiguity). The decisions below record concrete implementation facts confirmed by direct reads
of the actual code during planning, not assumed from the spec's description alone — several
corrected an initially-plausible-but-wrong assumption.

## Decision 1: `CapabilityNode` needs its prop type widened to reach the full subtree

**Decision**: Change `CapabilityNode`'s `capability` prop from `BusinessCapability` to
`CapabilityTreeNode` (already defined in `CapabilityTree.tsx` as `BusinessCapability & { children:
CapabilityTreeNode[] }`), and thread it through unchanged from `renderTree()`.

**Rationale**: The initially-plausible assumption — "the node component can just read
`capability.children` for its subtree" — turned out to be wrong on direct inspection.
`CapabilityNode.tsx`'s current prop is typed `capability: BusinessCapability` (no `children` data
field at all; its `children` prop is `React.ReactNode`, the already-rendered nested JSX from
`renderTree()`'s recursion, not raw subtree data). The full nested `CapabilityTreeNode[]`
structure only exists at the `CapabilityTree` component level (built once via `buildTree(items)`
from the flat `useCapabilities()` result). Since `CapabilityTreeNode extends BusinessCapability`
by strict addition (one new `children` field), widening the prop type is a compatible change —
every existing field access inside `CapabilityNode.tsx` continues to compile unchanged — and
`renderTree()` already has the exact `CapabilityTreeNode` objects on hand to pass through.

**Alternatives considered**:
- Compute each node's subtree at the `CapabilityTree` level and pass a pre-built `DiagramSeed`
  down as a plain callback closure (`onGenerateDiagram: () => void` per node, pre-bound) —
  rejected: `renderTree()` would need to import and call `generateFromCapabilitySubtree()`
  directly, coupling the tree-rendering module to the diagram-generation module for no benefit
  over just passing the node reference and letting the click handler call the generator.
- Re-fetch a capability's subtree from the backend at click time — rejected outright: the backend
  has no such endpoint, and one would have to be added purely to work around a frontend prop-typing
  gap that a one-line type widening already resolves for free (also would violate this feature's
  "zero backend change" constraint for no reason).

## Decision 2: `addNode` auto-generates node IDs — a generator must build an id-mapping table

**Decision**: Both generator functions walk their source data, calling `addNode()` for each entity
and recording `sourceEntityId → generatedNodeId` in a local `Map` as they go, then make a second
pass calling `addEdge()` using that map to resolve `sourceId`/`targetId`.

**Rationale**: Direct inspection of `diagram-ops.ts`'s `addNode()` shows it always assigns the new
node's `id` internally via `generateId('n')` — the caller has no way to pass a specific id (e.g.
reusing a capability's own database id as the node id). This ruled out an initially-simpler design
("just add all nodes, then add all edges using the source entity ids directly") — the mapping step
is not optional, it's required by the actual function signature. This is exactly the kind of
implementation-level fact that changes a generator's control flow but doesn't belong in spec.md
(a business-level document) — recorded here instead, per this project's established research.md
convention.

**Alternatives considered**:
- Patch `addNode`/`diagram-ops.ts` to optionally accept a caller-supplied id — rejected: would
  modify the vendored `core/` tree, which this project's own README convention (ADP-SPEC-046)
  explicitly discourages ("do not hand-edit files under `core/` without a documented reason");
  building an id map in the new, ADP-authored `generators.ts` is a strictly local, zero-risk
  alternative that needs no vendored-code change at all.

## Decision 3: Cross-page seed handoff reuses the existing `currentDesignId`/`onSelectDesign` pattern

**Decision**: `App.tsx` gains a `pendingDiagramSeed` state (parallel to its existing
`currentDesignId`) and an `onGenerateDiagram(seed)` callback (parallel to its existing
`onSelectDesign(id)`) that sets the pending seed *and* switches `view` to `"diagrams"` in one
action — threaded down to `BusinessPage` exactly as `onSelectDesign` is already threaded to
`PortfolioPage`/`GovernancePage`/`DesignsPage` today.

**Rationale**: `App.tsx` has no router and no shared store — `view: AppView` is the only piece of
cross-page navigation state, and lifting a second piece of state (`currentDesignId`) alongside it,
with a callback that sets both together, is already this codebase's own established solution to
exactly this problem shape ("a click on page A should both carry data to, and navigate to, page
B"). Confirmed by direct read of `App.tsx` that `onSelectDesign` does precisely this
(`setCurrentDesignId(id); setView("intake");`). Reusing that pattern for
`pendingDiagramSeed`/`onGenerateDiagram` needs no new concept — a reviewer already familiar with
how design-selection navigation works recognizes this immediately.

**Alternatives considered**:
- A new React Context or a small store (Zustand, already used in the project's `009-c4-workspace`
  plan history though not currently present in `web/src/`) dedicated to "pending diagram seed" —
  rejected: would introduce a second, parallel cross-page-state mechanism alongside the one that
  already exists and already solves this exact shape of problem, for a single, rarely-changing
  piece of transient state — added indirection with no corresponding benefit.
- `sessionStorage`/`localStorage` as the handoff channel — rejected: serializing/deserializing a
  `DiagramModel` through JSON storage adds failure modes (stale data across tabs, a version-shape
  concern for something that's supposed to be strictly transient) that simple in-memory React state
  doesn't have, for no benefit — the seed only ever needs to survive one synchronous render, not a
  page reload.

## Decision 4: The seed is a typed `DiagramModel`, not a DSL string — passed straight into the editor's existing state

**Decision**: `DiagramEditorPage.tsx` gains an optional `seed?: { title: string; model: DiagramModel
}` prop; when present (and no `diagramId`, i.e. a genuinely new diagram), its `title`/`model`/
`diagramType` state initializers use the seed directly instead of the persona-aware empty default
(ADP-914.6). The already-existing `useDslSync` hook then derives the DSL panel's text
representation from that model automatically — no separate DSL-string generation path is built.

**Rationale**: Directly satisfies spec ART-XIII and the originating request's own explicit
constraint ("generation should build a typed DiagramModel and serialize it, never hand-write DSL
text directly") with the least code: `DiagramEditorPage.tsx` already holds `model` as its source of
truth and already derives the DSL panel from it via `useDslSync` — a generator only needs to
produce a `DiagramModel`, not a serialized string, and the existing editor machinery handles the
rest identically to how a user's own manual edits do.

**Alternatives considered**:
- Have the generator call `serializeFlowchart(model)` itself and pass a DSL string through
  `DiagramEditorPage`'s existing (unrelated) DSL-loading path (the one `getDiagram()`'s
  `applyDsl(diagram.dsl_source)` uses when reopening an existing diagram) — rejected: an
  unnecessary model → text → re-parsed-model round trip for data that's already in the exact typed
  shape the editor wants, adding a parse-error surface (however unlikely) where none needs to
  exist.
