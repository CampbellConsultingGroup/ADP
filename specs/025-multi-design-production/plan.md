# Implementation Plan: Multi-Design UI and Production Readiness (ADP-SPEC-025)

## Tech Stack
- **Backend**: No new packages. New FastAPI endpoint `POST /api/v1/designs` + `GET /api/v1/designs` (list). Auto-increment design ID via existing store.
- **Frontend**: New `web/src/shell/NavBar.tsx` + `web/src/designs/DesignsPage.tsx`. TanStack Query hooks for design list + creation.
- **DevOps**: `Dockerfile` (Python 3.12 slim + Vite build stage), `docker-compose.yml` (api + db + frontend), `.env.example`

## Architecture

### Part A: Backend — Design List + Create

New endpoints in existing `src/adp/api/routers/layouts.py` (or a new `designs.py` router):

```
GET  /api/v1/designs          → list summaries (paginated, default 50)
POST /api/v1/designs          → create new design, return 201 with full ArchitectureDescription
```

Design ID generation: `DSN-{N:03d}` auto-incremented — query `SELECT MAX(id) FROM architecture_descriptions` and parse the sequence number. First design is `DSN-001`.

`DesignSummary` Pydantic model (summary only, not full model):
```python
class DesignSummary(BaseModel):
    id: str
    title: str
    description: str | None
    element_count: int
    created_at: datetime
    updated_at: datetime
```

### Part B: Frontend — NavBar + DesignsPage

**`web/src/shell/NavBar.tsx`**:
```tsx
<NavBar currentView={view} onNavigate={onNavigate} designId={designId} />
```
Renders: ADP wordmark | Intake | Recommendations | Canvas | Knowledge
Shows "← Designs" link when a design is open.
Omits design-specific tabs (Intake, Recommendations, Canvas) on the Designs view.

**`web/src/designs/DesignsPage.tsx`**:
- Calls `useDesignList()` (new hook in `web/src/api/designs.ts`)
- Lists designs with title, element count, created date
- "New Design" button → inline form with title field → calls `useCreateDesign()`
- On create success: set `currentDesignId` and navigate to Intake

**`App.tsx` changes**:
```tsx
type AppView = "designs" | "canvas" | "intake" | "recommend" | "knowledge";
const [currentDesignId, setCurrentDesignId] = useState<string | null>(null);
const [view, setView] = useState<AppView>("designs");  // landing page
```

Remove `getDesignIdFromPath()` and the `"DESIGN-001"` fallback entirely.

### Part C: Production Deployment

**`Dockerfile`** (multi-stage):
- Stage 1 `frontend-build`: `node:20-alpine`, runs `npm ci && npm run build`
- Stage 2 `api`: `python:3.12-slim`, copies backend + built frontend static files, runs uvicorn

**`docker-compose.yml`**:
```yaml
services:
  db:
    image: postgres:16-alpine
    volumes: [pgdata:/var/lib/postgresql/data]
    healthcheck: ...
  api:
    build: .
    environment: [ADP_DATABASE_URL, ADP_LLM_API_KEY, ADP_LLM_ENDPOINT, ADP_WORKERS]
    depends_on: db
    ports: ["${ADP_PORT:-8001}:8001"]
```

**`.env.example`**: Documents every env var with description and default.

## File Changes

| File | Action |
|------|--------|
| `src/adp/api/routers/designs.py` | CREATE — list + create endpoints |
| `src/adp/api/app.py` | EDIT — register designs router |
| `web/src/shell/NavBar.tsx` | CREATE — shared navigation component |
| `web/src/shell/index.ts` | CREATE — barrel export |
| `web/src/designs/DesignsPage.tsx` | CREATE — design list + create |
| `web/src/api/designs.ts` | EDIT — add `useDesignList()`, `useCreateDesign()` hooks |
| `web/src/App.tsx` | EDIT — add designs view, remove DESIGN-001 fallback |
| `web/src/intake/IntakePage.tsx` | EDIT — use NavBar, remove local NAV_ITEMS |
| `web/src/recommend/RecommendationPage.tsx` | EDIT — use NavBar, remove local NAV_ITEMS |
| `web/src/knowledge/KnowledgePage.tsx` | EDIT — use NavBar, remove local NAV_ITEMS |
| `web/src/canvas/Workspace.tsx` | EDIT — use NavBar, remove inline nav |
| `Dockerfile` | CREATE |
| `docker-compose.yml` | CREATE |
| `.env.example` | CREATE |
| `RUNBOOK.md` | EDIT — add Production Deployment section |
| `tests/contract/test_designs_api.py` | CREATE — list + create contract tests |
