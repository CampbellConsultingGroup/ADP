# Contract: Platform REST API

**Base path**: `/api/v1`  
**Auth**: Bearer JWT on all endpoints except `GET /openapi.json`  
**Date**: 2026-06-28

All request and response bodies are JSON. Errors always use `ApiError` shape. The authoritative, generated contract is served at `GET /openapi.json`.

---

## Authentication

All endpoints (except `/openapi.json`) require:

```
Authorization: Bearer <oidc_access_token>
```

Missing or invalid token → `401 Unauthorized` with `ApiError(error_code="UNAUTHORIZED")`.  
Valid token with insufficient persona → `403 Forbidden` with `ApiError(error_code="FORBIDDEN")`.

---

## Design Endpoints (FR-001)

### `POST /api/v1/designs`

Create a new architecture design.

**Required role**: `architect`  
**Request body**: `SaveDesignRequest`  
**Response 201**: `DesignResponse`  
**Response 409**: Design ID already exists — use `PUT` to update  
**Response 422**: Payload failed schema validation — `ApiError` with `violations`

### `GET /api/v1/designs/{design_id}`

Retrieve the latest version of a design.

**Required role**: `viewer` or `architect`  
**Path parameter**: `design_id` — opaque design identifier (no sensitive data)  
**Query parameters**: `version` (optional integer) — retrieve a specific version  
**Response 200**: `DesignResponse`  
**Response 404**: Design not found — `ApiError(error_code="NOT_FOUND")`

### `PUT /api/v1/designs/{design_id}`

Save a new version of an existing design.

**Required role**: `architect`  
**Request body**: `SaveDesignRequest` (may include `expected_version` for OCC)  
**Response 200**: `DesignResponse` with updated `current_version`  
**Response 409**: Version conflict — `ApiError(error_code="CONFLICT", message="Concurrency conflict: ...")`  
**Response 422**: Payload failed schema validation

### `GET /api/v1/designs/{design_id}/versions`

List version metadata for a design (no content, just version records).

**Required role**: `viewer` or `architect`  
**Response 200**: `{ "versions": [DesignVersion, ...] }`

---

## Operation Endpoints (FR-002, FR-003)

### `POST /api/v1/operations`

Submit an async AI operation request.

**Required role**: `architect`  
**Request body**:
```json
{
  "kind": "recommendation | validation | view_generation | intake",
  "design_id": "DESIGN-001",
  "parameters": { }
}
```
**Response 202**: `OperationHandle` with `status: "pending"`; returns within 2 seconds (FR-003)  
**Response 404**: Design not found  
**Response 422**: Invalid request body

### `GET /api/v1/operations/{operation_id}`

Poll the status and result of an async operation.

**Required role**: `viewer` or `architect`  
**Response 200**: `OperationHandle` reflecting current status  
**Response 404**: Operation ID unknown or expired — `ApiError(error_code="NOT_FOUND")`

---

## Confirmation Endpoint (FR-005)

### `POST /api/v1/operations/{operation_id}/confirm`

Accept and commit the result of a completed operation. This is the sole write path for consequential AI actions (ART-VIII / QG-14).

**Required role**: `architect`  
**Request body**: `ConfirmationPayload` — must carry the `operation_id` and `stated_intent`  
**Pre-conditions**:
1. Operation status must be `completed`
2. `OperationHandle.span.citations_present` must be `True` (ART-VII gate)
3. Operation must not already be confirmed (`confirmed == False`)

**Response 200**: `ConfirmationResult`  
**Response 409**: Already confirmed — `ApiError(error_code="CONFLICT")`  
**Response 422**: `ConfirmationPayload` invalid; or `citations_present` is `False` → `ApiError(error_code="CITATION_REQUIRED", message="AI output must carry grounding citations before acceptance (ART-VII)")`  
**Response 404**: Operation unknown, expired, or not in `completed` status

---

## Contract Endpoint (FR-006)

### `GET /openapi.json`

Serve the generated OpenAPI 3.1 contract. Unauthenticated. Generated from typed handler definitions — never hand-maintained.

**Response 200**: OpenAPI 3.1 document (JSON)

---

## Cross-Cutting Behaviours

### Correlation ID

Every response carries `X-Correlation-ID: <uuid4>`. Clients should log this when reporting issues.

### Sensitive Data in URLs (NFR-002)

Only stable, opaque identifiers (`design_id`, `operation_id`) appear in URL path segments. No design content, actor email, or token material ever appears in a URL or query string.

### Structured Logs (FR-007 / ART-VI)

Every request emits:
```json
{
  "event": "request",
  "method": "POST",
  "path": "/api/v1/designs",
  "status_code": 201,
  "duration_ms": 42,
  "correlation_id": "a1b2c3...",
  "principal_id": "sub:abc123",
  "error": null
}
```
No design content, auth tokens, or `stated_intent` text appears in logs.

### Error Response Shape

All non-2xx responses:
```json
{
  "error_code": "VALIDATION_ERROR",
  "message": "Request body failed schema validation",
  "violations": [
    { "field": "body.description.schema_version", "detail": "Field required" }
  ],
  "correlation_id": "a1b2c3..."
}
```

### Health Check

`GET /health` — unauthenticated; returns `{"status": "ok"}` or `{"status": "degraded", "reason": "..."}` depending on store connectivity.
