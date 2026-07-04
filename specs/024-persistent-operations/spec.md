# Feature Specification: Persistent Operation Store

**Feature Branch**: `024-persistent-operations`
**Created**: 2026-07-03
**Status**: Draft
**Depends on**: ADP-SPEC-023 (Internal Architecture Consolidation)

## Context

ADP has two long-running asynchronous operations: requirements extraction (intake) and architecture recommendation generation. Both are currently tracked in module-level Python dicts (`_intake_store` and `_recommend_store`). This was explicitly deferred in the original specs with the note "Redis deferred".

The consequence: every process restart silently discards all in-flight and completed operations. A client polling `GET /intake/{op_id}` after a uvicorn restart gets a 404. Multiple uvicorn workers cannot share operation state — load balancing between two workers means a client that POSTed to worker A might poll worker B and get nothing back. And the TTL is "not enforced in v1" (comment in the code), meaning the stores grow unbounded.

This spec replaces both stores with a single `operations` table in PostgreSQL. The polling API is unchanged — clients see the same 202 → polling → completed flow. The difference is durability and multi-worker correctness.

## Constitutional Articles Touched

- **ART-I** — Spec-Driven Development: always applies
- **ART-IV** — Test-Driven Development: always applies; operation state transitions must be tested
- **ART-II** — Model is Source of Truth: `operations` table stores transient pipeline state, not design data; the canonical model in `architecture_descriptions` is unchanged
- **ART-IX** — Audit Trail: operation completion already writes audit entries; this spec must not break that flow

## Threat Model

**Assets at risk**: In-flight operation state (extraction results, recommendation options). Loss of this state is annoying (user must retry) but not a data integrity issue — the canonical design model in `architecture_descriptions` is untouched.

**Trust boundaries crossed**: FastAPI workers → PostgreSQL (same boundary as today, no new trust boundary).

**Abuse cases**:
- Orphaned operations never cleaned up → table grows unbounded: mitigated by TTL enforcement on INSERT and a cleanup background task that runs every 10 minutes.
- Concurrent accept/reject on the same option from two workers: mitigated by using `UPDATE ... WHERE status = 'pending' RETURNING *` (optimistic concurrency) — only one update succeeds.

**Residual risk**: If PostgreSQL is unavailable, operation submission fails immediately (rather than the current behaviour of succeeding then running in-process). This is the correct behaviour for a production system — fail fast on infrastructure unavailability rather than silently accepting requests that cannot be persisted. Accepted.

## User Scenarios & Testing

### User Story 1 — Operations Survive Process Restart (Priority: P1)

An architect submits a recommendation request and the server is restarted before it completes (e.g. a deployment). When the server comes back up, polling the operation ID returns the operation's last known state — not a 404. If the operation was in-progress when the server restarted, it transitions to `failed` with an appropriate message on next poll.

**Why this priority**: This is the core correctness property that makes ADP suitable for real use.

**Independent Test**: Submit an intake operation; stop the server; restart; poll the operation ID; assert 200 with `status: "completed"` or `status: "failed"` — never 404.

**Acceptance Scenarios**:

1. **Given** an extraction operation is completed, **When** the server restarts, **Then** `GET /intake/{op_id}` returns the completed operation with its proposals.
2. **Given** an operation is `running` when the server restarts, **Then** on next poll the operation's status is `failed` with `error_description: "server restarted during processing"`.
3. **Given** an operation has been completed for longer than 24 hours, **Then** it is no longer returned and `GET /intake/{op_id}` returns 404 (expired, not an error).

---

### User Story 2 — Operations Work Across Multiple Workers (Priority: P2)

ADP is deployed with two uvicorn workers. An architect POSTs an intake request to worker A. They poll the result via worker B (load balancer round-robin). The result is returned correctly.

**Why this priority**: This is the direct enabler for horizontal scaling and production HA deployment.

**Independent Test**: With two in-process workers simulated by two separate FastAPI test clients sharing one database, submit on client A and poll on client B; assert correct result.

**Acceptance Scenarios**:

1. **Given** two workers share the same PostgreSQL database, **When** a request is submitted on one worker and polled on another, **Then** the correct operation status and result data is returned.
2. **Given** two workers attempt to mark the same option as accepted concurrently, **Then** exactly one succeeds with 200 and the other receives 409.

---

### User Story 3 — TTL Prevents Unbounded Growth (Priority: P3)

Operations older than 24 hours are automatically cleaned up from the database. The knowledge base items written on accept/reject are not affected — they are permanent records.

**Acceptance Scenarios**:

1. **Given** an operation was created 25 hours ago, **When** the cleanup task runs, **Then** the operation row is deleted from the `operations` table.
2. **Given** cleanup runs, **Then** `knowledge_items` and `architecture_descriptions` rows are not affected.

---

### Edge Cases

- Operation ID that never existed: returns 404 (same as today).
- Operation result payload exceeds JSONB column: truncate large LLM outputs to 1MB before storing; log a warning.
- Database unavailable on operation submit: return 503 immediately; do not queue the request.
- Concurrent accept of the same option: first succeeds, second gets 409 (same as today — optimistic concurrency via `UPDATE ... WHERE status='pending'`).

## Requirements

### Functional Requirements

**Schema (FR-001 to FR-003)**

- **FR-001**: A new Alembic migration MUST add an `operations` table with columns: `id` (text PK), `type` (text — "intake" or "recommend"), `design_id` (text), `status` (text — pending/running/completed/failed), `payload` (JSONB — stores input params, results, options), `actor` (text), `error` (text, nullable), `created_at` (timestamptz), `updated_at` (timestamptz), `expires_at` (timestamptz — `created_at + 24h`).
- **FR-002**: A GIN index on `payload` and a B-tree index on `(design_id, type, status)` and `expires_at` MUST be created to support polling queries efficiently.
- **FR-003**: An `OperationStore` class MUST be added to `src/adp/store/operations.py` with async methods: `create(op_id, type, design_id, actor, initial_payload) -> None`, `get(op_id) -> dict | None`, `update(op_id, status, payload_patch) -> None`, `delete_expired() -> int`.

**Intake Router (FR-004 to FR-006)**

- **FR-004**: `_intake_store: dict` MUST be removed from `src/adp/api/routers/intake.py`. All reads and writes MUST go through `OperationStore`.
- **FR-005**: The intake background task MUST write its results (extracted proposals, confirmed requirements) back to the `operations` table via `OperationStore.update()` rather than writing to the in-process dict.
- **FR-006**: On server startup, any operations with `status = "running"` MUST be transitioned to `status = "failed"` with `error = "server restarted during processing"` — this prevents stale "running" operations from appearing indefinitely after a crash.

**Recommend Router (FR-007 to FR-009)**

- **FR-007**: `_recommend_store: dict` MUST be removed from `src/adp/api/routers/recommend.py`. All reads and writes MUST go through `OperationStore`.
- **FR-008**: The accept and reject endpoints MUST use `UPDATE operations SET payload = jsonb_set(payload, ...) WHERE id = $1 AND payload->>'status' = 'pending' RETURNING id` to implement optimistic concurrency — ensuring exactly-once status transitions even under concurrent requests.
- **FR-009**: The `RecommendationOrchestrator` and `ExtractionOrchestrator` MUST accept `OperationStore` instead of a raw `dict` as their operation store parameter. Existing internal interfaces must continue to work.

**Cleanup (FR-010)**

- **FR-010**: A FastAPI startup event handler MUST register a repeating background coroutine (every 10 minutes) that calls `OperationStore.delete_expired()` and logs the count of deleted rows.

**API Contract (FR-011)**

- **FR-011**: The request/response schema for all intake and recommend endpoints MUST be unchanged. Clients polling operation IDs see identical JSON shapes before and after this migration.

### Key Entities

- **Operation**: id, type, design_id, status, payload (JSONB — contains type-specific data such as proposals for intake, options for recommend), actor, error, created_at, updated_at, expires_at

## Success Criteria

- **SC-001**: After a server restart, previously completed operations are retrievable with correct data — zero 404s for completed operations.
- **SC-002**: Two workers sharing one database return consistent operation state — no split-brain.
- **SC-003**: `SELECT count(*) FROM operations WHERE expires_at < now()` returns 0 within 10 minutes of operations expiring.
- **SC-004**: The intake and recommend polling APIs return responses within the same latency budget as before (< 50ms overhead for DB read vs in-process dict read).
- **SC-005**: All 437+ existing tests pass (adjusted for new import paths from ADP-SPEC-023).

## Assumptions

- ADP-SPEC-023 (Internal Architecture Consolidation) is complete before this spec is implemented — the single shared DB pool in `adp.api.deps` is a prerequisite.
- The `operations` table stores transient pipeline state only. It does not replace the canonical model in `architecture_descriptions`. Audit entries remain in `architecture_descriptions.audit_log` (JSONB).
- Option/proposal data in `payload` (JSONB) is a convenience cache. The source of truth for accepted elements/requirements is the `architecture_descriptions` table. If payload is lost, the design model is unaffected.
- The JSONB payload limit of 1MB is sufficient for all current pipeline outputs. If a recommendation pipeline returns > 1MB of options, the payload is truncated and flagged.
