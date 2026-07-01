# Contract: Knowledge Retrieval Python Interface

**Module**: `adp.knowledge`  
**Primary class**: `KnowledgeRetrieval`  
**Consumers**: ADP-SPEC-007 (recommendation subsystem), ADP-SPEC-008 (validation subsystem)  
**Date**: 2026-06-29

Internal Python interface. No HTTP surface for v1. All parameters and return types are typed Pydantic models (ART-XIII).

---

## `KnowledgeRetrieval` — Query Interface

```python
class KnowledgeRetrieval:
    def __init__(self, database_url: str, embedding_model: str) -> None:
        """Initialise retrieval against the given PostgreSQL database."""
```

### `hybrid_search(query: RetrievalQuery) -> RetrievalResult`

The primary retrieval method. Combines vector similarity, keyword search, and (optionally) relationship traversal using Reciprocal Rank Fusion. Returns a `RetrievalResult` in which every entry carries a `CitationRef` (FR-005 / QG-12).

**Guarantees**:
- Every `RetrievalResultEntry` in the result has a non-`None` `citation` field
- Results are ordered by descending `relevance_score`
- Only `active=True` items are returned by default
- Latency logged to structured log per ART-VI

**Raises**: `RetrievalError` on database or embedding failure

### `vector_search(query: RetrievalQuery) -> RetrievalResult`

Vector-only retrieval using pgvector HNSW cosine similarity. Used when semantic matching is the sole criterion.

### `keyword_search(query: RetrievalQuery) -> RetrievalResult`

Keyword-only retrieval using PostgreSQL full-text search (`ts_rank`). Used for exact terminology matching.

### `relationship_query(query: RetrievalQuery) -> RetrievalResult`

Relationship traversal only. Requires `query.traverse_from_id` and `query.relationship_type`. Returns items related to the specified item via the specified relationship type (FR-003, US3).

### `resolve_citation(citation: CitationRef) -> KnowledgeItem | None`

Resolve a citation reference to the exact knowledge item it describes. Returns `None` if the id+version combination is not in the index (US4 acceptance scenario 3).

---

## `KnowledgeIndexer` — Nightly CLI Interface

```python
class KnowledgeIndexer:
    def __init__(self, database_url: str, embedding_model: str) -> None: ...
    async def run(self) -> IndexerResult: ...
```

Called by the `adp-reindex` CLI entry point. Orchestrates: connector fetch → schema validation → embedding generation → upsert to index. Returns an `IndexerResult` summarising items indexed, updated, deactivated, and failed.

---

## Environment Variables

| Variable | Purpose | Required |
|---|---|---|
| `ADP_DATABASE_URL` | PostgreSQL connection URL (same as ADP-SPEC-002) | Yes |
| `ADP_EMBEDDING_MODEL` | sentence-transformers model name (e.g., `all-MiniLM-L6-v2`) | Yes |
| `ADP_EMBEDDING_DIM` | Embedding vector dimension; must match the chosen model | Yes |
| `ADP_GIT_REPO_URLS` | Comma-separated list of Git repository URLs to index | Yes |
| `ADP_GIT_LOCAL_CLONE_PATH` | Local directory for Git clones | Yes |
| `ADP_INDEX_SCHEMA_VERSION` | Expected schema version; indexer warns if mismatch | No (default `"1.0.0"`) |

All variables are externalized and MUST NOT appear in source (QG-08).

---

## Logging Contract (ART-VI / QG-10)

Every retrieval call emits a structured log entry:

```json
{
  "operation": "hybrid_search | vector_search | keyword_search | relationship_query",
  "query_id": "uuid",
  "result_count": 7,
  "latency_ms": 42,
  "error": null
}
```

The `query_text` and `full_text` of results are NEVER logged (organizational IP).

---

## Error Hierarchy

```python
class KnowledgeError(Exception): ...
class RetrievalError(KnowledgeError): ...      # query failure
class IndexingError(KnowledgeError): ...        # re-index failure
class SchemaValidationError(KnowledgeError): ...  # item failed FR-006 validation
class CitationResolutionError(KnowledgeError): ... # id+version not found
```
