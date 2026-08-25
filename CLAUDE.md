# ADP Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-08-19 (926-framework-versioning-correction COMPLY-01a implemented)

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
- `ExtractedProposal` records stored transiently in ADP-SPEC-003's operation store (TTL 24h); confirmed requirements written to the canonical store via ADP-SPEC-002 `DesignStore`; as of ADP-3ei, every submission (incl. raw source text) and every proposal + confirm/reject decision is additionally captured durably, linked to `design_id`, in `intake_submissions`/`intake_proposals` — source text is no longer discarded after extraction (006-requirements-intake)
- Python 3.11+ + `langgraph>=0.2` (step orchestration with inspectable state), `langchain-core>=0.2` (Pydantic structured output tooling for LLM responses); same LLM client as ADP-SPEC-006 (`httpx>=0.27`, configurable endpoint); `opentelemetry-sdk>=1.25` (already in stack) (007-recommendation-engine)
- `SolutionOption` records stored transiently in ADP-SPEC-003's operation store (TTL 24h); accepted option materializes `Element`/`Relationship` records into ADP-SPEC-002 `DesignStore`; as of ADP-3ei, every run and every option (incl. rejections, which previously left no durable trace at all) is additionally captured durably, linked to `design_id`, in `recommendation_runs`/`recommendation_options` (007-recommendation-engine)
- Python 3.11+ + `langgraph>=0.2` (already in stack from ADP-SPEC-007); same LLM client as ADP-SPEC-006/007 (`httpx>=0.27`); `opentelemetry-sdk>=1.25` (already in stack); `asyncio.gather` for critic fan-out (no additional deps) (008-llm-as-judge)
- `Verdict` stored transiently in ADP-SPEC-003's operation store (TTL 24h) while a run is in flight; as of ADP-3ei, `ValidationOrchestrator` is wired to a real API for the first time (`POST/GET /api/v1/designs/{id}/validate`, `POST .../validate/{op_id}/override`) — previously it had zero HTTP wiring and only ran in unit tests. Every verdict + finding + override is additionally captured durably, linked to `design_id`, in `validation_verdicts`/`validation_findings` (008-llm-as-judge)
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
- TypeScript 5.x + React 18 (frontend only — no backend touched at all). + None new. Reuses `generateFromCapabilitySubtree`'s own sibling `generateFromCapabilities()` (new, `web/src/diagrams/generators.ts`), the existing `useCapabilities()` hook, and `CapabilityTree.tsx`/`CapabilityNode.tsx` (043/048/052, extended not replaced). (920-capability-diagram-select)
- N/A — no new persisted data; selection is component-local, transient `useState` in `CapabilityTree.tsx`, discarded on unmount (tab switch) by design. (920-capability-diagram-select)
- Python 3.12 (backend); TypeScript 5.x + React 18 (frontend) — both existing stacks. + FastAPI ≥ 0.111, SQLAlchemy 2 async (Core), asyncpg, Pydantic v2, React 18, TanStack Query v5 — all existing project dependencies; zero new packages. (ADP-8xo)
- PostgreSQL 16 — no migration. One new endpoint (`GET /portfolio/application-capability-groups`) reads the existing `application_capability_links`/`business_capabilities` tables; the other 4 dimensions read the existing `applications` table via the existing `GET /applications`. (ADP-8xo)
- TypeScript 5.x + React 18 (frontend only — no backend touched at all). + None new. Reuses `groupApplications()` (ADP-8xo) per axis rather than reimplementing bucketing for two dimensions; styling mirrors `web/src/strategy/StrategyHeatMap.tsx`'s existing `<table>` matrix precedent. (ADP-3wa)
- N/A — no new persisted data; second dropdown's dimension is component-local `useState` in `PortfolioPage.tsx`, same lifecycle as the first. (ADP-3wa)
- TypeScript 5.x + React 18 (frontend only — no backend touched at all). + None new. Reuses `groupApplications()`/`bucketsFromResult()` (ADP-8xo/ADP-3wa) as the value source for "Filter by" -- a filter value's app list is just one bucket's `.apps`. (ADP-9ye)
- N/A — no new persisted data; filter field/value are component-local `useState` in `PortfolioPage.tsx`. (ADP-9ye)
- Python 3.12 (backend); TypeScript 5.x + React 18 (frontend) — both existing stacks + FastAPI ≥ 0.111, SQLAlchemy 2 async (Core), asyncpg, Alembic, Pydantic v2, React 18, TanStack Query v5 — all existing stack; zero new packages (921-compliance-framework-registry)
- PostgreSQL 16 — two new tables (`regulatory_frameworks`, `controls`) via migration `032` (down_revision `031`, confirmed against the real on-disk chain — research.md D7); self-referencing FK with `ON DELETE CASCADE` (D2); composite `UNIQUE(framework_id, code)` (D6) (921-compliance-framework-registry)
- PostgreSQL 16 — five new tables (`control_capability_mapping`, `control_application_mapping`, `control_design_mapping`, `control_pattern_mapping`, `control_organization_mapping`) via migration `033` (down_revision `032` — research.md D8); `ON DELETE CASCADE` on every FK leg (both `control_id` and each target leg); composite PKs on the four entity-targeted tables, single-column PK on the estate-wide table (research.md D1); named `CHECK` constraints on `compliance_status` per table (922-control-mappings)
- Python 3.12 (backend only — no frontend file touched) + None new. Adds `compute_compliance_status()` (pure, no I/O) and `get_entity_compliance_status()` (thin async dispatch) to the already-existing `adp.compliance.store` (COMPLY-01/COMPLY-02), reusing its existing `list_mappings_for_{capability,application,design,pattern}()` functions and the existing `ComplianceStatus`/`MappingTargetType` enums from `adp.compliance.models` — zero new packages. (923-derived-compliance-status)
- PostgreSQL 16 — no migration. Reads the five existing `control_*_mapping` tables (migration `033`, COMPLY-02) exclusively through already-existing store functions; this feature owns no SQL of its own. (923-derived-compliance-status)
- Python 3.12 (backend); TypeScript 5.x + React 18 (frontend) — both existing stacks + None new. FastAPI ≥ 0.111, SQLAlchemy 2 async (Core, raw `sa.select()` joins mirroring `adp.compliance.store`'s existing `Table()`-object style), Pydantic v2, React 18, TanStack Query v5 — all existing project dependencies. (924-compliance-rollup-reporting)
- PostgreSQL 16 — no migration. Both new endpoints read the existing `regulatory_frameworks`/`controls`/`control_*_mapping` tables (migrations 032/033) via two new JOIN queries in `adp.compliance.store`. (924-compliance-rollup-reporting)
- Python 3.12 (backend); TypeScript 5.x + React 18 (frontend) — both existing stacks + FastAPI ≥ 0.111, SQLAlchemy 2 async (Core), asyncpg, Alembic, Pydantic v2, React 18, TanStack Query v5 — all existing project dependencies; zero new packages (925-strategy-compliance-linkage)
- PostgreSQL 16 — six new tables via migration `034` (down_revision `033`): `objective_control_links` (a bare Objective↔Control link) plus five parallel `initiative_control_{capability,application,design,pattern,organization}_mapping` tables, each with a composite FK against its corresponding `control_*_mapping` table's own composite PK (research.md D1) (925-strategy-compliance-linkage)
- Python 3.12 (backend only — no frontend file touched, per the resolved data-model-and-API-only scope decision) + FastAPI ≥ 0.111, SQLAlchemy 2 async (Core), asyncpg, Alembic, Pydantic v2 — all existing project dependencies; zero new packages (926-framework-versioning-correction)
- PostgreSQL 16 — one migration (`035`, down_revision `034`): seven additive columns on `regulatory_frameworks` (`regulation_number`/`celex_number`/`adoption_date`/`oj_publication_date`/`entry_into_force_date`/`consolidated_as_of`/`status`, zero existing columns altered), plus two new `String(36)`-keyed, `ON DELETE CASCADE` child tables (`framework_application_phase`, `framework_amendment`) (926-framework-versioning-correction)

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
- 926-framework-versioning-correction: Implemented (COMPLY-01a, a correction to COMPLY-01's
  already-shipped, already-populated `RegulatoryFramework` entity) — full `/speckit.specify` →
  `/speckit.plan` → `/speckit.tasks` → `/speckit.implement` cycle sourced from an addendum document
  (`docs/compliance_update.md`) explicitly flagged by the user as generated outside this codebase
  ("take it as guidance, the specifics are probably not aligned with our reality"). That caution
  was warranted: the document's own justification claimed the field being replaced is `NUMERIC`
  (it's actually `VARCHAR(100)` free text, already holding real citation strings for all three
  currently-tracked frameworks — GDPR's own value already crams two OJ citation dates into one
  string); its draft schema used `Integer` autoincrement PKs (this codebase uses `String(36)` UUIDs
  everywhere, no exception found) and a field, `official_title`, that doesn't exist (the real field
  is `name`, left untouched); `source_url` was drafted as new when it already exists (and was
  already hardened against `javascript:`-scheme injection in an earlier security review this
  session); and its own "out of scope" section named the wrong screen ("Governance & Standards")
  for a wrong-screen mix-up already caught twice earlier this session from other source documents
  making the identical assumption. All five were corrected by direct code inspection before any
  requirement was written, recorded as Ground-Truth Corrections in spec.md rather than left as
  guessed specifics. Extends (not replaces) `RegulatoryFramework` with a regulation identity, four
  independent legal-event dates, and a directly-set status (`in_force`/`amended`/`repealed`/
  `not_yet_applicable` — deliberately not derived: neither new child concept records a repeal
  event, so partial derivation would always be wrong for one of the four values), plus two new
  one-to-many concepts: `FrameworkApplicationPhase` (staged rollout dates, e.g. the EU AI Act's
  phased application) and `FrameworkAmendment` (supplementing legal instruments, e.g. DORA's
  growing RTS stack). `RegulatoryFrameworkDetail` nests both new lists alongside its existing
  `controls`, reusing that precedent rather than inventing a new response shape. Two real scope
  questions were put to the user directly rather than guessed: what happens to the three real
  frameworks' existing `version` text (resolved: preserved untouched, new fields optional and
  filled in over time — nothing is auto-parsed or deleted, since GDPR's string alone mixes two
  distinct dates with no consistent delimiter to programmatically split) and whether this pass
  includes the Compliance screen's UI (resolved: data-model-and-API-only — `FrameworkForm.tsx`/
  `FrameworkDetail.tsx` are untouched, UI surfacing is explicit follow-on). One implementation-time
  correction, caught by checking a pre-existing test file before assuming a design was safe: the
  store-layer `status` column needed a Python-side `default=` (not just the migration's
  `server_default=`), since `test_compliance_status.py`'s own fixture does a raw
  `_frameworks.insert()` bypassing `create_framework()` entirely and would otherwise have broken on
  a `NOT NULL` column with no client-side default — caught and fixed before it became a real
  regression, confirmed by that exact test still passing unmodified. 1642 backend tests (was 1612,
  +30: 17 unit, 11 contract, 2 authz), `ruff`/`mypy`/`adp-generate --check` all clean (no frontend
  file touched, so no frontend suite change). 3 Docker-gated integration tests written (Docker
  unavailable in this environment, same constraint every COMPLY-0x spec on this branch has hit) —
  will run in CI. Verified live against the real local Postgres and running backend, migration
  applied directly against the three real, live, already-populated frameworks with a byte-for-byte
  before/after field comparison (not just unit-tested against synthetic data) confirming zero data
  loss — the load-bearing guarantee this entire spec exists to uphold — plus a full walkthrough of
  every quickstart.md scenario (legal-date recording, duplicate-`regulation_number` 409, staged
  application phases ordered correctly, an unlimited amendment stack, cascade delete, and the
  nested detail response) via direct API calls against the running backend, with GDPR's temporary
  test edit fully cleared back to its original state and all temporary test frameworks deleted
  afterward, confirmed by framework count returning to exactly 3. See
  `specs/926-framework-versioning-correction/`.
- 925-strategy-compliance-linkage: Implemented (COMPLY-05, the fifth and final spec of the
  Compliance Domain bundle) — full `/speckit.specify` → `/speckit.plan` → `/speckit.tasks` →
  `/speckit.implement` cycle linking the Compliance domain (COMPLY-01–04:
  `RegulatoryFramework`/`Control`/`ControlMapping`/derived status/rollups) back to the existing
  Strategy domain, via two independent traceability links: `ObjectiveControlMapping` ("why does
  this objective exist" — a bare link from a `StrategicObjective` to a `Control`) and
  `InitiativeControlMapping` ("the remediation loop" — a `StrategyInitiative` linked to a
  specific, already-assessed `ControlMapping`, so a `compliance_status` change becomes
  attributable to real closed work). The bundle's third, lower-priority link
  (`ThemeFrameworkMapping`) was explicitly deferred by the user during `/speckit.specify` and
  tracked as bead `ADP-1ox`, not built here. A real ground-truth correction was found and
  resolved before any code was written, not assumed: the bundle described
  `InitiativeControlMapping` as referencing one `control_mapping_id`, but COMPLY-02 actually
  implemented `ControlMapping` as five separate physical tables with composite PKs and no
  synthetic id — resolved by mirroring COMPLY-02's own five-parallel-tables shape one level up,
  each with a **composite** `ForeignKeyConstraint` against its corresponding `control_*_mapping`
  table's own composite PK (research.md D1; migration `034`, six tables total — one bare
  `objective_control_links` plus five `initiative_control_{capability,application,design,
  pattern,organization}_mapping` tables). Both link types live in `adp.strategy` (extending
  `store.py`/`initiatives.py`), not `adp.compliance` — the exact package-placement precedent
  ADP-d8u.2 already established for "Strategy reaches into a foreign domain" via
  `objective_design_links`/`objective_application_links` — with reverse-lookup routes on
  `adp.compliance.router` importing `adp.strategy.store`/`adp.strategy.initiatives` through a new
  `_get_strategy_session()` dependency, mirroring `adp/api/routers/designs.py`'s own
  cross-package reverse-lookup precedent verbatim. `adp.strategy.store` gained read-only mirrors
  of the Compliance schema (`_controls_mirror` plus five `control_*_mapping` mirrors, the latter
  carrying `compliance_status`/`evidence_ref`/`assessed_at` columns, not just keys) so an
  Initiative's linked-mapping status is always read live via JOIN on every request (research.md
  D3) — the link tables themselves carry no status column at all, making FR-008's
  never-drifts guarantee structural rather than a syncing job. Zero new `ActionType`, zero
  `PERMISSIONS_VERSION` bump — both link types reuse `WRITE_BUSINESS_ARCH`, already held by the
  identical persona set as `WRITE_COMPLIANCE`; the one new authz surface is the
  Application-targeted Initiative reverse-lookup route inheriting `READ_APPLICATION_GOVERNANCE`
  via a decorator-level `dependencies=[Depends(_require_governance_read)]` (spec.md FR-013,
  mirroring `adp.application.router`'s own precedent exactly — refactored into this shape during
  implementation after the original inline per-request check was found to force premature
  DB-session resolution ahead of the permission check, which would have broken
  `tests/authz/test_enforcement.py`'s explicit no-DB-required design). Frontend: a sixth "Linked
  Controls" section on `ObjectiveDetail.tsx` (`ObjectiveControlLinkEditor.tsx`) and a new "Linked
  Compliance Gaps" section in `InitiativeList.tsx`'s edit form (`InitiativeControlMappingEditor.tsx`,
  showing each linked gap's live status badge); `ControlTree.tsx` gained matching read-only
  reverse-lookup lines ("Regulatory driver for: …", "Remediation: …") on both the control row and
  each mapping row. 1612 backend tests (was 1609, +3: 3 authz), 527 frontend tests (was 519 after
  US1, +8 for US2's `ObjectiveControlLinkEditor.test.tsx`; 519 itself was 511 +8 for US1's own
  `InitiativeControlMappingEditor.test.tsx`), `ruff`/`mypy`/`tsc`/`adp-generate --check` all
  clean. Docker was unavailable in this environment (same constraint 921–923 hit), so the
  testcontainers-gated integration suite (6 tests covering real composite-FK cascade behavior
  across all four delete directions) is written and will run in CI but wasn't executed locally;
  verified instead via the full SQLite-backed unit/contract suites plus a complete live
  walkthrough against a real local Postgres and running backend/frontend: created a temporary,
  clearly-named test Framework/two Controls/Application/Objective/Initiative, confirmed the
  remediation-loop link (zero Objective involved), confirmed the live status update flowed
  through the link with zero writes to the link itself, confirmed both reverse lookups from the
  Control's own side, confirmed multiplicity (one Objective linked to two Controls) and the 409
  duplicate-link/404 missing-target paths, confirmed cascade delete (Control removal orphans the
  link, not the Objective), then a full browser walkthrough via Playwright of both new editor UIs
  (including linking live through the actual form, not just via curl) and both `ControlTree.tsx`
  reverse-lookup lines rendering correctly — all test data cleaned up afterward, confirmed by
  count back to the three real pre-existing frameworks (GDPR, EU AI Act, DORA) and original
  objective/initiative counts. See `specs/925-strategy-compliance-linkage/`.
- 924-compliance-rollup-reporting: Implemented (COMPLY-04, the read-side rollup spec of the
  Compliance Domain bundle, building directly on 921/922/923) — full `/speckit.specify` →
  `/speckit.plan` → `/speckit.tasks` → `/speckit.implement` cycle for two new read-only aggregate
  endpoints in `adp.compliance`: `GET .../frameworks/{id}/rollup` (US1, a framework × status
  matrix — a live count of entities at each of the five `ComplianceStatus` buckets, scoped to that
  framework's own controls, plus its estate-wide obligation status as a separate line when one
  exists) and `GET .../summary` (US2, platform-wide framework count / overall coverage % / at-risk
  count, backing a new sixth "Compliance" domain card on the Overview dashboard). Both directly
  mirror already-shipped precedents rather than inventing a new pattern:
  `918-strategy-rollups`' theme × status matrix (`GET /strategy/heatmap`, since `ComplianceStatus`
  isn't SQL-aggregable any more than `ObjectiveStatus` was) and `051-strategy-landing-card`'s
  Overview card. Both reuse COMPLY-03's `compute_compliance_status()` unmodified via one new
  shared `_bucket_entities_by_status()` helper — the only thing that differs between the two
  endpoints is which rows they feed it (framework-scoped vs. estate-wide). Two real ground-truth
  corrections to the source bundle were found and confirmed against the actual codebase before
  scoping, not assumed: one of the bundle's three "What to build" bullets (entity-level
  traceability) was already fully delivered by COMPLY-02's reverse-lookup endpoints, so this spec
  did not rebuild it; and the bundle's stated home for this feature ("the Governance & Standards
  screen... already claims a rollup") didn't hold — no such caption exists, and Governance's own
  `ComplianceTab.tsx` is an unrelated, already-shipped LLM-Judge validation-exceptions view (a
  naming collision already flagged during COMPLY-02) — the rollup views live on the dedicated
  Compliance screen instead. A real clarification was put to the user rather than guessed: whether
  Application-targeted entities should be excluded from, or included in, the new aggregate rollup
  counts for a caller lacking `READ_APPLICATION_GOVERNANCE` — resolved to exclude, mirroring
  COMPLY-02's own forward-lookup filtering precedent exactly, though implemented as
  filter-*before*-aggregate rather than filter-after-fetch (research.md D2), since aggregation
  happens inside the store layer here, unlike COMPLY-02's own non-aggregating forward lookup. One
  emergent, non-obvious property surfaced and explicitly tested rather than silently accepted:
  because `compute_compliance_status()` resolves any nonempty status list containing
  `NOT_ASSESSED` to `PARTIAL` (its own existing rule), the rollup's `not_assessed_count` bucket is
  structurally always zero — the only way an entity reaches `NOT_ASSESSED` is having zero mapped
  controls at all, which never produces a row to bucket in the first place; documented with a
  dedicated invariant test rather than left as an unexplained always-zero field. 1579 backend tests
  (was 1560, +19: 14 unit, 5 contract), 511 frontend tests (was 505, +6), `ruff`/`mypy`/`tsc`/
  `adp-generate --check` all clean. Verified live end-to-end against a live local Postgres and a
  running backend/frontend via Playwright: read the real rollup for an existing user-created GDPR
  framework (correctly all-zero, no stray obligation line), created a temporary, clearly-named
  test framework mapped to a real Application (non-compliant) and an estate-wide obligation
  (partial), confirmed both the rollup and the summary card reflected it correctly (non-compliant
  count 1, organization line "Partial" shown separately, coverage 0%, at-risk 1, framework count
  incremented), confirmed 404 for an unknown framework, then cleaned up — leaving the user's three
  real pre-existing frameworks (GDPR, EU AI Act, DORA) completely untouched, confirmed by name
  after cleanup. The Overview dashboard's new Compliance card was confirmed live too, including
  the FR-009 `null`-coverage-renders-as-"—" behavior (not a misleading "0%") and the deep-link tile
  correctly landing on the dedicated Compliance screen, not Governance. See
  `specs/924-compliance-rollup-reporting/`.
  Domain bundle, building directly on 921's `RegulatoryFramework`/`Control` registry and 922's
  `ControlMapping` traceability links) — full `/speckit.specify` → `/speckit.plan` → `/speckit.tasks`
  → `/speckit.implement` cycle for a pure `compute_compliance_status()` aggregation function
  (minimum-aggregation, mirroring the Health rubric's `MIN()` and
  `adp.strategy.store.compute_status()`'s own precedent for a derived-status pure function — one
  Non-Compliant control anywhere dominates the result rather than being averaged away) plus a thin
  `get_entity_compliance_status()` async dispatch wrapper that gathers a real Capability/
  Application/Design/Pattern's current `ControlMapping` statuses via COMPLY-02's already-existing
  `list_mappings_for_*` functions and forwards them to it. One real gap in the source bundle's own
  proposed aggregation rule was found and resolved with the user during `/speckit.specify`, not
  guessed at: what an entity whose every mapped control is Not Applicable (none Compliant) should
  derive to — the bundle's own Open Questions section named this exact hole without resolving it.
  Resolved to a distinct `NOT_APPLICABLE` outcome, not folded into `NOT_ASSESSED`, so "this
  framework doesn't apply here" reads differently from "nobody has looked yet." No new table, no
  new endpoint — deliberately scoped per the bundle's own stated implementation order
  ("`compute_compliance_status()` should be built and tested as a standalone pure function before
  it's wired into any store or router"); a caller is explicit future work, expected in COMPLY-04.
  `get_entity_compliance_status()`'s `entity_type` dispatch is restricted to the four
  FK-enforced, entity-targeted mapping types — `ORGANIZATION` (the estate-wide scope COMPLY-02 also
  supports) has no per-entity lookup at all and raises `ValueError` rather than silently returning a
  status, since it has no natural per-entity status to derive (that's COMPLY-04's framework-wide
  rollup concern instead). Both new functions live in `adp.compliance.store` (not `models.py`),
  matching the direct precedent of `compute_status()` (`adp.strategy.store`) and
  `compute_business_value_score()` (`adp.application.store`) — both store-layer despite being
  I/O-free. **A deliberate deviation from the task list's literal micro-sequencing, recorded rather
  than silently patched over**: tasks.md called for landing the aggregation's branches incrementally
  with `NotImplementedError` placeholders between each user-story phase (a "walking skeleton"
  pattern); all tests were still written first per spec.md's user stories and confirmed to fail
  (`ImportError`, since neither function existed yet) before implementation, but the five-branch
  decision table was then implemented in one pass rather than three separate edits, since an
  intentionally-wrong intermediate state added no genuine incremental-risk-reduction value for a
  function this small. New `tests/unit/compliance/test_compliance_status.py` (16 tests: the full
  status-combination matrix, a determinism/order-independence check, and a parametrized end-to-end
  dispatch test across all four entity types using an in-memory SQLite fixture mirroring
  `tests/contract/test_compliance_mappings_api.py`'s own `cstore._metadata.create_all()` pattern —
  no Docker/testcontainers needed for this feature at all, unlike 921/922's integration suites).
  1542 backend tests (was 1526, +16), `ruff`/`mypy` both clean. Verified live against a real local
  Postgres (available in this environment, unlike 921/922's own sessions) rather than relying on
  the SQLite fixture alone: created a temporary `RegulatoryFramework`/two `Control`s, mapped both to
  a real seeded `Application` (Compliant + Non-Compliant), confirmed `NOT_ASSESSED` before mapping
  and `NON_COMPLIANT` after, confirmed `ORGANIZATION` correctly raises against a real DB session,
  then deleted the mappings/controls/framework and confirmed zero leftover rows. See
  `specs/923-derived-compliance-status/`.
  compliance-domain diff (921/922/923 combined). A 2-phase agent process (identify → independently
  re-verify with false-positive filtering, confidence ≥ 8/10 required to survive) confirmed one
  real finding: `RegulatoryFramework.source_url` (COMPLY-01) had no scheme validation anywhere —
  `web/src/compliance/FrameworkDetail.tsx` rendered it directly as `<a href={source_url}>`, so a
  `WRITE_COMPLIANCE`-holding user (Solution/Technical Architect and above) could plant a
  `javascript:...` payload that executes in any other authenticated user's browser on click
  (framework reads are open to everyone; React's default escaping does not cover dangerous URI
  *schemes* in attribute values, only markup injection — confirmed from first principles, not
  React's general reputation). Fixed both ends: `adp.compliance.models` now rejects any
  `source_url` whose scheme isn't `http`/`https` via a new shared `_validate_source_url()` field
  validator on both `RegulatoryFrameworkCreate`/`Update` (8 new backend tests); `FrameworkDetail.tsx`
  additionally never renders the link unless `isHttpUrl()` confirms the scheme client-side too — a
  defense-in-depth backstop for any row that predates the validator or reached the database by a
  path other than these two models (2 new frontend tests). 1551 backend tests (was 1542, +9), 505
  frontend tests (was 503, +2), `ruff`/`mypy`/`tsc`/`adp-generate --check` all clean, plus a live
  check against real Postgres confirming both `Create` and `Update` reject a `javascript:`/`data:`
  payload and accept `https://`.
  bundle, building directly on 921's `RegulatoryFramework`/`Control` registry) — full `/speckit.specify`
  → `/speckit.plan` → `/speckit.tasks` → `/speckit.implement` cycle for `ControlMapping`: linking a
  Control to the Capability, Application, Design, Pattern (a `knowledge_items` row of kind `pattern`), or
  a standing estate-wide obligation it governs, each carrying its own `compliance_status`/`evidence_ref`/
  `assessed_at`/`assessed_by`. Three structural questions the source bundle explicitly left open
  (`docs/speckit-compliance-bundle_1.md`) were put to the user directly during `/speckit.specify` rather
  than guessed at, all resolved to the recommended option: five parallel, fully FK-enforced mapping
  tables (four entity-targeted + one estate-wide with a single-column `control_id` PK) instead of one
  polymorphic table; estate-wide obligations in scope; and a mapping's read visibility inherits its
  target's own existing gate — Application-targeted mappings require `READ_APPLICATION_GOVERNANCE` (the
  same gate already protecting that Application's other governance data), everything else stays open.
  New migration `033` (`down_revision="032"`, confirmed against the real chain head). **A real
  mid-implementation correction, caught by actually running the contract test rather than trusting the
  plan**: the plan called for Postgres's `ON CONFLICT DO UPDATE` for the upsert (mirroring `tags.py`'s
  idiom), but that turned out not to be a real precedent for this use case — `tags.py`'s own upsert is
  only ever exercised through a fully-mocked store, and every COMPLY-01/02 contract test runs the full
  router against a SQLite fixture, which cannot compile a `postgresql.insert()` construct at all. Fixed
  by switching to select-then-branch (mirroring `DesignStore.save()`'s own established idiom for the
  identical class of problem), which is dialect-portable and, once actually checked, the more consistent
  choice anyway — documented as a revised decision in research.md D3, not silently patched over. Writes
  and the Control-forward lookup (`GET .../controls/{id}/mappings`, which filters out Application rows
  inline for a caller lacking the governance permission rather than 403ing the whole response) live in
  `adp.compliance` (extended, not replaced); the four reverse-lookup endpoints live on each target's own
  existing router (business/application/designs/knowledge), each importing `adp.compliance.store` for a
  same-physical-DB query via a new `_get_compliance_session()` helper — mirroring ADP-d8u.2's own
  cross-package reverse-lookup precedent exactly, and requiring zero cross-package Python imports inside
  `adp.compliance` itself (target existence/kind validation goes through narrow same-DB mirror tables,
  extending `adp.strategy.store`'s own `design_exists`/`application_exists` idiom). Caught two other
  pre-existing "compliance" naming collisions before they could cause confusion, confirmed by reading
  each directly rather than assumed: `governance/ComplianceTab.tsx` is COMPLY-04's future home for
  LLM-as-Judge validation-*exception* rollups, an unrelated concept; `ApplicationDetail.tsx`'s existing
  "Risk & Compliance" tab is APM's own `risk_compliance_contribution` score (ADP-SPEC-038 US3) — the new
  Application tab is deliberately named "Regulatory Compliance" to disambiguate, and `ComplianceTab.tsx`
  was left untouched. Frontend: a new shared `ControlMappingsEditor.tsx` (create/edit/delete a mapping,
  reused across all five target shapes, mirroring `useLinkFeedback`'s own extract-once precedent) wired
  into `ControlTree.tsx`'s per-control row; reverse-lookup display added inline to `CapabilityNode.tsx`
  (no separate Capability detail screen exists — 043-capability-heat-map's own precedent) and as a new
  `ApplicationComplianceMappings.tsx` panel/tab on `ApplicationDetail.tsx`. Design and Pattern
  reverse-lookup ship API-only this pass — deliberately, not an oversight: neither domain has an
  established single-entity detail screen to embed a UI into, confirmed by direct search before deciding
  rather than guessed. 1526 backend tests (was 1500, +26: 14 unit, 10 contract, 2 authz), 503 frontend
  tests (was 489, +14), `ruff`/`mypy`/`tsc`/`adp-generate --check` all clean. Docker was unavailable in
  this environment (same constraint 921 hit), so the testcontainers-gated integration suite (18 tests
  covering every acceptance scenario plus cascade-delete behavior) is written and will run in CI but
  wasn't executed locally; verified instead via all 24 SQLite-backed contract tests (including two
  full-stack fixtures wiring business/application/compliance stores together for the reverse-lookup
  routes) plus a full live walkthrough against a real local Postgres and running backend — every mapping
  shape, re-mapping-updates-in-place, both cascade directions, the pattern-kind 422, and manual
  delete-then-404 all confirmed live, test data cleaned up afterward. The REVIEWER-role 403 check was
  confirmed via `tests/authz/test_enforcement.py` instead of curl (no dev-mode `X-Role` header exists),
  matching 921's own established pattern. See `specs/922-control-mappings/`.
  bundle from `docs/speckit-compliance-bundle_1.md`) — full `/speckit.specify` → `/speckit.clarify` →
  `/speckit.plan` → `/speckit.tasks` → `/speckit.implement` cycle for a `RegulatoryFramework` registry
  (NIST, GDPR, SOC 2, ...) with a self-referencing `Control` hierarchy beneath each framework.
  COMPLY-02 (cross-domain control mappings), COMPLY-03 (derived compliance status), COMPLY-04 (rollup
  reporting), and COMPLY-05 (Strategy linkage) are explicitly out of scope and unbuilt. One
  `/speckit.clarify` question resolved before planning: a new dedicated `ActionType.WRITE_COMPLIANCE`
  (mirroring `WRITE_APPLICATION`'s per-domain-permission precedent) rather than reusing
  `WRITE_BUSINESS_ARCH` the way Strategy did — Compliance is framed as its own cross-cutting domain, not
  a Business Architecture sub-concern. New sibling package `adp.compliance` (not folded into
  `adp.business`, whose core files were measured at 2,920 lines — already past the ~2,800-line threshold
  that historically triggered `adp.strategy`'s own split) via migration 032 (`down_revision="031"`,
  confirmed against the real on-disk chain rather than this file's own narrative history, which lagged
  it by 13 migrations). Control nesting is deliberately unbounded (no `level` column, unlike
  `business_capabilities`' fixed 3-level scheme) — the source doc's GDPR walkthrough showed depth
  genuinely varies clause-by-clause within one framework (Art. 5 wants six children, Art. 33 stands
  alone). A deliberate, explicitly-documented divergence from Business Capability's own precedent:
  both `controls.framework_id` and the self-referencing `controls.parent_id` use DB-level
  `ON DELETE CASCADE` (spec FR-005/FR-013 require cascade-with-disclosure, not
  `delete_capability`'s block-via-`ChildCapabilitiesExist`) — verified live against the real local
  Postgres, including a 3-generation cascade (grandparent→parent→child, confirming Postgres's
  self-referencing FK cascade recurses correctly, not just one level). Cycle/cross-framework-parent
  rejection is application-layer (store walks from the proposed parent toward the root before
  committing), mirroring `create_capability`'s own precedent for the same class of
  un-DB-constrainable rule; code uniqueness is DB-level (`UNIQUE(framework_id, code)`), not just an
  app-layer check. Frontend: a new top-level "Compliance" nav entry beside Governance;
  `CompliancePage` is self-contained (mirrors `StrategyPage`'s pattern, not `BusinessPage`'s
  prop-threaded tabs); delete actions disclose scope via a client-side descendant count computed from
  the already-fetched tree (no new "preview" endpoint). Caught and fixed three regressions in
  `tests/authz/test_permissions.py` from the `PERMISSIONS_VERSION` 1.8.0→1.9.0 bump (a pinned-version
  assertion and two completeness checks needing new-action entries) during a full-suite run before
  declaring done — the kind of drift a partial test run would have missed. 1500 backend tests (was
  1491, +9), 489 frontend tests (was 483, +6), `ruff`/`mypy`/`tsc`/`adp-generate --check` all clean.
  Verified end-to-end against a live local Postgres via direct API calls for every scenario (framework
  CRUD, the GDPR Art. 5/Art. 33 granularity example, duplicate-code 409, cycle/cross-framework 422,
  multi-level cascade delete, live REVIEWER-role 403) rather than relying on the Docker-gated
  testcontainers integration suite alone, since Docker was unavailable in this environment (that suite
  is written and will run in CI). One real gap surfaced and fixed during polish: quickstart.md's
  authz scenario assumed a dev-mode `X-Role` override header that doesn't exist anywhere in the
  codebase (confirmed by direct grep) — corrected to point at the actual mechanism
  (`tests/authz/test_enforcement.py::test_reviewer_denied_compliance_write`, a role-overridden
  `TestClient`) instead of a curl command that could never have worked. Live browser (Playwright)
  walkthrough was attempted but blocked by an existing browser-profile lock outside this session's
  control (`SingletonLock` pointing to a Windows-host process) — left un-run rather than force-clearing
  a lock that might belong to a real session; `tsc`, the full Vitest suite, and direct API verification
  cover the same UI logic paths. See `specs/921-compliance-framework-registry/`.
  follow-up right after ADP-3wa shipped: "time to add filter by option. it should be limited to value that
  limit the selection of applications." A real ambiguity resolved via `AskUserQuestion` before designing:
  the field dropdown's scope. Confirmed to be the same 5 Group By dimensions PLUS 3 more bounded-enum
  fields on `Application` never surfaced anywhere on this screen before (`lifecycle_status`,
  `hosting_model`, `pace_layer`) — 8 fields total, not just the existing 5. v1 is deliberately
  equality-only ("pick field, pick exact value"), per the user's own explicit phasing request; comparison
  operators (`>`/`<` on scores) and string operators (`contains`) are filed as a pre-authorized follow-on
  bead (`ADP-6w4`) rather than attempted here — the user's own words: "if it is more straightforward to do
  this in pieces that is OK, just open a bead for work that will follow." Deliberately reuses
  `groupApplications()`/`bucketsFromResult()` (already built for ADP-8xo/ADP-3wa) as the entire mechanism:
  a filter's available *values* for a chosen field are exactly that field's bucket list, and filtering to
  one value is exactly "return that one bucket's apps" — zero new value-enumeration or matching logic
  needed. `filteredApps` sits upstream of both the existing flat-grid and cross-tab computations, so
  filtering composes correctly with both Group By modes automatically, confirmed live (filtering while the
  cross-tab is active correctly narrows table cells too, not just the flat view). One correction caught
  live during the walkthrough, not a bug in the code: seed data has zero applications with `hosting_model`
  or `owning_business_unit` set at all, so filtering by those fields' non-"Unclassified" values correctly
  shows "No applications match the current filter" — confirmed this is accurate given the fixtures, not a
  regression, by cross-checking against `owning_business_unit`'s same known-empty state from ADP-8xo's own
  verification. 397 frontend tests (+16: 11 for the 3 new `groupBy*` functions plus `filterApplications`,
  5 for the page's filter UI behavior), `tsc` clean, no backend file touched. Full live Playwright
  walkthrough of the empty-field case, a real narrowing case (TIME=Migrate → exactly 1 app), Clear filter
  restoring the full set, and filter+cross-tab composing correctly together.
  follow-up request right after ADP-8xo shipped: "time to add a second drop down for the portfolio screen.
  same values. allow the selection of 2 different cuts of the application portfolio at the same time. if
  the same value is choosen in both drop downs the view will look like it does today with a single
  selection." Deliberately reuses `groupApplications()` per axis rather than reimplementing bucketing for
  two dimensions at once — a cross-tab cell is just the *intersection* of a row bucket's apps and a column
  bucket's apps (by app id), so every dimension's existing behavior (fixed vs. dynamic bucket sets, and
  capability's multi-membership) is inherited for free and stays covered by the already-existing
  per-dimension tests; only the new intersection logic (`crossTabApplications`, `groupApplications.ts`)
  needed its own tests. New `CrossTabGrid.tsx` mirrors `web/src/strategy/StrategyHeatMap.tsx`'s `<table>`
  matrix precedent (the only other 2D-grid UI in the codebase) — `overflowX: auto` wrapper, `borderCollapse`,
  same header/cell padding. Both dropdowns default to `"capability"`, so the page's default render stays
  byte-for-byte identical to what ADP-8xo shipped; cross-tabbing only activates once the two dropdowns
  genuinely differ, and setting them back to the same value (including a non-default one, e.g. both "TIME
  Disposition") reverts to the exact original flat card grid, not a degenerate diagonal-only table — the
  explicit requirement from the request. An empty Unclassified row/column is omitted from the grid entirely
  (unlike the 1D view's always-shown footer) since a whole empty grid line is clutter, not a useful
  confirmation, in a table. One live mid-turn correction, applied directly without re-entering plan mode
  since it was a single-file styling change with no architectural implication: the user asked for actual
  application names in each cell instead of the originally-planned count-with-hover-tooltip — cells now
  stack app names directly (comma-free, one per line, ellipsis-truncated) with background tint only on
  non-empty cells. 381 frontend tests (+9: 5 for `crossTabApplications`, 4 for the page's dropdown/table
  behavior), `tsc` clean, no backend file touched. Full live Playwright walkthrough of all three states
  (default flat view, an active cross-tab with real app names in cells, and both dropdowns reset to the
  same non-default value correctly reverting to the flat view) against a running local stack.
  "plan out how to accomplish this on the Portfolio screen" for the 8 recurring APM grouping dimensions the
  user described (business capability, domain/value-stream, TIME, technology layer, 7R, ownership,
  criticality, application type), following up on the ADP-v2n TIME-2x2 mockup investigation earlier in the
  session. Three parallel Explore agents plus a Plan agent researched the actual codebase before any design
  decision; the first found a **ground-truth correction surfaced to the user before proceeding**: ADP's
  "Portfolio" nav screen was entirely about Designs (technology tags, lifecycle status) with zero
  application data — the real Application registry lived on a separate "Applications" screen. Resolved via
  two rounds of `AskUserQuestion`: Portfolio's identity flips entirely to the Application Portfolio,
  replacing its Design-scoped content outright (not merged alongside); ship the 5 dimensions with clean
  existing data now (capability, TIME, 7R, ownership/business-unit, criticality), defer domain/value-stream
  and application-type (both had real data-model gaps, confirmed via direct field-by-field code reads) as
  follow-on beads (`ADP-r41`, `ADP-3jj`) rather than guessing at new fields. New `groupApplications.ts`
  (`web/src/portfolio/`) centralizes the bucketing logic — pulled out of the component (unlike
  `RationalizationView.tsx`'s inline single-dimension bucketing) specifically so 5 dimensions' worth of
  logic is independently unit-testable; `groupByCapability` is deliberately multi-membership (an app linked
  to 2 capabilities appears in both buckets — the underlying `application_capability_links` table is
  genuinely many-to-many, no "primary capability" concept exists to force a single bucket), while
  `groupByBusinessUnit` is the one dimension with a dynamic, data-driven bucket set rather than a fixed enum
  like the other three. One new backend endpoint (`GET /portfolio/application-capability-groups` +
  `store.list_all_capability_links`, mirroring `list_all_costs`'s 919-insights-dashboard bulk-read
  precedent) — the other 4 dimensions needed zero backend work, already returned by the existing
  `GET /applications`. The design agent caught two real cross-dependencies during planning that a shallower
  pass would have broken: `lifecycle.ts` is also imported by `governance/DesignStatusTab.tsx`, and
  `usePortfolioSummary` is also consumed directly by `OverviewPage.tsx` — both confirmed via direct grep and
  kept untouched; only the 4 truly single-importer old components
  (`PortfolioSummaryHeader`/`TechnologyLandscape`/`DependencySearch`/`PortfolioDesignList`) were deleted.
  Retiring the now-orphaned old backend endpoints themselves was deliberately deferred to a third follow-on
  bead (`ADP-704`), Phase-C-style, mirroring the `ADP-914.9` C4Canvas-retirement precedent — prove the
  replacement first, retire old surface only after. 1384 backend tests (+6), 372 frontend tests (+21),
  `ruff`/`mypy`/`tsc`/`adp-generate --check` all clean, plus a full live Playwright walkthrough of all 5
  dimensions against real seeded data (including the dynamic-bucket-set and fixed-empty-bucket edge cases)
  and both shared-dependency regression checks (Overview's summary tile, Governance's lifecycle badges).
  interjected mid-turn while investigating the ADP-c44 bug reports above ("business capability diagram
  should be multi-select — capabilities should come over to the diagram tool with the relationships").
  Replaces `CapabilityNode.tsx`'s old single-purpose "⛶ Generate Diagram" per-row button (which called
  `generateFromCapabilitySubtree` on one capability's own subtree) with a checkbox on every row plus a
  toolbar-level "Generate Diagram from Selected" action in `CapabilityTree.tsx` — an arbitrary,
  cross-branch selection instead of one capability's own descendants. New `generateFromCapabilities()`
  (`web/src/diagrams/generators.ts`, a sibling to the existing `generateFromCapabilitySubtree`): one node
  per selected capability plus one edge for each pair where `cap.parent_id` is *also* selected (a flat
  id-membership check, not a tree walk, per research.md Decision 3) — deliberately does not auto-include
  unselected ancestors, so a selected capability whose real parent isn't checked renders with no incoming
  edge. Title is the single capability's own name for a 1-item selection (parity with the old button's
  leaf-node behavior) or the generic "Capabilities Diagram" for multiple. US2 adds a visible
  "· N selected" count and a "Clear selection" toolbar action once anything is checked. Selection state
  (`selectedIds: Set<string>`) is intentionally component-local `useState` in `CapabilityTree.tsx`, not
  lifted to `BusinessPage.tsx` — it resets for free on tab switch since `BusinessPage.tsx` conditionally
  unmounts the tree, a deliberate contrast with `043-capability-heat-map`'s `focusCapabilityId` (which
  *does* need lifting, since it must survive a Heat Map → Capabilities tab switch). Both the cross-branch
  (zero-edge) and parent-child (hierarchy-edge) scenarios were confirmed live via Playwright against a
  running local stack, not just unit tests — including confirming selection genuinely resets on tab
  switch. First-ever render-based test for `CapabilityNode.tsx` (`CapabilityNode.test.tsx`, new — the
  component calls `useQueryClient()` directly, so needed a real `QueryClientProvider` wrapper, mirroring
  `CapabilityTree.test.tsx`'s own established `renderWithQueryClient()` helper). 351 frontend tests (was
  345 before this feature), `tsc`/`adp-generate --check` clean, backend suite (1378 tests) run unchanged
  as a no-op sanity check since this feature touches no backend file at all. See
  `specs/920-capability-diagram-select/`.
  reported live on the same screen: "once data is saved there is nowhere to see it again" and "no save
  button to save the linked items." Investigated live before touching any code (per this session's own
  established discipline): both mechanisms actually already worked correctly — the objective's own fields
  (owner/period/metric) rendered in the read view, and each link editor's "Link"/"Remove" persisted
  immediately on click, confirmed via a direct API check plus a full page reload. The real problem was
  legibility, not function: the core fields were small, unlabeled text sitting directly above six large,
  clearly-headed "Linked ___" sections, easy to read straight past; and clicking "Link" gave zero visual
  confirmation it had just saved, unlike every other form in the app (which all use an explicit Save
  button). Resolved via a real `AskUserQuestion` on which direction to take (both fixes, confirmed) rather
  than guessing. Fixed: (1) `ObjectiveDetail.tsx`'s read view now shows owner/fiscal period/target in a
  clearly labeled, bordered data card, visually distinct from the linked-entity sections below it; (2) a
  new shared `useLinkFeedback` hook (`web/src/strategy/useLinkFeedback.ts`) gives all five near-identical
  link editors (Capability/ValueStream/Design/Application/Initiative) a transient "✓ Linked X" / "Removed
  X" confirmation on success — extracted once rather than duplicated five times, mirroring
  `checkMetricFields`'s own precedent from ADP-5wf for de-duplicating logic identical across multiple
  near-verbatim editor components. **A real git-history wrinkle handled carefully, not silently**: this
  fix's branch was created from `920-capability-diagram-select`'s tip, which had itself forked from `main`
  *before* ADP-5wf's PR merged — meaning the branch's merge-base with `main` was one commit stale. Caught
  before opening a PR (a `git log`/`git merge-base` check surfaced the divergence) and fixed with
  `git reset --soft main`, which moves the branch pointer forward while leaving the working tree
  untouched — safe here specifically because the working tree already contained the ADP-5wf fix's content
  (never having been discarded across the branch-creation step), so the reset correctly nets out to "no
  diff" for that already-merged content and leaves only this fix's genuinely new changes for the PR. 16
  new/updated tests (`useLinkFeedback.test.ts` plus confirmation-message and unlink-call-signature updates
  across all five editors' test files and `ObjectiveDetail.test.tsx`), `tsc` clean — the labeled data card
  confirmed visually live; the link confirmation's correctness confirmed via deterministic unit tests using
  fake timers, since the message's 3-second auto-clear window is faster than this session's own live-browser
  tooling round-trip can reliably screenshot (attempted twice live, both times the message had already
  auto-cleared by the time the screenshot returned — a tooling-latency limitation, not a functional gap,
  and not worth stretching the timeout to chase given the unit coverage already exercises the exact code
  path deterministically).
  on the Strategy Objectives screen, root-caused live via direct reproduction rather than assumed. Both
  `ObjectiveForm.tsx` (create) and `ObjectiveDetail.tsx` (edit) shared an identical, flawed `hasMetric`
  check requiring only *one* of `metric_name`/`target_value`/`target_unit`/`direction` to be set before
  submitting all four — but `src/adp/strategy/models.py`'s `_validate_metric_fields` requires all four or
  none. Selecting just one field (e.g. only "Direction" from the dropdown, a very plausible real user
  action) silently sent a partial payload the backend rejected with a raw `POST ... failed: 422`, with no
  guidance — which read as "Save does nothing" exactly as reported. Confirmed via a live curl repro against
  the running backend before touching any code, not guessed at. Fixed with one new shared, pure validator
  (`web/src/strategy/objectiveMetric.ts`'s `checkMetricFields`) used by both forms, blocking submission
  client-side with a clear message ("...must all be filled in together, or all left blank") before any
  network call — avoiding the two forms' pre-existing duplicated-validation-logic drift risk by extracting
  the shared piece rather than patching both copies independently. 320 frontend tests (was 312, +8: 6 pure
  unit tests plus 2 component-level regression tests reproducing the exact original bug), backend
  untouched, `tsc` clean — plus a full live Playwright verification: reproduced the original 422 first
  (confirmed broken), then confirmed the fix blocks it client-side with zero network errors, then confirmed
  the happy path (all four metric fields filled in) still saves correctly. Also notable: this investigation
  collided harmlessly with the user's own live testing session on the same dev server — a test objective I
  created and deleted via a direct API call for cleanup was deleted *while* the user had it open/cached,
  which looked like a second "data loss" bug but was actually just my own cleanup timing; clarified rather
  than left ambiguous.
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

This project is indexed by GitNexus as **ADP** (18129 symbols, 28998 relationships, 240 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

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
