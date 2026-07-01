# ADP Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-07-01

## Active Technologies
- Python 3.11+ + SQLAlchemy 2.x (async ORM), asyncpg (PostgreSQL async driver), Alembic (migrations), testcontainers-python (PostgreSQL container for integration tests), pydantic-settings (database URL config) (002-design-store)
- PostgreSQL 15+ — primary persistence; JSONB for `ArchitectureDescription` content with indexed paths for traceability queries (002-design-store)
- Python 3.11+ + FastAPI ≥ 0.111, uvicorn[standard] ≥ 0.30, python-jose[cryptography] ≥ 3.3 (JWT/OIDC validation), httpx ≥ 0.27 (OIDC JWKS fetch + test client) (003-platform-api)
- Delegates all canonical model persistence to `adp.store.DesignStore` (ADP-SPEC-002); transient operation state stored in-process dict with TTL for v1 (Redis deferred) (003-platform-api)
- Python 3.11+ + None new — uses `adp.models.AuditEntry` (ADP-SPEC-001) and `adp.store.DesignStore` (ADP-SPEC-002); no additional runtime packages (004-identity-authz)
- Delegates audit writes to `adp.store.DesignStore` (ADP-SPEC-002); the permission table is an in-process Python constant (no database required) (004-identity-authz)
- Python 3.11+ + `pgvector>=0.3` (SQLAlchemy PostgreSQL vector type), `sentence-transformers>=2.7` (self-hosted embedding; model-agnostic), `gitpython>=3.1` (Git connector), `python-frontmatter>=1.1` (Markdown/YAML frontmatter parsing from Git repos); existing stack: `sqlalchemy[asyncio]==2.0.51`, `asyncpg==0.31.0` (005-knowledge-retrieval)
- PostgreSQL 15+ with the `pgvector` extension enabled; two new tables (`knowledge_items`, `knowledge_relationships`) + HNSW index on `embedding` column + GIN index on `full_text` for keyword search; migrations via Alembic (005-knowledge-retrieval)
- Python 3.11+ + `httpx>=0.27` (async HTTP client for configurable LLM endpoint), `opentelemetry-sdk>=1.25` (telemetry span emission per ADP-SPEC-012), `tiktoken>=0.7` (token counting for cost estimation); existing stack: Pydantic v2, SQLAlchemy 2 async, FastAPI (ADP-SPEC-003) (006-requirements-intake)
- `ExtractedProposal` records stored transiently in-memory (same in-process store as ADP-SPEC-003 operation results, TTL 24h); confirmed requirements written to the canonical store via ADP-SPEC-002 `DesignStore`; raw source text is NEVER persisted (006-requirements-intake)
- Python 3.11+ + `langgraph>=0.2` (step orchestration with inspectable state), `langchain-core>=0.2` (Pydantic structured output tooling for LLM responses); same LLM client as ADP-SPEC-006 (`httpx>=0.27`, configurable endpoint); `opentelemetry-sdk>=1.25` (already in stack) (007-recommendation-engine)
- `SolutionOption` records stored transiently in ADP-SPEC-003's in-process operation store (TTL 24h); accepted option materializes `Element`/`Relationship` records into ADP-SPEC-002 `DesignStore`; no additional database tables required (007-recommendation-engine)
- Python 3.11+ + `langgraph>=0.2` (already in stack from ADP-SPEC-007); same LLM client as ADP-SPEC-006/007 (`httpx>=0.27`); `opentelemetry-sdk>=1.25` (already in stack); `asyncio.gather` for critic fan-out (no additional deps) (008-llm-as-judge)
- `Verdict` stored transiently in ADP-SPEC-003's in-process operation store (TTL 24h); on human acceptance, verdict is optionally persisted to ADP-SPEC-002's design store as a design annotation; raw source text is NEVER stored (008-llm-as-judge)

- Python 3.11+ + Pydantic v2 (entity definitions and schema emission), jsonschema 4.x (schema validation in tests) (001-canonical-data-model)

## Project Structure

```text
src/
tests/
```

## Commands

cd src [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] pytest [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] ruff check .

## Code Style

Python 3.11+: Follow standard conventions

## Recent Changes
- 008-llm-as-judge: Added Python 3.11+ + `langgraph>=0.2` (already in stack from ADP-SPEC-007); same LLM client as ADP-SPEC-006/007 (`httpx>=0.27`); `opentelemetry-sdk>=1.25` (already in stack); `asyncio.gather` for critic fan-out (no additional deps)
- 007-recommendation-engine: Added Python 3.11+ + `langgraph>=0.2` (step orchestration with inspectable state), `langchain-core>=0.2` (Pydantic structured output tooling for LLM responses); same LLM client as ADP-SPEC-006 (`httpx>=0.27`, configurable endpoint); `opentelemetry-sdk>=1.25` (already in stack)
- 006-requirements-intake: Added Python 3.11+ + `httpx>=0.27` (async HTTP client for configurable LLM endpoint), `opentelemetry-sdk>=1.25` (telemetry span emission per ADP-SPEC-012), `tiktoken>=0.7` (token counting for cost estimation); existing stack: Pydantic v2, SQLAlchemy 2 async, FastAPI (ADP-SPEC-003)


<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
