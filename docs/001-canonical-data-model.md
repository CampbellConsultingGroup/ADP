---
spec_id: ADP-SPEC-001
title: Canonical Data Model & Schema Generation
status: draft
version: 0.1.0
depends_on: []
articles_engaged: [ART-II, ART-III, ART-XIII, ART-XIV, ART-XV]
quality_gates: [QG-02, QG-03, QG-05, QG-18]
owner: enterprise-architecture
---

# ADP-SPEC-001 — Canonical Data Model & Schema Generation

## Overview

The canonical data model is the single source of truth for every ADP design. It defines the typed entities — requirements, C4 elements, relationships, recommendation options, verdicts, and audit entries — and binds them into one traceable graph. The published JSON Schema and all downstream artifacts are generated from this model, never hand-authored, so description and implementation cannot drift. This spec delivers the model, the schema generator, the drift gate, and the canonical example fixture.

## User Scenarios & Acceptance Criteria

- **Authoring a design.** Given a service holds an `ArchitectureDescription`, when it is serialized, then the output MUST validate against the published schema and round-trip back to an identical model.
- **Rejecting malformed data.** Given an artifact with an unknown field, when it is loaded, then loading MUST fail rather than silently accept it.
- **Detecting drift.** Given a change to the model source, when the committed schema is not regenerated, then CI MUST fail with a drift error.
- **Resolving references.** Given an element references a requirement, recommendation, or another element, when the model is validated, then every reference MUST resolve to an existing entity.

## Functional Requirements

- **FR-001.** The model MUST define typed entities for `Requirement`, `Element`, `Relationship`, `SolutionOption`, `Finding`, `Verdict`, `AuditEntry`, and the aggregate `ArchitectureDescription`.
- **FR-002.** Every entity MUST reject unknown fields (`extra="forbid"`).
- **FR-003.** Entity identifiers MUST follow stable, validated formats (e.g. `REQ-NNN`, `OPT-NNN`).
- **FR-004.** A generator MUST emit the JSON Schema from the model; the schema MUST carry `$id`, `$schema`, title, and an embedded `schema_version`.
- **FR-005.** The generator MUST be the only writer of generated artifacts and MUST support a `--check` mode that fails when regeneration would change a committed file.
- **FR-006.** A canonical example instance MUST be maintained, MUST validate against the schema, and MUST be referentially intact.
- **FR-007.** The model MUST express end-to-end traceability fields (`satisfies`, `provenance`) enabling the requirement → element → recommendation → verdict thread.

## Non-Functional Requirements

- **NFR-001.** Schema generation MUST be deterministic and reproducible from a clean checkout.
- **NFR-002.** Backward-compatible model changes ship with a minor `schema_version` bump; breaking changes require a major bump, a migration, and an ADR.

## Data & Contracts

Owns all canonical entities and the published `architecture-description.schema.json`. This is the contract every other spec consumes.

## Out of Scope

Persistence (ADP-SPEC-002), API exposure (ADP-SPEC-003), and any UI.

## Dependencies

None (foundation). External: Pydantic v2, JSON Schema (Draft 2020-12).

## Constitutional Compliance

Implements ART-II (source of truth), ART-III (machine-readable), ART-XIII (typed contracts), ART-XIV (drift-free), ART-XV (governed evolution). Gates: QG-02, QG-03, QG-05, QG-18.

## Open Questions

- `[NEEDS CLARIFICATION]` Should the model support a fourth C4 level (code) or stop at component? (Open question OQ-02 from the solution architecture.)
