# ADP Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-08-12 (041-ai-chat-assistant plan added)

## Active Technologies
- Python 3.11+ + SQLAlchemy 2.x (async ORM), asyncpg (PostgreSQL async driver), Alembic (migrations), testcontainers-python (PostgreSQL container for integration tests), pydantic-settings (database URL config) (002-design-store)
- PostgreSQL 15+ — primary persistence; JSONB for `ArchitectureDescription` content with indexed paths for traceability queries (002-design-store)
- Python 3.11+ + FastAPI ≥ 0.111, uvicorn[standard] ≥ 0.30, python-jose[cryptography] ≥ 3.3 (JWT/OIDC validation), httpx ≥ 0.27 (OIDC JWKS fetch + test client) (003-platform-api)
- Delegates all canonical model persistence to `adp.store.DesignStore` (ADP-SPEC-002); transient operation state stored in-process dict with TTL for v1 (Redis deferred) (003-platform-api)
- Python 3.11+ + None new — uses `adp.models.AuditEntry` (ADP-SPEC-001) and `adp.store.DesignStore` (ADP-SPEC-002); no additional runtime packages (004-identity-authz)
- Delegates audit writes to `adp.store.DesignStore` (ADP-SPEC-002); the permission table is an in-process Python constant (no database required) (004-identity-authz)
- Python 3.11+ + `pgvector>=0.3` (SQLAlchemy PostgreSQL vector type), `sentence-transformers>=2.7` (self-hosted embedding; model-agnostic), `gitpython>=3.1` (Git connector), `python-frontmatter>=1.1` (Markdown/YAML frontmatter parsing from Git repos); existing stack: `sqlalchemy[asyncio]==2.0.51`, `asyncpg==0.31.0` (005-knowledge-retrieval)
- PostgreSQL 15+ with the `pgvector` extension enabled; two new tables (`knowledge_items`, `knowledge_relationships`) + HNSW index on `embedding` column + GIN index on `full_text` for keyword search; migrations via Alembic (005-knowledge-retrieval)
- Python 3.11+ + `httpx>=0.27` (async HTTP client for configurable LLM endpoint), `opentelemetry-sdk>=1.25` (telemetry span emission per ADP-SPEC-012), `tiktoken>=0.7` (token counting for cost estimation); existing stack: Pydantic v2, SQLAlchemy 2 async, FastAPI (ADP-SPEC-003) (006-requirements-intake)
- `ExtractedProposal` records stored transiently in-memory (same in-process store as ADP-SPEC-003 operation results, TTL 24h); confirmed requirements written to the canonical store via ADP-SPEC-002 `DesignStore`; raw source text is NEVER persisted (006-requirements-intake)
- Python 3.11+ + `langgraph>=0.2` (step orchestration with inspectable state), `langchain-core>=0.2` (Pydantic structured output tooling for LLM responses); same LLM client as ADP-SPEC-006 (`httpx>=0.27`, configurable endpoint); `opentelemetry-sdk>=1.25` (already in stack) (007-recommendation-engine)
- `SolutionOption` records stored transiently in ADP-SPEC-003's in-process operation store (TTL 24h); accepted option materializes `Element`/`Relationship` records into ADP-SPEC-002 `DesignStore`; no additional database tables required (007-recommendation-engine)
- Python 3.11+ + `langgraph>=0.2` (already in stack from ADP-SPEC-007); same LLM client as ADP-SPEC-006/007 (`httpx>=0.27`); `opentelemetry-sdk>=1.25` (already in stack); `asyncio.gather` for critic fan-out (no additional deps) (008-llm-as-judge)
- `Verdict` stored transiently in ADP-SPEC-003's in-process operation store (TTL 24h); on human acceptance, verdict is optionally persisted to ADP-SPEC-002's design store as a design annotation; raw source text is NEVER stored (008-llm-as-judge)
- TypeScript 5.x + React 18 + React Flow v12 (`@xyflow/react`) + TanStack Query v5 + Zustand v4 + Vite 5 (009-c4-workspace)
- Layout positions stored via a new `GET/PUT /api/v1/designs/{id}/layout` endpoint added to ADP-SPEC-003; canonical model data from existing endpoints (009-c4-workspace)
- Python 3.11+ + `cairosvg>=2.7` (SVG→PNG, no Java required); `jsonschema>=4.10` (theme schema validation, already in project); `LockedTheme` Pydantic v2 model generates `c4-theme.schema.json` via `adp-generate` (010-locked-theme-rendering)
- `c4-theme.json` authored artifact (versioned in git, reviewed as diff); `c4-theme.schema.json` generated from `LockedTheme` model; deterministic grid auto-layout for SVG; render exposed via `POST /api/v1/designs/{id}/render`; container fill updated to `#2874A6` (v1.0.1, WCAG AA compliant) (010-locked-theme-rendering)
- Python 3.11+ + `pyyaml>=6.0` (YAML export); `python-frontmatter>=1.1` (Markdown frontmatter — already in stack); new packages `adp.docs` (document generator, traceability), `adp.export` (export bundle orchestrator, importer, models); two new FastAPI routers; export requires ART-VIII `confirmation_id` gate + ART-IX audit entry; export bundle written atomically to configured VCS root (011-document-export)
- Python 3.11+ + `prometheus-client>=0.17` (metrics scrape endpoint); new `adp.telemetry` package with canonical span attribute constants, `TraceIdFilter` logging filter, `ai_step_span()` context manager, `ContextVar` trace ID carrier; `GET /health` + `GET /metrics` endpoints; QG-08 no-leak test enforced in CI; existing ADP-SPEC-006/007/008 telemetry.py files normalized to use `adp.telemetry.contract` constants (012-observability-telemetry)
- TypeScript 5.x + `@playwright/test` v1.47+ (E2E test runner); `playwright` browser lib (already in stack); Chromium browser; 18 API tests (no browser, no DB) + 4 browser tests (Chromium, route-mocked); `ADP_API_URL` and `ADP_WEB_URL` env vars control targets; `npm run test:e2e:api` for CI (013-playwright-e2e)
- Python 3.11+ + `psycopg2-binary` (synchronous driver for Alembic migrations; asyncpg used at runtime); `alembic.ini` at project root with `sqlalchemy.url` for direct CLI use; `ADP_DATABASE_URL` env var for runtime (DB setup)
- Python 3.12 (backend); TypeScript 5.x (frontend) (015-anthropic-llm)
- Python 3.12 (backend); TypeScript 5.x (frontend) + FastAPI, SQLAlchemy 2 async, asyncpg, Pydantic v2, React 18, TanStack Query v5 — all existing stack, zero new packages (029-element-technology-tags)
- PostgreSQL 16; new `element_technology_tags` table + B-tree + GIN indexes; `design_versions` JSONB extended with `technology_metadata` nested in element objects (029-element-technology-tags)
- PostgreSQL 16 — add `lifecycle_status` (B-tree indexed) + 4 date columns to `designs` table; extend `ArchitectureDescription` JSONB with lifecycle fields (030-design-lifecycle)
- Python 3.12 (backend); TypeScript 5.x + React 18 (frontend) + FastAPI, SQLAlchemy 2 async (raw SQL with sa.text() for aggregates), existing stack — zero new packages (031-portfolio-analysis)
- PostgreSQL 16; queries use existing `element_technology_tags` (B-tree + GIN indexes) and `designs` (lifecycle_status B-tree index) — no new migrations (031-portfolio-analysis)
- Python 3.12 (backend); TypeScript 5.x + React 18 (frontend) + Python stdlib `csv` module for CSV export; all else existing stack — zero new packages (032-governance-reporting)
- PostgreSQL 16; reads from `audit_entries`, `designs`, `design_versions.content` (JSONB for findings), `operations`, `llm_reasoning_log` — no new migrations (032-governance-reporting)
- Python 3.12 (backend); TypeScript 5.x + React 18 (frontend) + FastAPI ≥ 0.111, SQLAlchemy 2 async, asyncpg, Pydantic v2, TanStack Query v5 — all existing stack; zero new packages (033-business-architecture)
- PostgreSQL 16 — three new tables (`business_capabilities`, `value_streams`, `value_stream_stages`) via Alembic migration 007 (033-business-architecture)
- PostgreSQL 16; two new join tables (`capability_design_links`, `value_stream_design_links`) via Alembic migration 008; composite PK on both; `ON DELETE CASCADE` for both FK legs (034-business-arch-traceability)
- Python 3.12 (backend); TypeScript 5.x (frontend) + FastAPI ≥ 0.111, SQLAlchemy 2 async, asyncpg, Pydantic v2, React 18, TanStack Query v5 — all existing stack; `sa.ARRAY(sa.Text())` for TEXT[] columns; zero new packages (035-business-domain-registry)
- PostgreSQL 16; Alembic migration 009 (`down_revision = "008"`): new `business_domains` table, ALTER TABLE on `business_capabilities` (add `domain_id` FK with ON DELETE SET NULL), new `value_stream_stage_capabilities` join table (035-business-domain-registry)
- Python 3.12 (backend); TypeScript 5.x (frontend) + FastAPI ≥ 0.111, SQLAlchemy 2 async (Core), asyncpg, Pydantic v2, React 18, TanStack Query v5 — all existing stack; zero new packages (036-application-registry)
- PostgreSQL 16; Alembic migration 010 (`down_revision = "009"`): 8 new tables (036-application-registry)
- Python 3.12 (backend); TypeScript 5.x (frontend) + FastAPI ≥ 0.111, SQLAlchemy 2 async (Core), asyncpg, Pydantic v2, React 18, TanStack Query v5 — all existing stack; zero new packages (038-application-portfolio-management)
- PostgreSQL 16; Alembic migrations 011–019 (`down_revision` chained 010→...→018), 8 new 1:1/link tables across US1–US8 (rationalization scores, identity, risk & compliance, TCO/cost, technical fit, roadmap + transformation initiatives, ownership & governance, quality & performance signals); `PERMISSIONS_VERSION` progressed 1.1.0 → 1.4.0 adding `READ_/WRITE_APPLICATION_{RISK,COST,GOVERNANCE}` sensitive-category gates (US3/US4/US7); US1/US2/US5/US6/US8 are non-sensitive and ride the existing `WRITE_APPLICATION` prefix rule (038-application-portfolio-management)
- Python 3.12 (backend); TypeScript 5.x + React 18 (frontend) + FastAPI ≥ 0.111, SQLAlchemy 2 async (Core), asyncpg, Pydantic v2, TanStack Query v5 — all existing stack; no LangGraph (single-prompt reviewer, not a multi-node graph); no new packages (039-agent-review-toolkit)
- PostgreSQL 16; no new tables or columns — reuses `operations.design_id` (TEXT, no FK) as a generic entity-id slot and `llm_reasoning_log.option_id` (TEXT NULL, no FK) as a generic suggestion-id slot; `PERMISSIONS_VERSION` progresses 1.4.0 → 1.5.0 adding `CONFIRM_AGENT_SUGGESTION` (trigger reuses the existing `SUBMIT_AI_OPERATION`) (039-agent-review-toolkit)
- Python 3.12 (backend); TypeScript 5.x + React 18 (frontend) + same stack as 039 — zero new packages; adds a portfolio-scope sibling to the existing per-capability Agent Review (`run_portfolio_review`/`assemble_portfolio_context` in `adp.business.agent_review`), reusing `propose_new_capability` and adding a sixth suggestion type `flag_capability_for_removal` (040-portfolio-agent-review)
- PostgreSQL 16; no new tables — new routes `POST/GET /api/v1/business/capabilities/agent-review` (no `{cap_id}` segment, so no path collision with the per-capability routes) reuse the same `OperationStore`/`SUBMIT_AI_OPERATION`/`CONFIRM_AGENT_SUGGESTION` plumbing as 039; `operations.design_id` holds a `"PORTFOLIO"` sentinel (column is NOT NULL, no single reviewed entity at this scope); accept for `flag_capability_for_removal` reuses the existing `delete_capability` (already guards against removing a capability with children) (040-portfolio-agent-review)
- Python 3.12 (backend); TypeScript 5.x + React 18 (frontend) + same stack as 039/040, plus the platform's first streaming endpoint (SSE via FastAPI `StreamingResponse`) — no new package; a new top-level `adp.chat` package (deliberately NOT an `adp.agents` adapter, since cross-domain reads violate that toolkit's zero-domain-import contract by design), extending `adp.llm.client.LLMClient` with multi-turn/streaming/tool-use support built on its existing raw-httpx pattern (041-ai-chat-assistant, plan only — not yet implemented)
- PostgreSQL 16; **two new tables** via migration 022 (`chat_conversations`, `chat_messages`) — the first schema change either Agent Review spec needed; also extends the existing `adp.search` hybrid index (ADP-b6o) with `ENTITY_APPLICATION`/`ENTITY_VALUE_STREAM`/`ENTITY_BUSINESS_DOMAIN` discriminators (no schema change there); new `ActionType.USE_CHAT_ASSISTANT` (broadly granted — sensitivity is filtered per-question inside read-only tool calls against `READ_APPLICATION_{RISK,COST,GOVERNANCE}`, not by this outer gate) (041-ai-chat-assistant, plan only — not yet implemented)
- Python 3.12 (backend); TypeScript 5.x + React 18 (frontend) + FastAPI ≥ 0.111, SQLAlchemy 2 async (Core), asyncpg, Alembic, Pydantic v2, python-jose (existing OIDC/JWT stack); React 18, TanStack Query v5, Vite 5 — all existing project dependencies; zero new packages required (042-admin-prompt-management, implemented)
- PostgreSQL 16 — two new tables (`agent_prompt_overrides`, `agent_prompt_history`) via migration 023 (`down_revision = "022"`); existing hardcoded Python prompt constants remain as the untouched fallback layer; new `PersonaRole.PLATFORM_ADMIN` + `ActionType.MANAGE_AGENT_PROMPTS`, `PERMISSIONS_VERSION` 1.6.0 → 1.7.0 (narrows the `ENTERPRISE_ARCHITECT` wildcard grant so no architect role auto-inherits the new action) (042-admin-prompt-management, implemented)
- Python 3.12 + FastAPI (lifespan hook to start/stop the background task), SQLAlchemy 2 async (Core, reusing `adp.business.store`'s existing list/get functions), `asyncio` (background task loop) — all existing project dependencies; zero new packages required (044-business-arch-export)
- PostgreSQL 16 (read-only for this feature — no new tables, no migration); filesystem (the exported JSON file tree) is the only new persisted artifact, and it is itself derived/regenerable, not a system of record (044-business-arch-export)
- Python 3.12 + FastAPI (extends the existing lifespan hook — one more background task alongside ADP-SPEC-044's), SQLAlchemy 2 async (Core, reusing `adp.application.store`'s existing bulk-list functions plus direct `Table` queries for the tables that have none — research.md Decision 4), `asyncio` (shared background-loop scaffold, research.md Decision 5) — all existing project dependencies; zero new packages required (045-application-export)
- PostgreSQL 16 (read-only for this feature — no new tables, no migration); filesystem (the exported JSON file tree) is the only new persisted artifact, sibling to ADP-SPEC-044's own (045-application-export)
- Python 3.12 (backend); TypeScript 5.x + React 18.3 (frontend, matching ADP's existing `web/` toolchain and the sibling library's own — both confirmed via direct `package.json` comparison) + Backend — FastAPI, SQLAlchemy 2 async (Core), asyncpg, Alembic, Pydantic v2, `cairosvg` (already present, reused for PNG export — Decision 3) — all existing; zero new backend packages. Frontend — two new runtime dependencies matching the vendored library's own (`@dagrejs/dagre` for auto-layout, `yaml` for DSL front-matter parsing), both pure JS with no server-side coupling; React 18/TanStack Query/Vite/Vitest/Playwright all existing. (046-diagram-type-support)
- PostgreSQL 16 — one new table (`diagrams`), no relationship to `designs` (standalone per FR-011); DSL source stored as unparsed text (a size cap, not a syntax check — Decision 2). (046-diagram-type-support)
- TypeScript 5.x + React 18.3 (frontend only — no backend touched at all, matching ADP's existing `web/` toolchain) + None new. Reuses `useAuth()` (`web/src/auth/AuthProvider.tsx`, ADP-SPEC-026) and the existing `DiagramEditorPage.tsx`/`DiagramType` (ADP-SPEC-046, ADP-914.5). (047-persona-diagram-experience)
- N/A — no new persisted data; the persona→type mapping is a static, in-memory frontend constant (mirrors the existing `ROLE_LABELS`/`ROLE_COLORS` pattern in `AuthProvider.tsx`), not a database table or part of the `Diagram` model. (047-persona-diagram-experience)
- TypeScript 5.x + React 18.3 (frontend only — no backend touched at all) + None new. Reuses the vendored `diagram-core`'s `createEmptyDiagramModel`/`addNode`/`addEdge` (`web/src/diagrams/core/model/`), the existing `web/src/api/business.ts` read hooks (`useCapabilities()`, `useValueStream()`), and `DiagramEditorPage.tsx`/`DiagramsPage.tsx` (ADP-SPEC-046, ADP-914.5). (048-generate-diagrams-from-data)
- N/A — no new persisted data; generation is a pure, synchronous, in-memory transform of already-fetched React Query cache data into a `DiagramModel`. A generated diagram, once saved, is stored identically to a hand-authored one (spec FR-008). (048-generate-diagrams-from-data)
- Python 3.12 (backend); TypeScript 5.x + React 18.3 (frontend) — both existing stacks, no new language/version surface. + None new. Reuses `adp.chat`'s existing orchestrator/router/models (ADP-SPEC-041), `web/src/chat/{ChatButton,ChatPanel}.tsx` and `web/src/api/chat.ts`'s `useSendMessage` (already generic/`basePath`-parameterized), and `DiagramEditorPage.tsx`'s existing `useDslSync`/`applyDsl` (ADP-SPEC-046). (049-ai-diagram-editing)
- No schema change. `diagram_context` is a per-request, ephemeral string — appended to that turn's system prompt only, never persisted as part of the stored `ChatMessage` (a diagram's content changes continuously; "what was in the diagram at the time of a historical message" isn't a requirement this feature needs to satisfy — see Assumptions). (049-ai-diagram-editing)
- Python 3.12 (backend); TypeScript 5.x + React 18 (frontend) — both existing stacks, no new language/version surface. + None new. FastAPI, SQLAlchemy 2 async (Core), asyncpg, Alembic, Pydantic v2, React 18, TanStack Query v5 — all existing project dependencies. (050-strategic-objective-capture)
- PostgreSQL 16 — migration 025 (`down_revision="024"`): two new tables (`strategic_themes`, `strategic_objectives`) and two new join tables (`strategic_objective_capabilities`, `strategic_objective_value_streams`), mirroring migration 008's exact join-table shape (composite PK, `ON DELETE CASCADE` on both legs, one index, `created_at`). (050-strategic-objective-capture)
- Python 3.12 (backend); TypeScript 5.x + React 18 (frontend) — both existing stacks, no new language/version surface. + None new. FastAPI, SQLAlchemy 2 async (Core, raw `sa.text()` for the aggregate query — mirroring `adp.api.routers.portfolio`'s own established pattern for this exact kind of read), Pydantic v2, React 18, TanStack Query v5 — all existing project dependencies. (051-strategy-landing-card)
- PostgreSQL 16 — no migration. Reads existing tables only (`strategic_objectives`, `strategic_themes`, `strategic_objective_capabilities`, `strategic_objective_value_streams`), all already present from migration 025 (ADP-d8u.1). (051-strategy-landing-card)
- TypeScript 5.x + React 18 (frontend only — no backend touched at all, per spec.md FR-016). + None new. Existing `web/src/ui` primitives (`Button`, `Card`, `Panel`, `StatusBadge`, `Icon`), existing token system (`web/src/ui/tokens.css`), existing vendored `web/src/diagrams/editor/*` and `web/src/diagrams/core/*` (untouched internals) — all already in the project. (052-diagram-editor-redesign)
- N/A — no data persisted or read differently; this feature changes only presentation of already-fetched diagram data. (052-diagram-editor-redesign)
- TypeScript 5.x + React 18 (frontend); Python 3.12 (backend) — both existing stacks, no new language/version surface. + None new. Reuses the already-vendored `web/src/diagrams/core/dsl/c4.ts` parser/serializer and its `dslFamilies` registry entry (`registry.ts:23`); Pydantic v2 `Literal` (backend); existing FastAPI/SQLAlchemy stack — zero new packages either side. (053-c4-diagram-type)
- No schema change. `diagrams.diagram_type` is stored as plain `TEXT` (not a Postgres enum), per migration 024 — confirmed by reading the migration directly; the value set is enforced only at the Pydantic `Literal` layer, so adding `"c4"` needs no migration at all. (053-c4-diagram-type)
- Python 3.12 (backend); TypeScript 5.x + React 18 (frontend) — both existing stacks, no new language/version surface. + None new. Backend: FastAPI, SQLAlchemy 2 async (Core), Pydantic v2 — all existing. Frontend: reuses `web/src/diagrams/editor/Canvas.tsx`/`DslPanel.tsx` (ADP-SPEC-052, unmodified), `core/dsl/c4.ts`'s `parseC4`/`serializeC4` (ADP-SPEC-053, unmodified), `web/src/canvas/c4-filter.ts`'s `filterElementsForLevel`/`filterRelationshipsForLevel` (unmodified), `web/src/inspection/InspectionPanel.tsx`/`TechnologyEditor.tsx` (unmodified) — all pre-existing. (054-c4-design-view)
- No schema change to `ArchitectureDescription`/`Element`/`Relationship` — every new endpoint reads/writes the existing `designs`/`design_versions` tables via the existing `DesignStore.save()`/`.get()`. No migration. (054-c4-design-view)

- Python 3.11+ + Pydantic v2 (entity definitions and schema emission), jsonschema 4.x (schema validation in tests) (001-canonical-data-model)

## Project Structure

```text
src/adp/          # Python backend (all modules)
tests/            # pytest unit, contract, integration tests
web/              # TypeScript/React C4 canvas (Vite)
specs/            # Speckit spec/plan/tasks per feature (001–013)
generated/        # Generated JSON Schema (do not edit by hand)
```

## Commands

```bash
# Backend
pip install -e ".[dev]"                          # install with dev deps
pytest tests/ --ignore=tests/integration -q      # unit + contract tests (no DB needed)
pytest tests/integration/                        # integration tests (requires PostgreSQL)
ruff check src/                                  # lint
mypy src/                                        # type check
adp-generate                                     # regenerate JSON schemas
adp-generate --check                             # drift gate (must exit 0 in CI)
alembic upgrade head                             # run DB migrations (from project root)
alembic current                                  # check migration state

# Web canvas
cd web && npm install
cd web && npm run dev                            # Vite dev server on :5173
cd web && npm run test:run                       # Vitest unit + component tests
cd web && npm run test:e2e:api                   # Playwright API E2E (requires API server)
cd web && ADP_WEB_URL=http://localhost:5173 npm run test:e2e  # full E2E including browser

# Run the API server
export ADP_DATABASE_URL="postgresql+asyncpg://adp_user:adp_pass@127.0.0.1:5432/adp"
uvicorn adp.api.app:app --host 0.0.0.0 --port 8001 --reload
```

## Code Style

Python 3.12 (runtime) targeting 3.11+ compatibility; follow standard PEP 8 conventions enforced by ruff.

## Recent Changes
- 054-c4-design-view: Implemented (ADP-914.12, all four user stories) — Phase B of the C4Canvas-retirement roadmap decided on ADP-914.9: a genuinely new editing surface for the *canonical* `ArchitectureDescription`/`Element`/`Relationship` model, built on the diagram tool's reused `Canvas.tsx`/`DslPanel.tsx` (ADP-SPEC-052) instead of ReactFlow, reached via a **new, separate** nav entry ("C4 Design (Preview)") placed alongside — not replacing — the existing "Canvas" item; swapping/removing that item is explicitly ADP-914.13's job, gated on this view proving out first (research.md Decision 8). Two new pieces make the vendored, ReactFlow-free editor speak the canonical model: `web/src/canvas-v2/c4Adapter.ts` (pure `Element[]`/`Relationship[]` ⇄ `DiagramModel` mapping, reusing `web/src/canvas/c4-filter.ts`'s existing level-visibility rules unchanged) and `web/src/canvas-v2/reconcile.ts` (diffs `Canvas.tsx`'s single whole-model `onChange` callback against the previous model and fires the one specific granular mutation that matches — commits immediately per action, matching C4Canvas's own existing UX, never a staged whole-design save). A real, documented UX limitation, not a bug: `Canvas.tsx`'s toolbar exposes only 4 generic `UNIVERSAL_SHAPES` for any non-flowchart family with no way to set a node's `role` — so a toolbar-added element's `ElementKind` is inferred from a fixed 1:1 shape convention (person↔circle, system↔rectangle, container↔rounded-rectangle, component↔diamond); button labels stay generic ("Add Rectangle", not "Add System") since the vendored toolbar can't be relabeled per family. New backend: `src/adp/api/routers/elements.py`, 5 granular endpoints (`POST`/`PATCH`/`DELETE` elements, `POST`/`DELETE` relationships) that are **the actual fix for ADP-914.1–.4** — those bugs' root cause, found during ADP-914.9's research, was `usePlaceElement`/`useDrawRelationship` calling a whole-design `PUT /api/v1/designs/{id}` that was never registered as a route; this feature does not resurrect that endpoint, it replaces the capability with proper per-entity mutations. Element/relationship ID generation uses max(existing)+1, not the `len+1` the recommendation orchestrator gets away with elsewhere — this is the first feature to add deletion, so a naive `len+1` after an id-gap would collide (verified with a dedicated gap-after-deletion test). `DELETE /elements/{id}` cascades to remove any relationship still referencing it first, since `ArchitectureDescription`'s own `model_validator` rejects a dangling relationship endpoint. No new tables: `design_layouts` (`layouts.py`) turned out to already be a transient in-process dict, not real persistence, so "layout migration" was just calling the same unmodified `GET/PUT .../layout/{level}` endpoints (research.md Decision 3). No new `ElementKind` values, no optimistic-concurrency adoption (matches the zero-endpoint precedent already in place), and export wires straight to the *existing* locked-theme `POST /designs/{id}/render` and `GET /designs/{id}/export/calm` endpoints rather than the new diagram tool's own client-side SVG export — preserving ADP-SPEC-010's fixed-visual-identity guarantee. Boundary/container grouping was descoped mid-plan after confirming C4Canvas never had it and the canonical model has no field for it — a real schema-scope-creep catch, with spec.md corrected in the same pass per ART-I. 1231 backend tests (was 1190, +41: 39 for `elements.py` plus 2 pre-existing), 257 frontend tests (was 228, +29: `c4Adapter.test.ts`, `reconcile.test.ts`, `C4DesignView.test.tsx`), `ruff`/`mypy`/`tsc`/`adp-generate --check` all clean — plus a full live Playwright walkthrough against real seed data (level switching, adding a shape and confirming it persisted server-side as a real `ELM-NNN` id, selecting an element to inspect/edit technology metadata, both export actions, and confirming the legacy "Canvas" screen — reading the exact same live-mutated design — remains completely untouched) with the test element cleaned up afterward. See `specs/054-c4-design-view/`. Next in the roadmap: ADP-914.13 (retire `web/src/canvas/`), gated on this view being confirmed equivalent-or-better in production use.
- 053-c4-diagram-type: Implemented (ADP-914.11, all three user stories) — Phase A of the C4Canvas-retirement roadmap decided on ADP-914.9: exposes `"c4"` as a sixth selectable `DiagramType` in the standalone diagram tool (`web/src/diagrams/`). The Mermaid-C4 parser/serializer (`core/dsl/c4.ts`) and its `dslFamilies` registry entry were already fully vendored and correct — just unreachable, since no `DiagramType` value routed to them (the already-exposed `"architecture"` type is a false friend: Mermaid's unrelated `architecture-beta` cloud/service notation). This is genuinely additive with zero coupling to ADP's canonical `Design`/`Element`/`Relationship` model (confirmed during ADP-914.9's research) and does not touch `web/src/canvas/` at all. One real implementation wrinkle: `c4` is the only multi-level family, so a brand-new diagram must seed `diagramTypeId: "c4-context"` (matching `c4.ts`'s own `LEVEL_TO_HEADER`), not the bare `"c4"` selector value — a small mapping added to `DiagramEditorPage.tsx`'s new-diagram logic. A genuine, previously-undiscovered test-coverage gap was closed in the same pass: `c4.ts` had **zero** test coverage anywhere in the repo despite `families.test.ts` covering all five other families — new `core/dsl/c4.test.ts` fills it. Six existing tests that asserted `"c4"` was *rejected* on purpose were updated to assert the opposite (that's exactly the contract this feature changes), not silently left alone. **A genuine, pre-existing bug (not introduced by this feature) was found and fixed while writing the reopen test**: `DiagramEditorPage.tsx`'s load effect applied a freshly-fetched diagram's DSL text through a *stale* `applyDsl` closure still bound to the component's initial-default type (e.g. "flowchart"), not the diagram's actual saved type — silently mis-parsing any reopened diagram whose type differed from that default. Undetected until now because every prior test fixture happened to use `"flowchart"` as both the diagram's type and the default; fixed with a two-effect split (stage the loaded text, apply it only after `diagramType` state has actually committed) and verified live in the browser for both a C4 diagram and an unrelated UML diagram. 1192 backend tests (was 1190, +2 — the two parametrized "supported type" cases gaining `"c4"`; 1190 passing, 2 pre-existing failures confirmed unrelated — one depends on live LLM-configuration state, one is a timing-sensitive performance test, neither touches any file this feature changed), 228 frontend tests (was 216, +12), `adp-generate --check` clean — plus a full live Playwright walkthrough (create → author with Person/System/SystemDb/relationships → save → reopen with full fidelity → export SVG/PNG, inspecting the real exported SVG content) against a freshly-restarted backend, not just the automated suite. See `specs/053-c4-diagram-type/`. Next in the roadmap: ADP-914.12 (build a C4 Design View replacing C4Canvas's actual editing surface) and ADP-914.13 (retire `web/src/canvas/`).
- 052-diagram-editor-redesign: Implemented (ADP-SPEC-052, all three user stories) — a presentation-only redesign of the diagram list and editor screens (`web/src/diagrams/`), closing the gap where this screen was the one place in ADP with zero custom styling — confirmed directly that **zero `.css` files existed anywhere under `web/src/diagrams/`** before this feature. Two tracks: the three ADP-authored chrome files (`DiagramListPage.tsx`, `DiagramsPage.tsx`, `DiagramEditorPage.tsx`) were rewritten onto ADP's `.ui-*` classes and shared `Button`/`StatusBadge` components (mirroring `web/src/designs/DesignsPage.tsx`), including switching `DiagramListPage.tsx` off an ad hoc `useState`/`useEffect` fetch onto new `useDiagrams()`/`useDeleteDiagram()` TanStack Query hooks in `api.ts`; the six vendored editor internals (`Canvas.tsx`, `shapes.tsx`, `DslPanel.tsx`, `useDslSync.ts`, `ConfirmDialog.tsx`, `UnsupportedElementNotice.tsx`) kept their JSX structurally unchanged — a new feature-scoped stylesheet (`diagrams.css`) supplies every class name they already referenced — except two documented, one-line **value-only** exceptions: `shapes.tsx`'s hardcoded `SELECTION_STROKE` hex swapped for `var(--accent)` (SVG presentation attributes resolve `var()` the same as a CSS declaration), and `Canvas.tsx`'s old single-character Unicode shape glyphs swapped for real `Icon` components (10 new `IconName` entries). The canvas surface now adapts to theme (`--surface-2`/`--border-strong` dot-grid), while default shape fill/stroke colors deliberately stay fixed regardless of theme, matching ADP's locked-C4-theme precedent (FR-010, resolved via clarification). The editor's palette/canvas/DSL panel are now simultaneously visible via a CSS Grid workspace layout — built on `Canvas.tsx`'s pre-existing (but previously unused) `toolbarContainer` portal prop rather than any new vendored-file change — with the palette collapsing to an overlay drawer below 900px, reusing the shell's own existing breakpoint (`ui.css` lines 42–48) rather than inventing a new one. One test-infra gap found and fixed: jsdom has no `<dialog>` `showModal()`/`close()` — added a minimal polyfill to `web/tests/setup.ts`, needed because `ConfirmDialog`/`Modal` had never been directly unit-tested before. 216 frontend tests (was 202, +14), `tsc` clean — plus a full live Playwright walkthrough (dark theme, light theme, narrow-viewport drawer, Connect active state, shape palette) confirming the rendered screens match spec, not just the automated suite. Undo/redo remains explicitly out of scope, tracked separately as ADP-914.10. See `specs/052-diagram-editor-redesign/`.


<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->


<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:970c3bf2 -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

**Architecture in one line:** issues live in a local Dolt DB; sync uses `refs/dolt/data` on your git remote; `.beads/issues.jsonl` is a passive export. See https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md for details and anti-patterns.

## Agent Context Profiles

The managed Beads block is task-tracking guidance, not permission to override repository, user, or orchestrator instructions.

- **Conservative (default)**: Use `bd` for task tracking. Do not run git commits, git pushes, or Dolt remote sync unless explicitly asked. At handoff, report changed files, validation, and suggested next commands.
- **Minimal**: Keep tool instruction files as pointers to `bd prime`; use the same conservative git policy unless active instructions say otherwise.
- **Team-maintainer**: Only when the repository explicitly opts in, agents may close beads, run quality gates, commit, and push as part of session close. A current "do not commit" or "do not push" instruction still wins.

## Session Completion

This protocol applies when ending a Beads implementation workflow. It is subordinate to explicit user, repository, and orchestrator instructions.

1. **File issues for remaining work** - Create beads for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **Handle git/sync by active profile**:
   ```bash
   # Conservative/minimal/default: report status and proposed commands; wait for approval.
   git status

   # Team-maintainer opt-in only, unless current instructions forbid it:
   git pull --rebase
   bd dolt push
   git push
   git status
   ```
5. **Hand off** - Summarize changes, validation, issue status, and any blocked sync/commit/push step

**Critical rules:**
- Explicit user or orchestrator instructions override this Beads block.
- Do not commit or push without clear authority from the active profile or the current user request.
- If a required sync or push is blocked, stop and report the exact command and error.
<!-- END BEADS INTEGRATION -->

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **ADP** (13870 symbols, 22005 relationships, 232 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> Index stale? Run `node .gitnexus/run.cjs analyze` from the project root — it auto-selects an available runner. No `.gitnexus/run.cjs` yet? `npx gitnexus analyze` (npm 11 crash → `npm i -g gitnexus`; #1939).

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows. For regression review, compare against the default branch: `detect_changes({scope: "compare", base_ref: "main"})`.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `query({search_query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `context({name: "symbolName"})`.
- For security review, `explain({target: "fileOrSymbol"})` lists taint findings (source→sink flows; needs `analyze --pdg`).

## Never Do

- NEVER edit a function, class, or method without first running `impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `rename` which understands the call graph.
- NEVER commit changes without running `detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/ADP/context` | Codebase overview, check index freshness |
| `gitnexus://repo/ADP/clusters` | All functional areas |
| `gitnexus://repo/ADP/processes` | All execution flows |
| `gitnexus://repo/ADP/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
