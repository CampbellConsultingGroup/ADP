# Implementation Plan: Knowledge Base & Retrieval

**Branch**: `005-knowledge-retrieval` | **Date**: 2026-06-29 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/005-knowledge-retrieval/spec.md`

## Summary

Build the knowledge retrieval foundation that grounds ADP's AI. Index the organization's patterns, reference architectures, standards, principles, and prior solutions as typed, versioned, embedded records in PostgreSQL with the pgvector extension. Expose hybrid retrieval (vector similarity + full-text + relationship traversal) over a typed Python interface consumed by ADP-SPEC-007 and ADP-SPEC-008. Two connectors populate the index nightly: a Git connector (for document-based knowledge) and an ADP design store connector (for prior approved solutions).

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: `pgvector>=0.3` (SQLAlchemy PostgreSQL vector type), `sentence-transformers>=2.7` (self-hosted embedding; model-agnostic), `gitpython>=3.1` (Git connector), `python-frontmatter>=1.1` (Markdown/YAML frontmatter parsing from Git repos); existing stack: `sqlalchemy[asyncio]==2.0.51`, `asyncpg==0.31.0`  
**Storage**: PostgreSQL 15+ with the `pgvector` extension enabled; two new tables (`knowledge_items`, `knowledge_relationships`) + HNSW index on `embedding` column + GIN index on `full_text` for keyword search; migrations via Alembic  
**Testing**: pytest, pytest-asyncio; unit tests for embedding provider, connectors, and query logic; integration tests via testcontainers (PostgreSQL with pgvector extension)  
**Target Platform**: Python library sub-package (`adp.knowledge`) + nightly CLI runner (`adp-reindex`); consumed by AI orchestration specs  
**Project Type**: Python library + CLI indexer  
**Performance Goals**: Single retrieval query p95 < 500ms on a 10,000-item corpus (NFR-001, SC-005); nightly re-index of up to 10,000 items must complete within 4 hours  
**Constraints**: Self-hosted embedding model only — no organizational content transmitted to external services (ART-V / spec Assumptions); knowledge index does not own canonical content; re-index cadence is nightly (not real-time)  
**Scale/Scope**: v1 supports up to 10,000 knowledge items (NFR-002); HNSW index supports this with ample headroom

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Article(s) | Requirement | Status |
|------|-----------|-------------|--------|
| QG-01 | ART-I, ART-XVI | PR references approved spec/task IDs | ✅ All tasks will reference ADP-SPEC-005 |
| QG-03 | ART-III, ART-XIII, ART-XV | All knowledge items validate against their published schema before indexing; citation references are typed | ✅ FR-006; `KnowledgeItem` schema is versioned; citations carry typed `item_id + item_version` |
| QG-04 | ART-IV | Tests before implementation; ≥ 85% coverage | ✅ Pure-Python unit tests for connectors and query logic; integration tests with testcontainers+pgvector |
| QG-05 | ART-IV, ART-XIII | Contract tests pass | ✅ Typed retrieval interface contract tests verify citation completeness |
| QG-06 | ART-V | SAST clean; no secrets in source | ✅ No external API keys; self-hosted embedding |
| QG-07 | ART-V | Dep scan: no high/critical CVEs | ✅ Standard well-maintained libraries |
| QG-08 | ART-V | Secret scan clean; no org content transmitted externally | ✅ Self-hosted embedding; Git connector reads local clone only |
| QG-12 | ART-VII | AI recommendations carry grounding citations with versions | ✅ **This spec IS the QG-12 implementation**; every retrieval result carries `CitationRef(item_id, item_version)` (FR-005) |
| QG-18 | ART-XIV | Pinned deps; reproducible | ✅ New deps pinned in `pyproject.toml` |

**Constitution Alignment**: ART-II — the knowledge index stores derived representations; canonical sources remain authoritative; the index never becomes a primary record. ART-XV — `KnowledgeItem` schema is versioned; breaking changes require a version bump and migration. ART-VI (QG-10) — the indexer and retrieval paths emit structured logs.

## Project Structure

### Documentation (this feature)

```text
specs/005-knowledge-retrieval/
├── plan.md                 # This file
├── research.md             # Phase 0 — decisions and rationale
├── data-model.md           # Phase 1 — knowledge schema entities
├── contracts/
│   └── retrieval-contract.md  # Phase 1 — Python retrieval interface
├── quickstart.md           # Phase 1 — indexing and querying knowledge
├── checklists/
│   └── requirements.md     # Spec quality checklist
└── tasks.md                # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
src/
└── adp/
    ├── __init__.py               # ADP-SPEC-001 (unchanged)
    ├── models.py                 # ADP-SPEC-001 (unchanged)
    ├── store/                    # ADP-SPEC-002 (unchanged)
    ├── authz/                    # ADP-SPEC-004 (unchanged)
    ├── audit/                    # ADP-SPEC-004 (unchanged)
    └── knowledge/
        ├── __init__.py           # Exports KnowledgeRetrieval, KnowledgeItem, CitationRef
        ├── schema.py             # KnowledgeItem, KnowledgeRelationship, CitationRef,
        │                         #   RetrievalQuery, RetrievalResult, KnowledgeType (enum)
        ├── index.py              # KnowledgeIndex — SQLAlchemy ORM tables + Alembic migration
        │                         #   Tables: knowledge_items, knowledge_relationships
        ├── embedder.py           # EmbeddingProvider — wraps sentence-transformers;
        │                         #   model-configurable; never calls external APIs
        ├── retrieval.py          # KnowledgeRetrieval — hybrid query interface:
        │                         #   vector_search(), keyword_search(), relationship_query(),
        │                         #   hybrid_search() (combines all three via RRF)
        ├── indexer.py            # Indexer — orchestrates connectors → embedder → index;
        │                         #   runs nightly via adp-reindex CLI entry point
        └── connectors/
            ├── __init__.py
            ├── git.py            # GitConnector — clones/reads Git repos;
            │                     #   parses Markdown/YAML frontmatter into KnowledgeItem
            └── design_store.py   # DesignStoreConnector — reads approved ArchitectureDescription
                                  #   records from ADP-SPEC-002 as prior_solution items

tests/
└── knowledge/
    ├── __init__.py
    ├── test_schema.py            # KnowledgeItem validation + schema versioning
    ├── test_embedder.py          # EmbeddingProvider unit tests (mock model)
    ├── test_connectors.py        # GitConnector + DesignStoreConnector unit tests
    ├── test_retrieval.py         # KnowledgeRetrieval unit tests (mock index)
    └── test_integration.py       # Integration tests (testcontainers + pgvector)

src/adp/store/migrations/versions/
└── 002_knowledge_schema.py       # Adds knowledge_items + knowledge_relationships tables

pyproject.toml                    # Updated with pgvector, sentence-transformers, gitpython, etc.
```

**Structure Decision**: New `adp.knowledge` sub-package within `src/adp/`. The retrieval interface (`KnowledgeRetrieval`) is a pure Python API — no HTTP surface. It is consumed directly by ADP-SPEC-007/008 via Python import. The indexer (`Indexer`) is a CLI entry point (`adp-reindex`) invoked by the nightly scheduler.
