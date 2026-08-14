# ADP Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-08-14 (043-capability-heat-map implemented)

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
- Python 3.12 (backend); TypeScript 5.x + React 18 (frontend) — both existing stacks, no new language/version surface. + FastAPI ≥ 0.111, SQLAlchemy 2 async (Core, mirroring `adp.strategy.store`'s existing `sa.Table`/raw-`sa.text()` style — no ORM), Alembic, Pydantic v2, React 18, TanStack Query v5 — all existing project dependencies. Zero new packages either side. (915-objective-progress-tracking)
- PostgreSQL 16 — one new table (`strategic_objective_progress`), one new column set on the existing `strategic_themes` table (`description`, `owner`, `priority`), one new column set on the existing `strategic_objectives` table (`status`, `status_reason`). Migration 026 (`down_revision = "025"`). (915-objective-progress-tracking)
- PostgreSQL 16 — three new tables (`strategy_initiatives`, `strategy_initiative_objective_links`, `strategic_objective_dependencies`). Migration 027 (`down_revision = "026"`). (916-strategy-initiatives-dependencies)
- Python 3.12 (backend); TypeScript 5.x + React 18 (frontend) — both existing + FastAPI ≥ 0.111, SQLAlchemy 2 async (Core, mirroring `adp.strategy.store`'s (917-objective-design-traceability)
- PostgreSQL 16 — two new join tables via migration 028 (`down_revision = "027"`), no (917-objective-design-traceability)
- Python 3.12 (backend); TypeScript 5.x + React 18 (frontend) — both existing + FastAPI ≥ 0.111, SQLAlchemy 2 async (Core, mirroring `adp.strategy.store`'s and (918-strategy-rollups)
- PostgreSQL 16 — no migration. Every new/enriched endpoint reads existing tables (918-strategy-rollups)
- Python 3.12 (backend); TypeScript 5.x + React 18 (frontend) — both existing stacks, no + FastAPI ≥ 0.111, SQLAlchemy 2 async (Core, raw `sa.text()` mirroring (919-insights-dashboard)
- PostgreSQL 16 — no migration. The new endpoint reads the existing `applications` table (919-insights-dashboard)
- TypeScript 5.x + React 18 — frontend only, no backend touched at all (confirmed by the + None new. Reuses the existing `useCapabilities()` hook and `BusinessCapability`/ (043-capability-heat-map)
- N/A — no new persisted data, no migration. Reads the existing `business_capabilities` table (043-capability-heat-map)

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
- 043-capability-heat-map: Implemented (ADP-3up.1, all three user stories) — a "Heat Map" tab on the
  Business Architecture screen: every business capability as one cell in the same flat L1/L2/L3 hierarchy
  as the existing capability tree (FR-002, resolved via `/speckit-clarify` — no domain grouping), shaded by
  a selectable metric (maturity level, default, or strategic relevance). **A stale-branch incident, not a
  code issue**: the feature's own branch (`043-capability-heat-map`) was created 2026-08-04 and had sat
  untouched — checking it out mid-session reverted the working tree 28 commits, making every spec from 044
  onward appear to vanish (they were never lost, just not on that old branch tip); fixed with a user-
  authorized `git reset --hard main` before continuing, since the branch had zero unique commits to lose
  (the spec draft itself was always uncommitted working-tree content). **The headline research finding**:
  this needed zero backend changes — direct reads of `src/adp/business/router.py`'s existing
  `GET /capabilities` handler and `BusinessCapability` model confirmed every field the heat map needs
  (`level`, `parent_id`, `position`, `strategic_relevance`, `maturity_level`) was already returned,
  unfiltered, by the same endpoint `CapabilityTree.tsx` already calls — the smallest-footprint feature of
  the session, one new component plus three small, additive edits to already-existing files. Reuses the
  already-exported `buildTree()` for hierarchy construction rather than a second tree-builder, and reuses
  `web/src/insights/ApplicationsHeatMap.tsx`'s (919, this session) swatch/dimension-selector pattern
  directly. A second real correction, found during planning research rather than assumed: spec.md's "drill
  into that capability's existing detail view" (US3) doesn't map to any actual separate screen — capabilities
  have no detail page the way Value Streams/Domains do — resolved as a scroll-and-highlight to the
  capability's existing (always-expanded) row in the tree, not a new page, documented as a research.md
  decision rather than requiring a spec rewrite since it's an implementation-level fact, not a scope change.
  A minor UI bug (`"52 capabilityies"`, a naive `+ "ies"` pluralization) was caught and fixed live during
  the browser walkthrough, not by any test. 312 frontend tests (was 301, +11), backend suite unaffected at
  1378 (zero backend files touched), `ruff`/`mypy`/`tsc`/`adp-generate --check` all clean — plus a full live
  Playwright walkthrough (default maturity coloring, the metric switch to strategic relevance, and a real
  drill-through click landing on and highlighting the correct row with its live-edited values, using
  real seeded-then-cleaned-up capability data). See `specs/043-capability-heat-map/`.
- 919-insights-dashboard: Implemented (ADP-t3h, all three user stories) — the first genuinely
  non-architect-facing screen in ADP: a new "Insights" nav entry (sibling to Overview, not under the
  architect-facing Architecture section) holding an applications heat map, one cell per application,
  color-coded by a user-selectable dimension. **Not bead-driven from a source requirements doc like every
  other feature this session** — this one started from a deferred persistent-memory note
  (`adp-non-architect-visualization-layer`) capturing an earlier open architecture question; a real
  `AskUserQuestion` resolved the two genuinely open scope questions before any spec was written: the first
  visualization is a cross-domain applications heat map (health score / business criticality / TIME
  classification / cost), not the already-planned-but-unbuilt capability heat map (`ADP-3up.1`); and it
  ships fully independent of both `ADP-3up.1` and this session's own `918-strategy-rollups` heat map, with
  any future cross-linking left an explicit later decision. A real, open, architect-scoped epic (`ADP-3up`
  — six capability-visualization patterns, only the heat map ever drafted, left Paused on 2026-08-05) was
  discovered mid-research and explicitly addressed as a Ground-Truth Correction rather than silently
  ignored or assumed subsumed. The one genuinely new access-control shape in this feature: three of the
  four coloring dimensions are already-open reads, but cost is sensitive (`READ_APPLICATION_COST`) — rather
  than a route-level gate that would block the other three dimensions for a cost-denied caller, the cost
  check happens inline per request (`is_permitted(user.role, ActionType.READ_APPLICATION_COST)`), mirroring
  `adp.chat.tools.get_application_cost`'s (ADP-SPEC-041) existing inline-check precedent — confirmed
  correct live via a real Playwright walkthrough switching a REVIEWER-lacking-cost view against an
  ENTERPRISE_ARCHITECT-holding-cost view. The single new endpoint (`GET /portfolio/applications-heatmap`)
  returns every dimension for every application in one response (not one fetch per dimension), so switching
  the selector client-side recolors with zero network round-trip — a deliberate research.md decision, not
  an afterthought. Reuses `ApplicationCost.tco` (the existing computed total-cost-of-ownership field) via a
  new small `adp.application.store.list_all_costs()` bulk helper, added specifically to avoid duplicating
  the eight-bucket TCO formula in raw SQL. No new backend package (extends `adp.portfolio`, already the
  established cross-domain no-new-table aggregator) and no migration — a pure read projection over
  `applications`/`application_cost`, both already present from ADP-SPEC-038. 1378 backend tests (was 1375,
  +3), 301 frontend tests (was 292, +9), `ruff`/`mypy`/`tsc`/`adp-generate --check` all clean — plus a full
  live Playwright walkthrough (the new nav entry's placement confirmed via DOM order, all four coloring
  dimensions including a real seeded-then-cleaned-up cost record computing the correct $350,000 TCO,
  business-criticality's all-"Unclassified" rendering since that field isn't seeded in the demo data at
  all) against a running local stack, test data cleaned up afterward via a direct DB delete (no API delete
  path exists for a cost record). See `specs/919-insights-dashboard/`.
- 918-strategy-rollups: Implemented (ADP-d8u.7, all three user stories) — three read-only rollups composed entirely from existing data, no new tables anywhere. **A significant ground-truth correction confirmed before writing the spec**: the source doc's "Strategy stat tile + domain card on Overview" was already shipped in ADP-d8u.3 (PR #62, predating this bead) — confirmed via direct reads of `OverviewPage.tsx` and `strategy/router.py`'s existing `/summary` endpoint; this feature only enriches that endpoint's existing data, adding no new card. US1 — `GET /strategy/heatmap`, a theme × status matrix (resolved via a real clarification: full matrix with an optional single-theme filter, not a flat breakdown), new "Heat Map" tab on `StrategyPage.tsx`. US2 — `GET /business/orphans` (capabilities/value streams with zero strategic linkage), surfaced as both a badge and a toggle filter on the existing Capability Map and Value Streams screens (also a real clarification: both, not either alone) — implemented via a new pair of lightweight read-only mirror tables in `adp.business.store` (`_strategic_objective_capabilities`/`_strategic_objective_value_streams`), the exact symmetric counterpart to ADP-d8u.2's own `_designs`/`_applications` mirrors in `adp.strategy.store`, confirming that pattern generalizes cleanly in the reverse direction. US3 — enriches the *existing* `GET /strategy/summary` with a 5-way objective status breakdown and an initiative count (both of this bead's stated dependencies, ADP-d8u.5 and ADP-d8u.6, are now merged, so the initiative count ships unconditionally rather than the source doc's deferred fallback). Status isn't a column any SQL `GROUP BY` can compute (`compute_status()` derives it from progress-history trend, ADP-d8u.5) — both the heat map and the enriched summary reuse `list_objectives()`'s own established per-row `_status_for_objective()` loop rather than duplicating that logic in SQL, a design decision carried straight from research.md, not discovered mid-implementation. One implementation-time consequence handled carefully: `get_summary_stats()`'s existing tests mocked a single Postgres-only `session.execute()` call (real NOW()/EXTRACT() SQL, untestable against SQLite) — adding the second, Python-side status-tally query required extending those mocks (not just adding new ones) so both the atomic-aggregate path and the tally path stay independently verifiable; the tally itself (`_tally_objective_statuses`) is tested directly against a real SQLite fixture, mirroring `_reaches()`'s own precedent from ADP-d8u.6 of splitting out the portable, no-Postgres-syntax piece for direct testability. No new package on either side of this feature — `adp.strategy`'s three core files (1,889 lines pre-feature) and `adp.business`'s (2,847 lines, exactly the historical split threshold) both stayed under their extend-vs-split thresholds, since neither addition introduces a new domain concept. 1375 backend tests (was 1327 before ADP-d8u.2/.6/.7 combined, +20 for this feature specifically), 292 frontend tests (was 265 before this trio, +9 for this feature), `ruff`/`mypy`/`tsc`/`adp-generate --check` all clean — plus a full live Playwright walkthrough (the heat-map matrix and its theme filter, the orphan badge appearing/disappearing correctly around a real link/unlink, the toggle filter, and the enriched Overview card's new at-risk/on-track split and initiative count) against a running local stack, test data cleaned up afterward. See `specs/918-strategy-rollups/`.


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

This project is indexed by GitNexus as **ADP** (15101 symbols, 24370 relationships, 225 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

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
