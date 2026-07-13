# API Contracts: Design Lifecycle Management (ADP-SPEC-030)

## New Endpoint: Transition Design Lifecycle

```
PATCH /api/v1/designs/{design_id}/lifecycle
```

**Auth**: Bearer token required; write access to design required.

**Request body**:
```json
{
  "status": "proposed",
  "note": "Ready for governance board review Q3 2026",
  "proposed_date": "2026-07-05T09:00:00Z",
  "current_since": null,
  "review_due": null,
  "retirement_date": null
}
```

**Fields**:
- `status` (required): The target lifecycle status. Must be a valid next state per the transition graph.
- `note` (optional, max 500 chars): Explanation recorded in the audit entry (e.g. "Superseded by DSN-042").
- `proposed_date`, `current_since`, `review_due`, `retirement_date` (all optional): Override the auto-set date for the relevant transition, or manually set/update any date without changing status (set `status` to the current status to update dates only).

**Response 200 OK** (returns updated design summary):
```json
{
  "id": "DSN-001",
  "title": "Payment Platform",
  "lifecycle_status": "proposed",
  "proposed_date": "2026-07-05T09:00:00Z",
  "current_since": null,
  "review_due": null,
  "retirement_date": null,
  "updated_at": "2026-07-05T09:00:00Z"
}
```

**Response 409 Conflict** (invalid transition):
```json
{
  "detail": "Cannot transition from 'decommissioned' to 'current'. Valid next states: none (terminal). Use status='draft' to reset."
}
```

**Response 404**: Design not found.
**Response 422**: `status` is not a recognised lifecycle value, or `note` exceeds 500 characters.

**Side effects**:
1. Updates `lifecycle_status` and date fields in the design's canonical model (`ArchitectureDescription` JSONB in `design_versions`) and on the `designs` table columns.
2. Writes an ART-IX audit entry recording: actor, `previous_status → new_status`, timestamp, optional note.

---

## Extended: List Designs (adds lifecycle filter + lifecycle fields to response)

```
GET /api/v1/designs?status=current&page=1&page_size=50
```

**New query parameter**: `status` (optional) — filter by lifecycle status. One of: `draft`, `proposed`, `current`, `deprecated`, `decommissioned`. Omit to return all statuses.

**Updated `DesignSummary` response shape**:
```json
{
  "designs": [
    {
      "id": "DSN-001",
      "title": "Payment Platform",
      "description": null,
      "element_count": 7,
      "requirement_count": 4,
      "lifecycle_status": "current",
      "proposed_date": "2026-03-01T00:00:00Z",
      "current_since": "2026-05-15T00:00:00Z",
      "review_due": "2026-12-01T00:00:00Z",
      "retirement_date": null,
      "overdue_review": true,
      "created_at": "2026-02-20T12:00:00Z",
      "updated_at": "2026-07-01T08:30:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 50
}
```

**`overdue_review`**: computed field — `true` if `lifecycle_status == "current"` AND `review_due != null` AND `review_due < now()`. Never stored; always computed on read.

---

## Extended: Create Design (defaults lifecycle to Draft)

```
POST /api/v1/designs
```

**No change to request body.** Response now includes lifecycle fields:
- `lifecycle_status: "draft"`
- all date fields: `null`

---

## Extended: Get Design (includes lifecycle in canonical model)

```
GET /api/v1/designs/{design_id}
```

`ArchitectureDescription` response now includes lifecycle fields at the top level:
```json
{
  "id": "DSN-001",
  "lifecycle_status": "current",
  "current_since": "2026-05-15T00:00:00Z",
  "review_due": "2026-12-01T00:00:00Z",
  ...
}
```
