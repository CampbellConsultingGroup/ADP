# Research: Platform API

**Branch**: `003-platform-api` | **Date**: 2026-06-28  
**Phase**: 0 — Decisions and rationale before design begins

## Decision 1: API Framework — FastAPI

**Decision**: FastAPI with uvicorn as the ASGI server.

**Rationale**: FastAPI generates an OpenAPI contract from typed Pydantic handler signatures by construction (FR-006), satisfying ART-III and ART-XIII without any manual schema maintenance. It integrates natively with Pydantic v2 (already the project's standard per ART-XIII). The async request model fits the project's asyncpg/SQLAlchemy 2 async stack. FastAPI's dependency injection system cleanly separates auth, RBAC, and store injection — keeping routers testable without real infrastructure.

**Alternatives considered**:
- Flask/Quart — rejected: no native OpenAPI generation; Pydantic integration is unofficial; async support is bolted on
- Django REST Framework — rejected: synchronous-first; OpenAPI requires external packages; heavier than needed for a single-service API
- Starlette (raw) — FastAPI is a thin layer on top of Starlette; using raw Starlette loses the OpenAPI generation benefit

---

## Decision 2: OIDC / JWT Validation Strategy

**Decision**: Validate bearer JWTs using `python-jose[cryptography]`. Fetch the OIDC provider's JWKS endpoint at startup (cached) and rotate the cache on validation failure to handle key rollover. Extract `sub` (principal ID) and `adp_role` (custom claim) from the validated token.

**Rationale**: `python-jose` is lightweight, widely used for JWT validation in Python FastAPI projects, and handles RSA/EC key verification against JWKS. Caching the JWKS at startup avoids a network round-trip per request. The `adp_role` custom claim keeps persona role management in the identity provider rather than the application.

**Alternatives considered**:
- `authlib` — more complete OAuth2 library but heavier; adds complexity for a validation-only use case
- Delegating validation to a sidecar (e.g., envoy ext_authz) — appropriate for microservices at scale but overkill for v1 single-process deployment
- `jwt` (PyJWT) — valid alternative; `python-jose` was chosen for better JWKS handling out of the box

**Test approach**: Tests use FastAPI dependency overrides to replace the JWT validator with a mock that returns a preset `ApiPrincipal`. No real OIDC provider required in CI.

---

## Decision 3: Async Operation Store (v1)

**Decision**: In-process Python dict mapping `operation_id → OperationRecord`. TTL enforced by comparing stored creation timestamp against `ADP_OPERATION_TTL_SECONDS` (default: 86400 = 24h) on every read.

**Rationale**: AI backends (ADP-SPEC-006/007/008) are not yet built. The v1 operation store only needs to support the API contract (submit → poll → confirm); it does not need to survive process restarts or share state across workers. The in-process dict is the simplest correct implementation; it will be replaced by Redis or a database-backed store when AI backends need distributed workers.

**Alternatives considered**:
- Redis — correct target architecture but requires infrastructure not available for v1; deferred
- PostgreSQL table — adds a dependency on the canonical store for transient state; wrong separation
- Celery — task queue appropriate for AI workers but overkill when AI logic is stubbed

**API contract commitment**: The `OperationHandle` schema is stable and will not change when the backing store is swapped to Redis. The change is internal to `adp.api`.

---

## Decision 4: Correlation ID Strategy

**Decision**: Generate a UUID4 correlation ID in a Starlette middleware for every incoming request. Store it in a `contextvars.ContextVar`. Inject it into all log records via a logging filter. Return it to the caller as `X-Correlation-ID` response header.

**Rationale**: `contextvars` is the Python-idiomatic way to thread request-scoped context through an async call stack without passing it explicitly. Every log record gets the correlation ID automatically — satisfying ART-VI's requirement without polluting function signatures.

**Alternatives considered**:
- Pass correlation_id explicitly to every function — rejected: pollutes all function signatures; error-prone
- OpenTelemetry trace propagation — correct target for production but introduces significant infrastructure; deferred to ADP-SPEC-012 (telemetry pipeline)

---

## Decision 5: Persona Role Model (v1)

**Decision**: Two roles for v1: `Architect` (read + write + submit AI operations + confirm consequential actions) and `Viewer` (read only). Roles are extracted from the `adp_role` JWT claim. The full role model is defined in ADP-SPEC-004; this spec implements what it can given that ADP-SPEC-004 is a dependency.

**Rationale**: ADP-SPEC-004 is listed as a dependency but not yet planned. Rather than blocking on it, v1 implements the minimum viable RBAC that satisfies the spec's acceptance scenarios — two roles sufficient to test all auth scenarios. The RBAC module is designed to be extended when ADP-SPEC-004 defines additional roles.

**Endpoint permission matrix (v1)**:

| Operation | Viewer | Architect |
|---|---|---|
| GET /designs/{id} | ✅ | ✅ |
| POST /designs | ❌ 403 | ✅ |
| PUT /designs/{id} | ❌ 403 | ✅ |
| POST /operations | ❌ 403 | ✅ |
| GET /operations/{id} | ✅ | ✅ |
| POST /operations/{id}/confirm | ❌ 403 | ✅ |
| GET /openapi.json | ✅ (no auth) | ✅ (no auth) |

---

## Decision 6: Confirmation Idempotency and ART-VII Gate

**Decision**: The `OperationHandle` carries a `citations_present: bool` field. The confirmation endpoint checks this before accepting any AI-originated operation. If `citations_present` is `False`, the confirmation is rejected with a 422 and a message referencing ART-VII. Each operation ID is confirmed at most once; the operation store tracks `confirmed: bool` and rejects any second confirmation.

**Rationale**: ART-VII requires that AI outputs lacking grounding citations MUST NOT be committed to the canonical model. The API is the enforcement point for this rule when AI backends are built. Stubbing it now with `citations_present: bool` means the gate is present and tested before any AI result flows through it.

**Alternatives considered**:
- Enforce citation checking in the AI backend (ADP-SPEC-006/007/008) — correct additional layer but does not substitute for API-layer enforcement; defense in depth requires both
- Defer citation checking to the store layer — the store doesn't have knowledge of operation context; the API is the right layer

---

## Decision 7: Request/Response Error Shape

**Decision**: All error responses use a consistent `ApiError` shape: `{"error_code": "VALIDATION_ERROR", "message": "...", "violations": [{"field": "...", "detail": "..."}]}`. FastAPI's default 422 Unprocessable Entity responses are overridden to use this shape via a custom exception handler.

**Rationale**: A consistent error shape allows clients to handle all error cases with a single parsing pattern. The `error_code` field enables clients to branch on error type without parsing message strings. Overriding FastAPI's default 422 shape ensures consistency between validation errors and application errors.

---

## Decision 8: OpenAPI Contract Endpoint

**Decision**: The `/openapi.json` endpoint is served unauthenticated, as per spec Assumptions. The `/docs` (Swagger UI) endpoint is served only in non-production environments (controlled by `ADP_ENV` setting). The contract is the canonical FastAPI-generated schema; no additional schema file is committed to the repo.

**Rationale**: The spec Assumptions note that the OpenAPI contract does not expose sensitive design data and may be served unauthenticated. Restricting Swagger UI to non-production prevents accidental data exposure through interactive exploration in production environments.
