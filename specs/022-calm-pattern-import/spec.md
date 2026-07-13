# Feature Specification: CALM Pattern Import

**Feature Branch**: `022-calm-pattern-import`
**Created**: 2026-07-03
**Status**: Draft

## Constitutional Articles Touched

- **ART-I** — Spec-Driven Development: always applies
- **ART-IV** — Test-Driven Development: always applies
- **ART-V** — Security & Threat Model: imported files are parsed and persisted; injection and path traversal risks addressed below
- **ART-VII** — AI Grounding: imported CALM patterns become knowledge base items that directly ground AI recommendations; quality and accuracy of imports affects recommendation quality
- **ART-VIII** — Human in the Loop: import is always an explicit user-initiated action; no auto-import from untrusted sources

## Threat Model

**Assets at risk**: Knowledge base integrity — a maliciously crafted CALM file could inject adversarial content into the knowledge base, degrading AI recommendation quality.

**Trust boundaries crossed**: File system / HTTP body → Python parser → PostgreSQL knowledge_items table.

**Abuse cases**:
- Oversized `full_text` injection via a CALM file with very long node descriptions: mitigated by truncating imported text at 10,000 characters (consistent with the knowledge base CRUD limit — ADP-SPEC-020 FR-006).
- Path traversal via `source-ref` URLs that reference internal services: mitigated by treating `source-ref` as a display-only string, never fetching it.
- Invalid JSON that causes parser crash: mitigated by wrapping parse step in try/except; invalid files return a structured error response.

**Residual risk**: Imported CALM patterns are trusted to reflect the architectural intent of the file's author; no semantic validation of pattern quality beyond schema conformance. Accepted — same risk as manual knowledge base creation.

## User Scenarios & Testing

### User Story 1 — Import a CALM Pattern File via CLI (Priority: P1)

A platform engineer has a CALM pattern JSON file (e.g. from the FINOS CALM repository or their own pattern library) and wants to add it to the ADP knowledge base so the recommendation engine can use it to ground future suggestions. They run `adp-import-calm my-pattern.json` from the terminal and see confirmation that the pattern was indexed.

**Why this priority**: The CLI path is the fastest way to populate the knowledge base and the most useful for batch operations.

**Independent Test**: Run `adp-import-calm` against a valid CALM JSON file; `GET /api/v1/knowledge` shows one new item with `kind: "reference_architecture"` and the pattern's name as the title.

**Acceptance Scenarios**:

1. **Given** a valid CALM pattern file with a single pattern containing nodes and relationships, **When** `adp-import-calm pattern.json` is run, **Then** a `reference_architecture` knowledge item is created with the pattern name as title, a generated full_text summary of its nodes and relationships, and `source_ref` set to the file path or CALM `$id` URL if present.
2. **Given** a CALM file containing multiple named patterns, **When** imported, **Then** one knowledge item is created per pattern.
3. **Given** an invalid JSON file, **When** `adp-import-calm bad.json` is run, **Then** the command exits with a non-zero status and a clear error message; no knowledge items are created.
4. **Given** a CALM file that has already been imported (same unique-id), **When** imported again, **Then** the existing knowledge item is updated (upsert), not duplicated.

---

### User Story 2 — Import a CALM Pattern via the Knowledge Base UI (Priority: P2)

An architect is in the ADP Knowledge tab and wants to import a CALM pattern without using the command line. They click "Import CALM Pattern", paste or upload a CALM JSON document, and see the imported pattern appear in the list.

**Why this priority**: Makes CALM import accessible to non-CLI users. Builds on the existing Knowledge screen (ADP-SPEC-020).

**Independent Test**: POST a valid CALM JSON body to `POST /api/v1/knowledge/import/calm`; the pattern appears in `GET /api/v1/knowledge` with the correct title and kind.

**Acceptance Scenarios**:

1. **Given** the Knowledge tab is open, **When** the user clicks "Import CALM Pattern", pastes valid CALM JSON, and clicks Import, **Then** the new item appears in the knowledge list immediately.
2. **Given** invalid JSON is pasted, **When** the user clicks Import, **Then** a validation error is shown and nothing is persisted.
3. **Given** a CALM document with no recognisable pattern name, **When** imported, **Then** the item title defaults to the CALM document's `$id` or `"Imported CALM Pattern"` as a fallback.

---

### User Story 3 — Bulk Import from a Directory (Priority: P3)

A platform team has a directory of CALM pattern files from the FINOS repository. They run `adp-import-calm --dir ./calm-patterns/` and all valid pattern files in the directory are indexed in a single command.

**Why this priority**: Enables batch population of the knowledge base from an existing CALM pattern library.

**Independent Test**: Run `adp-import-calm --dir` against a directory of 3 CALM files; 3 (or more, if multi-pattern files) items are created in the knowledge base.

**Acceptance Scenarios**:

1. **Given** a directory of 3 valid CALM JSON files, **When** `adp-import-calm --dir ./patterns/` is run, **Then** all valid files are imported; invalid files are skipped with a warning; a summary shows counts of imported and skipped files.
2. **Given** the directory contains non-JSON files, **Then** they are silently skipped.

---

### Edge Cases

- CALM file with no nodes: generate a knowledge item whose full_text notes the pattern has no nodes — still valid to import.
- CALM pattern whose name contains special characters: sanitise for safe storage; preserve original in metadata.
- Embedding generation failure: save the item with a zero-vector; log a warning; do not fail the import.
- CALM file referencing external `$ref` URLs: do not resolve them; treat the CALM document as-is.
- Very large CALM files (100+ nodes): truncate the full_text summary at 10,000 characters; still import successfully.

## Requirements

### Functional Requirements

- **FR-001**: The system MUST provide an `adp-import-calm` CLI command (entry point registered in `pyproject.toml`) that accepts a CALM JSON file path as its argument.
- **FR-002**: The CLI MUST parse the CALM JSON document, extract the pattern name (from `$id`, top-level `name`, or first node name as fallback), and generate a human-readable `full_text` summary listing each node's type, name, and description, and each relationship's type and connected nodes.
- **FR-003**: The CLI MUST create a `KnowledgeItem` with `kind: reference_architecture`, `title` from the pattern name, `full_text` from the generated summary, `source_ref` from the CALM document's `$id` field (or file path if absent), and `metadata` including `{"calm_node_count": N, "calm_relationship_count": M, "calm_source": "import"}`.
- **FR-004**: The CLI MUST generate a real 384-dim embedding for the imported item using `EmbeddingProvider("all-MiniLM-L6-v2")` and persist it to the `knowledge_items` table via `KnowledgeIndex.upsert_item()`.
- **FR-005**: The CLI MUST support `--dir <path>` flag to import all `.json` files in a directory, reporting per-file success/failure.
- **FR-006**: The CLI MUST use upsert semantics: if a knowledge item with the same ID already exists, update it rather than creating a duplicate.
- **FR-007**: The system MUST expose `POST /api/v1/knowledge/import/calm` that accepts a CALM JSON document as the request body and imports it using the same logic as the CLI.
- **FR-008**: The `POST` endpoint MUST return 201 with a list of created/updated knowledge item summaries, or 422 for invalid JSON or schema violations.
- **FR-009**: The Knowledge tab UI MUST provide an "Import CALM Pattern" button that opens a textarea for pasting CALM JSON and a submit button.
- **FR-010**: The importer MUST truncate any single field to 10,000 characters maximum to prevent oversized entries.

### Key Entities

- **CALMImportResult**: `items_created: int`, `items_updated: int`, `items_failed: int`, `items: list[KnowledgeItemSummary]`

## Success Criteria

- **SC-001**: A CALM pattern from the FINOS CALM repository (e.g. API Gateway pattern) can be imported in under 10 seconds and immediately appears in `GET /api/v1/knowledge`.
- **SC-002**: After importing a CALM pattern, a recommendation request that includes a requirement matching the pattern's domain retrieves the imported pattern as a grounding citation.
- **SC-003**: Bulk import of 10 CALM pattern files completes in under 60 seconds.
- **SC-004**: An invalid CALM file produces a clear error message and leaves the knowledge base unchanged.

## Assumptions

- CALM pattern files follow the 2025-03 draft schema but the importer is lenient — it extracts what it can from any JSON file that has a `nodes` array.
- The importer does not validate that the CALM file passes the full CALM schema; it uses best-effort extraction.
- Each CALM file is treated as one pattern (one knowledge item) unless the file explicitly contains a named list of patterns.
- The `adp-import-calm` CLI command uses the `ADP_DATABASE_URL` environment variable for the database connection, consistent with other ADP CLI tools.
- Relationship semantics in CALM (protocol, auth) are captured in the `full_text` summary for embedding purposes but not stored as structured data beyond what the knowledge item schema supports.
