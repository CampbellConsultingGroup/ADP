# Tasks: Strategy Rollups — Heat Map, Orphan Report, Richer Summary

**Input**: Design documents from `/specs/918-strategy-rollups/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Mandatory for all ADP features (ART-IV). Test tasks appear before their implementation
counterparts in every user-story phase and MUST be verified to fail before implementation begins.

**Organization**: Grouped by user story (spec.md) to enable independent implementation and testing of
each.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 / US2 / US3, per spec.md's priorities (P1/P2/P3)

## Path Conventions

Extends existing files only, no new package, no migration (plan.md's Structure Decision):
- Backend: `src/adp/strategy/{models,store,router}.py` (extend), `src/adp/business/{models,store,
  router}.py` (extend)
- Backend tests: `tests/unit/strategy/test_strategy_store.py` (extend), `tests/unit/business/
  test_orphans.py` (new), `tests/contract/{test_strategy_api_contract,test_business_registry_api}.py`
  (extend)
- Frontend: `web/src/api/{strategy,business}.ts` (extend), `web/src/strategy/` (new tab component),
  `web/src/business/` (extend existing screens), `web/src/overview/OverviewPage.tsx` (extend)

---

## Phase 1: Setup

- [X] T001 Run `pytest tests/unit/strategy/ tests/unit/business/ tests/contract/test_strategy_api_contract.py tests/contract/test_business_registry_api.py -q` to confirm a clean, fully-green baseline before any change (no code changes in this task — establishes the starting point research.md's decisions build on)

---

## Phase 2: Foundational

**Not applicable** — this feature adds no tables and no migration (spec.md's Key Entities are explicitly
derived/non-persisted). All three user stories touch independent functions across `adp.strategy` (US1,
US3) and `adp.business` (US2) and can proceed in any order or in parallel; the only sequencing
constraint is file-level (US1 and US3 both edit `src/adp/strategy/store.py`, in different functions —
see Parallel Opportunities below).

---

## Phase 3: User Story 1 - See objective health across every theme at a glance (Priority: P1) 🎯 MVP

**Goal**: A strategy lead opens a new "Heat Map" tab and sees every theme as a row, objective counts per
status as columns, with an optional theme filter.

**Independent Test**: Seed objectives across several themes and every status (including a zero-objective
theme), open the Heat Map tab, confirm every theme appears with correct counts and the zero-objective
theme shows an all-zero row, then apply the theme filter (quickstart.md scenario 2).

### Tests for User Story 1 (MANDATORY — ART-IV, write first, confirm failing)

- [X] T002 [P] [US1] Unit tests for `get_strategy_heatmap()` in `tests/unit/strategy/
  test_strategy_store.py`: every theme appears exactly once with correct per-status counts, a
  zero-objective theme shows an all-zero row (not omitted), the `theme_id` filter narrows the result to
  one row, and the grand total across every cell equals `total_objectives`
- [X] T003 [US1] Contract test for `GET /api/v1/strategy/heatmap` (with and without `theme_id`) in
  `tests/contract/test_strategy_api_contract.py`: 200 with `StrategyHeatMapResponse` shape reflecting
  real seeded objectives/themes/statuses

### Implementation for User Story 1

- [X] T004 [P] [US1] Add `ThemeStatusCounts` and `StrategyHeatMapResponse` Pydantic models to
  `src/adp/strategy/models.py` (data-model.md) (depends on T002 being red)
- [X] T005 [US1] Implement `get_strategy_heatmap(session, theme_id=None)` in
  `src/adp/strategy/store.py`, reusing the existing `_status_for_objective` helper per objective
  (research.md Decision 1) — make T002 pass (depends on T004)
- [X] T006 [US1] Implement `GET /strategy/heatmap` in `src/adp/strategy/router.py` — make T003 pass
  (depends on T005)
- [X] T007 [P] [US1] Add `ThemeStatusCounts`/`StrategyHeatMapResponse` TS types and a
  `useStrategyHeatMap(themeId?)` hook to `web/src/api/strategy.ts`
- [X] T008 [P] [US1] Create `web/src/strategy/StrategyHeatMap.tsx` — a theme × status grid with an
  optional theme-filter dropdown, matching `specs/043-capability-heat-map/`'s established heat-map
  visual convention where applicable
- [X] T009 [US1] Wire a new "Heat Map" tab into `web/src/strategy/StrategyPage.tsx` alongside
  Objectives/Themes/Initiatives, rendering `StrategyHeatMap` (depends on T007, T008)
- [X] T010 [P] [US1] Component test for `StrategyHeatMap.tsx` in a new
  `web/src/strategy/StrategyHeatMap.test.tsx`: renders every theme row, applying the theme filter calls
  the hook with the selected id, zero-objective theme renders an all-zero row

**Checkpoint**: User Story 1 fully functional and independently testable — quickstart.md scenario 2.

---

## Phase 4: User Story 2 - Find capabilities and value streams with no strategic backing (Priority: P2)

**Goal**: A "no strategic linkage" badge appears on every orphaned capability/value-stream row on the
existing Capability Map and Value Streams screens, plus a toggle to filter each screen to orphans only.

**Independent Test**: Seed a mix of linked/unlinked capabilities and value streams, open the Capability
Map, confirm only unlinked ones show the badge, toggle the orphan filter and confirm only those remain;
repeat for Value Streams (quickstart.md scenario 3).

### Tests for User Story 2 (MANDATORY — ART-IV)

- [X] T011 [P] [US2] Unit tests for `list_orphan_capabilities()`/`list_orphan_value_streams()` in a new
  `tests/unit/business/test_orphans.py`: a capability/value-stream with a real link row is excluded, one
  with zero link rows is included, and the result is empty once everything is linked
- [X] T012 [US2] Contract test for `GET /api/v1/business/orphans` in
  `tests/contract/test_business_registry_api.py`: 200 with `OrphanReportResponse` reflecting real
  strategy-scoped link rows (extend the fixture with a strategy-scoped engine + `_strategic_objective_
  capabilities`/`_strategic_objective_value_streams` mirror tables, mirroring the cross-package fixture
  pattern already established in `test_designs_api.py`/`test_application_registry_api.py` for ADP-d8u.2)

### Implementation for User Story 2

- [X] T013 [P] [US2] Add `_strategic_objective_capabilities` and `_strategic_objective_value_streams`
  read-only `sa.Table` mirrors to `src/adp/business/store.py` (data-model.md, research.md Decision 4)
  (depends on T011 being red)
- [X] T014 [US2] Implement `list_orphan_capabilities()`/`list_orphan_value_streams()` in
  `src/adp/business/store.py` — make T011 pass (depends on T013)
- [X] T015 [P] [US2] Add `OrphanReportResponse` Pydantic model to `src/adp/business/models.py` (reuses
  the existing `BusinessCapability`/`ValueStream` models as list items, no new per-item model)
- [X] T016 [US2] Implement `GET /business/orphans` in `src/adp/business/router.py` — make T012 pass
  (depends on T014, T015)
- [X] T017 [P] [US2] Add `OrphanReportResponse` TS type and a `useOrphanReport()` hook to
  `web/src/api/business.ts`
- [X] T018 [US2] Add an orphan-filter toggle to `web/src/business/CapabilityTree.tsx`'s toolbar and a
  "no strategic linkage" badge to `web/src/business/CapabilityNode.tsx` when the node's id is in the
  orphan set (depends on T017)
- [X] T019 [US2] Add the same orphan-filter toggle and badge to `web/src/business/ValueStreamList.tsx`
  (depends on T017)
- [X] T020 [P] [US2] Component tests for the orphan filter/badge behavior: extend
  `web/src/business/CapabilityTree.test.tsx` if it exists (else create it) and create a new
  `web/src/business/ValueStreamList.test.tsx`

**Checkpoint**: User Stories 1 and 2 both independently functional.

---

## Phase 5: User Story 3 - See objective status and initiative counts on the existing Strategy card (Priority: P3)

**Goal**: The already-shipped Overview Strategy card shows a status breakdown and an initiative count,
with zero changes to its layout or existing 7 fields.

**Independent Test**: Seed objectives across every status and a couple of initiatives, load Overview,
confirm the existing Strategy card's new fields are accurate and sum correctly (quickstart.md scenario 1
plus the browser check).

### Tests for User Story 3 (MANDATORY — ART-IV)

- [X] T021 [P] [US3] Unit tests for `get_summary_stats()`'s six new fields in `tests/unit/strategy/
  test_strategy_store.py`: the five status counts sum to `total_objectives`, `initiative_count` matches
  the real number of seeded `strategy_initiatives` rows, and all seven pre-existing fields remain
  unchanged in behavior
- [X] T022 [US3] Contract test for `GET /api/v1/strategy/summary`'s enriched response shape in
  `tests/contract/test_strategy_api_contract.py`

### Implementation for User Story 3

- [X] T023 [US3] Add `proposed_count`, `active_count`, `at_risk_count`, `achieved_count`,
  `abandoned_count`, `initiative_count` fields to `StrategicSummaryResponse` in
  `src/adp/strategy/models.py` (data-model.md) (depends on T021 being red)
- [X] T024 [US3] Extend `get_summary_stats()` in `src/adp/strategy/store.py`: add
  `initiative_count` as one more scalar subquery column on the existing atomic `_SUMMARY_STATS_SQL`
  (research.md Decision 2), and add a Python-side pass over all objectives (reusing
  `_status_for_objective`, same as T005/US1) tallying the five status counts — make T021 pass (depends
  on T023)
- [X] T025 [P] [US3] Add the six new fields to the `StrategicSummary` TS type in
  `web/src/api/strategy.ts`
- [X] T026 [US3] Update `web/src/overview/OverviewPage.tsx`'s existing Strategy card to render the status
  breakdown and initiative count — no new card, no layout change beyond the card's own content (Ground-
  Truth Correction 1) (depends on T025)
- [X] T027 [P] [US3] Extend `web/src/overview/OverviewPage.test.tsx` with a case asserting the Strategy
  card renders the new status-breakdown/initiative-count data from a mocked enriched summary

**Checkpoint**: All three user stories independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T028 [P] Confirm OpenAPI/schema regeneration is clean with the new/enriched endpoints/models
  (`adp-generate --check`)
- [X] T029 Run the full regression suite: `pytest tests/ --ignore=tests/integration -q` and
  `cd web && npx vitest run && npx tsc --noEmit`
- [X] T030 Manually walk through all 4 quickstart.md scenarios against a running local stack
  (`ADP_AUTH_ENABLED=false`), including the Heat Map tab, the Capability Map/Value Streams orphan
  badge+filter, and the enriched Overview Strategy card, all in a real browser
- [X] T031 Replace the auto-generated `918-strategy-rollups` stub line in CLAUDE.md (and the matching
  AGENTS.md "Latest work"/"Prior work:" shift) with a proper hand-written narrative at commit time

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — a single baseline-verification task, no code change.
- **Foundational (Phase 2)**: Not applicable — no schema change, nothing blocks any user story.
- **User Stories (Phase 3–5)**: All three are independent of each other in principle (spec.md's stories
  serve genuinely separate screens/data). The only real coordination point: **US1 (T005) and US3 (T024)
  both edit `src/adp/strategy/store.py`**, in different functions (`get_strategy_heatmap` vs.
  `get_summary_stats`) — safe to write in either order, but not truly parallel-safe as a single merge
  (matches this session's established "shared file, disjoint functions" pattern, e.g. ADP-d8u.6's US1/US2
  both appending to the same three files).
- **Polish (Phase 6)**: Depends on all three user stories being complete.

### Within Each User Story

- Tests written and confirmed failing before implementation (ART-IV).
- Models before store functions; store functions before router endpoints; backend endpoints before
  frontend hooks; hooks before UI wiring.

### Parallel Opportunities

- Within US1: T002 alone; T004 blocks T005→T006; T007/T008 in parallel once T006 lands; T010 last.
- Within US2: T011 alone; T013 blocks T014; T015 in parallel with T013/T014; T016 depends on both T014
  and T015; T017 in parallel once T016 lands; T018/T019 can proceed in either order (different files);
  T020 last.
- Within US3: T021 alone; T023 blocks T024; T025 in parallel once T024 lands; T026 depends on T025; T027
  last.
- **US2's entire phase (T011–T020) can run fully in parallel with US1's and US3's phases** — it touches
  only `adp.business` files, zero overlap with `adp.strategy`. US1 and US3 share only
  `src/adp/strategy/store.py` (different functions) and `web/src/api/strategy.ts` (different hooks/types,
  additive) — safe to interleave, not safe to run as two literally-simultaneous edits to the same file
  without a merge step.

---

## Parallel Example: User Story 2 (fully independent of US1/US3)

```bash
# Tests:
Task: "Unit tests for orphan detection in tests/unit/business/test_orphans.py"
Task: "Contract test for GET /api/v1/business/orphans in tests/contract/test_business_registry_api.py"

# Once tests are red, models + frontend scaffolding together:
Task: "Add _strategic_objective_capabilities/_strategic_objective_value_streams mirrors to src/adp/business/store.py"
Task: "Add OrphanReportResponse model to src/adp/business/models.py"
Task: "Add OrphanReportResponse type + useOrphanReport hook to web/src/api/business.ts"
```

## Implementation Strategy

**MVP = User Story 1 only** (T001–T010): the heat map delivers the single most-requested "portfolio at a
glance" view named in the source requirements, fully standalone. User Stories 2 (orphan report) and 3
(enriched summary) are independent, lower-priority increments that can ship in either order afterward, or
be deferred indefinitely without weakening US1's value — none of the three shares a runtime dependency on
another.
