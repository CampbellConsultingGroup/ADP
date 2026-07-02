# ADP Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-07-02 (013-playwright-e2e added)

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
- TypeScript 5.x + React 18 + React Flow v12 (`@xyflow/react`) + TanStack Query v5 + Zustand v4 + Vite 5 (009-c4-workspace)
- Layout positions stored via a new `GET/PUT /api/v1/designs/{id}/layout` endpoint added to ADP-SPEC-003; canonical model data from existing endpoints (009-c4-workspace)
- Python 3.11+ + `cairosvg>=2.7` (SVG→PNG, no Java required); `jsonschema>=4.10` (theme schema validation, already in project); `LockedTheme` Pydantic v2 model generates `c4-theme.schema.json` via `adp-generate` (010-locked-theme-rendering)
- `c4-theme.json` authored artifact (versioned in git, reviewed as diff); `c4-theme.schema.json` generated from `LockedTheme` model; deterministic grid auto-layout for SVG; render exposed via `POST /api/v1/designs/{id}/render`; container fill updated to `#2874A6` (v1.0.1, WCAG AA compliant) (010-locked-theme-rendering)
- Python 3.11+ + `pyyaml>=6.0` (YAML export); `python-frontmatter>=1.1` (Markdown frontmatter — already in stack); new packages `adp.docs` (document generator, traceability), `adp.export` (export bundle orchestrator, importer, models); two new FastAPI routers; export requires ART-VIII `confirmation_id` gate + ART-IX audit entry; export bundle written atomically to configured VCS root (011-document-export)
- Python 3.11+ + `prometheus-client>=0.17` (metrics scrape endpoint); new `adp.telemetry` package with canonical span attribute constants, `TraceIdFilter` logging filter, `ai_step_span()` context manager, `ContextVar` trace ID carrier; `GET /health` + `GET /metrics` endpoints; QG-08 no-leak test enforced in CI; existing ADP-SPEC-006/007/008 telemetry.py files normalized to use `adp.telemetry.contract` constants (012-observability-telemetry)
- TypeScript 5.x + `@playwright/test` v1.47+ (E2E test runner); `playwright` browser lib (already in stack); Chromium browser; 18 API tests (no browser, no DB) + 4 browser tests (Chromium, route-mocked); `ADP_API_URL` and `ADP_WEB_URL` env vars control targets; `npm run test:e2e:api` for CI (013-playwright-e2e)
- Python 3.11+ + `psycopg2-binary` (synchronous driver for Alembic migrations; asyncpg used at runtime); `alembic.ini` at project root with `sqlalchemy.url` for direct CLI use; `ADP_DATABASE_URL` env var for runtime (DB setup)

- Python 3.11+ + Pydantic v2 (entity definitions and schema emission), jsonschema 4.x (schema validation in tests) (001-canonical-data-model)

## Project Structure

```text
src/adp/          # Python backend (all modules)
tests/            # pytest unit, contract, integration tests
web/              # TypeScript/React C4 canvas (Vite)
specs/            # Speckit spec/plan/tasks per feature (001–013)
generated/        # Generated JSON Schema (do not edit by hand)
```

## Commands

```bash
# Backend
pip install -e ".[dev]"                          # install with dev deps
pytest tests/ --ignore=tests/integration -q      # unit + contract tests (no DB needed)
pytest tests/integration/                        # integration tests (requires PostgreSQL)
ruff check src/                                  # lint
mypy src/                                        # type check
adp-generate                                     # regenerate JSON schemas
adp-generate --check                             # drift gate (must exit 0 in CI)
alembic upgrade head                             # run DB migrations (from project root)
alembic current                                  # check migration state

# Web canvas
cd web && npm install
cd web && npm run dev                            # Vite dev server on :5173
cd web && npm run test:run                       # Vitest unit + component tests
cd web && npm run test:e2e:api                   # Playwright API E2E (requires API server)
cd web && ADP_WEB_URL=http://localhost:5173 npm run test:e2e  # full E2E including browser

# Run the API server
export ADP_DATABASE_URL="postgresql+asyncpg://adp_user:adp_pass@127.0.0.1:5432/adp"
uvicorn adp.api.app:app --host 0.0.0.0 --port 8001 --reload
```

## Code Style

Python 3.12 (runtime) targeting 3.11+ compatibility; follow standard PEP 8 conventions enforced by ruff.

## Recent Changes
- 013-playwright-e2e: Added `@playwright/test` v1.47+; Chromium browser; 22 E2E tests (18 API + 4 browser); `npm run test:e2e:api` CI command; key fix: use regex `/\/api\/v1\//` not glob for Playwright route mocking to avoid intercepting Vite source files
- 012-observability-telemetry: Added `prometheus-client>=0.17`; `adp.telemetry` package; QG-08/10/11 CI gates; normalized existing telemetry files to `adp.telemetry.contract` constants
- 011-document-export: Added `pyyaml>=6.0`; `adp.docs` + `adp.export` packages; GET /document, /traceability, /views, POST /export, POST /import endpoints; ART-VIII `confirmation_id` gate
- 010-locked-theme-rendering: `cairosvg>=2.7`; locked theme v1.0.1 (`#2874A6` container fill, WCAG AA); `adp-generate` extended to emit `c4-theme.schema.json`
- DB setup: PostgreSQL 16.14 + pgvector 0.6.0 running natively; `psycopg2-binary` for Alembic sync migrations; `alembic.ini` updated with `sqlalchemy.url`; async/sync fix: `DesignStore.get()` is async, orchestrators now use `arender()` not `render()`


<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
