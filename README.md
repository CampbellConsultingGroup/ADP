# ADP — AI-Assisted Architecture Design Platform

ADP is a platform that helps enterprise architecture teams produce consistent, governed, AI-assisted architecture designs. Every design is a typed, schema-validated canonical model stored in a PostgreSQL database. AI recommendations and validation verdicts are grounded in an organizational knowledge base. Every output — documents, diagrams, exports — is a generated projection of the model, never a hand-authored artifact.

## What it does

| Capability | Entry point |
|---|---|
| Canonical data model | `adp.models.ArchitectureDescription` |
| Requirements intake (LLM-assisted) | `POST /api/v1/designs/{id}/intake` |
| Knowledge retrieval (hybrid search + pgvector) | `adp.knowledge.retrieval` |
| AI architecture recommendations (LangGraph) | `POST /api/v1/designs/{id}/recommend` |
| LLM-as-Judge validation (fan-out critics) | `POST /api/v1/designs/{id}/validate` |
| C4 diagram workspace (React + React Flow v12) | `web/` |
| Locked visual theme + diagram rendering | `POST /api/v1/designs/{id}/render` |
| Document + traceability generation | `GET /api/v1/designs/{id}/document` |
| Durable export to version control | `POST /api/v1/designs/{id}/export` |
| Observability (OTel spans + Prometheus) | `GET /health`, `GET /metrics` |

## Architecture overview

```
web/ (TypeScript/React)
  └── Canvas UI (React Flow v12) ──► API ──► src/adp/
                                              ├── models.py          # Canonical data model (Pydantic v2)
                                              ├── api/               # FastAPI application
                                              │   └── routers/       # All HTTP endpoints
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

- Python 3.11+
- PostgreSQL 15+ with `pgvector` extension (for knowledge base and design store)
- Node.js 24+ (for the C4 canvas web application)
- `libcairo2` system library (for SVG→PNG rendering via `cairosvg`)

```bash
# Python backend
pip install -e ".[dev]"

# Verify schema is up to date
adp-generate --check

# Run tests (no Docker required for unit/contract tests)
pytest tests/ --ignore=tests/integration

# Web canvas
cd web && npm install && npm run dev
```

### Running the API server

```bash
uvicorn adp.api.app:app --host 0.0.0.0 --port 8000 --reload
```

### Environment variables

| Variable | Required | Description |
|---|---|---|
| `ADP_DATABASE_URL` | Yes (integration) | PostgreSQL connection string |
| `ADP_LLM_ENDPOINT` | Yes (AI features) | LLM API base URL |
| `ADP_LLM_API_KEY` | Yes (AI features) | LLM API key — **never logged or stored in spans** |

## API endpoints

### Core model

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/designs/{id}` | Fetch a design |
| `PUT` | `/api/v1/designs/{id}` | Update a design (optimistic concurrency) |

### AI pipeline

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/designs/{id}/intake` | Extract requirements from text (LLM) |
| `POST` | `/api/v1/designs/{id}/recommend` | Generate architecture recommendations |
| `POST` | `/api/v1/designs/{id}/validate` | Run LLM-as-Judge validation |

### Canvas and layout

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/designs/{id}/layout/{level}` | Get element positions |
| `PUT` | `/api/v1/designs/{id}/layout/{level}` | Save element positions |

### Document generation

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/designs/{id}/document` | Generate stakeholder Markdown document |
| `GET` | `/api/v1/designs/{id}/traceability` | Generate requirements traceability matrix |
| `GET` | `/api/v1/designs/{id}/views` | All three C4 level renders (context/container/component) |
| `POST` | `/api/v1/designs/{id}/render` | Render a specific C4 level (DSL + SVG + PNG) |

### Export and import

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/designs/{id}/export` | Export bundle to VCS (requires confirmation) |
| `POST` | `/api/v1/designs/import` | Re-import an exported `model.json` |

### Theme

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/theme/c4` | Fetch the locked C4 visual theme |

### Observability

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Service liveness (`{"status": "healthy"}`) |
| `GET` | `/metrics` | Prometheus metrics scrape |

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
| `technical_architect` | Design CRUD, AI operations (no export, no override) |
| `reviewer` | Read + override verdict + add finding |

## Development commands

```bash
# Regenerate JSON Schema from models.py
adp-generate

# Verify no schema drift (CI gate)
adp-generate --check

# Validate a JSON file against the schema
adp-generate --validate path/to/design.json

# Reindex the knowledge base
adp-reindex

# Lint
ruff check src/

# Type check
mypy src/

# Full test suite (unit + contract)
pytest tests/ --ignore=tests/integration -q

# With coverage
pytest tests/ --ignore=tests/integration --cov=adp --cov-report=term-missing
```

## Project conventions

- **Spec-driven**: every feature has a spec in `specs/NNN-feature-name/` before any code
- **TDD**: tests committed before implementation; all tests must pass before merge
- **No content in logs or spans**: design descriptions and AI prompts are organizational IP; only IDs, counts, and latencies appear in telemetry (QG-08)
- **Canonical model is authoritative**: diagrams and documents are projections of the model, never primary records (ART-II)
- **Locked visual theme**: no per-element or per-diagram style overrides (ART-XII)
- **Human-in-the-loop for consequential actions**: recommendation acceptance, verdict override, and export require explicit human confirmation (ART-VIII)

## Specs implemented

| Spec | Branch | What it built |
|---|---|---|
| ADP-SPEC-001 | `001-canonical-data-model` | Pydantic v2 model + JSON Schema generator |
| ADP-SPEC-002 | `002-design-store` | PostgreSQL persistence (SQLAlchemy 2 async + Alembic) |
| ADP-SPEC-003 | `003-platform-api` | FastAPI REST API + auth middleware |
| ADP-SPEC-004 | `004-identity-authz` | RBAC + append-only audit trail |
| ADP-SPEC-005 | `005-knowledge-retrieval` | pgvector knowledge base + hybrid search |
| ADP-SPEC-006 | `006-requirements-intake` | LLM requirements extraction (LangGraph) |
| ADP-SPEC-007 | `007-recommendation-engine` | LangGraph recommendation pipeline |
| ADP-SPEC-008 | `008-llm-as-judge` | LLM-as-Judge validation + deterministic gate |
| ADP-SPEC-009 | `009-c4-workspace` | C4 canvas web app (React + React Flow v12) |
| ADP-SPEC-010 | `010-locked-theme-rendering` | Locked C4 theme + DSL/SVG/PNG renderer |
| ADP-SPEC-011 | `011-document-export` | Document generation + VCS export |
| ADP-SPEC-012 | `012-observability-telemetry` | OTel spans + Prometheus metrics + no-leak CI gates |
