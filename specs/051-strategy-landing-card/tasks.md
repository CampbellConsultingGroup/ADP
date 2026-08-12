# Tasks: Strategy Domain Card on the Overview Dashboard

**Input**: Design documents from `/specs/051-strategy-landing-card/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/strategy-summary-api.md, quickstart.md

**Tests**: Tests are MANDATORY for all ADP features (ART-IV). Test tasks appear before their implementation counterparts in every phase and MUST be confirmed to fail before implementation begins.

**Organization**: Three independently-testable user stories (card + mini-stats, linkage-health warning, fiscal-period warning) on top of a shared Foundational phase (the one new backend aggregate all three stories' frontend work depends on).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- File paths are exact and relative to the repo root

---

## Phase 1: Setup

**Purpose**: Confirm the plan's assumptions still hold against the live repo before editing.

- [x] T001 Confirm `src/adp/strategy/store.py`'s `_objectives`/`_themes`/`_objective_capabilities`/`_objective_value_streams` `Table()` definitions and `src/adp/strategy/router.py`'s `_get_session` dependency are still current (research.md's premise); confirm `src/adp/api/routers/portfolio.py`'s `get_portfolio_summary` still uses the `sa.text()` + `NOW()` pattern research.md Decision 3 mirrors; confirm `web/src/overview/OverviewPage.tsx`'s `DOMAINS` array shape and `web/src/api/portfolio.ts`'s `usePortfolioSummary()` hook shape are still current; confirm no `web/src/overview/OverviewPage.test.tsx` exists yet. No file changes — read-only; stop and re-plan if any premise has drifted.

**Checkpoint**: Plan's file-level assumptions reconfirmed — safe to proceed.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The one new backend aggregate endpoint every user story's frontend work needs before it can render anything real.

**⚠️ CRITICAL**: All three user stories are frontend-only phases that call this same endpoint — none can be meaningfully implemented or tested until it exists and returns correct data for all seven fields (the underlying query is genuinely atomic, per research.md Decision 3 — one round trip computes mini-stats, linkage split, and fiscal split together).

- [x] T002 [P] Create `tests/unit/strategy/test_strategy_store.py` additions (extend the existing file) — failing tests for a new `get_summary_stats(session)` function in `src/adp/strategy/store.py`: returns all-zero fields against an empty database; `total_objectives`/`total_themes` match seeded counts; an objective linked only to a capability (no value stream) counts in `linked_count` (FR-005); an objective with zero links counts in `unlinked_count`; `linked_count + unlinked_count == total_objectives` holds; fiscal-bucket tests for the current calendar quarter, an upcoming quarter, a past quarter, and the `FY`-period special case (an `FY` objective in the current fiscal year is never past-due; one in a prior fiscal year is). Confirm all fail (`get_summary_stats` doesn't exist yet).
- [x] T003 [P] Create `tests/contract/test_strategy_api_contract.py` additions (extend the existing file) — failing tests for `GET /api/v1/strategy/summary`: 200 with all-zero fields on an empty database; 200 with correct counts against seeded themes/objectives/links; response validates against `StrategicSummaryResponse` (`extra="forbid"`, no unexpected fields). Confirm all fail (no route exists yet).
- [x] T004 In `src/adp/strategy/models.py`: add `StrategicSummaryResponse` (`total_objectives`, `total_themes`, `linked_count`, `unlinked_count`, `current_period_count`, `upcoming_count`, `past_due_count`, all `int`, `extra="forbid"` per data-model.md).
- [x] T005 In `src/adp/strategy/store.py`: implement `get_summary_stats(session)` as one `sa.text()` query pass (research.md Decision 3) — `COUNT(*)` for themes, a `LEFT JOIN`-deduplicated pass over `strategic_objectives` against both link tables for the linkage split, and a `CASE`-classified, `COUNT(*) FILTER (WHERE ...)`-aggregated pass for the fiscal split anchored to the database's own `NOW()`/`EXTRACT()` (never Python's clock), implementing the `FY`-aware past-due rule from research.md Decision 4. Run T002 and confirm it passes.
- [x] T006 In `src/adp/strategy/router.py`: implement `GET /summary` calling `get_summary_stats`, returning `StrategicSummaryResponse`. No `ActionType` gate needed (`enforce_route_permission` is a no-op for GET; spec.md FR-012). Run T003 and confirm it passes.
- [x] T007 Run `pytest tests/unit/strategy/ tests/contract/test_strategy_api_contract.py -q` — confirm all green, zero regressions in ADP-d8u.1's existing cases.

**Checkpoint**: `GET /api/v1/strategy/summary` exists, is correct for all seven fields including the `FY`-special-case fiscal rule — no user-facing card exists yet.

---

## Phase 3: User Story 1 - See Strategy's presence and scale at a glance (Priority: P1) 🎯 MVP

**Goal**: A fifth "Strategy" domain card appears on the Overview dashboard, visually consistent with the other four, showing objective/theme counts and a deep-link into the Strategy screen — with no fabricated progress metric.

**Independent Test**: Load the Overview dashboard with a known number of seeded objectives/themes; confirm a Strategy card appears with those exact counts and that its deep-link opens the Strategy screen's Objectives view (spec.md's own Independent Test for this story).

### Tests for User Story 1 (MANDATORY — ART-IV)

- [x] T008 [P] [US1] Create `web/src/api/strategy.test.ts` additions (extend the existing file) — failing test: `useStrategySummary()` GETs `/api/v1/strategy/summary` and returns the typed response. Confirm it fails (the hook doesn't exist yet).
- [x] T009 [P] [US1] Create `web/src/overview/OverviewPage.test.tsx` (new — none exists today, confirmed in T001) — failing tests, mocking `useStrategySummary` (and the page's other existing hooks minimally, mirroring `web/src/chat/ChatPanel.test.tsx`'s `vi.mock(hooks-module)` convention): a Strategy card renders in the domain-card grid with the mocked `total_objectives`/`total_themes` values; clicking its deep-link control calls `onNavigate("strategy")`; no progress-percentage element is rendered anywhere on the card (FR-003). Confirm all fail (no Strategy card exists yet).

### Implementation for User Story 1

- [x] T010 [US1] In `web/src/api/strategy.ts`: add the `StrategicSummary` interface and `useStrategySummary()` hook (data-model.md's exact shape — `queryKey: ["strategy-summary"]`, `staleTime: 60_000`, mirroring `usePortfolioSummary()`). Run T008 and confirm it passes.
- [x] T011 [US1] In `web/src/overview/OverviewPage.tsx`: call `useStrategySummary()`; add a fifth entry to the `DOMAINS` array (icon, eyebrow "Strategy", title, description, mini-stats for `total_objectives`/`total_themes`, one tile whose `onClick` calls `onNavigate("strategy")`) — no progress/completion element (FR-003). Run T009 and confirm it passes.
- [x] T012 [US1] Run `cd web && npx vitest run src/api/strategy.test.ts src/overview/OverviewPage.test.tsx && npx tsc --noEmit` — confirm all green, zero regressions.

**Checkpoint**: User Story 1 fully functional and independently testable — the Strategy card exists with correct mini-stats and navigation. Shippable MVP increment.

---

## Phase 4: User Story 2 - Spot untraceable objectives as a governance signal (Priority: P2)

**Goal**: The Strategy card shows a linkage-health split, with the unlinked count visually flagged as a warning.

**Independent Test**: Seed a mix of linked and unlinked objectives; confirm the card's linkage indicator splits them correctly and visually flags the unlinked group as a warning (spec.md's own Independent Test for this story).

### Tests for User Story 2 (MANDATORY — ART-IV)

- [x] T013 [P] [US2] Extend `web/src/overview/OverviewPage.test.tsx` — failing tests: the Strategy card renders the linked/unlinked split from the mocked `useStrategySummary` data; when `unlinked_count > 0`, the unlinked segment carries a distinct warning-state visual treatment (e.g. a class/style asserted against, matching how the existing "At risk" KPI tile's `alert` class is asserted elsewhere in this codebase); when `unlinked_count === 0`, no warning treatment appears. Confirm all fail.

### Implementation for User Story 2

- [x] T014 [US2] In `web/src/overview/OverviewPage.tsx`: add the linkage-health bar to the Strategy card entry, reading `linked_count`/`unlinked_count` from `useStrategySummary()`, applying the existing at-risk/warning visual treatment when `unlinked_count > 0` (mirrors the KPI row's own existing `alert` class convention). Run T013 and confirm it passes.
- [x] T015 [US2] Run `cd web && npx vitest run src/overview/OverviewPage.test.tsx && npx tsc --noEmit` — confirm all green, zero regressions in User Story 1's cases.

**Checkpoint**: User Stories 1 and 2 both independently functional — the card shows presence, scale, and linkage health.

---

## Phase 5: User Story 3 - Spot past-due objectives as a governance signal (Priority: P3)

**Goal**: The Strategy card shows a fiscal-period breakdown (current / upcoming / past-due), with the past-due count visually flagged as a warning.

**Independent Test**: Seed objectives across past, current, and future fiscal periods relative to a known server date; confirm the card correctly buckets each and visually flags the past-due bucket as a warning (spec.md's own Independent Test for this story).

### Tests for User Story 3 (MANDATORY — ART-IV)

- [x] T016 [P] [US3] Extend `web/src/overview/OverviewPage.test.tsx` — failing tests: the Strategy card renders the current/upcoming/past-due breakdown from the mocked `useStrategySummary` data; when `past_due_count > 0`, that bucket carries the same warning-state visual treatment as User Story 2's unlinked segment; when `past_due_count === 0`, no warning treatment appears. Confirm all fail.

### Implementation for User Story 3

- [x] T017 [US3] In `web/src/overview/OverviewPage.tsx`: add the fiscal-period breakdown to the Strategy card entry, reading `current_period_count`/`upcoming_count`/`past_due_count` from `useStrategySummary()`, applying the warning treatment when `past_due_count > 0`. Run T016 and confirm it passes.
- [x] T018 [US3] Run `cd web && npx vitest run src/overview/OverviewPage.test.tsx && npx tsc --noEmit && npm run test:run` — confirm all green, zero regressions across the whole frontend.

**Checkpoint**: All three user stories independently functional — the Strategy card shows presence, scale, linkage health, and fiscal-timing health, matching the other four cards' visual convention.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation (ART-XVI) and full-suite regression confirmation, backend and frontend.

- [x] T019 [P] Add a short docstring/comment block above `get_summary_stats` in `src/adp/strategy/store.py` documenting the `FY`-special-case fiscal rule inline (research.md Decision 4) so a future reader doesn't need to re-derive it from spec.md's Edge Cases.
- [x] T020 Run `pytest tests/ --ignore=tests/integration -q`, `ruff check src/`, `mypy src/`, `adp-generate --check` — confirm all clean, zero regressions across the whole backend.
- [x] T021 Run `cd web && npx tsc --noEmit` and `npm run test:run` — confirm clean/green across the whole frontend.
- [x] T022 Walk through quickstart.md Scenarios 1–6 to confirm end-to-end behavior beyond the unit-test level (Scenario 7 is T020/T021, just run). If no browser-automation tool is available in-session, substitute Scenario 6's manual/browser check with equivalent automated coverage and document exactly which test covers it, rather than skipping silently.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all three user stories (none can render real data from an endpoint that doesn't exist yet, and the underlying query is atomic — see research.md Decision 3 — so it can't be meaningfully built in thirds across the three stories without rewriting the same SQL pass three times).
- **User Story 1 (Phase 3)**: Depends on Foundational. No dependency on User Stories 2 or 3.
- **User Story 2 (Phase 4)**: Depends on Foundational **and** on User Story 1's Strategy card entry existing in `OverviewPage.tsx` (it's additive to the same card) — not independently implementable in parallel with US1, though independently *testable* per its own acceptance scenarios once US1 exists.
- **User Story 3 (Phase 5)**: Same shape as US2 — depends on Foundational and US1's card entry; independent of US2's own linkage-bar code (a different sub-element of the same card).
- **Polish (Phase 6)**: Depends on all three user stories being complete.

### Parallel Opportunities

- T002 and T003 (Foundational tests) touch different files and can be drafted in parallel.
- T008 and T009 (US1 tests) touch different files and can be drafted in parallel.
- T013 (US2) and T016 (US3) both extend `OverviewPage.test.tsx` — same file, so draft sequentially or coordinate carefully rather than treating as parallel-safe.
- T019 (Polish docs) can run alongside T020/T021 once all three stories are implemented.

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (Setup) → Phase 2 (Foundational: the full aggregate endpoint, all seven fields).
2. Complete Phase 3 (User Story 1) → the Strategy card existing at all, with correct mini-stats and navigation, is a complete, shippable increment per spec.md (closes the literal "Strategy has no presence on the landing screen" gap this feature exists for).
3. **STOP and VALIDATE**: run T012, confirm quickstart.md Scenarios 1–2 pass.
4. Optionally stop here — User Stories 2 and 3 add governance-signal depth on top, independently valuable but not required for the core visibility gap to be closed.

### Incremental Delivery

1. Setup + Foundational → the aggregate endpoint ready, unit- and contract-tested in isolation.
2. Add User Story 1 → test independently → MVP.
3. Add User Story 2 → test independently → linkage-health governance signal.
4. Add User Story 3 → test independently → fiscal-timing governance signal, full card complete.
5. Polish → documentation + full-suite regression confirmation, backend and frontend.

## Notes

- No `[Story]` label on Setup/Foundational/Polish tasks, per the required task format.
- Every implementation task follows a task confirmed to fail first (ART-IV): T002→T005, T003→T006, T008→T010, T009→T011, T013→T014, T016→T017.
- This feature touches 0 new backend packages, 0 new migrations, 2 modified backend files (`src/adp/strategy/models.py`, `src/adp/strategy/store.py`, `src/adp/strategy/router.py` — three, not two; corrected count), 1 modified + 1 new frontend test file, 1 modified frontend API client (`web/src/api/strategy.ts`), 1 modified frontend page (`web/src/overview/OverviewPage.tsx`) — no other existing file is touched.
