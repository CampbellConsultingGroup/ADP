# Data Model: C4 Visual Design Workspace

**Branch**: `009-c4-workspace` | **Date**: 2026-07-01  
**Sources**: `web/src/api/` (TypeScript API client), `src/adp/api/routers/layouts.py` (new Python endpoint)

---

## UI-Layer Entities

These types exist only in the web client. They are NOT canonical model entities.

### `C4Level` (TypeScript enum)

```typescript
enum C4Level {
  CONTEXT = "context",
  CONTAINER = "container",
  COMPONENT = "component"
}
```

### `ElementPlacement` (client-only)

The 2D position of an element on the canvas. Stored in the layout API, not in the canonical model.

| Field | Type | Notes |
|---|---|---|
| `element_id` | `string` | References `Element.id` from ADP-SPEC-001 |
| `x` | `number` | Canvas x coordinate |
| `y` | `number` | Canvas y coordinate |

### `DiagramLayout` (API response / client cache)

The full layout record for one design at one C4 level.

| Field | Type | Notes |
|---|---|---|
| `design_id` | `string` | Parent design |
| `level` | `C4Level` | The C4 level this layout applies to |
| `positions` | `Record<string, {x: number, y: number}>` | element_id → position map |

### `C4NodeData` (React Flow node data)

Custom data attached to a React Flow node. Derives from the canonical `Element` and the theme.

| Field | Type | Notes |
|---|---|---|
| `element` | `Element` (from ADP-SPEC-001) | Full canonical element record |
| `style` | `C4ElementStyle` | Derived from theme by element kind |
| `selected` | `boolean` | Local UI state |

### `C4ElementStyle` (derived from theme)

| Field | Type | Notes |
|---|---|---|
| `fill` | `string` | Background color (hex) |
| `stroke` | `string` | Border color (hex) |
| `color` | `string` | Text color (hex) |
| `shape` | `"box" \| "actor"` | Shape type |

### `WorkspaceState` (Zustand store)

| Field | Type | Notes |
|---|---|---|
| `activeLevel` | `C4Level` | Currently displayed C4 level |
| `selectedElementId` | `string \| null` | Which element is selected in the canvas |
| `inspectionPanelOpen` | `boolean` | Whether the traceability panel is visible |
| `designId` | `string` | The design being edited |

---

## C4 Level → Element Kind Filter

Defined in `web/src/canvas/c4-filter.ts`. Pure function, fully tested.

```typescript
const C4_LEVEL_KINDS: Record<C4Level, ElementKind[]> = {
  [C4Level.CONTEXT]:   ["person", "system"],
  [C4Level.CONTAINER]: ["system", "container"],
  [C4Level.COMPONENT]: ["container", "component"],
};

function filterElementsForLevel(
  elements: Element[], level: C4Level
): Element[] {
  const kinds = C4_LEVEL_KINDS[level];
  return elements.filter(e => kinds.includes(e.kind));
}
```

Relationships are filtered by whether both endpoints are visible at the current level.

---

## New Backend Entity: Layout Record

Stored in a new Python module (`src/adp/api/routers/layouts.py`). NOT part of the canonical model — stored as a simple JSON document keyed by `(design_id, level)`.

**Storage approach for v1**: In-memory dict in the process (same as operation store pattern from ADP-SPEC-003). Layout data is transient — losing it means the canvas re-positions automatically (auto-layout fallback). A persistent store (database table) is v2.

---

## Relationships to ADP-SPEC-001 Entities

| Workspace Concept | Canonical Model | Notes |
|---|---|---|
| Canvas node | `Element` | Node renders from `Element`; position from `DiagramLayout` |
| Canvas edge | `Relationship` | Edge renders from `Relationship` |
| Level filter | `ElementKind` | Kind determines which C4 level shows this element |
| Inspection panel | `Element.satisfies` + `Element.provenance` | Read directly from canonical `Element` |
| Style | `ElementKind` + theme | Theme maps kind → style; NOT stored in element |
| Mutation | API POST/PUT | Every canvas change → Platform API call |
