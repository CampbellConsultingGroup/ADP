---
spec_id: ADP-SPEC-009
title: C4 Visual Design Workspace
status: draft
version: 0.1.0
depends_on: [ADP-SPEC-001, ADP-SPEC-003, ADP-SPEC-010]
articles_engaged: [ART-II, ART-III, ART-XI, ART-XII]
quality_gates: [QG-03, QG-16, QG-17]
owner: enterprise-architecture
---

# ADP-SPEC-009 — C4 Visual Design Workspace

## Overview

The workspace is the interactive surface where architects build C4 diagrams at the context, container, and component levels — matching the enterprise, solution, and technical architect personas. The canvas is a view over the canonical model: placing an element creates a typed record, and drawing a relationship creates a typed relationship. Diagram and data therefore cannot drift, and the same model can be projected to a different C4 level without redrawing.

## User Scenarios & Acceptance Criteria

- **Model-backed editing.** Given an architect places an element, when it is created, then a typed `Element` MUST be written to the model with the correct C4 level.
- **No drift.** Given a relationship is drawn, when persisted, then a typed `Relationship` MUST exist whose endpoints resolve to model elements.
- **Multi-level projection.** Given a design, when viewed at a different C4 level, then the projection MUST derive from the same model without separate hand-drawn diagrams.
- **Fixed styling.** Given any element, when rendered, then its styling MUST derive from its type via the locked theme; per-diagram style overrides MUST NOT be possible.
- **Traceability surfacing.** Given an element, when inspected, then its satisfied requirements and provenance MUST be visible.

## Functional Requirements

- **FR-001.** The canvas MUST support designing at context, container, and component levels.
- **FR-002.** Every canvas mutation MUST map to a typed model mutation via the Platform API.
- **FR-003.** The workspace MUST project a single model to any supported C4 level without duplicate diagram sources.
- **FR-004.** Element styling MUST derive from element type via the locked theme (ADP-SPEC-010); the UI MUST NOT expose per-diagram style overrides.
- **FR-005.** The workspace MUST surface each element's traceability (satisfied requirements, provenance).
- **FR-006.** Edits MUST result in schema-valid model state.

## Non-Functional Requirements

- **NFR-001.** Canvas and model edits MUST respond within sub-second interactive budgets.
- **NFR-002.** The workspace MUST remain consistent with the model under concurrent edits (last-write-wins acceptable initially).

## Data & Contracts

Consumes and mutates the canonical model through the Platform API; consumes the locked theme for rendering.

## Out of Scope

Server-side diagram rendering and export (ADP-SPEC-010, ADP-SPEC-011); the recommendation panel logic (ADP-SPEC-007).

## Dependencies

ADP-SPEC-001, ADP-SPEC-003, ADP-SPEC-010. External: web client runtime.

## Constitutional Compliance

Implements ART-II, ART-III, ART-XI (traceability), ART-XII (fixed visual language). Gates: QG-03, QG-16, QG-17.

## Open Questions

- `[NEEDS CLARIFICATION]` Real-time multi-user collaboration scope, or single-editor with optimistic locking for v1.
