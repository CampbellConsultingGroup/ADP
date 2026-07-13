# Feature Specification: Knowledge Base Management

**Feature Branch**: `020-knowledge-base-crud`
**Created**: 2026-07-03
**Status**: Draft

## Constitutional Articles Touched

- **ART-I** — Spec-Driven Development: always applies
- **ART-II** — Model is Source of Truth: knowledge items are canonical data; the API is the write path, the UI is a projection
- **ART-IV** — Test-Driven Development: always applies
- **ART-V** — Security & Threat Model: CRUD endpoints mutate the knowledge base used by the AI recommendation engine; injection and privilege escalation risks addressed below
- **ART-VII** — AI Grounding: knowledge items directly feed the recommendation retrieval step; polluted or low-quality items degrade output quality
- **ART-IX** — Audit Trail: create/update/delete actions must be recorded in the audit log

## Threat Model

**Assets at risk**: Knowledge items that ground AI recommendations; a corrupted knowledge base produces poor or misleading architectural advice.

**Trust boundaries crossed**: Browser → FastAPI (CRUD mutations).

**Abuse cases**:
- Prompt injection via `full_text` field: attacker embeds adversarial instructions that are later retrieved and injected into LLM prompts → Mitigation: knowledge items are passed as data context to the LLM, not as executable instructions; field length limits applied server-side.
- Mass deletion of knowledge base: user accidentally or maliciously deletes all items → Mitigation: delete is a soft-delete (sets `active=false`), not a hard delete; items are recoverable via direct DB access.

**Residual risk**: No authentication on the API in v1; any user can mutate the knowledge base. Accepted for v1 (single-tenant, internal tool).

## User Scenarios & Testing

### User Story 1 — Browse Knowledge Items (Priority: P1)

An architect opens the Knowledge tab and sees all active knowledge items listed with their kind badge, title, and source reference. They can filter by kind to focus on patterns, principles, or standards.

**Why this priority**: Read access is the most common operation and is needed before any editing can happen.

**Independent Test**: With knowledge items seeded in the database, the Knowledge tab lists them all; filtering by "pattern" shows only pattern items.

**Acceptance Scenarios**:

1. **Given** the knowledge base has 21 seeded items, **When** the user opens the Knowledge tab, **Then** all 21 active items are listed with kind badge, title, and source ref visible.
2. **Given** the item list is loaded, **When** the user selects "pattern" from the kind filter, **Then** only items with kind="pattern" are shown.
3. **Given** the item list is loaded, **When** the user clears the kind filter, **Then** all items are shown again.

---

### User Story 2 — Create a Knowledge Item (Priority: P2)

An architect clicks "Add Item", fills in the title, kind, full text (the knowledge content), and source reference, then saves. The new item immediately appears in the list with a real embedding generated server-side.

**Why this priority**: Enables teams to grow the knowledge base beyond the seeded data.

**Independent Test**: POST a new item via the UI form; it appears in the list and is retrievable by the recommendation engine.

**Acceptance Scenarios**:

1. **Given** the Knowledge tab is open, **When** the user fills in all required fields and clicks Save, **Then** the item is persisted and appears in the list.
2. **Given** the create form is open, **When** the user submits with a blank title, **Then** a validation error is shown and the item is not saved.
3. **Given** the create form is open, **When** the user submits with a blank full_text, **Then** a validation error is shown.

---

### User Story 3 — Edit a Knowledge Item (Priority: P3)

An architect clicks Edit on an existing item, modifies the title or full text, and saves. The updated content is re-embedded server-side so future recommendations reflect the change.

**Why this priority**: Existing items need refinement as organisational knowledge evolves.

**Independent Test**: Edit the title and full_text of a seeded item; the change is reflected in the list immediately.

**Acceptance Scenarios**:

1. **Given** an item exists, **When** the user clicks Edit, modifies the full_text, and saves, **Then** the updated item is shown in the list.
2. **Given** the edit form is open with an item's data pre-filled, **When** the user clears the title and saves, **Then** a validation error is shown and the item is not updated.

---

### User Story 4 — Delete a Knowledge Item (Priority: P4)

An architect clicks Delete on an item they want to remove. A confirmation dialog asks them to confirm before the soft-delete proceeds. The item disappears from the list but is not hard-deleted from the database.

**Why this priority**: Removes incorrect or superseded knowledge without irreversible data loss.

**Independent Test**: Delete an item; it disappears from the Knowledge tab list but the row remains in the database with active=false.

**Acceptance Scenarios**:

1. **Given** an item is listed, **When** the user clicks Delete and confirms, **Then** the item is removed from the list but remains in the database with active=false.
2. **Given** the delete confirmation dialog is shown, **When** the user clicks Cancel, **Then** the item is NOT deleted and remains in the list.

---

### Edge Cases

- What happens when the knowledge base is empty? Display a friendly empty state with a call-to-action to add the first item.
- What happens when the embedding generation fails server-side? Save the item with a zero-vector; log a warning; do not fail the request.
- What happens when the user enters very long full_text? Accept up to 10,000 characters server-side; truncate display in the list view.
- What happens when two users edit the same item simultaneously? Last write wins (acceptable for v1 single-tenant use).

## Requirements

### Functional Requirements

- **FR-001**: The system MUST expose a `GET /api/v1/knowledge` endpoint returning all active knowledge items (id, version, kind, title, source_ref, metadata, indexed_at).
- **FR-002**: The system MUST expose a `GET /api/v1/knowledge/{item_id}` endpoint returning a single item's full details including full_text.
- **FR-003**: The system MUST expose a `POST /api/v1/knowledge` endpoint that accepts a new item, generates its embedding server-side, and persists it.
- **FR-004**: The system MUST expose a `PUT /api/v1/knowledge/{item_id}` endpoint that accepts updated fields, re-generates the embedding, and upserts the item.
- **FR-005**: The system MUST expose a `DELETE /api/v1/knowledge/{item_id}` endpoint that soft-deletes the item (sets active=false).
- **FR-006**: The `POST` and `PUT` endpoints MUST validate that title and full_text are non-empty; return HTTP 422 on validation failure.
- **FR-007**: The React UI MUST add a "Knowledge" navigation tab alongside Intake, Recommendations, and Canvas.
- **FR-008**: The Knowledge screen MUST display all active items in a list with kind badge, title, and source_ref per row.
- **FR-009**: The Knowledge screen MUST provide a kind filter (dropdown) to filter items by KnowledgeType.
- **FR-010**: The Knowledge screen MUST provide an "Add Item" button that opens a form for creating a new item.
- **FR-011**: Each item row MUST have an Edit button that opens a pre-filled form for updating the item.
- **FR-012**: Each item row MUST have a Delete button that shows a confirmation dialog before soft-deleting.
- **FR-013**: The Knowledge screen MUST show a count of active items.

### Key Entities

- **KnowledgeItem**: id, version, kind (one of: principle, pattern, standard, reference_architecture, prior_solution), title, full_text, source_ref, metadata (JSON), active, indexed_at

## Success Criteria

- **SC-001**: An architect can create a new knowledge item in under 60 seconds from clicking "Add Item" to seeing it in the list.
- **SC-002**: All active knowledge items load within 2 seconds on the Knowledge tab.
- **SC-003**: Soft-deleted items do not appear in the knowledge list or in recommendation retrieval results.
- **SC-004**: Edited items reflect updated content in the list immediately after save.

## Assumptions

- The sentence-transformers model (`all-MiniLM-L6-v2`) is available server-side for embedding generation on create/update.
- No pagination is required for v1 (knowledge bases are expected to have fewer than 500 items).
- No full-text search within the Knowledge screen is required for v1; kind filter is sufficient.
- Metadata field is optional; the UI provides a plain-text JSON input for advanced users.
- Item IDs are provided by the client on create (slug-style, e.g., "PRIN-007"); if omitted, a UUID is generated server-side.
