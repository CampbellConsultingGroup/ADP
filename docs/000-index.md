---
document: spec-index
project: AI-Assisted Architecture Design Platform (ADP)
constitution: ADP-CONST-001
methodology: spec-driven-development
version: 1.1.0
status: current
spec_count: 36
---

# ADP Specification Set

These are the feature specifications required to build ADP. Each is an independent, buildable unit governed by the project constitution (`ADP-CONST-001`). Specs describe **what** and **why**; the **how** belongs in each spec's downstream plan. Genuine unknowns are tagged `[NEEDS CLARIFICATION]` and MUST be resolved before that spec's plan is approved.

The set has two generations:

- **Foundational specs (001–012)** — authored up front as this document set (`docs/001-*.md` … `docs/012-*.md`); the dependency table and build waves below describe them.
- **Delivered feature specs (013–036)** — added iteratively via the Speckit workflow. 013–019 have per-spec documents in `docs/`; from 020 onward the canonical spec lives in `specs/NNN-<slug>/spec.md` (with its plan, tasks, data model, and API contracts alongside). No separate `docs/` rendering is maintained for those.

## Foundational specifications (001–012)

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

## Delivered feature specs (013–036)

| ID | Title | Spec location |
|---|---|---|
| ADP-SPEC-013 | Playwright End-to-End Test Suite | `docs/013-playwright-e2e.md` |
| ADP-SPEC-014 | Requirements Intake HTTP API and Web Screen | `docs/014-requirements-intake-ui.md` |
| ADP-SPEC-015 | Anthropic LLM Integration with Model Selection | `docs/015-anthropic-llm-integration.md` |
| ADP-SPEC-016 | Intake as Landing Page with Rejected Requirements Section | `docs/016-intake-landing-page.md` |
| ADP-SPEC-017 | Intake Proposal Status Sync and Rejected Requirements Layout | `docs/017-intake-proposal-status-sync.md` |
| ADP-SPEC-018 | Architecture Recommendation Screen | `docs/018-recommendation-screen.md` |
| ADP-SPEC-019 | Recommendation Learning and Knowledge Capture | `docs/019-recommendation-learning.md` |
| ADP-SPEC-020 | Knowledge Base Management | `specs/020-knowledge-base-crud/spec.md` |
| ADP-SPEC-021 | CALM Export | `specs/021-calm-export/spec.md` |
| ADP-SPEC-022 | CALM Pattern Import | `specs/022-calm-pattern-import/spec.md` |
| ADP-SPEC-023 | Internal Architecture Consolidation | `specs/023-internal-consolidation/spec.md` |
| ADP-SPEC-024 | Persistent Operation Store | `specs/024-persistent-operations/spec.md` |
| ADP-SPEC-025 | Multi-Design UI and Production Readiness | `specs/025-multi-design-production/spec.md` |
| ADP-SPEC-026 | Keycloak Authentication | `specs/026-keycloak-authn/spec.md` |
| ADP-SPEC-027 | Immutable LLM Reasoning Store | `specs/027-llm-reasoning-store/spec.md` |
| ADP-SPEC-028 | Recommendation Reasoning Display | `specs/028-recommendation-reasoning-ui/spec.md` |
| ADP-SPEC-029 | Element Technology Tagging | `specs/029-element-technology-tags/spec.md` |
| ADP-SPEC-030 | Design Lifecycle Management | `specs/030-design-lifecycle/spec.md` |
| ADP-SPEC-031 | Portfolio Analysis Screen | `specs/031-portfolio-analysis/spec.md` |
| ADP-SPEC-032 | Governance Reporting Dashboard | `specs/032-governance-reporting/spec.md` |
| ADP-SPEC-033 | Business Architecture — Capability Model and Value Streams | `specs/033-business-architecture/spec.md` |
| ADP-SPEC-034 | Business Architecture Traceability | `specs/034-business-arch-traceability/spec.md` |
| ADP-SPEC-035 | Business Domain Registry and Stage-Capability Mapping | `specs/035-business-domain-registry/spec.md` |
| ADP-SPEC-036 | Application Registry | `specs/036-application-registry/spec.md` |

The current implemented state of the whole system is described in `docs/solution-architecture.md`.

## Build sequence

The dependency graph for the foundational set yields the following waves; specs within a wave may proceed in parallel. Delivered feature specs (013+) were built sequentially on top of these waves.

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

The per-spec front matter lists only the articles and gates a spec engages *distinctively*, so the set stays reviewable without restating universal obligations on every spec.

## Definition of Done (per spec)

A spec is implemented when: its functional requirements each have passing tests written first (Article IV); all engaged quality gates pass in CI; new artifacts validate against published schemas (Article III); service code emits the required telemetry (ADP-SPEC-012); and no `[NEEDS CLARIFICATION]` remains open.
