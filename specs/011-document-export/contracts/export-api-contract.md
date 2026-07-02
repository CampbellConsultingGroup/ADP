# Contract: Export & Import API

**Module**: `src/adp/api/routers/export_router.py`
**Date**: 2026-07-02

Two endpoints for durable export to version control and round-trip import. Export is a consequential action requiring explicit human confirmation (ART-VIII / QG-14).

---

## `POST /api/v1/designs/{design_id}/export`

Write a complete export bundle for a design to the configured version control path.

**Auth**: `architect` or `enterprise_architect` role required
**Content-Type**: `application/json`

**Request body**:
```json
{
  "confirmation_id": "CONF-001",
  "export_root": "/srv/exports"
}
```

**ART-VIII enforcement**: `confirmation_id` is required. A request without it, or with an already-consumed or expired confirmation ID, returns 400.

| Field | Required | Notes |
|---|---|---|
| `confirmation_id` | Yes | Valid confirmation ID from the confirmation flow |
| `export_root` | Yes | Absolute path to the configured VCS repository root |

**Response 200** (export succeeded):
```json
{
  "design_id": "DESIGN-001",
  "model_version": 3,
  "export_path": "/srv/exports/exports/DESIGN-001/v3",
  "artifacts": [
    "model.json", "model.yaml", "traceability.json", "README.md",
    "context/diagram.dsl", "context/diagram.svg", "context/diagram.png",
    "container/diagram.dsl", "container/diagram.svg", "container/diagram.png",
    "component/diagram.dsl", "component/diagram.svg", "component/diagram.png"
  ],
  "audit_entry_id": "AUD-042"
}
```

**Response 400**: Missing or invalid `confirmation_id`
**Response 403**: Role insufficient (not architect or enterprise_architect)
**Response 404**: Design not found
**Response 409**: Export directory already exists at this version (prevent overwrite)
**Response 422**: Design fails schema validation — export aborted, no files written

---

## `POST /api/v1/designs/import`

Re-import an exported canonical model JSON and reconstruct the in-memory representation.

**Auth**: `architect` or `enterprise_architect` role
**Content-Type**: `application/json`

**Request body**:
```json
{
  "model_json": "{\"schema_version\": \"1.0.0\", \"id\": \"DESIGN-001\", ...}"
}
```

**Response 200** (import succeeded):
```json
{
  "design_id": "DESIGN-001",
  "schema_version": "1.0.0",
  "element_count": 4,
  "relationship_count": 2,
  "validation_warnings": []
}
```

**Response 422**: Schema validation failed — identifies the failing constraint:
```json
{ "detail": "Import failed: schema_version '2.0.0' is not supported (current: '1.0.0')" }
```

**Response 422**: JSON parse error, referential integrity failure, orphan references

---

## Contract Test Requirements

- `POST /export` without `confirmation_id` returns 400
- `POST /export` with valid confirmation + valid design writes all 13 artifacts and returns 200
- `POST /export` returns 409 if the export directory already exists
- `POST /export` with an invalid design returns 422 and writes zero files
- `POST /export` audit entry is written (check `AUD-NNN` ID in response)
- `POST /import` with valid `model.json` returns 200 with correct element/relationship counts
- `POST /import` with wrong `schema_version` returns 422 with version mismatch detail
- `POST /import` with malformed JSON returns 422
