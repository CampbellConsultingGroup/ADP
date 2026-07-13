# Research: Knowledge Base & Retrieval

**Branch**: `005-knowledge-retrieval` | **Date**: 2026-06-29  
**Phase**: 0 — Decisions and rationale before design begins

## Decision 1: Vector Store — pgvector in PostgreSQL

**Decision**: Use the `pgvector` PostgreSQL extension for vector storage and similarity search. No separate vector database.

**Rationale**: ADP already depends on PostgreSQL (ADP-SPEC-002). Adding the `pgvector` extension reuses existing infrastructure, keeps all ADP data in a single database, and eliminates a separate vector store service. The 10,000-item v1 corpus is well within pgvector's tested range (millions of vectors). ART-II is satisfied — canonical knowledge and derived indexes share one system of record, making the relationship between them queryable.

**Alternatives considered**:
- Dedicated vector database (Pinecone, Weaviate, Qdrant) — rejected: adds operational complexity; ADP is not at scale where a separate service is justified; splits data across systems
- Elasticsearch with vector fields — rejected: adds a full ELK stack for a governance tool; over-engineered for v1

---

## Decision 2: HNSW vs. IVFFlat Index

**Decision**: Use HNSW (Hierarchical Navigable Small World) indexing for the vector similarity column.

**Rationale**: At 10,000 items, HNSW provides better query-time performance than IVFFlat without the need to pre-select a `nlist` parameter. HNSW supports incremental inserts (no rebuild required when new items are added), which is essential for nightly re-indexing. Query accuracy at the p95 latency target is achievable with HNSW at default parameters.

**Alternatives considered**:
- IVFFlat — valid for large corpora (100k+) where HNSW memory overhead is a concern; rejected for v1 because it requires a rebuild when `nlist` parameters need tuning and does not support incremental inserts cleanly

---

## Decision 3: Embedding Library — sentence-transformers

**Decision**: Use the `sentence-transformers` Python library for embedding generation. The specific model is a deployment configuration (not hard-coded in this spec).

**Rationale**: `sentence-transformers` supports hundreds of pre-trained models, runs entirely locally (no external API calls), and integrates cleanly into Python. The model name is read from an environment variable (`ADP_EMBEDDING_MODEL`), defaulting to `all-MiniLM-L6-v2` for testing (fast, small, well-tested). Production deployments choose a model appropriate for their language and domain.

**Alternatives considered**:
- fastembed — lighter and faster via ONNX; fewer supported models; less mature ecosystem; may be a v2 option
- Hugging Face transformers directly — more control but requires more boilerplate than sentence-transformers; rejected for v1

---

## Decision 4: Hybrid Retrieval Combination — Reciprocal Rank Fusion (RRF)

**Decision**: Combine vector similarity, keyword, and relationship results using Reciprocal Rank Fusion.

**Rationale**: RRF is a well-studied, parameter-free fusion algorithm that combines ranked lists without requiring score normalization. It handles the heterogeneous score scales from vector similarity (cosine) and keyword search (BM25/tsvector rank) cleanly. It degrades gracefully when one retrieval mode returns no results. No training data is required — it works immediately.

**Alternatives considered**:
- Linear score combination with tuned weights — requires calibration data; error-prone when one mode returns no results (division by zero or score collapse)
- Learning-to-rank — appropriate for a search product with large query logs; over-engineered for a governance tool with a fixed corpus

---

## Decision 5: Keyword Search — PostgreSQL Full-Text Search

**Decision**: Use PostgreSQL's native full-text search (`tsvector`/`tsquery`) for keyword retrieval. A generated `tsvector` column on `knowledge_items.full_text` is indexed with a GIN index.

**Rationale**: PostgreSQL full-text search is already available in the stack with no additional dependencies. It supports stemming, stop-word removal, and relevance ranking (`ts_rank`). For a knowledge corpus of governance documents, it is sufficient for v1. The generated column keeps the tsvector in sync with `full_text` automatically on insert/update.

**Alternatives considered**:
- BM25 via a dedicated plugin (pg_bm25 / paradedb) — better ranking for some domains; adds a less-stable extension dependency; deferred to v2
- Elasticsearch — rejected: separate service; over-engineered

---

## Decision 6: Git Connector — GitPython + python-frontmatter

**Decision**: Use `gitpython` to clone/pull Git repositories and `python-frontmatter` to parse YAML/Markdown frontmatter into structured `KnowledgeItem` records.

**Rationale**: `gitpython` is the standard Python Git library. YAML frontmatter (the `---` header block in Markdown files) is the established convention for adding structured metadata to documentation. `python-frontmatter` extracts it cleanly. Knowledge item `id` and `version` are taken from frontmatter fields (`id:` and `version:`) to ensure stability across re-indexes.

**Item schema convention for Git-sourced items**:
```yaml
---
id: PAT-001
version: "1.2.0"
kind: pattern
title: "Event-Driven Integration"
tags: [integration, messaging]
---
# Full Markdown content below...
```

**Alternatives considered**:
- GitHub/GitLab API — depends on remote API availability; rejected for the indexer which must run offline/self-contained
- RST / AsciiDoc — YAML frontmatter in Markdown is the overwhelming convention for technical governance docs; not expanded for v1

---

## Decision 7: Re-index Strategy — Full Nightly Re-index

**Decision**: The nightly re-index is a full replacement of indexed items (not incremental). Each run: reads all items from all connectors, generates embeddings, and upserts into `knowledge_items` by `id`. Items whose id is absent from the latest canonical source are marked `active=False` (not deleted).

**Rationale**: Full re-index is simpler to implement and reason about than incremental/delta indexing. At 10,000 items with a fast embedding model, a full re-index completes in under one hour. Incremental indexing (tracking git diffs, detecting deletions) adds significant complexity and failure modes. The `active` flag preserves citation resolvability for items removed from canonical sources.

**Alternatives considered**:
- Incremental (git diff-based) — correct target for large corpora (100k+); adds webhook/polling complexity; deferred to v2
- Re-index on-demand — complicates the operational model; not needed for v1 nightly cadence

---

## Decision 8: ADP-SPEC-002 Connector for Prior Solutions

**Decision**: The `DesignStoreConnector` reads all designs with `status=approved` from the ADP-SPEC-002 `DesignStore`, serializes each `ArchitectureDescription` as a `prior_solution` knowledge item with `id = description.id`, `version = str(current_version)`, and `full_text` derived from the design's title + requirements descriptions.

**Rationale**: Approved designs are already the platform's canonical record of prior solutions. Reading them directly from the store ensures the knowledge base always reflects the current approved set. No separate export or sync mechanism is needed.

---

## Decision 9: Embedding Dimension and Schema Versioning

**Decision**: The embedding column uses a configurable dimension (default 384 for `all-MiniLM-L6-v2`; configurable via `ADP_EMBEDDING_DIM`). The `knowledge_items` schema carries a `schema_version` column (semver string). A breaking change to the item schema bumps the schema version and triggers a full re-index.

**Rationale**: Different embedding models produce different dimensions. Making it configurable at deployment time allows model upgrades without code changes. The `schema_version` column enables ADP-SPEC-007/008 to detect if the index was built with a different schema version than expected.
