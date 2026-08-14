# Feature Specification: Insights Dashboard — Non-Architect Applications Heat Map

**Feature Branch**: `919-insights-dashboard`
**Created**: 2026-08-13
**Status**: Draft
**Input**: User description: "ADP-t3h — Non-architect insights layer: dimension-selectable applications heat map as the first pre-defined cross-platform visualization"

## Ground-Truth Corrections

The driving memory (`adp-non-architect-visualization-layer`) and its architectural analysis were re-verified
against the actual codebase before writing this spec:

1. **A real, open, adjacent-but-distinct epic already exists: `ADP-3up` / `ADP-3up.1`.** `bd show ADP-3up`
   confirms an OPEN "Business Capability Visualization Suite" epic, explicitly scoped to *architects* and to
   *business capabilities only* — six planned patterns (heat map, matrix, value-stream mapping, roadmap,
   dependency graph, bubble chart), of which only the heat map (`ADP-3up.1`) was ever drafted
   (`specs/043-capability-heat-map/`, left Paused mid-`/speckit-specify` on 2026-08-05, never planned or
   implemented). This feature is genuinely distinct in audience (non-architect vs. architect) and scope
   (cross-domain applications vs. capabilities-only) — resolved via clarification below to ship independently
   rather than absorb or be absorbed by `ADP-3up`.
2. **A second heat map — this session's own `918-strategy-rollups` (`ADP-d8u.7`) — has since shipped**,
   confirmed via `web/src/strategy/StrategyHeatMap.tsx` existing on `main`. The memory's original framing of
   it as "in flight" is now stale; it is a third, also-distinct precedent (theme × objective-status matrix,
   strategy-domain-scoped) for the same reasons `ADP-3up.1` is distinct — not folded into this feature either.
3. **Not every candidate coloring dimension is equally open to read.** Direct reads of
   `src/adp/application/models.py` and `src/adp/application/router.py` confirm `health_score` (1–5),
   `business_criticality` (1–5), and `time_classification` (`Tolerate`/`Invest`/`Migrate`/`Eliminate`) are
   plain fields on `Application`, returned by `list_applications()` with no extra permission gate. Cost data
   lives on a separate table (`ApplicationCostUpdate`/`CostRollupResponse`) and is gated behind
   `ActionType.READ_APPLICATION_COST` (`_require_cost_read` in `application/router.py`, added at
   `PERMISSIONS_VERSION` 1.3.0 — ADP-SPEC-038 US4). A dimension-selectable heat map that includes cost as an
   option cannot copy `adp.portfolio`'s existing no-gate read pattern outright for that one dimension.
4. **The existing per-field imperative permission-check pattern for exactly this situation already exists.**
   `adp.chat.tools.get_application_cost` (ADP-SPEC-041) checks `is_permitted(role,
   ActionType.READ_APPLICATION_COST)` inline before including cost data in a response that is otherwise open —
   the same shape this feature needs for its cost dimension, rather than a static route-level `Depends` gate
   (which would have to gate the whole endpoint, blocking the other three open dimensions unnecessarily).
5. **The recommended nav placement and backend home are still accurate.** `web/src/ui/AppShell.tsx` confirms
   `PRIMARY = [Overview, Designs]` and `ARCHITECTURE = [Strategy, Business, Applications, Portfolio,
   Governance, Knowledge]` — a new non-architect-facing entry belongs beside `Overview` in `PRIMARY`, not
   folded into the architect-facing `ARCHITECTURE` group. `src/adp/api/routers/portfolio.py` confirms
   `adp.portfolio` is a real, working precedent for a cross-domain, read-only, no-new-table aggregator
   (`/technologies`, `/designs`, `/search`, `/summary`, all plain `sa.text()` reads) — the natural home for
   one more read endpoint here rather than a new sibling package.
6. **Application data is demo-scale.** No pagination or performance concern for a v1 heat map — consistent
   with this session's separate confirmation (`ADP-914.9` research) that `scripts/seed_retail.py` seeds a
   small, fixed application set.

## Clarifications

### Session 2026-08-13

- Q: What should the first configurable visualization on this new non-architect screen actually visualize?
  → A: A cross-domain applications heat map — cells are the applications in the portfolio, color-coded by a
  user-selectable dimension (health score, business criticality, TIME classification, or cost) — rather than
  the business-capabilities heat map `ADP-3up.1` already has drafted.
- Q: How should this relate to the two existing heat maps — `ADP-3up.1`'s (planned, not yet built) capability
  heat map and `918-strategy-rollups`'s (shipped) strategy objective heat map? → A: Independent for now. This
  feature ships as its own new, general-audience screen; whether any of the three heat maps eventually link to
  or get embedded inside one another is an explicit future decision, out of scope here.

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: this document, plus `/speckit-plan`/`/speckit-tasks` before any code.
- **ART-II** — The Model is the Single Source of Truth: this feature is a pure read-side projection over the
  existing `Application` records — every cell's color is computed live from `health_score`/
  `business_criticality`/`time_classification`/cost at request time; no new persisted rollup or duplicate
  table.
- **ART-IV** — Test-Driven Development: the new aggregate endpoint and its per-dimension permission check get
  failing tests before implementation.
- **ART-V** — Security by Design: the cost dimension crosses an existing sensitive-data boundary
  (`READ_APPLICATION_COST`) that must be re-checked inside this new aggregate endpoint, not assumed inherited
  from the individual per-application cost endpoint's own gate. See Threat Model below.
- **ART-VII** — Grounded AI Only: not applicable — no AI-generated content anywhere in this feature.

## Threat Model *(mandatory — ART-V)*

**Assets at risk**: Application cost figures — the one dimension this feature can surface that is not already
open to every authenticated user.

**Trust boundaries crossed**: Browser → API, on a new read endpoint. No new external integration, no AI/LLM
call, no write path.

**Abuse cases**:
- A user without `READ_APPLICATION_COST` requests the heat map with the cost dimension selected, hoping the
  new cross-domain aggregate endpoint forgets to re-check the gate the single-application cost endpoint
  already enforces → mitigated by checking the same permission inline before including cost in either the
  dimension option list or the response data, mirroring `adp.chat.tools.get_application_cost`'s existing
  inline-check pattern (Ground-Truth Correction 4).
- A user without that permission infers approximate cost figures indirectly by cross-referencing the other
  three (open) dimensions → out of scope to fully prevent (those three dimensions are already individually
  open today; this feature does not increase what is inferable beyond existing per-application read access).

**Residual risk**: None beyond the platform's existing baseline for reading application data, once the inline
cost-dimension check is in place — matching the threat-model conclusion of `specs/043-capability-heat-map/`
and `specs/918-strategy-rollups/` for the same class of read-only aggregate-visualization feature.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See portfolio health at a glance (Priority: P1)

A non-architect stakeholder (e.g. a business sponsor or portfolio owner) opens the new dashboard and
immediately sees every application in the portfolio as a heat-map cell, colored by health score by default —
surfacing which applications are struggling without needing to open the Applications screen or understand any
architecture-specific terminology.

**Why this priority**: This is the entire value proposition from the driving memory — a pre-defined,
at-a-glance visualization for people who are not architects. Without this, there is no feature.

**Independent Test**: Load the dashboard with a seeded set of applications spanning the full health-score
range (including some with no score set); verify every application appears exactly once, colored by its
health-score band, with unscored applications visually distinct rather than blank or falsely "healthy".

**Acceptance Scenarios**:

1. **Given** a portfolio with applications at every health-score value (1–5) and some with no score set,
   **When** the dashboard loads, **Then** each application appears as one cell, shaded on a scale from its
   health score, and unscored applications are shown in a distinct "unclassified" treatment.
2. **Given** the portfolio has zero applications, **When** the dashboard loads, **Then** the user sees a clear
   empty-state message rather than a blank or broken visualization.

---

### User Story 2 - Change what the color means (Priority: P2)

The same user switches the coloring dimension — from health score to business criticality, or to TIME
classification — and the heat map recolors in place, letting them explore the same set of applications through
a different lens without leaving the screen.

**Why this priority**: This is the specific capability the memory called out as genuinely new to ADP — every
existing dashboard is fixed-axis; this is the first one that lets the viewer choose what they're looking at.

**Independent Test**: With the same seeded applications, switch the dimension selector through each open
option and verify the cell coloring changes to reflect the newly selected field, with the application set and
cell count unchanged.

**Acceptance Scenarios**:

1. **Given** the heat map is showing health score, **When** the user selects "business criticality" from the
   dimension selector, **Then** every cell recolors to reflect business criticality, without navigating away
   from the dashboard.
2. **Given** the current user does not have permission to read application cost data, **When** they open the
   dimension selector, **Then** "cost" does not appear as an option.
3. **Given** the current user does have permission to read application cost data, **When** they select "cost",
   **Then** the heat map recolors using cost data.

---

### User Story 3 - Find the dashboard without being an architect (Priority: P3)

A user who has never opened any of ADP's architecture-domain screens (Business, Applications, Portfolio,
Governance) can still find and open this dashboard, because it lives in the same top-level navigation area as
the general-audience Overview screen, not tucked inside the architecture section.

**Why this priority**: Placement determines whether the intended non-architect audience ever discovers the
feature at all — lower priority than the visualization itself, but still required for the feature to deliver
its stated value.

**Independent Test**: From a fresh app load, confirm a new top-level navigation entry exists alongside
Overview (not inside the Architecture section) and that selecting it opens this dashboard.

**Acceptance Scenarios**:

1. **Given** a signed-in user on any screen, **When** they look at the primary navigation, **Then** a new
   entry for this dashboard appears grouped with Overview, not under the Architecture section.
2. **Given** the user selects that new navigation entry, **When** the dashboard loads, **Then** they land on
   the applications heat map described in User Story 1.

---

### Edge Cases

- What happens when an application has no value set for the currently selected dimension? It must render as a
  visually distinct "unclassified" cell — never silently defaulted to the color of an actual value (e.g. an
  unscored application must never look "healthy").
- What happens when the user's permission changes mid-session (e.g. a role change) and they had cost selected?
  The dimension selector must fall back to the default dimension (health score) rather than continuing to
  request cost data the user can no longer read.
- What happens when every application in the portfolio has no value for the selected dimension? The heat map
  still renders (all cells "unclassified") rather than showing an empty state — the empty state is reserved
  for zero applications, not zero assessed values.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST display every application in the portfolio as one cell in a heat-map visualization.
- **FR-002**: System MUST shade/color each cell according to a single dimension selected by the user at a
  time.
- **FR-003**: Users MUST be able to select the coloring dimension from at least: health score, business
  criticality, and TIME classification.
- **FR-004**: System MUST offer cost as an additional selectable coloring dimension only to users who already
  have permission to read application cost data elsewhere in ADP, and MUST NOT expose cost data (as an option
  or as cell data) to users who lack that permission.
- **FR-005**: System MUST visually distinguish applications with no value set for the selected dimension from
  applications with an actual value — never implying a value that was never assessed.
- **FR-006**: System MUST let the user change the selected dimension and see the visualization update without
  navigating to a different screen.
- **FR-007**: System MUST reflect live application data — this feature introduces no new data-entry step and
  no new stored field.
- **FR-008**: System MUST be reachable from a top-level navigation entry grouped with the general-audience
  Overview screen, distinct from the architecture-domain navigation section.
- **FR-009**: System MUST show a distinct empty-state message when the application portfolio contains zero
  applications.

### Key Entities

- **Application** *(existing entity, not modified by this feature)*: the heat map is a read-only projection
  over already-captured `health_score`, `business_criticality`, `time_classification`, and cost fields — no
  new entity, attribute, or relationship is introduced.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can identify the least-healthy applications in the portfolio within 10 seconds of opening
  the dashboard, with no prior explanation of ADP's architecture terminology required.
- **SC-002**: Switching the coloring dimension updates every visible cell in under 1 second.
- **SC-003**: Every application in the portfolio appears in the heat map exactly once, regardless of whether
  it has an assessed value for the currently selected dimension.
- **SC-004**: Zero instances of cost data (or a cost option) appearing for a user without cost-read permission,
  verified across every dimension-selector state.

## Assumptions

- **Launch scope is one visualization type.** Per the resolved clarification, this feature ships exactly one
  configurable visualization (the applications heat map). Additional chart types (matrix, bubble/scatter,
  roadmap-over-time) from the broader `ADP-3up`-style pattern catalogue are explicitly out of scope and left
  for a future feature to scope individually.
- **No relationship to `ADP-3up`/`ADP-3up.1` or `918-strategy-rollups` is built in this feature.** Per the
  resolved clarification, this ships as an independent screen; any future cross-linking or absorption is a
  separate, later decision.
- **New navigation entry is a sibling to Overview** in the existing `PRIMARY` nav group (`web/src/ui/
  AppShell.tsx`), not nested under the `ARCHITECTURE` group.
- **The new read endpoint lives in the existing `adp.portfolio` package**, extending its established
  cross-domain, no-new-table, raw-SQL-aggregate pattern, rather than creating a new sibling backend package.
- **Default selected dimension is health score** — the least ambiguous, already-normalized (1–5) field, and
  the one every application is most likely to have assessed.
