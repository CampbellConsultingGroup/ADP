# ADP Runbook

Operational procedures for the AI-Assisted Architecture Design Platform.

---

## Health checks

```bash
# Liveness
curl http://localhost:8000/health
# {"status": "healthy", "reason": null, "version": "0.1.0"}

# Prometheus metrics
curl http://localhost:8000/metrics | grep adp_
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

### Backend API

```bash
cd /home/jmuir/projects/ADP
uvicorn adp.api.app:app --host 0.0.0.0 --port 8000 --reload
```

Required environment variables:

```bash
export ADP_DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/adp"
export ADP_LLM_ENDPOINT="https://api.anthropic.com"
export ADP_LLM_API_KEY="sk-..."   # Never logged; never in spans
```

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
cd src
alembic upgrade head
```

### Check current migration state

```bash
cd src
alembic current
```

### Rollback one step

```bash
cd src
alembic downgrade -1
```

### Regenerate the JSON Schema after model changes

```bash
# Always run after editing src/adp/models.py
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

This ingests content from configured Git repositories and the design store into the pgvector knowledge base. Requires Docker (PostgreSQL with pgvector) in the deployment environment.

### Validate a design JSON file

```bash
adp-generate --validate path/to/design.json
# ✓ path/to/design.json is schema-valid and referentially intact.
```

---

## Working with designs

### Fetch a design

```bash
curl http://localhost:8000/api/v1/designs/DESIGN-001 \
  -H "Authorization: Bearer $ADP_TOKEN"
```

### Generate a stakeholder document

```bash
curl http://localhost:8000/api/v1/designs/DESIGN-001/document \
  -H "Authorization: Bearer $ADP_TOKEN" \
  > design-001.md
```

### Generate all three C4 level renders

```bash
curl http://localhost:8000/api/v1/designs/DESIGN-001/views \
  -H "Authorization: Bearer $ADP_TOKEN" \
  | python3 -c "
import sys, json, base64
r = json.load(sys.stdin)
for level in ('context', 'container', 'component'):
    open(f'design-001-{level}.svg', 'w').write(r[level]['svg'])
    open(f'design-001-{level}.png', 'wb').write(base64.b64decode(r[level]['png_base64']))
    print(f'Saved {level}')
"
```

### Export a design to version control

```bash
# Step 1: get a confirmation ID
CONF=$(curl -s -X POST http://localhost:8000/api/v1/operations/confirm \
  -H "Authorization: Bearer $ADP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"action": "export_design", "target": "DESIGN-001"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['confirmation_id'])")

# Step 2: export with confirmation
curl -X POST http://localhost:8000/api/v1/designs/DESIGN-001/export \
  -H "Authorization: Bearer $ADP_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"confirmation_id\": \"$CONF\", \"export_root\": \"/srv/architecture-exports\"}"

# Step 3: commit the export
cd /srv/architecture-exports
git add exports/DESIGN-001/
git commit -m "ADP export: DESIGN-001 ($(date -u +%Y-%m-%dT%H:%M:%SZ))"
```

### Re-import an exported model

```bash
MODEL_JSON=$(cat /srv/architecture-exports/exports/DESIGN-001/v3/model.json)
curl -X POST http://localhost:8000/api/v1/designs/import \
  -H "Authorization: Bearer $ADP_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"model_json\": $(echo "$MODEL_JSON" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))')}"
```

---

## Request tracing

Every request gets a trace ID. Inject your own to correlate across systems:

```bash
curl http://localhost:8000/api/v1/designs/DESIGN-001/document \
  -H "Authorization: Bearer $ADP_TOKEN" \
  -H "X-Trace-ID: incident-2026-07-02-001"
# Response header: X-Trace-ID: incident-2026-07-02-001
```

All log lines for that request will carry `"trace_id": "incident-2026-07-02-001"`.

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
adp.step_name       "retrieve" | "generate" | "analyze_tradeoffs" | "rank" | ...
adp.input_tokens    1240
adp.output_tokens   380
adp.estimated_cost_usd  0.00312
adp.latency_ms      1840
adp.knowledge_item_ids  '["KI-001", "KI-003"]'
adp.design_id       "DESIGN-001"
adp.operation_id    "OP-042"
```

### Check the locked C4 theme

```bash
curl http://localhost:8000/api/v1/theme/c4 | python3 -m json.tool
```

Current baseline theme version: `1.0.1` (container fill updated from `#438DD5` to `#2874A6` to meet WCAG AA 4.5:1 contrast).

---

## Running tests

```bash
# Unit + contract tests (no Docker required)
pytest tests/ --ignore=tests/integration -q

# QG-08 no-leak CI gate (blocking)
pytest tests/unit/test_no_sensitive_data.py -v

# QG-10 trace ID in logs (blocking)
pytest tests/unit/test_trace_id_context.py -v

# QG-11 AI step span attributes (blocking)
pytest tests/unit/test_ai_step_span.py -v

# TypeScript tests (web canvas)
cd web && npm run test:run

# Integration tests (requires Docker + PostgreSQL with pgvector)
pytest tests/integration/ -v
```

Current test count: **335 Python + 23 TypeScript** (all passing).

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
# Debian/Ubuntu/WSL
sudo apt-get install -y libcairo2-dev
pip install cairosvg --break-system-packages
```

### 409 Conflict on design update

Two clients tried to update the same design version simultaneously. The canvas shows: "Design updated by another user. Reload to see the latest version." Click **Reload**.

From the API perspective:

```bash
# Get the current version before retrying
CURRENT_VERSION=$(curl -s http://localhost:8000/api/v1/designs/DESIGN-001 \
  -H "Authorization: Bearer $ADP_TOKEN" | python3 -c "import sys,json; print(json.load(sys.stdin)['version'])")

# Include the current version in the next mutation request
```

### Export returns 409 "directory already exists"

The design version has already been exported. Bump the design version number before re-exporting, or export to a different `export_root` path.

### Import fails with schema version mismatch

```
{"detail": "Schema version '2.0.0' is not supported; current: '1.0.0'"}
```

The exported file was produced by a newer ADP version. Either upgrade ADP, or re-export from an ADP instance running schema version `1.0.0`.

### `sentence-transformers` not installed (knowledge reindex)

The self-hosted embedding model requires `sentence-transformers>=2.7` (~300MB). In environments where this is unavailable, knowledge retrieval falls back to keyword-only search. To install:

```bash
pip install sentence-transformers --break-system-packages
```

---

## Security: what is never logged or stored in spans

Per FR-006 (ADP-SPEC-012 / QG-08):

- `ADP_LLM_API_KEY` — never in logs, spans, or any output
- Bearer tokens / authorization headers — only `auth_present: true` is logged
- Design content (element names, requirement text, AI prompt/response text) — only IDs and metadata
- Source text submitted for requirements intake — deleted from memory after extraction

The QG-08 CI gate (`tests/unit/test_no_sensitive_data.py`) verifies this automatically on every PR.

---

## Audit trail

Every consequential model mutation is recorded in `design.audit_log` (append-only per ART-IX). To read the audit trail for a design:

```bash
curl http://localhost:8000/api/v1/designs/DESIGN-001 \
  -H "Authorization: Bearer $ADP_TOKEN" \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
for entry in d.get('audit_log', []):
    print(f\"{entry['id']}: {entry['actor']} → {entry['action']} ({entry['timestamp']})\")
"
```

Audit entries cannot be deleted or modified; they are enforced at the database level by a PostgreSQL trigger (`deny_audit_mutation()`).

---

## Theme management

### View current theme

```bash
curl http://localhost:8000/api/v1/theme/c4 | python3 -m json.tool
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
    print(f'{kind}: {ratio:.2f}:1 {status}')
"
```
