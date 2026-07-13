# ADP Runbook

Operational procedures for the AI-Assisted Architecture Design Platform.

> **Port**: ADP API runs on **:8001**. Port 8000 may be occupied by other services.

---

## Health checks

```bash
# Liveness
curl http://localhost:8001/health
# {"status": "healthy", "reason": null, "version": "0.1.0"}

# Prometheus metrics
curl http://localhost:8001/metrics | grep adp_
```

Key metrics to watch:

| Metric | Type | Alert threshold |
|---|---|---|
| `adp_request_total` | counter | — (baseline) |
| `adp_error_total` | counter | > 5% of requests |
| `adp_request_latency_seconds` (p95) | histogram | > 5s |
| `adp_active_requests` | gauge | > 50 (saturation) |
| `adp_ai_estimated_cost_usd_total` | counter | Watch for cost spikes |

---

## Starting the stack

### PostgreSQL (one-time setup)

```bash
# Create cluster if not exists
sudo pg_createcluster 16 main --start

# Create database and user
sudo -u postgres psql <<'SQL'
CREATE USER adp_user WITH PASSWORD 'adp_pass';
CREATE DATABASE adp OWNER adp_user;
GRANT ALL PRIVILEGES ON DATABASE adp TO adp_user;
SQL

# Install pgvector extension
sudo apt-get install -y postgresql-16-pgvector
sudo -u postgres psql -d adp -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Run migrations (from project root)
alembic upgrade head
```

### Backend API

```bash
cd /home/jmuir/projects/ADP
export ADP_DATABASE_URL="postgresql+asyncpg://adp_user:adp_pass@127.0.0.1:5432/adp"
export ADP_LLM_ENDPOINT="https://api.anthropic.com"
export ADP_LLM_API_KEY="sk-..."   # Never logged; never in spans
export ADP_LLM_MODEL="claude-sonnet-4-6"   # Optional default model
# Optional — enable Keycloak OIDC auth (ADP-SPEC-026):
# export ADP_AUTH_ENABLED=true
# export ADP_KEYCLOAK_ISSUER="http://127.0.0.1:8080/realms/ADPRealm"
# export ADP_KEYCLOAK_CLIENT_ID="adp-frontend"
uvicorn adp.api.app:app --host 0.0.0.0 --port 8001 --reload
```

When `ADP_AUTH_ENABLED=true`, every `/api/v1/*` route requires a valid Keycloak
bearer token; roles on the token drive RBAC. Leave it unset (or `false`) for
local development without a Keycloak instance.

### Web canvas (development)

```bash
cd web
npm run dev
# → http://localhost:5173/designs/DESIGN-001
```

### Web canvas (production build)

```bash
cd web
npm run build
# Serve dist/ with any static file server
```

---

## Database operations

### Run migrations

```bash
# From the project root (alembic.ini is at root, not in src/)
alembic upgrade head
```

### Check current migration state

```bash
alembic current
```

### View migration history

```bash
alembic history
```

Migration chain (as of ADP-SPEC-036): `001` initial schema → `002` knowledge →
`003` operations → `004` LLM reasoning log → `005` element technology tags →
`006` design lifecycle → `007` business architecture → `008` business
traceability → `009` business domain registry → `010` application registry
(`head`).

### Rollback one step

```bash
alembic downgrade -1
```

### Regenerate JSON Schemas after model changes

```bash
# Always run after editing src/adp/models.py or src/adp/theme/models.py
adp-generate

# Verify no drift (CI gate — must exit 0 before any PR)
adp-generate --check
```

---

## Knowledge base

### Reindex from all configured sources

```bash
adp-reindex
```

This ingests content from configured Git repositories and the design store into the pgvector knowledge base. Requires PostgreSQL 15+ with the `pgvector` extension (no Docker needed — runs natively).

### Validate a design JSON file

```bash
adp-generate --validate path/to/design.json
# ✓ path/to/design.json is schema-valid and referentially intact.
```

---

## Working with designs

### Save a design to the database

The `/api/v1/designs/import` endpoint validates and stores a design:

```bash
curl -X POST http://localhost:8001/api/v1/designs/import \
  -H "Content-Type: application/json" \
  -d "{\"model_json\": $(cat path/to/design.json | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))')}"
```

### Generate a stakeholder document

```bash
curl http://localhost:8001/api/v1/designs/DESIGN-001/document \
  > design-001.md
```

### Generate all three C4 level renders

```bash
curl http://localhost:8001/api/v1/designs/DESIGN-001/views \
  | python3 -c "
import sys, json, base64
r = json.load(sys.stdin)
for level in ('context', 'container', 'component'):
    open(f'design-001-{level}.svg', 'w').write(r[level]['svg'])
    open(f'design-001-{level}.png', 'wb').write(base64.b64decode(r[level]['png_base64']))
    print(f'Saved {level}')
"
```

### Render a specific C4 level

```bash
curl -X POST http://localhost:8001/api/v1/designs/DESIGN-001/render \
  -H "Content-Type: application/json" \
  -d '{"level": "container"}' \
  | python3 -c "import sys,json,base64; r=json.load(sys.stdin); open('out.svg','w').write(r['svg']); print('DSL:', r['dsl'][:100])"
```

### Export a design to version control

Export uses ART-VIII: `confirmation_id` must be a non-empty string in the request body.

```bash
# Export with a confirmation ID (any non-empty string for v1)
curl -X POST http://localhost:8001/api/v1/designs/DESIGN-001/export \
  -H "Content-Type: application/json" \
  -d '{"confirmation_id": "CONFIRMED-BY-USER", "export_root": "/srv/architecture-exports"}'

# Commit the export
cd /srv/architecture-exports
git add exports/DESIGN-001/
git commit -m "ADP export: DESIGN-001 ($(date -u +%Y-%m-%dT%H:%M:%SZ))"
```

### Re-import an exported model

```bash
curl -X POST http://localhost:8001/api/v1/designs/import \
  -H "Content-Type: application/json" \
  -d "{\"model_json\": $(cat /srv/architecture-exports/exports/DESIGN-001/v1/model.json | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))')}"
```

---

## Request tracing

Every request gets a trace ID. Inject your own to correlate across systems:

```bash
curl http://localhost:8001/api/v1/designs/DESIGN-001/document \
  -H "X-Trace-ID: incident-2026-07-02-001"
# Response header: X-Trace-ID: incident-2026-07-02-001
```

All log lines for that request carry `"trace_id": "incident-2026-07-02-001"`.

### Finding a request in logs

```bash
# If logs are JSON-streamed to a file:
grep '"trace_id": "incident-2026-07-02-001"' /var/log/adp/app.log | jq .

# Check for errors in a trace:
grep '"trace_id": "incident-2026-07-02-001"' /var/log/adp/app.log | jq 'select(.level == "ERROR")'
```

---

## AI pipeline operations

### Check what a recommendation span looks like

All AI step spans carry these attributes (verifiable in your OTel backend):

```
adp.step_name            "retrieve" | "generate" | "analyze_tradeoffs" | "rank" | ...
adp.input_tokens         1240
adp.output_tokens        380
adp.estimated_cost_usd   0.00312
adp.latency_ms           1840
adp.knowledge_item_ids   '["KI-001", "KI-003"]'
adp.design_id            "DESIGN-001"
adp.operation_id         "OP-042"
```

### Check the locked C4 theme

```bash
curl http://localhost:8001/api/v1/theme/c4 | python3 -m json.tool
```

Current baseline theme version: `1.0.1` (container fill `#2874A6`, WCAG AA compliant).

---

## Portfolio & governance reporting

Portfolio analysis (ADP-SPEC-031) and governance reporting (ADP-SPEC-032) read
directly from the design store, technology tags, lifecycle status, and audit
trail — no separate ingestion step is required.

```bash
# Technology footprint across the portfolio
curl "http://localhost:8001/api/v1/portfolio/technologies" | python3 -m json.tool

# Portfolio summary (counts by lifecycle, technology, etc.)
curl "http://localhost:8001/api/v1/portfolio/summary" | python3 -m json.tool

# Governance dashboard status
curl "http://localhost:8001/api/v1/governance/status" | python3 -m json.tool

# Export governance activity as CSV
curl "http://localhost:8001/api/v1/governance/activity/export" > governance-activity.csv
```

---

## Business architecture & application registry

Capabilities, value streams, domains (ADP-SPEC-033/034/035) and the application
registry (ADP-SPEC-036) live in dedicated relational tables (migrations 007–010),
linked to designs via join tables for traceability.

```bash
# Capability model
curl "http://localhost:8001/api/v1/business/capabilities" | python3 -m json.tool

# Designs realizing a capability (traceability)
curl "http://localhost:8001/api/v1/business/capabilities/CAP-001/designs" | python3 -m json.tool

# Full business context for a design
curl "http://localhost:8001/api/v1/business/designs/DESIGN-001/context" | python3 -m json.tool

# Application registry
curl "http://localhost:8001/api/v1/applications" | python3 -m json.tool
```

If these tables are empty or missing, confirm migrations are applied:

```bash
alembic current   # should report 010 (head)
```

---

## CALM export

Export a design as a FINOS CALM document (ADP-SPEC-021):

```bash
curl "http://localhost:8001/api/v1/designs/DESIGN-001/export/calm" > design-001.calm.json
```

---

## Running tests

```bash
# Unit + contract tests (no DB required)
pytest tests/ --ignore=tests/integration -q

# QG-08 no-leak CI gate (blocking)
pytest tests/unit/test_no_sensitive_data.py -v

# QG-10 trace ID in logs (blocking)
pytest tests/unit/test_trace_id_context.py -v

# QG-11 AI step span attributes (blocking)
pytest tests/unit/test_ai_step_span.py -v

# Integration tests (requires PostgreSQL 16 + pgvector)
pytest tests/integration/ -v

# TypeScript unit + component tests (Vitest)
cd web && npm run test:run

# Playwright E2E — API tests (no browser; requires API server on :8001)
cd web && ADP_API_URL=http://localhost:8001 npm run test:e2e:api

# Playwright E2E — full suite including browser tests
cd web && ADP_API_URL=http://localhost:8001 ADP_WEB_URL=http://localhost:5173 npm run test:e2e
```

Current test count: **574 Python** unit + contract + **132 Python** integration (706 total across 72 files) + **~59 TypeScript** (Vitest) + **45 Playwright E2E** (all passing).

---

## Common issues

### `adp-generate --check` exits non-zero

The committed JSON Schema is out of sync with `models.py` or `LockedTheme`. Run:

```bash
adp-generate
git add generated/architecture-description.schema.json src/adp/theme/c4-theme.schema.json
git commit -m "chore: regenerate schemas after model change"
```

### `cairosvg` fails with "cannot load library 'libcairo'"

Install the system library:

```bash
sudo apt-get install -y libcairo2-dev
pip install cairosvg --break-system-packages
```

### 409 Conflict on design update

Two clients tried to update the same design version simultaneously. The canvas shows: "Design updated by another user. Reload to see the latest version." Click **Reload**.

### Export returns 409 "directory already exists"

The design version has already been exported at that path. Bump the design version number before re-exporting, or use a different `export_root`.

### Import fails with schema version mismatch

```
{"detail": "Schema version '2.0.0' is not supported; current: '1.0.0'"}
```

The exported file was produced by a newer ADP version. Re-export from an instance running schema `1.0.0`.

### `sentence-transformers` not installed (knowledge reindex)

The self-hosted embedding model requires ~300MB. Knowledge retrieval falls back to keyword-only search without it:

```bash
pip install sentence-transformers --break-system-packages
```

### DB-backed endpoints return 503

`ADP_DATABASE_URL` is not set. Export it before starting the server:

```bash
export ADP_DATABASE_URL="postgresql+asyncpg://adp_user:adp_pass@127.0.0.1:5432/adp"
```

### Playwright route mocking intercepts Vite source files

Use regex `/\/api\/v1\//` instead of glob `**/api/**` in `page.route()`. The glob matches Vite source paths like `/src/api/designs.ts` and corrupts the module system.

---

## Security: what is never logged or stored in spans

Per FR-006 (ADP-SPEC-012 / QG-08):

- `ADP_LLM_API_KEY` — never in logs, spans, or any output
- Bearer tokens / authorization headers — only `auth_present: true` is logged
- Design content (element names, requirement text, AI prompt/response text) — only IDs and metadata
- Source text submitted for requirements intake — deleted from memory after extraction

The QG-08 CI gate (`tests/unit/test_no_sensitive_data.py`) verifies this on every PR.

---

## Audit trail

Every consequential model mutation is recorded in `design.audit_log` (append-only per ART-IX):

```bash
python3 -c "
import asyncio, sys
sys.path.insert(0, 'src')
from adp.store.store import DesignStore

async def show():
    store = DesignStore('postgresql+asyncpg://adp_user:adp_pass@127.0.0.1:5432/adp')
    design = await store.get('DESIGN-001')
    for entry in design.audit_log:
        print(f\"{entry.id}: {entry.actor} → {entry.action} ({entry.timestamp})\")

asyncio.run(show())
"
```

Audit entries are enforced append-only at the database level by the PostgreSQL trigger `deny_audit_mutation()`.

---

## Theme management

### View current theme

```bash
curl http://localhost:8001/api/v1/theme/c4 | python3 -m json.tool
```

### Update the theme (Enterprise Architect only)

1. Edit `src/adp/theme/c4-theme.json`
2. Bump the `version` field (semantic versioning)
3. Run `adp-generate --check` to verify schema is still valid
4. Run `pytest tests/unit/test_theme_contrast.py` to verify WCAG AA compliance
5. Commit as a PR — the diff IS the change record (FR-005)

### Verify WCAG contrast ratios

```bash
python3 -c "
from adp.theme.loader import ThemeLoader
from adp.theme.contrast import compute_contrast_ratio
theme = ThemeLoader().load()
for kind, style in theme.styles.items():
    ratio = compute_contrast_ratio(style.color, style.fill)
    status = '✅ AA' if ratio >= 4.5 else '❌ FAIL'
    print(f'{kind}: {ratio:.2f}:1 {status}  ({style.color} on {style.fill})')
"
```

---

## Production Deployment

### Prerequisites

- Docker Engine 24+ and Docker Compose v2+
- A server with at least 2 GB RAM and 10 GB disk
- An Anthropic API key (or compatible LLM endpoint)

### 1. First-Time Setup

```bash
# Clone the repository
git clone <your-repo-url> adp && cd adp

# Copy the example env file and fill in your values
cp .env.example .env
# Edit .env — set POSTGRES_PASSWORD and ADP_LLM_API_KEY at minimum

# Start the database
docker compose up -d db

# Wait for it to be healthy, then run migrations
docker compose run --rm api alembic upgrade head

# Optional: seed the knowledge base with industry best practices
docker compose run --rm api python scripts/seed_knowledge.py
```

### 2. Start ADP

```bash
docker compose up -d
```

Verify it's running:
```bash
curl http://localhost:8001/health
# → {"status": "healthy", ...}
```

Open `http://localhost:8001` in a browser to access the UI.

### 3. Upgrade Procedure

```bash
git pull
docker compose build
docker compose run --rm api alembic upgrade head   # apply any new DB migrations
docker compose up -d
```

### 4. Scale Workers

Edit `.env`:
```
ADP_WORKERS=4
```

Then restart:
```bash
docker compose up -d
```

### 5. Troubleshooting

**Check logs**:
```bash
docker compose logs api --tail=100
docker compose logs db --tail=50
```

**Database connection failures**:
```bash
# Verify DB is healthy
docker compose ps db
# Check connectivity
docker compose exec db psql -U adp_user -d adp -c "\dt"
```

**Operations not persisting across restarts**:
```bash
# Verify the operations table exists (added in migration 003)
docker compose exec db psql -U adp_user -d adp -c "\d operations"
```

**Port conflict**:
Edit `.env` and set `ADP_PORT=8002` (or another available port), then `docker compose up -d`.
