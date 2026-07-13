# Tasks: Platform API

**Input**: Design documents from `/specs/003-platform-api/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: Tests are MANDATORY for all ADP features (ART-IV). Test tasks MUST appear before their implementation counterparts in every user-story phase. Tests MUST be committed and verified to fail before any implementation begins.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no file conflicts)
- **[Story]**: Which user story this task belongs to (US1–US5)
- Include exact file paths in every description

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Install dependencies, create directory skeleton, configure settings

- [ ] T001 Add API dependencies to `pyproject.toml` using minimum-version constraints: `fastapi>=0.111`, `uvicorn[standard]>=0.30`, `python-jose[cryptography]>=3.3`, `httpx>=0.27`, `openapi-spec-validator>=0.7`; run `pip install -e ".[dev]"` and verify; exact versions pinned in T053
- [ ] T002 [P] Create directory structure: `src/adp/api/`, `src/adp/api/middleware/`, `src/adp/api/auth/`, `src/adp/api/routers/`, `src/adp/api/models/`, `tests/api/`
- [ ] T003 [P] Create `tests/api/__init__.py` (empty)
- [ ] T004 Create `src/adp/api/config.py` using `pydantic-settings` `BaseSettings`: fields `ADP_OIDC_JWKS_URL: str`, `ADP_DATABASE_URL: str`, `ADP_OPERATION_TTL_SECONDS: int = 86400`, `ADP_ENV: str = "development"`; `model_config = SettingsConfigDict(env_file=".env")`
- [ ] T005 Verify installation: `python3 -c "import fastapi, uvicorn, jose, httpx; print('ok')"`

**Checkpoint**: All imports resolve; `pytest tests/unit/ tests/contract/ -q --no-cov` still passes 62 tests

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared models, middleware, auth plumbing, app factory, test conftest — MUST be complete before any user story

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T006 Create `ApiError` and `FieldViolation` Pydantic models in `src/adp/api/models/errors.py`: `ApiError` has fields `error_code: str`, `message: str`, `violations: list[FieldViolation] | None = None`, `correlation_id: str`; `FieldViolation` has `field: str`, `detail: str`; both use `model_config = ConfigDict(extra="forbid")`
- [ ] T007 Create `OperationStatus(StrEnum)`, `OperationKind(StrEnum)`, `OperationSpan`, `OperationHandle`, `OperationRequest` Pydantic models in `src/adp/api/models/operation.py` per data-model.md — `OperationSpan` has `citations_present: bool`, `inputs_ref`, `outputs_ref`, `token_usage`, `cost_usd`, `latency_ms` all optional; `OperationHandle` has all fields from data-model.md; `OperationRequest` has `kind: OperationKind`, `design_id: str`, `parameters: dict = {}`
- [ ] T008 Create `ConfirmationPayload` (fields: `operation_id: str`, `stated_intent: str` max 500 chars) and `ConfirmationResult` (fields: `operation_id`, `confirmed_by`, `confirmed_at: datetime`, `audit_entry_id: str`) in `src/adp/api/models/confirmation.py`
- [ ] T009 Create `SaveDesignRequest` (fields: `description: ArchitectureDescription`, `expected_version: int | None = None` — **no** `actor` field; actor is always taken from the authenticated principal per ART-IX) and `DesignResponse` (fields: `description: ArchitectureDescription`, `current_version: int`, `schema_version_stored: str`) in `src/adp/api/models/design.py`; import `ArchitectureDescription` from `adp.models`
- [ ] T010 Create correlation ID middleware in `src/adp/api/middleware/correlation.py`: generate UUID4 per request using `contextvars.ContextVar`; set `X-Correlation-ID` response header; expose `get_correlation_id() -> str` function used by loggers
- [ ] T011 Create structured request logging middleware in `src/adp/api/middleware/logging.py`: emit JSON log after each request with `operation`, `method`, `path`, `status_code`, `duration_ms`, `correlation_id`, `principal_id` (from context); NEVER log request body, response body, auth token, or `stated_intent`
- [ ] T012 Create `ApiPrincipal` dataclass in `src/adp/api/auth/jwt.py`: fields `principal_id: str`, `role: str`, `token_expires_at: datetime`; implement `validate_bearer_token(authorization_header: str, settings: Settings) -> ApiPrincipal` that: extracts bearer token, fetches JWKS from `settings.ADP_OIDC_JWKS_URL` (cached module-level), calls `jose.jwt.decode()`, extracts `sub` and `adp_role` claims, returns `ApiPrincipal`; raises `HTTPException(401)` on any failure (this exception is caught by the custom HTTPException handler added in T015 and converted to `ApiError(error_code="UNAUTHORIZED", ...)` with the correlation ID)
- [ ] T013 Create FastAPI dependencies in `src/adp/api/auth/rbac.py`: `require_architect(principal: ApiPrincipal = Depends(get_principal)) -> ApiPrincipal` — raises `HTTPException(403)` if `principal.role != "architect"`; `require_any_role(principal: ApiPrincipal = Depends(get_principal)) -> ApiPrincipal` — passes for any valid authenticated principal; `get_principal(authorization: str = Header(...), settings: Settings = Depends(get_settings)) -> ApiPrincipal` — calls `validate_bearer_token`
- [ ] T014 Create in-process operation store in `src/adp/api/operations_store.py`: `_store: dict[str, OperationHandle]` module-level dict; `create_operation(handle: OperationHandle) -> None`; `get_operation(operation_id: str, ttl_seconds: int) -> OperationHandle | None` — returns `None` (expired) if `now > expires_at`; `mark_confirmed(operation_id: str) -> None`; `update_status(operation_id: str, status: OperationStatus, ...) -> None`
- [ ] T015 Create `src/adp/api/app.py`: `create_app() -> FastAPI` factory that: instantiates `FastAPI(title="ADP Platform API", version="0.1.0")`; adds correlation and logging middleware; registers custom 422 exception handler that converts Pydantic `RequestValidationError` to `ApiError` shape with `violations`; adds health router at `/health`; adds `designs`, `operations`, `confirmations` routers at `/api/v1` prefix (stubs: routers exist but all return 501 until user story phases); disables `/docs` when `ADP_ENV == "production"`; also adds a custom `HTTPException` handler that converts 401 and 403 `HTTPException`s to `ApiError` shape with `correlation_id` injected from the request context — so ALL non-2xx responses use the same `ApiError` envelope
- [ ] T016 Create `src/adp/api/__init__.py` exporting `create_app`; create all `__init__.py` files in sub-packages (`middleware/`, `auth/`, `routers/`, `models/`)
- [ ] T017 Create `tests/api/conftest.py`: `test_app` fixture returning FastAPI app from `create_app()` with dependency overrides — `get_principal` overridden to return `ApiPrincipal(principal_id="test-architect", role="architect", ...)` for architect tests; separate `viewer_app` fixture with role="viewer"; `client` fixture returning `httpx.AsyncClient(app=test_app, base_url="http://test")`; `mock_store` fixture that injects a fake `DesignStore`

**Checkpoint**: `python3 -c "from adp.api import create_app; app = create_app(); print('ok')"` succeeds; `GET /health` returns `{"status": "ok"}`

---

## Phase 3: User Story 1 — Reject Malformed Payloads with Typed Errors (Priority: P1) 🎯 MVP

**Goal**: POST /api/v1/designs with missing required fields returns 422 with `ApiError` listing each violation; POST with an extra unknown field returns 422; POST with a valid payload returns 201.

**Independent Test**: Three HTTP calls (missing field, extra field, valid payload) to a test server running with a mocked auth and store — asserts on status code and error body. No auth or async required.

### Tests for User Story 1 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T018 [P] [US1] Write failing `test_post_design_missing_required_field()` in `tests/api/test_designs.py`: POST `/api/v1/designs` with `{"description": {"id": "D-001"}}` (missing `schema_version`, `title`, etc.); assert status 422; assert response JSON has `error_code == "VALIDATION_ERROR"`; assert `violations` list is non-empty and contains a violation for `description.schema_version`
- [ ] T019 [P] [US1] Write failing `test_post_design_extra_field_rejected()` in `tests/api/test_designs.py`: POST a valid design body with an extra top-level field (e.g., `"hack_field": "x"`); assert status 422 with `VALIDATION_ERROR`
- [ ] T020 [P] [US1] Write failing `test_post_design_valid_payload_accepted()` in `tests/api/test_designs.py`: POST a valid `SaveDesignRequest` (using the example fixture from `fixtures/example-adp.json`); assert status 201; assert response has `current_version == 1`

### Implementation for User Story 1

- [ ] T021 [US1] Implement POST `/api/v1/designs` handler in `src/adp/api/routers/designs.py`: accept `SaveDesignRequest`; call `store.save(description, actor=principal.principal_id)` — always use the authenticated principal as actor; never a caller-supplied override (ART-IX); return `DesignResponse(description=..., current_version=record.current_version, schema_version_stored=record...)`; raise 409 on `ConcurrencyConflictError`
- [ ] T022 [US1] Implement GET `/api/v1/designs/{design_id}` handler in `src/adp/api/routers/designs.py`: call `store.get(design_id, version=version_query_param)`; return `DesignResponse`; raise 404 with `ApiError(error_code="NOT_FOUND")` on `DesignNotFoundError`
- [ ] T023 [US1] Implement PUT `/api/v1/designs/{design_id}` and GET `/api/v1/designs/{design_id}/versions` handlers in `src/adp/api/routers/designs.py`; raise 409 on version conflict
- [ ] T024 [US1] Register designs router in `src/adp/api/app.py` (replace stub); verify `test_post_design_missing_required_field`, `test_post_design_extra_field_rejected`, `test_post_design_valid_payload_accepted` all pass

**Checkpoint**: `pytest tests/api/test_designs.py --no-cov -q` green; SC-001 (typed rejection, zero partial writes) verifiable

---

## Phase 4: User Story 2 — Authenticate and Authorize Every Request (Priority: P1)

**Goal**: No token → 401; Viewer reads → 200; Viewer writes → 403; Architect writes → 201.

**Independent Test**: Four HTTP calls with different auth states against the designs endpoints — asserts on status code only; no store interaction required.

### Tests for User Story 2 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T025 [P] [US2] Write failing `test_no_token_returns_401()`, `test_viewer_read_returns_200()`, `test_viewer_write_returns_403()`, `test_architect_write_returns_201()` in `tests/api/test_auth.py`; use separate `viewer_client` fixture (role=viewer) and `architect_client` fixture (role=architect); assert each returns the expected status code

### Implementation for User Story 2

- [ ] T026 [US2] Wire `require_architect` dependency onto `POST /designs`, `PUT /designs/{id}` in `src/adp/api/routers/designs.py`; wire `require_any_role` onto `GET /designs/{id}`, `GET /designs/{id}/versions`
- [ ] T027 [US2] Add a test in `tests/api/test_auth.py` verifying NFR-002: assert that none of the 401/403 response bodies or the `Location` / `X-Correlation-ID` headers contain the principal ID, bearer token, or any `stated_intent` text
- [ ] T028 [US2] Verify `test_no_token_returns_401`, `test_viewer_read_returns_200`, `test_viewer_write_returns_403`, `test_architect_write_returns_201` all pass

**Checkpoint**: `pytest tests/api/test_auth.py --no-cov -q` green; SC-002 (100% unauth → 401, underprivileged → 403) verifiable

---

## Phase 5: User Story 3 — Submit and Poll Async AI Operations (Priority: P2)

**Goal**: POST /operations returns 202 with OperationHandle within 2 seconds; GET /operations/{id} returns current status; expired operation returns 404.

**Independent Test**: POST to create an operation; assert 202 + operation_id within 2 seconds; GET to poll; assert status field is present; GET with fake ID; assert 404.

### Tests for User Story 3 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T029 [P] [US3] Write failing `test_submit_operation_returns_202_within_1s()` in `tests/api/test_operations.py`: POST `/api/v1/operations` with `{"kind": "recommendation", "design_id": "DESIGN-001", "parameters": {}}`; time the call; assert status 202; assert elapsed < 1.0 seconds; assert response has `operation_id`, `status == "pending"`, `confirmed == false`
- [ ] T029b [P] [US3] Write failing `test_all_operation_kinds_accepted()` in `tests/api/test_operations.py`: parametrize over all four `OperationKind` values (`recommendation`, `validation`, `view_generation`, `intake`); for each, POST `/api/v1/operations` with the given kind; assert status 202 and that `kind` in the response matches the submitted value (FR-002)
- [ ] T030 [P] [US3] Write failing `test_poll_operation_returns_handle()` in `tests/api/test_operations.py`: POST to create; GET `/api/v1/operations/{operation_id}`; assert 200 with same `operation_id`
- [ ] T031 [P] [US3] Write failing `test_poll_expired_operation_returns_404()` in `tests/api/test_operations.py`: attempt GET with a non-existent / TTL-expired `operation_id`; assert 404 with `error_code == "NOT_FOUND"`

### Implementation for User Story 3

- [ ] T032 [US3] Implement `POST /api/v1/operations` in `src/adp/api/routers/operations.py`: validate `OperationRequest`; verify design exists (call `store.get(design_id)` — raise 404 if not found); build `OperationHandle` with `status=pending`, `operation_id=uuid4()`, `expires_at=now + ttl`; call `operations_store.create_operation(handle)`; return 202 immediately
- [ ] T033 [US3] Implement `GET /api/v1/operations/{operation_id}` in `src/adp/api/routers/operations.py`: call `operations_store.get_operation(operation_id, ttl_seconds)`; if `None`, raise 404 with `ApiError(error_code="NOT_FOUND")`; return the handle
- [ ] T034 [US3] Wire `require_architect` on POST, `require_any_role` on GET in operations router; register operations router in `src/adp/api/app.py` (replace stub)
- [ ] T035 [US3] Verify `test_submit_operation_returns_202_within_2s`, `test_poll_operation_returns_handle`, `test_poll_expired_operation_returns_404` all pass

**Checkpoint**: `pytest tests/api/test_operations.py --no-cov -q` green; SC-003 (202 within 2s, pollable status) verifiable

---

## Phase 6: User Story 4 — Confirm Consequential Actions Explicitly (Priority: P2)

**Goal**: Confirming a completed operation with citations commits the change and writes an audit entry; confirming without citations returns 422 CITATION_REQUIRED; confirming twice returns 409; confirming a pending operation returns 404.

**Independent Test**: Four confirmation scenarios against an operation in `completed` state (with and without citations, first and second confirmation) — asserts on status codes and response bodies.

### Tests for User Story 4 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T036 [P] [US4] Write failing `test_confirm_completed_op_with_citations_returns_200()` in `tests/api/test_confirmations.py`: inject a completed `OperationHandle` with `span.citations_present=True` into the mock operation store; POST `/api/v1/operations/{id}/confirm` with valid `ConfirmationPayload`; assert 200; assert `audit_entry_id` is non-empty in response; assert mock store was called to write; also assert the mock store's `save` method was called with a `description` whose `audit_log` contains exactly one `AuditEntry` with `actor == "test-architect"`, `origin == "human"`, and a non-empty `action` describing the confirmation — confirming SC-004 at the store-call level, not just the response body
- [ ] T037 [P] [US4] Write failing `test_confirm_without_citations_returns_422()` in `tests/api/test_confirmations.py`: inject completed handle with `span.citations_present=False`; POST confirm; assert 422 with `error_code == "CITATION_REQUIRED"` (ART-VII gate)
- [ ] T038 [P] [US4] Write failing `test_confirm_twice_returns_409()` in `tests/api/test_confirmations.py`: confirm successfully once (mark `confirmed=True` in store); attempt second confirmation; assert 409 with `error_code == "CONFLICT"`
- [ ] T039 [P] [US4] Write failing `test_confirm_pending_op_returns_404()` in `tests/api/test_confirmations.py`: inject handle with `status=pending`; attempt confirm; assert 404 with appropriate error message

### Implementation for User Story 4

- [ ] T040 [US4] Implement `POST /api/v1/operations/{operation_id}/confirm` in `src/adp/api/routers/confirmations.py`: get handle from operation store; check `status == completed` → else 404; check `span.citations_present == True` → else 422 CITATION_REQUIRED; check `confirmed == False` → else 409; validate `ConfirmationPayload.operation_id` matches path param → else 422; write `AuditEntry` via store; call `operations_store.mark_confirmed(operation_id)`; return `ConfirmationResult(operation_id, confirmed_by=principal.principal_id, confirmed_at=now, audit_entry_id=...)`
- [ ] T041 [US4] Wire `require_architect` on the confirmation endpoint; register confirmations router in `src/adp/api/app.py`
- [ ] T042 [US4] Verify `test_confirm_completed_op_with_citations_returns_200`, `test_confirm_without_citations_returns_422`, `test_confirm_twice_returns_409`, `test_confirm_pending_op_returns_404` all pass

**Checkpoint**: `pytest tests/api/test_confirmations.py --no-cov -q` green; SC-004 (zero consequential mutations without audit entry) verifiable; QG-14 and ART-VII gates confirmed

---

## Phase 7: User Story 5 — Consume a Generated API Contract (Priority: P3)

**Goal**: GET /openapi.json returns a valid OpenAPI document listing all endpoints; no auth required; Swagger UI absent in production mode.

**Independent Test**: GET /openapi.json without auth; assert 200; assert response has `openapi` key; assert paths include `/api/v1/designs` and `/api/v1/operations`.

### Tests for User Story 5 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T043 [P] [US5] Write failing `test_openapi_json_accessible_without_auth()` in `tests/api/test_openapi.py`: GET `/openapi.json` with NO auth header; assert status 200
- [ ] T044 [P] [US5] Write failing `test_openapi_json_contains_all_endpoints()` in `tests/api/test_openapi.py`: GET `/openapi.json`; parse JSON; assert `"paths"` key present; assert `/api/v1/designs` and `/api/v1/operations` both in paths; assert schema `ArchitectureDescription` or `SaveDesignRequest` referenced in components; also call `from openapi_spec_validator import validate_spec; validate_spec(response.json())` and assert no exception is raised — verifying the contract is a valid OpenAPI 3.x document (SC-005)
- [ ] T045 [P] [US5] Write failing `test_swagger_ui_disabled_in_production()` in `tests/api/test_openapi.py`: create app with `ADP_ENV=production`; GET `/docs`; assert 404

### Implementation for User Story 5

- [ ] T046 [US5] Implement `GET /health` endpoint in `src/adp/api/routers/health.py` returning `{"status": "ok"}` with no auth; register in `create_app()`
- [ ] T047 [US5] Verify FastAPI auto-generates `/openapi.json` from registered routers — no additional code needed; confirm the endpoint is accessible in the test app; if `ADP_ENV == "production"` in `Settings`, set `docs_url=None` and `redoc_url=None` in the `FastAPI(...)` constructor in `app.py`
- [ ] T048 [US5] Verify `test_openapi_json_accessible_without_auth`, `test_openapi_json_contains_all_endpoints`, `test_swagger_ui_disabled_in_production` all pass

**Checkpoint**: `pytest tests/api/test_openapi.py --no-cov -q` green; SC-005 (generated contract passes validation) verifiable

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Coverage, quality gates, security validation, and final integration check

- [ ] T049 [P] Run `pytest tests/api/ --cov=adp.api --cov-report=term-missing --no-cov-on-fail` and verify ≥ 85% line coverage on `src/adp/api/`; add targeted tests for uncovered paths (e.g., 409 version conflict on PUT, store-unavailable degraded health) (QG-04)
- [ ] T050 [P] Run `ruff check src/adp/api/ tests/api/` and `mypy src/adp/api/`; fix all issues (QG-06)
- [ ] T051 [P] Run `bandit -r src/adp/api/ -ll` and `pip-audit --local`; fix any HIGH-severity findings; verify `ADP_OIDC_JWKS_URL` and `ADP_DATABASE_URL` are never hardcoded by grep (QG-06, QG-07, QG-08)
- [ ] T052 [P] Scan all router files (`src/adp/api/routers/*.py`) for any query parameter or path variable that could carry sensitive data (tokens, email addresses, design content); assert only opaque IDs (`design_id`, `operation_id`) appear in path segments (NFR-002 verification)
- [ ] T053 Pin installed versions of FastAPI, uvicorn, python-jose, httpx to exact specifiers in `pyproject.toml`; run clean install to verify (QG-18)
- [ ] T054 Run full existing test suite `pytest tests/unit/ tests/contract/ tests/api/ -q` to confirm ADP-SPEC-001 and ADP-SPEC-002 tests are unaffected by new code
- [ ] T055 Run `adp-generate --check` to confirm ADP-SPEC-001 schema is still drift-free (QG-02)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup (T001–T005) — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Foundational complete — 🎯 MVP; schema validation alone is independently useful
- **US2 (Phase 4)**: Depends on US1 design router existing (T021–T023); auth wraps the existing endpoints
- **US3 (Phase 5)**: Depends on Foundational complete; independent of US1/US2 endpoints but requires `store.get()` to validate design existence
- **US4 (Phase 6)**: Depends on US3 operation store and handles; independent of US1/US2 design CRUD
- **US5 (Phase 7)**: Depends on all routers being registered (US1–US4); OpenAPI generation is automatic
- **Polish (Phase 8)**: Depends on all desired user stories complete

### User Story Dependencies

- **US1 (P1)**: Can start after Phase 2 — no dependencies on US2–US5
- **US2 (P1)**: Depends on US1 router; auth wraps US1 endpoints
- **US3 (P2)**: Can start after Phase 2 — no dependency on US1 or US2 CRUD endpoints
- **US4 (P2)**: Depends on US3 (operation handle and store); no dependency on US1/US2
- **US5 (P3)**: Depends on all routers registered; no independent implementation needed

### Parallel Opportunities

- T002, T003 (Setup): parallel — different directories
- T006–T009 (Foundational models): parallel — different files
- T010, T011 (Middleware): parallel — different files
- T012, T013 (Auth, OperationStore): parallel — different files
- T018, T019, T020 (US1 tests): parallel — same file but independent functions (write as separate test functions)
- T029, T030, T031 (US3 tests): parallel — independent test functions
- T036, T037, T038, T039 (US4 tests): parallel — independent test functions
- T043, T044, T045 (US5 tests): parallel — independent test functions
- T049, T050, T051, T052 (Polish): parallel — independent tools

---

## Parallel Example: User Story 4

```bash
# Write all US4 tests in parallel (independent scenarios):
Task T036: test_confirm_completed_op_with_citations_returns_200
Task T037: test_confirm_without_citations_returns_422
Task T038: test_confirm_twice_returns_409
Task T039: test_confirm_pending_op_returns_404

# Implement confirmation router (sequential — single file):
T040 → T041 → T042
```

---

## Implementation Strategy

### MVP First (US1 + US2 Only)

1. Phase 1: Setup (T001–T005)
2. Phase 2: Foundational (T006–T017)
3. Write US1 tests T018–T020 — verify they fail
4. Phase 3: US1 implementation (T021–T024)
5. Write US2 tests T025 — verify they fail
6. Phase 4: US2 auth wiring (T026–T028)
7. **STOP and VALIDATE**: `pytest tests/api/ -q` green; GET /health ok; GET /openapi.json shows design endpoints
8. `adp-generate --check` still exits 0

### Incremental Delivery

1. Phase 1 + 2 → App factory, models, middleware ready
2. Phase 3 (US1) → Typed payload rejection working (MVP)
3. Phase 4 (US2) → Auth/authz enforced
4. Phase 5 (US3) → Async operation submission + polling
5. Phase 6 (US4) → Consequential confirmation + ART-VII gate
6. Phase 7 (US5) → Contract endpoint verified
7. Phase 8 → All quality gates green

---

## Notes

- [P] tasks = different files or independent test functions; no file conflict on concurrent execution
- Tests MUST fail before implementation; commit the failing test first (ART-IV)
- Never log request body, response body, bearer tokens, or `stated_intent` text (ART-VI / QG-08)
- The `get_principal` dependency must be overridable in tests — this is the seam for mock auth
- The ART-VII citation gate (T037, T041) must be present and tested before any AI backend is connected
- Constitution gates relevant to this feature: QG-01, QG-03, QG-04, QG-05, QG-06, QG-07, QG-08, QG-09, QG-10, QG-14
- `adp-generate --check` must remain exit 0 throughout — this feature introduces no model changes to ADP-SPEC-001
