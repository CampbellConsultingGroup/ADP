# Contract: Element/Relationship CRUD endpoints

Five new endpoints under the existing `/api/v1/designs` prefix, replacing the currently-broken
whole-design `PUT` (`usePlaceElement`/`useDrawRelationship` call `PUT /api/v1/designs/{id}`, which
has never had a matching route — confirmed by grep across every router mounted under that prefix).
All five follow `tags.py`'s exact existing shape: fetch the design, mutate one entity, append an
`AuditEntry`, `store.save()`.

## `POST /api/v1/designs/{design_id}/elements`

**Request** (`ElementCreate`): `{"kind": "system", "name": "Payments Service"}`

**Response** `201`: the created `Element` (full shape, `description`/`satisfies`/`provenance`/
`tags`/`technology_metadata` all `null`/empty — a brand-new element has none of these yet).

**Errors**: `404` if `design_id` doesn't exist. `422` if `kind` isn't one of `person|system|
container|component`, or `name` is blank/too long.

**Audit**: `action="create-element"`, `affected_entity=<new element id>`.

## `PATCH /api/v1/designs/{design_id}/elements/{element_id}`

**Request** (`ElementUpdate`): `{"name": "Payments API"}`

**Response** `200`: the updated `Element` — every field except `name` unchanged, especially
`description`/`satisfies`/`provenance`/`tags`/`technology_metadata` (FR-011).

**Errors**: `404` if `design_id` or `element_id` doesn't exist. `422` if `name` is blank/too long.

**Audit**: `action="update-element"`, `affected_entity=<element id>`.

## `DELETE /api/v1/designs/{design_id}/elements/{element_id}`

**Response** `204`. Cascades: every `Relationship` with `source == element_id` or
`target == element_id` is also removed, in the same save — required, because
`ArchitectureDescription`'s own `model_validator` (`validate_references`) rejects any relationship
whose endpoint doesn't resolve, so `store.save()` would hard-fail otherwise.

**Errors**: `404` if `design_id` or `element_id` doesn't exist.

**Audit**: two entries when relationships cascade — `action="delete-element"` for the element,
`action="delete-relationship"` for each cascaded relationship (same pattern as a direct relationship
delete, so the audit trail reads identically either way).

## `POST /api/v1/designs/{design_id}/relationships`

**Request** (`RelationshipCreate`): `{"source": "ELM-001", "target": "ELM-002", "label": "Uses"}`

**Response** `201`: the created `Relationship`.

**Errors**: `404` if `design_id` doesn't exist. `422` if `source`/`target` don't resolve to real
elements in the design, or `label` is too long.

**Audit**: `action="create-relationship"`, `affected_entity=<new relationship id>`.

## `DELETE /api/v1/designs/{design_id}/relationships/{relationship_id}`

**Response** `204`. No cascade — deleting a relationship never affects its endpoint elements.

**Errors**: `404` if `design_id` or `relationship_id` doesn't exist.

**Audit**: `action="delete-relationship"`, `affected_entity=<relationship id>`.

## Permission gating (`src/adp/authz/enforcement.py`)

All five routes added to the existing per-route dict (the designs domain's established exact-path
convention, matching `("PUT", "/api/v1/designs/{design_id}/elements/{element_id}/tags")`'s own
entry style — not the newer prefix-rule style other, newer domains use):

```python
("POST", "/api/v1/designs/{design_id}/elements"): ActionType.WRITE_DESIGN,
("PATCH", "/api/v1/designs/{design_id}/elements/{element_id}"): ActionType.WRITE_DESIGN,
("DELETE", "/api/v1/designs/{design_id}/elements/{element_id}"): ActionType.WRITE_DESIGN,
("POST", "/api/v1/designs/{design_id}/relationships"): ActionType.WRITE_DESIGN,
("DELETE", "/api/v1/designs/{design_id}/relationships/{relationship_id}"): ActionType.WRITE_DESIGN,
```

Same `ActionType` every other design-content mutation already requires — no new permission concept.

## Endpoints this feature reuses verbatim (zero change, listed for completeness)

| Endpoint | Used for |
|---|---|
| `GET /api/v1/designs/{id}` | Loading the design's current elements/relationships |
| `GET/PUT /api/v1/designs/{id}/layout/{level}` | Position load/save (research.md Decision 3) |
| `POST /api/v1/designs/{id}/render` | Locked-theme export (FR-009) |
| `GET /api/v1/designs/{id}/export/calm` | CALM export (FR-010) |
| `PUT /api/v1/designs/{id}/elements/{element_id}/tags` | Technology metadata editing (FR-008) |
