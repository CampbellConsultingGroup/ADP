---
spec_id: ADP-SPEC-006
title: Requirements Intake & Normalization
status: draft
version: 0.1.0
depends_on: [ADP-SPEC-001, ADP-SPEC-003]
articles_engaged: [ART-III, ART-VI, ART-VIII, ART-IX, ART-XI]
quality_gates: [QG-11, QG-13, QG-14, QG-16]
owner: enterprise-architecture
---

# ADP-SPEC-006 — Requirements Intake & Normalization

## Overview

Intake accepts business requirements in whatever form the organization produces them — documents, structured forms, or pasted text — and normalizes each into a typed `Requirement` in the canonical model. Extraction is AI-assisted, but every extracted requirement is confirmed by a human before it enters the model. The normalized requirement is the anchor for all downstream traceability.

## User Scenarios & Acceptance Criteria

- **Normalization.** Given raw business requirements, when intake runs, then each MUST become a typed `Requirement` with a statement, a classification, a stable id, and a recorded source.
- **Human confirmation.** Given AI-extracted requirements, when presented, then none MUST enter the canonical model until a human confirms it; the confirming actor MUST be recorded.
- **Traceability anchor.** Given a confirmed requirement, when later referenced, then it MUST be addressable by its stable id for the requirement → element → recommendation → verdict thread.
- **Observability.** Given an extraction run, when it executes, then it MUST emit a telemetry span recording inputs, outputs, and cost.

## Functional Requirements

- **FR-001.** Intake MUST accept requirements from documents, structured forms, and free text.
- **FR-002.** Each requirement MUST be normalized to a typed `Requirement` with kind (functional, non-functional, constraint, driver), source, and stable id.
- **FR-003.** AI-extracted requirements MUST be presented for human confirmation; unconfirmed requirements MUST NOT be committed to the model.
- **FR-004.** The confirming actor MUST be recorded on the requirement and in the audit trail.
- **FR-005.** Intake MUST link requirements to referenced capabilities and principles where identifiable.
- **FR-006.** Each AI extraction step MUST emit a telemetry span per ADP-SPEC-012.

## Non-Functional Requirements

- **NFR-001.** Extraction MUST run asynchronously and MUST NOT block the interactive surface.
- **NFR-002.** Normalized requirements MUST validate against the published schema.

## Data & Contracts

Produces `Requirement` records into the canonical model via the Platform API.

## Out of Scope

Recommendation generation (ADP-SPEC-007); document parsing fidelity guarantees beyond best-effort with human confirmation.

## Dependencies

ADP-SPEC-001, ADP-SPEC-003. External: configurable LLM endpoint.

## Constitutional Compliance

Implements ART-III, ART-VI, ART-VIII (human-in-the-loop), ART-IX (provenance), ART-XI (traceability). Gates: QG-11, QG-13, QG-14, QG-16.

## Open Questions

- `[NEEDS CLARIFICATION]` Supported input document formats and whether extraction confidence is surfaced to the confirming human.
