# Phase 1 Data Model: C4 Design View

No new database table, no migration, no change to the canonical `ArchitectureDescription`'s field
shape (research.md Decisions 1, 6). What follows is: the new typed request/response boundary for
the 5 new endpoints, the (unchanged) entities they operate on, the adapter's mapping tables, and
the reconciliation layer's state shape.

## New request/response models (`src/adp/api/routers/elements.py`)

Mirrors `tags.py`'s `TagsRequest`/`TagsResponse` convention exactly — `BaseModel`, `extra="forbid"`.

| Model | Fields | Used by |
|---|---|---|
| `ElementCreate` | `kind: ElementKind`, `name: str` (1–120 chars, matching `Element.name`'s own constraint) | `POST /designs/{id}/elements` |
| `ElementUpdate` | `name: str` (1–120 chars) — **name only** for v1; no `kind` field (changing an element's kind is not a supported interaction — delete and recreate instead, matching the toolbar's own affordances, which only offer "add," not "convert") | `PATCH /designs/{id}/elements/{element_id}` |
| `RelationshipCreate` | `source: ElementId`, `target: ElementId`, `label: str \| None` (≤80 chars, matching `Relationship.label`'s own constraint) | `POST /designs/{id}/relationships` |

Responses are the existing `Element`/`Relationship` Pydantic models (`src/adp/models.py`) directly
— no new response shape needed; every new endpoint returns the same typed entity every other
design-reading endpoint already returns.

## Entities operated on (existing, unchanged shape)

| Entity | Relevant fields | This feature's role |
|---|---|---|
| `Element` (`models.py:98-108`) | `id` (`ELM-NNN`), `name`, `kind`, `description`, `satisfies`, `provenance`, `tags`, `technology_metadata` | Created/renamed/deleted by the new endpoints. `description`/`satisfies`/`provenance` are read-only in this feature (FR-012) — every new endpoint that touches an element MUST preserve them exactly (FR-011), never overwrite with a default/empty value. |
| `Relationship` (`models.py:111-118`) | `id` (`REL-NNN`), `source`, `target`, `label`, `technology` | Created/deleted by the new endpoints. No `RelationshipUpdate` — editing a relationship's label is out of scope for v1 (not required by any FR; delete+recreate is the path). |

## ID generation (research.md Decision 2)

```
next_element_id(design)      = f"ELM-{max([int(e.id.split('-')[1]) for e in design.elements], default=0) + 1:03d}"
next_relationship_id(design) = f"REL-{max([int(r.id.split('-')[1]) for r in design.relationships], default=0) + 1:03d}"
```

Max-plus-one, not count-plus-one — collision-safe once deletion exists (this feature is the first
to introduce element/relationship deletion).

## Adapter mapping (`web/src/canvas-v2/c4Adapter.ts`) — `Element` ⇄ `DiagramNode`

| `Element.kind` | `DiagramNode.role` | `DiagramNode.shape` (toolbar-created default) |
|---|---|---|
| `person` | `person` | `person` |
| `system` | `system` | `rectangle` |
| `container` | `container` | `rounded-rectangle` |
| `component` | `component` | `rounded-rectangle` |

`role` is an **exact string match** with `ElementKind`'s values — confirmed directly against
`core/dsl/c4.ts`'s `ELEMENT_TO_ROLE` table, no translation needed in either direction.

**Save-back narrowing (research.md Decision 6)**: if a `DiagramNode.shape` is `cylinder` or
`stadium` (a Db/Queue variant, reachable only via direct DSL-text editing, not the toolbar), the
adapter still writes `Element.kind = node.role` (the base kind) — the Db/Queue distinction is not
persisted, since the canonical model has no field for it.

**Position**: not part of this mapping at all — `DiagramNode.position` is populated from/persisted
to the *existing*, unmodified `GET/PUT /designs/{id}/layout/{level}` endpoints (research.md
Decision 3), entirely independent of the Element/Relationship mapping above.

**Containers**: `DiagramModel.containers` (boundary groupings a user creates on canvas) are never
read from or written to any `Element`/`Relationship` field — they exist only in the in-session
`DiagramModel`, discarded on reconciliation (research.md Decision 1).

## Level filtering (reused unchanged — `web/src/canvas/c4-filter.ts`)

| C4 Level | Visible `Element.kind`s |
|---|---|
| `context` | `person`, `system` |
| `container` | `system`, `container` |
| `component` | `container`, `component` |

`filterElementsForLevel`/`filterRelationshipsForLevel` (already exported, already used by
C4Canvas) are called directly by the adapter — not reimplemented.

## Reconciliation state (`web/src/canvas-v2/reconcile.ts`)

Not a persisted entity — an in-memory diff step run on every `Canvas.tsx` `onChange(model)` call:

```
reconcile(previousModel, newModel, designId, level):
  addedNodes    = newModel.nodes    not in previousModel.nodes (by id)     -> POST element per node
  removedNodes  = previousModel.nodes not in newModel.nodes (by id)        -> DELETE element per node
  renamedNodes  = same id, label changed                                  -> PATCH element per node
  addedEdges    = newModel.edges    not in previousModel.edges (by id)     -> POST relationship per edge
  removedEdges  = previousModel.edges not in newModel.edges (by id)        -> DELETE relationship per edge
  # containers: never reconciled to the backend (Decision 1)
  # positions: never part of this diff (Decision 3) — a separate, debounced
  #   PUT /layout/{level} call, matching C4Canvas's own existing pattern
  # id reconciliation: after a POST succeeds, replace the node/edge's
  #   Canvas-generated temporary id with the real ELM-NNN/REL-NNN id via a
  #   controlled setModel() update
```
