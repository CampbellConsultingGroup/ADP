# Feature Specification: Multi-Design UI and Production Readiness

**Feature Branch**: `025-multi-design-production`
**Created**: 2026-07-03
**Status**: Draft
**Depends on**: ADP-SPEC-023 (Internal Consolidation), ADP-SPEC-024 (Persistent Operations)

## Context

ADP was built as a single-user, single-design tool with a hardcoded `DESIGN-001` fallback. The `App.tsx` comment says `"DESIGN-001"` — not a configuration value, not a design selector, a hardcoded string. Every architect who has used ADP has been working on this one design.

ADP-SPEC-024 makes the server multi-worker capable. This spec makes it multi-user capable from a product perspective. It has three parts that must ship together because they are mutually dependent:

1. **Design Management** — a screen to list all designs, open an existing one, and create a new one. Without this, the hardcode cannot be removed because there is no way for a user to navigate to a design.
2. **Navigation Consolidation** — the navigation bar is currently copy-pasted across five components (IntakePage, RecommendationPage, KnowledgePage, Workspace, and the new DesignsPage). Extracting it into one `NavBar` component is required before adding a sixth view.
3. **Production Deployment** — Docker Compose, environment variable documentation, and a startup runbook that a team can follow to deploy ADP as a shared tool. Without this, the multi-user capability is theoretical.

## Constitutional Articles Touched

- **ART-I** — Spec-Driven Development: always applies
- **ART-IV** — Test-Driven Development: always applies
- **ART-V** — Security & Threat Model: creating a new design is a write operation; no auth in v1 but the action is audited
- **ART-IX** — Audit Trail: design creation must write an audit entry

## Threat Model

**Assets at risk**: All designs in the shared PostgreSQL database — once ADP is multi-user, one user's designs are accessible to all users (no row-level security in v1).

**Trust boundaries crossed**: Browser → FastAPI → PostgreSQL. No new boundaries.

**Abuse cases**:
- Runaway design creation consuming disk: mitigated by a soft limit of 1,000 designs (configurable via `ADP_MAX_DESIGNS` env var); POST /designs returns 429 when exceeded.
- User accidentally deletes another user's design: no delete endpoint in v1; designs are immutable once created (elements and relationships can be modified, but the design record itself persists).

**Residual risk**: No authentication or authorisation in v1. All designs are visible to all users on the same ADP instance. Accepted for v1 single-tenant deployment (a team with shared trust). Multi-tenancy with auth is a future spec.

## User Scenarios & Testing

### User Story 1 — List and Open a Design (Priority: P1)

An architect lands on ADP and sees a list of all designs in the system — title, creation date, element count. They click a design to open it and are taken directly to the Intake view for that design.

**Why this priority**: Without a design selector, no user can navigate to their work without knowing the design ID and editing the URL.

**Independent Test**: With two designs seeded in the DB, the Designs screen lists both. Clicking one transitions to the Intake view with the correct `designId`.

**Acceptance Scenarios**:

1. **Given** three designs exist, **When** the user opens ADP, **Then** the Designs screen is the landing page and shows all three designs with title, element count, and created date.
2. **Given** the designs list is shown, **When** the user clicks a design, **Then** the Intake view opens for that design and the design ID is correctly set.
3. **Given** no designs exist, **When** the user opens ADP, **Then** the Designs screen shows an empty state with a "Create your first design" call-to-action.

---

### User Story 2 — Create a New Design (Priority: P2)

An architect clicks "New Design", enters a title and optional description, and is taken directly to the Intake view of the newly created design, ready to add requirements.

**Why this priority**: Without this, new users have no path into the tool (the hardcoded DESIGN-001 was the only entry point).

**Independent Test**: POST `/api/v1/designs` with a title; a new design appears in the list with zero elements; the response includes the new design ID.

**Acceptance Scenarios**:

1. **Given** the user is on the Designs screen, **When** they click "New Design", enter a title, and confirm, **Then** a new design is created and the Intake view opens for it.
2. **Given** the user submits a blank title, **Then** a validation error is shown and no design is created.
3. **Given** a design is created, **Then** it appears immediately in the designs list on next visit.

---

### User Story 3 — Shared Navigation Component (Priority: P3)

All five views (Designs, Intake, Recommendations, Canvas, Knowledge) share the same navigation bar. Adding or renaming a nav item requires changing one file.

**Why this priority**: The current copy-paste across five components is a maintenance trap — a bug or new view requires five simultaneous edits.

**Independent Test**: All five views render the same navigation labels and active-state highlighting without duplicating navigation JSX.

**Acceptance Scenarios**:

1. **Given** the user is on any view, **When** they look at the navigation bar, **Then** all five views are shown and the current view is visually active.
2. **Given** navigation is extracted to a shared component, **When** `grep -rn "NAV_ITEMS" web/src/` is run, **Then** it returns exactly one result — the `NavBar` component file.

---

### User Story 4 — Production Deployment (Priority: P4)

A team lead follows the `RUNBOOK.md` to deploy ADP on a Linux server with Docker Compose. The result is a running instance accessible on a configured port with multiple uvicorn workers, PostgreSQL, and persistent storage — the full multi-user setup.

**Why this priority**: Multi-user capability is theoretical without deployment infrastructure.

**Independent Test**: `docker compose up` from the project root starts ADP and PostgreSQL; `curl http://localhost:8001/health` returns `{"status": "healthy"}`; the design list endpoint returns an empty list.

**Acceptance Scenarios**:

1. **Given** a server with Docker and Docker Compose installed, **When** the team lead runs `docker compose up -d` after setting env vars, **Then** ADP is accessible at the configured port within 60 seconds.
2. **Given** ADP is running, **When** the host is rebooted, **Then** `docker compose up -d` restores the service with all existing designs intact.
3. **Given** `ADP_WORKERS=4` is set, **Then** uvicorn starts with 4 workers and all four serve requests correctly against the shared PostgreSQL database.

---

### Edge Cases

- Designs list with 500+ designs: paginate at 50 per page; show total count.
- Design title with special characters (quotes, slashes): sanitised server-side; stored as-is; displayed safely in UI.
- `POST /designs` while DB is unavailable: returns 503; no partial state.
- Opening a design ID that no longer exists (e.g. via a bookmarked URL): redirected to Designs list with a "design not found" banner.

## Requirements

### Functional Requirements

**Design Management API (FR-001 to FR-004)**

- **FR-001**: `POST /api/v1/designs` MUST accept `{"title": string, "description": string | null}` and return 201 with the new `ArchitectureDescription` (empty elements, requirements, relationships). The design ID MUST be a server-generated slug (e.g. `DSN-001`, auto-incrementing).
- **FR-002**: `GET /api/v1/designs` MUST return a paginated list of design summaries: id, title, description, element_count, created_at, updated_at. Default page size 50.
- **FR-003**: The existing `GET /api/v1/designs/{id}` endpoint is unchanged.
- **FR-004**: `POST /api/v1/designs` MUST write an ART-IX audit entry `action: "design-created"` to the new design.

**Navigation Consolidation (FR-005 to FR-006)**

- **FR-005**: A shared `web/src/shell/NavBar.tsx` component MUST be created, accepting `currentView: AppView` and `onNavigate: (view: AppView) => void` as props. It renders the ADP wordmark and all navigation tabs.
- **FR-006**: `IntakePage`, `RecommendationPage`, `KnowledgePage`, and `Workspace` MUST remove their local `NAV_ITEMS` arrays and inline navigation JSX, replacing them with `<NavBar currentView="intake" onNavigate={onNavigate} />`.

**Designs Screen (FR-007 to FR-009)**

- **FR-007**: A `web/src/designs/DesignsPage.tsx` component MUST be created as the application landing page (replaces the current default of Intake). It shows a list of designs, a "New Design" button, and an empty state.
- **FR-008**: `App.tsx` MUST set initial view to `"designs"` when no design is selected. `AppView` type MUST include `"designs"`. Once a design is selected, `currentDesignId` state is set and subsequent navigation within that design uses the existing four views.
- **FR-009**: The `App.tsx` hardcoded `"DESIGN-001"` fallback MUST be removed. `designId` MUST be `null` until the user selects or creates a design.

**Production Deployment (FR-010 to FR-013)**

- **FR-010**: A `docker-compose.yml` MUST be added to the project root, defining two services: `db` (postgres:16-alpine with a named volume for data persistence and health check) and `api` (ADP server built from a new `Dockerfile`, depending on `db`).
- **FR-011**: A `Dockerfile` MUST be added, using a Python 3.12 slim base image, installing only production dependencies (`pip install -e .`), and starting uvicorn with `$ADP_WORKERS` workers (default 2).
- **FR-012**: An `.env.example` file MUST document all required and optional environment variables: `ADP_DATABASE_URL`, `ADP_LLM_ENDPOINT`, `ADP_LLM_API_KEY`, `ADP_LLM_MODEL`, `ADP_WORKERS`, `ADP_PORT`, `ADP_MAX_DESIGNS`.
- **FR-013**: `RUNBOOK.md` MUST be updated with a "Production Deployment" section covering: prerequisites, first-time setup (copy `.env.example`, run migrations, start), upgrade procedure, and basic troubleshooting.

### Key Entities

- **DesignSummary**: id, title, description, element_count, created_at, updated_at (for the list view)

## Success Criteria

- **SC-001**: `grep -rn "DESIGN-001" web/src/` returns zero results after this spec.
- **SC-002**: `grep -rn "NAV_ITEMS" web/src/` returns exactly one result (the NavBar component).
- **SC-003**: `docker compose up -d && sleep 10 && curl -s http://localhost:8001/health` returns `{"status": "healthy"}`.
- **SC-004**: A new architect can go from `git clone` to a running multi-user ADP instance by following `RUNBOOK.md` in under 15 minutes.
- **SC-005**: Two browser tabs, each opened to a different design, operate independently without interfering with each other's operation state.

## Assumptions

- ADP-SPEC-023 and ADP-SPEC-024 are complete before this spec is implemented.
- Design IDs follow the pattern `DSN-\d{3,}` — the existing `^ELM-`, `^REQ-`, `^REL-` patterns do not apply to design IDs.
- The Vite-built frontend is served as static files by a separate web server (nginx in Docker Compose) rather than by the FastAPI backend — this is the standard production pattern.
- No SSL/TLS termination is in scope; that is handled by the infrastructure layer (reverse proxy, load balancer) above Docker Compose.
- The `web/` Vite build is a one-time `npm run build` step baked into the Docker image for the frontend — a separate `frontend` service in Docker Compose.
