# Research: Requirements Intake HTTP API and Web Screen

**Branch**: `014-requirements-intake-ui` | **Date**: 2026-07-02

---

## Decision 1: Background Task Pattern for Async Extraction

**Decision**: Use FastAPI's built-in `BackgroundTasks` to run `ExtractionOrchestrator.run()` after returning the `operation_id` to the client. The operation is tracked in the same in-process `_operation_store: dict[str, Any]` already used by ADP-SPEC-003.

**Rationale**: ADP-SPEC-003 already establishes the background-task + operation-store pattern for async AI workloads. The orchestrator's `run()` method signature is already `(submission, operation_store)` — it was designed exactly for this pattern. No new infrastructure needed.

**Alternatives considered**:
- asyncio.create_task — equally valid but FastAPI's BackgroundTasks is idiomatic and integrates with the request lifecycle (runs after response is sent)
- Celery/Redis — heavyweight; ruled out when Docker is unavailable and the pattern is in-process

---

## Decision 2: Operation Store Integration

**Decision**: The intake router will use its own module-level `_intake_store: dict[str, Any] = {}` (same pattern as other ADP-SPEC-003 routers). The key is `operation_id`; the value contains `status`, `proposals: dict[proposal_id, ExtractedProposal]`, `design_id`, `submitted_by`, and `created_at`.

**Rationale**: The existing `ExtractionOrchestrator` already expects to receive an `operation_store` dict and mutates it in place (setting `status`, `proposals`, etc.). This is the simplest integration: the router manages the store lifecycle.

---

## Decision 3: LLMClient Initialization

**Decision**: `LLMClient` reads `ADP_LLM_ENDPOINT` and `ADP_LLM_API_KEY` from environment variables (existing behavior from ADP-SPEC-006). The intake router creates a singleton `LLMClient` at module import time, or falls back to a "no-LLM" stub that returns empty proposals if `ADP_LLM_ENDPOINT` is not set, allowing the structured form path to work without LLM configuration.

**Rationale**: Matches how the recommendation engine (ADP-SPEC-007) handles missing LLM config — graceful degradation rather than a 500 error.

---

## Decision 4: Web Screen Routing

**Decision**: Add a new route `/designs/:designId/intake` to the React app. `App.tsx` already parses the design ID from the path; add a route match for `/intake` suffix that renders `<IntakePage designId={designId} />`. The intake screen is accessible from a "Requirements" navigation item in the workspace header.

**Rationale**: Keeps the intake screen co-located with the design workspace. The existing `App.tsx` routing is path-based (`getDesignIdFromPath`); extending it with a tab suffix is minimal change.

---

## Decision 5: Polling Strategy

**Decision**: Use TanStack Query's `refetchInterval` option: `useQuery({ ..., refetchInterval: (data) => data?.status === 'completed' || data?.status === 'failed' ? false : 2000 })`. Polling stops automatically when the operation completes or fails.

**Rationale**: TanStack Query's conditional `refetchInterval` pattern is idiomatic, integrates with the existing `useDesign` hook pattern, and stops polling automatically — no manual timer management needed.

---

## Decision 6: Proposal Review UI Pattern

**Decision**: Each `ExtractedProposal` is shown as a card with: (a) draft statement as editable text, (b) kind badge, (c) confidence bar, (d) source excerpt in a quoted/grey box, (e) three action buttons: Confirm / Edit & Confirm / Reject. "Edit & Confirm" shows an inline text area pre-filled with the draft statement.

**Rationale**: Mirrors the solution architecture document's description: "each extracted requirement is presented to the architect for confirmation." The source excerpt must always be visible (SC-005). The inline edit pattern avoids a modal and keeps all context visible.

---

## Decision 7: Direct Requirement Endpoint

**Decision**: `POST /api/v1/designs/{id}/requirements` creates a `Requirement` directly (no operation, no proposals). This is distinct from the intake flow. It uses `ExtractionOrchestrator` not at all — it goes directly to `DesignStore.save()` with a new `Requirement` appended.

**Rationale**: The structured form path should be simpler and faster (< 2s, SC-006). No need to create a proposal just to immediately confirm it. Direct write with audit entry is the correct implementation.

---

## Summary: New Files

**Python backend:**
- `src/adp/api/routers/intake.py` — 6 routes; uses `ExtractionOrchestrator` and `DesignStore`

**TypeScript frontend:**
- `web/src/intake/IntakePage.tsx` — top-level screen
- `web/src/intake/IntakeTextForm.tsx` — bulk text area + extract
- `web/src/intake/StructuredForm.tsx` — direct requirement form
- `web/src/intake/ProposalCard.tsx` — single proposal with actions
- `web/src/intake/ProposalsList.tsx` — proposals review panel
- `web/src/intake/RequirementsList.tsx` — confirmed requirements summary
- `web/src/api/intake.ts` — TanStack Query hooks
- `web/src/App.tsx` — (modified) add `/intake` route + nav link

**No new dependencies**: uses FastAPI BackgroundTasks (stdlib), existing TanStack Query + React.
