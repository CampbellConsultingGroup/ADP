# Research: Persistence & Design Store

**Branch**: `002-design-store` | **Date**: 2026-06-27  
**Phase**: 0 — Decisions and rationale before design begins

## Decision 1: ORM and Driver Choice

**Decision**: SQLAlchemy 2.x (async) with the `asyncpg` driver.

**Rationale**: SQLAlchemy 2's async API integrates cleanly with Pydantic v2 (both use Python's modern type system), provides Alembic migration support out of the box, and keeps the ADP stack Python-native. The async API allows non-blocking I/O under future load. `asyncpg` is the fastest native async PostgreSQL driver for Python and is the recommended companion to SQLAlchemy 2 async.

**Alternatives considered**:
- Raw asyncpg SQL — rejected: no migration framework; requires hand-written schema management; harder to test
- psycopg3 — viable but `asyncpg` has broader production adoption with SQLAlchemy 2 async; deferred as an option if asyncpg proves problematic
- Tortoise ORM — rejected: smaller community; less mature Alembic-equivalent; not aligned with SQLAlchemy ecosystem

---

## Decision 2: Content Storage Strategy — JSONB Blob vs. Normalized Tables

**Decision**: Store the full `ArchitectureDescription` as a validated JSONB blob in `design_versions.content`, with targeted GIN-indexed JSONB path expressions on the `elements` and `options` arrays to support traceability queries.

**Rationale**: The `ArchitectureDescription` is a governed, schema-versioned aggregate root (ART-II). Normalizing it into relational tables would require keeping the relational schema in sync with every model change — creating a second source of truth and violating ART-II. JSONB with GIN indexing on the paths used in traceability queries (`$.elements[*].satisfies`, `$.elements[*].id`) satisfies NFR-001 (sub-second reads) without normalization. PostgreSQL JSONB path queries on GIN indexes are sub-millisecond for typical design sizes.

**Alternatives considered**:
- Full normalization (elements/requirements/relationships tables) — rejected: creates a second schema that must track `architecture-description.schema.json`; violates ART-II; significant migration overhead on every model change
- Store as TEXT/blob with no indexing — rejected: cannot satisfy FR-005 (traceability queries without prose scanning) without application-layer filtering, which is O(n) on the full design content

---

## Decision 3: Immutable Versioning Schema

**Decision**: Two tables — `designs` (mutable pointer) and `design_versions` (immutable per-version record):
- `designs(id, current_version, title, created_at)` — one row per design; `current_version` is the only mutable field
- `design_versions(design_id, version_num, schema_version, content JSONB, created_at, created_by)` — composite PK; once inserted, no row is ever updated or deleted

**Rationale**: The two-table pattern is the canonical append-only versioning approach. It satisfies FR-002 (immutable prior versions) structurally — no UPDATE or DELETE is ever issued on `design_versions`. The `designs` table provides a cheap "latest version" pointer without a MAX(version_num) query on every read.

**Alternatives considered**:
- Single table with `is_latest` flag — rejected: requires an UPDATE to flip `is_latest` when a new version is added, which is a mutation on existing rows; harder to enforce immutability
- Event sourcing / event log — appropriate for future but overkill for v1; increases read complexity; deferred

---

## Decision 4: Optimistic Concurrency Control Strategy

**Decision**: The `save()` method accepts an optional `expected_version: int | None` parameter. When provided, the INSERT into `design_versions` is preceded by a check that `designs.current_version == expected_version`; if not, a `ConcurrencyConflictError` is raised. When `None` (first save), no check is needed.

**Rationale**: Optimistic concurrency avoids locking while making conflicts explicit. The architecture governance context means concurrent edits to the same design are rare; conflict rates are expected to be very low. The caller (future API layer) handles retries.

**Alternatives considered**:
- Pessimistic locking (SELECT FOR UPDATE) — rejected: blocks concurrent readers; unnecessary for low-conflict governance workflows
- Last-write-wins — explicitly rejected by the spec: "last-write-wins is not acceptable" (Assumptions section)

---

## Decision 5: Audit Entry Enforcement — Application Layer + Database Trigger

**Decision**: Two-layer enforcement:
1. **Application layer**: `DesignStore` has no `delete_audit_entry()` or `update_audit_entry()` method. The `StoredAuditEntry` ORM model has no `.delete()` pathway.
2. **Database layer**: A PostgreSQL trigger on `audit_entries` raises an exception on any UPDATE or DELETE statement, regardless of caller.

**Rationale**: FR-004 requires structural enforcement, not policy. Application-layer-only enforcement can be bypassed by direct SQL or future code. The database trigger provides a hard guarantee that survives API changes, direct psql connections, and future developers.

**Alternatives considered**:
- Application-layer-only enforcement — rejected: can be bypassed; violates FR-004's "structural" requirement
- PostgreSQL Row-Level Security (RLS) — equally valid but more complex to configure; trigger is simpler and more visible in the migration

---

## Decision 6: Traceability Query Implementation

**Decision**: Three targeted query functions backed by JSONB path expressions on GIN-indexed columns:
1. `query_satisfies(design_id, requirement_id)` — extracts elements from `content` where `satisfies` array contains the requirement ID, using `jsonb_path_query`
2. `query_orphan_requirements(design_id)` — returns requirements whose ID appears in no element's or option's `satisfies` array
3. `query_verdict_chain(design_id, option_id)` — extracts the option, its satisfies requirements, the verdict on it, and the elements that also satisfy those requirements

**Rationale**: All three queries operate on the JSONB blob with indexed path expressions — no full-text scan, satisfying FR-005. GIN indexes on the `content` JSONB column with targeted paths keep query times sub-100ms for typical designs.

---

## Decision 7: Test Infrastructure — testcontainers

**Decision**: Use `testcontainers[postgres]` to spin up a real PostgreSQL instance per test session. Each test function starts within a transaction that is rolled back after the test, keeping tests isolated without database cleanup overhead.

**Rationale**: The constitution (ART-IV) requires deterministic tests. The store's correctness guarantees (transactional integrity, trigger enforcement, JSONB indexing) can only be verified against a real database. Mocking SQLAlchemy/asyncpg would not validate the trigger, the schema, or the JSONB queries. `testcontainers` is the Python-idiomatic way to do this in CI.

**Alternatives considered**:
- SQLite for testing — rejected: SQLite does not support JSONB path expressions, GIN indexes, or BEFORE/AFTER triggers in the same semantics as PostgreSQL
- Mocking the database layer — rejected: cannot validate trigger behavior, schema constraints, or JSONB queries; incompatible with the project's "no mocked database" stance

---

## Decision 8: ART-VI Logging Strategy

**Decision**: Each store operation emits a structured log entry using Python's standard `logging` module with a JSON formatter. Log entries carry: `operation` (save/get/query), `design_id`, `version_num` (where applicable), `actor` (for mutations), `duration_ms`, and `error` (on failure). Sensitive content (the full `ArchitectureDescription` JSON) is never logged.

**Rationale**: ART-VI requires structured logs with correlation IDs on all code paths. The store is a runtime service; without logs, failures and performance issues are invisible. Logging metadata (not content) avoids leaking design IP into log aggregators.
