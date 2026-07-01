# Data Model: Knowledge Base & Retrieval

**Branch**: `005-knowledge-retrieval` | **Date**: 2026-06-29  
**Sources**: `src/adp/knowledge/schema.py` (Pydantic models), `src/adp/knowledge/index.py` (SQLAlchemy ORM tables)

---

## `KnowledgeType` (StrEnum)

Closed v1 taxonomy of knowledge item categories (FR-002). New types require a spec amendment and schema version bump.

| Value | Description |
|---|---|
| `pattern` | A reusable architectural approach (e.g., Event-Driven Integration) |
| `reference_architecture` | A canonical system topology for a class of solutions |
| `standard` | A mandatory organizational rule or constraint |
| `principle` | A guiding design philosophy (e.g., Prefer stateless services) |
| `prior_solution` | An approved `ArchitectureDescription` from the ADP design store |

---

## `KnowledgeItem` (Pydantic model + database row)

The central indexed record. All fields required; no untyped content crosses the index boundary (ART-XIII / FR-001).

| Field | Type | Notes |
|---|---|---|
| `id` | `str` | Stable, opaque identifier from the canonical source (e.g., `PAT-001`); primary key |
| `version` | `str` | Semver or commit-hash from canonical source; MUST change when content changes |
| `kind` | `KnowledgeType` | Closed enum; determines metadata schema |
| `title` | `str` | Short human-readable label |
| `full_text` | `str` | Full prose or structured content; used for keyword search and embedding |
| `metadata` | `dict` | Kind-specific structured fields (e.g., `tags`, `domain`, `replaces`); validated against a kind-specific sub-schema |
| `source_ref` | `str` | Reference to the canonical source and its version (e.g., `git:org/patterns@abc123`) |
| `schema_version` | `str` | Semver of the `knowledge_items` schema used when this item was indexed |
| `active` | `bool` | `True` for current items; `False` for items removed from canonical source (citation-resolvable but not returned in active retrieval) |
| `embedding` | `list[float]` | Vector representation of `full_text`; dimension = `ADP_EMBEDDING_DIM` (default 384) |
| `indexed_at` | `datetime` | UTC timestamp of last index write |

**Validation**: Every `KnowledgeItem` MUST pass schema validation before being written to the index (FR-006). The `embedding` field is populated by the `EmbeddingProvider` after schema validation.

---

## `KnowledgeRelationship` (Pydantic model + database row)

A typed, directed edge between two `KnowledgeItem` records. Enables relationship traversal queries (FR-003, US3).

| Field | Type | Notes |
|---|---|---|
| `id` | `str` | Stable identifier (e.g., `REL-001`) |
| `source_id` | `str` | FK → `knowledge_items.id` |
| `target_id` | `str` | FK → `knowledge_items.id` |
| `relationship_type` | `str` | One of: `satisfies`, `extends`, `supersedes`, `implements`, `contradicts` |
| `weight` | `float` | Relevance weight for relationship traversal scoring (default 1.0) |

---

## `CitationRef` (Pydantic model)

The citation-ready reference returned with every retrieval result (FR-005 / ART-VII / QG-12). Sufficient to reconstruct the exact knowledge item used in an AI step.

| Field | Type | Notes |
|---|---|---|
| `item_id` | `str` | The stable id of the cited knowledge item |
| `item_version` | `str` | The exact version of the item at retrieval time |

---

## `RetrievalQuery` (Pydantic model)

The typed request to the retrieval subsystem. No raw text blobs; all parameters are typed (ART-XIII).

| Field | Type | Notes |
|---|---|---|
| `query_text` | `str` | The semantic query (requirement text or natural-language description) |
| `kinds` | `list[KnowledgeType] \| None` | Filter results to specific knowledge types; `None` = all types |
| `relationship_type` | `str \| None` | If set, traverse relationships of this type from matched items |
| `traverse_from_id` | `str \| None` | If set, find items related to this specific item by `relationship_type` |
| `limit` | `int` | Maximum results to return (default 10, max 50) |
| `vector_weight` | `float` | Weight for vector similarity in RRF (default 1.0) |
| `keyword_weight` | `float` | Weight for keyword search in RRF (default 1.0) |
| `relationship_weight` | `float` | Weight for relationship traversal in RRF (default 1.0) |

---

## `RetrievalResult` (Pydantic model)

The typed response from the retrieval subsystem. Every entry includes a `CitationRef` — zero entries may omit a citation.

| Field | Type | Notes |
|---|---|---|
| `items` | `list[RetrievalResultEntry]` | Ranked list of matched items |
| `query_id` | `str` | UUID for the retrieval query; used for logging and ART-VI span |
| `latency_ms` | `float` | End-to-end retrieval latency for the QG-10 log |

### `RetrievalResultEntry`

| Field | Type | Notes |
|---|---|---|
| `item` | `KnowledgeItem` | The matched item (embedding field omitted from response) |
| `citation` | `CitationRef` | Citation-ready reference (item_id + item_version) |
| `relevance_score` | `float` | RRF-combined relevance score (0–1) |
| `match_reason` | `str` | Human-readable explanation: `"vector"`, `"keyword"`, `"relationship"`, or a combination |

---

## Database Tables

### `knowledge_items`

| Column | Type | Constraints |
|---|---|---|
| `id` | `TEXT` | PRIMARY KEY |
| `version` | `TEXT` | NOT NULL |
| `kind` | `TEXT` | NOT NULL; CHECK in taxonomy |
| `title` | `TEXT` | NOT NULL |
| `full_text` | `TEXT` | NOT NULL |
| `metadata` | `JSONB` | NOT NULL |
| `source_ref` | `TEXT` | NOT NULL |
| `schema_version` | `TEXT` | NOT NULL |
| `active` | `BOOLEAN` | NOT NULL DEFAULT TRUE |
| `embedding` | `vector(384)` | NOT NULL; dimension from `ADP_EMBEDDING_DIM` |
| `full_text_search` | `TSVECTOR` | GENERATED ALWAYS AS `to_tsvector('english', full_text)` STORED |
| `indexed_at` | `TIMESTAMPTZ` | NOT NULL |

**Indexes**:
- `knowledge_items_embedding_hnsw` — HNSW on `embedding` using `vector_cosine_ops`
- `knowledge_items_fts_gin` — GIN on `full_text_search`
- `knowledge_items_kind` — B-tree on `kind` for type filtering
- `knowledge_items_active` — partial index WHERE `active = TRUE`

### `knowledge_relationships`

| Column | Type | Constraints |
|---|---|---|
| `id` | `TEXT` | PRIMARY KEY |
| `source_id` | `TEXT` | FK → `knowledge_items.id` |
| `target_id` | `TEXT` | FK → `knowledge_items.id` |
| `relationship_type` | `TEXT` | NOT NULL |
| `weight` | `FLOAT` | NOT NULL DEFAULT 1.0 |

**Index**: `(source_id, relationship_type)` B-tree for relationship traversal lookups
