# Feature Specification: Canonical Data Model & Schema Generation

**Feature Branch**: `001-canonical-data-model`  
**Created**: 2026-06-27  
**Status**: Draft  
**Input**: User description: "ADP-SPEC-001 — Canonical Data Model & Schema Generation"

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: always applies; this spec is the foundation document for all downstream specs
- **ART-IV** — Test-Driven Development: always applies; every entity and the schema generator require automated test coverage
- **ART-II** — Source of Truth: the canonical model IS the single source of truth for all ADP designs
- **ART-III** — Machine-Readable: the emitted JSON Schema is the machine-readable contract consumed by every downstream spec
- **ART-V** — Security/Threat Model: in scope; model must reject unknown fields to prevent silent data corruption
- **ART-VII** — AI Grounding: not in scope for this feature
- **ART-XIII** — Typed Contracts: this feature defines the typed entity contracts all other specs depend on
- **ART-XIV** — Drift-Free: the generator's `--check` mode in CI enforces this article
- **ART-XV** — Governed Evolution: schema versioning with minor/major bump rules implements this article

## Threat Model *(mandatory — ART-V)*

This is an internal developer tooling feature with no external user surface. Risk is low but non-trivial: a corrupted or silently-extended model could propagate invalid data to downstream consumers without detection.

**Assets at risk**: Architecture description data (design decisions, requirements, recommendations, verdicts); the published JSON Schema consumed by all other ADP features.

**Trust boundaries crossed**: Developer working tree → CI pipeline → committed schema artifact.

**Abuse cases**:
- **Accidental field extension**: A developer adds an undocumented field to an entity; model silently accepts it and schema diverges from intent → Mitigation: strict unknown-field rejection on all entities (FR-002)
- **Schema drift**: Model changes without regenerating the schema; downstream consumers operate against a stale contract → Mitigation: check mode in CI exits non-zero on any drift (FR-005)
- **Broken references**: An element references a non-existent requirement ID; the design appears valid but is referentially broken → Mitigation: reference validation enforced at model load time (FR-007)

**Residual risk**: A developer with repository write access could bypass CI checks — accepted, as this is an internal development tool governed by standard source-control access controls.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Author a Valid Design (Priority: P1)

An architect creates an `ArchitectureDescription` containing requirements, elements, relationships, and a recommendation. They serialize it to JSON and expect to load it back identically.

**Why this priority**: Round-trip fidelity is the core contract — without it, the model cannot serve as a reliable source of truth for any downstream consumer.

**Independent Test**: Can be tested by constructing any valid `ArchitectureDescription`, serializing it to JSON, and deserializing it — delivers the core model contract independently of all other stories.

**Acceptance Scenarios**:

1. **Given** a service holds a valid `ArchitectureDescription`, **When** it is serialized to JSON, **Then** the output validates against the published schema without errors
2. **Given** valid serialized JSON, **When** it is deserialized, **Then** the result is identical to the original model (lossless round-trip)

---

### User Story 2 - Reject Malformed Data (Priority: P1)

A downstream consumer receives a JSON artifact with an unrecognized field or an invalid identifier format and attempts to load it into the model.

**Why this priority**: Silent data corruption is worse than a hard failure; strict rejection is a foundational safety invariant for every consumer of the model.

**Independent Test**: Can be tested by loading a JSON artifact with an extra field or malformed identifier — delivers the safety guarantee independently of all other stories.

**Acceptance Scenarios**:

1. **Given** a JSON artifact containing an unknown field on any entity, **When** it is loaded into the model, **Then** loading fails with a clear validation error naming the unexpected field
2. **Given** a JSON artifact with a malformed identifier (e.g., `REQ-ABC` instead of `REQ-001`), **When** it is loaded, **Then** loading fails with a format validation error

---

### User Story 3 - Detect Schema Drift in CI (Priority: P2)

A developer modifies the model but forgets to regenerate the committed JSON Schema before pushing.

**Why this priority**: Drift detection protects the contract integrity promise across the entire ADP system; without it, ART-XIV is unenforced.

**Independent Test**: Can be tested by modifying a model entity, running the generator in check mode, and confirming a non-zero exit — independently demonstrates the drift gate.

**Acceptance Scenarios**:

1. **Given** a model change has been made without regenerating the committed schema, **When** the generator runs in check mode, **Then** it exits non-zero and reports a drift error
2. **Given** a model change with the schema regenerated, **When** the generator runs in check mode, **Then** it exits cleanly

---

### User Story 4 - Validate Cross-Entity References (Priority: P2)

An architect's design has an element that `satisfies` a requirement by ID. They want to confirm all references are intact before committing.

**Why this priority**: Referential integrity underpins end-to-end traceability — a design with dangling references cannot be reliably audited or reasoned about.

**Independent Test**: Can be tested by constructing a model with a dangling reference and confirming validation fails with the specific missing ID named — demonstrates traceability enforcement independently.

**Acceptance Scenarios**:

1. **Given** an element references a requirement ID that exists in the description's requirements list, **When** the model is validated, **Then** validation passes
2. **Given** an element references a requirement ID that does not exist in the description, **When** the model is validated, **Then** validation fails with a reference resolution error naming the missing ID

---

### Edge Cases

- What happens when a `schema_version` field is absent from a loaded artifact?
- How does the model handle an empty `ArchitectureDescription` (no requirements, no elements)?
- What happens when the generator is invoked without write permissions to the output path?
- How does check mode behave when the committed schema file does not yet exist?
- What happens when two entities within a description share the same identifier?
- How are circular relationships between elements detected and reported?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The model MUST define typed entities for `Requirement`, `Element`, `Relationship`, `SolutionOption`, `Finding`, `Verdict`, `AuditEntry`, and the aggregate root `ArchitectureDescription`
- **FR-002**: Every entity MUST reject unknown fields, failing with a validation error rather than silently accepting extended or unrecognized data
- **FR-003**: Entity identifiers MUST follow stable, validated patterns (e.g., `REQ-NNN` for requirements, `OPT-NNN` for solution options) enforced at parse time with a clear error on violation
- **FR-004**: The schema generator MUST emit a JSON Schema document from the model; the emitted schema MUST carry a unique identifier, a schema dialect declaration, a human-readable title, and an embedded schema version field
- **FR-005**: The schema generator MUST be the sole authorized writer of generated schema artifacts and MUST support a check mode that exits non-zero when regeneration would alter a committed file, reporting the specific differences
- **FR-006**: A canonical example instance MUST be maintained alongside the schema; it MUST validate against the published schema and MUST be referentially intact at all times
- **FR-007**: The model MUST carry traceability fields (`satisfies`, `provenance`) on relevant entities, enabling the full Requirement → Element → SolutionOption → Verdict chain to be expressed and validated in a single referential-integrity pass

### Non-Functional Requirements

- **NFR-001**: Schema generation MUST be deterministic — identical model source MUST produce byte-identical output on every run from a clean checkout, regardless of environment
- **NFR-002**: Backward-compatible model changes MUST ship with a minor version increment; breaking changes MUST trigger a major version increment, a recorded migration path, and a published architecture decision record

### Key Entities

- **ArchitectureDescription**: Aggregate root; owns all other entities and is the unit of serialization, validation, and schema conformance
- **Requirement**: A single design requirement with a stable identifier (`REQ-NNN`) and optional compliance metadata; the starting point of every traceability chain
- **Element**: A structural element (person, system, container, or component) with traceability fields linking it to the requirements it satisfies
- **Relationship**: A directed link between two elements with optional description
- **SolutionOption**: A recommendation option under consideration, identified by `OPT-NNN`, carrying a verdict status and rationale
- **Finding**: An audit or review observation attached to an element or option
- **Verdict**: A recorded decision on a `SolutionOption` with rationale and provenance, closing the traceability chain
- **AuditEntry**: An immutable record of a change event, linking actor, timestamp, and affected entity

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Any valid architecture description serializes and deserializes without data loss — verified by automated round-trip equality tests covering all entity types
- **SC-002**: 100% of attempts to load artifacts containing unknown fields or malformed identifiers are rejected with a descriptive error; zero silent acceptances permitted
- **SC-003**: Schema drift is detected and blocked on every CI run — zero model changes merged when the committed schema diverges from model source
- **SC-004**: Any referentially broken description (dangling requirement, element, or option reference) is identified in a single validation pass with the specific missing identifier named in the error output
- **SC-005**: A team member unfamiliar with model internals can author a schema-valid architecture description using only the published schema and canonical example, without reading model source code

## Assumptions

- The C4 model scope extends to the **component** level (Person → System → Container → Component); the code level is out of scope for v1 — `Element.kind` is a closed four-value enum (`person`, `system`, `container`, `component`). Resolved from OQ-02; rationale in research.md Decision 1.
- All consumers of the canonical model operate within the ADP monorepo; no external schema publication or versioned remote endpoint is required for this spec
- The schema generator is a developer CLI tool, not a runtime service; it is invoked explicitly by developers and via CI, not on every model instantiation
- Identifier format patterns use three-digit zero-padded integers as the initial convention (`REQ-001`, `OPT-001`); the pattern is validated but allocation of specific IDs is out of scope
- Migration tooling for breaking schema changes is out of scope for v1; NFR-002 requires an ADR and migration path to be planned at version bump time, not implemented by this spec
- Append-only enforcement of `audit_log` is a governance rule only; the Pydantic model does not structurally prevent programmatic removal of `AuditEntry` items — enforcement is the responsibility of write-path callers

## Out of Scope

- Persistence layer (deferred to ADP-SPEC-002)
- API exposure of the model or schema (deferred to ADP-SPEC-003)
- Any user interface
- C4 code-level elements
- Circular relationship / graph-cycle detection (deferred; the model permits cycles; acyclicity validation is a future concern)
- Identifier registry or allocation management
