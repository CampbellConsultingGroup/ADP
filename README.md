# ADP — AI-Assisted Architecture Design Platform

ADP is a platform that helps enterprise architecture teams produce consistent, governed, AI-assisted architecture designs. Every design is a typed, schema-validated canonical model stored in a PostgreSQL database. AI recommendations and validation verdicts are grounded in an organizational knowledge base. Every output — documents, diagrams, exports — is a generated projection of the model, never a hand-authored artifact.

## What it does

| Capability | Entry point |
|---|---|
| Canonical data model | `adp.models.ArchitectureDescription` |
| Requirements intake (LLM-assisted) | `adp.intake` (CLI / direct; HTTP route not yet wired) |
| Knowledge retrieval (hybrid search + pgvector) | `adp.knowledge.retrieval` |
| AI architecture recommendations (LangGraph) | `adp.recommendation` (CLI / direct; HTTP route not yet wired) |
| LLM-as-Judge validation (fan-out critics) | `adp.validation` (CLI / direct; HTTP route not yet wired) |
| C4 diagram workspace (React + React Flow v12) | `web/` → `http://localhost:5173/designs/{id}` |
| Locked visual theme + diagram rendering | `POST /api/v1/designs/{id}/render` |
| Document + traceability generation | `GET /api/v1/designs/{id}/document` |
| Durable export to version control | `POST /api/v1/designs/{id}/export` |
| Observability (OTel spans + Prometheus) | `GET /health`, `GET /metrics` |
| End-to-end tests | `web/tests/e2e/` (Playwright; 22 tests) |

## Architecture overview

```
web/ (TypeScript/React)
  └── Canvas UI (React Flow v12) ──► API ──► src/adp/
                                              ├── models.py          # Canonical data model (Pydantic v2)
                                              ├── api/               # FastAPI application
                                              │   ├── deps.py        # Shared DB dependency
                                              │   └── routers/       # HTTP endpoints
                                              ├── store/             # PostgreSQL + SQLAlchemy 2 async
                                              ├── authz/             # RBAC + action types
                                              ├── audit/             # Append-only audit trail
                                              ├── knowledge/         # pgvector knowledge base
                                              ├── intake/            # Requirements extraction (LLM)
                                              ├── recommendation/    # LangGraph recommendation pipeline
                                              ├── validation/        # LLM-as-Judge + deterministic gate
                                              ├── renderer/          # DSL + SVG + PNG generation
                                              ├── theme/             # Locked C4 visual theme
                                              ├── docs/              # Document + traceability generation
                                              ├── export/            # VCS export bundle + importer
                                              └── telemetry/         # OTel spans + Prometheus metrics
```

## Quick start

### Prerequisites

- Python 3.11+ (runtime: 3.12.3)
- PostgreSQL 15+ with `pgvector` extension
- Node.js 24+ (for the C4 canvas web application)
- `libcairo2` system library (for SVG→PNG rendering via `cairosvg`)
- `psycopg2-binary` (for Alembic sync migrations)

```bash
# Python backend
pip install -e ".[dev]"
pip install psycopg2-binary --break-system-packages

# Set up PostgreSQL (one-time)
sudo -u postgres psql -c "CREATE USER adp_user WITH PASSWORD 'adp_pass';"
sudo -u postgres psql -c "CREATE DATABASE adp OWNER adp_user;"
sudo apt-get install -y postgresql-16-pgvector
sudo -u postgres psql -d adp -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Run database migrations (from project root)
alembic upgrade head

# Verify schema is up to date
adp-generate --check

# Run tests (no DB required for unit/contract)
pytest tests/ --ignore=tests/integration -q

# Web canvas
cd web && npm install && npm run dev
```

### Running the API server

```bash
export ADP_DATABASE_URL="postgresql+asyncpg://adp_user:adp_pass@127.0.0.1:5432/adp"
uvicorn adp.api.app:app --host 0.0.0.0 --port 8001
```

> **Note**: Port 8001 is the standard ADP port. Port 8000 may be occupied by other services.

### Environment variables

| Variable | Required | Description |
|---|---|---|
| `ADP_DATABASE_URL` | Yes | PostgreSQL async connection string (`postgresql+asyncpg://...`) |
| `ADP_LLM_ENDPOINT` | Yes (AI features) | LLM API base URL |
| `ADP_LLM_API_KEY` | Yes (AI features) | LLM API key — **never logged or stored in spans** |

## Implemented API endpoints

> Endpoints marked *(not yet wired)* have Python implementations but no registered FastAPI route.

### Currently active

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Service liveness |
| `GET` | `/metrics` | Prometheus scrape |
| `GET` | `/api/v1/theme/c4` | Locked C4 visual theme |
| `GET` | `/api/v1/designs/{id}/layout/{level}` | Element canvas positions |
| `PUT` | `/api/v1/designs/{id}/layout/{level}` | Save element positions |
| `POST` | `/api/v1/designs/{id}/render` | Render to DSL + SVG + PNG |
| `GET` | `/api/v1/designs/{id}/document` | Stakeholder Markdown document |
| `GET` | `/api/v1/designs/{id}/traceability` | Requirements traceability matrix |
| `GET` | `/api/v1/designs/{id}/views` | All three C4 level renders |
| `POST` | `/api/v1/designs/{id}/export` | Export bundle to VCS (requires `confirmation_id`) |
| `POST` | `/api/v1/designs/import` | Re-import an exported `model.json` |

### Planned (Python module exists; HTTP route not yet registered)

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/designs/{id}` | Fetch a design from store |
| `PUT` | `/api/v1/designs/{id}` | Update a design (optimistic concurrency) |
| `POST` | `/api/v1/designs/{id}/intake` | Extract requirements from text (LLM) |
| `POST` | `/api/v1/designs/{id}/recommend` | Generate architecture recommendations |
| `POST` | `/api/v1/designs/{id}/validate` | Run LLM-as-Judge validation |

## Data model

The canonical unit is `ArchitectureDescription` (schema version `1.0.0`):

```python
ArchitectureDescription
├── id: str                    # e.g. "DESIGN-001"
├── title: str
├── elements: list[Element]    # Nodes (person, system, container, component)
├── relationships: list[Relationship]
├── requirements: list[Requirement]
├── options: list[SolutionOption]   # AI-generated recommendations
├── findings: list[Finding]         # Validation critic outputs
├── verdicts: list[Verdict]         # Aggregated validation results
└── audit_log: list[AuditEntry]    # Append-only mutation history
```

JSON Schema: `generated/architecture-description.schema.json`

## Roles and permissions

| Role | Capabilities |
|---|---|
| `enterprise_architect` | All actions including export and amend theme |
| `solution_architect` | Design CRUD, AI operations, export |
| `technical_architect` | Design CRUD, AI operations (no export, no verdict override) |
| `reviewer` | Read + override verdict + add finding |

## Development commands

```bash
# Regenerate JSON Schemas from models.py and LockedTheme
adp-generate

# Verify no schema drift (CI gate — must exit 0)
adp-generate --check

# Validate a JSON file against the canonical schema
adp-generate --validate path/to/design.json

# Reindex the knowledge base (requires PostgreSQL with pgvector)
adp-reindex

# Lint
ruff check src/

# Type check
mypy src/

# Full test suite — unit + contract (no DB required)
pytest tests/ --ignore=tests/integration -q

# With coverage
pytest tests/ --ignore=tests/integration --cov=adp --cov-report=term-missing

# Integration tests (requires PostgreSQL)
pytest tests/integration/ -v

# Playwright E2E — API tests (requires API server on :8001, no DB needed)
cd web && ADP_API_URL=http://localhost:8001 npm run test:e2e:api

# Playwright E2E — full suite including browser (requires Vite on :5173)
cd web && ADP_API_URL=http://localhost:8001 ADP_WEB_URL=http://localhost:5173 npm run test:e2e
```

## Project conventions

- **Spec-driven**: every feature has a spec in `specs/NNN-feature-name/` before any code
- **TDD**: tests committed before implementation; all tests must pass before merge
- **No content in logs or spans**: design descriptions and AI prompts are organizational IP; only IDs, counts, and latencies appear in telemetry (QG-08)
- **Canonical model is authoritative**: diagrams and documents are projections of the model, never primary records (ART-II)
- **Locked visual theme**: no per-element or per-diagram style overrides (ART-XII); container fill `#2874A6` (v1.0.1, WCAG AA)
- **Human-in-the-loop for consequential actions**: export requires a non-empty `confirmation_id` in the request body (ART-VIII)
- **Async store**: `DesignStore.get()` and `save()` are async; orchestrators must `await` them

## Specs implemented

| Spec | Branch | What it built |
|---|---|---|
| ADP-SPEC-001 | `001-canonical-data-model` | Pydantic v2 model + JSON Schema generator |
| ADP-SPEC-002 | `002-design-store` | PostgreSQL persistence (SQLAlchemy 2 async + Alembic) |
| ADP-SPEC-003 | `003-platform-api` | FastAPI application factory + auth middleware |
| ADP-SPEC-004 | `004-identity-authz` | RBAC + append-only audit trail |
| ADP-SPEC-005 | `005-knowledge-retrieval` | pgvector knowledge base + hybrid search |
| ADP-SPEC-006 | `006-requirements-intake` | LLM requirements extraction (LangGraph) |
| ADP-SPEC-007 | `007-recommendation-engine` | LangGraph recommendation pipeline |
| ADP-SPEC-008 | `008-llm-as-judge` | LLM-as-Judge validation + deterministic gate |
| ADP-SPEC-009 | `009-c4-workspace` | C4 canvas web app (React + React Flow v12) |
| ADP-SPEC-010 | `010-locked-theme-rendering` | Locked C4 theme (v1.0.1) + DSL/SVG/PNG renderer |
| ADP-SPEC-011 | `011-document-export` | Document generation + VCS export bundle |
| ADP-SPEC-012 | `012-observability-telemetry` | OTel spans + Prometheus metrics + QG-08/10/11 CI gates |
| ADP-SPEC-013 | `013-playwright-e2e` | Playwright E2E suite (18 API + 4 browser tests) |
