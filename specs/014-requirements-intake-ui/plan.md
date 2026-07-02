# Implementation Plan: Requirements Intake HTTP API and Web Screen

**Branch**: `014-requirements-intake-ui` | **Date**: 2026-07-02 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/014-requirements-intake-ui/spec.md`

## Summary

Wire the existing `adp.intake.ExtractionOrchestrator` (ADP-SPEC-006) to 6 new FastAPI routes, and build a React intake screen in the web workspace. The Python backend is nearly zero new logic — it is a thin HTTP adapter over the existing orchestrator. The TypeScript frontend is the primary deliverable: a full intake screen with two input modes (bulk text + structured form), a proposals review panel with per-card confirm/edit/reject actions, and a requirements summary sidebar. No new Python dependencies; no new TypeScript dependencies beyond what's already installed.

**Key architectural constraint**: ART-VIII — every proposal requires an explicit per-proposal architect action. There is no "confirm all" shortcut. SC-004 mandates this in tests.

## Technical Context

**Language/Version**: Python 3.11+ (backend); TypeScript 5.x (frontend — existing web/ stack)
**Primary Dependencies**: No new dependencies. Backend uses FastAPI `BackgroundTasks` (stdlib). Frontend uses existing TanStack Query v5, React 18, Zustand v4.
**Storage**: Operation store is a module-level `dict[str, Any]` in `intake.py` (same in-process pattern as ADP-SPEC-003). No DB tables needed for proposals.
**Testing**: `pytest` (backend); Vitest + React Testing Library (frontend); Playwright E2E (existing suite)
**Target Platform**: Same as existing stack (Linux/WSL, port 8001 API, port 5173 Vite)
**Performance Goals**: Extraction returns `operation_id` within 2s (SC-001); confirm writes `Requirement` within 1s (SC-002); structured form completes < 2s (SC-006)
**Constraints**: Source text NEVER persisted after extraction (existing ADP-SPEC-006 policy); no auto-confirm (ART-VIII / SC-004); `LLMClient` must gracefully degrade when `ADP_LLM_ENDPOINT` is not set

## Constitution Check

| Gate | Article(s) | Requirement | Status |
|------|-----------|-------------|--------|
| QG-01 | ART-I, ART-XVI | PR references ADP-SPEC-014 task IDs | ✅ Will be enforced |
| QG-03 | ART-III, ART-XIII | All 6 request/response models use Pydantic v2 `extra="forbid"`; TypeScript interfaces match | ✅ Planned |
| QG-04 | ART-IV | Tests written before implementation; ≥ 85% coverage on new Python modules | ✅ TDD planned |
| QG-05 | ART-IV, ART-XIII | Contract tests for all 6 API endpoints | ✅ Planned |
| QG-09 | ART-V, ART-VIII | Confirm endpoint requires explicit per-proposal action; no batch/auto confirm | ✅ FR-004 / SC-004 |
| QG-10 | ART-VI | Intake router emits structured log with trace_id and operation_id | ✅ Planned (uses existing TraceIdFilter) |
| QG-13 | ART-VIII, ART-IX | Confirm writes audit entry; reject writes audit entry; both use existing DesignStore.save() | ✅ Delegated to ExtractionOrchestrator.confirm/reject_proposal() |
| QG-14 | ART-VIII | Each confirm is an explicit per-proposal human action | ✅ No batch confirm endpoint |

**N/A**: QG-02 (no schema changes), QG-06-08 (no new SAST surface), QG-11 (no new AI steps — existing intake telemetry covers it), QG-12 (existing ADP-SPEC-006 grounding), QG-15-18 (no new model/schema/validation).

## Project Structure

### Documentation (this feature)

```text
specs/014-requirements-intake-ui/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output — API models + TypeScript interfaces
├── quickstart.md        # Phase 1 output — curl + browser examples
├── contracts/
│   ├── intake-api-contract.md   # 6 REST endpoint contracts
│   └── intake-ui-contract.md   # Screen layout + component tree + hooks
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code

```text
# Python backend (new)
src/adp/api/routers/intake.py   # 6 routes; thin adapter over ExtractionOrchestrator

# Python backend (modified)
src/adp/api/app.py              # Register intake.router

# TypeScript frontend (new)
web/src/api/intake.ts           # TanStack Query hooks for all 6 endpoints + types
web/src/intake/IntakePage.tsx   # Top-level screen; tab state (bulk/form); layout
web/src/intake/IntakeTextForm.tsx  # Bulk text textarea + Extract button
web/src/intake/StructuredForm.tsx  # Direct requirement form (statement + kind)
web/src/intake/ProposalsList.tsx   # Maps proposals to ProposalCard
web/src/intake/ProposalCard.tsx    # Single proposal: kind/confidence/excerpt + actions
web/src/intake/RequirementsList.tsx  # Right panel: confirmed requirements summary

# TypeScript frontend (modified)
web/src/App.tsx                 # Add /designs/:id/intake route
web/src/canvas/Workspace.tsx    # Add "Requirements" nav link in header

# Tests (new)
tests/contract/test_intake_api.py         # Contract tests for all 6 endpoints
tests/unit/test_intake_router.py          # Unit tests for router logic
web/tests/unit/test_intake_types.ts       # TypeScript type tests (optional)
web/tests/component/IntakePage.test.tsx   # RTL component tests
web/tests/e2e/api.spec.ts                 # (extended) intake API E2E tests
```

## New Dependencies

None. All functionality uses existing stack:
- Python: FastAPI `BackgroundTasks` (stdlib), existing `adp.intake` module
- TypeScript: existing TanStack Query v5, React 18, React Testing Library
