# Feature Specification: Design Lifecycle Management

**Feature Branch**: `030-design-lifecycle`
**Created**: 2026-07-05
**Status**: Draft
**Prerequisite for**: ADP-SPEC-031 (Portfolio Analysis Screen)

## Context

Every architecture design in ADP currently exists in a single, timeless state. There is no way to distinguish a rough proof-of-concept from a production system that has been running for three years, or to mark a design as superseded by a newer approach. The portfolio view (ADP-SPEC-025) lists all designs equally regardless of whether they represent current systems, approved proposals, or retired architectures.

Enterprise architecture practice depends critically on understanding the lifecycle of every system in the estate. A governance board cannot make sound portfolio decisions if it cannot separate "what is live today" from "what was proposed last quarter" from "what we retired two years ago". An architect choosing a reference architecture needs to know whether it describes a current pattern or a deprecated approach the organisation has moved away from.

This spec adds lifecycle management to ADP designs. Each design gains a status that reflects its position in the architecture lifecycle, along with key dates that make the lifecycle timeline concrete. Lifecycle transitions are governed — each one is an explicit action with a confirmed actor in the audit trail — and the portfolio view gains the filtering capability that allows the estate to be viewed by status.

## Constitutional Articles Touched

- **ART-I** — Spec-Driven Development: always applies
- **ART-II** — Model is Source of Truth: lifecycle status is part of the canonical design record, queryable without parsing content
- **ART-IV** — Test-Driven Development: always applies
- **ART-VIII** — Human in the Loop: lifecycle transitions are explicit human actions, not automated
- **ART-IX** — Audit Trail: every transition must be recorded with the actor, the previous state, the new state, and the timestamp

## Threat Model

**Assets at risk**: Lifecycle status data could be used to identify systems approaching end-of-life or retirement, which has operational security implications if the portfolio is visible to external parties.

**Trust boundaries crossed**: Browser → ADP API (lifecycle transition writes). No new external trust boundaries.

**Abuse cases**:
- Falsely marking a deprecated system as current to avoid governance scrutiny: mitigated by the immutable audit trail recording every transition with the responsible architect's identity.
- Skipping lifecycle states to bypass governance gates: mitigated by the governed transition model (FR-004) which restricts which transitions are permitted.

**Residual risk**: ADP does not enforce external consequences of lifecycle transitions (e.g. triggering a decommissioning work order). Lifecycle status in ADP reflects the *architecture record*; operational consequences remain the organisation's responsibility. Accepted for v1.

## User Scenarios & Testing

### User Story 1 — Transition a Design Through Its Lifecycle (Priority: P1)

An architecture team has completed a design for a new payment processing platform and wants to progress it from a working draft to a formally proposed design awaiting governance approval. A principal architect opens the design, changes its status from Draft to Proposed, and optionally sets the proposed date. Later, after governance approval, the team advances it to Current and records the date the system went live.

**Why this priority**: Without the ability to set and change lifecycle status, the entire portfolio categorisation capability has no data. This is the write path.

**Independent Test**: Open a design with status Draft; transition it to Proposed; assert the Designs list shows the Proposed badge; assert the audit log records the transition.

**Acceptance Scenarios**:

1. **Given** a design in Draft status, **When** an architect selects "Propose" from the lifecycle controls, **Then** the design status changes to Proposed and the audit log records the transition with the architect's name, the old status, the new status, and the timestamp.
2. **Given** a design in Proposed status, **When** an architect selects "Mark Current" and optionally enters a live-since date, **Then** the status advances to Current and the date is saved.
3. **Given** a design in Current status, **When** an architect selects "Deprecate", **Then** the status moves to Deprecated; the architect is prompted to provide an optional note (e.g. "Superseded by DSN-012") which is recorded in the audit entry.
4. **Given** a design in Deprecated status, **When** an architect selects "Decommission", **Then** the status moves to Decommissioned and a retirement date is automatically recorded if not already set.
5. **Given** a design in any status, **When** an architect selects "Reset to Draft", **Then** the status returns to Draft regardless of the current state; this is recorded as a deliberate rollback in the audit log.

---

### User Story 2 — Filter the Portfolio by Lifecycle Status (Priority: P1)

An enterprise architect wants to produce a list of all current production systems for a technology audit. She opens the Designs screen and selects "Current" from the lifecycle filter. The list immediately narrows to only designs in Current status. She can then further combine this with the technology filter from ADP-SPEC-029 to find "all current designs using technology X".

**Why this priority**: The filter is the primary consumer of lifecycle data. Without it, setting status has no portfolio-level payoff.

**Independent Test**: With designs in multiple lifecycle states, select the "Current" filter; assert only Current designs are shown; clear the filter and assert all designs reappear.

**Acceptance Scenarios**:

1. **Given** the Designs screen with designs in multiple lifecycle states, **When** an architect selects a lifecycle filter (e.g. "Current"), **Then** only designs with that status are displayed and the count updates accordingly.
2. **Given** an active lifecycle filter, **When** the architect clears it, **Then** all designs are shown again.
3. **Given** no designs in the selected status, **When** the filter is applied, **Then** an empty state is shown ("No designs with status [X]") rather than an error.
4. **Given** a lifecycle filter is active, **When** a new design is created, **Then** it appears in the list only if its status (Draft, by default) matches the active filter.

---

### User Story 3 — Review Lifecycle Dates (Priority: P2)

A portfolio manager wants to know which designs are overdue for their scheduled review. She sees that designs in Current status can have a "review due" date set. She filters for Current designs and scans for those with a review due date in the past, displayed with a visual indicator.

**Why this priority**: The dates give the lifecycle status its temporal substance. Without them, "Current" is a label; with them, it becomes actionable portfolio data.

**Independent Test**: Set a review_due date in the past on a Current design; assert it displays with an "overdue" indicator on the Designs screen.

**Acceptance Scenarios**:

1. **Given** a design in Current status, **When** an architect opens the design details or the Designs screen row, **Then** a "Review due" date field is visible and editable.
2. **Given** a Current design with a review_due date earlier than today, **When** the Designs screen is viewed, **Then** the design displays a visual "overdue" indicator (e.g. amber badge) alongside its lifecycle status.
3. **Given** a Current design with no review_due date set, **Then** no overdue indicator is shown; the absence of a date is valid.
4. **Given** a design in any lifecycle status, **When** its record is viewed, **Then** all dates that have been set (proposed date, live since, review due, retirement date) are shown; unset dates display as empty rather than zero or a placeholder date.

---

### Edge Cases

- **New designs default to Draft**: Every design created through the New Design flow (ADP-SPEC-025) automatically starts in Draft status. No architect action is required to assign an initial status.
- **Invalid transitions are rejected**: Attempting to transition from Draft directly to Decommissioned, or from Current directly to Proposed (moving backwards in the main path except via Reset to Draft), is rejected with a clear message explaining what transitions are valid from the current state.
- **Status visible in exports**: Lifecycle status and all dates are included in CALM exports (ADP-SPEC-021) and document exports (ADP-SPEC-011).
- **Concurrent transition attempts**: If two architects attempt to transition the same design simultaneously, one succeeds and the other receives a conflict error prompting them to reload.
- **Dates in the future**: Setting a proposed date or live-since date in the future is permitted (e.g. for planned transitions); no validation prevents future dates.
- **Bulk status operations**: Changing the lifecycle status of multiple designs simultaneously is out of scope for v1.

## Requirements

### Functional Requirements

**Lifecycle States (FR-001 to FR-002)**

- **FR-001**: Every design MUST have a lifecycle status. The valid statuses are: **Draft** (initial state; work in progress), **Proposed** (formally submitted for governance consideration), **Current** (approved and representing an active system or pattern), **Deprecated** (superseded or scheduled for replacement; still exists but not recommended), **Decommissioned** (retired; the system or pattern no longer operates). No other statuses are permitted.
- **FR-002**: Every newly created design MUST default to **Draft** status without requiring any architect action.

**Lifecycle Dates (FR-003)**

- **FR-003**: Each design MUST support four optional lifecycle dates: `proposed_date` (when the design was first submitted for governance), `current_since` (when the design entered Current status), `review_due` (the scheduled date for the next architecture review), and `retirement_date` (when the design was or will be decommissioned). All dates are optional. Dates are set manually by architects or automatically when a status transition occurs (see FR-005).

**Lifecycle Transitions (FR-004 to FR-006)**

- **FR-004**: The system MUST enforce the following permitted lifecycle transitions:
  - Draft → Proposed
  - Proposed → Current
  - Proposed → Draft (rejection/rework)
  - Current → Deprecated
  - Deprecated → Decommissioned
  - Deprecated → Current (reinstatement)
  - Any status → Draft (deliberate rollback; architect must confirm)
  Transitions not listed are rejected.
- **FR-005**: When a transition occurs, the system MUST automatically record the relevant date if it has not already been set: transitioning to Proposed sets `proposed_date`; transitioning to Current sets `current_since`; transitioning to Decommissioned sets `retirement_date`. Architects may override these auto-set dates.
- **FR-006**: Every lifecycle transition MUST write an audit entry to the design's audit log (ART-IX) recording: the actor (authenticated user), the previous status, the new status, the transition timestamp, and any optional note the architect provided.

**Portfolio Display (FR-007 to FR-009)**

- **FR-007**: The Designs screen (ADP-SPEC-025) MUST display each design's lifecycle status as a colour-coded badge alongside the design title: Draft (grey), Proposed (blue), Current (green), Deprecated (amber), Decommissioned (red).
- **FR-008**: The Designs screen MUST provide a filter control allowing architects to narrow the list by lifecycle status (select one or all statuses). The design count must update to reflect the filtered set.
- **FR-009**: Designs with a `review_due` date in the past and in Current status MUST display an "overdue" indicator on the Designs screen row, visible without opening the design.

### Key Entities

- **DesignLifecycle**: `design_id`, `status` (one of the five enumerated values), `proposed_date` (optional date), `current_since` (optional date), `review_due` (optional date), `retirement_date` (optional date). This is part of the design record, queryable independently of design content for portfolio filtering.

## Success Criteria

- **SC-001**: An architect can transition a design from Draft to Proposed in under 15 seconds of interaction, including any optional note.
- **SC-002**: Filtering the Designs screen by lifecycle status returns the correct set of designs instantly (under 500 milliseconds) regardless of portfolio size.
- **SC-003**: Every lifecycle transition is traceable in the audit log — zero transitions occur without a corresponding audit entry.
- **SC-004**: Designs overdue for review are identifiable on the Designs screen without opening individual designs; an architect can identify all overdue reviews in a portfolio in under one minute.
- **SC-005**: Lifecycle status and all dates survive a full round-trip through the CALM export and document export without data loss.
- **SC-006**: All existing designs (created before this feature) default to Draft status without requiring any manual action from architects.

## Assumptions

- Lifecycle transitions are individual-design actions only; bulk status changes across multiple designs are deferred to a future spec.
- ADP does not validate that a design meets any content criteria before allowing a transition (e.g. it does not require a design to have passing validation verdicts before moving to Current). Governance gates are a human and process concern, not enforced by ADP in v1.
- The "Reset to Draft" transition from any status is permitted as an escape hatch for errors, but is intended to be rare; its audit entry makes it visible to governance.
- Review due dates are advisory — no notifications or automated actions occur when a review due date passes. The overdue indicator is purely informational.
- The five lifecycle statuses are sufficient for v1 and cannot be customised by individual organisations. Custom workflow states are a future capability.
- `retirement_date` may be set to a future date for planned decommissioning (i.e. the design is still in Deprecated/Current state but has a scheduled end date).
