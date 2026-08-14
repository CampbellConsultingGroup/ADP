# Tasks: Insights Dashboard — Non-Architect Applications Heat Map

**Input**: Design documents from `/specs/919-insights-dashboard/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Mandatory for all ADP features (ART-IV). Test tasks appear before their implementation
counterparts in every user-story phase and MUST be verified to fail before implementation begins.

**Organization**: Grouped by user story (spec.md) to enable independent implementation and testing of each.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 / US2 / US3, per spec.md's priorities (P1/P2/P3)

## Path Conventions

Extends existing files only, no new backend package, no migration (plan.md's Structure Decision):
- Backend: `src/adp/api/routers/portfolio.py` (extend — response models live directly in this router file,
  matching its existing convention, no separate `models.py`)
- Backend tests: `tests/contract/test_portfolio_api.py` (extend)
- Frontend: `web/src/api/portfolio.ts` (extend), `web/src/insights/` (new), `web/src/shell/index.ts` (extend),
  `web/src/ui/AppShell.tsx` (extend), `web/src/App.tsx` (extend)

---

## Phase 1: Setup

- [X] T001 Run `pytest tests/contract/test_portfolio_api.py -q` and `cd web && npx vitest run` to confirm a
  clean, fully-green baseline before any change (no code changes in this task)

---

## Phase 2: Foundational

**Not applicable** — this feature adds no table and no migration (data-model.md: pure projection over
existing `applications`/`application_cost`). The only sequencing constraint is file-level: US1 and US2 both
extend `src/adp/api/routers/portfolio.py` and `web/src/api/portfolio.ts` (US1 adds the endpoint/hook, US2
adds fields to the same response), and US3 touches entirely separate files (`shell/index.ts`, `AppShell.tsx`,
`App.tsx`) so it can proceed independently of US1/US2's completion status.

---

## Phase 3: User Story 1 - See portfolio health at a glance (Priority: P1) 🎯 MVP

**Goal**: Every application in the portfolio renders as one heat-map cell, colored by health score by
default, with unscored applications visually distinct and a clear empty state when the portfolio is empty.

**Independent Test**: Seed applications spanning the full health-score range plus one with no score set;
load the dashboard; confirm every application appears exactly once, correctly shaded, with the unscored one
visually distinct (quickstart.md scenario 1).

### Tests for User Story 1 (MANDATORY — ART-IV, write first, confirm failing)

- [X] T002 [P] [US1] Contract test for `GET /api/v1/portfolio/applications-heatmap` in
  `tests/contract/test_portfolio_api.py`: every seeded application appears exactly once in `items`, with
  `id`/`name`/`health_score`/`business_criticality`/`time_classification` reflecting real seeded data, and an
  unscored application's fields are `null` (never a false default)
- [X] T003 [P] [US1] Component test for `ApplicationsHeatMap.tsx` in a new
  `web/src/insights/ApplicationsHeatMap.test.tsx`: renders one cell per mocked application colored by
  `health_score`, an application with `health_score: null` renders with a distinct "unclassified" treatment,
  and zero applications renders an empty-state message

### Implementation for User Story 1

- [X] T004 [P] [US1] Add `ApplicationHeatmapEntry` (`id`, `name`, `health_score`, `business_criticality`,
  `time_classification`) and `ApplicationHeatmapResponse` (`items`) Pydantic models to
  `src/adp/api/routers/portfolio.py` (data-model.md; `cost`/`cost_permitted` land in US2, not here) (depends
  on T002 being red)
- [X] T005 [US1] Implement `GET /applications-heatmap` in `src/adp/api/routers/portfolio.py`: a raw
  `sa.text()` query against `applications`, ordered by name (research.md Decision 5) — make T002 pass
  (depends on T004)
- [X] T006 [P] [US1] Add `ApplicationHeatmapEntry`/`ApplicationHeatmapResponse` TS types and a
  `useApplicationsHeatmap()` hook to `web/src/api/portfolio.ts`, mirroring `usePortfolioSummary()`'s existing
  shape
- [X] T007 [P] [US1] Create `web/src/insights/ApplicationsHeatMap.tsx` — a grid with one cell per
  application, shaded on a fixed health-score gradient, unscored applications rendered in a distinct
  "unclassified" treatment, and an empty-state message when there are zero applications — make T003 pass
  (depends on T006)
- [X] T008 [US1] Create `web/src/insights/InsightsPage.tsx` — page shell rendering `ApplicationsHeatMap`,
  mirroring `OverviewPage.tsx`'s top-level layout conventions (depends on T007)
- [X] T009 [P] [US1] Component test for `InsightsPage.tsx` in a new `web/src/insights/InsightsPage.test.tsx`:
  renders the page heading and the heat map

**Checkpoint**: User Story 1 fully functional and independently testable — quickstart.md scenario 1.

---

## Phase 4: User Story 2 - Change what the color means (Priority: P2)

**Goal**: A dimension selector lets the user recolor the same heat map by business criticality, TIME
classification, or (only if permitted) cost — client-side, with no navigation.

**Independent Test**: With the same seeded applications, switch the dimension selector through each open
option and confirm cell coloring changes accordingly; confirm "cost" is present/absent based on the caller's
`READ_APPLICATION_COST` permission (quickstart.md scenario 2).

### Tests for User Story 2 (MANDATORY — ART-IV)

- [X] T010 [P] [US2] Extend the contract test in `tests/contract/test_portfolio_api.py`: response includes
  `cost` (per item) and `cost_permitted` (top-level); for a caller without `READ_APPLICATION_COST`, every
  item's `cost` is `null` and `cost_permitted` is `false`; for a caller with it, `cost` reflects the seeded
  application's `ApplicationCost.tco` and `cost_permitted` is `true` — mirrors
  `application/router.py`'s own `_require_cost_read` contract-test convention
- [X] T011 [P] [US2] Extend `ApplicationsHeatMap.test.tsx`: selecting each dimension in the selector recolors
  the mocked cells accordingly; "cost" is absent from the selector when the mocked response has
  `cost_permitted: false`, present when `true`

### Implementation for User Story 2

- [X] T012 [US2] Add `cost`/`cost_permitted` fields to `ApplicationHeatmapEntry`/`ApplicationHeatmapResponse`
  in `src/adp/api/routers/portfolio.py`; extend the `GET /applications-heatmap` handler to join
  `application_cost` (`tco`, research.md Decision 4) and check `is_permitted(user.role,
  ActionType.READ_APPLICATION_COST)` inline via the existing `get_current_user` dependency (research.md
  Decision 2) — make T010 pass (depends on T004, T005; T010 being red)
- [X] T013 [P] [US2] Extend the TS types and `useApplicationsHeatmap()` hook in `web/src/api/portfolio.ts`
  with `cost`/`cost_permitted` (depends on T006)
- [X] T014 [US2] Add a dimension selector to `web/src/insights/ApplicationsHeatMap.tsx` — switches which
  field colors each cell client-side (no re-fetch, per research.md Decision 3), omitting "cost" from the
  option list when `cost_permitted` is `false` — make T011 pass (depends on T007, T013)

**Checkpoint**: User Stories 1 and 2 both independently functional — quickstart.md scenario 2.

---

## Phase 5: User Story 3 - Find the dashboard without being an architect (Priority: P3)

**Goal**: A new top-level navigation entry, grouped with Overview rather than the architecture-domain
section, opens the dashboard.

**Independent Test**: From a fresh app load, confirm a new nav entry appears alongside Overview (not under
Architecture) and opens the dashboard (quickstart.md scenario 3, browser walkthrough).

### Tests for User Story 3 (MANDATORY — ART-IV)

- [X] T015 [P] [US3] Component test in a new `web/src/ui/AppShell.test.tsx`: the `PRIMARY` nav group renders
  an "Insights" entry alongside "Overview" (not inside the Architecture group), and clicking it calls
  `onNavigate("insights")`

### Implementation for User Story 3

- [X] T016 [US3] Add `"insights"` to the `AppView` union in `web/src/shell/index.ts`
- [X] T017 [US3] Add an `"insights"` entry (label "Insights") to `PRIMARY` in `web/src/ui/AppShell.tsx`,
  sibling to `"overview"`, plus its `TITLES` entry — make T015 pass (depends on T016)
- [X] T018 [US3] Wire `case "insights": return <InsightsPage onNavigate={onNavigate} />;` into
  `renderPage()` in `web/src/App.tsx` (depends on T008, T016)

**Checkpoint**: All three user stories independently functional — quickstart.md scenario 3 + full browser
walkthrough.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T019 [P] Confirm `adp-generate --check` remains clean (this feature touches no `models.py`/canonical
  schema, but the CI gate must still be re-verified unaffected)
- [X] T020 Run the full regression suite: `pytest tests/ --ignore=tests/integration -q` and
  `cd web && npx vitest run && npx tsc --noEmit`
- [X] T021 Manually walk through all quickstart.md scenarios against a running local stack
  (`ADP_AUTH_ENABLED=false` for the open-dimension path; a non-cost-permitted role for the gated path), plus
  the full browser walkthrough (nav entry, default coloring, dimension switching, unclassified treatment,
  empty state)
- [X] T022 Replace the auto-generated `919-insights-dashboard` stub line in `CLAUDE.md` (and the matching
  `AGENTS.md` "Latest work"/"Prior work:" shift) with a proper hand-written narrative at commit time

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — a single baseline-verification task, no code change.
- **Foundational (Phase 2)**: Not applicable — no schema change, nothing blocks any user story.
- **User Stories (Phase 3–5)**: US1 and US2 share two files (`portfolio.py`, `portfolio.ts`) — US2's tasks
  extend the same response model/hook US1 creates, so US2 must follow US1 in practice even though both are
  "independent" in the sense that each is separately testable and delivers standalone value. **US3 has zero
  file overlap with US1/US2** and can proceed fully in parallel with either.
- **Polish (Phase 6)**: Depends on all three user stories being complete.

### Within Each User Story

- Tests written and confirmed failing before implementation (ART-IV).
- Models before store/handler logic; backend endpoint before frontend hook; hook before UI component; UI
  component before page wiring.

### Parallel Opportunities

- Within US1: T002/T003 in parallel; T004 blocks T005; T006 in parallel with T004/T005 (different file);
  T007 depends on T006; T008 depends on T007; T009 last.
- Within US2: T010/T011 in parallel; T012 depends on T010 (and on US1's T004/T005 already landing); T013 in
  parallel with T012; T014 depends on T007 and T013.
- Within US3: T015 alone; T016 blocks T017; T018 depends on T016 and US1's T008.
- **US3's entire phase (T015–T018) can run fully in parallel with US1's and US2's phases** — it touches only
  `shell/index.ts`, `AppShell.tsx`, and `App.tsx`, zero overlap with the backend or `portfolio.ts`/
  `insights/` files (T018's `<InsightsPage />` reference is the one integration point, safe to stub until
  T008 lands).

---

## Parallel Example: User Story 3 (fully independent of US1/US2's own internal sequencing)

```bash
# Test:
Task: "Component test for the new Insights nav entry in web/src/ui/AppShell.test.tsx"

# Once red, implementation:
Task: "Add 'insights' to the AppView union in web/src/shell/index.ts"
Task: "Add the Insights nav entry to PRIMARY in web/src/ui/AppShell.tsx"
Task: "Wire case 'insights' into web/src/App.tsx"
```

## Implementation Strategy

**MVP = User Story 1 only** (T001–T009): a health-score-colored applications heat map, fully standalone and
independently demoable, delivers the core "portfolio at a glance" value even without the dimension selector
(US2) or top-level nav placement (US3, though without US3 the page would only be reachable by direct code
change — US3 is low-effort enough that it is reasonable to ship alongside US1 in practice, but remains
logically separable per the spec's own priority ordering).
