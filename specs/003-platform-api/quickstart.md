# Quickstart: Making and Polling an API Request

**Branch**: `003-platform-api` | **Date**: 2026-06-28  
**Prerequisite**: `ADP_OIDC_JWKS_URL`, `ADP_DATABASE_URL` set in environment; server running via `uvicorn adp.api.app:create_app --factory`

This guide covers the primary flows (US1–US5) using the Platform API.

---

## Starting the Server

```bash
export ADP_OIDC_JWKS_URL=https://your-idp/.well-known/jwks.json
export ADP_DATABASE_URL=postgresql+asyncpg://user:pass@localhost/adp
uvicorn adp.api.app:create_app --factory --reload
```

---

## US1: Submitting a Valid Design (CRUD)

```bash
curl -X POST http://localhost:8000/api/v1/designs \
  -H "Authorization: Bearer $ARCHITECT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "description": {
      "schema_version": "1.0.0",
      "id": "DESIGN-001",
      "title": "Order Processing System",
      "requirements": [{"id": "REQ-001", "title": "Stateless", "description": "..."}],
      "elements": [{"id": "ELM-001", "name": "API Gateway", "kind": "container", "satisfies": ["REQ-001"]}],
      "created_at": "2026-06-28T00:00:00Z",
      "updated_at": "2026-06-28T00:00:00Z"
    }
  }'
# → 201 {"description": {...}, "current_version": 1, "schema_version_stored": "1.0.0"}
```

---

## US1: Rejecting a Malformed Payload

```bash
curl -X POST http://localhost:8000/api/v1/designs \
  -H "Authorization: Bearer $ARCHITECT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"description": {"id": "DESIGN-BAD"}}'  # missing schema_version, title, etc.
# → 422 {
#   "error_code": "VALIDATION_ERROR",
#   "message": "Request body failed schema validation",
#   "violations": [
#     {"field": "body.description.schema_version", "detail": "Field required"},
#     {"field": "body.description.title", "detail": "Field required"}
#   ],
#   "correlation_id": "..."
# }
```

---

## US2: Authentication and Authorization

```bash
# No token → 401
curl http://localhost:8000/api/v1/designs/DESIGN-001
# → 401 {"error_code": "UNAUTHORIZED", ...}

# Viewer reads → OK
curl -H "Authorization: Bearer $VIEWER_TOKEN" \
  http://localhost:8000/api/v1/designs/DESIGN-001
# → 200 {"description": {...}, "current_version": 1, ...}

# Viewer writes → 403
curl -X POST http://localhost:8000/api/v1/designs \
  -H "Authorization: Bearer $VIEWER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"description": {...}}'
# → 403 {"error_code": "FORBIDDEN", ...}
```

---

## US3: Submitting and Polling an Async Operation

```bash
# Submit recommendation request → accepted immediately
curl -X POST http://localhost:8000/api/v1/operations \
  -H "Authorization: Bearer $ARCHITECT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"kind": "recommendation", "design_id": "DESIGN-001", "parameters": {}}'
# → 202 {
#   "operation_id": "op-uuid-here",
#   "kind": "recommendation",
#   "status": "pending",
#   "design_id": "DESIGN-001",
#   "submitted_by": "sub:architect-123",
#   "submitted_at": "2026-06-28T...",
#   "confirmed": false,
#   "expires_at": "2026-06-29T...",
#   "span": null
# }

# Poll until completed (2-5 second interval)
curl -H "Authorization: Bearer $ARCHITECT_TOKEN" \
  http://localhost:8000/api/v1/operations/op-uuid-here
# → 200 {"status": "completed", "result_summary": "...", "span": {"citations_present": true, ...}}
```

---

## US4: Confirming a Consequential Action

```bash
# Accept the recommendation (requires citations_present=true in span)
curl -X POST http://localhost:8000/api/v1/operations/op-uuid-here/confirm \
  -H "Authorization: Bearer $ARCHITECT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "operation_id": "op-uuid-here",
    "stated_intent": "Accept JWT auth recommendation for Order Service gateway element"
  }'
# → 200 {
#   "operation_id": "op-uuid-here",
#   "confirmed_by": "sub:architect-123",
#   "confirmed_at": "2026-06-28T14:30:00Z",
#   "audit_entry_id": "AUD-001"
# }

# Second confirmation → 409
curl -X POST http://localhost:8000/api/v1/operations/op-uuid-here/confirm \
  -H "Authorization: Bearer $ARCHITECT_TOKEN" \
  -d '{"operation_id": "op-uuid-here", "stated_intent": "Retry"}'
# → 409 {"error_code": "CONFLICT", "message": "Operation already confirmed"}
```

---

## US4: ART-VII Citation Gate

```bash
# Attempting to confirm an operation whose span.citations_present=false
curl -X POST http://localhost:8000/api/v1/operations/op-no-citations/confirm \
  -H "Authorization: Bearer $ARCHITECT_TOKEN" \
  -d '{"operation_id": "op-no-citations", "stated_intent": "Accept anyway"}'
# → 422 {
#   "error_code": "CITATION_REQUIRED",
#   "message": "AI output must carry grounding citations before acceptance (ART-VII)",
#   "violations": null,
#   "correlation_id": "..."
# }
```

---

## US5: Fetching the Generated Contract

```bash
# No auth required
curl http://localhost:8000/openapi.json
# → 200 OpenAPI 3.1 document with all endpoints, schemas, and error shapes
```

---

## What Gets Rejected

| Attempt | Status | Error Code |
|---|---|---|
| Request with no bearer token | 401 | `UNAUTHORIZED` |
| Viewer attempting a write | 403 | `FORBIDDEN` |
| Payload with missing required field | 422 | `VALIDATION_ERROR` |
| Payload with extra unknown field | 422 | `VALIDATION_ERROR` |
| Confirmation with no citations | 422 | `CITATION_REQUIRED` |
| Second confirmation of same operation | 409 | `CONFLICT` |
| Version conflict on PUT | 409 | `CONFLICT` |
| Unknown design_id | 404 | `NOT_FOUND` |
| Expired operation_id | 404 | `NOT_FOUND` |
