# Feature Specification: Intake Proposal Status Sync and Rejected Requirements Layout

**Feature Branch**: `017-intake-status-sync`
**Created**: 2026-07-02
**Status**: Draft

## Constitutional Articles Touched
- **ART-I**: Spec-Driven Development — always applies
- **ART-IV**: Test-Driven Development — always applies

## User Scenarios

### US1 — Proposals Removed After Action (P1)
When a proposal is confirmed or rejected, it immediately disappears from the Extracted Proposals list. No reload required.

**Acceptance**: Confirm a proposal → it is gone from the list in the same render. Reject a proposal → same.

### US2 — Rejected Requirements in Right Sidebar (P1)
Rejected proposals appear in the right sidebar, directly below the Confirmed Requirements list.

**Acceptance**: After rejecting a proposal, the "Rejected Requirements" section appears in the RIGHT sidebar (not in the left extraction area).

## Requirements
- **FR-001**: `useConfirmProposal` and `useRejectProposal` MUST invalidate the `["intake-status", designId, operationId]` query on success, causing the proposal list to refresh.
- **FR-002**: The Extracted Proposals list MUST show only `status: "pending"` proposals (already filtered; only works once FR-001 is fixed).
- **FR-003**: The "Rejected Requirements" section MUST render in the right sidebar below Confirmed Requirements.
- **FR-004**: The "Rejected Requirements" section MUST NOT appear in the left extraction panel.

## Success Criteria
- **SC-001**: After confirming a proposal, it disappears from the proposals list within one render cycle (no reload).
- **SC-002**: After rejecting a proposal, it disappears from the proposals list and appears in the right sidebar "Rejected Requirements" section within one render cycle.
- **SC-003**: The right sidebar shows Confirmed Requirements above Rejected Requirements when both are present.
