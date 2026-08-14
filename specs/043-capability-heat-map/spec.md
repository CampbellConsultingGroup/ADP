# Feature Specification: Capability Heat Map

**Feature Branch**: `043-capability-heat-map`
**Created**: 2026-08-05
**Status**: Draft
**Input**: User description: "ADP-3up.1 — Capability heat map: a hierarchical grid of L1/L2/L3 business capabilities color-coded by a selectable metric (maturity, strategic relevance, tech debt, or strategic fit), giving architects a dense, scannable view of the capability portfolio at a glance"

## Clarifications

### Session 2026-08-14

- Q: Should capabilities be grouped/partitioned by their assigned business domain, or shown as a flat
  L1/L2/L3 hierarchy that ignores domain assignment? → A: Flat L1/L2/L3 hierarchy, matching the existing
  capability tree's own rendering exactly — domain assignment is ignored by this view entirely (no
  domain-grouping concept, no "Unassigned" bucket to design).

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: (always applies)
- **ART-IV** — Test-Driven Development: (always applies)
- **ART-III** — Everything is Machine-Readable: this feature is a read-only visualization *projection* of existing typed data (`business_capabilities`, ADP-SPEC-033/034/035) — it introduces no new persisted artifact and must not become a second source of truth for capability classification; the grid always reflects the same `strategic_relevance`/`maturity_level` fields editable elsewhere on the platform.

ART-V (security/threat model) is engaged only nominally — this feature is a read-only view over data every authenticated role can already read (business capability reads are not permission-gated today); no new write path, no new sensitive-data exposure. ART-VII (AI grounding) does not apply — no AI-generated content is involved.

## Threat Model *(mandatory — ART-V)*

**Assets at risk**: none beyond what is already exposed — business capability names, hierarchy, and classification fields (`strategic_relevance`, `maturity_level`) are already readable by any authenticated user via the existing capability-tree view and API.

**Trust boundaries crossed**: browser → API (an existing, already-open read path); no new boundary.

**Abuse cases**: none specific to this feature — it adds no write path and no new data exposure. The only risk is an information-density one (surfacing classification gaps at a glance makes it easier to see, say, "most of the portfolio is unclassified" or "this capability is stuck at maturity 1") — this is the feature's *intended* value (surfacing gaps for architects to act on), not a security concern.

**Residual risk**: none beyond the platform's existing baseline for reading business architecture data.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See the whole capability portfolio color-coded by maturity at a glance (Priority: P1)

An enterprise or business architect opens the capability heat map and sees every business capability laid out in its hierarchy, each cell shaded by its current maturity level, so they can immediately spot which parts of the portfolio are mature versus which are still ad hoc — without opening each capability individually.

**Why this priority**: this is the single most common EA capability-visualization artifact and the reason this feature exists; it delivers the core "scan the whole portfolio at a glance" value with data that already exists today, with zero new write paths.

**Independent Test**: can be fully tested by seeding a handful of capabilities across different maturity levels (including some left unclassified), opening the heat map, and confirming each capability's cell color visually corresponds to its actual maturity level, with unclassified capabilities visually distinguishable from every real level.

**Acceptance Scenarios**:

1. **Given** a set of business capabilities with a mix of maturity levels assigned, **When** an architect opens the capability heat map, **Then** every capability appears exactly once, shaded according to its maturity level, with a legend explaining what each shade means.
2. **Given** a capability with no maturity level assigned yet, **When** it appears on the heat map, **Then** it is shown with a distinct "unclassified" treatment that is visually different from every real maturity level (not blank, not silently omitted, not defaulted to look like a real level).
3. **Given** the heat map is open, **When** an architect hovers or selects a capability's cell, **Then** they see that capability's full name and its exact maturity level (or "unclassified") without leaving the heat map.

---

### User Story 2 - Switch the color-coding metric to strategic relevance (Priority: P2)

An architect viewing the heat map switches the color-coding metric from maturity to strategic relevance, so they can ask a different question of the same portfolio ("where is our strategic investment concentrated?") without navigating to a different screen.

**Why this priority**: the second most valuable lens on the same data, using the other classification field that already exists platform-wide; depends on Story 1's grid existing but is a small, additive increment on top of it.

**Independent Test**: can be fully tested by switching the metric selector from maturity to strategic relevance on an already-loaded heat map and confirming every cell's shade updates to reflect strategic relevance instead, with the legend updating to match.

**Acceptance Scenarios**:

1. **Given** the heat map is showing capabilities shaded by maturity, **When** an architect selects "strategic relevance" as the metric, **Then** every cell's shading updates to reflect strategic relevance and the legend updates accordingly.
2. **Given** a capability that is unclassified for the currently-selected metric but classified for the other, **When** the metric is switched, **Then** that capability's cell updates from "unclassified" to its real value (or vice versa) — the unclassified treatment is per-metric, not a fixed property of the capability.

---

### User Story 3 - Drill from the heat map into a capability's detail (Priority: P3)

An architect spots an interesting cell on the heat map (e.g., a strategically important but low-maturity capability) and clicks through to that capability's existing detail view to see more context or take action (e.g., trigger an Agent Review, view linked applications).

**Why this priority**: turns the heat map from a read-only dashboard into an actionable starting point, but the heat map already delivers standalone value (Stories 1–2) without this; it's a navigation convenience, not core functionality.

**Independent Test**: can be fully tested by clicking a capability's cell on the heat map and confirming the existing capability detail (as already shown on the Business Capabilities page) opens for that exact capability.

**Acceptance Scenarios**:

1. **Given** the heat map is open, **When** an architect clicks a capability's cell, **Then** that capability's existing detail view opens, matching what they would see by navigating there directly from the capability tree.

---

### Edge Cases

- What happens when there are no business capabilities at all yet? The heat map must show an explicit empty state (with guidance to create capabilities first), not a blank or broken grid.
- What happens when a capability is renamed, reclassified, or deleted (e.g., by another architect, or by an Agent Review suggestion) while the heat map is open? The next time the heat map's data is refreshed, it must reflect the current state — this feature does not need to invent a new live-update mechanism beyond however current the platform's existing capability data already is when the page loads.
- What happens with a capability hierarchy that is very deep or very wide (e.g., dozens of L2/L3 children under one L1)? The heat map must remain usable (scrollable/navigable) rather than becoming unusably dense or silently truncating capabilities without indication.
- What happens if a capability has an invalid or out-of-range classification value (should not occur given existing validation, but the view must not crash if it does)? The cell should fall back to the "unclassified" treatment rather than erroring the whole view.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST display every business capability the user is authorized to read, arranged according to its existing L1/L2/L3 hierarchy, in a single grid-style view.
- **FR-002**: System MUST organize capabilities on the grid as a flat L1/L2/L3 hierarchy, matching how the
  existing capability tree renders today — business domain assignment is not used to group or partition the
  grid (Clarification Session 2026-08-14).
- **FR-003**: System MUST shade each capability's cell according to a color-coding metric, where the initial/default metric is maturity level.
- **FR-004**: Users MUST be able to switch the color-coding metric to strategic relevance and see every cell update accordingly.
- **FR-005**: System MUST visually distinguish capabilities that have no value set for the currently-selected metric ("unclassified") from every capability with a real value for that metric, using a treatment that cannot be confused with any real value.
- **FR-006**: System MUST display a legend that explains what each shade/color represents for the currently-selected metric.
- **FR-007**: System MUST let a user see a capability's full name and its exact value for the current metric (including "unclassified") without navigating away from the heat map.
- **FR-008**: System MUST let a user navigate from a capability's cell on the heat map to that capability's existing detail view.
- **FR-009**: System MUST show an explicit empty state when no business capabilities exist yet.
- **FR-010**: System MUST NOT introduce a new persisted classification value — the heat map reads the same `strategic_relevance` and `maturity_level` values editable elsewhere on the platform; editing those values elsewhere MUST be reflected the next time the heat map loads.
- **FR-011**: System MUST remain usable (readable, navigable) for a portfolio with a deep or wide capability hierarchy, without silently hiding or truncating capabilities.

### Key Entities *(include if feature involves data)*

- **Business Capability** *(existing entity, not introduced by this feature)*: the L1/L2/L3 hierarchical unit already captured by the platform, carrying `strategic_relevance` and `maturity_level` classification fields (each independently nullable/"unclassified") and an optional domain assignment (L1 only). This feature is a read-only visualization of this existing entity; it defines no new entity or field.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An architect can identify the overall maturity distribution of the entire capability portfolio (e.g., "most of our claims capabilities are ad hoc") in under 30 seconds, without opening any individual capability.
- **SC-002**: An architect can switch between viewing the portfolio by maturity and by strategic relevance in a single action (one click/selection), with the view updating immediately.
- **SC-003**: 100% of capabilities appear on the heat map exactly once, with unclassified capabilities for the selected metric unambiguously distinguishable from classified ones — zero capabilities silently omitted or misrepresented as having a real value they don't have.
- **SC-004**: An architect can go from spotting a capability of interest on the heat map to viewing its full detail in a single click.

## Assumptions

- **v1 metric scope is exactly the two classification fields that exist directly on a business capability today**: maturity level and strategic relevance. "Tech debt" and "strategic fit," mentioned as illustrative candidate metrics when this feature was first proposed, are not fields that exist on business capabilities today (tech-debt flags exist only on the separate application registry, and "strategic fit" does not correspond to any existing field); adding either as a heat-map metric would require a new cross-entity rollup and is explicitly out of scope for v1. They may be considered in a future iteration once (or if) such a rollup is built for other reasons.
- The grid shows one metric at a time via an explicit selector (not multiple metrics encoded simultaneously in one color) — the established, unambiguous convention for this kind of heat map.
- The L1→L2→L3 nesting mirrors the existing hierarchy already used by the capability tree (FR-002) — this
  feature does not invent a new hierarchy-traversal model, only a new color-coded presentation of the
  existing one. Business domain assignment (optional, L1-only) plays no role in this view's structure.
- Reading business capability data is not permission-gated today (any authenticated role can already read the capability tree); this feature does not introduce a new permission and inherits that existing openness.
- The heat map is a new, dedicated view on the existing Business Capabilities page area — it does not replace the existing capability tree view, which remains available for capability management (create/edit/delete, domain assignment, Agent Review) that the heat map itself does not need to duplicate.
- "Real-time" updates are not required — the heat map reflects data as of when it was loaded/last refreshed, consistent with how the rest of the platform's business architecture views already behave.
- Filtering and search (e.g., by domain, by level, by name) are out of scope for v1 — the target portfolio size is assumed to be scannable as a single view (per SC-001); revisit if real portfolios prove too large for this to hold.
