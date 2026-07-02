# Tasks: Document, View & Export Generation

**Input**: Design documents from `/specs/011-document-export/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: Tests are MANDATORY for all ADP features (ART-IV). Test tasks appear before their implementation counterparts in every user-story phase. Tests MUST fail before implementation begins.

**Note**: Pure Python, no Docker, no Java. Export tests use `tmp_path` pytest fixtures for filesystem writes. `pyyaml>=6.0` is the only new dependency. All new modules follow the `adp.docs` / `adp.export` package pattern from the plan.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no file conflicts)
- **[Story]**: Which user story this task belongs to (US1–US5)
- Include exact file paths in every description

---

## Phase 1: Setup

**Purpose**: Add pyyaml dependency, create package skeletons

- [X] T001 Add `pyyaml>=6.0` to `pyproject.toml` dependencies section; install with `pip install pyyaml --break-system-packages`; verify `python3 -c "import yaml; print(yaml.__version__)"` succeeds
- [X] T002 [P] Create `src/adp/docs/__init__.py` as empty package marker
- [X] T003 [P] Create `src/adp/export/__init__.py` as empty package marker

**Checkpoint**: `python3 -c "import yaml, adp.docs, adp.export; print('ok')"` succeeds

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: All Pydantic v2 models in one file that every user story depends on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 Create `src/adp/docs/models.py` with document-layer models only (all `extra="forbid"`):
  - `C4Level = Literal["context", "container", "component"]` — shared type alias
  - `DocumentMetadata(design_id: str, schema_version: str, generated_at: str, generator: Literal["ADP-SPEC-011"], level: C4Level | None = None)` — typed frontmatter for generated Markdown
  - `GeneratedDocument(design_id: str, markdown: str, metadata: DocumentMetadata)` — return value from DocumentGenerator
  - `TraceabilityEntry(element_id: str, element_name: str, element_kind: str, satisfied_requirements: list[str], provenance: str | None, verdict_ids: list[str], is_orphan: bool)` — one matrix row; `verdict_ids` is always `[]` in v1 (lookup deferred to v2 — see T018 note)
  - `TraceabilityMatrix(design_id: str, schema_version: str, generated_at: str, total_elements: int, orphan_count: int, entries: list[TraceabilityEntry])` — full machine-readable matrix
  - `ViewBundle(design_id: str, context: RenderResult, container: RenderResult, component: RenderResult)` — all three C4 levels from ADP-SPEC-010 renderer; import `RenderResult` from `adp.theme.models`

- [X] T004b [P] Create `src/adp/export/models.py` with export/import API boundary models (all `extra="forbid"`); these are kept separate from `adp.docs.models` to avoid circular imports:
  - `ExportRequest(confirmation_id: str, export_root: str)` — ART-VIII enforcement: `confirmation_id` must be a non-empty string (add `@field_validator("confirmation_id")` that raises `ValueError("Export requires a non-empty confirmation_id — this is a consequential action per ART-VIII")` if blank); in tests supply `confirmation_id="CONF-TEST"` as a sentinel; in production, obtain the confirmation_id from the prior confirmation step
  - `ExportResult(design_id: str, model_version: int, export_path: str, artifacts: list[str], audit_entry_id: str)` — successful export response
  - `ImportRequest(model_json: str)` — raw JSON string of canonical model to import
  - `ImportResult(design_id: str, schema_version: str, element_count: int, relationship_count: int, validation_warnings: list[str])` — successful import response

**Checkpoint**: `python3 -c "from adp.docs.models import GeneratedDocument, TraceabilityMatrix, ViewBundle; from adp.export.models import ExportRequest, ExportResult, ImportResult; print('ok')"` succeeds

---

## Phase 3: User Story 1 — Generate a Stakeholder Document (Priority: P1) 🎯 MVP

**Goal**: Given a design, produce a Markdown document with YAML frontmatter containing design metadata; all content derived from the canonical model; byte-identical output for the same model version.

**Independent Test**: Provide a design with 2 elements and 1 requirement; call `DocumentGenerator.generate(design)`; assert the returned Markdown contains both element names and the requirement summary; assert the frontmatter contains `design_id` and `schema_version`.

### Tests for User Story 1 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T005 [P] [US1] Write failing `test_generate_document_contains_element_names()` in `tests/unit/test_document_generator.py`: construct an `ArchitectureDescription` with elements "API Gateway" (container) and "User" (person) plus one requirement; call `DocumentGenerator().generate(design)`; assert "API Gateway" and "User" appear in `result.markdown`; assert result.markdown starts with `---` (YAML frontmatter delimiter)
- [X] T006 [P] [US1] Write failing `test_generate_document_frontmatter_has_typed_metadata()` in `tests/unit/test_document_generator.py`: call `DocumentGenerator().generate(design)` on any valid design; parse the frontmatter from the first `---...---` block using `python-frontmatter`; assert `design_id`, `schema_version`, `generated_at`, `generator` keys all present; assert `generator == "ADP-SPEC-011"`
- [X] T007 [P] [US1] Write failing `test_document_generation_is_deterministic()` in `tests/unit/test_document_generator.py`: call `DocumentGenerator().generate(design)` twice with the same design; assert both `result.markdown` strings are identical (byte-identical output enforces ART-XIV / SC-006)
- [X] T008 [P] [US1] Write failing `test_document_api_returns_200_with_frontmatter()` in `tests/contract/test_document_api.py`: POST a test design to the mock store; call `GET /api/v1/designs/D-001/document` via TestClient; assert 200; assert response body starts with `---`; assert response Content-Type contains `text/plain` or `text/markdown`

### Implementation for User Story 1

- [X] T009 [US1] Create `src/adp/docs/generator.py` with `DocumentGenerator` class: `generate(design: ArchitectureDescription) -> GeneratedDocument`; builds YAML frontmatter block using `yaml.dump(metadata_dict, default_flow_style=False, sort_keys=True)`; then builds the Markdown body with sections: `# {design.title}`, elements section (each element name + kind + description + `satisfies` requirement IDs), requirements section (table: ID | Title | Satisfied By), traceability summary (count of orphans); raises `ValueError` with clear message if `design.title` is empty; verify T005–T007 pass
- [X] T010 [US1] Create `src/adp/api/routers/documents.py` with `GET /api/v1/designs/{design_id}/document` returning `PlainTextResponse(generated_doc.markdown, media_type="text/markdown; charset=utf-8")`; handles 404 for missing design; emits structured log (ART-VI) with `design_id` and `correlation_id`; register router in `src/adp/api/app.py`; verify T008 passes

**Checkpoint**: `pytest tests/unit/test_document_generator.py tests/contract/test_document_api.py::test_document_api_returns_200_with_frontmatter -v --no-cov` green; stakeholder document generated from any valid design

---

## Phase 4: User Story 2 — Project Per-Persona C4 Views (Priority: P1)

**Goal**: A single `GET /views` call returns all three C4 level renders from the same design; each level uses the locked theme; both context and container views use identical styling for shared element types.

**Independent Test**: Mock `RenderOrchestrator` to return distinct `RenderResult` objects per level; call `GET /api/v1/designs/D-001/views`; assert response JSON has `context`, `container`, `component` top-level keys; assert each has `dsl`, `svg`, `png_base64` fields.

### Tests for User Story 2 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T011 [P] [US2] Write failing `test_views_returns_all_three_levels()` in `tests/contract/test_document_api.py`: call `GET /api/v1/designs/D-001/views` via TestClient with mocked `RenderOrchestrator`; assert 200; assert response JSON has keys `design_id`, `context`, `container`, `component`; assert each level dict has `dsl`, `svg`, `png_base64` fields
- [X] T012 [P] [US2] Write failing `test_views_calls_renderer_once_per_level()` in `tests/contract/test_document_api.py`: mock `RenderOrchestrator.render` as a spy; call `GET /api/v1/designs/D-001/views`; assert `render` was called exactly 3 times (once per C4 level); assert the calls used levels `"context"`, `"container"`, `"component"`

### Implementation for User Story 2

- [X] T013 [US2] Add `GET /api/v1/designs/{design_id}/views` to `src/adp/api/routers/documents.py`: calls `RenderOrchestrator(mock_store).render(design_id, level)` for all three C4 levels; assembles and returns `ViewBundle` as JSON; handles 404; verify T011–T012 pass

**Checkpoint**: `pytest tests/contract/test_document_api.py -v --no-cov` green; single `GET /views` call returns all 3 C4 level renders

---

## Phase 5: User Story 3 — Generate Requirements Traceability Matrix (Priority: P2)

**Goal**: Generate a machine-readable `TraceabilityMatrix` where every element appears exactly once (with its requirements, provenance, and verdict IDs); orphan elements (no satisfied requirements) are flagged with `is_orphan: true`; output is deterministic.

**Independent Test**: Provide a design with ELM-001 satisfying REQ-001 (provenance OPT-001) and ELM-002 with no satisfied requirements; call `TraceabilityGenerator().generate(design)`; assert the matrix has 2 entries; assert ELM-001 has `is_orphan: false` and `satisfied_requirements: ["REQ-001"]`; assert ELM-002 has `is_orphan: true`; assert `orphan_count == 1`.

### Tests for User Story 3 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T014 [P] [US3] Write failing `test_matrix_contains_all_elements()` in `tests/unit/test_traceability.py`: construct a design with 3 elements; call `TraceabilityGenerator().generate(design)`; assert `result.total_elements == 3`; assert `len(result.entries) == 3`; assert all element IDs appear in entries
- [X] T015 [P] [US3] Write failing `test_orphan_elements_flagged()` in `tests/unit/test_traceability.py`: construct a design where ELM-001 satisfies REQ-001 and ELM-002 has `satisfies=[]`; assert `result.orphan_count == 1`; assert the entry for ELM-002 has `is_orphan: true`; assert the entry for ELM-001 has `is_orphan: false`
- [X] T016 [P] [US3] Write failing `test_matrix_is_deterministic()` in `tests/unit/test_traceability.py`: call `TraceabilityGenerator().generate(design)` twice; assert `result1.entries` equals `result2.entries` (entries sorted by `element_id` for stable ordering)
- [X] T017 [P] [US3] Write failing `test_traceability_api_returns_200_with_orphan_count()` in `tests/contract/test_document_api.py`: call `GET /api/v1/designs/D-001/traceability` with a mock design that has one orphan element; assert 200; assert response JSON has `orphan_count` field; assert `total_elements` matches design element count

### Implementation for User Story 3

- [X] T018 [US3] Create `src/adp/docs/traceability.py` with `TraceabilityGenerator` class: `generate(design: ArchitectureDescription) -> TraceabilityMatrix`; iterates `design.elements` sorted by `element.id`; for each element, creates `TraceabilityEntry` with `element.satisfies` (list of requirement IDs), `element.provenance` (recommendation/option ID or `None`), and `verdict_ids=[]`; sets `is_orphan = len(element.satisfies or []) == 0`; computes `generated_at` with `datetime.utcnow().isoformat() + "Z"`; verify T014–T016 pass

  **v1 scope note (I1 remediation)**: `verdict_ids` is always `[]` in v1. Spec US3 acceptance scenario 3 mentions "each element lists its provenance (recommendation ID and accepted option ID)" — this is fully covered by `element.provenance`. The verdict-linking part of scenario 3 ("validation verdicts that evaluated it") requires cross-referencing the `audit_log` and verdict store, which is deferred to v2. Add a code comment in `traceability.py`: `# v2: populate verdict_ids from audit_log entries with action="validate" that reference this design version`
- [X] T019 [US3] Add `GET /api/v1/designs/{design_id}/traceability` to `src/adp/api/routers/documents.py`; returns `TraceabilityMatrix` as JSON; verify T017 passes

**Checkpoint**: `pytest tests/unit/test_traceability.py tests/contract/test_document_api.py -v --no-cov` green; traceability matrix generated with all orphans flagged

---

## Phase 6: User Story 4 — Export to Version Control (Priority: P2)

**Goal**: Given an attributable human confirmation (`confirmation_id` — a non-empty string obtained from the confirmation flow, per ART-VIII), write an atomic export bundle (model.json + model.yaml + traceability.json + README.md + DSL/SVG/PNG per C4 level) to the configured VCS directory; write an audit entry; abort with zero files written if any artifact fails validation.

**Independent Test**: Call `ExportOrchestrator.export(...)` with `confirmation_id="CONF-TEST"` and a `tmp_path` as `export_root`; assert the export directory exists and contains all 13 expected files; assert an audit entry is returned.

### Tests for User Story 4 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T020 [P] [US4] Write failing `test_export_without_confirmation_returns_400()` in `tests/contract/test_export_api.py`: POST `{"confirmation_id": "", "export_root": "/tmp/test"}` (empty string) to `POST /api/v1/designs/D-001/export`; assert 422 (Pydantic field_validator rejects blank ID) and response body mentions "consequential action" or "confirmation_id"; also test missing `confirmation_id` field entirely → 422
- [X] T021 [P] [US4] Write failing `test_export_writes_all_artifacts()` in `tests/integration/test_export_bundle.py`: create a mock design; call `ExportOrchestrator(mock_store, mock_render_orchestrator).export(design_id="D-001", export_root=str(tmp_path), confirmation_id="CONF-TEST", actor="test-actor")`; assert export path `tmp_path/exports/D-001/v1/` exists; assert files `model.json`, `model.yaml`, `traceability.json`, `README.md`, `context/diagram.dsl`, `context/diagram.svg`, `context/diagram.png`, `container/diagram.dsl`, `container/diagram.svg`, `container/diagram.png`, `component/diagram.dsl`, `component/diagram.svg`, `component/diagram.png` all exist under the export path (13 artifacts total)
- [X] T022 [P] [US4] Write failing `test_export_is_atomic_on_failure()` in `tests/integration/test_export_bundle.py`: mock one of the renderers to raise; call export; assert the export directory does NOT exist (no partial export created at the final path)
- [X] T023 [P] [US4] Write failing `test_export_rejects_if_directory_exists()` in `tests/integration/test_export_bundle.py`: create the export directory manually; attempt export; assert a `FileExistsError` or clear error is returned and no files are overwritten
- [X] T024 [P] [US4] Write failing `test_export_api_returns_audit_entry_id()` in `tests/contract/test_export_api.py`: POST valid export request with `confirmed: true`; assert 200; assert response JSON has `audit_entry_id` field (non-empty string matching `AUD-\d+` or similar)

### Implementation for User Story 4

- [X] T025 [US4] Create `src/adp/export/bundle.py` with `ExportOrchestrator` class: `export(self, design_id: str, export_root: str, confirmation_id: str, *, actor: str) -> ExportResult`; **emit structured log at entry** (C1 / ART-VI / QG-10): `logger.info({"event": "export.start", "design_id": design_id, "export_root": export_root, "confirmation_id": confirmation_id, "actor": actor})`; raises `ValueError(...)` if `confirmation_id.strip() == ""`; fetches design from store; builds export path `{export_root}/exports/{design_id}/v{model_version}/`; **pre-check FileExistsError BEFORE writing to tmpdir** (atomicity: if path exists → raise immediately, no tmpdir created); writes all artifacts to `tempfile.mkdtemp()` first; validates `model.json` against `ArchitectureDescription` schema; on any failure calls `shutil.rmtree(tmpdir, ignore_errors=True)` in `finally` block and re-raises; on success calls `shutil.copytree(tmpdir, final_path)` then removes tmpdir; writes audit entry via `adp.audit.writer.write_audit_record()` with `action="export"`; **emit structured log at completion**: `logger.info({"event": "export.complete", "design_id": design_id, "export_path": str(final_path), "artifact_count": 13})`; returns `ExportResult` with `audit_entry_id`; verify T021–T023 pass

  **Export artifact details**:
  - `model.json`: `json.dumps(design.model_dump(mode="json"), sort_keys=True, indent=2)` 
  - `model.yaml`: `yaml.dump(design.model_dump(mode="json"), default_flow_style=False, sort_keys=True, allow_unicode=True)`
  - `traceability.json`: `TraceabilityGenerator().generate(design).model_dump_json(indent=2)`
  - `README.md`: `DocumentGenerator().generate(design).markdown`
  - `context/diagram.dsl`, `.svg`, `.png`: from `RenderOrchestrator.render(design_id, "context")`
  - `container/`: from `RenderOrchestrator.render(design_id, "container")`
  - `component/`: from `RenderOrchestrator.render(design_id, "component")`

  **Export artifact details**:
  - `model.json`: `json.dumps(design.model_dump(mode="json"), sort_keys=True, indent=2)` 
  - `model.yaml`: `yaml.dump(design.model_dump(mode="json"), default_flow_style=False, sort_keys=True, allow_unicode=True)`
  - `traceability.json`: `TraceabilityGenerator().generate(design).model_dump_json(indent=2)`
  - `README.md`: `DocumentGenerator().generate(design).markdown`
  - `context/diagram.dsl`, `.svg`, `.png`: from `RenderOrchestrator.render(design_id, "context")`
  - `container/`: from `RenderOrchestrator.render(design_id, "container")`
  - `component/`: from `RenderOrchestrator.render(design_id, "component")`

- [X] T026 [US4] Create `src/adp/api/routers/export_router.py` with `POST /api/v1/designs/{design_id}/export` that accepts `ExportRequest` from `adp.export.models`; `ExportRequest.confirmation_id` is already validated non-empty by its Pydantic field_validator (empty → 422 before handler runs); checks role is `architect` or `enterprise_architect` (403 if not); emits structured log (ART-VI) with `design_id`, `export_root`, `correlation_id` from `X-Correlation-ID` header; calls `ExportOrchestrator.export(design_id, request.export_root, request.confirmation_id, actor=...)` — note: logging also happens inside the orchestrator (C1 fix); handles `FileExistsError → 409`, `ValueError → 400`, design-not-found → 404, schema validation failure → 422; returns `ExportResult`; register router in `src/adp/api/app.py`; verify T020 and T024 pass

**Checkpoint**: `pytest tests/integration/test_export_bundle.py tests/contract/test_export_api.py -v --no-cov` green; export bundle with all 13 artifacts written atomically; audit entry recorded

---

## Phase 7: User Story 5 — Round-Trip Import and Validation (Priority: P3)

**Goal**: Re-import an exported `model.json`; validate against current schema version; reconstruct an equivalent `ArchitectureDescription`; reject models with wrong schema version or invalid JSON.

**Independent Test**: Serialize a design to JSON via `model.model_dump_json()`; pass to `DesignImporter().import_from_json(json_str)`; assert returned design has same `id`, same element count, same relationship count as original.

### Tests for User Story 5 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T027 [P] [US5] Write failing `test_import_valid_model_json_succeeds()` in `tests/unit/test_importer.py`: create a valid `ArchitectureDescription` fixture; serialize to JSON with `design.model_dump_json()`; call `DesignImporter().import_from_json(json_str)`; assert returned design has same `id`, `len(elements)`, `len(relationships)` as original
- [X] T028 [P] [US5] Write failing `test_import_wrong_schema_version_rejected()` in `tests/unit/test_importer.py`: create a model dict with `schema_version: "99.0.0"`; call `import_from_json(json.dumps(data))`; assert `ValueError` or `pydantic.ValidationError` is raised with message mentioning schema version
- [X] T029 [P] [US5] Write failing `test_import_malformed_json_rejected()` in `tests/unit/test_importer.py`: call `import_from_json("not json")`; assert `ValueError` raised with clear message
- [X] T030 [P] [US5] Write failing `test_import_api_returns_element_count()` in `tests/contract/test_export_api.py`: create a valid design JSON; POST `{"model_json": json_str}` to `POST /api/v1/designs/import`; assert 200; assert response has `element_count` matching the design's element count and `validation_warnings: []`

### Implementation for User Story 5

- [X] T031 [US5] Create `src/adp/export/importer.py` with `DesignImporter` class: `import_from_json(json_str: str) -> ArchitectureDescription`; raises `ValueError("Invalid JSON: ...")` on JSON parse error; raises `ValueError(f"Schema version {found!r} is not supported; current: {SCHEMA_VERSION!r}")` if the parsed `schema_version` field doesn't match `adp.models.SCHEMA_VERSION`; calls `ArchitectureDescription.model_validate(data)` (Pydantic raises `ValidationError` on invalid fields); calls `adp.validate.validate_references(design)` for referential integrity; returns the validated design; verify T027–T029 pass
- [X] T032 [US5] Add `POST /api/v1/designs/import` to `src/adp/api/routers/export_router.py`; accepts `ImportRequest`; calls `DesignImporter().import_from_json(request.model_json)`; handles `ValueError → 422` with detail message; handles `pydantic.ValidationError → 422`; returns `ImportResult` with element and relationship counts; verify T030 passes

**Checkpoint**: `pytest tests/unit/test_importer.py tests/contract/test_export_api.py::test_import_api_returns_element_count -v --no-cov` green; round-trip JSON → import → model validated

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Full test suite, lint, schema drift check, coverage

- [X] T033 Run `pytest tests/ --ignore=tests/integration -q --no-cov` — assert all 286+ Python tests pass; fix any regressions
- [X] T034 [P] Run `ruff check src/adp/docs/ src/adp/export/ src/adp/api/routers/documents.py src/adp/api/routers/export_router.py` — fix all lint errors
- [X] T035 [P] Run `adp-generate --check` — confirm both schemas are drift-free (no changes expected from this feature)
- [X] T036 [P] Run `pytest tests/integration/ -v --no-cov` — confirm integration tests pass (export bundle creates all 13 files; atomicity test passes)
- [X] T037 [P] Run `pytest tests/ --ignore=tests/integration --cov=adp --cov-report=term-missing -q` — assert coverage ≥ 85% for `adp.docs` and `adp.export` modules; add targeted tests for uncovered branches (empty design, YAML dump edge cases, export path collision, import of design with referential integrity errors)
- [X] T038 [P] Write `tests/unit/test_docs_performance.py` to satisfy SC-001 and SC-004: (a) `test_sc001_document_generation_under_60s()` — construct a design with 50 elements and 10 requirements; call `DocumentGenerator().generate(design)` using `time.perf_counter()`; assert elapsed ≤ 60.0 seconds; (b) `test_sc004_export_bundle_under_120s()` — construct the same 50-element design; call `ExportOrchestrator(mock_store, mock_render_orchestrator).export(...)` with a `tmp_path`; assert elapsed ≤ 120.0 seconds; run with `pytest tests/unit/test_docs_performance.py -v --no-cov` to ensure timing gates are tracked in CI

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories; Pydantic models must exist before any service or endpoint can be written
- **US1 (Phase 3)**: Depends on Foundational — 🎯 MVP; `DocumentGenerator` + `GET /document` demonstrates core model-as-source-of-truth pipeline
- **US2 (Phase 4)**: Depends on Foundational only; uses existing ADP-SPEC-010 renderer — independently testable from US1
- **US3 (Phase 5)**: Depends on Foundational; `TraceabilityGenerator` is independently testable from US1/US2; shares `GET /traceability` endpoint with the `documents.py` router created in US1
- **US4 (Phase 6)**: Depends on US1 (needs `DocumentGenerator`) and US3 (needs `TraceabilityMatrix`); US2's renderer is also called during export
- **US5 (Phase 7)**: Depends on Foundational only — independently testable; shares router with US4
- **Polish (Phase 8)**: Depends on all user stories complete

### User Story Dependencies

- **US1 (P1)**: Can start after Foundational — core generator + document endpoint
- **US2 (P1)**: Can start after Foundational — thin renderer wrapper; `documents.py` router created in US1 is extended
- **US3 (P2)**: Can start after Foundational — traceability is independently testable; extends `documents.py` router
- **US4 (P2)**: Depends on US1 (DocumentGenerator) and US3 (TraceabilityGenerator)
- **US5 (P3)**: Can start after Foundational; shares `export_router.py` with US4

### Parallel Opportunities

- T002, T003 (Setup): parallel — different package files
- T005, T006, T007, T008 (US1 tests): parallel — independent test functions
- T011, T012 (US2 tests): parallel — independent test functions
- T014, T015, T016, T017 (US3 tests): parallel — independent test functions/files
- T020, T021, T022, T023, T024 (US4 tests): parallel — independent test functions
- T027, T028, T029, T030 (US5 tests): parallel — independent test functions
- T033, T034, T035, T036, T037, T038 (Polish): parallel — independent tooling

---

## Implementation Strategy

### MVP First (US1 only)

1. Phase 1 + 2 → `pyyaml` installed, `adp.docs` + `adp.export` packages, all models
2. Phase 3 (US1) → stakeholder document generator + `GET /document`
3. **STOP and VALIDATE**: `GET /api/v1/designs/DESIGN-001/document` returns Markdown with frontmatter

### Incremental Delivery

1. Setup + Foundational → Infrastructure ready
2. US1 → Document generation (MVP)
3. US2 → Per-persona views (thin wrapper)
4. US3 → Traceability matrix
5. US4 → Export bundle (requires US1 + US3)
6. US5 → Round-trip import
7. Polish → Coverage + lint + integration test

---

## Notes

- [P] tasks = different files, no file conflicts
- Tests MUST fail before implementation; commit failing tests first (ART-IV)
- `ExportRequest.confirmation_id` (non-empty string) is the ART-VIII enforcement; T020 verifies empty `confirmation_id → 422`; this is more attributable than a boolean (the ID is logged and auditable)
- `ExportOrchestrator.export()` emits structured logs at both start and completion (C1 fix, QG-10); logging happens in the library function, not only in the HTTP router
- `verdict_ids=[]` in v1 TraceabilityEntry — verdict linking is deferred to v2 (I1 fix; see T018 code comment)
- Export atomicity: temp dir → validate → `shutil.copytree` to final path (T022 verifies partial failure leaves no files)
- All generated documents use `datetime.utcnow().isoformat() + "Z"` for timestamps — no local timezone
- `adp-generate --check` must remain exit 0 — no new generated schemas in this feature
- SC-006 (byte-identical output): T007 and T016 are the determinism regression guards
