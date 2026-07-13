---
spec_id: ADP-SPEC-017
title: Intake Proposal Status Sync and Rejected Requirements Layout
status: draft
version: 0.1.0
depends_on: [ADP-SPEC-014, ADP-SPEC-016]
articles_engaged: [ART-I, ART-IV]
quality_gates: [QG-04]
owner: enterprise-architecture
---

# ADP-SPEC-017 — Intake Proposal Status Sync and Rejected Requirements Layout

## Overview

Fix two related defects in the Requirements Intake screen:

1. When a proposal is confirmed or rejected, it remains visible in the proposals list because the UI cache is not refreshed after the mutation. Confirmed and rejected proposals must be immediately removed from the "Extracted Proposals" list.

2. The "Rejected Requirements" section is positioned in the left extraction panel. It should appear in the right sidebar, directly below the "Confirmed Requirements" list, so both outcomes of reviewing proposals are visible in the same column.

## User Scenarios & Acceptance Criteria

- **Proposal removed on action.** Given a proposal is in the Extracted Proposals list, when the architect confirms OR rejects it, then it disappears from that list immediately (no page reload).
- **Rejected section placement.** Given one or more proposals are rejected, when viewed, then the "Rejected Requirements" section appears in the right sidebar, below the Confirmed Requirements list — not in the left extraction panel.
- **Right sidebar layout.** Given the right sidebar, when viewed, then it shows: Confirmed Requirements (top) → Rejected Requirements (bottom, only if rejections exist).

## Functional Requirements

- **FR-001**: After a confirm or reject action completes, the intake status query MUST be refreshed so the proposal list reflects the new state.
- **FR-002**: A confirmed proposal MUST disappear from the Extracted Proposals list immediately after confirmation.
- **FR-003**: A rejected proposal MUST disappear from the Extracted Proposals list immediately after rejection.
- **FR-004**: The "Rejected Requirements" section MUST be rendered in the right sidebar, below the Confirmed Requirements list.
- **FR-005**: The left extraction panel MUST NOT contain the Rejected Requirements section.

## Assumptions

- The intake status API already returns correct proposal statuses after mutation (verified: `_intake_store` updates correctly).
- The fix is in the TanStack Query invalidation — adding `["intake-status", designId, operationId]` to the `onSuccess` invalidation in `useConfirmProposal` and `useRejectProposal`.
- The layout fix moves `RejectedRequirementsSection` from `IntakePage`'s left panel into the right sidebar column, after `RequirementsList`.
