# Tasks: Portfolio Analysis Screen (ADP-SPEC-031)

**Feature**: Portfolio Analysis Screen
**Branch**: `031-portfolio-analysis`
**Prerequisites**: ADP-SPEC-029 (element_technology_tags table) ✅, ADP-SPEC-030 (designs.lifecycle_status column) ✅

---

## Phase 1: Foundational — Backend Portfolio API

*All 4 portfolio endpoints serve as the data foundation for all 4 user stories. Must complete before any frontend work.*

### Tests (TDD — ART-IV)

- [X] T001 [P] Create `tests/contract/test_portfolio_api.py` — `test_technologies_returns_aggregated_counts()`: seed 3 `element_technology_tags` rows with `technology="Kafka"` (different design_ids) and 2 with `technology="RabbitMQ"`; GET `/api/v1/portfolio/technologies`; assert response contains `{"technology": "Kafka", "design_count": 3}` and `{"technology": "RabbitMQ", "design_count": 2}` sorted by count descending
- [X] T002 [P] Write `test_portfolio_designs_filter_by_technology()` in `tests/contract/test_portfolio_api.py`: seed tags; GET `/api/v1/portfolio/designs?technology=Kafka`; assert only designs with Kafka tags returned; assert `primary_technology` field present
- [X] T003 [P] Write `test_portfolio_designs_filter_by_status()` in `tests/contract/test_portfolio_api.py`: seed designs with `lifecycle_status='current'` and `lifecycle_status='draft'`; GET `/api/v1/portfolio/designs?status=current`; assert only current designs returned
- [X] T004 [P] Write `test_portfolio_designs_combined_filter()`: GET with both `?technology=Kong&status=current`; assert only designs matching both criteria returned
- [X] T005 [P] Write `test_portfolio_search_finds_by_technology()` in `tests/contract/test_portfolio_api.py`: seed tags with `technology="Kong API Gateway"`; GET `/api/v1/portfolio/search?q=Kong`; assert matching design in results with `matched_elements` list populated
- [X] T006 [P] Write `test_portfolio_search_requires_min_2_chars()`: GET `/api/v1/portfolio/search?q=K`; assert 422
- [X] T007 [P] Write `test_portfolio_summary_returns_correct_counts()`: seed 3 designs as draft and 2 as current; GET `/api/v1/portfolio/summary`; assert `by_status.draft == 3` and `by_status.current == 2`

### Implementation

- [X] T008 Create `src/adp/api/routers/portfolio.py` with Pydantic response models: `TechnologyCountItem(technology: str, design_count: int)`, `TechnologiesResponse(technologies: list[TechnologyCountItem], total_unique: int)`, `PortfolioDesignSummary(id, title, lifecycle_status, overdue_review, element_count, primary_technology)`, `PortfolioDesignsResponse(designs: list, total, page, page_size)`, `PortfolioSearchResult(id, title, lifecycle_status, overdue_review, element_count, primary_technology, matched_elements: list[str])`, `PortfolioSearchResponse(designs: list, total, truncated: bool)`, `PortfolioSummaryResponse(total_designs, by_status: dict, overdue_review_count)`
- [X] T009 Implement `GET /api/v1/portfolio/technologies` in `src/adp/api/routers/portfolio.py` — raw SQL: `SELECT technology, COUNT(DISTINCT design_id) AS design_count FROM element_technology_tags WHERE technology IS NOT NULL GROUP BY technology ORDER BY design_count DESC LIMIT 50`; use `Depends(_get_kb_session)` from `adp.api.deps`; return `TechnologiesResponse`
- [X] T010 Implement `GET /api/v1/portfolio/designs` with optional `technology: str | None` and `status: str | None` query params — SQL JOINs `element_technology_tags` and `designs` using indexed columns: `SELECT DISTINCT d.id, d.title, d.lifecycle_status, d.review_due FROM designs d LEFT JOIN element_technology_tags ett ON d.id = ett.design_id WHERE ($technology IS NULL OR ett.technology ILIKE '%' || $technology || '%') AND ($status IS NULL OR d.lifecycle_status = $status)`; loads element count from design JSONB for matched rows; returns paginated `PortfolioDesignsResponse`
- [X] T011 Implement `GET /api/v1/portfolio/search` with required `q: str = Query(min_length=2)` — two-stage: (1) query `element_technology_tags WHERE technology ILIKE '%q%'`, (2) load matching designs and check element names in JSONB; merge results, cap at 200, return `PortfolioSearchResponse` with `matched_elements` strings like `"ElementName (technology: Kong)"`
- [X] T012 Implement `GET /api/v1/portfolio/summary` — SQL: `SELECT lifecycle_status, COUNT(*) FROM designs GROUP BY lifecycle_status` plus separate `COUNT(*) WHERE lifecycle_status='current' AND review_due < now()`; return `PortfolioSummaryResponse`
- [X] T013 Register `portfolio.router` (prefix `/api/v1/portfolio`, tags `["portfolio"]`) in `src/adp/api/app.py`
- [X] T014 [P] Run `pytest tests/contract/test_portfolio_api.py -q --no-cov` — all 7 tests pass

**Checkpoint**: All 4 portfolio endpoints return correct responses.

---

## Phase 2: US1 — Technology Landscape

*P1. Architect sees top technologies across portfolio as clickable filter chips. Clicking filters the design list.*

**Independent test criteria**: Technology landscape panel shows "Kafka (7)" chip; clicking it filters the design list to only Kafka designs; clicking again deselects.

- [X] T015 [P] [US1] Create `web/src/api/portfolio.ts` — TypeScript interfaces for all API responses (`TechnologyCount`, `PortfolioDesignSummary`, `PortfolioSearchResult`, `PortfolioSummary`) plus hooks: `usePortfolioTechnologies()`, `usePortfolioDesigns(technology?: string, status?: string, page?: number)`, `usePortfolioSearch(q: string, enabled: boolean)`, `usePortfolioSummary()`; all use `apiGet` from `../api/client`
- [X] T016 [US1] Create `web/src/portfolio/TechnologyLandscape.tsx` — accepts `technologies: TechnologyCount[]`, `activeTechnology: string | null`, `onSelect: (tech: string | null) => void` props; renders chips as `<button>` elements styled as coloured pills (blue when active, grey-outline when inactive); shows count badge per chip; empty state when no technologies; loading skeleton

**Checkpoint**: `TechnologyLandscape` renders chips; clicking sets active technology.

---

## Phase 3: US2 — Combined Technology + Lifecycle Filter

*P1. Architect can filter portfolio by technology AND lifecycle status simultaneously. Design list updates instantly.*

**Independent test criteria**: Select "Current" status + click "Kong" technology chip; design list shows only current designs using Kong; clearing either filter expands results accordingly.

- [X] T017 [US2] Create `web/src/portfolio/PortfolioDesignList.tsx` — accepts `designs: PortfolioDesignSummary[]`, `isLoading: boolean`, `onSelectDesign: (id: string) => void` props; renders design rows with lifecycle status badge (reuses colour map from ADP-SPEC-030), "⚠ Review overdue" amber chip when `overdue_review=true`, primary technology tag chip, element count, and "Open" button; empty state "No designs match these filters"; loading skeleton rows

---

## Phase 4: US3+US4 — Dependency Search + Summary Header

*US3 (P2): Cross-design element search. US4 (P2): Portfolio health summary. Grouped as both are smaller independent panels.*

**Independent test criteria (US3)**: Typing "Auth Service" in dependency search shows all designs containing matching elements with matched_elements highlighted. **Independent test criteria (US4)**: Summary header shows `Draft: 3 / Proposed: 1 / Current: 8` etc.

- [X] T018 [P] [US3] Create `web/src/portfolio/DependencySearch.tsx` — text input with 300ms debounce; calls `usePortfolioSearch(q, q.length >= 2)`; renders result list showing design title, lifecycle badge, and `matched_elements` as grey sub-text; "Clear" button resets input; shows "Type at least 2 characters" hint when input too short; "No matches found" empty state
- [X] T019 [P] [US4] Create `web/src/portfolio/PortfolioSummaryHeader.tsx` — fetches via `usePortfolioSummary()`; displays total designs + 5 status count chips (draft=grey, proposed=blue, current=green, deprecated=amber, decommissioned=red); shows overdue review count as separate amber badge if >0; loading skeleton; each status chip is clickable to apply that lifecycle filter (calls `onStatusSelect(status)`)

---

## Phase 5: Portfolio Page + App Integration

*Assembles all panels and wires navigation.*

- [X] T020 Create `web/src/portfolio/PortfolioPage.tsx` — orchestrates all panels; state: `activeTechnology: string | null`, `activeStatus: string`, `searchMode: boolean`, `searchQuery: string`; layout: (1) `<PortfolioSummaryHeader onStatusSelect={setActiveStatus} />` at top, (2) filter bar with lifecycle dropdown + "Search" toggle button, (3) when `!searchMode`: `<TechnologyLandscape>` + `<PortfolioDesignList>`, when `searchMode`: `<DependencySearch>`; "Open design" callback calls `onSelectDesign(id)` which sets `currentDesignId` and navigates to "intake"; accepts `onNavigate: (view: AppView) => void` and `onSelectDesign: (id: string) => void` props; a "Governance Report" button (`onNavigate("governance")`) for ADP-SPEC-032 integration
- [X] T021 Edit `web/src/shell/NavBar.tsx` — add `"portfolio"` to `AppView` type and add `{ view: "portfolio", label: "Portfolio" }` to `DESIGN_TABS` array (appears after Knowledge)
- [X] T022 Edit `web/src/shell/index.ts` — re-export updated `AppView` type (no code change needed if the type is inferred from NavBar.tsx)
- [X] T023 Edit `web/src/App.tsx` — extend `AppView` union type to include `"portfolio"`; import `PortfolioPage`; add render branch: `if (view === "portfolio") return <PortfolioPage onNavigate={onNavigate} onSelectDesign={onSelectDesign} />`
- [X] T024 [P] Run `cd web && npx tsc --noEmit` — zero TypeScript errors

---

## Phase 6: Polish

- [X] T025 [P] Run `pytest tests/ --ignore=tests/integration -q --no-cov` — full suite passes
- [X] T026 [P] Run `ruff check src/adp/api/routers/portfolio.py` — zero errors
- [X] T027 [P] Run `cd web && npx tsc --noEmit` — final TypeScript confirmation
- [X] T028 Manual E2E: start server; navigate to Portfolio tab; verify summary header shows design counts by status; verify technology landscape shows technologies from seeded data; click a technology chip; verify design list filters; click "Search" mode; type a known element name; verify dependency search results; verify "Open" button navigates to that design's Intake view

---

## Dependencies

```
T001–T007 (tests) can be written in parallel with T008–T013 (implementation) since they mock the DB
T008 → T009, T010, T011, T012     (models before endpoints)
T013 (register router) → T014     (router must exist before tests run against live app)
T014 (all backend tests pass) → T015 (frontend API hooks)
T015 → T016, T017, T018, T019     (TypeScript types needed before components)
T016, T017, T018, T019 → T020    (all sub-components before PortfolioPage)
T020, T021 → T023                  (PortfolioPage + NavBar before App.tsx wiring)
T023 → T024                        (TypeScript check after all changes)
```

## Parallel Opportunities

- T001–T007 (contract tests) can all be written simultaneously
- T015 (API hooks) and T016 (TechnologyLandscape) are independent files — parallel
- T018 (DependencySearch) and T019 (SummaryHeader) are independent files — parallel
- T025, T026, T027 (polish checks) all run independently

## Implementation Strategy (MVP)

**MVP = Phase 1 + Phase 2 + Phase 3 (T001–T017)**

Delivers: Portfolio tab exists with working backend; architects can see technology landscape and filter designs by technology + lifecycle status. Dependency search (US3) and summary header (US4) follow as fast increments since the backend endpoints are already complete.
