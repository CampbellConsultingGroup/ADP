---
spec_id: ADP-SPEC-018
title: Architecture Recommendation Screen
status: draft
version: 0.1.0
depends_on: [ADP-SPEC-007, ADP-SPEC-014, ADP-SPEC-015, ADP-SPEC-016]
articles_engaged: [ART-I, ART-IV, ART-VII, ART-VIII, ART-IX, ART-XI]
quality_gates: [QG-04, QG-09, QG-12, QG-13, QG-14]
owner: enterprise-architecture
---

# ADP-SPEC-018 — Architecture Recommendation Screen

## Overview

Add an Architecture Recommendation screen to the ADP workspace. After capturing requirements (ADP-SPEC-014), the architect can request AI-generated solution options grounded in the organisational knowledge base. Each option includes a title, rationale, trade-off analysis, and a list of proposed C4 elements. The architect reviews the options and accepts one, which materialises the proposed elements directly onto the design canvas. Accepting a recommendation is a consequential action requiring explicit human confirmation.

## User Scenarios & Acceptance Criteria

- **Request recommendations.** Given confirmed requirements on a design, when the architect opens the Recommendations screen and clicks "Get Recommendations", then the pipeline runs asynchronously and returns ranked options grounded in the knowledge base.
- **Review options.** Given completed recommendations, when the architect views the results, then each option shows its title, rationale, a trade-off table (criterion → meets/partially meets/does not meet), proposed elements, and the knowledge items it was grounded on.
- **Accept an option.** Given a pending option, when the architect clicks "Accept this option", then a confirmation dialog appears (ART-VIII); on confirmation, the proposed elements are written to the canonical design and the architect is navigated to the canvas to see them.
- **Advisory warning.** Given an option marked advisory (grounding citations incomplete), when displayed, then a clear warning indicates the option lacks full knowledge-base grounding and requires extra scrutiny before acceptance.
- **Navigate the workflow.** The screen sits between Intake and Canvas in the navigation header: Intake → Recommendations → Canvas.

## Functional Requirements

- **FR-001**: `POST /api/v1/designs/{id}/recommend` MUST accept a list of `requirement_ids` and start the recommendation pipeline as a background task, returning an `operation_id`.
- **FR-002**: `GET /api/v1/designs/{id}/recommend/{operation_id}` MUST return `status` (pending/running/completed/failed) and, when complete, the ranked list of `SolutionOption` records.
- **FR-003**: `POST /api/v1/designs/{id}/recommend/{operation_id}/options/{option_id}/accept` MUST require explicit human confirmation (ART-VIII) and, on acceptance, materialise the option's proposed elements into the design store and write an audit entry (ART-IX).
- **FR-004**: The Recommendations screen MUST display each option's rank, title, rationale, trade-off table, proposed elements (name, kind, description), and grounding citations.
- **FR-005**: Options marked `advisory: true` MUST display a prominent warning and require the architect to explicitly acknowledge the advisory status before accepting (ART-VII).
- **FR-006**: After accepting an option, the screen MUST navigate the architect to the C4 canvas to see the materialised elements.
- **FR-007**: The Recommendations screen MUST be accessible from a "Recommendations" navigation item in the workspace header, between "Intake" and "Canvas".
- **FR-008**: The screen MUST show the design's current confirmed requirements so the architect can select which to include in the recommendation request.

## Non-Functional Requirements

- **NFR-001**: The recommendation pipeline runs asynchronously; the screen polls for status (same pattern as intake extraction).
- **NFR-002**: If the knowledge base is empty or unavailable, the pipeline may still run but all options will be marked advisory; the screen must handle this gracefully.

## Out of Scope

- Comparing multiple accepted options side-by-side (future)
- Editing proposed elements before acceptance (elements are accepted as-is and can then be edited on the canvas)
- Re-running recommendations for the same requirements (architect can submit a new request)

## Assumptions

- `RecommendationOrchestrator.run()` and `materialize_option()` are fully implemented (ADP-SPEC-007) — this spec only wires HTTP and UI.
- The knowledge base (pgvector) may be empty in the current environment; options will be advisory in that case.
- The same `LLMClient` and model selection from ADP-SPEC-015 (Anthropic, claude-sonnet-4-6) is used.
- The `confirmation_id` pattern from ADP-SPEC-011 is used for the accept action (ART-VIII).
- Requirement selection defaults to all confirmed requirements; the architect can deselect individual ones.
