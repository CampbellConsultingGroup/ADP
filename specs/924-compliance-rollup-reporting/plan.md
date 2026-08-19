# Implementation Plan: Compliance Rollup Reporting

**Branch**: `924-compliance-rollup-reporting` | **Date**: 2026-08-19 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/924-compliance-rollup-reporting/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Two new read-only aggregate endpoints inside the already-existing `adp.compliance` package: (1)
`GET /api/v1/compliance/frameworks/{framework_id}/rollup` — a framework × status matrix (US1),
directly mirroring `918-strategy-rollups`' `GET /strategy/heatmap` theme × status matrix, the closest
precedent in the codebase for this exact problem shape; (2) `GET /api/v1/compliance/summary` —
platform-wide framework count / overall coverage % / at-risk count for a new sixth domain card on
`OverviewPage.tsx`, directly mirroring `051-strategy-landing-card`'s `GET /strategy/summary` Strategy
card. Both reuse COMPLY-03's already-built `compute_compliance_status()` pure function per entity
group rather than inventing new aggregation logic. No new table, no new migration, no new
`ActionType` — both endpoints reuse the exact `READ_APPLICATION_GOVERNANCE` permission COMPLY-02
already established, applied per spec.md FR-007's resolution (exclude, don't block).

## Technical Context

**Language/Version**: Python 3.12 (backend); TypeScript 5.x + React 18 (frontend) — both existing
stacks, no new language/version surface.
**Primary Dependencies**: None new. FastAPI ≥ 0.111, SQLAlchemy 2 async (Core, raw `sa.select()`
joins mirroring `adp.compliance.store`'s existing `Table()`-object style — no ORM), Pydantic v2,
React 18, TanStack Query v5 — all existing project dependencies.
**Storage**: PostgreSQL 16 — no migration. Both new endpoints read the existing
`regulatory_frameworks`/`controls`/`control_{capability,application,design,pattern,organization}_mapping`
tables (migrations 032/033) via two new JOIN queries in `adp.compliance.store` — no new table.
**Testing**: pytest (unit tests for the new pure bucketing/aggregation helper, mirroring
`tests/unit/compliance/test_compliance_status.py`'s established SQLite-fixture-free style for the
pure part and its SQLite-fixture style for the async dispatch part; contract tests for the two new
endpoints, mirroring `tests/contract/test_compliance_mappings_api.py`'s fixture); Vitest + Testing
Library for the frontend (mirroring `OverviewPage.tsx`'s and `FrameworkDetail.tsx`'s existing
hook-mocking convention).
**Target Platform**: Linux server (backend), browser (frontend) — unchanged.
**Project Type**: Web application (existing `src/adp/` backend + `web/` frontend split).
**Performance Goals**: No new performance surface distinct from `918-strategy-rollups`' own
heat-map precedent — one JOIN query per endpoint, Python-side per-entity-group aggregation over
demo-scale data; no materialized view or index-backed optimization in this pass (matches 918's own
explicit Assumption for the same class of problem).
**Constraints**: Every count/percentage MUST be computed fresh, never cached (spec.md FR-006, ART-II)
— identical constraint to every other derived-value feature this session has built. Application-
targeted entities MUST be excluded from both endpoints' aggregates for a caller lacking
`READ_APPLICATION_GOVERNANCE` (spec.md FR-007) — the one deliberate deviation from `918-strategy-
rollups`' own "all rollup endpoints stay ungated" precedent, justified because Compliance's
underlying per-mapping data (unlike Strategy's) already carries a real sensitivity gate COMPLY-02
established; this feature must respect it, not silently ignore it because the *older* precedent (a
different domain) didn't need one.
**Scale/Scope**: Zero new tables, zero new migrations, zero new `ActionType`. Two new Pydantic
response models (`FrameworkCoverageRollup`, `ComplianceSummaryResponse`) plus one new internal
five-field status-tally value object (mirrors `ThemeStatusCounts`'s "explicit fields, not
`dict[str, int]`, per ART-XIII" precedent exactly). Two new `adp.compliance.store` functions built
on one new shared private bucketing helper. Two new `adp.compliance.router` endpoints. Two new
frontend hooks (`web/src/api/compliance.ts`) + one new display block on `FrameworkDetail.tsx` (US1)
+ one new `DOMAINS` entry on `OverviewPage.tsx` (US2, matching the Strategy card's shape exactly,
including its `shield` icon, already used for Compliance's own nav entry).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Applies? | How this feature satisfies it |
|---|---|---|
| ART-I (SDD mandatory) | Yes | This plan follows an approved spec (`spec.md`, all `[NEEDS CLARIFICATION]` resolved); `/speckit.tasks` → `/speckit.implement` next. |
| ART-II (Model is Single Source of Truth) | Yes — central to this feature | Every count/percentage is a live query + Python-side pass over `ControlMapping`/`Control`/`RegulatoryFramework` data, computed fresh on every request (spec.md FR-006) — no new persisted or cached rollup field, matching `918-strategy-rollups`' own identical framing for the same class of problem. |
| ART-III (Machine-Readable) | Yes, incidentally | Both new response shapes are typed Pydantic v2 models with `extra="forbid"`, explicit fields (not `dict[str, int]`), mirroring `ThemeStatusCounts`. |
| ART-IV (TDD) | Yes | tasks.md will sequence failing unit tests for the new pure bucketing helper and failing contract tests for both endpoints before their implementation tasks, per this session's established pattern. |
| ART-V (Security by Design) | Yes — central to this feature | spec.md's Threat Model and FR-007 are exactly this article in practice: the one real design decision this feature makes is a data-exposure question, resolved via explicit user clarification (Q1) rather than assumed either way. |
| ART-VI (Observability) | Yes | Both new endpoints get the same structured request logging every other ADP read route already gets — no bespoke logging path (mirrors `918`'s own note for its heat-map endpoint). |
| ART-VII (Grounded AI Only) | N/A | No AI/LLM involvement in this feature. |
| ART-VIII (Human-in-the-Loop) | N/A | No consequential/write action — this is entirely a read-side feature over data already entered via COMPLY-01/02's own confirm/write flows. |
| ART-IX (Provenance/Auditability) | N/A, by design | Nothing is mutated; no new audit-worthy event. |
| ART-X (Deterministic Validation Gating) | N/A | Not an LLM-as-Judge gate. |
| ART-XI (Traceability End to End) | Yes | Every rollup number remains traceable back to the individual `ControlMapping` rows that produced it via COMPLY-02's already-shipped reverse-lookup endpoints — this feature adds a summarized *view*, never an opaque number with no path back to its source data. |
| ART-XIII (Typed Contracts Everywhere) | Yes | New Pydantic v2 models for both response shapes; no untyped dict crosses either boundary. |
| ART-XIV/XV (Reproducible builds / Schema evolution) | N/A | No generated artifact, no schema change. |
| ART-XII, ART-XVI | N/A | No visual/diagram theme surface; no new stakeholder-facing document beyond this spec/plan. |

**Gate result: PASS.** No violations requiring justification; Complexity Tracking is not needed — the
one genuinely new pattern (per-caller-varying aggregate counts, per FR-007) is a small, well-scoped
extension of COMPLY-02's own already-reviewed filtering precedent, not a new architectural concept.

**Post-Phase-1 re-check**: Confirmed unchanged after design (research.md, data-model.md, contracts/,
quickstart.md). No new table, no new endpoint beyond the two planned, no new dependency was
introduced during design — the PASS assessment above holds exactly as evaluated pre-research.

## Project Structure

### Documentation (this feature)

```text
specs/924-compliance-rollup-reporting/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md         # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
# Single project (existing ADP layout) — purely additive to the already-existing adp.compliance
# package (COMPLY-01/02/03) and two already-existing frontend files.

src/adp/compliance/
├── models.py             # ADD: FrameworkCoverageRollup, EntityStatusCounts (the explicit-fields
│                          #      tally, mirrors ThemeStatusCounts), ComplianceSummaryResponse
├── store.py                # ADD: get_framework_coverage_rollup(), get_compliance_summary(),
│                            #      one new shared private bucketing helper (research.md D1/D2) —
│                            #      reuses compute_compliance_status() (COMPLY-03) unchanged
├── router.py                # ADD: GET /frameworks/{id}/rollup, GET /summary
└── __init__.py               # UNCHANGED

tests/unit/compliance/
├── test_rollup.py            # ADD: bucketing helper + both store functions (SQLite fixture,
│                              #      mirroring test_compliance_status.py's dual pure/async style)
├── test_compliance_status.py  # UNCHANGED
├── test_models.py              # UNCHANGED
└── test_mapping_models.py       # UNCHANGED

tests/contract/
└── test_compliance_rollup_api.py   # ADD: both new endpoints, mirroring
                                     #      test_compliance_mappings_api.py's fixture shape

web/src/api/compliance.ts       # MODIFIED: + useFrameworkRollup(), useComplianceSummary()
web/src/compliance/
└── FrameworkDetail.tsx         # MODIFIED: + rollup display block (US1)
web/src/overview/
├── OverviewPage.tsx            # MODIFIED: + one new "compliance" DOMAINS entry (US2)
└── OverviewPage.test.tsx        # MODIFIED: + tests for the new Compliance card, mirroring the
                                  #    existing "OverviewPage: Strategy domain card" describe block
web/src/compliance/FrameworkDetail.test.tsx   # MODIFIED: + rollup display tests
```

**Structure Decision**: Single project — this is an additive, backend+frontend change entirely
inside already-existing files/packages. No new package, no new router file, no new top-level
frontend directory. The only two files outside `adp.compliance`/`web/src/compliance/` touched at all
are `OverviewPage.tsx` (one new card, following its own established `DOMAINS` array pattern exactly)
and its API hook file.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

*No violations — table intentionally omitted.*
