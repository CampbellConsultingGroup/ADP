# Implementation Plan: CALM Export (ADP-SPEC-021)

## Tech Stack

- **Backend**: Python 3.12 + FastAPI; new module `src/adp/calm/exporter.py`; new router endpoint added to existing `src/adp/api/routers/export_router.py` (or new `calm.py` router)
- **CALM schema**: targeted at draft 2025-03; implemented as Pydantic v2 models in `src/adp/calm/models.py`
- **No new packages**: uses existing `pydantic`, `fastapi`, `sqlalchemy` stack
- **Frontend**: TypeScript/React; "Export as CALM" button added to canvas toolbar in `web/src/canvas/Workspace.tsx`; uses `fetch` + `Blob` download pattern already used by the existing export

## Architecture

### New module `src/adp/calm/`

```
src/adp/calm/
  __init__.py
  models.py      — Pydantic models: CALMDocument, CALMNode, CALMRelationship, CALMControl
  exporter.py    — map_design_to_calm(design: ArchitectureDescription) -> CALMDocument
```

### Element Kind Mapping (FR-002 to FR-004)

| ADP ElementKind | CALM node-type |
|---|---|
| PERSON | actor |
| SYSTEM | system |
| CONTAINER | service |
| COMPONENT | service |

### Relationship Mapping (FR-006, FR-007)

All ADP relationships map to CALM `connects` relationship type.
Protocol inference from ADP `technology` label (case-insensitive substring match):
- "http" → HTTP, "https"/TLS → HTTPS, "amqp"/"rabbit" → AMQP, "kafka"/"event" → AMQP, "jdbc"/"sql"/"db" → JDBC, default → HTTPS

### New API endpoint

`GET /api/v1/designs/{design_id}/export/calm`

Returns `Content-Type: application/json` with `Content-Disposition: attachment; filename="{design_id}-calm.json"`.
Writes ART-IX audit entry `calm-export` to the design.

### Frontend addition

"Export CALM" button in `Workspace.tsx` toolbar alongside existing level selector.
On click: `fetch('/api/v1/designs/{designId}/export/calm')` → create Blob → `URL.createObjectURL` → programmatic `<a>` click → download.

## File Changes

| File | Action |
|---|---|
| `src/adp/calm/__init__.py` | CREATE |
| `src/adp/calm/models.py` | CREATE — Pydantic CALM document models |
| `src/adp/calm/exporter.py` | CREATE — mapping logic |
| `src/adp/api/routers/calm.py` | CREATE — FastAPI endpoint |
| `src/adp/api/app.py` | EDIT — register calm router |
| `web/src/canvas/Workspace.tsx` | EDIT — add Export CALM toolbar button |
| `tests/unit/test_calm_exporter.py` | CREATE — unit tests for mapping logic |
| `tests/contract/test_calm_export_api.py` | CREATE — contract tests for endpoint |

## Constitution Compliance

- **ART-IV**: unit tests cover all four element kind mappings and relationship protocol inference; contract tests cover 200 response shape, 404 for missing design, audit entry written
- **ART-IX**: audit entry written with `action: "calm-export"` on every successful export
- **ART-XI**: CALM metadata carries `source: "adp"` and `design-id` for provenance tracing
