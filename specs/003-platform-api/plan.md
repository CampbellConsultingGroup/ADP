# Implementation Plan: Platform API

**Branch**: `003-platform-api` | **Date**: 2026-06-28 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/003-platform-api/spec.md`

## Summary

Build the single HTTP entrypoint to ADP as an async FastAPI service — typed CRUD for `ArchitectureDescription`, typed async operation submission and polling for AI work, explicit consequential-action confirmation with audit trail, OIDC-based auth/authz, per-request structured telemetry with correlation IDs, and a generated OpenAPI contract. Implemented as `adp.api` sub-package extending the existing ADP Python package.

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: FastAPI ≥ 0.111, uvicorn[standard] ≥ 0.30, python-jose[cryptography] ≥ 3.3 (JWT/OIDC validation), httpx ≥ 0.27 (OIDC JWKS fetch + test client)  
**Storage**: Delegates all canonical model persistence to `adp.store.DesignStore` (ADP-SPEC-002); transient operation state stored in-process dict with TTL for v1 (Redis deferred)  
**Testing**: pytest ≥ 7, pytest-asyncio, httpx.AsyncClient against FastAPI's `ASGITransport`; no real OIDC provider required — tests use pre-signed test JWTs or mock dependency overrides  
**Target Platform**: Async Python HTTP service; deployable as a single process via uvicorn  
**Project Type**: REST API web service (`adp.api` sub-package extending `src/adp/`)  
**Performance Goals**: CRUD and polling endpoints ≤ 1 second under normal load for designs with ≤ 500 entities (NFR-001); async operation acceptance ≤ 2 seconds (FR-003)  
**Constraints**: No sensitive data in URL paths or query strings (NFR-002); every request authenticated before processing; typed Pydantic models on every boundary (ART-XIII); generated OpenAPI — never hand-maintained (FR-006)  
**Scale/Scope**: Single-tenant for v1; no horizontal scale requirements beyond uvicorn workers

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Article(s) | Requirement | Status |
|------|-----------|-------------|--------|
| QG-01 | ART-I, ART-XVI | PR references approved spec/task IDs | ✅ All tasks will reference ADP-SPEC-003 |
| QG-03 | ART-III, ART-XIII, ART-XV | All payloads validate against published, versioned schemas; OpenAPI generated | ✅ FastAPI + Pydantic enforce typed boundaries by construction; FR-006 delivers generated contract |
| QG-04 | ART-IV | Tests before implementation; ≥ 85% coverage | ✅ httpx AsyncClient tests against FastAPI ASGI; no real DB or OIDC required |
| QG-05 | ART-IV, ART-XIII | Contract tests pass | ✅ Contract tests validate every endpoint response shape |
| QG-06 | ART-V | SAST clean; no secrets in source | ✅ OIDC secrets externalized via env vars |
| QG-07 | ART-V | Dep scan: no high/critical CVEs | ✅ Standard well-maintained stack |
| QG-08 | ART-V | Secret scan: no tokens, credentials, or sensitive data in source | ✅ `ADP_OIDC_JWKS_URL` and `ADP_DATABASE_URL` externalized; NFR-002 enforces no sensitive data in URLs |
| QG-09 | ART-V, ART-VIII | No prohibited-action code paths; consequential actions gated by per-action human confirmation | ✅ FR-005 / US4 implement this gate; confirmation endpoint is the sole write path for consequential actions |
| QG-10 | ART-VI | Every code path emits structured, correlated logs; no secrets in logs | ✅ Correlation middleware injects request ID; JSON log formatter; FR-007 |
| QG-11 | ART-VI | AI orchestration spans emit inputs/outputs/cost/latency | ⚠️ **Deferred** — AI backends (ADP-SPEC-006/007/008) not built yet; `OperationHandle` carries placeholder span fields (`None`); spans populated when AI specs are implemented |
| QG-14 | ART-VIII | Consequential actions require explicit, attributable human confirmation | ✅ FR-005 / US4: dedicated confirmation endpoint; single-use; audit entry on every acceptance |

**QG-11 note**: Not a violation — the operation model is designed now to carry `inputs_ref`, `outputs_ref`, `token_usage`, `cost_usd`, `latency_ms`; all `None` until AI backends are built. The gate will be enforced as part of ADP-SPEC-006/007/008 implementation.

**ART-VII constraint**: The confirmation endpoint MUST reject AI-originated `OperationHandle` results that lack grounding citations. This gate is implemented as a citation-presence check in `confirmations.py` before any acceptance write.

**Constitution Alignment**: ART-II — the API exposes `ArchitectureDescription` from ADP-SPEC-001 directly; no parallel model definitions introduced. ART-X and ART-XII are not in scope.

## Project Structure

### Documentation (this feature)

```text
specs/003-platform-api/
├── plan.md                  # This file
├── research.md              # Phase 0 — decisions and rationale
├── data-model.md            # Phase 1 — API-layer entities
├── contracts/
│   └── rest-api.md          # Phase 1 — REST endpoint catalog
├── quickstart.md            # Phase 1 — making and polling a request
├── checklists/
│   └── requirements.md      # Spec quality checklist
└── tasks.md                 # Phase 2 output (/speckit.tasks — not created here)
```

### Source Code (repository root)

```text
src/
└── adp/
    ├── __init__.py               # ADP-SPEC-001 (unchanged)
    ├── models.py                 # ADP-SPEC-001 (unchanged)
    ├── generate.py               # ADP-SPEC-001 (unchanged)
    ├── validate.py               # ADP-SPEC-001 (unchanged)
    ├── store/                    # ADP-SPEC-002 (unchanged)
    └── api/
        ├── __init__.py           # Exports create_app()
        ├── app.py                # FastAPI app factory; wires middleware + routers
        ├── config.py             # pydantic-settings: ADP_OIDC_JWKS_URL, ADP_DATABASE_URL, ADP_OPERATION_TTL_SECONDS
        ├── middleware/
        │   ├── __init__.py
        │   ├── correlation.py    # Generate X-Correlation-ID per request; inject into context + response header
        │   └── logging.py        # Structured JSON request/response log (ART-VI / QG-10)
        ├── auth/
        │   ├── __init__.py
        │   ├── jwt.py            # Fetch JWKS from OIDC provider, validate bearer JWT, return ApiPrincipal
        │   └── rbac.py           # Persona role FastAPI dependencies (require_architect, require_any_role)
        ├── routers/
        │   ├── __init__.py
        │   ├── designs.py        # FR-001: POST /designs, GET /designs/{id}, PUT /designs/{id}
        │   ├── operations.py     # FR-002/003: POST /operations, GET /operations/{id}
        │   └── confirmations.py  # FR-005: POST /operations/{id}/confirm (ART-VII + ART-VIII gate)
        └── models/
            ├── __init__.py
            ├── operation.py      # OperationHandle, OperationStatus enum, OperationSpan
            ├── confirmation.py   # ConfirmationPayload, ConfirmationResult
            └── errors.py         # ApiError, FieldViolation

tests/
├── unit/                         # ADP-SPEC-001 (unchanged)
├── contract/                     # ADP-SPEC-001 (unchanged)
├── integration/                  # ADP-SPEC-002 (unchanged)
└── api/
    ├── __init__.py
    ├── conftest.py               # FastAPI test app; mock auth + store dependency overrides
    ├── test_designs.py           # US1 + US2: payload validation + auth on CRUD endpoints
    ├── test_auth.py              # US2: JWT validation, 401/403 enforcement
    ├── test_operations.py        # US3: operation submission + status polling
    └── test_confirmations.py     # US4: confirmation gate, audit write, ART-VII citation check

pyproject.toml                    # Updated with FastAPI, uvicorn, python-jose, httpx
```

**Structure Decision**: Single `src/adp/` package with `api/` sub-package. The API layer calls the store through its typed `DesignStore` interface — no direct database access. Auth, routing, and request models are isolated in `api/` sub-modules; they never import from each other's internals.
