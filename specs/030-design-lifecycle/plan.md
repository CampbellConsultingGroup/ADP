# Implementation Plan: Design Lifecycle Management

**Branch**: `030-design-lifecycle` | **Date**: 2026-07-05 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/030-design-lifecycle/spec.md`

## Summary

Adds lifecycle status (draft/proposed/current/deprecated/decommissioned) and four optional lifecycle dates to every ADP design. Lifecycle is stored in the canonical `ArchitectureDescription` model (JSONB — for exports) AND as indexed columns on the `designs` table (for fast portfolio filtering). A `PATCH /lifecycle` endpoint enforces the transition graph and writes an audit entry per transition. The Designs screen gains status badges, lifecycle filter, and an overdue-review indicator.

## Technical Context

**Language/Version**: Python 3.12 (backend); TypeScript 5.x (frontend)
**Primary Dependencies**: FastAPI, SQLAlchemy 2 async, asyncpg, Pydantic v2, React 18, TanStack Query v5 — all existing stack, zero new packages
**Storage**: PostgreSQL 16 — add `lifecycle_status` (B-tree indexed) + 4 date columns to `designs` table; extend `ArchitectureDescription` JSONB with lifecycle fields
**Testing**: pytest + FastAPI TestClient; existing contract test patterns
**Target Platform**: Same as existing ADP — Linux server, browser frontend
**Performance Goals**: SC-002 — lifecycle filter returns in under 500ms regardless of portfolio size
**Constraints**: Additive schema change (ART-XV) — all existing designs must default to `draft` without manual action (SC-006); existing tests must pass unchanged
**Scale/Scope**: 100 designs filtered by status; `designs` table B-tree index makes filter O(log n)

## Constitution Check

| Article | Requirement | This Plan |
|---|---|---|
| ART-I | Spec-driven | Plan derived from spec.md ✅ |
| ART-II | Model is source of truth | `LifecycleStatus` + dates added to `ArchitectureDescription`; `designs` table columns are derived index ✅ |
| ART-IV | TDD | Contract tests before implementation in each phase ✅ |
| ART-V | Security by design | Auth required on PATCH; invalid transitions rejected 409 ✅ |
| ART-VIII | Human in loop | Every transition is explicit PATCH call with actor identity ✅ |
| ART-IX | Audit trail | Every transition writes audit entry with actor, old/new status, note ✅ |
| ART-XIII | Typed contracts | `LifecycleStatus` StrEnum; `LifecycleTransitionRequest` Pydantic; `DesignSummary` extended ✅ |
| ART-XV | Governed schema evolution | Additive field on `ArchitectureDescription` with defaults; versioned migration 006 ✅ |

## File Changes

| File | Action |
|---|---|
| `src/adp/models.py` | EDIT — add `LifecycleStatus` StrEnum + lifecycle fields to `ArchitectureDescription` |
| `src/adp/store/migrations/versions/006_design_lifecycle.py` | CREATE — add columns to `designs` table |
| `src/adp/store/store.py` | EDIT — sync lifecycle columns in `save()`; add `status` filter to `list_all()` and `count_all()` |
| `src/adp/api/routers/lifecycle.py` | CREATE — `PATCH /api/v1/designs/{id}/lifecycle` |
| `src/adp/api/routers/designs.py` | EDIT — add `status` query param; extend `DesignSummary` with lifecycle + `overdue_review` |
| `src/adp/api/app.py` | EDIT — register lifecycle router |
| `src/adp/calm/exporter.py` | EDIT — include lifecycle fields in CALM metadata |
| `tests/unit/test_lifecycle_model.py` | CREATE — transition graph + auto-date unit tests |
| `tests/contract/test_lifecycle_api.py` | CREATE — PATCH endpoint contract tests |
| `tests/contract/test_designs_api.py` | EDIT — lifecycle fields in list/create responses |
| `web/src/api/designs.ts` | EDIT — extend `DesignSummary`; add `useTransitionLifecycle()` hook |
| `web/src/designs/DesignsPage.tsx` | EDIT — status badges, filter dropdown, overdue indicator |
| `web/src/designs/LifecycleTransitionButton.tsx` | CREATE — transition dropdown with confirmation |

## Phase 1: Canonical Model + Migration

**Goal**: Extend data model and create indexed table columns. No API or UI yet.

### Tasks

- [ ] Add `LifecycleStatus` StrEnum to `src/adp/models.py` with five values: `draft`, `proposed`, `current`, `deprecated`, `decommissioned`
- [ ] Add lifecycle fields to `ArchitectureDescription`: `lifecycle_status: LifecycleStatus = LifecycleStatus.DRAFT`, `proposed_date: datetime | None = None`, `current_since: datetime | None = None`, `review_due: datetime | None = None`, `retirement_date: datetime | None = None`
- [ ] Create `src/adp/store/migrations/versions/006_design_lifecycle.py`: `ALTER TABLE designs ADD COLUMN lifecycle_status TEXT NOT NULL DEFAULT 'draft'`; add four nullable TIMESTAMPTZ date columns; B-tree index on `lifecycle_status`; partial index on `review_due WHERE review_due IS NOT NULL`
- [ ] Run `alembic upgrade head`; verify `\d designs` shows new columns; `SELECT lifecycle_status, count(*) FROM designs GROUP BY 1` shows all 'draft'
- [ ] Run `adp-generate` then `adp-generate --check` — schema drift gate passes

**Checkpoint**: All existing tests still pass; `adp-generate --check` exits 0.

## Phase 2: Backend — Lifecycle API

**Goal**: `PATCH /lifecycle` with transition graph, auto-dates, audit trail, and lifecycle-aware `list_all()`.

### Tests first (TDD — ART-IV)

- [ ] `tests/unit/test_lifecycle_model.py`: valid/invalid transitions; auto-date logic; default status is draft
- [ ] `tests/contract/test_lifecycle_api.py`: 200 on valid transition; 409 on invalid; audit entry written; auto-date populated; date override respected
- [ ] `tests/contract/test_designs_api.py` (extend): filter by status; new design defaults to draft; `overdue_review` computed correctly

### Implementation

- [ ] Edit `src/adp/store/store.py`:
  - `save()`: additionally update `designs` table lifecycle columns after JSONB write
  - `list_all(status=None)`: add WHERE clause on indexed `lifecycle_status` column when status is set
  - `count_all(status=None)`: same filter
- [ ] Create `src/adp/api/routers/lifecycle.py`: `VALID_TRANSITIONS` graph dict; `LifecycleTransitionRequest` Pydantic model; `PATCH /{design_id}/lifecycle` handler with transition validation, auto-dates, save, audit entry
- [ ] Edit `src/adp/api/routers/designs.py`: add `status: str | None = Query(default=None)` param; extend `DesignSummary` with lifecycle fields + computed `overdue_review`
- [ ] Register `lifecycle.router` in `src/adp/api/app.py`
- [ ] Update CALM exporter: include `lifecycle_status` + dates in CALM document metadata

**Checkpoint**: All contract tests pass; `GET /api/v1/designs?status=current` returns only Current designs.

## Phase 3: Frontend — Lifecycle Badges, Filter, Transition

- [ ] Extend `DesignSummary` TypeScript interface; add `useTransitionLifecycle(designId)` mutation hook (PATCH `/lifecycle`; invalidates `["designs"]` on success)
- [ ] Create `web/src/designs/LifecycleTransitionButton.tsx`: dropdown of valid next transitions; confirmation popover with optional Note field; calls `useTransitionLifecycle`
- [ ] Edit `web/src/designs/DesignsPage.tsx`: colour-coded status badge per row; lifecycle filter dropdown (passes `?status=` to `useDesignList()`); amber "⚠ Review overdue" chip when `overdue_review === true`; `LifecycleTransitionButton` per row

**Checkpoint**: TypeScript clean; all interactions work end-to-end.

## Phase 4: Polish

- [ ] Run `pytest tests/ --ignore=tests/integration -q` — full suite passes
- [ ] Run `ruff check src/adp/api/routers/lifecycle.py src/adp/models.py src/adp/store/store.py` — clean
- [ ] Run `cd web && npx tsc --noEmit` — zero TypeScript errors
- [ ] Verify SC-006: all existing designs show 'draft' status without any manual action
- [ ] Manual E2E: create → propose → current → set past review_due → confirm overdue indicator → deprecate → verify 3 audit entries

## Constitution Compliance Summary

- **ART-II** ✅ Lifecycle in `ArchitectureDescription` (JSONB); `designs` table columns are derived index
- **ART-IV** ✅ Unit tests for graph + auto-dates; contract tests before each implementation phase
- **ART-VIII** ✅ Every transition is explicit PATCH; no auto-transitions
- **ART-IX** ✅ Every `PATCH /lifecycle` writes audit entry with actor, old→new status, timestamp, note
- **ART-XV** ✅ Additive field with defaults; migration 006 sets DEFAULT 'draft' for all existing rows

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

[Extract from feature spec: primary requirement + technical approach from research]

## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.
-->

**Language/Version**: [e.g., Python 3.11, Swift 5.9, Rust 1.75 or NEEDS CLARIFICATION]  
**Primary Dependencies**: [e.g., FastAPI, UIKit, LLVM or NEEDS CLARIFICATION]  
**Storage**: [if applicable, e.g., PostgreSQL, CoreData, files or N/A]  
**Testing**: [e.g., pytest, XCTest, cargo test or NEEDS CLARIFICATION]  
**Target Platform**: [e.g., Linux server, iOS 15+, WASM or NEEDS CLARIFICATION]
**Project Type**: [e.g., library/cli/web-service/mobile-app/compiler/desktop-app or NEEDS CLARIFICATION]  
**Performance Goals**: [domain-specific, e.g., 1000 req/s, 10k lines/sec, 60 fps or NEEDS CLARIFICATION]  
**Constraints**: [domain-specific, e.g., <200ms p95, <100MB memory, offline-capable or NEEDS CLARIFICATION]  
**Scale/Scope**: [domain-specific, e.g., 10k users, 1M LOC, 50 screens or NEEDS CLARIFICATION]

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

[Gates determined based on constitution file]

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)
<!--
  ACTION REQUIRED: Replace the placeholder tree below with the concrete layout
  for this feature. Delete unused options and expand the chosen structure with
  real paths (e.g., apps/admin, packages/something). The delivered plan must
  not include Option labels.
-->

```text
# [REMOVE IF UNUSED] Option 1: Single project (DEFAULT)
src/
├── models/
├── services/
├── cli/
└── lib/

tests/
├── contract/
├── integration/
└── unit/

# [REMOVE IF UNUSED] Option 2: Web application (when "frontend" + "backend" detected)
backend/
├── src/
│   ├── models/
│   ├── services/
│   └── api/
└── tests/

frontend/
├── src/
│   ├── components/
│   ├── pages/
│   └── services/
└── tests/

# [REMOVE IF UNUSED] Option 3: Mobile + API (when "iOS/Android" detected)
api/
└── [same as backend above]

ios/ or android/
└── [platform-specific structure: feature modules, UI flows, platform tests]
```

**Structure Decision**: [Document the selected structure and reference the real
directories captured above]

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
