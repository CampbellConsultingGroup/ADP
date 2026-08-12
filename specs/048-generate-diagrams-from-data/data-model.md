# Phase 1 Data Model: Generate Diagrams from Business Data

No persisted entity, no database table, no Pydantic model, no change to the existing
`BusinessCapability`/`ValueStream`/`ValueStreamStage`/`Diagram` models. The only new "data" this
feature introduces is a transient, in-memory frontend type — never serialized, never stored,
never sent over the network — that exists only between a "Generate Diagram" click and the moment
the diagram editor consumes it.

## `DiagramSeed` (transient frontend type, `web/src/diagrams/generators.ts`)

```ts
interface DiagramSeed {
  title: string;
  diagramType: DiagramType;  // always "flowchart" for both v1 generators
  model: DiagramModel;       // from web/src/diagrams/core -- the same type the editor already uses
}
```

Produced by exactly two pure functions:

| Function | Input | Output |
|---|---|---|
| `generateFromValueStream(vs: ValueStreamDetail)` | A value stream with its ordered `stages` | One node per stage (label = stage name, in `position` order), sequential edges between consecutive stages, `title = vs.name` |
| `generateFromCapabilitySubtree(node: CapabilityTreeNode)` | A capability plus its nested `children` (already-built subtree, `CapabilityTree.tsx`) | One node per capability in the subtree (label = capability name), a parent→child edge for every capability with a parent inside the subtree, `title = node.name` |

**Validation rules**: None beyond what `addNode`/`addEdge` (vendored `diagram-ops.ts`) already
enforce — both functions produce well-formed input to those existing, already-tested builders.
Neither function can itself produce an invalid `DiagramModel`, by construction (spec Edge Case:
zero stages / a leaf capability with no children both simply produce zero nodes/edges beyond the
root, not an error).

**State transitions**: None — a `DiagramSeed` is consumed exactly once. `App.tsx`'s
`pendingDiagramSeed` state is set on "Generate Diagram" and cleared the moment `DiagramsPage`
reports it consumed (research.md Decision 3) — there is no multi-step lifecycle to model.

**Relationships**: None to any persisted entity, by design (spec FR-008 — no provenance is kept).
Conceptually, a `DiagramSeed`'s `model` is a snapshot derived from `BusinessCapability`/
`ValueStreamStage` rows at generation time; once handed to the editor, it is an ordinary
`DiagramModel` indistinguishable from one built by hand — the source relationship exists only in
the momentary closure between click and hand-off, never in any stored record.

## `CapabilityTreeNode` (existing type, prop-widened per research.md Decision 1)

No new type — `CapabilityTree.tsx`'s existing `export interface CapabilityTreeNode extends
BusinessCapability { children: CapabilityTreeNode[] }` is reused as-is for
`generateFromCapabilitySubtree`'s input and (per Decision 1) as `CapabilityNode.tsx`'s widened
`capability` prop type.
