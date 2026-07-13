# Contract: Document & View API

**Module**: `src/adp/api/routers/documents.py`
**Date**: 2026-07-02

Two read-only endpoints for generating stakeholder documents, traceability matrices, and multi-level view bundles. No side effects; no confirmation required; available to all authenticated roles.

---

## `GET /api/v1/designs/{design_id}/document`

Generate a stakeholder Markdown document from the canonical model.

**Auth**: any authenticated role
**Response 200** (`text/plain; charset=utf-8`):
```
---
design_id: DESIGN-001
schema_version: "1.0.0"
generated_at: "2026-07-02T12:34:56Z"
generator: ADP-SPEC-011
level: null
---

# My Architecture
...
```

**Response 404**: Design not found
**Response 422**: Design is schema-invalid (cannot generate from invalid model)

---

## `GET /api/v1/designs/{design_id}/traceability`

Generate the requirements traceability matrix for a design.

**Auth**: any authenticated role
**Response 200** (`application/json`):
```json
{
  "design_id": "DESIGN-001",
  "schema_version": "1.0.0",
  "generated_at": "2026-07-02T12:34:56Z",
  "total_elements": 4,
  "orphan_count": 1,
  "entries": [
    {
      "element_id": "ELM-001",
      "element_name": "API Gateway",
      "element_kind": "container",
      "satisfied_requirements": ["REQ-001", "REQ-003"],
      "provenance": "OPT-001",
      "verdict_ids": [],
      "is_orphan": false
    },
    {
      "element_id": "ELM-002",
      "element_name": "Legacy Connector",
      "element_kind": "component",
      "satisfied_requirements": [],
      "provenance": null,
      "verdict_ids": [],
      "is_orphan": true
    }
  ]
}
```

**Response 404**: Design not found

---

## `GET /api/v1/designs/{design_id}/views`

Return all three C4 level renders (context, container, component) for the design.

**Auth**: any authenticated role
**Response 200** (`application/json`):
```json
{
  "design_id": "DESIGN-001",
  "context":   { "design_id": "DESIGN-001", "level": "context",   "dsl": "...", "svg": "...", "png_base64": "..." },
  "container": { "design_id": "DESIGN-001", "level": "container", "dsl": "...", "svg": "...", "png_base64": "..." },
  "component": { "design_id": "DESIGN-001", "level": "component", "dsl": "...", "svg": "...", "png_base64": "..." }
}
```

**Response 404**: Design not found

---

## Contract Test Requirements

- `GET /document` returns 200 with Markdown starting with `---` (YAML frontmatter)
- `GET /document` frontmatter contains `design_id`, `schema_version`, `generated_at`, `generator`
- `GET /traceability` returns 200 with `entries` array; `total_elements` matches design element count
- Elements with no satisfied requirements have `is_orphan: true` in the matrix
- `GET /views` returns 200 with `context`, `container`, `component` keys all present
- All three endpoints are byte-deterministic: same design → same response
