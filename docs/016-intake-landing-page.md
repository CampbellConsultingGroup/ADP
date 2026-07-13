---
spec_id: ADP-SPEC-016
title: Intake as Landing Page with Rejected Requirements Section
status: draft
version: 0.1.0
depends_on: [ADP-SPEC-014, ADP-SPEC-015]
articles_engaged: [ART-I, ART-II, ART-IV, ART-IX]
quality_gates: [QG-04]
owner: enterprise-architecture
---

# ADP-SPEC-016 — Intake as Landing Page with Rejected Requirements Section

## Overview

Change the default view when opening ADP to the Requirements Intake screen instead of the C4 canvas. When an architect rejects an extracted proposal, display it in a visible "Rejected Requirements" section on the Intake page so the decision is explicit and reviewable — not silently discarded.

## User Scenarios & Acceptance Criteria

- **Intake is the landing page.** Given the architect navigates to `/designs/{id}`, when the page loads, then the Requirements Intake screen is shown by default (not the C4 canvas).
- **Canvas still accessible.** Given the architect is on the Intake screen, when they click "Go to Canvas", then the C4 canvas workspace is shown.
- **Rejected proposals are visible.** Given an architect rejects a proposal, when the Intake page is viewed, then the rejected proposal appears in a "Rejected Requirements" section distinct from the confirmed requirements sidebar.
- **Rejected proposals are clearly styled.** Given a rejected proposal in the section, when viewed, then it is visually distinguished (e.g. strikethrough or muted styling) with the original draft statement and kind visible.

## Functional Requirements

- **FR-001**: The default view on page load MUST be the Requirements Intake screen, not the C4 canvas.
- **FR-002**: The Intake screen MUST provide navigation to the C4 canvas workspace ("Go to Canvas" or equivalent).
- **FR-003**: When a proposal is rejected, the Intake page MUST display the rejected proposal in a "Rejected Requirements" section, distinct from the confirmed requirements sidebar.
- **FR-004**: Rejected proposals in the section MUST show the original draft statement and kind classification.
- **FR-005**: The "Rejected Requirements" section MUST only appear when at least one rejection exists in the current session's proposals.

## Out of Scope

- Persisting rejected proposals to the database (rejections remain in-session only, matching the existing transient proposal store)
- Undo/restore of rejections (future spec)

## Assumptions

- Rejected proposals are already tracked in the in-memory `_intake_store` with `status: "rejected"` (ADP-SPEC-014)
- The Rejected Requirements section is populated from the current operation's proposals, not from a global history
