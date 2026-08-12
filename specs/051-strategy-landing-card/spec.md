# Feature Specification: Strategy Domain Card on the Overview Dashboard

**Feature Branch**: `051-strategy-landing-card`
**Created**: 2026-08-12
**Status**: Draft
**Input**: User description: "Add a Strategy domain card to the ADP landing Overview dashboard, closing the open-frontier gap where the Strategy layer has no visibility on the landing screen while Business, Enterprise, Solution, and Technical already do." (full text: `docs/strategy-landing-card-specify-input.md`, ADP-d8u.3)

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: (always applies)
- **ART-IV** — Test-Driven Development: (always applies)
- **ART-II** — The Model is the Single Source of Truth: applies — every figure on the card is a rendered read of already-canonical data (`StrategicObjective`/`StrategicTheme` and their existing link tables); no new field, no derived value stored anywhere.
- **ART-III** — Everything is Machine-Readable: applies directly — this feature is the concrete instance of the platform's own stated thesis ("no governance finding should live somewhere nobody re-checks") being extended to the one domain currently exempt from it.
- **ART-V** — Security by Design: low-risk — see Threat Model. A new read-only aggregate surface over already-readable data; no new write path.
- **ART-VI** — Observability: applies at the ordinary level — a new read endpoint (if the plan phase adds one) gets normal structured logging, matching every other ADP read route; no AI step is involved.
- **ART-VII, ART-VIII, ART-IX, ART-X, ART-XI**: do not apply — no AI-generated content, no AI proposal to confirm, no new audit-trail obligation (nothing is written), no validation gating, no traceability-thread change.
- **ART-XII** — Fixed Visual Language: applies loosely — the card must match the four existing domain cards' established visual/structural convention rather than introduce a new card shape.
- **ART-XIII** — Typed Contracts Everywhere: applies if a new read endpoint is added — any new response model uses Pydantic v2 with `extra="forbid"`, matching every other ADP boundary.
- **ART-XIV, ART-XV** — Reproducible builds / Schema evolution: do not apply — no schema change; this feature requires no migration (FR-011).
- **ART-XVI** — Documentation as Code: applies (SHOULD).

## Threat Model *(mandatory — ART-V)*

**Assets at risk**: aggregate counts derived from strategic objective data (objective/theme totals, link-health split, fiscal-timing split). No individual objective statement, owner name, or metric/target value is newly exposed by this feature — only counts.

**Trust boundaries crossed**: browser → API → Postgres — the same shape as every other ADP dashboard read; no new external system.

**Abuse cases**:
- A user without Strategy-domain familiarity infers sensitive business-timing information (e.g., "the org has 3 objectives past due") from an aggregate count alone → accepted as equivalent risk to every other already-ungated dashboard aggregate (application health distribution, TIME disposition counts, capability/domain totals) — aggregate counts are not treated as more sensitive than the individual records they summarize, and the individual `StrategicObjective` records themselves are already ungated reads (confirmed in Assumptions).

**Residual risk**: the same class already accepted for every other Overview dashboard tile — reused read path, no new authorization mechanism, no new data exposed beyond what a user could already compute themselves from the existing Strategy screen and Objectives list.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See Strategy's presence and scale at a glance (Priority: P1)

An architect lands on the Overview dashboard and sees a fifth "Strategy" domain card, alongside the existing Business, Enterprise, Solution, and Technical cards, showing how many strategic objectives and themes currently exist, with a control that opens the Strategy screen.

**Why this priority**: The baseline fix this feature exists for — Strategy currently has zero presence on the landing screen at all. Every other piece of this feature (the linkage bar, the fiscal breakdown) is additional signal layered on top of this minimum bar, which is valuable on its own.

**Independent Test**: Load the Overview dashboard with a known number of strategic objectives and themes seeded; confirm a Strategy card appears showing those exact counts, visually consistent with the other four cards, and that clicking its deep-link opens the Strategy screen's Objectives view.

**Acceptance Scenarios**:

1. **Given** the platform has strategic objectives and themes recorded, **When** an architect opens the Overview dashboard, **Then** a Strategy domain card appears in the same "Architecture domains" grid as the existing four cards, showing the total objective count and total theme count.
2. **Given** the Strategy card is visible, **When** the architect clicks its deep-link control, **Then** they are taken to the Strategy screen's Objectives view — the same navigation pattern the other four cards use for their own screens.
3. **Given** no strategic objectives or themes have been created yet, **When** an architect opens the Overview dashboard, **Then** the Strategy card still renders (zero counts, no error), consistent with how the dashboard already handles an empty Business/Enterprise/Technical domain.
4. **Given** the Strategy card is visible, **When** an architect looks for a progress-to-target percentage on it, **Then** none is shown — the card never fabricates a completion metric the underlying data can't support.

---

### User Story 2 - Spot untraceable objectives as a governance signal (Priority: P2)

An architect looks at the Strategy card and can immediately tell whether any strategic objectives have zero links to a capability or value stream — objectives that can't be traced from and that nothing else in the platform rolls up to.

**Why this priority**: The direct payoff of the platform's own governance thesis applied to Strategy specifically — an untraceable objective is exactly the kind of "finding nobody re-checks" the rest of ADP already surfaces for other domains. Depends on User Story 1's card existing, so it's second.

**Independent Test**: Seed a mix of objectives — some linked to at least one capability or value stream, some linked to neither — and confirm the card's linkage indicator correctly splits the two groups and visually flags the unlinked group as a warning, not a neutral stat.

**Acceptance Scenarios**:

1. **Given** some objectives have at least one linked capability or value stream and others have none, **When** an architect views the Strategy card, **Then** it shows a two-segment breakdown distinguishing linked objectives from unlinked ones.
2. **Given** at least one objective has zero links, **When** an architect views the card, **Then** the unlinked segment is visually presented as a warning/at-risk state, consistent with how the dashboard's existing "At risk" tile is styled.
3. **Given** an objective is linked to a value stream but not to any capability (or vice versa), **When** the linkage split is computed, **Then** that objective counts as linked — having either kind of link is sufficient, neither is individually required.
4. **Given** every objective has at least one link, **When** an architect views the card, **Then** the warning state does not appear (or shows zero), and the card does not falsely imply a governance problem where none exists.

---

### User Story 3 - Spot past-due objectives as a governance signal (Priority: P3)

An architect looks at the Strategy card and can immediately tell how many objectives belong to the current fiscal period, how many are upcoming, and how many are already past their fiscal period without (as far as this card shows) having been closed out.

**Why this priority**: A second, independent governance signal layered on the same card. Lower priority than the linkage signal (User Story 2) because a stale-but-linked objective is a smaller traceability gap than an objective nothing can trace to at all, but it's still real value on its own and independently testable.

**Independent Test**: Seed objectives across past, current, and future fiscal periods (relative to a known server date); confirm the card correctly buckets each into past-due, current, or upcoming, and visually flags the past-due bucket as a warning.

**Acceptance Scenarios**:

1. **Given** objectives exist in past, current, and future fiscal periods, **When** an architect views the Strategy card, **Then** it shows a breakdown of how many objectives fall into each of the three buckets.
2. **Given** at least one objective is in a past fiscal period, **When** an architect views the card, **Then** the past-due count is visually presented as a warning state.
3. **Given** the classification is computed, **When** two architects in different browser time zones view the same dashboard, **Then** they see the same bucket counts — the classification is anchored to the server's current date, not each browser's local clock.

---

### Edge Cases

- What happens when zero strategic objectives exist yet? → The card still renders: mini-stats show zero counts, the linkage and fiscal breakdowns show an empty/zero state — not an error, not a blank card, not a divide-by-zero failure.
- What happens to an objective whose period is `FY` (the whole fiscal year, not a specific quarter) — is it ever "past due" partway through that year? → No: an `FY`-period objective is past due only once its entire fiscal year has fully elapsed (the current fiscal year is later than the objective's). A quarterly objective (`Q1`–`Q4`) is past due once the current period is later than its own within the same fiscal year, or the fiscal year itself has passed.
- What happens when a capability or value stream a linked objective points to is later deleted from its own registry? → Not independently reachable: the existing cascading-delete behavior (ADP-d8u.1) already removes the link row along with the deleted registry record, so the objective correctly reverts to "unlinked" on its own — no orphaned "linked" state is possible for this card to misreport.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The Overview dashboard MUST display a fifth domain card for Strategy, in the same "Architecture domains" grid as the existing Business, Enterprise, Solution, and Technical cards, matching their visual and structural convention (icon, title, description, mini-stat row, deep-link control).
- **FR-002**: The card's mini-stats MUST show the total count of strategic objectives and the total count of strategic themes.
- **FR-003**: The card MUST NOT display any progress-to-target or completion-percentage metric, since the current strategic-objective metric group (name, target, unit, direction) has no stored current/actual value to compute one from.
- **FR-004**: The card MUST show a linkage-health breakdown distinguishing objectives with at least one confirmed link (to a capability and/or a value stream) from objectives with zero links.
- **FR-005**: An objective with at least one capability link OR at least one value-stream link counts as linked for FR-004 — neither link type is individually required.
- **FR-006**: Objectives with zero links MUST be visually presented as a warning/at-risk state, not a neutral statistic.
- **FR-007**: The card MUST show a fiscal-period breakdown of objectives into three buckets: current period, upcoming, and past due.
- **FR-008**: The fiscal-period classification MUST be computed against the server's current date, not the requesting browser's local date or clock.
- **FR-009**: Objectives in the past-due bucket MUST be visually presented as a warning state.
- **FR-010**: The card MUST include a deep-link control that navigates to the Strategy screen's Objectives view, consistent with how the other four domain cards' controls navigate to their own screens.
- **FR-011**: Every count and classification on the card MUST be computable from already-stored fields (objective and theme records, the existing objective↔capability and objective↔value-stream link tables, and each objective's fiscal year and period) — this feature requires no new persisted field and no schema migration.
- **FR-012**: The card's underlying read surface MUST require the same normal authentication as every other Overview dashboard element, and MUST NOT be gated behind a stricter permission than the comparable Business/Enterprise summary statistics already shown ungated on the same dashboard.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An architect can state the total number of strategic objectives and themes without navigating away from the Overview dashboard.
- **SC-002**: An architect can tell, within one glance at the dashboard, whether any strategic objectives currently lack traceability to a capability or value stream.
- **SC-003**: An architect can tell, within one glance at the dashboard, whether any strategic objectives are past their fiscal period.
- **SC-004**: Every count shown on the card matches the true underlying data at the moment the dashboard loads it — no fabricated, estimated, or stale-beyond-the-platform's-normal-refresh-behavior figure.
- **SC-005**: Reaching the Strategy screen from the Overview dashboard takes exactly one click, the same as reaching any of the other four domain screens from their cards.

## Out of Scope

- Any progress/completion percentage tied to a metric target (FR-003) — would require a new "current value" field this feature does not add.
- The portfolio-level strategy map / causal view (Layer 0 → Layer 3 rollup) — a separate, larger piece of open-frontier work.
- Reverse traceability from Solution Designs back to strategic objectives — tracked separately (ADP-d8u.2).
- Any change to how objectives or themes are captured, or to the metric-group shape itself.

## Assumptions

- **Theme count scope**: the theme mini-stat counts every strategic theme in the registry, including themes not yet referenced by any objective — matching how the existing Business card's domain count includes domains with zero capabilities.
- **"Linked" definition (resolves the source material's own flagged open question)**: an objective counts as linked if it has at least one capability link or at least one value-stream link — the source request's own "Card contents" section already specifies this as an either/or condition ("at least one confirmed link... to a capability and/or a value stream"); the later-listed open question is resolved using that same wording, not left ambiguous.
- **Fiscal calendar (resolves the source material's own flagged open question)**: "current period" is derived from the server's current date mapped onto fixed calendar-year quarter boundaries (Q1 = Jan–Mar, Q2 = Apr–Jun, Q3 = Jul–Sep, Q4 = Oct–Dec). Confirmed directly against the codebase that no configurable per-organization fiscal-calendar-start field exists anywhere today, so there is nothing to make configurable yet — this assumption can be revisited if a future feature introduces one.
- **Aggregate-endpoint shape (resolves the source material's own flagged open question)**: whether this card's figures are computed by extending the existing objectives-list response or by a new dedicated summary endpoint is a planning-phase decision, not a scope decision — this spec requires only that the four displayed facts (objective count, theme count, linked/unlinked split, fiscal-period split) are correct and current, not any particular API shape.
- **Sensitivity gating (resolves the source material's own flagged open question)**: this card's aggregate reads stay ungated, matching the platform's existing convention that route-permission enforcement is a documented no-op for safe (read) HTTP methods, and that comparable Business/Enterprise dashboard aggregates are already shown without any additional permission gate.
- **Presentation-only for v1**: mini-stats and the two breakdown bars are not required to be independently clickable/filterable beyond the one existing deep-link to the Objectives screen — matching how the other four cards' own mini-stats are non-interactive today.
