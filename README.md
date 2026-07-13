# ADP — AI-Assisted Architecture Design Platform

ADP is a platform that helps enterprise architecture teams produce consistent, governed, AI-assisted architecture designs. Every design is a typed, schema-validated canonical model stored in a PostgreSQL database. AI recommendations and validation verdicts are grounded in an organizational knowledge base. Every output — documents, diagrams, exports — is a generated projection of the model, never a hand-authored artifact.

The platform now spans the full enterprise-architecture stack: business capabilities and value streams, a business domain registry, an application/integration registry, C4 solution designs, portfolio analysis, and governance reporting — all traceable back to the canonical model.

## What it does

| Capability | Entry point |
|---|---|
| Canonical data model | `adp.models.ArchitectureDescription` |
| Requirements intake (LLM-assisted) | `POST /api/v1/designs/{id}/intake` → `adp.intake` |
| Knowledge base management (hybrid search + pgvector) | `adp.knowledge`, `/api/v1/knowledge` |
| AI architecture recommendations (LangGraph) | `POST /api/v1/designs/{id}/recommend` → `adp.recommendation` |
| LLM-as-Judge validation (fan-out critics) | `adp.validation` (invoked within the recommendation pipeline) |
| Immutable LLM reasoning store | `adp.llm`, `/api/v1/reasoning` |
| C4 diagram workspace (React + React Flow v12) | `web/` → Canvas view |
| Locked visual theme + diagram rendering | `POST /api/v1/designs/{id}/render` |
| Document + traceability generation | `GET /api/v1/designs/{id}/document` |
| Durable export to version control | `POST /api/v1/designs/{id}/export` |
| CALM export / pattern import | `adp.calm`, `GET /api/v1/designs/{id}/export/calm` |
| Element technology tagging | `PUT /api/v1/designs/{id}/elements/{eid}/tags` |
| Design lifecycle management | `PATCH /api/v1/designs/{id}/lifecycle` |
| Portfolio analysis (technology footprint) | `/api/v1/portfolio` |
| Governance reporting dashboard | `/api/v1/governance` |
| Business architecture (capabilities, value streams, domains) | `adp.business`, `/api/v1/business` |
| Application & integration registry | `adp.application`, `/api/v1/applications` |
| Identity / authorization (Keycloak OIDC) | `adp.auth`, `adp.authz` |
| Observability (OTel spans + Prometheus) | `GET /health`, `GET /metrics` |
| End-to-end tests | `web/tests/e2e/` (Playwright) |

## Architecture overview

```
web/ (TypeScript/React — AppShell + views)
  Overview · Designs · Business · Applications · Portfolio ·
  Governance · Knowledge · Intake · Recommendations · Canvas
        │
        ▼
src/adp/
  ├── models.py          # Canonical data model (Pydantic v2)
  ├── api/               # FastAPI application factory
  │   ├── deps.py        # Shared DB dependency
  │   └── routers/       # HTTP endpoints (designs, intake, recommend, …)
  ├── store/             # PostgreSQL + SQLAlchemy 2 async + Alembic migrations
  ├── auth/              # Keycloak OIDC token validation + middleware
  ├── authz/             # RBAC + action types
  ├── audit/             # Append-only audit trail
  ├── knowledge/         # pgvector knowledge base + hybrid search
  ├── intake/            # Requirements extraction (LLM)
  ├── recommendation/    # LangGraph recommendation pipeline
  ├── validation/        # LLM-as-Judge + deterministic gate
  ├── llm/               # LLM client + immutable reasoning store
  ├── renderer/          # DSL + SVG + PNG generation
  ├── theme/             # Locked C4 visual theme
  ├── docs/              # Document + traceability generation
  ├── export/            # VCS export bundle + importer
  ├── calm/              # FINOS CALM export + pattern import
  ├── business/          # Capabilities, value streams, domains, traceability
  ├── application/       # Application / integration / technical-capability registry
  └── telemetry/         # OTel spans + Prometheus metrics
```

## Quick start

### Prerequisites

- Python 3.11+ (runtime: 3.12)
- PostgreSQL 16 with the `pgvector` extension
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
| `ADP_LLM_ENDPOINT` | Yes (AI features) | LLM API base URL (e.g. `https://api.anthropic.com`) |
| `ADP_LLM_API_KEY` | Yes (AI features) | LLM API key — **never logged or stored in spans** |
| `ADP_LLM_MODEL` | No | Default model for intake/validation (e.g. `claude-sonnet-4-6`) |
| `ADP_LLM_RECOMMENDATION_MODEL` | No | Override model for the recommendation pipeline |
| `ADP_AUTH_ENABLED` | No | Enable Keycloak OIDC auth (`true`/`false`; default off in dev) |
| `ADP_KEYCLOAK_ISSUER` | If auth enabled | OIDC issuer URL (e.g. `http://127.0.0.1:8080/realms/ADPRealm`) |
| `ADP_KEYCLOAK_CLIENT_ID` | If auth enabled | Expected token audience / client ID |
| `ADP_MAX_DESIGNS` | No | Cap on stored designs (default 1000) |
| `ADP_EMBEDDING_MODEL` / `ADP_EMBEDDING_DIM` | No | Knowledge-base embedding config |
| `ADP_GIT_REPO_URLS` / `ADP_GIT_LOCAL_CLONE_PATH` | No | Knowledge-base Git ingestion sources |

## API endpoints

All routes below are registered and active. Auth (when `ADP_AUTH_ENABLED=true`) is enforced via Keycloak OIDC bearer tokens; DB-backed routes return 503 if `ADP_DATABASE_URL` is unset.

### Platform & config

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Service liveness |
| `GET` | `/metrics` | Prometheus scrape |
| `GET` | `/api/v1/config/models` | Available LLM models |
| `GET` / `PUT` | `/api/v1/config/llm` | Read / update LLM configuration |
| `GET` | `/api/v1/theme/c4` | Locked C4 visual theme |

### Designs

| Method | Path | Description |
|---|---|---|
| `GET` / `POST` | `/api/v1/designs` | List / create designs |
| `POST` | `/api/v1/designs/import` | Re-import an exported `model.json` |
| `GET` | `/api/v1/designs/{id}` | Fetch a design |
| `GET` / `PUT` | `/api/v1/designs/{id}/layout/{level}` | Element canvas positions |
| `POST` | `/api/v1/designs/{id}/render` | Render to DSL + SVG + PNG |
| `GET` | `/api/v1/designs/{id}/document` | Stakeholder Markdown document |
| `GET` | `/api/v1/designs/{id}/traceability` | Requirements traceability matrix |
| `GET` | `/api/v1/designs/{id}/views` | All three C4 level renders |
| `POST` | `/api/v1/designs/{id}/export` | Export bundle to VCS (requires `confirmation_id`) |
| `GET` | `/api/v1/designs/{id}/export/calm` | FINOS CALM document export |
| `PATCH` | `/api/v1/designs/{id}/lifecycle` | Update lifecycle status + dates |
| `PUT` | `/api/v1/designs/{id}/elements/{eid}/tags` | Set element technology tags |

### Requirements intake (LLM)

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/designs/{id}/intake` | Extract requirements from text |
| `GET` | `/api/v1/designs/{id}/intake/{op_id}` | Poll intake operation status |
| `POST` | `/api/v1/designs/{id}/intake/{op_id}/proposals/{pid}/confirm` | Confirm a proposed requirement |
| `POST` | `/api/v1/designs/{id}/intake/{op_id}/proposals/{pid}/reject` | Reject a proposed requirement |
| `GET` / `POST` | `/api/v1/designs/{id}/requirements` | List / add confirmed requirements |

### Recommendations (LLM)

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/designs/{id}/recommend` | Generate architecture recommendations |
| `GET` | `/api/v1/designs/{id}/recommend/{op_id}` | Poll recommendation status |
| `POST` | `/api/v1/designs/{id}/recommend/{op_id}/options/{oid}/accept` | Accept an option (materializes elements) |
| `POST` | `/api/v1/designs/{id}/recommend/{op_id}/options/{oid}/reject` | Reject an option |

### Knowledge, reasoning, portfolio, governance

| Method | Path | Description |
|---|---|---|
| `GET`/`POST`/`PUT`/`DELETE` | `/api/v1/knowledge[/{id}]` | Knowledge base CRUD |
| `GET` | `/api/v1/reasoning` | Immutable LLM reasoning log |
| `GET` | `/api/v1/portfolio/{technologies,designs,search,summary}` | Technology footprint & portfolio analysis |
| `GET` | `/api/v1/governance/{status,exceptions,activity}` | Governance reporting |
| `GET` | `/api/v1/governance/activity/export` | CSV export of governance activity |

### Business architecture & application registry

| Method | Path | Description |
|---|---|---|
| `GET`/`POST`/`PUT`/`DELETE` | `/api/v1/business/capabilities[/{id}]` | Capability model |
| `GET`/`POST`/`PUT`/`DELETE` | `/api/v1/business/value-streams[/{id}]` | Value streams + stages |
| `GET`/`POST`/`PUT`/`DELETE` | `/api/v1/business/domains[/{id}]` | Business domain registry |
| `GET` | `/api/v1/business/capabilities/{id}/designs`, `/value-streams/{id}/designs`, `/designs/{id}/context` | Traceability |
| `GET`/`POST`/`PATCH`/`DELETE` | `/api/v1/applications[/{id}]` (+ link sub-resources) | Application registry |
| `GET`/`POST`/`PATCH`/`DELETE` | `/api/v1/technical-capabilities[/{id}]` | Technical capabilities |
| `GET`/`POST`/`PATCH`/`DELETE` | `/api/v1/integrations[/{id}]` | Application integrations |

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

Business architecture and the application registry are stored in dedicated relational tables (Alembic migrations 007–010), not in the JSONB model, and are linked to designs via join tables for traceability.

## Roles and permissions

| Role | Capabilities |
|---|---|
| `enterprise_architect` | All actions including export and amend theme |
| `solution_architect` | Design CRUD, AI operations, export |
| `technical_architect` | Design CRUD, AI operations (no export, no verdict override) |
| `reviewer` | Read + override verdict + add finding |

Roles come from Keycloak realm/client roles on the OIDC token when `ADP_AUTH_ENABLED=true`.

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

# Lint / type check
ruff check src/
mypy src/

# Full test suite — unit + contract (no DB required)
pytest tests/ --ignore=tests/integration -q

# Integration tests (requires PostgreSQL 16 + pgvector)
pytest tests/integration/ -v

# Web unit + component tests (Vitest)
cd web && npm run test:run

# Playwright E2E — API tests (requires API server on :8001, no DB needed)
cd web && ADP_API_URL=http://localhost:8001 npm run test:e2e:api

# Playwright E2E — full suite including browser (requires Vite on :5173)
cd web && ADP_API_URL=http://localhost:8001 ADP_WEB_URL=http://localhost:5173 npm run test:e2e
```

## Project conventions

- **Spec-driven**: every feature has a spec in `specs/NNN-feature-name/` before any code (see `docs/000-index.md`)
- **TDD**: tests committed before implementation; all tests must pass before merge
- **No content in logs or spans**: design descriptions and AI prompts are organizational IP; only IDs, counts, and latencies appear in telemetry (QG-08)
- **Canonical model is authoritative**: diagrams and documents are projections of the model, never primary records (ART-II)
- **Locked visual theme**: no per-element or per-diagram style overrides (ART-XII); container fill `#2874A6` (v1.0.1, WCAG AA)
- **Human-in-the-loop for consequential actions**: export requires a non-empty `confirmation_id` in the request body (ART-VIII)
- **Async store**: `DesignStore.get()` and `save()` are async; orchestrators must `await` them

## Specs implemented

The full specification set (36 specs) is indexed in `docs/000-index.md`. Foundational specs (001–012) have per-spec design docs in `docs/`; delivered feature specs 013–019 also have `docs/` docs; from 020 onward the canonical spec lives in `specs/NNN-<slug>/spec.md`.

| Spec | What it built |
|---|---|
| ADP-SPEC-001 … 012 | Canonical model, design store, platform API, RBAC/audit, knowledge base, intake, recommendation engine, LLM-as-Judge, C4 workspace, locked theme/renderer, document+export, observability |
| ADP-SPEC-013 | Playwright E2E suite |
| ADP-SPEC-014 | Requirements intake HTTP API + web screen |
| ADP-SPEC-015 | Anthropic LLM integration + model selection |
| ADP-SPEC-016 / 017 | Intake landing page + proposal status sync |
| ADP-SPEC-018 / 019 | Recommendation screen + learning/knowledge capture |
| ADP-SPEC-020 | Knowledge base management (CRUD) |
| ADP-SPEC-021 / 022 | CALM export + pattern import |
| ADP-SPEC-023 | Internal architecture consolidation |
| ADP-SPEC-024 | Persistent operation store |
| ADP-SPEC-025 | Multi-design UI + production readiness |
| ADP-SPEC-026 | Keycloak authentication |
| ADP-SPEC-027 / 028 | Immutable LLM reasoning store + reasoning display |
| ADP-SPEC-029 | Element technology tagging |
| ADP-SPEC-030 | Design lifecycle management |
| ADP-SPEC-031 | Portfolio analysis screen |
| ADP-SPEC-032 | Governance reporting dashboard |
| ADP-SPEC-033 | Business architecture — capability model + value streams |
| ADP-SPEC-034 | Business architecture traceability |
| ADP-SPEC-035 | Business domain registry + stage-capability mapping |
| ADP-SPEC-036 | Application registry |
