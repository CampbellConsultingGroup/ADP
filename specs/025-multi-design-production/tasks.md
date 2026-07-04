# Tasks: Multi-Design UI and Production Readiness (ADP-SPEC-025)

**Input**: Design documents from `/specs/025-multi-design-production/`
**Prerequisites**: ADP-SPEC-023 ✅, ADP-SPEC-024 ✅

---

## Phase 1: Backend — Design List + Create Endpoints

### Tests (MANDATORY — ART-IV)

- [X] T001 [P] Create `tests/contract/test_designs_api.py`: write `test_list_designs_returns_empty_list()` — mock store returns []; GET `/api/v1/designs`; assert 200 with `{"designs": [], "total": 0}`
- [X] T002 [P] Write `test_list_designs_returns_summaries()`: mock store returns 2 designs; assert both appear with `id`, `title`, `element_count`, `created_at`
- [X] T003 [P] Write `test_create_design_returns_201()`: POST `{"title": "My New Design"}`; assert 201; body has `id` matching `DSN-\d+`, `title`, empty `elements`/`requirements`/`relationships`
- [X] T004 [P] Write `test_create_design_blank_title_returns_422()`: POST `{"title": ""}`; assert 422
- [X] T005 [P] Write `test_create_design_audit_entry_written()`: POST new design; assert `audit_log` contains entry with `action: "design-created"`

### Implementation

- [X] T006 Create `src/adp/api/routers/designs.py`: define `DesignSummary` Pydantic model (id, title, description, element_count, created_at, updated_at); define `DesignListResponse(designs: list[DesignSummary], total: int, page: int, page_size: int)`; define `CreateDesignRequest(title: str, description: str | None = None)` with non-empty title validator; implement `GET /api/v1/designs` listing all designs (paginated, default 50, sorted by created_at desc); implement `POST /api/v1/designs` creating a new `ArchitectureDescription` with auto-generated DSN-xxx ID and writing an ART-IX audit entry
- [X] T007 Edit `src/adp/api/app.py`: import and register `designs.router`
- [X] T008 [P] Add `useDesignList()` TanStack Query hook to `web/src/api/designs.ts`: GET `/api/v1/designs`; returns `{ designs, total }`
- [X] T009 [P] Add `useCreateDesign()` mutation hook to `web/src/api/designs.ts`: POST `/api/v1/designs` with `{ title, description }`; on success invalidates `["designs"]` query

**Checkpoint**: `pytest tests/contract/test_designs_api.py -q --no-cov` — all pass

---

## Phase 2: Frontend — Shared NavBar Component

- [X] T010 Create `web/src/shell/NavBar.tsx`: shared navigation component accepting `currentView: AppView`, `onNavigate: (view: AppView) => void`, and optional `designId: string | null`; renders ADP wordmark + nav tabs (Designs always visible; Intake/Recommendations/Canvas/Knowledge only when `designId` is set); active tab highlighted with white underline on blue background; "← Designs" back link shown when in design context
- [X] T011 Create `web/src/shell/index.ts`: barrel export `export { default as NavBar } from './NavBar'`
- [X] T012 Edit `web/src/intake/IntakePage.tsx`: replace local `NAV_ITEMS` array + inline nav JSX with `<NavBar currentView="intake" onNavigate={onNavigate} designId={designId} />`; import `NavBar` from `../shell`; remove `NavView` type and `NAV_ITEMS` constant
- [X] T013 Edit `web/src/recommend/RecommendationPage.tsx`: same NavBar replacement as T012
- [X] T014 Edit `web/src/knowledge/KnowledgePage.tsx`: same NavBar replacement; note Knowledge page has no designId context — pass `designId={null}`
- [X] T015 Edit `web/src/canvas/Workspace.tsx`: replace inline nav buttons and `NAV_ITEMS` with `<NavBar currentView="canvas" onNavigate={onNavigate} designId={designId} />`
- [X] T016 [P] Run `cd web && npx tsc --noEmit` — zero TypeScript errors after NavBar extraction
- [X] T017 [P] Verify: `grep -rn "NAV_ITEMS" web/src/` returns exactly one result (the NavBar component file itself, if it uses that name internally, otherwise zero)

---

## Phase 3: Frontend — Designs Screen and App Refactor

- [X] T018 Create `web/src/designs/DesignsPage.tsx`: renders `<NavBar currentView="designs" onNavigate={...} designId={null} />`; fetches design list via `useDesignList()`; shows list rows (title, element count, date, "Open" button); shows "New Design" button opening inline form with title field; on form submit calls `useCreateDesign()`; on success calls `onSelectDesign(newDesign.id)`; handles empty state with call-to-action
- [X] T019 Edit `web/src/App.tsx`: extend `AppView` to include `"designs"`; add `currentDesignId` state (`string | null`, initial `null`); set initial `view` to `"designs"`; add `onSelectDesign(id: string)` handler that sets `currentDesignId` and navigates to `"intake"`; remove `getDesignIdFromPath()` function; remove `"DESIGN-001"` fallback; pass `designId={currentDesignId ?? ""}` only after a design is selected; render `<DesignsPage>` when `view === "designs"` or `currentDesignId === null`
- [X] T020 [P] Run `cd web && npx tsc --noEmit` — zero TypeScript errors
- [X] T021 [P] Verify: `grep -rn "DESIGN-001" web/src/` returns zero results

---

## Phase 4: Production Deployment

- [X] T022 Create `Dockerfile` (multi-stage): Stage 1 `frontend-build` uses `node:20-alpine`, copies `web/`, runs `npm ci && npm run build`; Stage 2 `api` uses `python:3.12-slim`, installs system deps (`libpq-dev`), copies `src/` and `pyproject.toml`, runs `pip install -e . --no-cache-dir`, copies Vite build output from stage 1 to `/app/static/`, sets `CMD uvicorn adp.api.app:app --host 0.0.0.0 --port ${ADP_PORT:-8001} --workers ${ADP_WORKERS:-2}`
- [X] T023 Create `docker-compose.yml`: defines `db` service (postgres:16-alpine, named volume `pgdata`, environment `POSTGRES_DB/USER/PASSWORD`, health check `pg_isready`); defines `api` service (build from Dockerfile, environment from `.env`, `depends_on: {db: {condition: service_healthy}}`, port mapping `${ADP_PORT:-8001}:8001`); `volumes: pgdata:`
- [X] T024 Create `.env.example` documenting: `ADP_DATABASE_URL` (required), `ADP_LLM_ENDPOINT` (default `https://api.anthropic.com`), `ADP_LLM_API_KEY` (required), `ADP_LLM_MODEL` (default `claude-sonnet-4-6`), `ADP_WORKERS` (default `2`), `ADP_PORT` (default `8001`), `ADP_MAX_DESIGNS` (default `1000`)
- [X] T025 Edit `RUNBOOK.md`: add "Production Deployment" section with steps: (1) Prerequisites (Docker, Docker Compose), (2) Clone and configure (copy `.env.example` to `.env`, fill in API key and DB password), (3) First-time setup (`docker compose up -d db && sleep 5 && docker compose run --rm api alembic upgrade head`), (4) Start (`docker compose up -d`), (5) Verify (`curl http://localhost:8001/health`), (6) Upgrade procedure (`git pull && docker compose build && docker compose up -d`), (7) Troubleshooting (logs, DB connection check)

---

## Phase 5: Polish

- [X] T026 [P] Run `pytest tests/ --ignore=tests/integration -q --no-cov` — full suite clean
- [X] T027 [P] Run `ruff check src/adp/api/routers/designs.py` — clean
- [X] T028 [P] Run `cd web && npx tsc --noEmit` — zero TypeScript errors
- [X] T029 [P] Smoke test: `docker compose build && docker compose up -d && sleep 10 && curl -s http://localhost:8001/health` returns `{"status": "healthy"}`
- [X] T030 [P] End-to-end verify: open browser at `http://localhost:8001`; see Designs screen; create a design; navigate to Intake; submit requirements; see proposals

---

## Notes

- DSN ID generation: query `SELECT id FROM architecture_descriptions ORDER BY created_at DESC LIMIT 1` and parse sequence; if none exist, start at `DSN-001`; must handle concurrent creation gracefully (retry on unique constraint violation)
- The NavBar `designId` prop drives conditional rendering — when `null`, the design-specific tabs (Intake, Recommendations, Canvas) are not shown. This prevents navigating to Intake without a design selected.
- Dockerfile static file serving: uvicorn does not serve static files efficiently in production. For v1 the `Dockerfile` serves static files via a simple `StaticFiles` mount on FastAPI (`app.mount("/", StaticFiles(directory="/app/static", html=True))`). A separate nginx container is the correct long-term solution but is out of scope for this spec.
- `ADP_MAX_DESIGNS` check should happen in `POST /api/v1/designs` before creating — query COUNT and return 429 if exceeded
