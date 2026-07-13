# Implementation Plan: Portfolio Analysis Screen (ADP-SPEC-031)

**Branch**: `031-portfolio-analysis` | **Date**: 2026-07-05 | **Spec**: [spec.md](./spec.md)

## Summary

Adds a Portfolio view (fifth nav tab) with: a portfolio summary header (counts by lifecycle status + overdue), a technology landscape panel (top 50 technologies across all designs as clickable filter chips), a filtered design list (combines technology + lifecycle filters), and a cross-design dependency search. Backend is 4 read-only endpoints querying the `element_technology_tags` indexed table and `designs` lifecycle columns — no new DB tables or schema changes.

## Technical Context

**Language/Version**: Python 3.12 (backend); TypeScript 5.x + React 18 (frontend)
**Primary Dependencies**: FastAPI, SQLAlchemy 2 async (raw SQL with sa.text() for aggregates), existing stack — zero new packages
**Storage**: PostgreSQL 16; queries use existing `element_technology_tags` (B-tree + GIN indexes) and `designs` (lifecycle_status B-tree index) — no new migrations
**Testing**: pytest + FastAPI TestClient; existing contract test patterns
**Target Platform**: Same as ADP
**Performance Goals**: SC-002 — all portfolio endpoints under 2 seconds for 500 designs; indexed columns only for technology/lifecycle queries
**Constraints**: Read-only view; no editing in Portfolio screen; element name search uses JSONB (bounded by 200-result cap)
**Scale/Scope**: Up to 500 designs; top 50 technologies shown

## Constitution Check

| Article | Requirement | This Plan |
|---|---|---|
| ART-I | Spec-driven | Plan derived from spec.md ✅ |
| ART-II | Model is source of truth | Portfolio derives from canonical model + derived indexes; no new separate portfolio store ✅ |
| ART-IV | TDD | Contract tests before implementation ✅ |
| ART-V | Security | Auth required on all portfolio endpoints ✅ |
| ART-XIII | Typed contracts | `TechnologyCount`, `PortfolioDesignSummary`, `PortfolioSummary` typed Pydantic models ✅ |

## File Changes

| File | Action |
|---|---|
| `src/adp/api/routers/portfolio.py` | CREATE — 4 read-only endpoints |
| `src/adp/api/app.py` | EDIT — register portfolio router |
| `tests/contract/test_portfolio_api.py` | CREATE — contract tests |
| `web/src/api/portfolio.ts` | CREATE — TypeScript interfaces + TanStack Query hooks |
| `web/src/portfolio/PortfolioPage.tsx` | CREATE — main layout |
| `web/src/portfolio/TechnologyLandscape.tsx` | CREATE — chip grid |
| `web/src/portfolio/PortfolioDesignList.tsx` | CREATE — filtered design list |
| `web/src/portfolio/DependencySearch.tsx` | CREATE — search input + results |
| `web/src/shell/NavBar.tsx` | EDIT — add "Portfolio" fifth tab |
| `web/src/shell/index.ts` | EDIT — re-export updated AppView type |
| `web/src/App.tsx` | EDIT — add "portfolio" to AppView + render PortfolioPage |

## Phase 1: Backend Portfolio API

**Goal**: 4 read-only endpoints, all using indexed columns.

### Tests first (TDD — ART-IV)

- [ ] Write `tests/contract/test_portfolio_api.py`: `test_technologies_returns_aggregated_counts()` — seed element_technology_tags with 3 designs using "Kafka" and 2 using "RabbitMQ"; GET /api/v1/portfolio/technologies; assert Kafka count=3, RabbitMQ count=2
- [ ] Write `test_portfolio_designs_filter_by_technology()` — seed tags; GET with `?technology=Kafka`; assert only Kafka designs returned
- [ ] Write `test_portfolio_designs_filter_by_status()` — seed designs with different statuses; GET with `?status=current`; assert only current designs
- [ ] Write `test_portfolio_search_finds_matching_designs()` — seed tags with technology="Kong"; GET `?q=Kong`; assert matching designs returned
- [ ] Write `test_portfolio_summary_returns_correct_counts()` — seed 3 draft + 2 current; GET /summary; assert by_status matches
- [ ] Write `test_portfolio_search_requires_min_2_chars()` — GET `?q=K`; assert 422

### Implementation

- [ ] Create `src/adp/api/routers/portfolio.py` with:
  - `TechnologyCountResponse`, `PortfolioDesignSummaryResponse`, `PortfolioSummaryResponse` Pydantic models
  - `GET /api/v1/portfolio/technologies` — raw SQL aggregate on `element_technology_tags`, returns top 50
  - `GET /api/v1/portfolio/designs` — JOIN `element_technology_tags` + `designs` with optional technology ILIKE + status filter; returns `PortfolioDesignSummaryResponse` list
  - `GET /api/v1/portfolio/search` — two-stage: tags table technology match + JSONB element name match; merge; cap 200; return `matched_elements` in each result
  - `GET /api/v1/portfolio/summary` — GROUP BY on `designs.lifecycle_status` + overdue count
  - All endpoints use `Depends(_get_db_session)` from `adp.api.deps` (shared pool, no new connections)
- [ ] Register `portfolio.router` in `src/adp/api/app.py`

**Checkpoint**: All portfolio contract tests pass.

## Phase 2: Frontend Portfolio Screen

**Goal**: Portfolio tab with summary header, technology landscape, filtered design list, dependency search.

- [ ] Create `web/src/api/portfolio.ts` — TypeScript interfaces (`TechnologyCount`, `PortfolioDesignSummary`, `PortfolioSummary`) + hooks (`usePortfolioTechnologies()`, `usePortfolioDesigns(technology?, status?)`, `usePortfolioSearch(q, enabled)`, `usePortfolioSummary()`)
- [ ] Create `web/src/portfolio/TechnologyLandscape.tsx` — renders technology chips sorted by count; active chip highlighted; onClick calls `onTechnologySelect(tech)`
- [ ] Create `web/src/portfolio/PortfolioDesignList.tsx` — design list with lifecycle badge, overdue indicator, primary technology tag, Open button; empty state when no matches
- [ ] Create `web/src/portfolio/DependencySearch.tsx` — text input + debounced search (300ms); shows matched_elements per result; clear button
- [ ] Create `web/src/portfolio/PortfolioPage.tsx` — orchestrates all panels; manages `activeTechnology` + `activeStatus` + `searchQuery` state; summary header at top; technology landscape + filter controls in middle; design list / search results at bottom
- [ ] Edit `web/src/shell/NavBar.tsx` — add `"portfolio"` to `AppView` type and NAV_ITEMS array with label "Portfolio"
- [ ] Edit `web/src/App.tsx` — extend `AppView` type, add `portfolio` view, render `<PortfolioPage>` when `view === "portfolio"`
- [ ] Run `cd web && npx tsc --noEmit` — TypeScript clean

## Phase 3: Polish

- [ ] Run `pytest tests/ --ignore=tests/integration -q --no-cov` — full suite passes
- [ ] Run `ruff check src/adp/api/routers/portfolio.py` — clean
- [ ] Run `cd web && npx tsc --noEmit` — zero errors
- [ ] Manual E2E: navigate to Portfolio tab; verify summary counts; click a technology chip; verify design list filters; try dependency search for a known element name; verify results

## Constitution Compliance

- **ART-II** ✅ All portfolio data sourced from canonical model and derived indexes — no separate portfolio store
- **ART-IV** ✅ Contract tests written before implementation
- **ART-XIII** ✅ All response shapes are typed Pydantic models (backend) and TypeScript interfaces (frontend)

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

[Extract from feature spec: primary requirement + technical approach from research]

## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.
-->

**Language/Version**: [e.g., Python 3.11, Swift 5.9, Rust 1.75 or NEEDS CLARIFICATION]  
**Primary Dependencies**: [e.g., FastAPI, UIKit, LLVM or NEEDS CLARIFICATION]  
**Storage**: [if applicable, e.g., PostgreSQL, CoreData, files or N/A]  
**Testing**: [e.g., pytest, XCTest, cargo test or NEEDS CLARIFICATION]  
**Target Platform**: [e.g., Linux server, iOS 15+, WASM or NEEDS CLARIFICATION]
**Project Type**: [e.g., library/cli/web-service/mobile-app/compiler/desktop-app or NEEDS CLARIFICATION]  
**Performance Goals**: [domain-specific, e.g., 1000 req/s, 10k lines/sec, 60 fps or NEEDS CLARIFICATION]  
**Constraints**: [domain-specific, e.g., <200ms p95, <100MB memory, offline-capable or NEEDS CLARIFICATION]  
**Scale/Scope**: [domain-specific, e.g., 10k users, 1M LOC, 50 screens or NEEDS CLARIFICATION]

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

[Gates determined based on constitution file]

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)
<!--
  ACTION REQUIRED: Replace the placeholder tree below with the concrete layout
  for this feature. Delete unused options and expand the chosen structure with
  real paths (e.g., apps/admin, packages/something). The delivered plan must
  not include Option labels.
-->

```text
# [REMOVE IF UNUSED] Option 1: Single project (DEFAULT)
src/
├── models/
├── services/
├── cli/
└── lib/

tests/
├── contract/
├── integration/
└── unit/

# [REMOVE IF UNUSED] Option 2: Web application (when "frontend" + "backend" detected)
backend/
├── src/
│   ├── models/
│   ├── services/
│   └── api/
└── tests/

frontend/
├── src/
│   ├── components/
│   ├── pages/
│   └── services/
└── tests/

# [REMOVE IF UNUSED] Option 3: Mobile + API (when "iOS/Android" detected)
api/
└── [same as backend above]

ios/ or android/
└── [platform-specific structure: feature modules, UI flows, platform tests]
```

**Structure Decision**: [Document the selected structure and reference the real
directories captured above]

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
