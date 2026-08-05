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
# Optional — continuous Business Architecture + Application registry export
# to versioned JSON files (ADP-SPEC-044 / ADP-SPEC-045). Unset (the default)
# disables BOTH features entirely — no background task runs for either,
# nothing is written to disk. One pair of env vars controls both; there is
# no separate on/off switch or interval for the Application registry export.
# export ADP_BUSINESS_ARCH_EXPORT_ROOT="/path/to/git-tracked/export/root"
# export ADP_BUSINESS_ARCH_EXPORT_INTERVAL_SECONDS=60
uvicorn adp.api.app:app --host 0.0.0.0 --port 8001 --reload
```

When `ADP_AUTH_ENABLED=true`, every `/api/v1/*` route requires a valid Keycloak
bearer token; roles on the token drive RBAC. Leave it unset (or `false`) for
local development without a Keycloak instance.

When `ADP_BUSINESS_ARCH_EXPORT_ROOT` is set, two independent background syncs
start:

- Business capabilities, value streams, value stream stages, and business
  domains are reconciled to one JSON file per entity under
  `$ADP_BUSINESS_ARCH_EXPORT_ROOT/business-architecture/` — see
  `specs/044-business-arch-export/contracts/exported-file-formats.md`.
- Applications, technical capabilities, transformation initiatives, and
  application-to-application integrations are reconciled to one JSON file per
  entity under `$ADP_BUSINESS_ARCH_EXPORT_ROOT/applications/` — see
  `specs/045-application-export/contracts/exported-file-formats.md`.
  **Unlike the Business Architecture export, this one includes an
  application's risk, cost, and governance data unredacted** — data the live
  API otherwise gates behind dedicated read permissions. If you enable this,
  treat `$ADP_BUSINESS_ARCH_EXPORT_ROOT` (and any git remote it's pushed to)
  as equivalently sensitive to those gated endpoints — this feature applies
  no access control of its own to the exported files.

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

Migration chain (as of ADP-SPEC-038): `001` initial schema → `002` knowledge →
`003` operations → `004` LLM reasoning log → `005` element technology tags →
`006` design lifecycle → `007` business architecture → `008` business
traceability → `009` business domain registry → `010` application registry →
`011` searchable items → `012` APM rationalization (US1) → `013` APM identity
(US2) → `014` APM risk & compliance (US3, sensitive) → `015` APM TCO/cost
(US4, sensitive) → `016` APM technical fit (US5) → `017` APM roadmap /
transformation initiatives (US6) → `018` APM ownership & governance (US7,
sensitive) → `019` APM quality & performance signals (US8, `head`).

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
alembic current   # should report 019 (head)
```

---

## Application portfolio management

Rationalization, identity, risk, cost, tech fit, roadmap, governance, and
quality signals (ADP-SPEC-038, US1–US8) live in dedicated 1:1/link tables
added by migrations 011–019. Risk, cost, and governance are sensitive
categories — reads require `READ_APPLICATION_{RISK,COST,GOVERNANCE}`
(`PERMISSIONS_VERSION` 1.4.0); a caller without the grant gets `403`.

```bash
# TIME rationalization quadrant (business_value × health_score)
curl "http://localhost:8001/api/v1/applications/rationalization" | python3 -m json.tool

# Risk & compliance register for one application (sensitive)
curl "http://localhost:8001/api/v1/applications/APP-001/risk" | python3 -m json.tool

# TCO rollup by business unit (sensitive)
curl "http://localhost:8001/api/v1/applications/cost/rollup" | python3 -m json.tool

# Decommission roadmap (Eliminate-classified or sunset/retired applications)
curl "http://localhost:8001/api/v1/applications/roadmap" | python3 -m json.tool

# Contracts renewing within 90 days (sensitive; ?within_days=N to override)
curl "http://localhost:8001/api/v1/applications/governance/renewals-soon" | python3 -m json.tool

# Quality & performance signals — advisory only, never overrides health_score
curl "http://localhost:8001/api/v1/applications/APP-001/quality" | python3 -m json.tool
```

If a sensitive-category read returns `403` for a role that should have
access, check `PERMISSIONS_VERSION` in `adp.authz.permissions` matches
`1.4.0` and that migrations 014/015/018 are applied.

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

Current test count: **659 Python** unit + contract + authz + **136 Python** integration (795 total across 90 files) + **75 TypeScript** (Vitest) + **45 Playwright E2E** (all passing).

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

---

## Azure Deployment (Container Apps)

The alternative to the single-VM docker-compose path above: Azure Container Apps
(API + Keycloak), Postgres Flexible Server + pgvector, Key Vault + managed
identity, ACR. All infra is Bicep under `infra/azure/`. Built and hardened
across ADP-fnv (epic) and ADP-cm9 (security review). This is `az`-CLI + Bicep,
not docker-compose.

**Scripts** (all in `infra/azure/`):
- `deploy.sh` — build images + deploy/update the whole environment
- `destroy.sh` — full teardown (deletes the resource group + purges Key Vault)
- `pause.sh` / `resume.sh` — stop/start compute without losing data (cheaper idle)

### Get the live site URL

The API app serves the built SPA from the same origin, so one URL is both UI and API:
```bash
az containerapp show -g adp-rg -n adp-api \
  --query "properties.configuration.ingress.fqdn" -o tsv
# → https://adp-api.<env-domain>.eastus2.azurecontainerapps.io
```

### Redeploy from scratch (after a destroy)

A brand-new environment is a **two-pass bootstrap** — this is expected, not a bug
(documented in `deploy.sh`'s own header):

```bash
cd infra/azure

# If a prior Key Vault was left soft-deleted (destroy.sh purges it, but a manual
# `az group delete` does NOT), the name is reserved and the deploy fails with
# "A vault with the same name already exists in deleted state". Purge it first:
az keyvault list-deleted --query "[?starts_with(name,'adp-kv-')].name" -o tsv
# az keyvault purge --name <adp-kv-...> --location eastus2

./deploy.sh   # PASS 1: creates RG/network/Postgres/Key Vault/ACR/Container Apps env.
              # Keycloak/API/jobs FAIL here — their Key Vault secrets don't exist
              # in the brand-new vault yet. This is expected.

./deploy.sh   # PASS 2: secrets are now seeded, so everything provisions. Also picks
              # up the real Container Apps env domain and bakes it into the API
              # image's VITE_KEYCLOAK_URL build-arg (see "frontend auth" below).
```

Then run the DB migrations (one-off Container Apps Job):
```bash
az containerapp job start -g adp-rg -n adp-migrate
```

### CRITICAL: patch the Keycloak realm for the new domain

Every fresh deploy gets a **new** env domain (e.g. `salmonfield-…`,
`lemondesert-…`). But `infra/keycloak/adp-realm.json`'s `redirectUris`/`webOrigins`
are pinned to a *specific* domain, and Keycloak's `--import-realm` uses
`IGNORE_EXISTING` — so the realm is imported once with whatever domain the JSON
had, and **login redirect validation will fail on the new domain** until patched.
Fix it via the `adp-keycloak-admin` job (built for exactly this, ADP-cm9):

```bash
API_FQDN=$(az containerapp show -g adp-rg -n adp-api \
  --query "properties.configuration.ingress.fqdn" -o tsv)
KC_FQDN=$(az containerapp show -g adp-rg -n adp-keycloak \
  --query "properties.configuration.ingress.fqdn" -o tsv)   # internal .internal. FQDN

PATCH_BODY="{\"redirectUris\":[\"https://${API_FQDN}/*\"],\"webOrigins\":[\"https://${API_FQDN}\"]}"

az containerapp job start -g adp-rg -n adp-keycloak-admin \
  --image "<acr-login-server>/adp-api:<tag>" \
  --container-name keycloak-admin \
  --command "python3" "/app/src/adp/ops/keycloak_admin_patch.py" \
  --env-vars \
    KEYCLOAK_URL="https://${KC_FQDN}/auth" \
    KEYCLOAK_REALM=ADPRealm \
    KEYCLOAK_ADMIN_USERNAME=admin \
    "KEYCLOAK_ADMIN_PASSWORD=secretref:keycloak-admin-password" \
    KC_PATCH_TARGET=client KC_PATCH_CLIENT_ID=adp-frontend \
    "KC_PATCH_BODY=${PATCH_BODY}"
```
Note `KEYCLOAK_URL` must include the `/auth` path — Keycloak serves everything
under `/auth` (`--http-relative-path=/auth`); without it the admin token endpoint
404s. Also commit the corrected `redirectUris`/`webOrigins` back into
`adp-realm.json` so the next from-scratch deploy imports them right.

Verify the realm patch landed (checks the /auth reverse proxy end to end):
```bash
curl -s "https://${API_FQDN}/auth/realms/ADPRealm/.well-known/openid-configuration" | head -c 200
```

### Enabling MFA (TOTP) on an already-provisioned realm (ADP-odp)

`adp-realm.json`'s `otpPolicy*`/`requiredActions` fields (added for ADP-odp)
only take effect on a **fresh** realm import — the same `IGNORE_EXISTING`
limitation as above means they're inert against an already-provisioned
`ADPRealm`. Apply live with the identical `keycloak_admin_patch.py` mechanism,
just targeting the realm instead of the client:

```bash
PATCH_BODY='{"otpPolicyType":"totp","otpPolicyAlgorithm":"HmacSHA1","otpPolicyDigits":6,"otpPolicyPeriod":30,"otpPolicyInitialCounter":0,"otpPolicyLookAheadWindow":1,"otpPolicyCodeReusable":false,"requiredActions":[{"alias":"CONFIGURE_TOTP","name":"Configure OTP","providerId":"CONFIGURE_TOTP","enabled":true,"defaultAction":true,"priority":10,"config":{}}]}'

az containerapp job start -g adp-rg -n adp-keycloak-admin \
  --image "<acr-login-server>/adp-api:<tag>" \
  --container-name keycloak-admin \
  --command "python3" "/app/src/adp/ops/keycloak_admin_patch.py" \
  --env-vars \
    KEYCLOAK_URL="https://${KC_FQDN}/auth" \
    KEYCLOAK_REALM=ADPRealm \
    KEYCLOAK_ADMIN_USERNAME=admin \
    "KEYCLOAK_ADMIN_PASSWORD=secretref:keycloak-admin-password" \
    KC_PATCH_TARGET=realm \
    "KC_PATCH_BODY=${PATCH_BODY}"
```

Note `requiredActions[].defaultAction` only auto-assigns to users created via
Keycloak's own self-registration/first-login flow — **not** to users created
through the admin REST API (which is how every user in this deployment is
created, since self-registration is disabled). `keycloak_create_users.py`
already sets `"requiredActions": ["CONFIGURE_TOTP"]` explicitly on new-user
creation for this reason; existing users are left alone on re-run (no forced
re-enrollment on already-provisioned accounts).

Verify with a real browser login (not curl) — confirm the OTP enrollment
screen actually appears on first login for a newly-created user.

### Frontend auth must stay ON in the deployed build

The deployed frontend and backend must agree on auth. The backend hardcodes
`ADP_AUTH_ENABLED=true` (`apiapp.bicep`). The frontend's `VITE_AUTH_ENABLED` and
`VITE_KEYCLOAK_URL` are **baked into the static bundle at build time** by Vite,
so `deploy.sh`/the CI workflow pass them as `--build-arg`s and the root
`.dockerignore` + `Dockerfile` pin `VITE_AUTH_ENABLED=true` (ADP-cm9). If the
deployed site shows a **black screen**: the frontend likely built with auth
disabled (e.g. a stray `web/.env.local` leaked into the image) — it then sends no
token, every API call 401s, and the SPA fails to render. Confirm the bundle is
correct:
```bash
# In a freshly built image / dist: the local dev URL must NOT appear, and the
# real deploy Keycloak URL must be present.
grep -c "127.0.0.1:8080" web/dist/assets/*.js   # want 0
```

### Pause / resume (cheaper idle, keeps data)

```bash
cd infra/azure
./pause.sh    # scales both apps toward zero, stops Postgres. Keeps all data + config.
./resume.sh   # starts Postgres, restores replicas. Same URL, no redeploy needed.
```
Postgres storage, ACR, and Key Vault still bill a few $/mo while paused; only
compute is paused. Azure auto-restarts a stopped Flexible Server after 7 days.

### Full teardown (destroys ALL data)

```bash
cd infra/azure
./destroy.sh   # type the resource-group name to confirm; deletes the RG and purges
               # the Key Vault. Local infra/azure/.secrets/ is kept for a rebuild.
```

### Seeding data from local dev into Azure

```bash
cd infra/azure
./seed-data.sh   # or ./seed-data.sh "postgresql://user:pass@host:5432/dbname" for a non-default source
```

Copies data from a local Postgres database into the already-deployed Azure
Postgres instance. **Deliberately a manual, on-demand script — not part of
`deploy.sh` or the CD pipeline below.** Unlike infrastructure provisioning or
an app-image rollout, this is *not* idempotent: re-running it against
already-seeded data will duplicate rows or hit unique-constraint errors. Runs
from your own authenticated `az` session, not CI — the CI service principal
is deliberately scoped to zero Postgres access (see CI/CD below), and this
script doesn't change that.

Excludes `alembic_version` (already correct on the target from its own
migration run), `audit_entries`, and `operations` — environment-specific
bookkeeping/audit records, not content data that should follow you between
environments. Handles the two self-referencing hierarchy tables
(`business_capabilities`, `technical_capabilities`) by reordering rows by
`level` ascending rather than using `pg_dump --disable-triggers`, which
requires superuser privileges Azure's admin login doesn't have.

### CI/CD

Push to `main` triggers `.github/workflows/deploy-azure.yml` (OIDC federated
credential, no stored secret) — it rebuilds the API image and rolls out
`adp-api`. Infra (Bicep) changes are applied manually via `deploy.sh`, not by the
workflow. **Data is never part of this pipeline** — see "Seeding data" above.
