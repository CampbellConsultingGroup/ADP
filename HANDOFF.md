# ADP Implementation Handoff Document

**Created**: 2026-07-01  
**Purpose**: Resume implementation after context compaction  
**Current branch**: `009-c4-workspace`

---

## Project Overview

ADP (AI-Assisted Architecture Design Platform) is a Python monorepo (`/home/jmuir/projects/ADP/`) that has been spec-driven from the ground up using the Speckit workflow. Every feature follows: spec → plan → tasks → analyze → implement.

The project uses a **Speckit** skill system for spec-driven development. Commands: `/speckit-specify`, `/speckit-plan`, `/speckit-tasks`, `/speckit-analyze`, `/speckit-implement`.

---

## What Has Been Completed

### Python Backend (all implemented and tested)
| Spec | Branch | Status | What it does |
|------|--------|--------|--------------|
| ADP-SPEC-001 | `001-canonical-data-model` | ✅ Done | Pydantic v2 canonical model (`adp.models`) + JSON Schema generator |
| ADP-SPEC-002 | `002-design-store` | ✅ Done | PostgreSQL persistence layer (`adp.store`) via SQLAlchemy 2 async |
| ADP-SPEC-003 | `003-platform-api` | ✅ Done | FastAPI REST API (`adp.api`) with auth, operations, confirmations |
| ADP-SPEC-004 | `004-identity-authz` | ✅ Done | RBAC authorization (`adp.authz`) + audit trail (`adp.audit`) |
| ADP-SPEC-005 | `005-knowledge-retrieval` | ✅ Done | pgvector knowledge base (`adp.knowledge`) with hybrid retrieval |
| ADP-SPEC-006 | `006-requirements-intake` | ✅ Done | LLM-assisted requirements extraction (`adp.intake`) |
| ADP-SPEC-007 | `007-recommendation-engine` | ✅ Done | LangGraph recommendation pipeline (`adp.recommendation`) |
| ADP-SPEC-008 | `008-llm-as-judge` | ✅ Done | LLM-as-a-Judge validation (`adp.validation`) with deterministic gating |

### All Python Tests Passing
```bash
python3 -m pytest tests/ --ignore=tests/integration -q --no-cov
# 248 passed (as of last run)
```

### Specs Created (not yet implemented)
| Spec | Branch | What it is |
|------|--------|-----------|
| ADP-SPEC-009 | `009-c4-workspace` | **CURRENT** — C4 Visual Design Workspace (TypeScript/React web app) |

---

## What Needs to Be Done Right Now

**Run `/speckit-implement` for ADP-SPEC-009 (`009-c4-workspace`)**

This is a **TypeScript/React web application** — fundamentally different from all prior Python specs. Key facts:

### Technology Stack
- **Language**: TypeScript 5.x
- **Framework**: React 18 + React Flow v12 (`@xyflow/react`)
- **State**: TanStack Query v5 (server state) + Zustand v4 (local UI state)
- **Build**: Vite 5
- **Testing**: Vitest + React Testing Library + Playwright (E2E)
- **Location**: New `web/` directory in the monorepo root
- **Python change**: Only one new Python file: `src/adp/api/routers/layouts.py` (layout position API) + `src/adp/api/routers/theme.py` (theme stub)

### What the workspace does
- Canvas for building C4 diagrams (context/container/component levels)
- Every element placed → `PUT /api/v1/designs/{id}` (model mutation)
- Every relationship drawn → same API mutation
- Multi-level projection: same model, different C4 level filter
- Locked theme: element styling from type only, zero style controls in UI
- Traceability panel: click element → see satisfied requirements + provenance
- Optimistic updates with 409 conflict handling

### Tasks file location
```
/home/jmuir/projects/ADP/specs/009-c4-workspace/tasks.md
```
47 tasks total. All analysis issues have been remediated.

### Key remediation already applied (analysis findings fixed)
- T015 uses `PUT /api/v1/designs/{id}` (not POST) for element placement
- React Flow v12 (`@xyflow/react`) throughout (not v11)
- T005b: theme stub endpoint (`GET /api/v1/theme/c4`) added
- T015 separates canonical model mutation from layout position save
- T043b: timing test for SC-003 performance requirement
- T044b: Python tests for `layouts.py`
- T001 includes `tsd@^0.31` devDependency for T035 type testing

---

## How to Resume: The Exact Command

After context reload, run:

```
/speckit-implement
```

The Speckit skill will:
1. Check prerequisites (tasks.md exists ✅)
2. Verify checklists (16/16 complete ✅)
3. Execute tasks T001–T047 in order
4. Mark tasks complete as it goes

---

## Environment Notes

- **Python**: 3.12.3, pip available with `--break-system-packages`
- **Node/npm**: NOT YET VERIFIED — the `web/` directory doesn't exist yet; T001 creates it
- **Docker**: NOT available in this WSL environment (integration tests skip)
- **OS**: WSL2 on Windows
- **Working directory**: `/home/jmuir/projects/ADP/`
- **Git branch**: `009-c4-workspace`

### Check if Node is available before implementing
```bash
node --version && npm --version
```
If not available, the web app cannot be implemented. The implementation will need to note this and create the files without running npm commands, similar to how Python integration tests were skipped (Docker not available).

---

## Key File Locations

```
/home/jmuir/projects/ADP/
├── specs/009-c4-workspace/
│   ├── spec.md          # Feature specification
│   ├── plan.md          # Tech stack (TypeScript/React/Vite)
│   ├── tasks.md         # 47 tasks — what to implement
│   ├── research.md      # 9 decisions (React Flow, TanStack Query, etc.)
│   ├── data-model.md    # UI entities (C4Level, DiagramLayout, etc.)
│   ├── contracts/
│   │   ├── api-client-contract.md    # TanStack Query hooks
│   │   ├── layout-api-contract.md   # New layout endpoint
│   │   └── theme-contract.md        # C4 theme JSON shape
│   └── quickstart.md    # Usage examples
├── src/adp/             # All existing Python backend
├── tests/               # All existing Python tests (248 passing)
├── pyproject.toml       # Python deps (pydantic, sqlalchemy, langgraph, etc.)
└── web/                 # DOES NOT EXIST YET — T001 creates it
```

---

## Critical Implementation Notes for 009

1. **Separation of concerns**: Element positions (x/y on canvas) go to `PUT /api/v1/designs/{id}/layout/{level}` NOT to the canonical model API
2. **No style controls**: The `C4ElementNode` React component accepts ONLY `data.element` and `data.style` — no color/stroke/fill props allowed (ART-XII / QG-17)
3. **Two new Python files needed**:
   - `src/adp/api/routers/layouts.py` — layout position store
   - `src/adp/api/routers/theme.py` — theme stub returning JSON from `contracts/theme-contract.md`
   - Both registered in `src/adp/api/app.py`
4. **React Flow v12**: Import from `@xyflow/react`, not `reactflow`
5. **Bearer token**: `localStorage["adp_token"]` with a security debt comment (XSS risk, v1 only)

---

## Specifying What Needs to Be Implemented (Task Phases)

The `/speckit-implement` command will work through the tasks in order:

- **Phase 1** (T001–T006): Create `web/` project structure, package.json, tsconfig, vite.config, AND Python layout + theme endpoints
- **Phase 2** (T007–T011): API client, state management (Zustand + TanStack Query), theme hook
- **Phase 3** (T012–T020): Canvas editing — React Flow canvas, element nodes, relationship edges, place/draw mutations
- **Phase 4** (T021–T026): Multi-level C4 projection — element filter by kind, level toggle
- **Phase 5** (T027–T032): Traceability inspection panel — satisfies + provenance
- **Phase 6** (T033–T038): Locked theme enforcement — `getElementStyle()`, no style controls
- **Phase 7** (T039–T047): Polish — Playwright E2E, layout auto-save, conflict notification, build verification

---

## Current Git State

```bash
git branch   # → 009-c4-workspace
git status   # → Python source files modified/added from prior specs; web/ doesn't exist yet
```

All prior spec implementations were committed as implementation went. This spec's implementation has NOT started yet.

---

## Prior Session Summary

The session implemented ADP-SPEC-001 through ADP-SPEC-008 (all Python), then specified, planned, tasked, and analyzed ADP-SPEC-009 (C4 Visual Design Workspace). All analysis findings were remediated. The workspace is ready for implementation.

The implementation of ADP-SPEC-009 will be the first TypeScript/React code in this project.
