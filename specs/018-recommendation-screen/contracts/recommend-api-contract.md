# Contract: Recommendation API

**Module**: `src/adp/api/routers/recommend.py`
**Date**: 2026-07-02

---

## `POST /api/v1/designs/{design_id}/recommend`

Start the 5-step recommendation pipeline as a background task.

**Auth**: any authenticated role (recommendation is read-only on the design)
**Content-Type**: `application/json`

**Request body** (`RecommendRequest`, `extra="forbid"`):
```json
{ "requirement_ids": ["REQ-001", "REQ-002"], "model": null }
```

**Response 202** (pipeline started):
```json
{
  "operation_id": "a1b2c3d4-...",
  "design_id": "DESIGN-001",
  "status": "pending",
  "options": [],
  "result_summary": null,
  "error_description": null
}
```

**Response 404**: Design not found
**Response 422**: `requirement_ids` is empty

---

## `GET /api/v1/designs/{design_id}/recommend/{operation_id}`

Poll pipeline status and retrieve options.

**Response 200** (completed):
```json
{
  "operation_id": "a1b2c3d4-...",
  "design_id": "DESIGN-001",
  "status": "completed",
  "options": [
    {
      "option_id": "OPT-001",
      "rank": 1,
      "title": "Microservices with API Gateway",
      "rationale": "Addresses NFR-001 (scalability) via horizontal scaling...",
      "advisory": false,
      "satisfies": ["REQ-001", "REQ-002"],
      "trade_offs": [
        { "criterion": "Scalability", "stance": "meets", "rationale": "..." },
        { "criterion": "Operational complexity", "stance": "partially_meets", "rationale": "..." }
      ],
      "proposed_elements": [
        { "name": "API Gateway", "kind": "container", "description": "Routes all inbound traffic", "satisfies": ["REQ-001"] },
        { "name": "Auth Service", "kind": "container", "description": "Handles OAuth 2.0", "satisfies": ["REQ-002"] }
      ],
      "grounded_on": ["KI-012", "KI-034"],
      "ranking_score": 0.84,
      "status": "pending"
    }
  ],
  "result_summary": "3 options generated",
  "error_description": null
}
```

**Response 404**: Operation not found

---

## `POST /api/v1/designs/{design_id}/recommend/{operation_id}/options/{option_id}/accept`

Accept one option — materialises proposed elements into the canonical design (ART-VIII / ART-IX / ART-XI).

**Request body** (`AcceptOptionRequest`, `extra="forbid"`):
```json
{ "confirmation_id": "ACCEPT-DESIGN-001-OPT-001", "advisory_acknowledged": false }
```

For advisory options:
```json
{ "confirmation_id": "ACCEPT-ADVISORY", "advisory_acknowledged": true }
```

**Response 200**:
```json
{
  "option_id": "OPT-001",
  "elements_created": [
    { "id": "ELM-004", "name": "API Gateway", "kind": "container" },
    { "id": "ELM-005", "name": "Auth Service", "kind": "container" }
  ],
  "audit_entry_id": "AUD-005"
}
```

**Response 404**: Option not found
**Response 409**: Option already accepted
**Response 422**: Blank `confirmation_id`; or `advisory_acknowledged=false` for advisory option

---

## Advisory Handling

When `option.advisory == True`:
- `advisory_acknowledged` MUST be `True` in the request body
- If `advisory_acknowledged == False`, return 422: "advisory option requires advisory_acknowledged=true"
- The accept dialog in the UI shows an extra checkbox: "I understand this option lacks full knowledge-base grounding and accept additional risk"

---

## Contract Test Requirements

- `POST /recommend` with valid requirement_ids → 202 with operation_id
- `POST /recommend` with empty requirement_ids → 422
- `GET /recommend/{op_id}` → 200 with status field
- `GET /recommend/nonexistent` → 404
- `POST /accept` with blank confirmation_id → 422 (ART-VIII gate)
- `POST /accept` advisory option with `advisory_acknowledged=false` → 422
- `POST /accept` valid → 200 with elements_created
- `POST /accept` already-accepted option → 409
