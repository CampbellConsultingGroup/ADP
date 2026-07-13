# Implementation Plan: C4 Visual Design Workspace

**Branch**: `009-c4-workspace` | **Date**: 2026-07-01 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/009-c4-workspace/spec.md`

## Summary

Build the interactive C4 diagramming workspace as a TypeScript/React web application that renders a node-edge canvas over the ADP canonical model. Every element placed and every relationship drawn maps to a typed API mutation through ADP-SPEC-003. The canvas enforces the locked organizational theme (ADP-SPEC-010) with no style overrides, projects the model to any of three C4 levels without separate diagram sources, and surfaces element traceability in an inspection panel.

**Key distinction from prior specs**: This is a web client application (TypeScript/React), not a Python backend service. It has a separate build toolchain, testing framework, and project structure under `web/`.

## Technical Context

**Language/Version**: TypeScript 5.x  
**Primary Framework**: React 18 + React Flow v12 (`@xyflow/react`) (node-edge diagram library; designed for exactly this use case — typed nodes/edges with custom rendering)  
**State Management**: TanStack Query v5 (server state / API data fetching with optimistic updates); Zustand v4 (local UI state: selection, hover, active C4 level, panel open/close)  
**Build Tool**: Vite 5 + TypeScript  
**Testing**: Vitest (unit/component tests); React Testing Library (component interaction tests); Playwright (E2E canvas interaction tests)  
**Storage**: Layout positions stored via a new `GET/PUT /api/v1/designs/{id}/layout` endpoint added to ADP-SPEC-003; canonical model data from existing endpoints  
**Target Platform**: Modern browsers (Chrome/Firefox/Safari); responsive for large screens; mobile out of scope  
**Project Type**: Web application (new `web/` directory in the ADP monorepo)  
**Performance Goals**: Canvas interactions < 1 second; API mutations complete within 2 seconds (NFR-001); canvas must handle up to 200 visible elements without degradation  
**Constraints**: Zero per-element or per-diagram style controls (ART-XII / QG-17); all mutations through ADP-SPEC-003 API (ART-II); schema validation before commit (FR-006); optimistic concurrency (NFR-002)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Article(s) | Requirement | Status |
|------|-----------|-------------|--------|
| QG-01 | ART-I, ART-XVI | PR references approved spec/task IDs | ✅ All tasks will reference ADP-SPEC-009 |
| QG-03 | ART-III, ART-XIII | Canvas mutations produce schema-valid typed records | ✅ FR-002/FR-006; API client validates responses against ADP-SPEC-001 schema; mutations rejected if invalid |
| QG-16 | ART-XI | Element traceability surfaced | ✅ FR-005; inspection panel shows `satisfies` and `provenance` |
| QG-17 | ART-XII | Element styling derives from locked theme; no overrides | ✅ FR-004; React Flow custom node renderer reads styles from theme JSON; no style controls in UI |

**Constitution Alignment**: ART-II is the primary article — the canvas is a VIEW over the canonical model, not the primary store. React Flow's node/edge model is a UI concern only; the canonical model (ADP-SPEC-001) remains authoritative. No in-memory diagram state bypasses the API.

## Project Structure

### Documentation (this feature)

```text
specs/009-c4-workspace/
├── plan.md              # This file
├── research.md          # Phase 0 — decisions and rationale
├── data-model.md        # Phase 1 — UI entities and API contracts
├── contracts/
│   ├── api-client-contract.md   # Typed API client contract (wraps ADP-SPEC-003)
│   ├── theme-contract.md        # Theme JSON shape consumed from ADP-SPEC-010
│   └── layout-api-contract.md   # Layout persistence endpoint (new ADP-SPEC-003 extension)
├── quickstart.md        # Phase 1 — using the workspace
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
web/
├── package.json              # Dependencies: react, react-flow, @tanstack/react-query, zustand, vite
├── tsconfig.json
├── vite.config.ts
├── index.html
├── src/
│   ├── main.tsx              # App entry point; auth + API client setup
│   ├── App.tsx
│   ├── api/
│   │   ├── client.ts         # Typed API client (ADP-SPEC-003 wrapper; auth headers)
│   │   ├── designs.ts        # Design CRUD + layout API hooks (TanStack Query)
│   │   └── theme.ts          # Theme fetch hook
│   ├── canvas/
│   │   ├── Workspace.tsx     # Top-level workspace: C4 level toggle + canvas + panel
│   │   ├── C4Canvas.tsx      # React Flow canvas; manages nodes/edges from model
│   │   ├── nodes/
│   │   │   ├── C4ElementNode.tsx  # Custom React Flow node; reads styling from theme
│   │   │   └── NodeTypes.ts       # React Flow node type registry
│   │   └── edges/
│   │       ├── C4RelationshipEdge.tsx  # Custom React Flow edge
│   │       └── EdgeTypes.ts
│   ├── inspection/
│   │   └── InspectionPanel.tsx  # Element traceability panel (satisfies + provenance)
│   ├── theme/
│   │   └── c4-theme.ts          # Theme application: element type → visual style map
│   └── store/
│       └── workspace-store.ts   # Zustand: selected element id, active C4 level, panel state
├── tests/
│   ├── unit/
│   │   ├── theme.test.ts         # Theme style resolution tests
│   │   └── c4-filter.test.ts     # C4 level element filter tests
│   ├── component/
│   │   ├── C4Canvas.test.tsx     # Canvas component tests (RTL)
│   │   └── InspectionPanel.test.tsx
│   └── e2e/
│       └── workspace.spec.ts     # Playwright E2E: place element → verify API call
└── playwright.config.ts

src/adp/api/routers/
└── layouts.py                    # New: GET/PUT /api/v1/designs/{id}/layout (ADP-SPEC-003 extension)
```

**Structure Decision**: The web app lives in `web/` as a separate package with its own build toolchain. It is NOT a Python package. The only Python change is a new `layouts.py` router in ADP-SPEC-003 for layout position persistence.
