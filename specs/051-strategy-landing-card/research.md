# Research: Strategy Domain Card on the Overview Dashboard

## Decision 1: A new `GET /api/v1/strategy/summary` aggregate endpoint, not a client-side computation

**Decision**: Add one new backend endpoint that computes all four card facts (objective count,
theme count, linked/unlinked split, current/upcoming/past-due split) in a single server-side
query pass, rather than deriving them in the browser from the existing
`GET /api/v1/strategy/objectives` list response.

**Rationale**: Confirmed by direct read of `web/src/overview/OverviewPage.tsx` that the four
existing domain cards *do* compute their mini-stats client-side — but each does so from list
data the page was already fetching for other reasons (`useCapabilities()`, `useApplications()`,
etc.), and none of those computations need a fact the list response doesn't already carry.
Strategy's card is different on two specific points spec.md pins down:

- **FR-004/FR-005** (linkage split) need to know, per objective, whether it has at least one
  capability or value-stream link. `StrategicObjectiveSummary` (the shape
  `GET /api/v1/strategy/objectives` returns) deliberately omits `capability_ids`/
  `value_stream_ids` — only the single-objective `GET .../objectives/{id}` detail response
  carries them (confirmed directly in `src/adp/strategy/models.py`). Computing the split
  client-side would mean fetching full detail for every objective (an N+1 fan-out) just to
  render a dashboard tile.
- **FR-008** requires the fiscal-period classification to be anchored to the server's clock, not
  the browser's. That's inherently a server-side computation regardless of what data shape the
  list endpoint returns.

**Alternatives considered**:
- *Extend `StrategicObjectiveSummary` with link-count fields* — would fix the N+1 problem for
  FR-004/005 but still leaves FR-008's server-clock requirement unaddressed, and would mean
  every caller of the list endpoint (including the Strategy screen's own `ObjectiveList.tsx`,
  which has no use for a link count) pays the cost of computing it. Rejected: conflates a
  dashboard-specific need with the general-purpose list endpoint's own contract.
- *Client-side computation with the browser's `Date.now()` for the fiscal split* — directly
  violates FR-008 (explicit, deliberate requirement — see spec.md's Edge Cases and Acceptance
  Scenario 3 of User Story 3, which exists specifically to catch this). Rejected.
- *A new aggregate endpoint, mirroring `adp.portfolio`'s existing summary pattern* — chosen.
  Confirmed this exact pattern already exists and is already proven at exactly this call site:
  `GET /api/v1/portfolio/summary` (`src/adp/api/routers/portfolio.py`), consumed by this same
  `OverviewPage.tsx` today for its design-lifecycle donut chart via `usePortfolioSummary()`. Not
  a new idea for the codebase — only new to `adp.strategy` specifically.

## Decision 2: The aggregate query lives in `adp.strategy.store`, not a new `adp.portfolio`-style cross-domain router

**Decision**: `get_summary_stats(session)` is added to the existing `src/adp/strategy/store.py`,
and `GET /api/v1/strategy/summary` is added to the existing `src/adp/strategy/router.py` — no new
file, no new package.

**Rationale**: `adp.portfolio`'s own summary endpoint lives in a dedicated cross-domain router
(`adp/api/routers/portfolio.py`, using a shared `get_kb_session` dependency) because its
aggregation genuinely spans tables owned by different domains (`designs`,
`element_technology_tags`). Strategy's aggregate needs only tables `adp.strategy` already owns
(`strategic_objectives`, `strategic_themes`, `strategic_objective_capabilities`,
`strategic_objective_value_streams`) — there's no cross-domain join, so there's no reason to
reach for `adp.portfolio`'s cross-domain-router shape. Keeping it inside `adp.strategy` matches
this codebase's own established convention (confirmed across every prior spec this session): a
domain's own aggregate reads live inside that domain's own package.

**Alternatives considered**:
- *A new endpoint under `/api/v1/portfolio/`* — rejected: would mean `adp.portfolio` importing
  from `adp.strategy` (or vice versa) for something that isn't actually a cross-domain
  aggregation, breaking the single-domain-ownership convention every other package in this
  codebase follows.

## Decision 3: Raw `sa.text()` aggregation, mirroring `adp.portfolio`'s own established query style

**Decision**: `get_summary_stats` uses `sa.text()` SQL (`COUNT`, `GROUP BY`, and the database's
own `NOW()`/`EXTRACT()` for the fiscal comparison) directly against `adp.strategy.store`'s
existing `Table()` objects' underlying tables, rather than composing the count via SQLAlchemy
Core's expression builder or by fetching rows into Python and counting there.

**Rationale**: Directly mirrors `adp.api.routers.portfolio.get_portfolio_summary`'s own
implementation, read in full during this research pass — it uses `sa.text()` with `NOW()` for
exactly the same shape of problem (`review_due < NOW()` for "overdue"). Reusing the database
server's own clock (rather than Python's `datetime.now(timezone.utc)`, which is `adp.strategy`'s
own existing convention for row timestamps, but wrong here) is what actually satisfies FR-008 —
the comparison happens inside the one database every request already talks to, so there's no
clock to disagree with in the first place.

**Alternatives considered**:
- *Fetch `(fiscal_year, period)` for every objective, classify in Python against
  `datetime.now(timezone.utc)`* — technically still "server-side" (the API process's clock, not
  the browser's), and would work in a single-process deployment. Rejected in favor of pushing the
  comparison into SQL: keeps the whole aggregate a single round-trip query (no fetch-then-loop),
  and mirrors the one existing precedent (`adp.portfolio`) exactly rather than introducing a
  second style for the same class of problem.

## Decision 4: Fiscal-period comparison logic (the `FY`-period special case)

**Decision**: The current-vs-past-due comparison treats `FY`-period objectives specially, exactly
as spec.md's Edge Cases section already resolved: an `FY` objective is past due only once its
entire `fiscal_year` has elapsed (current fiscal year strictly greater than the objective's); a
quarterly objective (`Q1`–`Q4`) is past due once the current period is later than its own within
the same fiscal year, or the fiscal year itself has passed. This is expressed as one `CASE`
expression per objective row inside the same aggregate query (Decision 3), comparing against
`EXTRACT(YEAR FROM NOW())` and a quarter number derived from `EXTRACT(QUARTER FROM NOW())`.

**Rationale**: Confirmed directly against `src/adp/strategy/models.py` that
`ObjectivePeriod = Literal["Q1", "Q2", "Q3", "Q4", "FY"]` is the complete, already-shipped value
set — no other period shape exists to plan around. Confirmed directly against the codebase (grep
for `fiscal_calendar`/`FISCAL_YEAR_START`, no hits) that no configurable fiscal-calendar-start
field exists anywhere today, so calendar-year quarters (Q1 = Jan–Mar, etc.) is not an assumption
being introduced here — it's the only calendar concept that exists in the system to compare
against.

**Alternatives considered**: none genuinely — this is spec.md's own Edge Cases resolution
(already settled at spec time, not re-opened here); this section exists only to record exactly
where that logic lives (one `CASE` expression, in SQL, inside the new aggregate query) rather than
to re-litigate the rule itself.
