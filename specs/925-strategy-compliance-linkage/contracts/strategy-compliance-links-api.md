# API Contract: Strategy Domain Linkage — COMPLY-05

**Auth**: All write operations require `ActionType.WRITE_BUSINESS_ARCH` via the existing
`("/api/v1/strategy/", WRITE_BUSINESS_ARCH)` prefix rule — no `enforcement.py` change, no new
`ActionType`, no `PERMISSIONS_VERSION` bump (research.md D2; identical persona set to `WRITE_COMPLIANCE`
already). Reads of the forward direction (an Objective's/Initiative's own linked controls/mappings) are
open, matching every other field on those read models. Reads of the reverse direction inherit
`ControlMapping`'s own existing gate — an Application-targeted mapping's linked-Initiatives lookup
requires `ActionType.READ_APPLICATION_GOVERNANCE` (spec.md FR-013).

---

## ObjectiveControlMapping — `adp.strategy.router`

### POST /api/v1/strategy/objectives/{objective_id}/controls

**Request body** (`ObjectiveControlLinkCreate`):
```json
{ "control_id": "CTRL-abc123" }
```

**Response 201**: `list[str]` — the objective's full, updated `control_ids` (mirrors
`link_objective_design`'s existing response shape).
**Response 404**: `objective_id` or `control_id` does not exist.
**Response 409**: this pair is already linked.

### DELETE /api/v1/strategy/objectives/{objective_id}/controls/{control_id}

**Response 204**: unlinked.
**Response 404**: no such link exists.

### GET /api/v1/strategy/objectives/{objective_id}

Unchanged route; response (`StrategicObjective`) gains `control_ids: list[str]`.

---

## InitiativeControlMapping — `adp.strategy.router`

### POST /api/v1/strategy/initiatives/{initiative_id}/control-mappings/{target_type}/{control_id}[/{target_id}]

`target_type` is one of `capabilities` / `applications` / `designs` / `patterns` / `organization`
(matches COMPLY-02's own path vocabulary exactly — research.md D4). `{target_id}` is present for the
first four; omitted for `organization`:

- `POST /api/v1/strategy/initiatives/{initiative_id}/control-mappings/capabilities/{control_id}/{capability_id}`
- `POST /api/v1/strategy/initiatives/{initiative_id}/control-mappings/applications/{control_id}/{application_id}`
- `POST /api/v1/strategy/initiatives/{initiative_id}/control-mappings/designs/{control_id}/{design_id}`
- `POST /api/v1/strategy/initiatives/{initiative_id}/control-mappings/patterns/{control_id}/{pattern_id}`
- `POST /api/v1/strategy/initiatives/{initiative_id}/control-mappings/organization/{control_id}`

**Response 201**: `StrategyInitiative` — the full, updated initiative (mirrors
`link_initiative_objective`'s own existing response shape exactly, `strategy/router.py:532-551` — **not**
`link_objective_design`'s bare-list shape, which is the *Objective*-side link convention instead).
`control_mappings` on the returned object carries live status (research.md D3).
**Response 404**: `initiative_id` does not exist, **or** no `ControlMapping` row exists yet for that
`(control_id, target_type, target_id)` — an Initiative links to an already-*assessed* mapping; it does not
create one (data-model.md State/validation rules).
**Response 409**: this pair is already linked.

### DELETE /api/v1/strategy/initiatives/{initiative_id}/control-mappings/{target_type}/{control_id}[/{target_id}]

Same path shape as the corresponding POST. **Response 204** / **404** as above.

### GET /api/v1/strategy/initiatives/{initiative_id}

Existing route (or, if Initiatives have no dedicated single-GET route today, the entry inside
`GET /api/v1/strategy/initiatives`'s `items` list); response (`StrategyInitiative`) gains
`control_mappings: list[ControlMappingRef]`, each entry always carrying the *current* `compliance_status`
read live off the underlying `ControlMapping` row (research.md D3) — never a value captured at
link-creation time.

---

## Reverse lookups — `adp.compliance.router`

### GET /api/v1/compliance/controls/{control_id}/objectives

Every Strategic Objective linked to this Control (spec.md FR-003 reverse direction).
**Response 200**: `StrategicObjectiveListResponse`. Ungated beyond general platform read access — an
abstract Control carries no target-entity sensitivity of its own.
**Response 404**: `control_id` does not exist.

### GET /api/v1/compliance/controls/{control_id}/mappings/{target_type}/{target_id}/initiatives

*(For `target_type == organization`, the path omits `{target_id}`:
`GET /api/v1/compliance/controls/{control_id}/mappings/organization/initiatives`.)*

Every Strategy Initiative linked to this specific `ControlMapping` row (spec.md FR-007 reverse
direction).
**Response 200**: `StrategyInitiativeListResponse`.
**Response 403**: `target_type == "application"` and the caller lacks `READ_APPLICATION_GOVERNANCE`
(spec.md FR-013 — mirrors `application/router.py`'s existing single-entity `_require_governance_read`
gate, not the partial-filter approach COMPLY-02 uses for its own multi-row forward lookup, since this
route is always scoped to one specific target already).
**Response 404**: `control_id` does not exist, or no `ControlMapping` row exists for that
`(control_id, target_type, target_id)`.

---

## Response Model Reference

```json
// ControlMappingRef (adp.strategy.initiatives) — appears inside StrategyInitiative.control_mappings
{
  "control_id": "string",
  "target_type": "capability | application | design | pattern | organization",
  "target_id": "string | null",
  "compliance_status": "compliant | partial | non_compliant | not_assessed | not_applicable",
  "evidence_ref": "string | null",
  "assessed_at": "date | null"
}
```
