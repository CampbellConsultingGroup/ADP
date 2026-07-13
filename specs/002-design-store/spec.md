# Feature Specification: Persistence & Design Store

**Feature Branch**: `002-design-store`  
**Created**: 2026-06-27  
**Status**: Draft  
**Input**: User description: "ADP-SPEC-002 — Persistence & Design Store"

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: always applies; all store behavior derives from this spec
- **ART-II** — The Model is the Single Source of Truth: the canonical model persisted here must remain the authoritative record; derived views or caches MUST be generated from it, not stored alongside it as peers
- **ART-III** — Everything is Machine-Readable: all persisted artifacts MUST conform to the published schema; the persistence interface exposes typed contracts, not raw blobs
- **ART-IV** — Test-Driven Development: always applies; every store operation requires a test that exercises the acceptance criteria before implementation
- **ART-V** — Security by Design: in scope; design data is sensitive organizational intellectual property; audit trail must be tamper-evident
- **ART-VII** — Grounded AI Only: not in scope; no AI outputs are written or read by this spec
- **ART-IX** — Provenance and Auditability: the central concern; this spec is the primary implementation of the append-only audit trail and of mutation provenance recording
- **ART-XI** — Traceability End to End: in scope; the traceability query capability (FR-005) serves the requirement that every element traces to the requirement it satisfies
- **ART-XIII** — Typed Contracts Everywhere: the store interface MUST accept and return typed models (ArchitectureDescription); raw dict or string payloads are prohibited at the store boundary
- **ART-XIV** — Reproducible, Drift-Free Builds: persisted artifacts MUST validate against the live schema on write; a schema change that makes a stored artifact invalid constitutes drift (NFR-002)

## Threat Model *(mandatory — ART-V)*

This feature handles organizational architecture decisions — sensitive intellectual property. Risk is moderate: a compromised store could expose design decisions or allow undetected tampering with the audit record.

**Assets at risk**: Architecture descriptions (design decisions, requirements, solution options, verdicts); the audit trail that provides accountability for those decisions.

**Trust boundaries crossed**: Application layer → persistence layer → durable store.

**Abuse cases**:
- **Audit trail tampering**: An insider attempts to delete or modify an audit entry to conceal a design change → Mitigation: FR-004 prohibits all update/delete paths on audit entries at the application layer; the store enforces this structurally, not just through policy
- **Version overwrite**: A caller overwrites an existing design version rather than creating a new one → Mitigation: FR-002 requires immutability of persisted versions; the store must reject in-place updates to versioned records
- **Schema bypass on write**: A caller persists an artifact that does not conform to the published schema, injecting unvalidated data → Mitigation: FR-006 requires schema validation before any write commits
- **Partial mutation without audit**: A transaction commits the design change but not the audit entry, leaving a gap in the audit trail → Mitigation: FR-003 requires atomicity — audit entry and mutation commit together or not at all

**Residual risk**: A database administrator with direct SQL access could bypass application-layer controls. Accepted for v1; physical-layer access control is a deployment/infrastructure concern outside this spec's scope.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Save and Retrieve a Design (Priority: P1)

An architect completes a design session and saves their `ArchitectureDescription`. Later, they or a colleague retrieves it and expects to work with the identical model.

**Why this priority**: Durable, lossless storage is the foundational contract — all other capabilities depend on it. Without this, nothing else is meaningful.

**Independent Test**: Save any valid `ArchitectureDescription`, retrieve it by ID, assert the result equals the saved model. Delivers the core storage contract independently.

**Acceptance Scenarios**:

1. **Given** a valid `ArchitectureDescription`, **When** it is persisted, **Then** it is retrievable by its design ID and the returned model MUST be structurally identical to what was saved (all fields equal), and MUST validate against the published schema
2. **Given** a persisted design, **When** it is retrieved, **Then** it validates against the published schema without errors
3. **Given** an `ArchitectureDescription` that does not conform to the published schema, **When** a save is attempted, **Then** the save is rejected with a schema validation error and nothing is written

---

### User Story 2 - Atomic Audit Trail on Every Mutation (Priority: P1)

Any change to a stored design — adding an element, accepting a recommendation, recording a verdict — must produce an audit entry that commits atomically with the change.

**Why this priority**: The audit trail is non-negotiable for governance. A design change with no audit record violates ART-IX and undermines the platform's accountability guarantee.

**Independent Test**: Perform any mutation on a stored design; query the audit log immediately after; assert the entry is present with the correct actor, action, and timestamp. Confirm that simulating a mid-transaction failure leaves neither the mutation nor the audit entry committed.

**Acceptance Scenarios**:

1. **Given** a stored design, **When** a mutation is applied, **Then** an audit entry recording the actor, action, affected entity, and timestamp is written in the same transaction
2. **Given** a transaction that would commit a mutation, **When** the audit entry write fails, **Then** the entire transaction is rolled back and neither the mutation nor the audit entry persists
3. **Given** a committed audit entry, **When** any application path attempts to update or delete it, **Then** the operation is rejected; the entry remains unchanged

---

### User Story 3 - Immutable Version History (Priority: P2)

An architect modifies a design that was previously saved. The prior version must remain accessible so that reviewers can compare what changed and when.

**Why this priority**: Version history enables review, rollback, and accountability. It builds on US1 (storage) and is needed before meaningful governance workflows can run.

**Independent Test**: Save a design, modify and re-save it, retrieve both versions by version identifier; assert the first version is unchanged and the second reflects the modification.

**Acceptance Scenarios**:

1. **Given** an existing stored design, **When** it is modified and saved, **Then** a new version is created and the prior version remains retrievable unchanged
2. **Given** multiple versions of a design, **When** a specific version is requested by version identifier, **Then** the exact state of that version is returned
3. **Given** a prior design version, **When** any application path attempts to modify it, **Then** the operation is rejected; only a new version can be created

---

### User Story 4 - Traceability Query (Priority: P2)

A reviewer asks the system "which elements in design D satisfy requirement REQ-003?" and expects an answer without manually scanning prose.

**Why this priority**: Traceability queries are the primary governance read path; without them, the platform cannot automate compliance checking or produce audit reports.

**Independent Test**: Store a design with known element-to-requirement links. Query for elements satisfying a specific requirement; assert only the correct elements are returned. Query for a requirement with no satisfying elements; assert an empty result (not an error).

**Acceptance Scenarios**:

1. **Given** a stored design where two elements satisfy `REQ-003`, **When** a traceability query is run for `REQ-003`, **Then** exactly those two elements are returned
2. **Given** a stored design, **When** queried for all requirements with no satisfying elements, **Then** the result accurately identifies the orphaned requirements
3. **Given** a stored design, **When** queried for the full verdict chain of a SolutionOption, **Then** the linked Requirement, Element satisfies, and Verdict are all returned in one response

---

### Edge Cases

- What happens when a save is attempted for a design whose ID already exists at the current (latest) version?
- How does the store behave when the schema version of a stored artifact is older than the current live schema?
- What happens when a traceability query references a design ID that does not exist?
- How does the store handle concurrent mutations to the same design from two simultaneous actors?
- What happens when an audit entry references an entity ID that does not exist in the design at the time of writing?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The store MUST persist and retrieve the full canonical `ArchitectureDescription` with transactional integrity — a write either fully succeeds or fully fails; partial writes are not permitted
- **FR-002**: The store MUST retain every saved version of a design immutably; prior versions MUST remain retrievable by version identifier; no application path may overwrite or delete a persisted version
- **FR-003**: Every mutation to a stored design MUST write an audit entry atomically in the same transaction; if the audit entry cannot be written, the mutation MUST NOT commit
- **FR-004**: Audit entries MUST NOT be modifiable or deletable through any application path; the store MUST structurally enforce this, not merely by policy
- **FR-005**: The store MUST support traceability queries over `satisfies`, `provenance`, relationships, and verdicts without requiring full-text or prose scanning
- **FR-006**: The store MUST validate every artifact against the published schema before writing; artifacts that fail schema validation MUST be rejected with a descriptive error

### Non-Functional Requirements

- **NFR-001**: A single-design read for a typical design (≤ 500 entities) MUST complete in under 1 second under normal operating conditions
- **NFR-002**: The store MUST guarantee durability of committed designs and audit entries — a committed write survives process crash, restart, and power loss; a stored artifact that no longer validates against the current schema must be detectable (not silently accepted as valid)

### Key Entities

- **DesignRecord**: The persisted envelope for a single `ArchitectureDescription`; carries a stable design ID, a version sequence number, the schema version at time of write, the serialized model, and created/updated timestamps
- **DesignVersion**: An immutable snapshot of a `DesignRecord` at a specific version; once written, no field may change
- **StoredAuditEntry**: An append-only record of a single mutation; carries actor, action, affected entity, summary, timestamp, origin, and a reference to the design ID and version it was recorded against; structurally non-deletable

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A saved design is retrievable with no data loss — every field of the retrieved model is identical to what was submitted; verified by automated round-trip equality tests
- **SC-002**: 100% of committed mutations have a corresponding audit entry; zero committed mutations with no audit record; verified by integration tests that confirm atomicity
- **SC-003**: All prior versions of any design remain retrievable indefinitely; no version is ever overwritten; verified by versioning tests asserting version count and immutability
- **SC-004**: Traceability queries return correct, complete results without scanning prose fields; verified by integration tests with known entity-to-requirement mappings
- **SC-005**: Single-design reads complete in under 1 second for designs with up to 500 entities under single-user load; verified by performance tests

## Assumptions

- Design versions are retained indefinitely with no automatic purge or archival. The open question on retention policy (OQ-02 from the source description) is resolved as: **retain all versions forever** — appropriate for a governance and audit tool where ART-IX prohibits deletion of provenance records. Storage tiering (e.g., moving old versions to cheaper storage) is deferred and out of scope for v1.
- The store is not the primary authentication or authorization boundary; callers are assumed to have been authenticated and authorized before reaching the store interface. Role-based access enforcement (which architects can read/write which designs) is out of scope and deferred to the API layer (ADP-SPEC-003).
- Concurrent mutation conflicts (two actors modifying the same design simultaneously) are resolved by optimistic concurrency — the second writer receives a conflict error and must re-read and retry; last-write-wins is not acceptable.
- A "typical design" for performance purposes (SC-005) is defined as ≤ 500 entities across all collections in one `ArchitectureDescription`.
- Schema migration for stored artifacts (when the published schema version changes) is handled as a deferred concern; v1 stores the schema version at write time and exposes it on read so callers can detect version mismatches; automated migration is out of scope.

## Out of Scope

- API exposure of the store (deferred to ADP-SPEC-003)
- Role-based access control and multi-tenant isolation (deferred to ADP-SPEC-003)
- Vector knowledge index (ADP-SPEC-005)
- Export to version control systems (ADP-SPEC-011)
- Automated schema migration for stored artifacts (detecting stored artifacts with a mismatched schema version is in scope as a read-time warning; automated migration of their content is not)
- Handling of schema version mismatches beyond read-time detection (migration tooling, backfill jobs, and explicit upgrade paths are deferred)
- Storage tiering or archival of old design versions
- Full-text search or semantic search over design content
