# Phase 1 Data Model: C4 Diagram Type in the Diagram Tool

No new entity, table, or migration (research.md Decision 4) — this feature extends one existing
enumeration. What follows is that enumeration's before/after state and the one model-field
convention this feature must get right (research.md Decision 1).

## `DiagramType` (backend `Literal`, `src/adp/diagrams/models.py:10`; frontend union,
`web/src/diagrams/api.ts:11`)

| Before | After |
|---|---|
| `"flowchart" \| "sequence" \| "erd" \| "uml" \| "architecture"` | `"flowchart" \| "sequence" \| "erd" \| "uml" \| "architecture" \| "c4"` |

Both sides MUST change together (they are hand-mirrored today, not generated from one source — the
existing convention for this file pair, unchanged by this feature). No other field on `Diagram`/
`DiagramCreate`/`DiagramUpdate`/`DiagramSummary` changes shape.

## `DiagramModel.diagramTypeId` (`web/src/diagrams/core/model/diagram-model.ts:209`)

A plain `string`, not itself typed against `DiagramType` — this is the field the DSL family's own
parse/serialize functions read and write, and for `c4` specifically it carries *level* information
`DiagramType` does not:

| `DiagramType` (app-level selector) | `diagramTypeId` value(s) the `c4` family actually uses |
|---|---|
| `"c4"` (one value, always) | `"c4-context"` \| `"c4-container"` \| `"c4-component"` \| `"c4-code"` \| `"c4-deployment"` (varies — set by whichever header the current DSL text starts with, per `c4.ts`'s `HEADER_TO_LEVEL`) |

**New-diagram creation rule** (research.md Decision 1): when `DiagramType === "c4"`, the initial
`DiagramModel` MUST be created via `createEmptyDiagramModel("c4-context")`, not
`createEmptyDiagramModel("c4")`. For every other `DiagramType` value, the existing
`createEmptyDiagramModel(diagramType)` call (passing the `DiagramType` value directly) is correct
and unchanged — this is a `c4`-specific exception, not a new general rule.

**Reopen-an-existing-diagram path is unaffected**: when loading a saved diagram, `applyDsl(diagram
.dsl_source)` (`DiagramEditorPage.tsx`'s existing load effect) re-parses the stored DSL text via
`parseC4`, which sets `model.diagramTypeId` from the DSL's own header line — already correct,
already exercised by the existing reopen flow for every other family, no change needed there.

## `DiagramNode.role` / C4 element-kind mapping (`c4.ts:88-135`, unchanged — reference only)

Already fully implemented; not modified by this feature. Included here only so the mapping this
feature makes reachable is visible in one place:

| `Element.kind`-equivalent DSL keyword | `DiagramNode.role` | `DiagramNode.shape` |
|---|---|---|
| `Person` / `Person_Ext` | `person` | `person` |
| `System` / `System_Ext` | `system` | `rectangle` |
| `SystemDb` / `SystemDb_Ext` | `system` | `cylinder` |
| `SystemQueue` / `SystemQueue_Ext` | `system` | `stadium` |
| `Container` / `Container_Ext` | `container` | `rounded-rectangle` |
| `ContainerDb` / `ContainerDb_Ext` | `container` | `cylinder` |
| `ContainerQueue` / `ContainerQueue_Ext` | `container` | `stadium` |
| `Component` / `Component_Ext` | `component` | `rounded-rectangle` |
| `ComponentDb` / `ComponentDb_Ext` | `component` | `cylinder` |
| `ComponentQueue` / `ComponentQueue_Ext` | `component` | `stadium` |
| *(no role set — e.g. a toolbar-added generic shape)* | `undefined` | whatever shape was added | serializes as `System` (`elementKindFor`'s default fallback) |
