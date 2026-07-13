# Implementation Plan: Architecture Recommendation Screen

**Branch**: `018-recommendation-screen` | **Date**: 2026-07-02 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/018-recommendation-screen/spec.md`

## Summary

Wire the existing `RecommendationOrchestrator` (ADP-SPEC-007) to 3 FastAPI routes and build a React Recommendations screen. The screen sits between Intake and Canvas in a three-view workspace nav. The backend is a thin HTTP adapter pattern — same as ADP-SPEC-014 for intake. No new Python dependencies; no new TypeScript dependencies.

One critical bug fix included: `materialize_option()` in the orchestrator uses `len()+1` for audit IDs — must be changed to `_next_audit_id()` (ADP-SPEC-017 fix) before any acceptance will work without a UniqueViolationError.

## Technical Context

**Language/Version**: Python 3.11+ (backend); TypeScript 5.x (frontend)
**Primary Dependencies**: None new. Uses: existing `langgraph`, `langchain-core`, `httpx`, TanStack Query v5, React 18.
**Storage**: `_recommend_store: dict[str, Any]` in `recommend.py` (same in-process pattern). No DB tables.
**Testing**: `pytest` + Vitest + Playwright (existing)
**Performance Goals**: Pipeline completes within 60 seconds (SC-001); accept writes elements within 2 seconds
**Constraints**: ART-VII (advisory grounding), ART-VIII (confirmation_id on accept), ART-IX (audit entry), ART-XI (provenance on elements)

## Constitution Check

| Gate | Article(s) | Requirement | Status |
|------|-----------|-------------|--------|
| QG-04 | ART-IV | TDD; contract tests before implementation | ✅ Planned |
| QG-09 | ART-V, ART-VIII | Accept requires explicit confirmation_id; no auto-accept | ✅ FR-003 |
| QG-12 | ART-VII | Advisory flag surfaced in UI; advisory_acknowledged required | ✅ FR-005 |
| QG-13 | ART-VIII, ART-IX | Accept writes audit entry with actor + option ID | ✅ FR-003 |
| QG-14 | ART-VIII | Per-option explicit confirmation dialog; no batch accept | ✅ FR-003, SC-003 |

**N/A**: QG-02 (no schema changes), QG-06-08 (no new SAST), QG-10/11 (existing telemetry covers it).

## Project Structure

```text
# Python backend (new)
src/adp/api/routers/recommend.py      # 3 routes + _recommend_store + Pydantic models

# Python backend (modified)
src/adp/api/app.py                    # register recommend.router
src/adp/recommendation/orchestrator.py  # fix audit ID: len+1 → _next_audit_id()

# TypeScript frontend (new)
web/src/api/recommend.ts              # hooks: useStartRecommendation, useRecommendStatus, useAcceptOption
web/src/recommend/RecommendationPage.tsx  # top-level page
web/src/recommend/RequirementSelector.tsx # checkboxes (P2; all checked default)
web/src/recommend/OptionCard.tsx      # rank, title, advisory badge, trade-offs, elements, accept button
web/src/recommend/AcceptDialog.tsx    # ART-VIII confirmation with optional advisory checkbox

# TypeScript frontend (modified)
web/src/App.tsx                       # add "recommend" view; pass onNavigate to all pages
web/src/intake/IntakePage.tsx         # three-view nav header
web/src/canvas/Workspace.tsx          # add Recommendations nav item

# Tests (new)
tests/contract/test_recommend_api.py  # contract tests for 3 endpoints
web/tests/e2e/api.spec.ts             # extend with recommend E2E tests
```

## New Dependencies

None.
