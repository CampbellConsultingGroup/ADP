# Research: C4 Visual Design Workspace

**Branch**: `009-c4-workspace` | **Date**: 2026-07-01  
**Phase**: 0 — Decisions and rationale before design begins

## Decision 1: React + React Flow for Canvas Rendering

**Decision**: React 18 as the UI framework with React Flow v11 as the diagram/canvas library.

**Rationale**: React Flow is purpose-built for node-edge diagrams — exactly the shape of a C4 diagram (elements = nodes, relationships = edges). It provides: built-in pan/zoom, selection, drag-and-drop positioning, custom node/edge renderers, and a typed state model. Custom node components allow the locked theme to be applied per element type without any style controls exposed to users. The React Flow node/edge model is a CLIENT-ONLY concern; the canonical model lives in the API.

**Alternatives considered**:
- D3.js — more flexible but requires building the node-edge abstraction from scratch; significantly more work
- Excalidraw / Mermaid — opinionated about styling; don't support the locked-theme constraint without heavy forking
- plain SVG with React — viable but React Flow's node positioning and interaction model would need to be rebuilt

---

## Decision 2: TanStack Query + Zustand for State

**Decision**: TanStack Query v5 for server state (API data, mutations, optimistic updates); Zustand v4 for local UI state (which element is selected, active C4 level, panel open/closed).

**Rationale**: TanStack Query's optimistic update support is essential: when the architect places an element, the canvas shows it immediately while the API mutation is in flight; if the API returns a conflict (409), the query invalidates and the canvas reverts. Zustand is lightweight for the small amount of ephemeral UI state not tied to the server.

---

## Decision 3: Vite as Build Toolchain

**Decision**: Vite 5 with TypeScript; no Create React App.

**Rationale**: Vite is the modern standard for React/TypeScript apps; fast HMR; simpler configuration than webpack. TypeScript enforces the typed API contract at compile time — if ADP-SPEC-003's types change and the web client doesn't update, the build fails, preventing silent drift.

---

## Decision 4: C4 Level → Element Kind Mapping

**Decision**: Each C4 level shows specific element kinds:
- **Context level**: `person` + `system` elements; relationships between them
- **Container level**: `system` + `container` elements; relationships between them  
- **Component level**: `container` + `component` elements; relationships between them

This mapping is hardcoded in `c4-filter.ts` and tested. Switching levels filters the canonical model's elements by kind; no separate diagram source is used.

**Rationale**: This matches the canonical C4 model hierarchy. Architects work at the level appropriate to their persona (enterprise → context, solution → container, technical → component).

---

## Decision 5: Layout Persistence — Dedicated API Endpoint

**Decision**: Canvas element positions (2D x/y coordinates) are stored in a new `PUT /api/v1/designs/{id}/layout` endpoint that accepts a JSON map of `element_id → {x, y}`. Layout is fetched with `GET /api/v1/designs/{id}/layout`. This endpoint is a new addition to ADP-SPEC-003 (router `layouts.py`).

**Rationale**: Layout is a UI concern, not a model concern — storing it in the canonical `Element` model would violate ART-II (adding diagram-specific data to the model). A separate endpoint keeps the canonical model clean while providing durable layout storage. Layout is NOT tied to model versioning — changing positions doesn't bump the design version.

**Layout data shape**:
```json
{
  "design_id": "DESIGN-001",
  "level": "container",
  "positions": {
    "ELM-001": {"x": 120, "y": 80},
    "ELM-002": {"x": 350, "y": 200}
  }
}
```

---

## Decision 6: Theme Contract — JSON Configuration from ADP-SPEC-010

**Decision**: The workspace fetches the locked C4 theme as a JSON object from a `GET /api/v1/theme/c4` endpoint. The theme JSON maps element kind → visual style (fill color, border color, border style, icon, font, shape). The workspace MUST NOT allow overrides. The theme is cached client-side with a long TTL (invalidated on explicit theme update).

**Theme JSON shape (v1 baseline)**:
```json
{
  "version": "1.0.0",
  "locked": true,
  "styles": {
    "person": {"fill": "#08427B", "stroke": "#073B6F", "color": "#ffffff", "shape": "actor"},
    "system": {"fill": "#1168BD", "stroke": "#0E5FA3", "color": "#ffffff", "shape": "box"},
    "container": {"fill": "#438DD5", "stroke": "#3C7FC0", "color": "#ffffff", "shape": "box"},
    "component": {"fill": "#85BBE0", "stroke": "#78A8CC", "color": "#000000", "shape": "box"}
  }
}
```

---

## Decision 7: Optimistic Concurrency (NFR-002)

**Decision**: TanStack Query's optimistic update pattern:
1. When an architect submits a canvas mutation (place element, draw relationship), the UI updates immediately (optimistic)
2. The API mutation fires asynchronously
3. If the API returns 200: the query re-fetches and confirms the update
4. If the API returns 409 (conflict): TanStack Query reverts the optimistic update, refetches the latest model version, and displays a conflict notification: "Another user has edited this design. Your change was not saved — please review the latest version and retry."

This satisfies NFR-002 without requiring real-time WebSocket infrastructure.

---

## Decision 8: Schema Validation Before API Commit

**Decision**: The API client validates mutation requests against TypeScript types derived from ADP-SPEC-001's JSON Schema before sending them. If the mutation would be invalid (e.g., a relationship targeting a non-existent element id), the canvas shows a typed error and rolls back the action without making a network request.

This satisfies FR-006 at the client level; the API enforces the same validation server-side as a second layer.

---

## Decision 9: Testing Strategy

**Decision**:
- **Unit**: Vitest for pure logic (theme resolution, C4 filter, element kind mapping)
- **Component**: React Testing Library for component interaction (clicking an element shows the panel; placing an element sends a mutation)
- **E2E**: Playwright against a running ADP backend (ADP-SPEC-003) with a seeded test design; verifies the full flow: open workspace → place element → verify element appears in model via API query

All E2E tests require the ADP backend to be running (similar to ADP-SPEC-002's integration tests requiring Docker). They run in CI but are marked `@slow`.
