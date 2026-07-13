# Contract: Render API

**Endpoint**: `POST /api/v1/designs/{design_id}/render`
**Python module**: `src/adp/api/routers/render.py`
**Date**: 2026-07-01

Accepts a render request for a design at a specified C4 level and returns three outputs: Structurizr DSL source, SVG image, and PNG image. All styling is applied from the locked theme — no style overrides are accepted.

---

## Request

**Path parameters**: `design_id` (str) — the design to render  
**Auth**: any authenticated role  
**Content-Type**: `application/json`

```json
{
  "level": "container"
}
```

**Type**: `RenderRequest` (Pydantic, `extra="forbid"`)

| Field | Type | Required | Values |
|---|---|---|---|
| `level` | string | Yes | `"context"` \| `"container"` \| `"component"` |

**FR-002 enforcement**: The request model has NO `style`, `color`, `fill`, or override fields. Any attempt to send extra fields is rejected with 422 (`extra="forbid"`).

---

## Response 200 — Render Successful

```json
{
  "design_id": "DESIGN-001",
  "level": "container",
  "dsl": "workspace \"My System\" {\n    model {\n ...",
  "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" ...",
  "png_base64": "iVBORw0KGgoAAAANSUhEUgAA..."
}
```

**Type**: `RenderResult` (Pydantic)

| Field | Type | Notes |
|---|---|---|
| `design_id` | string | The rendered design |
| `level` | string | C4 level that was rendered |
| `dsl` | string | Full Structurizr DSL source (UTF-8 text) |
| `svg` | string | Complete SVG XML document as a string |
| `png_base64` | string | Base64-encoded PNG bytes |

---

## Response 404 — Design Not Found

```json
{ "detail": "Design DESIGN-001 not found" }
```

---

## Response 422 — Theme Validation Failure

Returned when the loaded `c4-theme.json` fails schema validation (before the model is processed).

```json
{
  "detail": "Theme validation failed: 'locked' must be true",
  "failing_constraint": "locked"
}
```

---

## Response 422 — Invalid Request Body

Standard FastAPI validation error when `level` is missing or not in allowed values, or when unknown fields are present.

```json
{
  "detail": [
    { "loc": ["body", "level"], "msg": "field required", "type": "missing" }
  ]
}
```

---

## Error Cases

| HTTP Status | Cause | Canvas Behavior |
|---|---|---|
| 200 | Render successful | All three outputs available |
| 404 | Design not found | Show "Design not found" error |
| 422 | Invalid level, extra style fields, or theme validation failure | Show specific validation error |
| 500 | Internal render error (SVG/PNG generation failure) | Show "Render failed" error with correlation ID for support |

---

## Contract Test Requirements

- `POST /api/v1/designs/DESIGN-001/render` with `{"level": "container"}` returns 200 with `dsl`, `svg`, `png_base64` fields
- `POST` with `{"level": "container", "fill": "#FF0000"}` returns 422 (extra field rejected)
- `POST` with `{"level": "invalid"}` returns 422
- `POST /api/v1/designs/NONEXISTENT/render` returns 404
- The returned DSL contains the design title and all visible element names
- The returned SVG contains `fill` attributes matching the locked theme colors
