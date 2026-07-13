# Feature Specification: Platform API

**Feature Branch**: `003-platform-api`  
**Created**: 2026-06-28  
**Status**: Draft  
**Input**: User description: "ADP-SPEC-003 — Platform API"

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: always applies; this spec governs every endpoint before any handler is written
- **ART-II** — The Model is the Single Source of Truth: not owned by this spec; the API consumes and exposes the canonical model from ADP-SPEC-001 — it MUST NOT define its own parallel model representations
- **ART-III** — Everything is Machine-Readable: the API MUST publish a generated OpenAPI contract (FR-006); every request and response validates against a typed schema
- **ART-IV** — Test-Driven Development: always applies; every endpoint requires a contract test before the handler is written
- **ART-V** — Security by Design: central concern; auth/authz, OIDC delegation, sensitive data in URLs (NFR-002), and threat model below
- **ART-VI** — Observability is Not Optional: the API MUST emit structured, correlated telemetry on every request (FR-007); AI operation spans MUST carry inputs/outputs/cost/latency
- **ART-VII** — Grounded AI Only: not owned by this spec; AI logic is in ADP-SPEC-006/007/008; the API is the transport layer only
- **ART-VIII** — Human-in-the-Loop for Consequence: central concern; FR-005 implements this article for every consequential action (accept recommendation, override verdict, export)
- **ART-IX** — Provenance and Auditability: every consequential action MUST write an audit entry attributable to the acting principal
- **ART-XIII** — Typed Contracts Everywhere: all request and response payloads MUST be typed against the published schema; untyped dicts and raw JSON strings MUST NOT cross the API boundary

## Threat Model *(mandatory — ART-V)*

The Platform API is the internet-facing (or network-exposed) surface of ADP. It handles sensitive organizational intellectual property and delegates consequential AI recommendations. Risk is moderate-to-high.

**Assets at risk**: Architecture description data (confidential design decisions, requirements, verdicts); authentication tokens and session context; AI-derived recommendations before human review; the audit trail itself.

**Trust boundaries crossed**: Client (browser/CLI/service) → API, API → ADP-SPEC-002 store, API → OIDC identity provider, API → AI orchestration services (ADP-SPEC-006/007/008).

**Abuse cases**:
- **Unauthenticated access**: A caller bypasses authentication and reads or mutates designs → Mitigation: every endpoint MUST verify a valid token before processing (FR-004); 401 on missing/invalid token
- **Privilege escalation**: An architect with Viewer role submits a mutation → Mitigation: persona-based authorization checked after authentication before any store operation (FR-004); 403 on insufficient permission
- **Schema bypass**: A caller sends a partially valid payload that passes superficial checks but violates the canonical model → Mitigation: all payloads are validated against the published schema before any store write; FR-001 and ART-XIII
- **Sensitive data leakage via URLs**: Design IDs, version numbers, or actor identifiers embedded in query strings appear in server logs, referrer headers, and browser history → Mitigation: NFR-002; only stable opaque identifiers are permitted in path segments; no sensitive parameters in query strings
- **Unauthorized consequential action**: A caller accepts a recommendation without an explicit confirmation step, or replays a previous confirmation → Mitigation: FR-005 requires a confirmation payload per action; confirmations are single-use and tied to a specific operation ID
- **AI output injection without grounding**: An AI recommendation that lacks citations is committed to the model via the API → Mitigation: the API MUST reject AI-originated writes that lack grounding citations (ART-VII); this is enforced at the API boundary even before the AI spec is built

**Residual risk**: Compromised OIDC tokens (mitigated by short token lifetimes and standard OIDC practices); DDoS against the API surface (accepted as an infrastructure concern, not an application concern for v1).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Reject Malformed Payloads with Typed Errors (Priority: P1)

An API consumer (a UI, a CLI, or a service integration) sends a request with a payload that is missing required fields or contains an unknown field. The API rejects it immediately with a structured validation error identifying the specific problem — without touching the store.

**Why this priority**: Typed rejection is the API's first safety layer. If malformed payloads can be partially applied, downstream consumers receive corrupted data. This is also the foundational test that every other user story depends on.

**Independent Test**: Send a request with a missing required field and an extra unknown field; assert the response carries a structured error listing both problems; assert nothing was written to the store. Tests independently of all other stories.

**Acceptance Scenarios**:

1. **Given** a request payload missing a required field, **When** the request is submitted, **Then** the API responds with a structured validation error identifying the missing field; the store is not modified
2. **Given** a request payload containing an unknown field, **When** the request is submitted, **Then** the API responds with a structured validation error identifying the extra field; the store is not modified
3. **Given** a valid, well-formed request payload, **When** the request is submitted with a valid token, **Then** the API accepts it and processes it normally

---

### User Story 2 - Authenticate and Authorize Every Request (Priority: P1)

A user or service sends a request to create, read, or modify a design. If they have no valid credential, the request is rejected before any processing. If their credential is valid but their persona does not permit the operation, the request is also rejected.

**Why this priority**: Authentication and authorization are the security boundary for all other capabilities. No other user story is safe to deploy without this one.

**Independent Test**: Send a request without a token and assert 401. Send a read request with a Viewer token and assert success. Send a write request with the same Viewer token and assert 403. All three assertions are independent of AI, async, or confirmation flows.

**Acceptance Scenarios**:

1. **Given** a request with no authentication token, **When** the request reaches any endpoint, **Then** the API responds with 401 and does not process the request
2. **Given** a valid token for a Viewer persona, **When** a read operation is requested, **Then** the API permits it and returns the requested resource
3. **Given** a valid token for a Viewer persona, **When** a write or mutation operation is requested, **Then** the API responds with 403 and no mutation occurs
4. **Given** a valid token for an Architect persona, **When** a write operation is requested, **Then** the API permits it and processes the mutation

---

### User Story 3 - Submit and Poll Async AI Operations (Priority: P2)

An architect submits a recommendation request for their design. Rather than waiting for the AI to respond (which may take seconds to minutes), they receive an operation handle immediately and can poll for the result at their convenience.

**Why this priority**: Async operations protect the API from blocking on AI latency. Without this, the API's availability is coupled to AI service response times. Builds on US1 (payload validation) and US2 (auth).

**Independent Test**: Submit a recommendation request; assert the response carries an operation ID and a "pending" status within 2 seconds; poll the status endpoint with the operation ID; assert status transitions from "pending" to "running" to "completed" or "failed". Tests independently of CRUD and confirmation flows.

**Acceptance Scenarios**:

1. **Given** an authenticated Architect submits a recommendation request for a stored design, **When** the request is accepted, **Then** the API responds within 2 seconds with an operation handle carrying a unique ID and a `pending` status
2. **Given** an operation handle, **When** the caller polls the status endpoint, **Then** the response reflects the current operation state (`pending`, `running`, `completed`, or `failed`) and — when completed — includes a result reference
3. **Given** a recommendation operation that has failed, **When** the status is polled, **Then** the response includes a human-readable error description and no partial result is committed to the model

---

### User Story 4 - Confirm Consequential Actions Explicitly (Priority: P2)

An architect receives a recommendation and decides to accept it. Before any change is committed to the design, the API requires them to submit an explicit confirmation carrying the operation ID and their stated intent. The confirmation and its actor are recorded in the audit trail.

**Why this priority**: Consequential confirmation is the primary ART-VIII implementation. Without it, AI-derived changes can be silently committed — undermining architect accountability. Builds on US2 (auth) and US3 (async).

**Independent Test**: Complete an async operation; attempt to accept without the confirmation payload and assert rejection; submit with the confirmation payload and assert the design version is updated and the audit trail carries the actor and action. Tests the confirmation gate independently.

**Acceptance Scenarios**:

1. **Given** a completed recommendation operation, **When** the architect submits an acceptance without the required confirmation payload, **Then** the API rejects the request with a clear error; no change is committed
2. **Given** a completed recommendation operation, **When** the architect submits an acceptance with the confirmation payload (operation ID + stated intent), **Then** the change is committed to the design and an audit entry is written recording the actor, action, and timestamp
3. **Given** a confirmation payload for an operation ID that has already been used, **When** it is submitted again, **Then** the API rejects it as already-confirmed; no duplicate write occurs

---

### User Story 5 - Consume a Generated API Contract (Priority: P3)

A developer or integration tool fetches the API contract to understand available endpoints, payload shapes, and error schemas. The contract reflects the current state of the API and was produced from the typed handlers — not hand-authored.

**Why this priority**: A generated contract is a governance and integration prerequisite but not a blocking dependency for the first four stories; other teams can begin integrating once the first four stories are stable.

**Independent Test**: Fetch the contract endpoint; assert the response is a valid OpenAPI document; assert it contains at least one defined schema referencing the canonical design model; assert the document was generated (carry a generation timestamp) — independently of any specific endpoint behavior.

**Acceptance Scenarios**:

1. **Given** the API is running, **When** a caller fetches the contract endpoint (unauthenticated), **Then** the response is a valid OpenAPI document reflecting all live endpoints
2. **Given** a handler is added or modified, **When** the API is rebuilt, **Then** the contract endpoint reflects the change without any manual editing of the contract document
3. **Given** the contract document, **When** it is validated against the OpenAPI specification standard, **Then** it passes validation without errors

---

### Edge Cases

- What happens when a polling client uses an expired or unknown operation ID?
- How does the API behave when the backing store (ADP-SPEC-002) is unavailable?
- What happens when an operation completes but the result write to the store fails?
- How does the confirmation step behave if the underlying operation result has expired from the operation store?
- What is the behavior when a Viewer requests a design they do not have access to — do they receive 403 or 404?
- How does the API handle a request body larger than the configured maximum?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The API MUST expose create, read, update, and list operations for the canonical model; every request payload MUST be validated against the published schema before any store write; validation failures MUST return a structured error describing each violation without partially applying the request
- **FR-002**: The API MUST expose intake, recommendation request, validation request, and view-generation operations; each MUST be independently callable via a typed endpoint
- **FR-003**: Recommendation and validation operations MUST be handled asynchronously; every accepted operation request MUST return a typed operation handle within 2 seconds; callers MUST be able to poll status and retrieve results without blocking
- **FR-004**: Every request MUST be authenticated via the organizational identity provider before any processing; every mutation MUST be authorized against the caller's persona role before any store interaction; unauthorized requests MUST be rejected with role-specific error context
- **FR-005**: Consequential actions (accepting a recommendation, overriding a verdict, triggering an export) MUST require a distinct confirmation request carrying the operation ID and the caller's stated intent; confirmation MUST be single-use; every accepted confirmation MUST write an audit entry attributable to the confirmed principal
- **FR-006**: The API MUST serve a generated OpenAPI contract reflecting its current endpoint surface; the contract MUST be produced from the typed handler definitions and MUST NOT be hand-maintained
- **FR-007**: Every request MUST emit a structured log entry carrying a correlation ID; AI operation spans MUST carry inputs, outputs, cost, and latency; no sensitive data or credentials MUST appear in any log or telemetry record

### Non-Functional Requirements

- **NFR-001**: Non-AI endpoints (CRUD, status polling, contract) MUST respond within 1 second under normal operating conditions for typical payloads (designs with ≤ 500 entities)
- **NFR-002**: No personal data, design content, authentication tokens, or sensitive identifiers MUST appear in URL paths or query string parameters; only stable, opaque resource identifiers are permitted in path segments

### Key Entities

- **OperationHandle**: The typed response to an async operation request; carries a unique operation ID, a status (`pending`, `running`, `completed`, `failed`), a result reference (when completed), and an error description (when failed)
- **ConfirmationPayload**: The required request body for a consequential action; carries the operation ID to confirm and the caller's stated intent (a brief human-readable string)
- **ApiPrincipal**: The resolved identity of an authenticated caller; carries the principal ID, persona role, and token expiry; MUST NOT be logged or embedded in response bodies
- **ApiError**: The structured error response shape; carries a machine-readable error code, a human-readable message, and an optional list of field-level violations

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of requests with invalid payloads are rejected with a structured error identifying the specific violation(s); zero partial writes occur on validation failure; verified by contract tests covering all request schemas
- **SC-002**: 100% of unauthenticated requests receive a 401 response; 100% of requests from under-privileged personas receive a 403 response before any store interaction; verified by auth integration tests
- **SC-003**: 100% of recommendation and validation operation requests receive an `OperationHandle` within 1 second of submission; operation submission is treated as a non-AI endpoint latency target because it stores a handle and checks design existence without calling AI; callers can poll status until the operation reaches a terminal state; verified by async operation tests
- **SC-004**: Zero consequential mutations (recommendation acceptances, verdict overrides, exports) occur without a recorded audit entry carrying the actor, action, and timestamp; verified by audit integrity tests
- **SC-005**: The served OpenAPI contract passes validation against the OpenAPI standard on every build; no endpoint exists in the served contract that is not covered by at least one contract test; verified by CI gate
- **SC-006**: Zero instances of personal data, tokens, or sensitive content appear in API URLs, query strings, or log output; verified by automated URL and log scanning in CI

## Assumptions

- **Async transport is polling-only for v1.** The open question on SSE/webhooks is resolved as: the API exposes status polling endpoints only; callers poll at their own cadence. Server-Sent Events (SSE) and webhooks are deferred to v1.1 when consuming client patterns are better understood. Polling at 2–5 second intervals is acceptable for the recommendation and validation latencies expected in v1.
- Authentication delegation to the organizational OIDC provider is assumed; the API validates OIDC tokens but does not issue, store, or rotate them. Token lifecycle management is out of scope.
- Persona roles are defined in ADP-SPEC-004; this spec assumes at minimum two roles: **Architect** (read + write + submit) and **Viewer** (read only). Additional roles (e.g., Reviewer, Admin) are defined in ADP-SPEC-004.
- "Sensitive data" in the context of NFR-002 means: design content, entity names or descriptions, authentication tokens, actor email addresses, and IP addresses. Stable, opaque design IDs and operation IDs are acceptable in path segments.
- The API serves the OpenAPI contract at an unauthenticated endpoint (`/openapi.json` or equivalent) since API documentation does not expose sensitive design data.
- Operation results (from async AI work) are stored in a transient operation store separate from the canonical design store; results expire after a configurable retention period (default 24 hours). Once accepted and committed, they enter the canonical store permanently.
- The API is the authorization boundary; the ADP-SPEC-002 store is not — callers do not interact with the store directly.
- The audit actor for all mutations is always the authenticated `ApiPrincipal.principal_id` from the validated JWT; no caller-supplied actor override is permitted (ART-IX / QG-13).
- FR-007 is satisfied for v1 by per-request structured logging (ART-VI middleware) and the `OperationSpan` stub model; full telemetry pipeline integration against ADP-SPEC-012 is deferred until ADP-SPEC-012 is ratified.

## Out of Scope

- Web workspace UI (ADP-SPEC-009)
- AI recommendation logic (ADP-SPEC-006), validation logic (ADP-SPEC-007), view generation logic (ADP-SPEC-008)
- Identity provider setup, token issuance, and token rotation
- Multi-tenant data isolation beyond persona-based authorization
- Server-Sent Events or webhook delivery for async operation completion (deferred to v1.1)
- Rate limiting and DDoS protection (infrastructure concern, not application-layer for v1)
- Export format implementations (ADP-SPEC-011)
- Telemetry pipeline and dashboards (ADP-SPEC-012)
