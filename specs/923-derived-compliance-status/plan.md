# Implementation Plan: Derived Compliance Status

**Branch**: `923-derived-compliance-status` | **Date**: 2026-08-18 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/923-derived-compliance-status/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

COMPLY-03 adds a pure, no-I/O function that derives one overall `ComplianceStatus` for a Capability,
Application, Design, or Pattern from the set of `ControlMapping` rows (COMPLY-02) currently targeting
it, using minimum-aggregation ("one Non-Compliant control anywhere wins"), plus a thin async
dispatch helper that gathers those mappings via COMPLY-02's already-existing
`list_mappings_for_{capability,application,design,pattern}()` store functions and feeds their
statuses into the pure function. No new table, no new migration, no new API endpoint — this pass
delivers only the derivation logic itself and its unit tests, consistent with the source bundle's
explicit implementation-order note that this function must be built and validated standalone before
anything else depends on it.

## Technical Context

**Language/Version**: Python 3.12 (backend only — no frontend file is touched; this feature has no
UI surface in this pass)
**Primary Dependencies**: None new. Extends `adp.compliance.models` (adds the pure function,
alongside the existing `ComplianceStatus` enum it returns) and `adp.compliance.store` (adds the
thin async dispatch helper, alongside the four existing `list_mappings_for_*` functions it calls) —
both already part of the existing stack from COMPLY-01/COMPLY-02.
**Storage**: N/A — no new table, no migration. Reads the five existing `control_*_mapping` tables
(migration `033`) exclusively through COMPLY-02's existing store functions; this feature owns no SQL
of its own.
**Testing**: pytest — a new standalone unit test module exercising the pure function against the
full status-combination matrix from spec.md (SC-001/FR-010), mirroring
`tests/unit/strategy/test_objective_status.py`'s precedent for testing a derived-status pure function
in isolation before it is wired into any store or router.
**Target Platform**: Linux server (existing FastAPI/uvicorn backend) — unchanged.
**Project Type**: Backend-only addition to the existing `adp.compliance` package (single project;
no web/mobile split applies).
**Performance Goals**: Not a distinguishing concern — the aggregation is a single O(n) pass over one
entity's mapped-control statuses, where n is the number of controls mapped to that one entity
(bounded, small; no different in shape from the existing `min(scores.values())` Health rubric).
**Constraints**: The aggregation itself MUST be a pure function with zero I/O (spec's ART-II/ART-IV
notes) — the async dispatch helper that fetches mapping rows is a separate, thin wrapper around it,
never merged into the pure function itself, so the aggregation rule stays independently unit-testable
without a database.
**Scale/Scope**: One new pure function, one new thin async dispatch helper, one new unit test module.
No schema change, no router change, no new permission action.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Applies? | How this feature satisfies it |
|---|---|---|
| ART-I (Spec-Driven Development) | Yes | This plan follows an approved spec (`spec.md`, all `[NEEDS CLARIFICATION]` resolved). |
| ART-II (Model is Single Source of Truth) | Yes — central to this feature | The derived status is never persisted or hand-set; it is computed fresh from `ControlMapping` rows on every call (spec FR-007). |
| ART-III (Everything is Machine-Readable) | Yes, incidentally | The function's output is the existing typed `ComplianceStatus` enum — no new free-text or untyped artifact. |
| ART-IV (Test-Driven Development) | Yes — central to this feature | The pure function is written test-first against the full status-combination matrix (spec SC-001/FR-010), mirroring `compute_status()`'s and `compute_business_value_score()`'s own established precedent, before any caller depends on it. |
| ART-V (Security by Design) | Yes, minimal | Threat model in spec.md: no new data surface, no new endpoint; the one residual note (future callers must respect COMPLY-02's existing sensitivity gate) is carried forward, not resolved here, since there is no caller in this pass. |
| ART-VI (Observability) | N/A this pass | No new service boundary, no new orchestration step; a pure function has no request/trace of its own to instrument. Revisit when a router/endpoint wires this in (COMPLY-04). |
| ART-VII (Grounded AI Only) | N/A | No AI/LLM involvement in this feature. |
| ART-VIII (Human-in-the-Loop) | N/A | No consequential/write action — this is a read-side derivation over data humans already entered via COMPLY-02's confirm/write flow. |
| ART-IX (Provenance and Auditability) | N/A, by design | Nothing is mutated; there is no new audit-worthy event. The underlying `ControlMapping` writes are already audited by COMPLY-02, unchanged here. |
| ART-X (Deterministic Validation Gating) | Yes, by analogy | Not an LLM-as-Judge gate, but the same determinism principle applies directly: given the same set of mapped-control statuses, the derived result MUST be identical every time (spec FR-007, SC-004). |
| ART-XI (Traceability End to End) | Yes | The derived status is always re-derivable from, and traceable back to, the specific `ControlMapping` rows that produced it — never an opaque cached value (spec's Constitutional Articles Touched). |
| ART-XIII (Typed Contracts Everywhere) | Yes | Function signature and return type use existing Pydantic/`StrEnum` types (`ControlMapping`, `ComplianceStatus`) from `adp.compliance.models`; no untyped dict crosses this boundary. |
| ART-XIV / ART-XV (Reproducible builds / Schema evolution) | N/A | No generated artifact, no schema change. |
| ART-XII, ART-XVI | N/A | No visual/diagram surface; no new stakeholder-facing document beyond this spec/plan. |

**Gate result: PASS.** No violations requiring justification; Complexity Tracking is not needed.

**Post-Phase-1 re-check**: Confirmed unchanged after design (data-model.md, contracts/, quickstart.md).
No new table, no new endpoint, no new dependency was introduced during design — the PASS assessment
above holds exactly as evaluated pre-research.

## Project Structure

### Documentation (this feature)

```text
specs/923-derived-compliance-status/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md         # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command) — empty; no new HTTP contract (see research.md D1)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
# Single project (existing ADP layout) — this feature touches only the backend, inside the
# already-existing adp.compliance package from COMPLY-01/COMPLY-02.

src/adp/compliance/
├── store.py                # ADD: compute_compliance_status(statuses) -> ComplianceStatus (pure fn,
│                            #      no I/O) + get_entity_compliance_status(entity_type, entity_id,
│                            #      session) (thin async dispatch to the existing list_mappings_for_*
│                            #      helpers already in this file) — mirrors where compute_status()
│                            #      and compute_business_value_score() live in their own domains
│                            #      (research.md D2)
├── models.py                # UNCHANGED — ComplianceStatus enum already defined here (COMPLY-02)
├── router.py                # UNCHANGED — no new endpoint in this pass (research.md D1)
└── __init__.py               # UNCHANGED

tests/unit/compliance/
├── test_compliance_status.py   # ADD: full status-combination matrix against the pure function
├── test_models.py               # UNCHANGED
└── test_mapping_models.py       # UNCHANGED
```

**Structure Decision**: Single project — this is an additive, backend-only change inside the
existing `adp.compliance` package created by COMPLY-01/COMPLY-02 (`specs/921-...`, `specs/922-...`).
No new package, no new router file, no frontend directory touched (`web/` is unaffected — there is
no UI surface for a derivation with no caller yet).

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

*No violations — table intentionally omitted.*
