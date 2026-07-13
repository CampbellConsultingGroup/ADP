# Contract: Layout Persistence API (ADP-SPEC-003 Extension)

**New endpoints**: `GET/PUT /api/v1/designs/{design_id}/layout/{level}`  
**Python module**: `src/adp/api/routers/layouts.py`  
**Date**: 2026-07-01

These endpoints store C4 diagram layout positions — 2D coordinates for element placement. Layout is NOT part of the canonical model; it is a UI concern stored separately. Changing positions does NOT bump the design version.

---

## `GET /api/v1/designs/{design_id}/layout/{level}`

Retrieve element positions for a design at a specific C4 level.

**Path parameters**: `design_id` (str), `level` (`context` | `container` | `component`)  
**Auth**: any authenticated role  
**Response 200**:
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
**Response 404**: Design not found (positions default to auto-layout in the client)

---

## `PUT /api/v1/designs/{design_id}/layout/{level}`

Save element positions for a design at a specific C4 level. Replaces the entire layout for that level.

**Auth**: `architect` or `enterprise_architect` role  
**Request body**:
```json
{
  "positions": {
    "ELM-001": {"x": 120, "y": 80},
    "ELM-002": {"x": 350, "y": 200}
  }
}
```
**Response 200**: Saved layout (same shape as GET response)  
**Response 400**: Invalid position data  
**Response 403**: Insufficient role for this design

---

## Storage (v1)

For v1, positions are stored in-process in a module-level dict (same pattern as ADP-SPEC-003's operation store). Layout is transient — a process restart clears positions and the canvas falls back to auto-layout. Persistent storage (database table) is v2.

```python
# In-process layout store (v1)
_layout_store: dict[tuple[str, str], dict[str, dict]] = {}
# Key: (design_id, level)
```
