# Contract: Requirements Intake API

**Module**: `src/adp/api/routers/intake.py`
**Date**: 2026-07-02

All endpoints are registered under `/api/v1/designs/{design_id}`. Auth pattern: same as existing routers (no-auth for local dev; `X-Actor` header used for actor attribution).

---

## `POST /api/v1/designs/{design_id}/intake`

Start an extraction operation. For `bulk_text` mode, LLM extraction runs as a background task. For `structured_form` mode, a single proposal is created synchronously and immediately pending for confirmation.

**Request body** (`IntakeSubmitRequest`, `extra="forbid"`):
```json
{ "mode": "bulk_text", "text": "The system must handle 10,000 concurrent users..." }
```
Or for structured form:
```json
{ "mode": "structured_form", "text": "The API must be stateless", "kind": "non_functional" }
```

**Response 202** (accepted, extraction starting):
```json
{
  "operation_id": "a1b2c3d4-...",
  "design_id": "DESIGN-001",
  "mode": "bulk_text",
  "status": "pending"
}
```

**Response 404**: Design not found
**Response 422**: Text too short (< 20 chars for bulk) or `kind` missing for structured form

---

## `GET /api/v1/designs/{design_id}/intake/{operation_id}`

Poll extraction status and retrieve proposals.

**Response 200** (pending or running):
```json
{
  "operation_id": "a1b2c3d4-...",
  "design_id": "DESIGN-001",
  "status": "running",
  "proposals": [],
  "result_summary": null,
  "error_description": null
}
```

**Response 200** (completed):
```json
{
  "operation_id": "a1b2c3d4-...",
  "design_id": "DESIGN-001",
  "status": "completed",
  "proposals": [
    {
      "proposal_id": "p1-uuid",
      "draft_statement": "The system MUST handle 10,000 concurrent users without degradation",
      "kind": "non_functional",
      "source_excerpt": "The system must handle 10,000 concurrent users...",
      "confidence": 0.92,
      "verification_status": "verified",
      "status": "pending",
      "confirmed_statement": null
    }
  ],
  "result_summary": "1 requirement extracted",
  "error_description": null
}
```

**Response 404**: Operation ID not found

---

## `POST /api/v1/designs/{design_id}/intake/{operation_id}/proposals/{proposal_id}/confirm`

Confirm a proposal → writes `Requirement` to canonical model.

**Request body** (`ConfirmProposalRequest`):
```json
{ "edited_statement": null }
```
Or with edit:
```json
{ "edited_statement": "The system MUST handle 10,000 concurrent users with < 1s p99 latency" }
```

**Response 200**:
```json
{
  "requirement_id": "REQ-003",
  "title": "The system MUST handle 10,000 concurrent users...",
  "description": "The system MUST handle 10,000 concurrent users with < 1s p99 latency",
  "kind": "non_functional",
  "proposal_id": "p1-uuid"
}
```

**Response 404**: Proposal not found
**Response 409**: Proposal already actioned (not pending)
**Response 410**: Proposal expired (> 24h old)

---

## `POST /api/v1/designs/{design_id}/intake/{operation_id}/proposals/{proposal_id}/reject`

Reject a proposal. No `Requirement` is written.

**Request body**: empty `{}`
**Response 200**: `{ "proposal_id": "p1-uuid", "status": "rejected" }`
**Response 404**: Proposal not found
**Response 409**: Already actioned

---

## `POST /api/v1/designs/{design_id}/requirements`

Add a requirement directly (structured form fast path; no LLM, no proposal).

**Request body** (`DirectRequirementRequest`):
```json
{ "statement": "The API must be stateless", "kind": "non_functional" }
```

**Response 201**:
```json
{
  "requirement_id": "REQ-004",
  "title": "The API must be stateless",
  "description": "The API must be stateless",
  "kind": "non_functional",
  "proposal_id": null
}
```

**Response 404**: Design not found
**Response 422**: Missing/invalid fields

---

## `GET /api/v1/designs/{design_id}/requirements`

List all requirements for a design.

**Response 200**:
```json
{
  "design_id": "DESIGN-001",
  "requirements": [
    { "id": "REQ-001", "title": "Stateless API", "description": "...", "kind": "non_functional", "satisfies": ["ELM-001"] },
    { "id": "REQ-002", "title": "10,000 concurrent users", "description": "...", "kind": "non_functional", "satisfies": [] }
  ],
  "total": 2
}
```

**Response 404**: Design not found
