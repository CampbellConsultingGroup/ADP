# Data Model: Multi-Select Capabilities → Generate Diagram

No new entities, tables, columns, or API response models. This feature is a client-side selection layer
over the already-existing `BusinessCapability` entity, producing the already-existing `DiagramSeed`/
`DiagramModel` shape — see plan.md's Ground-Truth Research and research.md.

## Existing entities consumed (unchanged)

### `BusinessCapability` (`web/src/api/business.ts`)

Only `id`, `name`, and `parent_id` are used by the new generator (research.md Decision 3) — every other
field (`level`, `strategic_relevance`, `maturity_level`, etc.) is irrelevant to diagram generation.

### `DiagramSeed` / `DiagramModel` (`web/src/diagrams/generators.ts` / `web/src/diagrams/core/`)

Unchanged. `generateFromCapabilities()` produces exactly the same `{ title, diagramType: "flowchart",
model }` shape `generateFromCapabilitySubtree()` already does.

## New client-side-only state

### Selection (`CapabilityTree.tsx`, component-local)

| Field | Type | Notes |
|---|---|---|
| `selectedIds` | `Set<string>` | Capability ids currently checked. Never persisted (spec.md FR-009); discarded automatically when `CapabilityTree` unmounts on tab switch (plan.md Ground-Truth Research #4). |

No new TypeScript interface is needed for this — a plain `Set<string>` in a `useState` hook is sufficient
(mirrors `orphansOnly`'s existing `boolean` `useState` in the same file, just a richer type for a richer
state shape).

## Validation rules

None new — capability data already validates at write time via the existing `BusinessCapability` model.
This feature only reads.

## State transitions

None persisted. The only "transition" is the transient selection set changing as the user checks/unchecks
rows, and resetting to empty on tab navigation away from Capabilities (not a modeled state machine, just
ordinary React component lifecycle).
