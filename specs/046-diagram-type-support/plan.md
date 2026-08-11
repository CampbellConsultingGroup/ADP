# Implementation Plan: Diagram Types Beyond C4

**Branch**: `046-diagram-type-support` | **Date**: 2026-08-06 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/046-diagram-type-support/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Add five new, standalone diagram types (flowchart, sequence, ER, UML, cloud-architecture) alongside ADP's existing C4-only workspace, entirely additive — `ArchitectureDescription`, the C4 React Flow canvas, and `adp.renderer` are untouched. Reuses a sibling project's mature, 55-test-file TypeScript diagramming library (`/home/jmuir/projects/canvas`, package `@canvas/diagram-core` + portable pieces of its React editor), vendored (copied) into ADP's own `web/` package rather than depended on live, per research.md Decision 1. Parsing, DSL validation, and SVG rendering run entirely client-side (research.md Decision 2); ADP's Python backend is reduced to CRUD storage of an opaque DSL-source string plus one new PNG-export endpoint reusing the `cairosvg` dependency ADP's C4 pipeline already has (Decision 3). One new table, one new backend package, one new RBAC action — each a direct, minimal application of patterns this codebase already has, not a new mechanism.

## Technical Context

**Language/Version**: Python 3.12 (backend); TypeScript 5.x + React 18.3 (frontend, matching ADP's existing `web/` toolchain and the sibling library's own — both confirmed via direct `package.json` comparison)
**Primary Dependencies**: Backend — FastAPI, SQLAlchemy 2 async (Core), asyncpg, Alembic, Pydantic v2, `cairosvg` (already present, reused for PNG export — Decision 3) — all existing; zero new backend packages. Frontend — two new runtime dependencies matching the vendored library's own (`@dagrejs/dagre` for auto-layout, `yaml` for DSL front-matter parsing), both pure JS with no server-side coupling; React 18/TanStack Query/Vite/Vitest/Playwright all existing.
**Storage**: PostgreSQL 16 — one new table (`diagrams`), no relationship to `designs` (standalone per FR-011); DSL source stored as unparsed text (a size cap, not a syntax check — Decision 2).
**Testing**: pytest (backend CRUD contract tests, mirroring existing router test conventions) + Vitest (frontend unit tests for the vendored parser/serializer/renderer functions, largely inherited test *cases* translated from the sibling project's own 55 test files rather than invented fresh) + Playwright (one end-to-end smoke covering create→edit→render→list→delete for at least one diagram type)
**Target Platform**: Linux server (existing `adp-api` process) + browser (existing `web/` SPA) — no new deployable, no new service
**Project Type**: Web application (existing FastAPI backend + React frontend) — this feature adds to both sides of the existing split, not a new architecture
**Performance Goals**: No specific throughput target beyond "the same responsiveness as the existing C4 canvas" — client-side parsing/rendering of diagrams at the scale a single architect authors (tens to low hundreds of nodes) is already proven performant by the sibling project's own use
**Constraints**: Zero changes to `ArchitectureDescription`, `web/src/canvas/C4Canvas.tsx`, or `adp.renderer` (spec Assumptions); the vendored code must remain buildable/testable from a clean ADP checkout alone (ART-XIV — rules out any live path/submodule dependency on the sibling repo, per research.md Decision 1)
**Scale/Scope**: 5 diagram types, 1 new DB table, 1 new backend package (~4 files), 1 new frontend module (vendored library + ported editor, ~20 files copied/adapted from the sibling project), 1 new RBAC action

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Applies? | How this feature satisfies it |
|---|---|---|
| ART-I (SDD Mandatory) | Yes | spec.md (clarification resolved) → this plan → tasks.md (next command) → implementation, in order. |
| ART-II (Model is Source of Truth) | Yes | Each diagram's DSL source text is *that diagram's* authoritative representation — a second, independent typed-source-of-truth relationship parallel to (not an extension of) `ArchitectureDescription`'s. Rendered SVG/PNG is always derived from it, never hand-edited as a primary record. |
| ART-III (Machine-Readable) | Yes | The entire point of this feature — closes the gap where non-C4 diagram types have no structured, diffable home in ADP today. |
| ART-IV (TDD) | Yes | tasks.md will sequence failing backend contract tests and frontend unit tests (many translated from the sibling project's own existing test cases, not invented from scratch) before each implementation task. |
| ART-V (Security by Design) | Yes | Threat model already verified against real source (research.md's "Verified security property") rather than left as an assumption: the vendored SVG renderer escapes all user-supplied text via `escapeXml()`, confirmed by direct read, not inferred from the spec author's description. |
| ART-VI (Observability) | Yes | Diagram create/update/delete are ordinary structured-logged CRUD mutations, matching every other ADP domain router; no AI-orchestration span needed (ART-VII doesn't apply — no AI step exists in this feature). |
| ART-VII (Grounded AI Only) | No | Explicitly out of scope (spec Assumptions) — no AI-generated content anywhere in this feature. |
| ART-VIII (Human-in-the-Loop for Consequence) | No (see spec.md) | 100% human-authored content; diagram deletion is an ordinary CRUD delete, matching how business capabilities/applications/domains are already deleted in this codebase (no `confirmation_id` gate — that's reserved for AI-originated actions). |
| ART-IX (Provenance/Auditability) | No new obligation | Explicitly deferred to a later iteration (spec Assumptions) — ordinary `created_at`/`updated_at` timestamps only, no append-only audit trail integration this iteration. |
| ART-X, ART-XI (Validation gating / Traceability) | No | No LLM-as-a-Judge verdict; linking into the requirement→element→recommendation→verdict thread is an explicit stretch goal for later (spec Assumptions), not this iteration. |
| ART-XII (Fixed Visual Language) | No | The locked C4 theme governs C4 diagrams specifically; these new types render via the vendored library's own separate styling system — a deliberate, spec-documented scope boundary, not a violation. |
| ART-XIII (Typed Contracts) | Yes | New backend boundary (`POST/GET/PUT/DELETE /api/v1/diagrams`) uses Pydantic v2 models with `extra="forbid"`, identical to every other ADP router. |
| ART-XIV, ART-XV (Reproducible builds / Schema evolution) | Yes | Directly shaped research.md Decision 1 — vendoring (not a live cross-repo dependency) specifically so the build stays reproducible from a clean ADP checkout alone; the new migration is a normal, reversible Alembic step. |
| ART-XVI (Documentation as Code) | Yes (SHOULD) | This plan + research.md + data-model.md + contracts/ are the documentation; research.md's decisions are grounded in direct source reads of the reused library, not paraphrased assumptions. |

**Initial gate result**: PASS. No article is violated. **One Complexity Tracking entry is warranted** (below) for vendoring ~20 files of externally-authored source into ADP's own repo — a larger one-time addition than this project's typical single-new-module features, though each individual design decision behind it (Decisions 1–3) picked the option that *avoids* a more complex alternative (re-implementing five DSL parsers in Python, a Node sidecar, a second PNG toolchain), not one that introduces complexity for its own sake.

**Post-Phase-1 re-check**: PASS (unchanged) — data-model.md and contracts/ below implement exactly the additive, client-side-parsing, minimal-backend design described above; no new gate is implicated by the detailed design.

## Project Structure

### Documentation (this feature)

```text
specs/046-diagram-type-support/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/            # Phase 1 output (/speckit.plan command)
│   └── diagrams-api.md
├── checklists/
│   └── requirements.md
└── tasks.md               # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/adp/
├── diagrams/                          # NEW package (backend)
│   ├── __init__.py
│   ├── models.py                      # Pydantic v2: Diagram, DiagramCreate, DiagramUpdate,
│   │                                   #   DiagramListResponse, DiagramType literal (5 values)
│   ├── store.py                       # SQLAlchemy Core CRUD against the new `diagrams` table
│   └── router.py                      # POST/GET/PUT/DELETE /api/v1/diagrams,
│                                       #   POST /api/v1/diagrams/{id}/export (PNG via cairosvg)
├── authz/
│   └── roles.py                       # MODIFIED: + ActionType.WRITE_DIAGRAM
│   └── permissions.py                 # MODIFIED: grant WRITE_DIAGRAM to Solution/Technical
│                                       #   Architect (Enterprise Architect via existing wildcard);
│                                       #   PERMISSIONS_VERSION 1.7.0 -> 1.8.0
└── api/
    └── app.py                         # MODIFIED: register the new diagrams router

alembic/versions/
└── 024_diagrams.py                    # NEW migration: `diagrams` table (no FK to `designs`)

web/src/
├── canvas/                            # existing C4 canvas — UNTOUCHED
└── diagrams/                          # NEW module (frontend)
    ├── core/                          # vendored from canvas/packages/diagram-core/src/
    │   ├── model/                     #   diagram-model.ts, diagram-ops.ts, auto-layout.ts
    │   ├── dsl/                       #   flowchart-{parser,serializer}.ts, sequence.ts, erd.ts,
    │   │                               #   uml.ts, architecture.ts, c4.ts (vendored, unregistered
    │   │                               #   in ADP's UI — research.md Decision 6), registry.ts,
    │   │                               #   detect.ts, types.ts, front-matter.ts
    │   ├── libraries/                 #   icon libraries + svg-sanitizer.ts, c4-notation.ts
    │   └── render/svg-renderer.ts     #   escapeXml-hardened SVG renderer
    ├── editor/                        # vendored+adapted from canvas/apps/web/src/canvas/
    │   ├── Canvas.tsx                 #   confirmed backend-agnostic props: {model, onChange,
    │   │                               #   dslFamily, toolbarContainer}
    │   ├── shapes.tsx
    │   ├── DslPanel.tsx
    │   ├── useDslSync.ts
    │   ├── ConfirmDialog.tsx
    │   └── UnsupportedElementNotice.tsx
    │   # NOT vendored: ViolationsPanel.tsx (Standards system, deferred — FR-009),
    │   # ExportMenu.tsx's fetch call (rebuilt against ADP's own new PNG endpoint)
    ├── DiagramListPage.tsx            # NEW: User Story 3 (browse/reopen)
    ├── DiagramEditorPage.tsx          # NEW: User Story 1/2 (create/author/render), wraps Canvas
    └── api.ts                         # NEW: typed client for the new /api/v1/diagrams endpoints

tests/
├── unit/diagrams/
│   ├── test_diagrams_store.py         # NEW
│   └── test_diagrams_router.py        # NEW
└── contract/
    └── test_diagrams_api_contract.py  # NEW

web/src/diagrams/
└── **/*.test.ts(x)                    # NEW: unit tests, largely translated from the sibling
                                        #   project's own existing test cases for the vendored code
```

**Structure Decision**: One new backend package (`adp.diagrams`, ~4 files) and one new frontend module (`web/src/diagrams/`, split into `core/` — the vendored, low-diff library copy — and `editor/` — the vendored, adapted React components — plus two new ADP-authored page components and an API client). The existing `web/src/canvas/` (C4) is untouched and lives alongside `web/src/diagrams/` with no shared code between them, matching the spec's additive framing exactly. One new Alembic migration, one new RBAC action, one new router registration in `app.py` — every touch to existing files is a registration/wiring change, not a behavioral modification of what's already there.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|---------------------------------------|
| Vendoring ~20 externally-authored TypeScript files into ADP's own repo, rather than a single new small module (this project's typical feature footprint) | Reuses a mature, 55-test-file library instead of re-implementing five DSL parsers, a graph-layout algorithm, and an XSS-hardened SVG renderer from scratch — research.md Decisions 1–3 each independently chose the option that avoids a larger, more complex, redundant alternative | Re-implementing the parsers/renderer in Python (server-side) or from scratch in TypeScript: rejected as substantially more code, more risk, and direct duplication of already-tested logic, for a "smaller diff" that would actually be a much larger and riskier undertaking. A live cross-repo dependency (submodule/file-path): rejected on ART-XIV reproducibility grounds (research.md Decision 1) — the vendoring is *itself* the simpler-in-the-ways-that-matter choice, not a workaround. |
