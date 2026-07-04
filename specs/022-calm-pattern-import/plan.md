# Implementation Plan: CALM Pattern Import (ADP-SPEC-022)

## Tech Stack

- **Backend**: Python 3.12; new module `src/adp/calm/importer.py`; new CLI entry point `adp-import-calm`; new FastAPI endpoint in `src/adp/api/routers/calm.py` (shared with ADP-SPEC-021)
- **Embedding**: `adp.knowledge.embedder.EmbeddingProvider` (all-MiniLM-L6-v2, dim=384) — already in stack
- **DB**: `adp.knowledge.index.KnowledgeIndex.upsert_item()` — already in stack
- **No new packages**: uses existing `asyncio`, `json`, `pathlib`, `click` (already in stack for other CLI tools)
- **Frontend**: TypeScript/React; "Import CALM Pattern" button and textarea modal added to `web/src/knowledge/KnowledgePage.tsx`

## Architecture

### New module additions to `src/adp/calm/`

```
src/adp/calm/
  importer.py    — parse_calm_document(data: dict) -> list[KnowledgeItem + embedding]
                   import_calm_file(path: Path, db_url: str) -> CALMImportResult
                   import_calm_dir(dir: Path, db_url: str) -> CALMImportResult
```

### Parsing Strategy (FR-002)

The importer uses best-effort extraction from any JSON with a `nodes` array:

1. **Pattern name**: `$id` field → top-level `name` → filename stem → `"Imported CALM Pattern"`
2. **full_text**: generated prose summary:
   ```
   Pattern: {name}
   
   Nodes ({N}):
   - [{node-type}] {name}: {description}
   ...
   
   Relationships ({M}):
   - {unique-id}: {source} → {destination} [{protocol}]
   ...
   
   Controls: {K} control requirements
   ```
3. **Item ID**: `calm-{slugified-name}` or `calm-{uuid}` if name is absent
4. **metadata**: `{"calm_node_count": N, "calm_relationship_count": M, "calm_source": "import", "calm_schema_id": "$id value"}`

### CLI entry point

```
adp-import-calm [--dir] <path> [--db-url URL]
```

Registered in `pyproject.toml` under `[project.scripts]`.

### New API endpoint

`POST /api/v1/knowledge/import/calm` — accepts raw CALM JSON body, returns `CALMImportResult`.

### Frontend addition

"Import CALM Pattern" button on Knowledge page opens an inline textarea.
On submit: POST to `/api/v1/knowledge/import/calm` with the pasted JSON body.
On success: invalidate `["knowledge-items"]` TanStack Query; show item count added.

## File Changes

| File | Action |
|---|---|
| `src/adp/calm/importer.py` | CREATE — parsing and import logic |
| `src/adp/calm/__init__.py` | EDIT — export importer |
| `src/adp/api/routers/calm.py` | EDIT — add import endpoint (shares router with 021) |
| `pyproject.toml` | EDIT — register `adp-import-calm` script entry point |
| `web/src/knowledge/KnowledgePage.tsx` | EDIT — add Import CALM Pattern button + textarea |
| `web/src/api/knowledge.ts` | EDIT — add `useImportCalmPattern()` mutation hook |
| `tests/unit/test_calm_importer.py` | CREATE — unit tests for parsing logic |
| `tests/contract/test_calm_import_api.py` | CREATE — contract tests for endpoint |

## Constitution Compliance

- **ART-IV**: unit tests cover valid CALM import, multi-node summary generation, invalid JSON handling, duplicate upsert
- **ART-VII**: embeddings always generated from the full_text summary so KB items are semantically retrievable
- **ART-VIII**: import is always user-initiated; no background auto-import
