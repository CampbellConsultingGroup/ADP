# Tasks: Knowledge Base Management

**Input**: Design documents from `/specs/020-knowledge-base-crud/`
**Prerequisites**: All complete ✅

---

## Phase 1: Setup

- [X] T001 Register new knowledge router in `src/adp/api/app.py` (import + `app.include_router(knowledge.router)`)

---

## Phase 2: US1 — Browse Knowledge Items

### Tests (MANDATORY — ART-IV)

- [X] T002 [P] [US1] Write `test_list_knowledge_items_returns_200()` in `tests/contract/test_knowledge_api.py`: seed two items in the in-memory store; GET `/api/v1/knowledge`; assert 200 and both items in response with id, kind, title, source_ref fields present
- [X] T003 [P] [US1] Write `test_list_knowledge_items_empty_returns_empty_list()`: GET with empty store; assert 200 and `{"items": []}` shape

### Implementation

- [X] T004 [US1] Create `src/adp/api/routers/knowledge.py`: define `KnowledgeItemSummary` Pydantic response model (id, version, kind, title, source_ref, metadata, indexed_at, active); define `KnowledgeItemDetail` extending summary with `full_text`; define `KnowledgeItemListResponse(items: list[KnowledgeItemSummary])`; add `GET /api/v1/knowledge` endpoint that queries `knowledge_items` table for all active rows and returns list
- [X] T005 [US1] Add `GET /api/v1/knowledge/{item_id}` endpoint to `src/adp/api/routers/knowledge.py`: query by id where active=true; return 404 if not found; return `KnowledgeItemDetail`

**Checkpoint**: `GET /api/v1/knowledge` lists all 21 seeded items

---

## Phase 3: US2 — Create a Knowledge Item

### Tests (MANDATORY — ART-IV)

- [X] T006 [P] [US2] Write `test_create_knowledge_item_returns_201()` in `tests/contract/test_knowledge_api.py`: POST valid body `{id: "TEST-001", version: "1.0.0", kind: "principle", title: "Test", full_text: "Some content", source_ref: "https://example.com"}`; assert 201 and body contains `id` and `kind`
- [X] T007 [P] [US2] Write `test_create_knowledge_item_blank_title_returns_422()`: POST with `title: ""`; assert 422
- [X] T008 [P] [US2] Write `test_create_knowledge_item_blank_full_text_returns_422()`: POST with `full_text: ""`; assert 422

### Implementation

- [X] T009 [US2] Add `KnowledgeItemCreateRequest` Pydantic model to `src/adp/api/routers/knowledge.py`: fields id (optional, generates UUID if absent), version (default "1.0.0"), kind (KnowledgeType), title (non-empty, max 200 chars), full_text (non-empty, max 10000 chars), source_ref (non-empty), metadata (dict, default {}); field validators for non-empty title and full_text
- [X] T010 [US2] Add `POST /api/v1/knowledge` endpoint to `src/adp/api/routers/knowledge.py`: generate embedding via module-level `EmbeddingProvider("all-MiniLM-L6-v2")`; call `KnowledgeIndex.upsert_item()`; return 201 with `KnowledgeItemSummary`; on embedding failure log warning and use zero vector `[0.0] * 384`

**Checkpoint**: POST creates item; `GET /api/v1/knowledge` count increases by 1

---

## Phase 4: US3 — Edit a Knowledge Item

### Tests (MANDATORY — ART-IV)

- [X] T011 [P] [US3] Write `test_update_knowledge_item_returns_200()` in `tests/contract/test_knowledge_api.py`: PUT to existing item id with updated title; assert 200 and updated title in response
- [X] T012 [P] [US3] Write `test_update_knowledge_item_not_found_returns_404()`: PUT to non-existent id; assert 404

### Implementation

- [X] T013 [US3] Add `KnowledgeItemUpdateRequest` Pydantic model to `src/adp/api/routers/knowledge.py`: same fields as create but all optional (patch semantics); at least one field must be provided
- [X] T014 [US3] Add `PUT /api/v1/knowledge/{item_id}` endpoint to `src/adp/api/routers/knowledge.py`: fetch existing item (404 if not found); merge request fields over existing values; re-generate embedding if title or full_text changed; call `KnowledgeIndex.upsert_item()`; return 200 with `KnowledgeItemSummary`

**Checkpoint**: PUT updates item fields; list reflects new title immediately

---

## Phase 5: US4 — Delete a Knowledge Item

### Tests (MANDATORY — ART-IV)

- [X] T015 [P] [US4] Write `test_delete_knowledge_item_returns_204()` in `tests/contract/test_knowledge_api.py`: DELETE existing item; assert 204; subsequent GET returns 404
- [X] T016 [P] [US4] Write `test_delete_knowledge_item_not_found_returns_404()`: DELETE non-existent id; assert 404

### Implementation

- [X] T017 [US4] Add `DELETE /api/v1/knowledge/{item_id}` endpoint to `src/adp/api/routers/knowledge.py`: fetch item (404 if not found or already inactive); call `KnowledgeIndex.mark_inactive([item_id])`; return 204 No Content

**Checkpoint**: DELETE soft-deletes; item no longer appears in GET list

---

## Phase 6: Frontend — Knowledge Tab and Page

### Implementation

- [X] T018 [P] [US1] Create `web/src/api/knowledge.ts`: TypeScript interfaces `KnowledgeItemSummary`, `KnowledgeItemDetail`, `KnowledgeItemCreateRequest`, `KnowledgeItemUpdateRequest`; TanStack Query hooks `useKnowledgeItems()` (GET list), `useKnowledgeItem(id)` (GET detail), `useCreateKnowledgeItem()` (POST), `useUpdateKnowledgeItem()` (PUT), `useDeleteKnowledgeItem()` (DELETE)
- [X] T019 [US1] Create `web/src/knowledge/KnowledgePage.tsx`: renders list of `KnowledgeItemRow` components; kind filter dropdown (All / principle / pattern / standard / reference_architecture / prior_solution); item count display; "Add Item" button that toggles `KnowledgeItemForm` in create mode; uses `useKnowledgeItems()` hook
- [X] T020 [US1] Create `web/src/knowledge/KnowledgeItemRow.tsx`: displays kind badge (colour-coded), title, source_ref link; Edit button sets parent state to edit mode for that item; Delete button opens `DeleteConfirmDialog`
- [X] T021 [US2] [US3] Create `web/src/knowledge/KnowledgeItemForm.tsx`: create/edit form with fields id (create only), kind (select), title (text), full_text (textarea, rows=8), source_ref (text), metadata (textarea JSON); validates non-empty title and full_text before submit; calls `useCreateKnowledgeItem` or `useUpdateKnowledgeItem` depending on mode; on success invalidates `["knowledge-items"]` query and resets form
- [X] T022 [US4] Create `web/src/knowledge/DeleteConfirmDialog.tsx`: modal with item title, "Cancel" and "Delete" buttons; calls `useDeleteKnowledgeItem()` on confirm; on success invalidates `["knowledge-items"]` query
- [X] T023 [P] Update `web/src/App.tsx`: extend `AppView` type to include `"knowledge"`; add "Knowledge" nav tab to all three existing pages' headers; render `KnowledgePage` when view === "knowledge"; pass `onNavigate` prop

---

## Phase 7: Polish

- [X] T024 [P] Run `pytest tests/contract/test_knowledge_api.py -q --no-cov` — all tests pass
- [X] T025 [P] Run `pytest tests/ --ignore=tests/integration -q --no-cov` — full suite clean
- [X] T026 [P] Run `ruff check src/adp/api/routers/knowledge.py` — clean
- [X] T027 [P] Run `cd web && npx tsc --noEmit` — zero TypeScript errors
