# Feature Specification: Strategy Rollups — Heat Map, Orphan Report, Richer Summary

**Feature Branch**: `918-strategy-rollups`
**Created**: 2026-08-13
**Status**: Draft
**Input**: User description: "ADP-d8u.7 — Strategy rollups: heat map, orphan report, and richer summary (status/initiative breakdown)"

## Ground-Truth Corrections

The source bead and `docs/strategy-domain-expansion-specs.md` SPEC-STRAT-04 were re-verified against the
actual codebase before writing this spec, per the bead's own explicit instruction to do so:

1. **The Overview "Strategy" domain card and its stat tile are already shipped.** SPEC-STRAT-04 §2 lists
   "A `Strategy` stat tile + domain card on the Overview screen" as in-scope. Direct reads of
   `web/src/overview/OverviewPage.tsx` (imports and renders `useStrategySummary()`, a "strategy" domain
   card entry alongside the other four) and `src/adp/strategy/router.py` (`GET /api/v1/strategy/summary`,
   already registered) confirm this shipped in ADP-d8u.3 (PR #62), before this bead was even filed. **This
   spec does not add a new Overview card or tile** — it only enriches the data the *existing* card's
   existing endpoint returns (see FR-007 below), which the card will pick up automatically since it
   already renders whatever `useStrategySummary()` returns.
2. **The existing `StrategicSummaryResponse` has exactly 7 fields, none of them a status breakdown or an
   initiative count.** Direct read of `src/adp/strategy/models.py` confirms today's fields are
   `total_objectives`, `total_themes`, `linked_count`, `unlinked_count`, `current_period_count`,
   `upcoming_count`, `past_due_count` — computed by one atomic raw-SQL aggregate
   (`adp.strategy.store.get_summary_stats`). Neither a per-status count nor an initiative count exists
   today, confirming the bead's claim that this part of SPEC-STRAT-04 is still genuinely net-new.
3. **Both of this bead's stated dependencies (ADP-d8u.2, ADP-d8u.5) — and ADP-d8u.6, which the source doc
   treats as merely optional — are now closed and merged** (PRs #71, #72, #73, all on `main` as of this
   writing). This means the "richer summary" piece can include a real initiative count outright, rather
   than the doc's own fallback of shipping without it "if ADP-d8u.6 hasn't landed yet."
4. **Objective status is a computed-on-read value, not a stored column queryable by plain SQL.**
   `compute_status()` (ADP-d8u.5) derives status from an objective's target/direction plus its last 3
   progress entries' trend — it is not a column `GROUP BY` can aggregate directly. The existing
   `list_objectives()` function already handles this by computing status per-row in a loop
   (`_row_to_summary` → `_status_for_objective`, one call per objective). Both the status-breakdown
   summary field and the heat map in this spec follow that same established per-row computation pattern,
   not a single atomic SQL aggregate the way the existing 7 summary fields are computed.

## Clarifications

### Session 2026-08-13

- Q: SPEC-STRAT-04 describes the heat map as "objectives × status, optionally filterable by theme." What
  shape should it be? → A: A full matrix — every theme as a row, every one of the 5 statuses as a column,
  with a count in each cell — the classic at-a-glance heat-map view. An optional theme filter narrows the
  matrix to a single row/theme rather than changing its shape.
- Q: How should the orphan report (capabilities/value streams with zero strategic linkage) surface on the
  existing Capability Map and Value Streams screens? → A: Both a persistent "no strategic linkage" badge
  on every orphaned row, and a toggle to filter the list down to orphans only — matching the source doc's
  own "filter/badge" phrasing literally, giving both an at-a-glance signal while browsing everything and a
  way to get a full orphan count/list on a large tree.

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: this document, plus `/speckit-plan`/`/speckit-tasks` before any
  code.
- **ART-II** — The Model is the Single Source of Truth: this entire feature is a read-side projection —
  every number it surfaces is derived live from `strategic_objectives`/`strategic_themes`/
  `strategy_initiatives`/the traceability link tables at query time, never a separately-maintained rollup
  table. No new persisted artifact of any kind.
- **ART-IV** — Test-Driven Development: all new aggregate/orphan-detection functions and endpoints get
  failing tests before implementation, mirroring this package's established rhythm.
- **ART-VII** — AI Grounding: not applicable — no AI-generated content anywhere in this feature's scope.
- **ART-XI** — Traceability End to End: the orphan report is itself a traceability-completeness signal —
  it exists specifically to surface where the objective→capability/value-stream traceability chain is
  currently broken (an entity with zero strategic backing).

## Threat Model *(mandatory — ART-V)*

**Assets at risk**: None beyond what is already exposed. Every field this feature surfaces (objective
counts, theme names, capability/value-stream names and linkage state) is already readable individually by
any authenticated user via existing endpoints; this feature only re-aggregates and re-presents that same
already-open data.

**Trust boundaries crossed**: Browser → API only, on already-open read paths. No new external
integration, no new AI/LLM call, no new write path anywhere in this feature.

**Abuse cases**: None specific to this feature — it introduces no write path and no new data exposure
beyond existing per-entity reads. The only externally-observable effect of the new aggregate endpoints is
information density (e.g. "most of the portfolio has zero strategic linkage" becomes visible at a glance)
— this is the feature's *intended* value (surfacing traceability gaps for architects to act on), not a
security concern.

**Residual risk**: None beyond the platform's existing baseline for reading business/strategy data —
matching `specs/043-capability-heat-map/spec.md`'s own threat model for the same class of read-only
aggregate-visualization feature.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See objective health across every theme at a glance (Priority: P1)

A strategy lead opens a new "Heat Map" tab on the Strategy screen and sees every theme as a row, with a
count of objectives in each status (proposed / active / at-risk / achieved / abandoned) as columns — so
they can immediately spot which themes are healthy and which are concentrated with at-risk or stalled
objectives, without opening each objective individually.

**Why this priority**: This is the single most-requested "portfolio at a glance" view named in the source
requirements — it turns data that already exists (objectives, their computed status, their theme) into an
immediately actionable scan, the same value proposition the already-drafted capability heat map
(`specs/043-capability-heat-map/`) delivers for capabilities.

**Independent Test**: Seed objectives across several themes and every status value (including a theme
with zero objectives), open the Heat Map tab, and confirm every theme appears exactly once with correct
per-status counts, including themes with all-zero counts shown as zero, not omitted.

**Acceptance Scenarios**:

1. **Given** objectives spread across multiple themes and statuses, **When** a strategy lead opens the
   Heat Map tab, **Then** every theme appears as a row with an accurate count for each of the 5 statuses,
   and the grand total across all cells equals the total objective count.
2. **Given** the heat map is showing every theme, **When** the strategy lead selects one theme as a
   filter, **Then** the matrix narrows to that theme's row (or an equivalent single-theme view) without
   losing the per-status breakdown.
3. **Given** a theme with zero objectives, **When** it appears on the heat map, **Then** every status
   column for that row shows zero — not blank, not omitted from the grid.

---

### User Story 2 - Find capabilities and value streams with no strategic backing (Priority: P2)

A business or enterprise architect browsing the existing Capability Map or Value Streams screen sees a
"no strategic linkage" badge on any capability or value stream that isn't referenced by any strategic
objective, and can toggle a filter to see only those orphaned items — surfacing where the
objective-to-outcome traceability chain is currently incomplete.

**Why this priority**: Directly serves the traceability-completeness value ART-XI exists for, and now that
ADP-d8u.2 has landed the objective↔design/application links, this is the natural next traceability-gap
signal to surface — but it's a smaller, more targeted addition than the heat map (an indicator on two
already-existing screens, not a new tab), so it follows P1 rather than leading.

**Independent Test**: Seed a mix of capabilities/value streams — some linked to at least one objective,
some with zero links — open the Capability Map, confirm only the unlinked ones show the badge, then
toggle the orphan filter and confirm only those same items remain visible. Repeat for Value Streams.

**Acceptance Scenarios**:

1. **Given** a capability with zero strategic-objective links, **When** an architect views the Capability
   Map, **Then** that capability shows a "no strategic linkage" badge, and a linked capability does not.
2. **Given** the Capability Map is showing every capability, **When** the architect toggles the orphan
   filter on, **Then** only capabilities with zero strategic linkage remain visible.
3. **Given** the same badge-and-filter behavior, **When** an architect views Value Streams instead,
   **Then** the identical behavior holds for value streams and their own linkage state.

---

### User Story 3 - See objective status and initiative counts on the existing Strategy dashboard card (Priority: P3)

An executive or strategy lead glancing at the Overview dashboard's already-existing Strategy card now
also sees a breakdown of objectives by status and a count of active initiatives, without navigating away
from Overview.

**Why this priority**: The smallest piece of this bead — it enriches data already surfaced on an
already-shipped card (no new screen, no new tab, no new navigation), so it delivers the least *net-new*
value relative to the other two stories, even though it's simple to deliver.

**Independent Test**: Seed objectives across every status and a couple of strategy initiatives, load the
Overview screen, and confirm the existing Strategy card now shows accurate status-breakdown counts and an
accurate initiative count, summing correctly against the objective/initiative totals.

**Acceptance Scenarios**:

1. **Given** objectives in a mix of statuses, **When** the Overview screen loads, **Then** the existing
   Strategy card shows a count for each status that sums to the total objective count.
2. **Given** a set of strategy initiatives exist, **When** the Overview screen loads, **Then** the
   Strategy card shows the current total initiative count.

### Edge Cases

- No objectives exist at all yet: the heat map shows an explicit empty state (not a blank or broken
  grid), and the enriched summary's status breakdown shows all-zero counts rather than erroring.
- No themes exist at all yet: same — the heat map shows an explicit empty state rather than a broken
  render.
- A capability or value stream is deleted while linked to an objective: the existing cascade (`ON DELETE
  CASCADE` on the link tables) already removes the link row, so it correctly stops counting toward
  "linked" and would appear as an orphan only if it still existed — this feature does not need to invent
  new cleanup behavior.
- Very large capability hierarchies: per the source doc's own open question, this spec's orphan query
  targets the current demo-scale dataset (matching every other rollup/aggregate feature already shipped
  this session); a materialized-view optimization is explicitly out of scope unless a real performance
  problem is observed.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a heat map view showing every strategic theme as a row and every
  objective status as a column, with an accurate count of objectives in each theme/status combination.
- **FR-002**: The system MUST allow the heat map to be narrowed to a single theme without changing its
  per-status breakdown shape.
- **FR-003**: A theme with zero objectives MUST still appear on the heat map with all-zero counts, not be
  omitted.
- **FR-004**: The system MUST identify every business capability that is not referenced by any strategic
  objective link as an "orphan."
- **FR-005**: The system MUST identify every value stream that is not referenced by any strategic
  objective link as an "orphan," using the same rule as FR-004.
- **FR-006**: The system MUST show a "no strategic linkage" badge on every orphaned capability and value
  stream on their respective existing list/tree screens, and MUST provide a toggle to filter each screen
  down to orphans only.
- **FR-007**: The system MUST enrich the existing Strategy dashboard summary with a count of objectives
  per status and a count of strategy initiatives, without altering any of its 7 existing fields.
- **FR-008**: All new read endpoints introduced by this feature MUST require no additional permission
  beyond standard authentication — consistent with every other aggregate/rollup read already in this
  codebase.

### Key Entities *(include if feature involves data)*

- **Strategy Heat Map**: A derived, non-persisted view — a theme-by-status matrix of objective counts.
  Not a stored entity; computed fresh on every read from existing `strategic_themes`/
  `strategic_objectives` data.
- **Orphan Report**: A derived, non-persisted list — capabilities and value streams with zero rows in the
  existing `strategic_objective_capabilities`/`strategic_objective_value_streams` link tables.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A strategy lead can identify which themes have the highest concentration of at-risk
  objectives without opening any individual objective.
- **SC-002**: An architect can find every capability or value stream with no strategic backing directly
  from the screen they already use to browse capabilities/value streams, without cross-referencing
  objective data by hand.
- **SC-003**: The existing Overview Strategy card conveys objective health (by status) and program-of-work
  scale (initiative count) without the viewer navigating to the Strategy screen at all.
- **SC-004**: Every count shown by this feature (heat map cells, orphan lists, enriched summary fields)
  always reflects the current live state of the underlying data — never a stale or separately-maintained
  copy.

## Assumptions

- No new `ActionType`/permission is needed for any of the three new/enriched read endpoints — consistent
  with every other rollup/aggregate endpoint in this codebase (`GET /strategy/summary`, `GET
  /portfolio/summary`, etc.), all ungated reads.
- The orphan report's query targets demo/current-scale data, matching the source doc's own explicitly
  deferred performance open question and every other rollup feature already shipped this session; a
  materialized view or index-backed optimization is out of scope unless a concrete performance problem
  surfaces.
- "Capabilities" in the orphan report means every business capability regardless of hierarchy level
  (L1/L2/L3) — linkage happens at the specific capability level already-existing link rows target, with
  no level restriction implied anywhere in the source doc.
- The Overview Strategy card itself (its layout, its existing 7 fields' presentation) is unchanged by this
  feature — only the data available to it grows, per Ground-Truth Correction 1.
