---
document: spec-index
project: AI-Assisted Architecture Design Platform (ADP)
constitution: ADP-CONST-001
methodology: spec-driven-development
version: 1.0.0
status: draft
spec_count: 12
---

# ADP Specification Set

These are the feature specifications required to build ADP. Each is an independent, buildable unit governed by the project constitution (`ADP-CONST-001`). Specs describe **what** and **why**; the **how** belongs in each spec's downstream plan. Genuine unknowns are tagged `[NEEDS CLARIFICATION]` and MUST be resolved before that spec's plan is approved.

## Specifications

| ID | Title | Depends on |
|---|---|---|
| ADP-SPEC-001 | Canonical Data Model & Schema Generation | — |
| ADP-SPEC-002 | Persistence & Design Store | 001 |
| ADP-SPEC-003 | Platform API | 001, 002, 004 |
| ADP-SPEC-004 | Identity, Authorization & Audit Trail | 001, 002 |
| ADP-SPEC-005 | Knowledge Base & Retrieval | 001, 002 |
| ADP-SPEC-006 | Requirements Intake & Normalization | 001, 003 |
| ADP-SPEC-007 | AI Recommendation Engine | 001, 005, 006 |
| ADP-SPEC-008 | LLM-as-a-Judge Validation | 001, 005 |
| ADP-SPEC-009 | C4 Visual Design Workspace | 001, 003, 010 |
| ADP-SPEC-010 | Locked Visual Theme & Diagram Rendering | 001 |
| ADP-SPEC-011 | Document, View & Export Generation | 001, 010 |
| ADP-SPEC-012 | Observability & Telemetry | 003 (cross-cutting) |

## Build sequence

The dependency graph yields the following waves; specs within a wave may proceed in parallel.

1. **Wave 0 — Foundation:** ADP-SPEC-001
2. **Wave 1 — Stores & rendering primitives:** ADP-SPEC-002, ADP-SPEC-010
3. **Wave 2 — Governance, knowledge, projection:** ADP-SPEC-004, ADP-SPEC-005, ADP-SPEC-011
4. **Wave 3 — Surface:** ADP-SPEC-003
5. **Wave 4 — Interaction & ingestion:** ADP-SPEC-006, ADP-SPEC-009
6. **Wave 5 — AI judgment:** ADP-SPEC-007, ADP-SPEC-008

ADP-SPEC-012 (observability) is cross-cutting: its requirements MUST be satisfied by every service-bearing spec as it is built, not deferred to the end.

## Shared spec template

Every spec in this set conforms to the following structure so the set is machine-readable and uniformly reviewable:

- **Front matter** — `spec_id`, `title`, `status`, `version`, `depends_on`, `articles_engaged`, `quality_gates`, `owner`.
- **## Overview** — what the feature is and the problem it solves.
- **## User Scenarios & Acceptance Criteria** — Given/When/Then, testable.
- **## Functional Requirements** — `FR-NNN`, each MUST/SHOULD and verifiable.
- **## Non-Functional Requirements** — `NFR-NNN`, measurable.
- **## Data & Contracts** — model entities and schemas touched.
- **## Out of Scope** — explicit exclusions.
- **## Dependencies** — upstream specs and external systems.
- **## Constitutional Compliance** — articles engaged and gates enforced.
- **## Open Questions** — `[NEEDS CLARIFICATION]` items.

## Universal articles and gates

Some constitutional articles and quality gates apply to **every** spec and are therefore not repeated in individual `articles_engaged` / `quality_gates` front matter. They are enforced on all specs by default:

- **ART-I (Spec-Driven Development)** and **ART-IV (Test-Driven Development)** — process articles binding every feature.
- **QG-01** (spec/task linkage), **QG-04** (coverage), **QG-06** (SAST), **QG-07** (dependency scan) — universal CI gates run on all changes.

The per-spec front matter lists only the articles and gates a spec engages *distinctively*, so the set stays reviewable without restating universal obligations on all twelve.

## Definition of Done (per spec)

A spec is implemented when: its functional requirements each have passing tests written first (Article IV); all engaged quality gates pass in CI; new artifacts validate against published schemas (Article III); service code emits the required telemetry (ADP-SPEC-012); and no `[NEEDS CLARIFICATION]` remains open.
