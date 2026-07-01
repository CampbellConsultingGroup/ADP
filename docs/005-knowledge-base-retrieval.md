---
spec_id: ADP-SPEC-005
title: Knowledge Base & Retrieval
status: draft
version: 0.1.0
depends_on: [ADP-SPEC-001, ADP-SPEC-002]
articles_engaged: [ART-III, ART-VII, ART-XV]
quality_gates: [QG-03, QG-12]
owner: enterprise-architecture
---

# ADP-SPEC-005 — Knowledge Base & Retrieval

## Overview

The knowledge base is what grounds ADP's AI. It indexes the organization's existing patterns, reference architectures, standards, principles, and prior approved solutions as typed, versioned, embedded records, and exposes hybrid retrieval (vector + keyword + relationship) so the recommendation and validation subsystems can ground and cite their outputs. The knowledge base indexes canonical sources; it does not become a fork of them.

## User Scenarios & Acceptance Criteria

- **Grounded retrieval.** Given a set of requirements, when relevant knowledge is requested, then retrieval MUST return typed records each carrying a stable id and version usable as a citation.
- **Currency.** Given an upstream standard changes, when re-indexing runs, then retrieval MUST reflect the new version and the version MUST be distinguishable from the old.
- **Relationship queries.** Given a principle, when asked "which patterns satisfy it", then retrieval MUST answer using indexed relationships, not text matching alone.
- **Provenance.** Given any retrieved item, when used by an AI step, then the item id and version MUST be available to record as provenance.

## Functional Requirements

- **FR-001.** Each knowledge item MUST be stored as a typed record with id, version, type, full text, structured metadata, and an embedding.
- **FR-002.** Knowledge types MUST include patterns, reference architectures, standards, principles, and prior solutions.
- **FR-003.** Retrieval MUST be hybrid, combining vector similarity, keyword search, and relationship traversal.
- **FR-004.** Re-indexing MUST update items from canonical sources and MUST preserve version distinguishability.
- **FR-005.** Every retrieval result MUST expose a citation-ready id and version.
- **FR-006.** Indexed items MUST validate against their published schemas.

## Non-Functional Requirements

- **NFR-001.** Retrieval latency MUST be low enough not to dominate AI step latency budgets.
- **NFR-002.** The index MUST scale to the organization's full corpus of patterns, standards, and prior solutions.

## Data & Contracts

Owns the knowledge-item schema and the vector index; provides retrieval contracts to ADP-SPEC-007 and ADP-SPEC-008.

## Out of Scope

The recommendation and validation logic that consume retrieval (ADP-SPEC-007, ADP-SPEC-008); authoring of the knowledge itself.

## Dependencies

ADP-SPEC-001, ADP-SPEC-002. External: PostgreSQL with pgvector; the organization's canonical knowledge sources.

## Constitutional Compliance

Implements ART-III, ART-VII (grounded AI), ART-XV. Gates: QG-03, QG-12.

## Open Questions

- `[NEEDS CLARIFICATION]` Canonical sources of truth and connectors for each knowledge type, and their re-index cadence.
- `[NEEDS CLARIFICATION]` Embedding model selection and whether it is hosted or self-hosted.
