# Quickstart: Using the C4 Visual Design Workspace

**Branch**: `009-c4-workspace` | **Date**: 2026-07-01  
**Prerequisites**: ADP backend running; authenticated as Architect; design DESIGN-001 exists

---

## Starting the Web Client

```bash
cd web/
npm install
npm run dev   # Vite dev server at http://localhost:5173
```

Open `http://localhost:5173/designs/DESIGN-001` to open the workspace for DESIGN-001.

---

## US1: Placing Elements and Drawing Relationships

```
1. The canvas opens at the Container level by default (or the last-used level)
2. Click "Add Element" → select kind "Container" → type name "API Gateway"
3. The element appears on the canvas; the API immediately creates an Element record:
   GET /api/v1/designs/DESIGN-001 → now contains ELM-XXX with kind=container
4. Drag the element to position it; positions are saved automatically
5. Hover over ELM-XXX → drag the connection handle to another element
6. The relationship line appears; the API creates a Relationship record
```

**What the user sees**: Instant visual feedback (optimistic update); the API confirms in < 2 seconds; if the API rejects, the element/relationship disappears with an error tooltip.

---

## US2: Switching C4 Levels

```
1. Level toggle at the top of the workspace: [Context] [Container] [Component]
2. Click "Context" — the canvas immediately shows only person + system elements
3. The same DESIGN-001 model is used; no separate diagram is drawn
4. Container-level elements (API Gateway, etc.) are hidden at the context level
5. Click "Container" to return — all container elements reappear in their last positions
```

---

## US3: Inspecting an Element

```
1. Click on the "API Gateway" container element
2. The Inspection Panel slides in on the right:
   ┌─────────────────────────────────────┐
   │ API Gateway (container)              │
   │                                     │
   │ Satisfies:                          │
   │   • REQ-001: Stateless handling     │
   │   • REQ-003: Auth at gateway        │
   │                                     │
   │ Provenance:                         │
   │   Accepted from recommendation      │
   │   OPT-001 (JWT Auth Option)         │
   └─────────────────────────────────────┘
3. Click elsewhere on the canvas to close the panel
```

---

## US4: Locked Styling

```
All "container" elements: blue box (#438DD5), white text
All "system" elements: darker blue box (#1168BD), white text
All "person" elements: dark navy actor-shape (#08427B), white text

No color picker, no border selector, no font size control anywhere in the UI.
The Properties panel for an element shows only: Name, Description, Satisfies links.
```

---

## Conflict Scenario (NFR-002)

```
1. Architect A opens DESIGN-001 at version 3
2. Architect B places an element → design is now version 4
3. Architect A tries to place a different element
4. API returns 409 Conflict
5. Canvas shows banner: "Design was updated by another user.
   Your change was not saved. Reload to see the latest version."
6. Architect A clicks "Reload" → sees Architect B's element; retries their action
```
