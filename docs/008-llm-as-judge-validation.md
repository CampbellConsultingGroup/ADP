---
spec_id: ADP-SPEC-008
title: LLM-as-a-Judge Validation
status: draft
version: 0.1.0
depends_on: [ADP-SPEC-001, ADP-SPEC-005]
articles_engaged: [ART-VI, ART-VII, ART-VIII, ART-IX, ART-X, ART-XI]
quality_gates: [QG-11, QG-12, QG-13, QG-15, QG-16]
owner: enterprise-architecture
---

# ADP-SPEC-008 — LLM-as-a-Judge Validation

## Overview

Validation evaluates a design against the organization's standards, patterns, principles, and prior approved solutions, and produces a structured, citeable verdict a reviewer can act on. It runs as a fan-out of independent critics — each scoped to one dimension and each citing the specific item it judges against — followed by aggregation and deterministic gating. Humans may override verdicts; overrides are explicit and recorded.

## User Scenarios & Acceptance Criteria

- **Cited findings.** Given a design, when validated, then every finding MUST identify the offending element, the violated standard/principle/pattern, a severity, and a citation with version.
- **Deterministic gating.** Given the same critic scores, when gated twice, then the pass/fail decision MUST be identical.
- **Orphan detection.** Given an element with no satisfied requirement, when validated, then validation MUST fail with a traceability finding.
- **Human override.** Given a reviewer overrides a verdict, when committed, then the override MUST be explicit and recorded with justification in the audit trail.
- **Inspectability.** Given a validation run, when it executes, then each critic MUST emit a telemetry span with inputs, retrieved standards, outputs, cost, and latency.

## Functional Requirements

- **FR-001.** Validation MUST run as independent critics (fan-out), each scoped to one dimension (standards, principles, pattern-fit, consistency with prior solutions).
- **FR-002.** Each critic MUST retrieve and cite the specific knowledge items it judges against, with versions.
- **FR-003.** Critic outputs MUST aggregate into a `Verdict` with a score, findings, and a pass/fail decision.
- **FR-004.** Gating thresholds MUST be explicit configuration; gating MUST be deterministic given the critic scores.
- **FR-005.** Validation MUST fail designs containing orphan elements or dangling references.
- **FR-006.** A human override MUST be explicit, MUST carry a justification, and MUST be recorded.
- **FR-007.** Each critic MUST emit a telemetry span per ADP-SPEC-012.

## Non-Functional Requirements

- **NFR-001.** Validation MUST run asynchronously; full fan-out within minutes for typical designs.
- **NFR-002.** Verdicts MUST be linked to the design version they evaluated and retained in history.

## Data & Contracts

Consumes ADP-SPEC-005 retrieval and the canonical design; produces `Verdict` and `Finding` records.

## Out of Scope

Recommendation (ADP-SPEC-007); definition of the standards themselves (knowledge authoring).

## Dependencies

ADP-SPEC-001, ADP-SPEC-005. External: configurable LLM endpoint; orchestration via LangGraph.

## Constitutional Compliance

Implements ART-VI, ART-VII, ART-VIII, ART-IX, ART-X (deterministic gating), ART-XI. Gates: QG-11, QG-12, QG-13, QG-15, QG-16.

## Open Questions

- `[NEEDS CLARIFICATION]` Default gating thresholds per severity and whether thresholds are configurable per organization (open question OQ-01).
- `[NEEDS CLARIFICATION]` Critic calibration approach to keep scoring stable across model versions.
