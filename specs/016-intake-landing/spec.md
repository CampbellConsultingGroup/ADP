# Feature Specification: Intake as Landing Page with Rejected Requirements Section

**Feature Branch**: `016-intake-landing`
**Created**: 2026-07-02
**Status**: Draft

## Constitutional Articles Touched

- **ART-I**: Spec-Driven Development — always applies
- **ART-II**: Model is the Source of Truth — rejected proposals remain transient; only confirmed requirements enter the canonical model; this spec does not change that
- **ART-IV**: Test-Driven Development — always applies
- **ART-IX**: Provenance and Auditability — displaying rejected proposals makes the architect's decision explicit and reviewable within the session

**ART-V**: Low risk — view-routing change only; no new data persistence or external boundary.

## Threat Model

No new threat surface. The rejected proposals section reads from the existing in-memory operation store (already accessible via the status API). No new persistence or external API boundary introduced.

## User Scenarios

### User Story 1 — Intake is the Default Landing View (Priority: P1)

An architect opens ADP. Instead of landing on the C4 canvas, they immediately see the Requirements Intake screen with the Bulk Text tab active. They can navigate to the canvas from there via a "Go to Canvas" button in the Intake header.

**Why this priority**: Requirements capture is the first step in the workflow. Starting on Intake reflects the intended usage sequence and reduces the number of clicks to get to work.

**Independent Test**: Load the app; assert the "Requirements Intake" heading is visible without any user action; assert "Bulk Text" tab is active; assert a "Go to Canvas" button is present.

**Acceptance Scenarios**:

1. **Given** the app loads at `/designs/DESIGN-001`, **When** no user action is taken, **Then** the Requirements Intake screen is visible with the Bulk Text tab active.
2. **Given** the Intake screen is shown, **When** the architect clicks "Go to Canvas", **Then** the C4 canvas workspace renders.
3. **Given** the architect is on the canvas, **When** they click "Requirements", **Then** they return to the Intake screen.

---

### User Story 2 — Rejected Proposals Shown in Dedicated Section (Priority: P1)

An architect runs an extraction, reviews proposals, and rejects one or more. The rejected proposals do not disappear — they appear in a "Rejected Requirements" section on the Intake page, visually muted. This makes the rejection decision explicit rather than silently discarding it.

**Why this priority**: Without this section, the architect cannot see what was considered and dismissed during the session. The section provides a visible, session-scoped audit of rejections.

**Independent Test**: Extract proposals; reject one; assert "Rejected Requirements" section appears with the rejected proposal's draft statement and kind.

**Acceptance Scenarios**:

1. **Given** no proposals have been rejected, **When** the Intake page is viewed, **Then** the "Rejected Requirements" section is NOT shown.
2. **Given** a proposal is rejected, **When** the Intake page re-renders, **Then** a "Rejected Requirements" section appears containing the rejected proposal's `draft_statement` and `kind`.
3. **Given** two proposals are rejected, **When** the section is viewed, **Then** each rejected proposal has its own entry with distinct statement and kind.
4. **Given** a rejected entry is displayed, **When** viewed, **Then** it is visually muted (greyed, reduced opacity, or struck through) to distinguish it from the confirmed requirements sidebar.

---

### Edge Cases

- What if ALL proposals are rejected? The section shows all rejections; the proposals area shows "No proposals remaining"; the confirmed requirements sidebar is unchanged.
- What if a new extraction is started? The rejected proposals from the previous operation are replaced when the new operation's proposals load — scope is per-operation.

## Requirements

### Functional Requirements

- **FR-001**: The application default view on first load MUST be the Requirements Intake screen (not the C4 canvas).
- **FR-002**: The Intake screen MUST include a "Go to Canvas" button that switches to the C4 canvas workspace.
- **FR-003**: When the current operation has one or more rejected proposals, the Intake page MUST render a "Rejected Requirements" section.
- **FR-004**: Each entry in the Rejected Requirements section MUST display the proposal's `draft_statement` and `kind`.
- **FR-005**: The "Rejected Requirements" section MUST NOT render when zero proposals have been rejected.
- **FR-006**: Rejected entries MUST use visually distinct muted styling.

## Success Criteria

- **SC-001**: On first load at `localhost:5173/designs/DESIGN-001`, the Requirements Intake heading is visible without any user interaction.
- **SC-002**: After rejecting a proposal, the "Rejected Requirements" section appears within the same page render — no reload required.
- **SC-003**: Each rejected entry displays the full `draft_statement` and `kind` badge.

## Assumptions

- The `view` state in `App.tsx` defaults to `"intake"` (changed from `"canvas"`).
- Rejected proposals are available in `statusData.proposals` with `status: "rejected"` — no new API calls needed.
- The section is session-scoped: shows proposals from the current `operationId` only.
- Persisting rejection history across sessions is out of scope for v1.
