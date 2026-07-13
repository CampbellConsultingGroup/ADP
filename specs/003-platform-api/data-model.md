# Data Model: Platform API

**Branch**: `003-platform-api` | **Date**: 2026-06-28  
**Source**: `src/adp/api/models/` (Pydantic v2 models used as FastAPI request/response types)

The API layer does not define canonical domain entities — those belong to ADP-SPEC-001 (`src/adp/models.py`). This document defines only the API-layer envelopes, operation lifecycle types, and error types that the HTTP interface introduces.

---

## `OperationStatus` (Enum)

The lifecycle states of an async operation.

| Value | Meaning |
|---|---|
| `pending` | Accepted; not yet dispatched to a worker |
| `running` | Worker has picked up the operation |
| `completed` | Worker finished successfully; result is available |
| `failed` | Worker encountered an error; no result committed |
| `expired` | Result TTL has elapsed; handle is no longer valid |

**State transitions**: `pending → running → completed | failed`; any state → `expired` after TTL.

---

## `OperationKind` (Enum)

The type of AI operation the handle represents.

| Value | AI Spec | Description |
|---|---|---|
| `recommendation` | ADP-SPEC-006 | Request AI recommendations for a design element |
| `validation` | ADP-SPEC-007 | Request AI validation of the full design |
| `view_generation` | ADP-SPEC-008 | Request generation of a diagram or document view |
| `intake` | ADP-SPEC-006 | AI-assisted requirements extraction from prose |

---

## `OperationSpan`

Telemetry payload for a completed AI operation. Populated by AI backends; all fields `None` until ADP-SPEC-006/007/008 are implemented (QG-11 deferred).

| Field | Type | Notes |
|---|---|---|
| `inputs_ref` | `str \| None` | Reference to stored input snapshot (not the input itself) |
| `outputs_ref` | `str \| None` | Reference to stored output snapshot |
| `token_usage` | `int \| None` | Total tokens consumed |
| `cost_usd` | `float \| None` | Cost in USD |
| `latency_ms` | `float \| None` | End-to-end latency in milliseconds |
| `citations_present` | `bool` | Whether the AI output carries grounding citations (ART-VII gate) |

---

## `OperationHandle`

The primary response type for async operation submission and polling (FR-003). Immutable after creation except for `status` and `span` fields.

| Field | Type | Required | Notes |
|---|---|---|---|
| `operation_id` | `str` | Yes | UUID4; stable identifier for polling and confirmation |
| `kind` | `OperationKind` | Yes | Type of operation |
| `status` | `OperationStatus` | Yes | Current lifecycle state |
| `design_id` | `str` | Yes | The design this operation targets |
| `submitted_by` | `str` | Yes | Principal ID of the submitting architect (from JWT `sub`) |
| `submitted_at` | `datetime` | Yes | ISO 8601 UTC timestamp |
| `completed_at` | `datetime \| None` | No | Set when status reaches `completed` or `failed` |
| `result_summary` | `str \| None` | No | Human-readable summary of the result (when completed) |
| `error_description` | `str \| None` | No | Human-readable error (when failed) |
| `span` | `OperationSpan \| None` | No | Telemetry payload; `None` until AI backends populate it |
| `confirmed` | `bool` | Yes | Default `False`; `True` after a successful confirmation |
| `expires_at` | `datetime` | Yes | When this handle expires from the operation store |

---

## `ConfirmationPayload`

The required request body for a consequential action confirmation (FR-005 / ART-VIII / QG-14). The caller must explicitly state what they are confirming — prevents accidental or replayed confirmations.

| Field | Type | Required | Validation | Notes |
|---|---|---|---|---|
| `operation_id` | `str` | Yes | UUID4 format | Must match the path parameter; prevents cross-confirmation |
| `stated_intent` | `str` | Yes | Non-empty, ≤ 500 chars | Human-readable statement of what is being accepted (e.g., "Accept JWT auth recommendation for Order Service") |

---

## `ConfirmationResult`

Response to a successful confirmation.

| Field | Type | Notes |
|---|---|---|
| `operation_id` | `str` | The confirmed operation |
| `confirmed_by` | `str` | Principal ID of the confirming actor |
| `confirmed_at` | `datetime` | ISO 8601 UTC |
| `audit_entry_id` | `str` | The `AuditEntry.id` written to the canonical store as proof |

---

## `ApiPrincipal`

The resolved, validated identity of an authenticated caller. Produced by `auth/jwt.py` and injected via FastAPI dependency. **Never** returned in any response body; never logged.

| Field | Type | Notes |
|---|---|---|
| `principal_id` | `str` | `sub` claim from JWT; opaque actor identifier |
| `role` | `str` | `adp_role` claim from JWT (`"architect"` or `"viewer"`) |
| `token_expires_at` | `datetime` | `exp` claim; used for logging token health only |

---

## `ApiError`

Consistent error response shape for all non-2xx responses (research Decision 7).

| Field | Type | Notes |
|---|---|---|
| `error_code` | `str` | Machine-readable code (e.g., `VALIDATION_ERROR`, `UNAUTHORIZED`, `FORBIDDEN`, `NOT_FOUND`, `CONFLICT`, `CITATION_REQUIRED`) |
| `message` | `str` | Human-readable description |
| `violations` | `list[FieldViolation] \| None` | Present only for `VALIDATION_ERROR` responses |
| `correlation_id` | `str` | The request correlation ID; enables log lookup |

## `FieldViolation`

One field-level detail within a `VALIDATION_ERROR` response.

| Field | Type | Notes |
|---|---|---|
| `field` | `str` | JSON path to the invalid field (e.g., `"body.requirements[0].id"`) |
| `detail` | `str` | Why this field failed validation |

---

## Design Request/Response Envelopes

The design CRUD endpoints wrap `ArchitectureDescription` from ADP-SPEC-001 in these thin envelopes (no field redefinition — ART-II compliance).

### `SaveDesignRequest`

| Field | Type | Notes |
|---|---|---|
| `description` | `ArchitectureDescription` | Full canonical model; validated by ADP-SPEC-001 model validator; actor is always sourced from the authenticated principal — not the request body (ART-IX / QG-13) |
| `expected_version` | `int \| None` | Optimistic concurrency version (passed through to ADP-SPEC-002 store) |

### `DesignResponse`

| Field | Type | Notes |
|---|---|---|
| `description` | `ArchitectureDescription` | Full canonical model |
| `current_version` | `int` | Current version in the store |
| `schema_version_stored` | `str` | Schema version at time of write |

---

## Operation State Machine

```
POST /operations
    → OperationHandle(status=pending)
    
GET /operations/{id}
    → OperationHandle(status=pending|running|completed|failed|expired)

POST /operations/{id}/confirm    [only when status=completed]
    ├── Check: citations_present = True  (ART-VII gate)
    ├── Check: confirmed = False  (idempotency gate)
    ├── Write: ArchitectureDescription mutation via DesignStore
    ├── Write: AuditEntry via DesignStore
    └── Return: ConfirmationResult
```
