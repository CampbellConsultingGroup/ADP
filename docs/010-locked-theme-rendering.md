---
spec_id: ADP-SPEC-010
title: Locked Visual Theme & Diagram Rendering
status: draft
version: 0.1.0
depends_on: [ADP-SPEC-001]
articles_engaged: [ART-II, ART-III, ART-XII, ART-XIV]
quality_gates: [QG-03, QG-17, QG-18]
owner: enterprise-architecture
---

# ADP-SPEC-010 — Locked Visual Theme & Diagram Rendering

## Overview

This feature guarantees that every diagram across ADP looks identical in visual language regardless of author. It owns the locked theme — a versioned, non-overridable mapping from C4 element type to fill, stroke, text color, and shape — and the renderer that turns the model into diagram-as-code (Structurizr DSL) and then into SVG/PNG. Styling is a property of element type applied at render time, never an authoring choice.

## User Scenarios & Acceptance Criteria

- **Consistency.** Given two unrelated designs, when rendered, then equivalent element types MUST appear with identical styling.
- **Non-override.** Given a render request carrying per-element style input, when processed, then the renderer MUST ignore it and apply only the locked theme.
- **Diagram-as-code.** Given a model, when rendered, then the renderer MUST emit machine-readable, version-controllable diagram source before producing images.
- **Theme validity.** Given the theme artifact, when checked, then it MUST be marked locked and MUST validate against the theme schema.
- **Deliberate change.** Given the visual language must change, when updated, then it MUST be a versioned, reviewed change to the theme artifact, not an ad-hoc override.

## Functional Requirements

- **FR-001.** The locked theme MUST map every `ElementType` to fill, stroke, text color, and shape, and MUST be marked locked.
- **FR-002.** The renderer MUST apply only the locked theme; it MUST NOT accept per-diagram or per-element style overrides.
- **FR-003.** The renderer MUST emit diagram-as-code (Structurizr DSL) from the model and render it to SVG and PNG.
- **FR-004.** The theme MUST validate against the theme schema and carry a version.
- **FR-005.** A theme change MUST bump the theme version and be reviewable as an artifact diff.
- **FR-006.** Datastores MUST be distinguishable by shape, not color alone.

## Non-Functional Requirements

- **NFR-001.** Rendering MUST be deterministic: the same model and theme MUST produce equivalent diagram source.
- **NFR-002.** Colors MUST meet sufficient text-contrast thresholds for legibility.

## Data & Contracts

Owns `c4-theme.json` and `c4-theme.schema.json`; consumes the canonical model; produces diagram source and images.

## Out of Scope

The interactive canvas (ADP-SPEC-009); document export bundling (ADP-SPEC-011).

## Dependencies

ADP-SPEC-001. External: Structurizr DSL tooling.

## Constitutional Compliance

Implements ART-II, ART-III, ART-XII (fixed visual language), ART-XIV. Gates: QG-03, QG-17, QG-18.

## Open Questions

- `[NEEDS CLARIFICATION]` Whether to support a separate high-contrast/accessibility theme variant while keeping it locked.
