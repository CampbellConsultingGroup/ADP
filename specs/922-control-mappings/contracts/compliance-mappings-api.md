# API Contract: Control Mappings (Traceability Links) — COMPLY-02

**Auth**: All write operations (`PUT`/`DELETE` under `/api/v1/compliance/...`) require
`ActionType.WRITE_COMPLIANCE` via the existing `("/api/v1/compliance/", WRITE_COMPLIANCE)` prefix rule
(no `enforcement.py` change needed). Reads are open **except** any Application-targeted mapping, which
requires `ActionType.READ_APPLICATION_GOVERNANCE` (research.md D2).

---

## Writes & forward lookup — `adp.compliance.router`

### PUT /api/v1/compliance/controls/{control_id}/mappings/capabilities/{capability_id}

Create-or-update the mapping (D3 upsert — never a 409 on re-mapping).

**Request body** (`ControlMappingWrite`):
```json
{
  "compliance_status": "compliant",
  "evidence_ref": "https://docs.example.com/audit/2026-mfa-rollout",
  "assessed_at": "2026-08-18",
  "assessed_by": "alice"
}
```
All fields optional except `compliance_status` (defaults to `not_assessed` if omitted entirely).

**Response 200**: `ControlMapping` (with `target_type: "capability"`, `target_id: capability_id`)
**Response 404**: `control_id` or `capability_id` does not exist
**Response 422**: invalid `compliance_status` value

The equivalent routes exist for the other three entity-targeted shapes:
- `PUT /api/v1/compliance/controls/{control_id}/mappings/applications/{application_id}`
- `PUT /api/v1/compliance/controls/{control_id}/mappings/designs/{design_id}`
- `PUT /api/v1/compliance/controls/{control_id}/mappings/patterns/{pattern_id}` (**422** additionally if the
  referenced knowledge item's `kind` is not `"pattern"` — research.md D5)

### PUT /api/v1/compliance/controls/{control_id}/mappings/organization

Create-or-update the Control's estate-wide assessment (no target id — research.md D1).

**Request body**: same `ControlMappingWrite` shape.
**Response 200**: `ControlMapping` with `target_type: "organization"`, `target_id: null`.
**Response 404**: `control_id` does not exist.

### DELETE /api/v1/compliance/controls/{control_id}/mappings/{capabilities|applications|designs|patterns}/{target_id}

Remove one mapping (research.md D6 — not an explicit FR, added for CRUD completeness matching every other
join table's unlink endpoint in the platform).

**Response 204**: removed
**Response 404**: no such mapping exists

### DELETE /api/v1/compliance/controls/{control_id}/mappings/organization

Remove the Control's estate-wide mapping. **204** / **404** as above.

### GET /api/v1/compliance/controls/{control_id}/mappings

All mappings for one Control, across every target shape (FR-011).

**Response 200** (`ControlMappingListResponse`):
```json
{
  "items": [
    { "control_id": "...", "target_type": "capability", "target_id": "...", "compliance_status": "not_assessed", "evidence_ref": null, "assessed_at": null, "assessed_by": null, "created_at": "2026-08-18T00:00:00Z" },
    { "control_id": "...", "target_type": "application", "target_id": "...", "compliance_status": "compliant", "evidence_ref": "...", "assessed_at": "2026-08-18", "assessed_by": "alice", "created_at": "2026-08-18T00:00:00Z" }
  ],
  "total": 2
}
```
If the caller lacks `READ_APPLICATION_GOVERNANCE`, any `target_type: "application"` rows are silently
omitted from `items` (and `total` reflects the filtered count) rather than the request being rejected
(research.md D2; spec.md User Story 3 Acceptance Scenario 3).

**Response 404**: `control_id` does not exist.

---

## Reverse lookups — each target's own existing router

### GET /api/v1/business/capabilities/{cap_id}/compliance-mappings

Every Control mapped to this Capability (FR-012). **Response 200**: `ControlMappingListResponse`. Ungated
beyond general platform read access (business router's existing convention).

### GET /api/v1/applications/{app_id}/compliance-mappings

Same shape, gated by `dependencies=[Depends(_require_governance_read)]` (mirrors the existing
`/applications/{app_id}/governance` route in the same router). **Response 403** if the caller lacks
`READ_APPLICATION_GOVERNANCE`.

### GET /api/v1/designs/{design_id}/compliance-mappings

Same shape. Ungated (designs router's existing convention — no sensitivity gate on design reads).

### GET /api/v1/knowledge/{item_id}/compliance-mappings

Same shape, scoped to `target_type: "pattern"` mappings for that knowledge item. Ungated (knowledge
router's existing read convention — `/api/v1/knowledge` prefix rule only gates writes via
`AMEND_STANDARD`).

All four reverse-lookup routes return **404** if the target entity itself does not exist.

---

## Response Model Reference

```json
// ControlMapping (read model)
{
  "control_id": "string",
  "target_type": "capability | application | design | pattern | organization",
  "target_id": "string | null",
  "compliance_status": "compliant | partial | non_compliant | not_assessed | not_applicable",
  "evidence_ref": "string | null",
  "assessed_at": "date | null",
  "assessed_by": "string | null",
  "created_at": "datetime"
}
```
