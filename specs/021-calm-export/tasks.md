# Tasks: CALM Export (ADP-SPEC-021)

**Input**: Design documents from `/specs/021-calm-export/`
**Prerequisites**: All complete ✅

---

## Phase 1: Setup

- [X] T001 Create `src/adp/calm/__init__.py` (empty module marker)
- [X] T002 Register `src/adp/api/routers/calm.py` router in `src/adp/api/app.py` (import + `app.include_router(calm.router)`)

---

## Phase 2: US1 — CALM Exporter Core

### Tests (MANDATORY — ART-IV)

- [X] T003 [P] [US1] Create `tests/unit/test_calm_exporter.py`: write `test_person_element_maps_to_actor()` — create an `ArchitectureDescription` with one `ElementKind.PERSON` element; call `map_design_to_calm()`; assert the CALM document has one node with `node-type == "actor"`
- [X] T004 [P] [US1] Write `test_system_element_maps_to_system()` in `tests/unit/test_calm_exporter.py`: assert `ElementKind.SYSTEM` → `node-type: "system"`
- [X] T005 [P] [US1] Write `test_container_element_maps_to_service()` and `test_component_element_maps_to_service()`: assert both map to `node-type: "service"`
- [X] T006 [P] [US1] Write `test_relationship_maps_to_connects()`: create design with two elements and one relationship; assert CALM output has one relationship with `relationship-type: "connects"` and correct `source-node`/`destination-node` IDs
- [X] T007 [P] [US1] Write `test_requirement_maps_to_control()`: design with one requirement; assert CALM output has `controls` array with one entry whose `control-requirement-url` is `urn:adp:requirement:{req_id}` and `description` matches the requirement statement
- [X] T008 [P] [US1] Write `test_metadata_carries_provenance()`: assert exported CALM document has `metadata` entry with `source: "adp"` and correct `design-id`
- [X] T009 [P] [US1] Write `test_empty_design_produces_valid_calm()`: design with no elements or relationships; assert output has `nodes: []` and `relationships: []` — still valid CALM structure
- [X] T010 [P] [US1] Write `test_protocol_inference()` in `tests/unit/test_calm_exporter.py`: parametrize over technology strings ("kafka", "https", "jdbc", "unknown"); assert correct CALM protocol enum value returned

### Implementation

- [X] T011 [US1] Create `src/adp/calm/models.py`: define Pydantic v2 models `CALMNode(unique_id, node_type, name, description, metadata=None)`, `CALMConnects(source_node, destination_node, protocol=None)`, `CALMRelationship(unique_id, relationship_type="connects", connects)`, `CALMControl(control_requirement_url, description)`, `CALMMetadataEntry(key, value)`, `CALMDocument(nodes, relationships, controls=None, metadata=None)` — all matching CALM draft 2025-03 field names (kebab-case serialized via `model_config = ConfigDict(populate_by_name=True)`)
- [X] T012 [US1] Create `src/adp/calm/exporter.py`: implement `_infer_protocol(technology: str | None) -> str` mapping tech labels to CALM protocol enum values; implement `map_design_to_calm(design: ArchitectureDescription) -> CALMDocument` following the element kind mapping table, creating one `CALMNode` per element, one `CALMRelationship` per relationship, one `CALMControl` per requirement, and a provenance `CALMMetadataEntry`

---

## Phase 3: US1 — Export API Endpoint

### Tests (MANDATORY — ART-IV)

- [X] T013 [P] [US1] Create `tests/contract/test_calm_export_api.py`: write `test_export_calm_returns_200_with_valid_structure()` — seed a design with elements; GET `/api/v1/designs/{id}/export/calm`; assert 200; assert response JSON has `nodes` and `relationships` arrays; assert at least one node has `unique-id` and `node-type`
- [X] T014 [P] [US1] Write `test_export_calm_not_found_returns_404()`: GET with non-existent design ID; assert 404
- [X] T015 [P] [US1] Write `test_export_calm_content_disposition_header()`: assert response has `Content-Disposition` header containing `filename=` and `.json`

### Implementation

- [X] T016 [US1] Create `src/adp/api/routers/calm.py`: define `router = APIRouter(prefix="/api/v1/designs", tags=["calm"])`; implement `GET /{design_id}/export/calm` endpoint — fetch design from store (404 if missing), call `map_design_to_calm()`, serialize to JSON, write audit entry `action="calm-export"`, return `Response` with `media_type="application/json"` and `Content-Disposition: attachment; filename="{design_id}-calm.json"`

**Checkpoint**: `GET /api/v1/designs/DESIGN-001/export/calm` returns downloadable CALM JSON

---

## Phase 4: US2 — Canvas Toolbar Button

### Implementation

- [X] T017 [US2] Edit `web/src/canvas/Workspace.tsx`: add "Export CALM" button to the toolbar alongside the level selector; on click: `fetch('/api/v1/designs/${designId}/export/calm')` → convert to Blob → `URL.createObjectURL` → create and click a temporary `<a download="{designId}-calm.json">` element → revoke object URL; show brief "Exporting..." disabled state during fetch; display error toast on failure

---

## Phase 5: Polish

- [X] T018 [P] Run `pytest tests/unit/test_calm_exporter.py tests/contract/test_calm_export_api.py -q --no-cov` — all tests pass
- [X] T019 [P] Run `pytest tests/ --ignore=tests/integration -q --no-cov` — full suite clean
- [X] T020 [P] Run `ruff check src/adp/calm/ src/adp/api/routers/calm.py` — clean
- [X] T021 [P] Run `cd web && npx tsc --noEmit` — zero TypeScript errors

---

## Notes

- CALM field names use kebab-case in JSON (`unique-id`, `node-type`, `source-node`) — use `model_config = ConfigDict(alias_generator=...)` or explicit `Field(alias=...)` in Pydantic to serialize correctly
- ADP element IDs (e.g. `EL-001`) are already valid CALM `unique-id` values
- The CALM `connects` relationship uses a nested `connects` object — `{"unique-id": "...", "relationship-type": "connects", "connects": {"source-node": "...", "destination-node": "..."}}`
