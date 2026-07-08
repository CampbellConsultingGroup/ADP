---
name: dev-server-up
description: Start the ADP backend (FastAPI/uvicorn) and web canvas (Vite) dev servers locally, checking PostgreSQL/pgvector readiness and migration state first.
metadata:
  author: house
---

## When to use

Invoke when the user asks to start, run, or restart the ADP API, web canvas, or "the app" locally (e.g. "start up ADP", "start the backend"). Not for E2E test runs — Playwright's `fullstack` project targets whatever `ADP_API_URL`/`ADP_WEB_URL` you point it at rather than owning its own server lifecycle, so check RUNBOOK.md if E2E servers specifically are needed.

## Ports and prerequisites

- Backend: FastAPI/uvicorn on **:8001** (RUNBOOK.md: "Port 8000 may be occupied by other services" — that's the neighboring `llmasjudge` repo's backend port; ADP deliberately uses 8001 to avoid the collision when both are running side by side)
- Web canvas: Vite dev server on **:5173** (same default as llmasjudge's frontend — if both repos' frontends are wanted simultaneously, the second one Vite starts will auto-increment to 5174; confirm which port it actually bound to from its own log output rather than assuming)
- **PostgreSQL 15+ with the `pgvector` extension**, native (not Docker) for local dev per RUNBOOK.md — this is NOT started by this skill. Check readiness, don't provision it:
  ```bash
  pg_isready -h 127.0.0.1 -p 5432 -U adp_user -d adp
  ```
  If this fails, stop and point the user at RUNBOOK.md's "Starting the stack → PostgreSQL (one-time setup)" section rather than attempting cluster creation yourself — that's a one-time, host-level setup step, not a routine dev-server start.
- `ADP_DATABASE_URL`, `ADP_LLM_API_KEY` are **required** with no code-level default (`os.environ["ADP_DATABASE_URL"]` raises if unset in `adp.knowledge.indexer`) — read from a real `.env` at repo root if present; if no `.env` exists, stop and ask rather than fabricating a connection string or key.

## Steps

1. **Check what's already running**:
   ```bash
   curl -sf http://localhost:8001/health >/dev/null && echo "backend up"
   curl -sf http://localhost:5173 >/dev/null && echo "web canvas up"
   ```
   If both respond, report that and stop.

2. **Check PostgreSQL readiness** (see above). If up, check migration state before starting the API — a stale schema fails confusingly deep inside request handlers rather than at startup:
   ```bash
   alembic current   # from repo root, where alembic.ini lives
   ```
   If it doesn't match `alembic history`'s head, tell the user migrations are pending (`alembic upgrade head`) rather than running it for them silently — a migration is a schema change, not a routine dev-server action.

3. **Start the backend** in the background from the repo root:
   ```bash
   set -a; source .env; set +a
   uvicorn adp.api.app:app --host 0.0.0.0 --port 8001 --reload
   ```
   Use `run_in_background: true`. If `ADP_AUTH_ENABLED` is unset or `true` (the default per `.env.example`), Keycloak-issued tokens will be required for authenticated endpoints — confirm with the user whether they want `ADP_AUTH_ENABLED=false` for a local no-auth session before exporting it, rather than silently overriding their `.env`.

4. **Start the web canvas** in the background from `web/`:
   ```bash
   npm run dev
   ```
   Use `run_in_background: true`.

5. Poll for readiness (don't sleep-guess a fixed duration) until both checks in step 1 succeed, then report the URLs: `http://localhost:5173` (canvas) and `http://localhost:8001` (API, plus `/health` and `/metrics`).

6. Never kill an existing process on these ports, and never run `alembic upgrade head` or attempt Postgres cluster setup, without asking first.
