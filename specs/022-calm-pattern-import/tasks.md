# Tasks: CALM Pattern Import (ADP-SPEC-022)

**Input**: Design documents from `/specs/022-calm-pattern-import/`
**Prerequisites**: ADP-SPEC-021 calm router exists at `src/adp/api/routers/calm.py` ✅

---

## Phase 1: Setup

- [X] T001 Register `adp-import-calm` script entry point in `pyproject.toml` under `[project.scripts]`: `adp-import-calm = "adp.calm.importer:cli"`

---

## Phase 2: US1 — CALM Importer Core

### Tests (MANDATORY — ART-IV)

- [X] T002 [P] [US1] Create `tests/unit/test_calm_importer.py`: write `test_parse_calm_document_extracts_name()` — pass a dict with `$id: "https://example.com/api-gateway-pattern"` and `nodes`/`relationships` arrays; call `parse_calm_document()`; assert returned item has `title` derived from the `$id` path segment
- [X] T003 [P] [US1] Write `test_parse_calm_document_generates_full_text_with_nodes()`: CALM dict with 2 nodes; assert `full_text` contains both node names and types
- [X] T004 [P] [US1] Write `test_parse_calm_document_generates_full_text_with_relationships()`: CALM dict with 1 relationship of type `connects`; assert `full_text` mentions source and destination node IDs
- [X] T005 [P] [US1] Write `test_parse_calm_document_sets_kind_reference_architecture()`: assert returned `KnowledgeItem` has `kind == KnowledgeType.REFERENCE_ARCHITECTURE`
- [X] T006 [P] [US1] Write `test_parse_calm_document_metadata_includes_counts()`: assert `metadata` has `calm_node_count` and `calm_relationship_count` with correct values
- [X] T007 [P] [US1] Write `test_parse_calm_document_invalid_json_raises()`: pass a non-dict value; assert `ValueError` is raised
- [X] T008 [P] [US1] Write `test_parse_calm_document_no_nodes_still_succeeds()`: CALM dict with no `nodes` key; assert `KnowledgeItem` is created with node count of 0 in metadata
- [X] T009 [P] [US1] Write `test_parse_calm_document_upsert_id_is_stable()`: same CALM dict called twice; assert both calls return same `item.id` (deterministic from name)

### Implementation

- [X] T010 [US1] Create `src/adp/calm/importer.py`: implement `_slugify(name: str) -> str` (lowercase, replace non-alphanumeric with `-`, truncate to 60 chars); implement `_extract_pattern_name(data: dict, fallback: str) -> str` (checks `$id`, `name`, `nodes[0].name`, then fallback); implement `_generate_full_text(name: str, data: dict) -> str` building the structured prose summary (truncate at 10,000 chars); implement `parse_calm_document(data: dict, source_ref: str = "") -> tuple[KnowledgeItem, str]` returning the item and generated full_text; raise `ValueError` if `data` is not a dict

- [X] T011 [US1] Add async `import_calm_data(data: dict, source_ref: str, db_url: str) -> CALMImportResult` to `src/adp/calm/importer.py`: call `parse_calm_document()`, generate embedding via `EmbeddingProvider`, create async DB session, call `KnowledgeIndex.upsert_item()`, commit, return `CALMImportResult`

- [X] T012 [US1] Add `import_calm_file(path: Path, db_url: str) -> CALMImportResult` to `src/adp/calm/importer.py`: read file, `json.loads()`, call `import_calm_data()` with `source_ref=str(path)`; on `json.JSONDecodeError` return result with `items_failed=1` and error message

- [X] T013 [US1] Add `import_calm_dir(directory: Path, db_url: str) -> CALMImportResult` to `src/adp/calm/importer.py`: glob `*.json`, call `import_calm_file()` for each, aggregate results

---

## Phase 3: US1 — CLI Entry Point

### Implementation

- [X] T014 [US1] Add `def cli()` Click command to `src/adp/calm/importer.py` decorated with `@click.command()`, `@click.argument("path")`, `@click.option("--dir", "is_dir", is_flag=True)`, `@click.option("--db-url", envvar="ADP_DATABASE_URL", default="postgresql+asyncpg://adp_user:adp_pass@127.0.0.1:5432/adp")`; runs `asyncio.run(import_calm_file())` or `asyncio.run(import_calm_dir())`; prints per-item results and final summary; exits non-zero on any failure

---

## Phase 4: US2 — Import API Endpoint

### Tests (MANDATORY — ART-IV)

- [X] T015 [P] [US2] Create `tests/contract/test_calm_import_api.py`: write `test_import_calm_pattern_returns_201()` — POST valid CALM JSON to `/api/v1/knowledge/import/calm`; assert 201; assert response body has `items_created == 1` and `items[0].kind == "reference_architecture"`
- [X] T016 [P] [US2] Write `test_import_calm_invalid_json_returns_422()`: POST `"not json"` with `Content-Type: application/json`; assert 422
- [X] T017 [P] [US2] Write `test_import_calm_upsert_returns_items_updated()`: POST same CALM JSON twice; assert second response has `items_updated == 1` and `items_created == 0`

### Implementation

- [X] T018 [US2] Add `POST /api/v1/knowledge/import/calm` to `src/adp/api/routers/calm.py`: accept `request: Request`, read raw body as JSON (422 if invalid), call `parse_calm_document()` + embedding + upsert using the knowledge router's session dependency; return 201 `CALMImportResult`

- [X] T019 [US2] Add `CALMImportResult` Pydantic model to `src/adp/calm/models.py`: `items_created: int`, `items_updated: int`, `items_failed: int`, `errors: list[str]`, `items: list[KnowledgeItemSummary]`

---

## Phase 5: US2 — Frontend Import Button

### Implementation

- [X] T020 [US2] Add `useImportCalmPattern()` hook to `web/src/api/knowledge.ts`: `useMutation` POST to `/api/v1/knowledge/import/calm` with raw JSON string body and `Content-Type: application/json`; on success invalidate `["knowledge-items"]` query

- [X] T021 [US2] Edit `web/src/knowledge/KnowledgePage.tsx`: add "Import CALM" button alongside "Add Item"; on click show an inline textarea labelled "Paste CALM JSON"; "Import" button calls `useImportCalmPattern()` with the textarea content; on success show `"{N} item(s) imported"` and close; on error show the error message; disable Import button when textarea is empty or mutation is pending

---

## Phase 6: Polish

- [X] T022 [P] Run `pytest tests/unit/test_calm_importer.py tests/contract/test_calm_import_api.py -q --no-cov` — all tests pass
- [X] T023 [P] Run `pytest tests/ --ignore=tests/integration -q --no-cov` — full suite clean
- [X] T024 [P] Run `ruff check src/adp/calm/importer.py` — clean
- [X] T025 [P] Run `cd web && npx tsc --noEmit` — zero TypeScript errors
- [X] T026 [P] Manual verification: run `adp-import-calm` against a CALM sample file from `scripts/` directory; confirm item appears in `GET /api/v1/knowledge`

---

## Notes

- `parse_calm_document()` is intentionally lenient — it never fails on missing CALM fields, only on non-dict input
- Item ID generation: `calm-{_slugify(name)}` — deterministic so upsert works correctly on re-import
- The CLI uses `asyncio.run()` which requires Python 3.7+; confirmed available in project's Python 3.12 environment
- `click` is already in the stack (used by `adp-generate`); no new dependency needed
