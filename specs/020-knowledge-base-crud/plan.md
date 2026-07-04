# Implementation Plan: Knowledge Base Management (ADP-SPEC-020)

## Tech Stack

- **Backend**: Python 3.12 + FastAPI; new router `src/adp/api/routers/knowledge.py`
- **Embedding**: `adp.knowledge.embedder.EmbeddingProvider` (already in stack, all-MiniLM-L6-v2, dim=384)
- **DB**: `adp.knowledge.index.KnowledgeIndex` + `knowledge_items` table (vector(384), already migrated)
- **Store dependency**: reuses `_get_design_store_dep` pattern from recommend router to inject the session factory
- **Frontend**: TypeScript + React; new `web/src/knowledge/` directory; TanStack Query v5 hooks; inline form (no modal library)
- **Navigation**: extend `AppView` type in `web/src/App.tsx` to include `"knowledge"`; add 4th nav tab

## Architecture

### Backend — new router `src/adp/api/routers/knowledge.py`

```
GET    /api/v1/knowledge              → list all active items (summary, no full_text)
GET    /api/v1/knowledge/{item_id}    → get single item (full details incl. full_text)
POST   /api/v1/knowledge              → create item; generate embedding; upsert
PUT    /api/v1/knowledge/{item_id}    → update item; re-generate embedding; upsert
DELETE /api/v1/knowledge/{item_id}    → soft-delete (active=false)
```

Embedding generated inline on POST/PUT via `EmbeddingProvider("all-MiniLM-L6-v2")`.
Embedder is module-level singleton (lazy-loaded on first request).
All writes go through `KnowledgeIndex.upsert_item()` / `mark_inactive()`.
Session factory injected via `Depends(_get_kb_session_dep)` — same pattern as recommend router.

### Frontend — `web/src/knowledge/`

```
KnowledgePage.tsx        — main page: list + kind filter + count + "Add Item" button
KnowledgeItemRow.tsx     — single row: kind badge, title, source_ref, Edit/Delete buttons
KnowledgeItemForm.tsx    — create/edit form (inline, not modal): id, kind, title, full_text, source_ref, metadata
DeleteConfirmDialog.tsx  — simple confirmation modal
web/src/api/knowledge.ts — TanStack Query hooks: useKnowledgeItems, useCreateItem, useUpdateItem, useDeleteItem
```

`App.tsx`: extend `AppView` to `"canvas" | "intake" | "recommend" | "knowledge"` and add Knowledge nav tab.

## File Changes

| File | Action |
|------|--------|
| `src/adp/api/routers/knowledge.py` | CREATE — CRUD router |
| `src/adp/api/app.py` | EDIT — register knowledge router |
| `web/src/api/knowledge.ts` | CREATE — TanStack Query hooks |
| `web/src/knowledge/KnowledgePage.tsx` | CREATE |
| `web/src/knowledge/KnowledgeItemRow.tsx` | CREATE |
| `web/src/knowledge/KnowledgeItemForm.tsx` | CREATE |
| `web/src/knowledge/DeleteConfirmDialog.tsx` | CREATE |
| `web/src/App.tsx` | EDIT — 4th nav tab + knowledge view |
| `tests/contract/test_knowledge_api.py` | CREATE — contract tests |

## Constitution Compliance

- **ART-IV**: contract tests cover list, create (valid), create (invalid), update, delete
- **ART-V**: full_text length capped at 10,000 chars server-side (FR-006 extension)
- **ART-VII**: embeddings always regenerated on write — grounding quality maintained
