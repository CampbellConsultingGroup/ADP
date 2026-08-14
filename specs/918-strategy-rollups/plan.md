# Implementation Plan: Strategy Rollups — Heat Map, Orphan Report, Richer Summary

**Branch**: `918-strategy-rollups` | **Date**: 2026-08-13 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/918-strategy-rollups/spec.md`

## Summary

Three read-only rollup additions, all composed from data that already exists (no new tables, no new
write paths): (1) `GET /strategy/heatmap` — a theme × status matrix of objective counts, optionally
narrowed to one theme; (2) `GET /business/orphans` — capabilities and value streams with zero strategic-
objective linkage, surfaced as a badge + toggle filter on the existing Capability Map and Value Streams
screens; (3) enriching the already-shipped `GET /strategy/summary` (Overview Strategy card) with a
per-status objective breakdown and a strategy-initiative count.

## Technical Context

**Language/Version**: Python 3.12 (backend); TypeScript 5.x + React 18 (frontend) — both existing
stacks, no new language/version surface.
**Primary Dependencies**: FastAPI ≥ 0.111, SQLAlchemy 2 async (Core, mirroring `adp.strategy.store`'s and
`adp.business.store`'s existing `sa.Table`/raw-`sa.text()` style — no ORM), Pydantic v2, React 18,
TanStack Query v5 — all existing project dependencies. Zero new packages either side.
**Storage**: PostgreSQL 16 — no migration. Every new/enriched endpoint reads existing tables
(`strategic_objectives`, `strategic_themes`, `strategy_initiatives`, `strategic_objective_capabilities`,
`strategic_objective_value_streams`, `business_capabilities`, `value_streams`) — this feature is entirely
read-side, per spec.md's ART-II framing.
**Testing**: pytest (unit + contract, mirroring this package's established in-memory-SQLite fixture
convention); Vitest + Testing Library for the two updated React screens.
**Target Platform**: Linux server (backend), browser (frontend) — unchanged.
**Project Type**: Web application (existing `src/adp/` backend + `web/` frontend split).
**Performance Goals**: No new performance surface for the heat map/enriched summary (same per-row status-
computation loop `list_objectives()` already uses, same demo-scale dataset). The orphan report's `NOT IN`
query is explicitly scoped to current demo-scale data per spec.md's Assumptions — no materialized view or
index-backed optimization in this pass.
**Constraints**: All three endpoints MUST remain ungated reads (no new `ActionType`), per spec.md FR-008
and every other rollup/aggregate endpoint already in this codebase.
**Scale/Scope**: Zero new tables. Two new Pydantic models (heat map response, per-theme row) plus 6 new
fields on the already-existing `StrategicSummaryResponse`. Two new `adp.business` read functions + 2
lightweight cross-package mirror tables. One new frontend hook set + a badge/filter addition to two
already-existing screens (`CapabilityTree.tsx`/`CapabilityNode.tsx`, `ValueStreamList.tsx`) plus a new
"Heat Map" tab on `StrategyPage.tsx`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Applies? | How this feature satisfies it |
|---|---|---|
| ART-I (SDD mandatory) | Yes | This plan, following `spec.md`, precedes all code; `/speckit-tasks` → `/speckit-implement` next. |
| ART-II (model is source of truth) | Yes | This feature is *the* embodiment of this article for this session — every number is a live query over existing typed data, zero new persisted state, zero separately-maintained rollup. |
| ART-III (machine-readable) | Yes | New/enriched response fields are typed Pydantic v2 models, `extra="forbid"`, same as every other field in these packages. |
| ART-IV (TDD) | Yes | Store/router/component tests written and confirmed red before implementation, mirroring this package's established rhythm across 915/916/917. |
| ART-V (security by design) | Yes | Threat model in spec.md; no new `ActionType`, all three endpoints ungated reads (FR-008); no new data exposure beyond already-open per-entity reads. |
| ART-VI (observability) | N/A | Pure reads, no mutation — no new `logger.info(...)` call sites needed (this package's existing convention only logs writes). |
| ART-VII (grounded AI only) | N/A | No AI-generated content anywhere in this feature's scope. |
| ART-VIII (human-in-the-loop) | N/A | No consequential/irreversible action — read-only. |
| ART-IX (provenance/auditability) | N/A | No mutation to audit — reads carry no audit obligation anywhere else in this codebase either. |
| ART-X (deterministic validation gating) | N/A | No LLM-as-a-Judge involvement. |
| ART-XI (traceability end to end) | Yes | The orphan report *is* a traceability-completeness signal by design (spec.md's stated purpose). |
| ART-XII (fixed visual language) | N/A | No diagram/theme rendering touched. |
| ART-XIII (typed contracts) | Yes | All new/enriched response shapes are Pydantic v2 models with `extra="forbid"`; heat map cells use explicit per-status fields, not a loose `dict[str, int]`. |
| ART-XIV (reproducible builds) | Yes | `adp-generate --check` run as part of Polish phase, same as every prior feature. |
| ART-XV (schema evolution governed) | Yes | Purely additive fields on an existing response model + one new response model — no breaking change, no migration at all. |
| ART-XVI (documentation as code) | N/A | No new stakeholder-facing document generator touched. |

No violations requiring justification — Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/918-strategy-rollups/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
├── contracts/            # Phase 1 output
└── tasks.md              # Phase 2 output (/speckit-tasks, not this command)
```

### Source Code (repository root)

```text
src/adp/strategy/
├── models.py             # extend: StrategicSummaryResponse gains 6 fields (5 status counts +
│                           #   initiative_count); new ThemeStatusCounts + StrategyHeatMapResponse
├── store.py               # extend: get_summary_stats() gains initiative_count (one more subquery
│                           #   column in the existing atomic _SUMMARY_STATS_SQL) + a Python-side
│                           #   per-objective status-tally pass (reusing _status_for_objective,
│                           #   list_objectives()'s own established pattern); new
│                           #   get_strategy_heatmap() reusing the same per-row status computation,
│                           #   grouped by theme
└── router.py               # extend: new GET /strategy/heatmap endpoint (optional theme_id query
                            #   param); get_summary unchanged in shape, just returns richer data

src/adp/business/
├── models.py              # extend: no new models needed -- reuses existing BusinessCapability/
│                           #   ValueStream directly for the orphan lists
├── store.py                # extend: two new lightweight read-only mirror tables
│                           #   (_strategic_objective_capabilities, _strategic_objective_value_streams,
│                           #   mirroring adp.strategy.store's own precedent for _designs/_applications
│                           #   -- same physical database, no second session needed), new
│                           #   list_orphan_capabilities()/list_orphan_value_streams()
└── router.py                # extend: new GET /business/orphans endpoint

tests/unit/strategy/test_strategy_store.py       # extend
tests/unit/business/test_business_store.py        # extend (or equivalent existing file)
tests/contract/test_strategy_api_contract.py      # extend
tests/contract/test_business_registry_api.py       # extend (or equivalent existing file)

web/src/api/strategy.ts                    # extend: richer StrategicSummary type,
                                            #   StrategyHeatMapResponse type, useStrategyHeatMap hook
web/src/api/business.ts                     # extend: OrphanReport type, useOrphanReport hook
web/src/strategy/StrategyHeatMap.tsx         # new -- theme x status grid, optional theme filter
web/src/strategy/StrategyPage.tsx            # extend: new "Heat Map" tab
web/src/business/CapabilityTree.tsx           # extend: orphan-filter toggle in toolbar, threads
                                              #   orphan-id set down to CapabilityNode
web/src/business/CapabilityNode.tsx           # extend: "no strategic linkage" badge when orphaned
web/src/business/ValueStreamList.tsx          # extend: orphan-filter toggle + badge per row
```

**Structure Decision**: No new package anywhere. `adp.strategy`'s `models.py`+`store.py`+`router.py`
total 1,889 lines pre-feature (well under the ~2,847-line split threshold); the heat map and enriched
summary are small, same-shape additions to functions that already exist there (`get_summary_stats`,
`list_objectives`'s status-computation pattern). `adp.business`'s three core files total 2,847 lines
pre-feature — right at the historical split threshold, but the orphan-report addition here is a single
small `NOT IN`-style read function pair plus two lightweight mirror tables, not a new domain concept, so
it stays in the existing files rather than triggering a new package (mirroring ADP-d8u.2's own "more of
the same" reasoning, not ADP-d8u.6's "new concept → submodule" reasoning).

## Complexity Tracking

*No violations — table intentionally empty.*
