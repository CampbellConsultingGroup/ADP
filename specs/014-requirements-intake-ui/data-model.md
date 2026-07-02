# Data Model: Requirements Intake HTTP API and Web Screen

**Branch**: `014-requirements-intake-ui` | **Date**: 2026-07-02

---

## Python API Boundary Models (Pydantic v2, `extra="forbid"`)

### `IntakeSubmitRequest`

Request body for `POST /api/v1/designs/{id}/intake`.

| Field | Type | Required | Notes |
|---|---|---|---|
| `mode` | `Literal["bulk_text", "structured_form"]` | Yes | Determines whether LLM is called |
| `text` | `str` | Yes | Raw text (bulk) or single requirement statement (structured); min 20 chars for bulk |
| `kind` | `RequirementKind \| None` | No | Required when `mode="structured_form"` |

**Validation**: If `mode="bulk_text"` and `len(text) < 20`, raise 422 "text too short for extraction". If `mode="structured_form"`, `kind` is required.

### `IntakeSubmitResponse`

Response from `POST /api/v1/designs/{id}/intake`.

| Field | Type | Notes |
|---|---|---|
| `operation_id` | `str` | UUID; use to poll status |
| `design_id` | `str` | Echo of the path parameter |
| `mode` | `str` | Echo of the mode submitted |
| `status` | `Literal["pending", "running", "completed", "failed"]` | Initial value: `"pending"` |

### `ProposalResponse`

One extracted proposal, returned in the operation status response.

| Field | Type | Notes |
|---|---|---|
| `proposal_id` | `str` | UUID |
| `draft_statement` | `str` | AI-extracted requirement statement |
| `kind` | `str` | `"functional"\|"non_functional"\|"constraint"\|"driver"` |
| `source_excerpt` | `str` | Portion of source text the AI cited (always shown in UI) |
| `confidence` | `float` | 0.0–1.0 |
| `verification_status` | `str` | `"verified"\|"unverified"` |
| `status` | `str` | `"pending"\|"confirmed"\|"edited_confirmed"\|"rejected"\|"expired"` |
| `confirmed_statement` | `str \| None` | Set after confirmation (may be edited version) |

### `IntakeStatusResponse`

Response from `GET /api/v1/designs/{id}/intake/{operation_id}`.

| Field | Type | Notes |
|---|---|---|
| `operation_id` | `str` | |
| `design_id` | `str` | |
| `status` | `str` | `"pending"\|"running"\|"completed"\|"failed"` |
| `proposals` | `list[ProposalResponse]` | Empty until `status="completed"` |
| `result_summary` | `str \| None` | e.g. "3 requirements extracted" |
| `error_description` | `str \| None` | Set when `status="failed"` |

### `ConfirmProposalRequest`

Request body for `POST /api/v1/designs/{id}/intake/{op_id}/proposals/{proposal_id}/confirm`.

| Field | Type | Required | Notes |
|---|---|---|---|
| `edited_statement` | `str \| None` | No | If provided, this replaces the draft_statement; must be non-empty if present |

### `ConfirmProposalResponse`

Response from the confirm endpoint.

| Field | Type | Notes |
|---|---|---|
| `requirement_id` | `str` | e.g. "REQ-003" |
| `title` | `str` | First 120 chars of the confirmed statement |
| `description` | `str` | Full confirmed statement |
| `kind` | `str` | Requirement kind |
| `proposal_id` | `str` | Echo of the confirmed proposal ID |

### `DirectRequirementRequest`

Request body for `POST /api/v1/designs/{id}/requirements` (structured form, no LLM).

| Field | Type | Required | Notes |
|---|---|---|---|
| `statement` | `str` | Yes | Full requirement text; min 10 chars |
| `kind` | `RequirementKind` | Yes | `"functional"\|"non_functional"\|"constraint"\|"driver"` |
| `description` | `str \| None` | No | Additional detail; if absent, `statement` is used as description |

### `RequirementListResponse`

Response from `GET /api/v1/designs/{id}/requirements`.

| Field | Type | Notes |
|---|---|---|
| `design_id` | `str` | |
| `requirements` | `list[RequirementItem]` | Ordered by ID |
| `total` | `int` | Count |

### `RequirementItem`

One requirement in the list response.

| Field | Type | Notes |
|---|---|---|
| `id` | `str` | e.g. "REQ-001" |
| `title` | `str` | Short title (≤ 120 chars) |
| `description` | `str` | Full statement |
| `kind` | `str` | Requirement kind |
| `satisfies` | `list[str]` | Element IDs that satisfy this requirement |

---

## Operation Store Entry Structure

```python
# _intake_store[operation_id] = {
#   "status": "pending"|"running"|"completed"|"failed",
#   "design_id": str,
#   "submitted_by": str,
#   "created_at": datetime,
#   "proposals": dict[proposal_id, ExtractedProposal],  # set by orchestrator
#   "result_summary": str | None,
#   "error_description": str | None,
#   "correlation_id": str,
# }
```

---

## TypeScript Interfaces (web/src/api/intake.ts)

```typescript
export type IntakeMode = "bulk_text" | "structured_form";
export type OperationStatus = "pending" | "running" | "completed" | "failed";
export type ProposalStatus = "pending" | "confirmed" | "edited_confirmed" | "rejected" | "expired";
export type RequirementKind = "functional" | "non_functional" | "constraint" | "driver";

export interface IntakeSubmitRequest {
  mode: IntakeMode;
  text: string;
  kind?: RequirementKind;
}

export interface IntakeSubmitResponse {
  operation_id: string;
  design_id: string;
  mode: string;
  status: OperationStatus;
}

export interface ProposalResponse {
  proposal_id: string;
  draft_statement: string;
  kind: RequirementKind;
  source_excerpt: string;
  confidence: number;
  verification_status: "verified" | "unverified";
  status: ProposalStatus;
  confirmed_statement?: string | null;
}

export interface IntakeStatusResponse {
  operation_id: string;
  design_id: string;
  status: OperationStatus;
  proposals: ProposalResponse[];
  result_summary?: string | null;
  error_description?: string | null;
}

export interface ConfirmProposalRequest {
  edited_statement?: string | null;
}

export interface ConfirmProposalResponse {
  requirement_id: string;
  title: string;
  description: string;
  kind: RequirementKind;
  proposal_id: string;
}

export interface DirectRequirementRequest {
  statement: string;
  kind: RequirementKind;
  description?: string | null;
}

export interface RequirementItem {
  id: string;
  title: string;
  description: string;
  kind: RequirementKind;
  satisfies: string[];
}

export interface RequirementListResponse {
  design_id: string;
  requirements: RequirementItem[];
  total: number;
}
```

---

## State Machine: ProposalStatus

```
PENDING ──confirm──► CONFIRMED
PENDING ──edit+confirm──► EDITED_CONFIRMED
PENDING ──reject──► REJECTED
PENDING ──(24h elapses)──► EXPIRED
```

CONFIRMED, EDITED_CONFIRMED, REJECTED, EXPIRED are all terminal — no further transitions.

---

## Routing Map

| HTTP Method | Path | Handler | Calls |
|---|---|---|---|
| `POST` | `/api/v1/designs/{id}/intake` | `submit_intake` | `ExtractionOrchestrator.run()` (background) |
| `GET` | `/api/v1/designs/{id}/intake/{op_id}` | `get_intake_status` | `_intake_store[op_id]` |
| `POST` | `/api/v1/designs/{id}/intake/{op_id}/proposals/{pid}/confirm` | `confirm_proposal` | `ExtractionOrchestrator.confirm_proposal()` |
| `POST` | `/api/v1/designs/{id}/intake/{op_id}/proposals/{pid}/reject` | `reject_proposal` | `ExtractionOrchestrator.reject_proposal()` |
| `POST` | `/api/v1/designs/{id}/requirements` | `add_requirement` | `DesignStore.save()` directly |
| `GET` | `/api/v1/designs/{id}/requirements` | `list_requirements` | `DesignStore.get()` |
