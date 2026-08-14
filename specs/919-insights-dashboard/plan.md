# Implementation Plan: Insights Dashboard — Non-Architect Applications Heat Map

**Branch**: `919-insights-dashboard` | **Date**: 2026-08-13 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/919-insights-dashboard/spec.md`

## Summary

Add a new, non-architect-facing "Insights" screen showing every application in the portfolio as a heat-map
cell, colored by a user-selectable dimension (health score, business criticality, TIME classification, and —
only for permitted users — total cost of ownership). Implemented as a pure read-side projection: one new
endpoint on the existing `adp.portfolio` aggregator (mirroring its established raw-`sa.text()`, no-new-table
pattern) returning every application's dimension values in a single response so the frontend can switch the
coloring dimension client-side with no re-fetch, plus a new top-level nav entry and page in
`web/src/insights/`.

## Technical Context

**Language/Version**: Python 3.12 (backend); TypeScript 5.x + React 18 (frontend) — both existing stacks, no
new language/version surface.
**Primary Dependencies**: FastAPI ≥ 0.111, SQLAlchemy 2 async (Core, raw `sa.text()` mirroring
`adp.portfolio`'s own established pattern — see `src/adp/api/routers/portfolio.py`), Pydantic v2, React 18,
TanStack Query v5 — all existing project dependencies; zero new packages either side.
**Storage**: PostgreSQL 16 — no migration. The new endpoint reads the existing `applications` table
(`health_score`, `business_criticality`, `time_classification`, already present) and the existing
`application_cost` table (`tco` is a computed field on `ApplicationCost`, ADP-SPEC-038 US4) via the same
`ADP_DATABASE_URL`-backed session `adp.portfolio`'s existing endpoints already use — confirmed same physical
database as `adp.application.store`'s own session factory, so no cross-package session or mirror table is
needed (same conclusion this session reached twice before, in 917 and 918).
**Testing**: pytest (new contract tests in `tests/contract/test_portfolio_api.py`, mirroring its existing
`/summary` test shape); Vitest + Testing Library (new component tests in `web/src/insights/`, mirroring
`OverviewPage.test.tsx`'s mocked-hooks convention).
**Target Platform**: Existing ADP web app (FastAPI server + React SPA), no new platform surface.
**Project Type**: Web application (existing frontend + backend monorepo).
**Performance Goals**: SC-002 (dimension switch reflected in under 1 second) is met by construction — the
endpoint returns all dimension values for every application in one response; switching the selected dimension
is a client-side recolor with no network round-trip.
**Constraints**: The cost dimension MUST be checked against `ActionType.READ_APPLICATION_COST` per request
(FR-004) — inline inside the new endpoint via `is_permitted(user.role, ActionType.READ_APPLICATION_COST)`
(mirroring `adp.chat.tools.get_application_cost`'s existing inline-check pattern), not a static
`Depends(require_action_dep(...))` route gate, since the other three dimensions must remain open to every
authenticated user on the same request.
**Scale/Scope**: Demo-scale application portfolio (`scripts/seed_retail.py` seeds a small fixed set) — no
pagination needed for a single-response heat map.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Status | Notes |
|---|---|---|
| ART-I — Spec-Driven Development | PASS | This plan follows an approved spec (`spec.md`, checklist 100% pass). |
| ART-II — Model is Single Source of Truth | PASS | Pure read projection over existing `Application`/`ApplicationCost` records; no new table, no duplicated rollup. |
| ART-III — Everything Machine-Readable | PASS | Response is a typed Pydantic model (see `contracts/`), not free-text. |
| ART-IV — Test-Driven Development | PASS (planned) | Contract tests for the new endpoint and component tests for the new page written before implementation in `/speckit-tasks`/`/speckit-implement`. |
| ART-V — Security by Design | PASS | Threat model in spec.md; cost dimension re-checked inline per request against `READ_APPLICATION_COST`. |
| ART-VI — Observability | PASS | New endpoint inherits the app's existing structured request logging; no new AI step, so no span requirement applies. |
| ART-VII — Grounded AI Only | N/A | No AI-generated content in this feature. |
| ART-VIII — Human-in-the-Loop | N/A | Read-only feature; no consequential/write action. |
| ART-IX — Provenance and Auditability | N/A | No model mutation. |
| ART-XI — Traceability End to End | N/A | No new relationship/reference field introduced. |
| ART-XIII — Typed Contracts Everywhere | PASS | New response model uses Pydantic v2 with `extra="forbid"`, matching every existing router in this codebase. |

No violations requiring justification — Complexity Tracking table is empty.

## Project Structure

### Documentation (this feature)

```text
specs/919-insights-dashboard/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md         # Phase 1 output (/speckit.plan command)
├── quickstart.md         # Phase 1 output (/speckit.plan command)
├── contracts/             # Phase 1 output (/speckit.plan command)
└── tasks.md              # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/adp/api/routers/
└── portfolio.py                       # + GET /api/v1/portfolio/applications-heatmap

tests/contract/
└── test_portfolio_api.py              # + contract tests for the new endpoint

web/src/api/
└── portfolio.ts                       # + useApplicationsHeatmap() hook + response types

web/src/insights/                      # NEW — sibling to overview/, portfolio/, business/
├── InsightsPage.tsx                   # page shell, mirrors OverviewPage.tsx's top-level layout
├── InsightsPage.test.tsx
├── ApplicationsHeatMap.tsx            # the grid + dimension selector
└── ApplicationsHeatMap.test.tsx

web/src/shell/index.ts                 # + "insights" to the AppView union
web/src/ui/AppShell.tsx                # + "insights" nav entry in PRIMARY, sibling to Overview
web/src/App.tsx                        # + case "insights": <InsightsPage />
```

**Structure Decision**: Extend the existing `adp.portfolio` router (`src/adp/api/routers/portfolio.py`) with
one new endpoint rather than create a new backend package — it is already the established cross-domain,
no-new-table, raw-SQL-aggregate home (Ground-Truth Correction 5), and this feature adds a single endpoint, not
a new domain concept. On the frontend, create a new top-level feature folder `web/src/insights/` (not nested
inside the existing `web/src/portfolio/` folder, which is the architect-facing Portfolio Analysis screen,
ADP-SPEC-031) — matching the spec's resolved placement (`PRIMARY` nav group, sibling to Overview) and keeping
this genuinely separate, non-architect-facing screen out of an architect-facing folder.

## Complexity Tracking

*No violations — table intentionally empty.*
