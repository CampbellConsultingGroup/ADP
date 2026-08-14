# Data Model: Capability Heat Map

No new entities, tables, columns, or API response models. This feature is a read-only, client-side
visualization of the already-existing `BusinessCapability` entity (ADP-SPEC-033/034/035), fetched via the
already-existing `useCapabilities()` hook — see plan.md's Ground-Truth Research and research.md Decision 1.

## Existing entity consumed (unchanged)

### `BusinessCapability` (`web/src/api/business.ts`, mirrors `src/adp/business/models.py`)

| Field | Type | Used by this feature for |
|---|---|---|
| `id` | `string` | Cell identity, drill-through target |
| `name` | `string` | Cell label |
| `level` | `1 \| 2 \| 3` | Hierarchy depth (via `buildTree()`) |
| `parent_id` | `string \| null` | Hierarchy construction (via `buildTree()`) |
| `position` | `number` | Sibling ordering (via `buildTree()`) |
| `strategic_relevance` | `1 \| 2 \| 3 \| null` | Selectable coloring metric; `null` = unclassified |
| `maturity_level` | `1 \| 2 \| 3 \| 4 \| 5 \| null` | Selectable coloring metric (default); `null` = unclassified |

`domain_id`/`domain_name` exist on the entity but are not used by this feature (FR-002, resolved: domain
assignment plays no role in this view's structure).

## New client-side-only shape

### `CapabilityTreeNode` (already exists, `web/src/business/CapabilityTree.tsx`)

```ts
interface CapabilityTreeNode extends BusinessCapability {
  children: CapabilityTreeNode[];
}
```

Produced by the already-exported, already-tested `buildTree(items: BusinessCapability[]):
CapabilityTreeNode[]` (research.md Decision 2) — this feature's heat map component consumes this shape
directly, introducing no new tree-node type of its own.

## Validation rules

None new — every underlying field already validates at write time via the existing `BusinessCapability`
model (ADP-SPEC-033/034). This feature only reads.

## State transitions

None — this feature has no lifecycle or mutable state of its own beyond the transient, in-memory "which
metric is currently selected" UI state (not persisted, resets on reload — spec.md's own Assumptions:
"real-time updates are not required").
