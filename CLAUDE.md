# ADP Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-11-14 (934-pattern-metamodel planned)

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
- Python 3.12 (backend) — no frontend file touched (data-model-and-API-only, + FastAPI ≥ 0.111, SQLAlchemy 2 async (Core), asyncpg, Alembic, Pydantic v2 — all (927-theme-framework-mapping)
- PostgreSQL 16 — one new table via migration `037` (`down_revision = "036"`): (927-theme-framework-mapping)
- Python 3.12 + FastAPI (extends the existing lifespan hook — a third background task (928-strategy-export)
- Python 3.12 (backend); TypeScript 5.x + React 18 (frontend) — both existing + FastAPI ≥ 0.111, SQLAlchemy 2 async (Core), asyncpg, Alembic, Pydantic (929-application-type-cots)
- PostgreSQL 16 — one additive migration (`039`, `down_revision="038"`): one nullable (929-application-type-cots)
- Python 3.12 (backend only — no frontend file touched; this is a pure + SQLAlchemy 2 async (Core), pgvector, PostgreSQL full-text search — all (930-hybrid-search-phase)
- PostgreSQL 16 with pgvector (migration 011, already applied) — no new migration; one (930-hybrid-search-phase)
- PostgreSQL 16 — one new migration (`040`, `down_revision="039"`): two new tables, (931-admin-ui-editing)
- PostgreSQL 16 — one new migration (`041`, `down_revision="040"`): new table (932-regulatory-framework-tags)
- Python 3.12 (backend); TypeScript 5.x + React 18 (frontend). Both are existing stacks. + FastAPI ≥ 0.111, SQLAlchemy 2 async (Core), asyncpg, Alembic, Pydantic v2; React 18, TanStack Query v5. All are existing, with **zero new packages**. (933-agent-registry)
- PostgreSQL 16. Migration `043` (`down_revision="042"`) adds two new tables and re-creates one CHECK constraint on `applications`. (933-agent-registry)
- Python 3.12 runtime, 3.11+ compatible. + Pydantic v2 and `pyyaml>=6.0` (both existing). **One new runtime dependency:** `cel-expr-python==0.1.4`, pinned exactly (research D1). It ships cp311/cp312 manylinux_2_28 wheels and has no transitive dependencies. (934-pattern-metamodel)

- Python 3.12 (3.11+) + TypeScript 5.x/React 18 -- existing stacks, zero new packages; agent traceability (ADP-12x): agent -> business L3 / value stream stage / value chain activity "automates" links owned by `adp.agentic` (narrow mirrors, reverse lookups on the agentic router), `MappingTargetType.AGENT` + `control_agent_mapping` in `adp.compliance` (no initiative linkage), pure `adp.agentic.risk` band derived on read; migration `052` (4 tables, additive) (944-agent-traceability, implemented)
- Python 3.12 (3.11+) + TypeScript 5.x/React 18 -- existing stacks, zero new packages; mapping rationale (target/tactical/transitional/redundant) + optional geography on 937's app_capability_realizations, migration `051` (2 nullable columns, CHECK, FK SET NULL in the migration only); 938 overlaps derive needs_attention/explained + reasons on read (943-mapping-rationale)
- Python 3.12 (3.11+) and TypeScript 5.x + React 18 (existing). + FastAPI, SQLAlchemy 2 async Core, Alembic, Pydantic v2, TanStack Query v5. All existing; **zero new packages**. (938-capability-model-analysis)
- Python 3.12 (3.11+) + TypeScript 5.x/React 18 -- existing stacks, zero new packages; new `adp.organization` package (org units + geography, routes under `/api/v1/business/`), ISO 3166/UN M49 data committed as `src/adp/organization/data/geographies.json`, migration `048` (org_units, geographies seeded, org_unit_geographies, applications.owning_org_unit_id) (940-org-units-geography)
- Python 3.12 (3.11+) + TypeScript 5.x/React 18 -- existing stacks, zero new packages; capability <-> org unit mappings (owner L1/L2 one per capability, performer L3 + optional geography, contributor L3) in `adp.organization.cap_mappings` + pure `cap_org_analysis` (effective owner, findings, footprint derived on read, never stored), migration `049` (capability_org_mappings) (941-capability-org-mappings)
- Python 3.12 (3.11+) + TypeScript 5.x/React 18 -- existing stacks, zero new packages; regional maturity assessments (capability x region/country, score 1-5 and/or note, global maturity stays the baseline) + region-specific scope in `adp.organization.regional` + pure `regional_analysis` (applicability, heat map cells, derived on read), migration `050` (capability_regional_assessments, region_specific_capabilities, region_specific_capability_geographies) (942-regional-assessments)
- PostgreSQL 16. Migration `047` (`down_revision="046"`) adds 2 columns plus a CHECK on `technical_capabilities`. All analysis is derived. (938-capability-model-analysis)

- Python 3.12 (3.11+ compatible) + TypeScript 5.x/React 18 -- existing stacks, zero new packages; extends `adp.patterns` with registry/lifecycle/projection/render modules, writes managed rows into the existing `knowledge_items` (pgvector embedding via `adp.knowledge.embedder`), migration `044` (4 tables: ea_pattern, ea_pattern_version, ea_pattern_relation, ea_pattern_lifecycle_event) (935-pattern-registry)

- Python 3.12 (3.11+) + TypeScript 5.x/React 18 -- existing stacks, zero new packages; pure conformance engine in `adp.patterns` (snapshot/engine) over 934's CEL adapter, per-caller portfolio snapshot from registry mirrors, migration `045` (ea_pattern_adoption, _member, _pin; status derived, never stored) (936-pattern-conformance)

- Python 3.12 (3.11+) + TypeScript 5.x/React 18 -- existing stacks, zero new packages; application capabilities (middle layer between business and technical capabilities) in `adp.application.app_capabilities` + router, migration `046` (application_capabilities + 3 link tables; level rules in the store; missing-technical-capability warning derived, never stored) (937-application-capabilities)

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
# after changing any API model: adp-generate, then (cd web && npm run gen:api); commit both
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
- Fable review ADP-blp.28 (backend test speed; tests only, no source change):
  - `tests/conftest.py` replaces `adp.api.app.create_app` with a version that returns ONE shared app
    per configuration (the `ADP_*` environment), with `dependency_overrides` and `app.state` cleared on
    every call. FastAPI analyses every route's dependencies on an app's first request (about half a
    second for 370 routes) and nearly every contract test built its own app. Suite without coverage
    224 s -> 69 s; with coverage 525 s -> 155 s.
  - A test that adds a route, middleware or exception handler to the app is fine: an app whose shape
    changed is discarded after the test. A test that needs its own app calls `create_app.__wrapped__()`.
    Guard: `tests/unit/test_shared_app.py`.
  - `pyproject.toml` silences one warning only: aiosqlite's worker thread failing to report back when
    an undisposed test engine is collected after its event loop closed.
  - NOT done: one shared Postgres container for the migration tests. `tests/integration` needs
    Docker, which this machine does not have, and CI does NOT run it either
    (`pytest tests/ --ignore=tests/integration`), so earlier notes here saying an integration test
    "will run in CI" are wrong: those tests currently run nowhere.
- Fable review ADP-blp.57, .68 and .65, closing increments (frontend only):
  - The open entity is owned by the page, in the URL. `useRouteEntity(kind, initial)` in
    `shell/routing.ts` reads it from the hash and writes it back with `openEntity(kind, id)`: a
    selection is a history entry (Back returns to the previous selection, reload restores it), the
    page's own parameters (`?tab=`) are kept, and the page is NOT remounted. Used by Applications
    (application, application capability), Business (focused capability), Technical Architecture,
    Agents and Pattern adoptions. An entity in the URL decides the tab (an application capability shows
    Capabilities); choosing another tab closes it.
  - `App.tsx` no longer holds six `pending*Id` states, page `key`s, `AppCapNavContext` or
    `CapabilityNavContext`; all are deleted, with the `onOpenSolution` / `onOpenAdoption` props. Link to
    an entity with `<EntityLink kind id>`; from an event handler use `goToEntity(kind, id)`.
    `CapLink`, the application capability summary list, "Automated by" and an agent's solutions are
    plain links now (tests assert `href`, not a callback).
  - Back: the top-bar control goes to the previous *screen* (with whatever was open there), not to the
    previous selection on this screen. Clicking the nav item of the screen already showing closes the
    open entity.
  - Permissions: `LinkEditor` takes `action` (the strategy link editors and business design links pass
    `write_business_arch`) and disables the picker and Remove with the reason. Pattern lifecycle uses
    `govern_pattern` (`useCanGovernPatterns`); business writes ask for `write_business_arch`
    (`useBusinessWrite`), no longer borrowing `write_application`. Application Add / Edit / Delete, the
    solution agents panel and an agent's Automates links are disabled for roles without
    `write_application`. The role lists in `appCapNav.tsx` and `patterns/permissions.ts` remain only as
    the guess used until the server's answer loads.
- Fable review ADP-blp.61 and .46, closing increments (frontend only):
  - .61: Agents and Patterns lists use `EmptyState`. An empty registry says what it is and what to do
    next (or that the role cannot add); when filters hide everything it says so and offers Clear filters.
  - .46: `Table` primitive (`columns`, `caption`, `dense`; rows are plain `<tr>/<td>`, `tr.clickable`)
    on the Agents, Patterns and Cost tables. Button classes `ui-btn-xs`, `ui-btn-link` (`danger`,
    `muted`: a text action in a row) and `ui-btn-plain` (a row, expander or name; keeps its own layout
    `style`). `ui-form-stack` spaces a column of `Field`s. The Risk, Cost, Governance and Quality panels
    use `Field` + `ui-input`; 63 hand-styled buttons in `application/` and `admin/` use the classes;
    the application capability views use `Tabs`.
  - Lint: a `<button>` with `style` and no `className` is an error. 55 files outside `application/`
    and `admin/` (147 buttons) are listed as a baseline in `web/eslint.config.js`: convert a file and
    remove it from the list, never add to it. Most forms and tables elsewhere are still hand-styled.
  - ADP-blp.26 closed without unifying the table declarations: the drift guard covers the risk.
- Fable review ADP-blp.27, third part: the two largest backend files split (no API change;
  `generated/openapi.json` unchanged).
  - `adp.application.store` (2,317 lines -> 479) keeps the session factory, application CRUD and
    technical capability CRUD. New siblings: `tables.py` (metadata and every table), `store_base.py`
    (row converters, `get_application`, `get_technical_capability`), `assessments.py` (risk, health,
    business value, cost, governance, quality), `roadmap.py` (initiatives), `links.py` (capability,
    stage, domain, integration and design links). The store RE-EXPORTS every one of their names, so
    `astore._applications`, `astore.upsert_application_risk` etc. and test fixtures are unchanged. The
    siblings must not import `adp.application.store` (import cycle). Functions that call
    `index_entity` stay in the store, because tests patch it there.
  - `adp.business.router` (1,428 -> 667): `agent_review_router.py` and `value_chains_router.py` hold
    those routes; `router_deps.py` holds the shared dependencies (re-exported by the router, so
    `brouter._get_session` overrides work). Tests patch
    `adp.business.agent_review_router._make_agent_review_llm_client` now.
  - Gotcha: do NOT nest a router in another router (`router.include_router(sub)`). The matched route
    then reports its path without the outer prefix, and the permission lookup and metrics label read
    that path, so a nested mutating route is allowed unmapped. Both new routers carry the full
    `/api/v1/business` prefix and are registered in `adp.api.app`. Guard:
    `test_no_router_is_nested_in_another`.
- Fable review ADP-blp.27, second part (no API change; `generated/openapi.json` unchanged):
  - New `adp.api.common`: `session_dependency("adp.<domain>.store")` replaces the four-line
    `_get_session` / `_get_<other>_session` functions in 24 places (the module is named and imported on
    first use, so cross-domain reverse lookups create no import cycle; each call returns a distinct
    function, so `app.dependency_overrides[router._get_session]` works as before). `named_path_param`
    (moved from the compliance router) lets one handler serve routes with differently named path
    parameters.
  - `adp.strategy.router._INITIATIVE_MAPPING_ROUTES`: the initiative control-mapping link/unlink routes
    for the five entity targets are registered from a table, like the compliance router's.
  - Not changed: the `_get_*_session_factory` dependencies (chat, business) and the per-target
    "compliance-mappings" reverse-lookup route on each target's own router (one small route each; the
    agentic router may not import other domains).
- Fable review ADP-blp.27 (compliance mappings driven from one table; no API change):
  - `adp.compliance.store._ENTITY_TARGETS` describes each entity mapping target (table, key column,
    existence rule). `upsert_entity_mapping` / `list_mappings_for_entity` / `delete_entity_mapping` take a
    `MappingTargetType`; the per-target functions (`upsert_capability_mapping`, ...) are one-line wrappers
    kept for their callers. `list_mappings_for_control`, the status dispatch and both roll-up row queries
    loop over the table. ORGANIZATION is not in it (no target id).
  - `adp.compliance.router._ENTITY_MAPPING_ROUTES` registers PUT, DELETE and the "initiatives" GET per
    target from one pair of handlers. `_named_target` keeps each route's own path parameter name
    (`capability_id`, `agent_id`, ...), so `generated/openapi.json` is unchanged.
  - A new mapping target is now one entry in each table plus its mapping table and migration (and the
    strategy side's own dispatch tables). Guard: `tests/unit/compliance/test_mapping_target_table.py`.
- Fable review ADP-blp.36, next step (frontend only): the shared link editor moved to `web/src/links/`
  (`LinkEditor.tsx`, `useLinkFeedback.ts`, `NavLinkButton.tsx`; strategy imports updated). `LinkOption`
  gained `detail` (shown beside a linked item) and `LinkEditor` takes `linkedItems` for callers that load
  the linked rows themselves, so a linked item outside the picker's capped list is still shown.
  `business/DesignLinkEditor` (capability and value stream design links) is now a wrapper over it: choosing
  a design links it, there is no separate Link button. Still separate: the control link editor, the
  initiative control-mapping editor and the application-side editors (they carry extra fields).
- Fable review P3 batch 8 (epic ADP-blp, more of .34 .65 .68; frontend only):
  - Portfolio filter is in the URL (`?filter=<field>&op=<operator>&value=<value>`), next to `group`/`then`.
    The reset effects in `PortfolioPage` act only on a field or operator the user changed
    (`lastFilter` ref), so a filter from the URL survives the first render and data refreshes.
  - Capability create/update/delete call `invalidateCapabilityViews` (`api/business.ts`): the capability
    list, `CAP_ANALYSIS_KEY`, `ORG_KEY`, `["portfolio"]` and `["strategy-heatmap"]`.
  - Permissions: `useCanManagePatterns` asks the server (`write_pattern`); the control mapping editor's
    Add/Edit/Remove need `write_compliance`; the Risk, Cost and Governance panels disable Save without
    `write_application_{risk,cost,governance}` and show `<Restricted what="..."/>` (new primitive) when
    the role may not read the tab.
- Fable review ADP-blp.7 (least-privilege Postgres roles on Azure):
  - `src/adp/ops/db_roles.py` (run by `deploy.sh` through the `adp-migrate` job, command overridden)
    creates `adp_app` (SELECT/INSERT/UPDATE/DELETE in the `adp` database, default privileges for later
    tables, no write to `alembic_version`) and `adp_keycloak` (owns the `keycloak` database's objects).
    Only the migration job keeps the administrator login. Idempotent; resets both passwords.
  - Key Vault: `postgres-app-connection-string` (the API's `ADP_DATABASE_URL`), `postgres-app-password`,
    `postgres-keycloak-password`. `postgres-connection-string` is now the migration job's only.
  - `apps.bicep` has `jobsOnly`: `deploy.sh` deploys the jobs, runs migrations, runs the role script, then
    deploys the apps. `keycloakFqdn`/`apiFqdn` outputs are computed from the environment domain.
  - The app must not run DDL at runtime: it has no right to. Schema changes go in a migration.
- Fable review ADP-blp.64 (auth proxy and metrics, checked on a deployed Azure environment):
  - `/auth/*` proxy: every forwarding header the client sent (`Forwarded`, `X-Forwarded-*`, `X-Real-IP`)
    is dropped. The proxy sets `X-Forwarded-For` to the last entry of the incoming header (the one the
    ingress appended) or the socket peer, and `X-Forwarded-Proto`/`-Host` from `ADP_KEYCLOAK_ISSUER`.
  - `/metrics`: open when auth is off; with auth on it needs `Authorization: Bearer <ADP_METRICS_TOKEN>`
    and answers 404 otherwise (also when no token is configured).
  - `infra/keycloak/adp-realm.json`: `sslRequired` is `external`. The file is only read when the realm is
    first created; a running realm is changed with the `adp-keycloak-admin` job (`KC_PATCH_TARGET=realm`).
  - `apiapp.bicep`: an empty `allowedIpRanges` without `allowPublicIngress=true` gives one Deny-all rule
    (`deploy.sh` passes the flag for `ADP_ALLOW_PUBLIC=1`).
  - Azure gotcha: a fresh deploy can leave the Postgres private DNS zone without its VNet link (the
    migration job then cannot resolve the database host); see `bd memories azure-private-dns`.
- Fable review ADP-blp.26 and .46, first increments:
  - .26: `tests/support/schema.py`. `find_drift()` compares every duplicate table declaration (27 tables
    are declared in more than one store) with the widest one, on the PostgreSQL dialect;
    `tests/unit/test_schema_declarations.py` fails on any disagreement (none today) and if the number of
    duplicated tables grows. `create_schema(sync_conn)` creates every store's tables once, each from its
    widest declaration -- use it in new multi-store fixtures instead of hand-ordered `create_all` calls
    with mirrors excluded (`test_initiative_agent_mapping_api.py` is converted). The tables themselves are
    NOT yet unified into one module: tests insert into the narrow mirrors directly, so that is a larger
    change.
  - .46: `Loading`, `Alert` and `Field` in `web/src/ui/primitives.tsx`. `Field` passes `id`,
    `aria-describedby`, `aria-invalid` and `aria-required` to its control (not native `required`: forms
    validate themselves). 28 hand-written "Loading…" lines and the four application-panel Save buttons use
    the primitives; `ValueStreamForm` is the worked example of `Field`. Most forms and tables are not
    migrated yet.
- Fable review ADP-blp.59, last part: `designs/DesignFlowSteps.tsx` shows the four steps of creating a
  design (Describe, Recommend, Design, Validate) above the New Design and C4 Design screens. Each step is
  a link to its screen; steps that need a design are inactive until one exists. `IntakePage`'s tab is now
  in the URL (`?tab=recommend`) so the Recommend step can link to it. App wraps those two views in a flex
  column with the steps on top (`DESIGN_FLOW_VIEWS`).
- Fable review P3 batch 6 (epic ADP-blp, more of .27 .36 .65 .68):
  - `adp.auth.actor.actor_of(request, default)`: the one actor lookup for audit and log lines. All twenty
    routers' `_get_actor` call it. The design export route used to read only the `X-Actor` header, so a
    signed-in user's export was audited as "unknown"; it now records the username.
  - `LinkEditor` gained `onOpen`/`openTitle` (open an item within the screen); the objective-initiative
    and initiative-objective editors use it. Six strategy link editors now share it. Still separate: the
    control link editor, `business/DesignLinkEditor` and the application-side editors.
  - Portfolio "Group by" / "Then by" are in the URL (`?group=...&then=...`). The filter is not.
  - Compliance control tree: add, edit and delete are disabled with a reason for roles without
    `write_compliance`.
- Fable review ADP-blp.57 and .59 (frontend only):
  - `application/ApplicationSummary.tsx`: score cards at the top of an application's Overview tab (health,
    business value, disposition, lifecycle, risk, cost, compliance). Risk, cost and compliance cards open
    their tab; a card the caller may not read says "Restricted". Compliance shows the worst mapped status.
  - `business/CapabilityNode.tsx`: one "Details" button opens a panel with pill tabs (Links, Organization,
    Regions, Compliance, Review) in place of five expander buttons per row; `detail` state holds the open
    section. Tests click "Details" and then the section tab.
  - `shell/EntityLink.tsx`: `<EntityLink kind id>` is a plain `<a href="#/...">` to the entity's own
    screen (`entityHref`). `LinkEditor` takes `entityKind` to link the names of linked capabilities and
    applications. Most other places that show an entity name still use the older nav contexts.
  - Back: `App` keeps a trail of visited routes and passes `backView`/`onBack` to `AppShell`, which
    shows "<- Back to <screen>" in the top bar after moving to another screen (uses history.back()).
  - Not done from .59: the design-flow stepper. Not done from .57: replacing the nav contexts.
- Fable review P3 batch 5 (epic ADP-blp.37): frontend API types generated from the API.
  - `adp-generate` now also writes `generated/openapi.json` (the app's OpenAPI document, keys sorted), and
    `adp-generate --check` fails when it is out of date. The Keycloak proxy route is excluded from the
    schema (`include_in_schema=False`): one handler for seven methods gave an operation id that changed
    from run to run.
  - `cd web && npm run gen:api` (openapi-typescript) writes `web/src/api/generated/schema.d.ts`;
    `tests/unit/api-types-drift.test.ts` fails if it is stale. So after ANY change to a request or
    response model: run `adp-generate`, then `npm run gen:api`, and commit both files.
  - Use `components["schemas"]["Name"]` from `./generated/schema` for new and changed types.
    `StrategicTheme` is the first one moved over (the hand-written type had no `framework_ids`). The other
    ~350 hand-written types in `web/src/api/*.ts` are unchanged.
- Fable review P3 batch 4 (epic ADP-blp: .49, part of .36, part of .13); frontend plus CI:
  - `web/src/ui/tones.ts` holds every status-to-tone map (design and pattern lifecycle, conformance,
    objective status, risk band, TIME, classification, validation verdict) against one stated meaning for
    each tone; the feature modules re-export from it under their old names. `tones.test.ts` fails if an
    ended state is "crit" or the same word gets two tones. A validation verdict of "indeterminate" is now
    blue (info), matching conformance; it was amber.
  - `strategy/LinkEditor.tsx`: the shared link editor. The objective's capability, value stream, design and
    application editors are thin wrappers over it (538 lines -> 264). Not yet converted: the control,
    initiative and initiative-objective editors (extra behaviour) and the application-side ones.
  - CI: the actions in `drift-check.yml` are pinned to commit SHAs (the tag is kept as a comment).
- Fable review P3 batch 3 (epic ADP-blp: .50 .66, parts of .27 .34 .65 .68):
  - `docs/ui-glossary.md`: the words the UI uses (Link vs Map vs Realized by; Add / Delete / Remove; names
    written in full; what each status colour means). "Tech Caps" -> "Technical Capabilities", "APM
    Analysis" -> "Portfolio Analysis".
  - Tabs in the URL: `useHashParam(name, allowed, initial)` in `shell/routing.ts` keeps one named value in
    the hash query (`#/business?tab=heatmap`) with `replaceState`; used by the Business, Strategy,
    Governance and Applications tabs. App's route sync now leaves the URL alone when the route itself is
    unchanged, so page parameters survive a reload. Filters are still not in the URL.
  - `PageHeader compact` on Agents, Patterns, Compliance and Applications.
  - Permissions: `useCan(action, fallback)`; `useCanWriteApplications` now asks the server and uses the old
    role list only until the answer loads. Edit/Delete on agents, frameworks, themes, initiatives and
    objectives are disabled with a reason for roles that cannot write.
  - Pickers: the design and application pickers' query keys are under `["designs", ...]` /
    `["applications", ...]`, so creating one refreshes them; the design picker asks for 200, not 100.
  - `adp.db.is_unique_violation(exc)` replaces seventeen copies of a text test in the stores.
  - Deferred with reasons on the beads: .25 (snapshot cache) and .67 (export change marker).
  - Gotcha: Vite can serve a stale transform of a file edited twice in quick succession (the browser saw
    `useState is not defined` while tsc and vitest passed). `touch` the file.
- Fable review P3 batch 2 (epic ADP-blp: .47 .61 .69, part of .28):
  - `ui/confirm.tsx`: `confirmAction(message)` returns a promise; `<ConfirmHost />` (mounted in AppShell)
    draws a themed dialog, with a fallback to `window.confirm` when no host is mounted -- so component tests
    that mock `window.confirm` are unchanged. All 19 native `confirm()` calls use it. FIVE record deletes had
    NO confirmation at all and now ask first: business capability rows (`CapabilityNode`), value stream
    stages, transformation initiatives (Roadmap), domain integrations and diagrams.
  - `EmptyState` primitive (title, why, next step, optional action; `compact`) on the Applications,
    Frameworks, Themes, Objectives and Initiatives lists. Agents and Patterns still show "No ... match".
  - Docker: CPU-only torch is installed before the editable install (`--index-url
    https://download.pytorch.org/whl/cpu`). Image 9.89 GB -> 2.42 GB; `torch.cuda.is_available()` is False.
  - Tests: an autouse root-conftest fixture replaces `adp.knowledge.embedder._load_model` with a fake
    model for every test outside `tests/integration` (opt out with `@pytest.mark.real_embedding_model`).
    The per-file `index_entity` stubs are now redundant but left in place.
  - Gotcha: when checking destructive UI in a browser, NEVER click a Delete button on live data to see
    whether a dialog appears -- capability rows deleted on one click. Assert on a scratch record.
- Fable review P3 batch 1 (epic ADP-blp: .8 .10 .11 .21 .23 .24 .39 .51 .52 .55 .58, parts of .13 .49):
  - Docker: three stages (frontend, `python-build` with gcc, runtime without); the venv is at
    `/opt/venv` (editable install pointing at `/app/src`); the image runs as user `adp` (uid 10001).
  - Headers: HSTS and a Content-Security-Policy on every response except the relayed `/auth/` pages
    (`ADP_CONTENT_SECURITY_POLICY` overrides it; empty string sends none). Default allows inline styles,
    not inline scripts. `/openapi.json` is still public (the CI ZAP scan reads it).
  - Audit CSV export prefixes formula-like cells with an apostrophe (`_csv_cell`). The export is still
    open to every role.
  - `JwksCache.get_keys_for(kid)`: a token naming an unknown key id triggers one early JWKS refresh, at
    most every 30 s. Tests that mock `get_keys` keep working (the kid is checked against its result).
  - `adp.background.spawn()` replaces bare `asyncio.create_task` for reasoning-log and knowledge writes
    (strong reference, failures logged); `drain()` runs at shutdown.
  - Pattern adoptions: `_to_models` loads any number in six queries; parsed definitions are cached by
    digest (`_parsed_definition`).
  - Lists: knowledge and diagram lists select only summary columns; the roadmap loads all initiative
    links in one query. No pagination was added.
  - `GET /api/v1/portfolio/counts` + `useEstateCounts`: Overview no longer downloads six collections.
  - UI: `--ink-3` darkened (light) / lightened (dark) to reach 4.5:1; text on accent backgrounds uses
    `--accent-ink`; dead `var(--accent, #2874A6)` fallbacks removed. Nav: Application Portfolio moved to
    Workspace, Diagrams to the Design group, every item has its own icon. Decommissioned / abandoned show
    as neutral, not red (the seven tone maps are still separate). The initiative control-mapping editor
    picks a control by framework, then control, instead of a typed id.
- Fable review P2 batch 5 (epic ADP-blp: .48, .53, .62) -- the last P2s:
  - Routing: the app's location is mirrored into the URL hash (`web/src/shell/routing.ts`:
    `#/<view>[/<entity id>][?design=DSN-x]`, plus `#/applications/capabilities/<id>` and
    `#/patterns/adoptions/<id>`). `App.tsx` state stays the source of truth: a `route` memo is pushed to
    history, and `popstate`/`hashchange` are applied back. Back/Forward, reload and pasted links work.
    Tabs and filters are NOT in the URL yet. `auth/keycloak.ts` sets a deep-link hash aside in
    sessionStorage before the login redirect and restores it afterwards (keycloak-js uses the fragment too)
    -- NOT yet exercised against a real Keycloak. `tests/setup.ts` resets the hash before each test.
    Gotcha: `page.goto` to the same URL with a different hash does not reload the page, so a browser check
    can run stale modules -- call `page.reload()`.
  - Permissions: `GET /api/v1/auth/permissions` (`adp.api.routers.me`) returns the caller's role and
    granted actions from `PERMISSION_GRANTS`; `web/src/auth/permissions.ts` `useCan(action)` (allowed until
    loaded or if the request fails). Applied to the create buttons on Agents, Compliance frameworks, and
    Strategy themes/objectives/initiatives (disabled, with the reason as a tooltip). Other write controls on
    those screens still fail after the click.
  - Save feedback: `apiRequest` raises a `adp:write` window event after every successful non-GET request
    (not for AI operations, chat, dry runs, renders); `ui/Toaster` in the shell shows "Saved" / "Removed".
    Inline ticks (`useLinkFeedback`) remain alongside it.
- Fable review P2 batch 4, UI shell (epic ADP-blp: .44, .45, .54, .56, .60); frontend only:
  - Search: `ui/SearchPalette` (`SearchLauncher` in the top bar, Ctrl/Cmd+K) over `GET /api/v1/search`;
    `App.onOpenSearchResult` opens capabilities, applications, application capabilities, technical
    capabilities and agents on their own screens, other kinds on Business. Rendered in a portal: the top bar's
    `backdrop-filter` makes it the containing block for `position: fixed`. The dead notifications bell is gone.
  - Renames: nav "APM" -> "Application Portfolio", "Intake" -> "New Design"; Governance tab "Compliance" ->
    "Design Validation"; application tabs "Risk & Compliance" -> "Risk Profile", "Regulatory Compliance" ->
    "Regulatory Mappings"; Governance's "<- APM" button removed. The top-bar title is the nav label
    (`titleFor`), no separate TITLES map. Active nav item has `aria-current="page"`.
  - `ui/Tabs` (role=tablist, arrow/Home/End keys, roving tabindex; `variant="pill"`) replaces eight inline tab
    bars (Business, Governance, Strategy, Intake, Applications, Application detail, both Admin screens).
    Tests find tabs with `getByRole("tab", ...)`, not "button".
  - `PageHeader` on Business, Strategy, Insights, Knowledge, Technical Architecture, Governance and
    Application Portfolio; seven pages no longer force Arial. The split-layout registries (Applications,
    Agents, Patterns, Compliance) still rely on the top-bar title.
  - `chat/AskAiLauncher`: "Ask AI" in the top bar opens the chat assistant in a side drawer on any screen
    (passed to the shell as `topActions`, so `ui/` imports no feature code).
- Fable review P2 batch 3, frontend code (epic ADP-blp: .31, .32, .33, .35, .40):
  - Code splitting: every page except Overview is `React.lazy` in `App.tsx` (PageBoundary's Suspense shows
    the loading state). First load 195 kB (57 kB gzip), was 1,782 kB; the diagram editor chunk (626 kB) loads
    only for diagram views. `@xyflow/react` was unused (only a provider in `main.tsx`) and is removed.
  - ESLint works: `web/eslint.config.js` (flat config: typescript-eslint, react-hooks, jsx-a11y; vendored
    `src/diagrams/core` and `editor` ignored). `npm run lint` = `eslint src tests --max-warnings 0`, clean,
    and runs in CI with `vite build`. Run it as `./node_modules/.bin/eslint` if the rtk hook breaks `npx`.
  - One request helper: `apiRequest` in `api/client.ts`; `apiGet`/`apiMutation`/`application.ts`'s `apiFetch`
    all use it. An `ApiError`'s message is now the server's reason (`detail` string, field errors joined,
    or `detail.message`), falling back to "<METHOD> <path> failed: <status>". Use `hasStatus(err, 403)`,
    never `message.includes("403")`. One `errorDetail` (re-exported by the three modules that had copies).
  - Control tree: `GET /compliance/frameworks/{id}/control-objectives` +
    `useFrameworkControlObjectives` replace one request per control (`useControlObjectives` is gone).
    The per-stage "Automated by" lookups are unchanged (a handful per value stream).
  - Accessibility: `ui/clickableRow` (role=button, Tab, Enter/Space) on the list rows that open a detail
    view; `ui/ModalOverlay` (role=dialog, aria-modal, Escape, focus in/restore, Tab trap) replaces eight
    hand-built `position: fixed` backdrops; sibling labels got `htmlFor`/`id`.
- Fable review P2 batch 2 (epic ADP-blp: .16, .17, .18):
  - Event loop: embedding and SVG rasterising run in worker threads (`EmbeddingProvider.aembed`,
    `aembed_or_zero`, `asyncio.to_thread` in `SearchIndex.upsert/hybrid_search`, the knowledge and CALM
    routes, `KnowledgeRetriever.vector_search`, diagram PNG export, `RenderOrchestrator.arender`). One loaded
    model per name for the process (`embedder._models`). `SearchIndex.upsert` does nothing when the stored
    text is unchanged (one lookup, no re-embed, no write).
  - Strategy reads are bulk: `_statuses_for_objectives` (one progress query), `_rows_to_summaries`,
    `_summaries_for_ids`, `_rows_to_themes`; `sinit.get_initiatives(ids)` loads any number of initiatives in
    eight queries (`_control_mappings_by_initiative`). List objectives/themes, the heat map, the Overview
    tally, the reverse lookups and `GET /strategy/initiatives` no longer grow with row count (guard
    `tests/unit/strategy/test_bulk_reads.py` counts queries). The strategy export's recorded N+1 deviation
    is gone.
  - Export loops (`adp.export.common`): `_write_entity_file` skips a file with one `stat()` when its data
    digest and the file's mtime/size match what this process last saw (`_seen`); a cycle takes a Postgres
    transaction-level advisory lock per domain (`_try_cycle_lock`) so a second worker arriving during a
    cycle skips it. Still open: the DB is re-read every cycle and the file phase is not threaded.
- Fable review P2 batch 1 (epic ADP-blp: .5, .6, .9, .19, .20, .22):
  - Limits (`adp.api.limits`): `BodySizeLimitMiddleware` refuses bodies over `ADP_MAX_REQUEST_BYTES` (default
    2 MiB, 0 = off) with 413, counting received bytes as well as Content-Length; `enforce_llm_rate_limit`
    (app-level dependency, limiter on `app.state` so each `create_app()` starts clean) returns 429 +
    Retry-After after `ADP_LLM_RATE_LIMIT_PER_MINUTE` (default 30, per user, per worker, 0 = off) on the six
    model-calling POSTs (chat messages, intake, recommend, validate, both agent-review routes). Chat
    `content` max 20,000 chars, `diagram_context` 200,000; diagram PNG export refuses an SVG declaring more
    than 10,000 px per side.
  - Auth proxy: `/auth/*` forwards only `realms/<realm from ADP_KEYCLOAK_ISSUER>/...`, `resources/` and `js/`;
    admin console, master realm and dot segments get 404. Realm file enables brute-force protection.
  - Metrics: request metrics are labelled by the matched route template (`_metric_route`), "unmatched" for
    anything that matched no route.
  - `DesignStore.list_all` is one joined query and accepts `page_size=None` (all designs); Governance
    exceptions uses it (it silently covered only the 50 newest designs).
  - Design export: the route awaits `ExportOrchestrator.aexport()` (loads the design, then runs the sync
    pipeline in a thread against a prefetched store). The sync `export()` failed against the real async
    store with "This event loop is already running" -- the old tests only used a sync mock.
  - LLM client: one shared `httpx.AsyncClient` per event loop (`_shared_client`, closed in lifespan),
    `httpx.Timeout(read, connect=10)`, and `_post_with_retry` (2 retries with backoff on 429/5xx/529 and
    connect errors, honours Retry-After, never retries a read timeout). Streaming calls are not retried.
    Tests patch `adp.llm.client.httpx.AsyncClient` as before (the cache is keyed by the client class).
  - Follow-up ADP-blp.64 (needs a deployed check): forwarded headers, sslRequired, allowedIpRanges, /metrics.
- Fable review P1 fixes (epic ADP-blp "Fable Recommendations", 63 beads from a 2026-11-17 review; this is
  .1-.4, .14, .15, .30, .43):
  - Auth (`adp.auth`): no recognised group now maps to REVIEWER, not TECHNICAL_ARCHITECT; new `Reviewer` group
    (also in `infra/keycloak/adp-realm.json` and the frontend's `groupsToRole`). A token must belong to this
    client: `azp == ADP_KEYCLOAK_CLIENT_ID` or the client id in `aud` (jose's `verify_aud` stays off because
    Keycloak sets aud="account"). `ADP_AUTH_ENABLED` turns auth off ONLY for false/0/no/off; anything else keeps
    it on, and startup logs the mode (`log_auth_mode`). DEPLOY NOTE: existing realm users with no group lose
    write access until they are put in a group.
  - Initiatives: every route returning a `StrategyInitiative` (strategy router and the six compliance reverse
    lookups) drops APPLICATION-targeted `control_mappings` unless the caller holds READ_APPLICATION_GOVERNANCE
    (`sinit.without_application_mappings`, `_initiative_redactor` dependency).
  - One engine: new `adp.db` (`get_session_factory()`, `dispose()` in lifespan shutdown; per event loop and per
    URL; `ADP_DB_POOL_SIZE`/`_MAX_OVERFLOW`/`_POOL_RECYCLE`, default 10/10/1800, `pool_pre_ping`). Every store's
    `_get_session_factory()` returns the module's own `_session_factory` if a test set it, else the shared one
    -- so existing monkeypatch fixtures are unchanged. `get_design_store` keeps one `DesignStore`
    (`DesignStore.from_session_factory`) instead of a new engine per request. Not yet moved: `KnowledgeRetriever`,
    the CALM importer and the CLI indexer.
  - Frontend: `ui/PageBoundary` (error + Suspense boundary inside the shell, keyed by view, "Try again" resets
    failed queries) so a failed suspense query no longer replaces the whole app; `tokens.css` aliases `--text`,
    `--text-secondary`, `--error`, `--danger`; guard test `tests/unit/css-tokens-defined.test.ts`.
  - Gotchas: several of these files are CRLF (`auth/tokens.py`, `auth/middleware.py`, `api/deps.py`,
    `store/store.py`, `business/store.py`, `ui/tokens.css`, `AuthProvider.tsx`) -- edit with newline-preserving
    I/O. Never call `asyncio.run()` in a sync test: it clears the thread's event loop and breaks later tests
    that use `asyncio.get_event_loop()` (use a private `new_event_loop()`).
- ADP-321 (initiative linkage for agent compliance mappings, follow-on to 944): 925's remediation loop now
  covers all six mapping targets. Migration `053` adds `initiative_control_agent_mapping` in 034's shape (composite
  FK to `control_agent_mapping`, CASCADE on every leg); `adp.strategy` gains a `control_agent_mapping` mirror and
  AGENT entries in both initiative dispatch tables. Routes POST/DELETE
  `/strategy/initiatives/{id}/control-mappings/agents/{control_id}/{agent_id}` and GET
  `/compliance/controls/{id}/mappings/agents/{agent_id}/initiatives` (not governance-gated, like agent mappings).
  UI: agent target (registry picker) in `InitiativeControlMappingEditor`, agent rows by name, and the
  "Remediation:" line on agent rows in `ControlMappingsEditor`. 944's guard `test_initiative_agent_excluded.py` is
  replaced by `test_initiative_agent_mapping.py` (dispatch covers every MappingTargetType). Contract fixture
  gotcha: import `adp.strategy.initiatives` before `sstore._metadata.create_all`, and create sstore LAST (it
  mirrors cstore's `control_agent_mapping`). 2743 backend, 841 frontend.
- 944-agent-traceability: Implemented (ADP-12x, Agentic P3 of `docs/agentic-solutions-plan.md`; clarify
  2026-11-16: capability links L3 only, the FR-013 risk rule as written, agent and solution compliance kept
  separate). Three additions to the 933 agent registry, all derived data computed on read.
  - Automates links (migration `052`, FKs CASCADE only in the migration): agent -> business L3 capability /
    value stream stage / value chain activity, owned by `adp.agentic` and validated through narrow mirrors
    (`adp.agentic` still imports no other domain package). Store `add_link/remove_link/get_automates/
    list_agents_for(kind, ...)`; L3 rule -> `LevelRuleError` 422. Routes under `/api/v1/agentic/`:
    `/agents/{id}/automates[...]` and reverse lookups `/capabilities|value-stream-stages|
    value-chain-activities/{id}/agents` (on the agentic router so `adp.business` doesn't import agentic).
  - Compliance: `MappingTargetType.AGENT` + `control_agent_mapping` (033 shape) in `adp.compliance`;
    PUT/DELETE `/controls/{id}/mappings/agents/{agent_id}`, GET `/compliance/agents/{id}/mappings` (+ derived
    status) and `/compliance/agents/statuses?ids=` (max 200). Agents feed `get_entity_compliance_status`,
    the framework roll-up and the summary. Initiative linkage stays at five types (guard
    `test_initiative_agent_excluded.py`; follow-on ADP-321). Never filtered by READ_APPLICATION_GOVERNANCE.
  - Risk: pure `adp.agentic.risk` -- high = autonomy >= 3 and (approval none or confidential/restricted
    data); medium = autonomy >= 2 or sensitive; else low. `Agent.agentic_risk` on every read (no query);
    `SolutionAgentListResponse.solution_risk` = highest non-retired member, null = "No agents". Tools are
    `not_considered` until P2 (ADP-a00 noted). Guard `test_agentic_risk_not_stored.py`.
  - UI: Agent detail gains Automates (save on choose; stage/activity via stream/chain first), Compliance and
    risk; Agents list Risk column; Agents tab solution banner + per-agent risk and compliance; "Automated by
    agents" expander on business L3 rows and list on value stream stages (`web/src/agentic/AutomatedBy.tsx`);
    Agent target (registry picker) in the control mapping editor; `CapabilityNav.openAgent` +
    `AgentsPage initialAgentId`. First frontend value chain hooks (`useValueChains/useValueChain`).
  - Export: agent files gain `automates` and `compliance_mappings` (fixed 6 queries/cycle). Seed phase D: L1
    "Technology & Architecture" > "Architecture Management" L3s automated by ADP's agents, chat assistant
    mapped to EU AI Act Art. 50 (framework found by name or created); new tables in WIPE_TABLES (not run).
  - Gotchas: fixtures creating bstore + agstore must create bstore first; agstore before cstore (cstore
    mirrors `agents`). `ValueStreamStageEditor.tsx` is CRLF -- edit with newline-preserving I/O.
  - Tests: 2740 backend, 839 frontend. Verified live (migration up/down/up on Postgres, curl quickstart,
    Playwright). Follow-on ADP-aav (agents on a future value chain activity screen).
    See `specs/944-agent-traceability/`.
- 943-mapping-rationale: Implemented (ADP-55k.4, spec 4 of 4 in epic ADP-55k; clarify 2026-11-16 confirmed
  all four defaults). 937's realization link (application capability L3 <-> application) gains an optional
  `rationale` (target / tactical / transitional / redundant; NULL = unclassified) and an optional `geography_id`
  (region or country; NULL = everywhere; Global refused with "No geography already means everywhere").
  - Migration `051`: two nullable columns, a CHECK, and an FK SET NULL that exists ONLY in the migration. The
    astore metadata declares a plain column, because geographies live on the organization metadata (940
    precedent). A dangling id reads as everywhere, which gives SQLite parity.
  - Writes: `POST /{ac_id}/applications` accepts both fields; new `PATCH /{ac_id}/applications/{app_id}`
    (omitted = unchanged, explicit null clears, an empty body is a 422) logs
    `app_capability.realization.update` old->new. Writes ride the WRITE_APPLICATION prefix rule.
  - Validation goes through two new public read-only helpers, `ostore.geography_level` and
    `ostore.geography_index` (application -> organization direction, lazy import).
  - 938's pure `findings()` now gives each overlap `status` (needs_attention | explained), `reasons`
    (unclassified, redundant, no_target, competing_targets) and `applications[].mappings`, ordered
    needs-attention first.
    - `no_target` is reported only when nothing is unclassified or redundant.
    - competing_targets = 2+ targets of DIFFERENT applications whose scopes overlap: either is
      everywhere, or one geography contains the other.
  - `findings()` also returns `redundant[]`, grouped by business L3 (null group last), with TIME, 7R and
    `consistency_hint`: target + Eliminate/Migrate, or redundant + Invest. The hint is advisory only and
    server-side only; `realized_by` entries carry rationale, geography and hint too.
  - The snapshot reads the geography index ONLY when some realization names a geography, so 938's query
    count and its fixtures are unchanged. The guard test forbids status/reason columns.
  - UI:
    - `RealizationList.tsx` replaces the generic "Realized by applications" list. Rationale and geography
      selects save on choose (the ADP-w7z convention); the multi-field add row keeps a Link button.
    - Overlaps tab: "Needs attention (n)" / "Explained (n)", with reason chips.
    - A fourth "Redundant" tab.
    - The application's own capability list shows its rationale chip.
    - The Governance Overlaps tile counts needs_attention only, with "n explained" beneath.
  - Export: `realizations[]` on application capability files (`realized_by_application_ids` kept).
    Seed phase G (not run locally).
  - Gotchas:
    - fixtures needing geographies create astore metadata then ostore (`checkfirst` skips the mirrors);
    - the speckit `update-agent-context.sh` truncated older Recent Changes entries here, so CLAUDE.md
      entries are added by hand.
  - Tests: 2596 backend, 816 frontend. See `specs/943-mapping-rationale/`.
- 942-regional-assessments: Implemented (ADP-55k.3, spec 3 of 4 in epic ADP-55k; `/speckit-clarify` skipped,
  the spec's Assumptions stand). A business capability can be assessed per REGION or COUNTRY, never Global:
  a maturity score on the global 1-5 scale and/or a variant note, at most one per capability and geography
  (upsert `PUT /api/v1/business/regional-assessments/{cap_id}/{geo_id}`). The capability's own `maturity_level`
  is the BASELINE and is never written by these routes; the guard `test_regional_not_stored.py` checks that
  migration `050` alters no existing table.

  Region-specific scope: a 1:1 `region_specific_capabilities` flag table plus its geographies
  (`PUT /capability-region-scope/{cap_id}`, replace; false clears). It is a separate table so the flag
  survives losing its last geography, which then shows "scope needs updating".

  The pure `adp.organization.regional_analysis` derives, over a 4-query snapshot:
  - applicability by containment both ways (a Brazil-only capability is applicable in the Americas column);
  - cell states: not_applicable > assessed (with delta vs baseline) > not_assessed;
  - the heat map (`GET /regional-heatmap?geography_ids=`; defaults to the regions, max 12 columns, Global refused).

  There is NO roll-up across capability levels and NO inheritance between regions and countries. Deleting a
  geography removes its assessments and scope rows but keeps the flag. The organization store's
  `business_capabilities` mirror gained a nullable `maturity_level` (astore's mirror has none).

  UI:
  - a Capabilities | Regional switch on the Heat Map tab. `RegionalHeatMap` is a `<table>` in its own
    `overflow-x: auto` area, with click-to-edit cells, ▲/▼ against the baseline and the note in the cell title;
  - the column choice and view live in BusinessPage state (session);
  - a "Regions" expander on each capability row (`RegionalAssessmentsPanel` + `RegionScopeEditor`);
  - the 5-step maturity swatches moved to `web/src/business/maturityScale.ts`, shared with `CapabilityHeatMap`.

  Export: a `regional` block on capability files. Seed phase C5 adds a new L3 "Statutory eSocial Reporting"
  under Human Capital Management, Brazil-only. Gotcha found live: don't mix the `border` shorthand with
  `borderStyle` in a cell style that changes; React warns and can mis-style it. Use longhands. See
  `specs/942-regional-assessments/`.
- 941-capability-org-mappings: Implemented (ADP-55k.2, spec 2 of 4 in epic ADP-55k). One table,
  `capability_org_mappings` (migration `049`), links a business capability to a 940 org unit with a role:
  owner (L1/L2, at most one per capability: partial unique index plus a replace-only `PUT .../{cap_id}/owner`),
  performer (L3, optional geography) or contributor (L3, no geography). Uniqueness uses
  `COALESCE(geography_id,'')` so "everywhere" can't be added twice. Level rules are enforced in
  `adp.organization.cap_mappings` with rule-named 422s (`LevelRuleError`; unknown body ids raise
  `UnknownReferenceError`, also 422). Everything else is derived on read by the pure
  `adp.organization.cap_org_analysis` over a 4-query snapshot, never stored (guard
  `test_cap_org_analysis_not_stored.py`):
  - the effective owner: own, else the nearest owned ancestor;
  - an outside-geography note: the geography is not one of the unit's operating geographies or inside one; never shown for a unit with no operating geographies;
  - findings: no owner (L1/L2), shared-service candidates (L3s with >= 2 INDEPENDENT performers: a unit and its own descendants fold into one branch), unmapped L3s, owned L3s with no performer;
  - each org unit's footprint, including its sub-units, attributed.

  Routes: `/api/v1/business/capability-org-mappings` (GET bulk, `/findings`, PUT owner, POST, DELETE) and
  `/org-units/{id}/footprint`, served by the organization router. Writes use the business prefix rule, so
  there is no new permission. Deletes: deleting an org unit removes its mappings; deleting a geography first drops performer
  rows that would collide with an existing "everywhere" row, then clears the rest (FK CASCADE / SET NULL as
  a safety net). The organization store mirrors `business_capabilities` narrowly (position nullable, since
  astore's mirror has none). Fixtures that also create the bstore or astore metadata must exclude it from the
  ostore `create_all`.

  UI:
  - owner chip (own or "(inherited)") and performer chip on each capability row, plus an Organization expander. The name column needs `minWidth: 0` so the chips truncate instead of pushing the row's controls off-screen;
  - a Findings sub-tab on Business → Organization, whose entries open the focused capability via BusinessPage's `focusCapabilityId`;
  - the footprint in the org-unit panel.

  Export: an `organization` block on each capability file. Seed: phase C4. 2493 backend, 775 frontend.
  Follow-on: ADP-m7x (Governance tiles). See `specs/941-capability-org-mappings/`.
- 940-org-units-geography: Implemented (ADP-55k.1, spec 1 of 4 in epic ADP-55k "organization & region dimensions on
  the capability model"; decisions D1-D7 in the epic notes). New package `adp.organization` (routes under
  `/api/v1/business/`, so the existing WRITE_BUSINESS_ARCH prefix rule covers writes -- no new permission): governed
  Org Unit tree (enterprise > division > function) and a separate Geography tree (global > region > country) with 937's
  hierarchy rules; org unit <-> geography many-to-many + optional primary geography; `applications.owning_org_unit_id`
  (plain column in astore, real FK only in migration `048`; the application router validates through
  `adp.organization.store.org_unit_exists`). Geography is SEEDED BY THE MIGRATION from the committed
  `src/adp/organization/data/geographies.json` (UNSD M49 + ISO 3166, 255 rows, stable ids `geo-001` / `geo-m49-NNN` /
  `geo-XX`; AQ and TW sit directly under Global) via the dependency-free `adp.organization.geodata` loader shared with
  tests. Review queue (`/org-units/unmatched`, `/unmatched/resolve`) maps each EXACT free-text owning_business_unit value
  to an org unit (existing or created in the same call); it never writes the free text and never merges near-duplicates.
  UI: Business -> Organization tab (Org units | Geography | Unmatched), org-unit picker on the application form,
  Portfolio groups business units via `withOrgUnitLabels()` (org unit name, else "<text> (unmatched)"). Search indexes
  org units only (geography deliberately not). Export `business-architecture/organization/`. Seed phase C3 adds an org
  tree, geography links and unmatched values; `geographies` is NEVER in WIPE_TABLES. Gotchas: fixtures creating both
  astore and ostore metadata must create astore first and exclude ostore's narrow `applications` mirror; tests rendering
  PortfolioPage must mock `../api/organization`. 2443 backend, 749 frontend. See `specs/940-org-units-geography/`.
- 939-governance-architecture-health: Implemented (ADP-loz + ADP-n2t). Governance gets a fourth tab, "Architecture
  Health": five tiles (non-conformant / indeterminate adoptions, exposed business L3s = exposure past_end_of_life or
  retiring, overlaps, gaps), a Patterns section (non_conformant -> indeterminate -> conformant_with_warnings, rest
  summarized, each opens the adoption on the Patterns screen) and a Capabilities section (exposed L3s with band + path,
  then 938's `CapFindingsViews` overlaps/gaps). FRONTEND ONLY -- reads `useAdoptions(true)`, `useCapabilityRollup`,
  `useCapabilityFindings`, `useCapabilities` (for paths; the roll-up has no parent ids); pure derivations in
  `web/src/governance/architectureHealth.ts` shared by tiles and lists. New cross-screen entry: App.tsx
  `pendingAdoptionId` -> `PatternsPage initialAdoptionId` -> `AdoptionsList initialSelected`. Tiles show "…" while
  loading and "—" on error, never a misleading 0; sections fail independently. 728 frontend tests. See
  `specs/939-governance-architecture-health/`.
- 938-capability-model-analysis: Implemented (ADP-6et.2, spec B of epic ADP-6et). Analysis over 937's three-layer
  capability model, all DERIVED ON READ and never stored (guard test `test_cap_analysis_not_stored.py`). Pure engine
  `adp.application.cap_analysis` (no I/O, `as_of` injected) over a frozen `CapabilitySnapshot` built by
  `cap_analysis_store.build_snapshot` in a fixed 6-8 queries; risk/cost are NOT EVEN QUERIED for a caller without
  READ_APPLICATION_RISK/_COST (inline `is_permitted`, response `*_available` flags, null metrics). Roll-ups per business
  capability: health (worst app `health_score`), risk (fixed FR-006 band: high/medium/low/unknown from posture,
  vulnerability, end-of-support; unknown never sets worst), cost (full TCO of DISTINCT apps, not allocated), technology
  exposure (worst effective lifecycle band of technical caps reached via app caps; a linked technical L2 expands to its
  children). L3 = worst over its apps; L2/L1 = worst over leaf L3s with the spread counted over LEAVES. Retired apps are
  excluded (listed as excluded), sunset counted. Also impact (technical cap + descendants -> app caps -> apps -> business
  caps with paths and routes), per-L3 technology dependencies, findings (overlaps = business L3 realized by >=2
  non-retired apps; three gap lists; shared >= 3). Four GETs under `/api/v1/application-capabilities/analysis/` (before
  `/{ac_id}`). Migration `047`: `technical_capabilities.lifecycle_status` (emerging/current/contained/retiring/retired,
  CHECK, default current, Python-side default too) + `end_of_life_date`; PATCH logs old->new; exported. UI: Business heat
  map +4 metrics from ONE lazily-enabled roll-up query (cell detail on hover/focus, cost/risk options disabled "not
  available to you"); tech cap rows get lifecycle select/date, past-EOL flag, Impact expander; business L3 rows get a
  "Technology dependencies" expander; Applications -> Capabilities gets Overlaps/Gaps/Shared tabs. New
  `CapabilityNavContext` (appCapNav.tsx, provided by App.tsx) navigates to business caps/apps/tech caps. Seed: offline
  sync Retiring 2027-06-30, Online Promotion Evaluation (Commerce Cloud) -> Apply Promotions overlap, POS posture weak.
  Gotchas: the seed HARD-WIPES and adp_user cannot CREATE DATABASE, so it was verified by applying the same changes via
  the API rather than a reseed; vitest automock of `../api/application` empties exported arrays/objects (use a partial
  mock with importOriginal when a test needs real constants); app INFO logs don't show in local uvicorn output. Engine
  96% / snapshot+models 100% covered. Follow-ons: ADP-n2t (Governance roll-up), ADP-6ky (editable mapping/horizon/
  threshold), ADP-v2l (history), ADP-3uy (seed cost records). See `specs/938-capability-model-analysis/`.
- 937-application-capabilities: Implemented (ADP-6et.1, spec A of 2 in epic ADP-6et "three-layer capability
  model"). A NEW application capability entity (shared L1-L3 catalog: level derived from the parent, max 3,
  parent/level immutable, delete blocked while children exist, sibling names unique case-insensitive incl. NULL-
  parent roots via a COALESCE expression index) sits between business and technical capabilities. Three many-to-
  many link tables (migration `046`), each with level rules enforced in the store (an FK can't check the far row's
  level), refused with a 422 naming the rule: business L3 <-> application L3; application L3 -> technical L2/L3;
  application L3 realized by applications. No direct business -> technical link. The user's mapping guidance
  (L1 is navigation only, roll-ups come from the leaves, comparable granularity across layers) is in ADP-6et's notes
  and shown in the UI. An L3 with no technical capability gets a governance WARNING (badge plus gaps list), derived
  on read and never stored (guard test); it never blocks saving. The existing application <-> business capability
  (fit score) and application <-> technical capability (provides/consumes) links are UNCHANGED. Links are edited
  only on the application capability (Applications -> new Capabilities tab). The business L3 rows, technical
  capability rows and application detail show read-only, expand-to-load lists that navigate there via
  `AppCapNavContext` (App.tsx). Writes use the `("/api/v1/application-capabilities", WRITE_APPLICATION)` prefix
  rule (no new permission). Search `ENTITY_APPLICATION_CAPABILITY` (text includes the L1/L2 path; renaming
  reindexes descendants) plus backfill. Export `applications/application-capabilities/<id>.json`. `seed_retail.py`
  seeds the user's Store POS example (5 chains plus "Loyalty Points Accrual" with no technical capability).
  Tables are defined in `adp.application.store` (no circular import); models in `app_capability_models.py`.
  Reads inner-join the far end, so SQLite's unenforced FKs never surface dangling links; Postgres CASCADE removes
  them. 2318+ backend, 675 frontend; new modules 95-100% covered; the Docker-gated `test_migration_046.py` runs in
  CI. Verified live after a reseed (API rules, warning lifecycle, search, Playwright across all four screens).
  Follow-on: ADP-6et.2 (roll-ups, impact analysis, gap/overlap). See `specs/937-application-capabilities/`.
- 936-pattern-conformance: Implemented (ADP-mmm.3, spec 3 of 4 in epic ADP-mmm). Pattern adoptions (a pattern
  applied to a business domain / application set / portfolio, optional version pin, role pins; migration `045`:
  ea_pattern_adoption + _member + _pin, partial-unique per domain/portfolio) evaluated by a PURE engine
  (`adp.patterns.engine` over `adp.patterns.snapshot`): pins are AUTHORITATIVE for their role (B2 warning if a pin
  fails the selector, B3 dangling), implicit K:<role>(/per) cardinality and E:<rel> registry evidence
  (integrations / capability links / tech-cap 'provides'), declared CEL constraints with the polarity matrix,
  derived status (not_applicable > non_conformant > indeterminate > with_warnings > conformant) and transition
  plateau -- computed per request and per caller, NEVER stored (guard test). Snapshot (`snapshot_store`, ~13 fixed
  queries via mirrors on the patterns metadata) derives application domain_ids by walking capabilities up to the
  L1 (domains attach only to L1), integration `cross_domain` (null if either side has no domain), and includes
  gated risk/cost(tco via list_all_costs)/governance attributes only for callers holding READ_APPLICATION_*
  (else field_unavailable -> indeterminate). Separate `adoptions_router` registered BEFORE the registry router so
  /adoptions and /evaluate are not taken as {key}; anti-pattern discovery; dry-run POST /evaluate (WRITE_PATTERN);
  conformance/transition flowchart views; UI Patterns|Adoptions toggle, adoption page, pins editor, Discovery tab,
  Evaluate panel, Save as diagram (seed hand-off to the Diagrams editor). Fixed `scripts/seed_retail.py` (was
  broken: health_score passed to ApplicationCreate; now via upsert_health_assessment), added Enterprise Event Hub
  + hub-routed integrations; `seed_patterns.py` creates demo adoptions (M&L conformant, E-commerce non_conformant,
  mesh migration PL1->PL2). Gotchas: the 934 fixture selector `all(d, !(d in target.domain_ids))` is vacuously true
  for domainless apps (seed ships 1.1.0 patterns using `it.cross_domain == true`); Vite HMR can serve a stale module
  after many edits (restart it); `pkill -f <pattern>` can match its own shell. 2282+ backend, 661 frontend; verified
  live after a full reseed. Follow-ons: Governance rollup, conformance history, ADP-n4e renderer legibility.
  See `specs/936-pattern-conformance/`.
- 935-pattern-registry: Implemented (ADP-mmm.2, spec 2 of 4 in epic ADP-mmm). Governed EA pattern registry on
  top of 934's `adp.patterns`: migration `044` (ea_pattern, ea_pattern_version with partial-unique one-current,
  ea_pattern_relation with NO target FK so drafts may reference unwritten families, ea_pattern_lifecycle_event).
  Lifecycle draft->proposed->current->deprecated->decommissioned (+proposed->draft, deprecated->current rollback),
  immutable after draft, every transition needs reason + confirmation_id (GOVERN_PATTERN in REQUIRES_CONFIRMATION);
  WRITE_PATTERN/GOVERN_PATTERN EA+Platform Admin only, PERMISSIONS_VERSION 1.11.0. References (principles, controls,
  relation targets, known implementations) resolve from the stored definition: warnings on import (R1-R4), blocking
  at promotion. Current versions project into knowledge_items as `adp-pattern:<key>` (reference-architecture ->
  reference_architecture, else pattern; deactivated, never deleted, when no version is current); the nightly indexer
  skips them, the knowledge API refuses to edit/forge them (409/422), control_pattern_mapping now also accepts
  reference_architecture. Pure `adp.patterns.render` emits the vendored diagram-core flowchart dialect (NOT real
  Mermaid: unquoted sanitised labels, parentheses are metacharacters, no x-arrowheads); goldens are parsed by a vitest.
  5th export task writes patterns/<key>@<version>.yaml byte-identical to the download. New Patterns screen (Oversight).
  `scripts/seed_patterns.py` seeds 4 patterns citing real PRIN-* principles (run after seed_knowledge.py; the 934 unit
  fixtures cite placeholder P-* ids and share keys, so import them only AFTER seeding or with another version).
  Gotchas: JSONB loses object key order, so definitions are stored in 934's canonical form (roles as [key, role]
  pairs); `jq` is not installed on the dev box. 2181 backend (+180), 648 frontend (+39); verified live (migration
  044 up/down/up, seed, curl quickstart, Playwright). Follow-ons: ADP-4zn (indexer sweeps API/CALM items - bug),
  ADP-ufu, ADP-wmu, ADP-8nq, renderer legibility. See `specs/935-pattern-registry/`.
- 934-pattern-metamodel: Implemented (ADP-mmm.1, spec 1 of 4 in epic ADP-mmm "EA Patterns-as-Code", source
  `docs/PATTERN-01-metamodel-and-yaml.md` + the review addendum in `docs/PATTERN-00-bundle-overview.md`).
  New pure-library package `adp.patterns` (no DB/API/UI -- spec 935 adds the registry and first UI):
  frozen Pydantic `PatternDefinition` (roles/relationships/CEL constraints/motivation/transition plateaus),
  hardened YAML parser (`parse_pattern_yaml` never raises; rejects >256 KB, anchors/aliases, multi-doc;
  every problem is a `PatternIssue{path, code, message}` with codes P0-P5, schema.*, V1-V9), canonical
  JSON/YAML + SHA-256 digest (roles encoded as ordered pairs so key-sorting can't erase role order), and
  `generated/pattern.schema.json` via `adp-generate` (accepts cardinality shorthand). Corrections vs the
  source doc: no `technology_standard` element type (no such entity), `agent` added, relationship `owns`
  dropped (no evidence source), no `lifecycle` in authored YAML (registry state). NEW DEPENDENCY
  `cel-expr-python==0.1.4` (Google cel-cpp), chosen by a 3-library spike (research.md D1): the only one with a
  real compile-time checker and a built-in iteration budget (fixed, ~5-10k comprehension iterations per
  evaluation, not configurable from Python) -- wrapped behind `adp.patterns.cel.CelEngine` so it can be swapped
  (fallback `common-expression-language`). Gotcha: a `bound(map, string)` function must be declared with a
  `map<string,dyn>` first parameter -- a `dyn` parameter did not match map arguments at runtime. 116 new tests
  (2001 backend total), patterns coverage 88-100% per file, ruff/mypy/bandit/adp-generate clean.
  See `specs/934-pattern-metamodel/`.
- 933-agent-registry: Implemented (ADP-hii, P1 of the agentic-solutions plan `docs/agentic-solutions-plan.md`,
  planning bead ADP-wma) -- full `/speckit.specify` → clarify → plan → tasks → implement cycle. An agentic
  solution is an ordinary Application with new `application_type="agentic"`; its AI agents live in a new
  solution-independent registry, joined many-to-many (`solution_agents`: role
  orchestrator|worker|reviewer|router + position normalised 0..n-1). New sibling package `adp.agentic`
  (`adp.agents` is taken by the Agent Review toolkit) with `/api/v1/agentic/agents` CRUD and
  `/api/v1/agentic/solutions/{app_id}/agents` (+ PATCH role, PUT `/order`, DELETE). Migration `043`
  (`down_revision="042"`): drops/re-creates `ck_app_application_type` with 'agentic' (downgrade nulls agentic
  rows first), new `agents` (ADP 0-4 autonomy scale, human_approval, prompt_ref = version reference only,
  data_classification_max, a2a_card_url http(s)-only, design-time cost estimates, `external_registry_ref` for
  a future runtime-registry link) and `solution_agents` (composite PK, CASCADE both legs). Clarified with the
  user: agents only on agentic apps (reclassifying an agentic app that still has agents → 409, guarded in
  `adp.application.store.update_application` via a narrow `solution_agents` mirror; `delete_application`
  deletes memberships explicitly, never agents); cost estimates gated like application cost (reads redact to
  null + `cost_visible=false` without READ_APPLICATION_COST, setting them needs WRITE_APPLICATION_COST).
  Writes reuse `WRITE_APPLICATION` via a new `/api/v1/agentic/` prefix rule -- no new ActionType. Audit =
  actor-attributed structured logs (application/compliance precedent). Search `ENTITY_AGENT` (+ backfill;
  note `/api/v1/search` defaults to capability types -- pass `entity_types=agent`), export
  `agentic/agents/<id>.json` with `solutions[]` (new `adp.export.agentic`, 4th lifespan export task), seed
  (`scripts/seed_retail.py` Phase D: ADP itself as an agentic solution with its 5 agents). Frontend: new
  "Agents" nav view (`web/src/agentic/`: AgentsPage list+filters, AgentDetail with solution links that open
  the application, AgentForm, SolutionAgentsPanel), Agents tab on agentic applications, `isHttpUrl` extracted
  to `web/src/ui/url.ts`. Fixture gotcha: any fixture creating both `astore` and `agstore` metadata must
  create astore first EXCLUDING `solution_agents`, then agstore (see tests/contract/test_agentic_api.py).
  1885 backend tests (+64), 609 frontend (+20), ruff/mypy/tsc/adp-generate clean; Docker-gated
  `tests/integration/test_migration_043.py` runs in CI. Verified live on local Postgres (migrations 042+043
  applied) and in the browser via Playwright; scratch data cleaned up. See `specs/933-agent-registry/`.
- 933-agent-registry: Added Python 3.12 (backend); TypeScript 5.x + React 18 (frontend). Both are existing stacks. + FastAPI ≥ 0.111, SQLAlchemy 2 async (Core), asyncpg, Alembic, Pydantic v2; React 18, TanStack Query v5. All are existing, with **zero new packages**.
- ADP-nag (value chain data model, part of epic ADP-o9p "consume Canvas diagram-core as a package +
  value stream & value chain diagrams"): Porter value chains as a first-class Business Architecture
  entity, mirroring value streams. Migration `042` (`down_revision="041"`): `value_chains`
  (`margin_label` NOT NULL default 'Margin'), `value_chain_activities` (`category` CHECK
  primary|support, position ordered *within* its category), `value_chain_activity_capabilities`
  (composite PK, CASCADE both legs). Tables live on `adp.business.store._metadata` (so the FK to
  `business_capabilities` resolves and every fixture's `create_all()` picks them up); the functions
  live in a new sibling `adp.business.value_chains` (the `adp.strategy.initiatives` split
  precedent, since the business core files are already past the size threshold), routes appended to
  `adp.business.router` under `/api/v1/business/value-chains` (+ `/activities`, reorder via
  `PUT .../activities` with `{category, activity_ids}`, `/activities/{id}/capabilities`). Two
  deliberate differences from value stream stages: activity positions are kept normalised to
  0..n-1 per category on every add/move/delete/reorder (stages allow gaps/duplicates), and a reorder
  only reorders (rejects a mismatched id list with 422) rather than doubling as a bulk delete. Deletes
  remove child rows explicitly so they behave the same on SQLite (no FK enforcement) as Postgres; the
  migration's cascade stays as the safety net. Authz rides the existing
  `("/api/v1/business/", WRITE_BUSINESS_ARCH)` rule (no new ActionType). Search: new
  `ENTITY_VALUE_CHAIN`/`ENTITY_VALUE_CHAIN_ACTIVITY` with write hooks and backfill; deliberately NOT
  added to chat retrieval (`DEFAULT_ENTITY_TYPES`) -- chat/strategy/design links for value chains are
  deferred. Export: `business-architecture/value-chains/<id>/value-chain.json` +
  `activities/<id>.json` with `linked_capability_ids`, orphan cleanup at both levels. 1821 backend
  tests (was 1768, +53: 27 store, 21 contract, 3 export, backfill extended), coverage 87.7%. Migration
  042's DDL, CHECK constraint and both cascade directions were verified on the real local Postgres
  inside a rolled-back transaction (Docker Desktop's WSL integration is off, so the new
  `tests/integration/test_migration_042.py` runs in CI). Gotcha hit and fixed: `store.py`,
  `models.py` and `router.py` are CRLF on main -- editing them through Python text I/O silently
  converted them to LF and made the diff look like a full-file rewrite.
- 932-regulatory-framework-tags: Implemented (ADP-bkg, "Application Risk & Compliance: hook
  regulatory tags to Compliance frameworks" — filed directly by the user while looking at the Risk
  & Compliance tab, confirmed as genuinely disconnected free text before filing) — full
  `/speckit.specify` → `/speckit.clarify` → `/speckit.plan` → `/speckit.tasks` → `/speckit.implement`
  cycle. `ApplicationRisk.regulatory_tags` (APM US3, ADP-SPEC-038) moves from an unvalidated
  `list[str]` of free text (e.g. `"SOX"`, `"GDPR"`) to a governed many-to-many link,
  `ApplicationFrameworkTag`, against the real `RegulatoryFramework` registry (COMPLY-01) — a
  lightweight, unassessed "applies here" tag, explicitly distinct from (and left untouched
  alongside) the separate "Regulatory Compliance" tab's per-control `ControlMapping` assessed
  status (COMPLY-02). Two real clarifications were resolved directly with the user before planning
  rather than guessed: (1) pre-existing free-text tag values are discarded outright at migration
  time (Option B of three), satisfied for free by dropping the old column so the new link table
  starts empty for every application, with zero backfill/matching logic; (2) the framework picker
  only offers `in_force`/`amended` frameworks (COMPLY-01a's `status` field) — but an
  already-tagged framework that *later* turns `repealed` keeps its existing tag untouched, since
  the status gate only governs newly-added ids, confirmed with a dedicated test and a live
  PATCH-then-resave check against real Postgres. The link table deliberately lives in
  `adp.application` (not `adp.compliance`), mirroring `theme_framework_links`' own precedent one
  level up (927) for an unassessed tag; no new endpoint is added at all — the existing batched
  `GET`/`PUT /applications/{app_id}/risk` gained new reconciliation/validation semantics only, no
  new `ActionType`, no `PERMISSIONS_VERSION` bump. Two real, non-obvious regressions were caught
  and fixed during implementation, not anticipated by the plan: (1)
  `adp.export.application_arch._fetch_all`'s own bulk-fetch path called the store's internal
  `_row_to_risk(row)` directly against a raw table row, bypassing the join entirely — broke the
  moment that function's signature gained a required second parameter; fixed with one more bulk
  query grouping tags by `app_id`, preserving the export module's own stated no-N+1 invariant
  rather than reverting to N+1; (2) adding `adp.application.store`'s own narrow
  `regulatory_frameworks` mirror (same idiom `adp.strategy.store` already carries since 927)
  collided with `tests/contract/test_compliance_mappings_api.py`'s `full_client` fixture, which
  creates both `astore` and `cstore` table metadata against one shared SQLite connection — the one
  table where `cstore`, not the other module, is the real full-column owner, inverting that
  fixture's existing `bstore → astore → cstore` ordering assumption; fixed by excluding that one
  table from `astore`'s call rather than reordering the whole fixture (which would have broken the
  three *other*, pre-existing collisions — `business_capabilities`, `designs`, `applications` —
  the original order was already correctly tuned for). 1768 backend tests (was 1753, +15: 11 unit
  in new `test_application_risk_framework_tags.py`, 4 new contract in extended
  `test_apm_risk_api.py`), 589 frontend tests (was 584, +5 in new `RiskPanel.test.tsx`),
  `ruff`/`mypy`/`tsc` all clean. 3 Docker-gated integration tests written
  (`tests/integration/test_application_framework_tags.py`, unavailable locally — same constraint
  every export/COMPLY-0x/928/930/931 suite this session has hit; will run in CI). Verified live
  end-to-end against a real local Postgres (migration 041 applied, downgraded, and reapplied
  cleanly) and a running backend/frontend: every quickstart.md scenario confirmed via direct API
  calls against the three real, live, already-populated frameworks (GDPR, EU AI Act, DORA) plus a
  scratch framework for the status-gate/cascade scenarios (newly-added unknown/repealed ids
  rejected whole-write with no partial save, an already-linked framework surviving its own later
  repeal, cascade-delete removing only the deleted framework's tag), and a full live Playwright
  walkthrough — created a real scratch application through the actual UI, tagged it with two real
  frameworks via the new checkbox picker, confirmed both the picker's status filtering and the
  persisted selection survived a full page reload showing real framework names, then deleted the
  scratch application, confirmed back to the original 18 applications and all three real
  frameworks left completely untouched (still `in_force`, confirmed by id and name afterward). See
  `specs/932-regulatory-framework-tags/`.
  value, and future similar composite scores)" — deferred from the Application Business Value
  assessment build, 2026-08-15) — full `/speckit.specify` → `/speckit.plan` → `/speckit.tasks` →
  `/speckit.implement` cycle. The bead explicitly names its own architectural precedent ("mirroring
  the existing Agent Prompt Management admin surface, ADP-SPEC-042"), so every structural decision
  — registry pattern, override/history table pair, single-transaction write, optimistic-concurrency
  `version`/409, confirmation-gate on edit and restore, `PersonaRole.PLATFORM_ADMIN`-only carve-out
  from the Enterprise Architect wildcard — is a direct, literal mirror of that already-shipped,
  already-reviewed feature, confirmed by reading `adp.admin.{prompt_registry,models,service}` and
  `admin_prompts_router.py` before writing a line of spec. New `adp.admin.rubric_registry` (mirrors
  `prompt_registry`) registers one rubric today (`business_value`, wrapping the existing
  `BUSINESS_VALUE_WEIGHTS` constant as its fallback) but is extensible to any future rubric with
  zero schema change — weights are stored as `JSONB` (not one column per dimension), validated by
  each rubric's own registered callback (exactly 6 keys, sum to `1.0 ± 1e-6` for `business_value`).
  New migration `040`: `rubric_weight_overrides`/`rubric_weight_history`, a line-for-line structural
  mirror of migration 023. New `ActionType.MANAGE_SCORING_RUBRICS` (`PERMISSIONS_VERSION` 1.9.0 →
  1.10.0), granted only to `PLATFORM_ADMIN`, explicitly excluded from Enterprise Architect's
  wildcard — identical precedent to `MANAGE_AGENT_PROMPTS`. `compute_business_value_score()` gains
  an optional `weights` parameter while staying pure/no-I/O (its own docstring's deliberate
  invariant, shared with `adp.strategy.store.compute_status()`) — its two existing callers resolve
  the effective weights via a new self-contained `get_effective_weights()` (mirroring
  `get_effective_prompt()`'s exact signature and resilience property: any DB-resolution failure
  falls back to the hardcoded default) before calling it. New "Scoring Rubrics" admin nav entry,
  sibling to "Agent Prompts" — `ScoringRubricsPage.tsx`/`RubricEditor.tsx` (a numeric input per
  dimension + a live running-sum indicator, since a validated weight set needs a fundamentally
  different control than a prompt's free-text `<textarea>`)/`RubricHistory.tsx`, all new (no
  `PromptEditor.test.tsx`/`AdminPage.test.tsx` existed to mirror either — this feature's own new
  component tests are the first frontend coverage either admin screen has). Explicitly out of
  scope: `BUSINESS_VALUE_EVIDENCE_CAP` (a different data shape, a score→cap lookup, not a weight
  distribution — the bead's own text names only "weights"). 1753 backend tests (was 1721, +32: 10
  unit registry/validator, 14 contract, 2 optional-weights-parameter, 6 authz parametrized
  entries), 584 frontend tests (was 574, +10), `ruff`/`mypy`/`tsc` all clean. 3 Docker-gated
  integration tests written (unavailable locally, same constraint every export/COMPLY-0x/928/930
  suite this session has hit; will run in CI), mirroring `test_admin_prompts_flow.py`'s own
  real-Postgres, no-restart-takes-effect guarantee — including a real
  `compute_business_value_score()` computation confirming an overridden weight set (not the
  default) is what's actually used. Verified live against a real running backend and local
  Postgres: migration applied cleanly (`alembic current` confirmed `040 (head)`); the new
  endpoint's permission denial behaves identically to the existing, already-shipped
  `/admin/agent-prompts` endpoint under the same real dev-mode auth config (both 403 for the
  default `enterprise_architect` role) — confirming the new authz wiring is correctly integrated,
  not just unit-tested. The PLATFORM_ADMIN happy-path (confirm/history/restore) could not be
  curled locally, since this environment runs `ADP_AUTH_ENABLED=false` with a hardcoded
  `enterprise_architect` sentinel and no dev-mode role-override header exists — an accepted,
  already-documented limitation ADP-SPEC-042's own quickstart.md hit identically; that path is
  instead fully exercised by the 14 passing contract tests (a real dependency-override to
  `PLATFORM_ADMIN`) and the written Docker-gated integration suite. See
  `specs/931-admin-ui-editing/`.
  other text fields") — full `/speckit.specify` → `/speckit.plan` → `/speckit.tasks` →
  `/speckit.implement` cycle. **A Ground-Truth Correction found before writing any requirement**:
  the bead's own text assumed phase 2 (value stream + domain indexing) was entirely unbuilt — direct
  code inspection showed `041-ai-chat-assistant` had already wired `ENTITY_APPLICATION`/
  `ENTITY_VALUE_STREAM`/`ENTITY_BUSINESS_DOMAIN` write hooks into `adp.application.store`/
  `adp.business.store` as an incidental side effect of building the Chat Assistant's retrieval leg,
  confirmed via `adp.chat.retrieval.DEFAULT_ENTITY_TYPES`'s own inline comment. This spec covered
  only the real remaining gaps, found by direct inspection rather than the bead's now-partly-stale
  framing: (1) `value_stream_stages` were never indexed at all — new `ENTITY_VALUE_STREAM_STAGE`
  constant + write hooks in `add_stage`/`update_stage`/`delete_stage`/`reorder_stages`; (2) a latent
  cascade-unindex bug — `delete_value_stream`'s own comment said "FK CASCADE handles stage
  deletion," true at the DB level but unable to invoke `unindex_entity()`, silently orphaning every
  deleted value stream's stages' index rows (fixed by reading stage ids before the cascading
  delete); (3) `business_domains`' indexed text omitted `org_unit` (only `name`+`scope_statement`)
  — added to both `create_domain`/`update_domain`; (4) `adp.search.backfill` covered only
  capabilities — new `reindex_all()` covers all 6 entity types (business/technical capabilities,
  applications, value streams, stages, domains) with a per-type count dict, `main()` updated to
  call it; (5) zero test coverage existed for ANY of this — new or the pre-existing 041 wiring —
  confirmed by grep across `tests/`. New `tests/unit/business/test_search_indexing.py` (11 tests,
  monkeypatched `index_entity`/`unindex_entity` recording stubs — `SearchIndex.upsert`'s
  Postgres-only `ON CONFLICT DO UPDATE` can't compile against SQLite, so this tier verifies store
  wiring only) and `tests/unit/search/test_backfill.py` (3 tests, a recording fake in place of
  `default_index()`); `tests/integration/test_search.py` extended with 3 Docker-gated tests
  (unavailable locally, same constraint every export/COMPLY-0x/928 suite this session has hit —
  written and will run in CI), including one exercising the real store-layer cascade fix end-to-end
  against a live Postgres container. 1721 backend tests (was 1707, +14), `ruff`/`mypy` clean.
  Verified live end-to-end against a real running backend and local Postgres (no migration needed —
  confirmed via `alembic current` unchanged at `039 (head)`): every quickstart.md scenario, incl.
  the cascade-unindex fix (indexed before delete → confirmed gone after cascading delete) and a
  live `python -m adp.search.backfill` run indexing 135 previously-partially-unindexed entities
  across all 6 types (22 stages, never indexed before this feature, now discoverable). **One real
  finding surfaced only through live verification, not caught by any test**: `hybrid_search`'s
  vector leg has no similarity threshold, so with very few rows of one `entity_type` in the index it
  can still surface a row for a completely unrelated query — a pre-existing property of the whole
  hybrid-search mechanism (shared by every entity type since phase 1), not a defect introduced by
  this feature; `quickstart.md`'s rename-verification scenario was corrected to check the returned
  hit's `text` field (the reliable signal) rather than assert zero hits for the old name. All
  synthetic test data (2 value streams, 3 stages, 1 domain) cleaned up and confirmed deleted
  afterward. See `specs/930-hybrid-search-phase/`.
  grouping dimension for Application Portfolio" — follow-on from ADP-8xo, deferred at that time
  because no such field existed on `Application` at all) — full `/speckit.specify` →
  `/speckit.plan` → `/speckit.tasks` → `/speckit.implement` cycle. Zero `AskUserQuestion` rounds
  were needed: every design decision (four-value set, nullable/no-default, dropdown UI shape,
  fixed bucket order, filter-parameter parity) directly mirrors `hosting_model`'s own
  already-shipped precedent (ADP-SPEC-038, migration 016) on the exact same `Application` entity,
  confirmed by direct read before writing spec.md rather than guessed. New
  `application_type: Literal["custom", "cots", "saas", "legacy"] | None` field added via migration
  `039` (nullable `TEXT` + `CHECK` constraint + filter index, mirroring migration 016's
  `hosting_model` shape line-for-line) — independent of `hosting_model` (build-vs-buy/vendor
  classification vs. deployment location; an app can be `custom` + `saas` simultaneously, spec.md
  Edge Cases). Backend: `adp.application.models`/`store`/`router` gain the field end-to-end
  (create/update/list-filter, mirroring `hosting_model`'s exact code shape at every layer);
  `adp.export.application_arch`'s existing `_serialize_application()` (ADP-SPEC-045) also gained
  the field, closing a gap that would otherwise have left file-based AI/tool consumers silently
  out of sync with the API the moment this feature shipped. Frontend: an "Application Type"
  dropdown in `ApplicationForm.tsx`, a conditional read line in `ApplicationDetail.tsx` (matching
  `pace_layer`'s own convention), and — the bead's actual deliverable — a sixth Group By/Then
  By/Filter by dimension on the Application Portfolio screen (`groupByApplicationType` in
  `groupApplications.ts`, fixed Custom→COTS→SaaS→Legacy bucket order, matching
  `groupByHostingModel`/`groupByPaceLayer`'s own fixed-enum convention rather than
  `groupByBusinessUnit`'s dynamic one); `ALL_FILTER_FIELDS`/`FILTER_FIELD_LABELS` inherited the new
  dimension automatically (both are defined as spreads of `ALL_DIMENSIONS`/`DIMENSION_LABELS`, so
  no separate edit was needed there). Deliberately out of scope, per the bead's own title and
  research.md D4: no change to the separate Insights `ApplicationsHeatMap.tsx` screen (an
  independently-defined `Dimension` type, confirmed by direct read) — matching how this session's
  two prior Portfolio-dimension features (ADP-6w4/ADP-9ye) were also scoped to the Portfolio screen
  only. 1707 backend tests (was 1693, +14: 8 unit model-validation, 6 contract create/update/
  filter/invalid-value — mirroring `hosting_model`'s own original test shapes exactly), 574
  frontend tests (was 570, +4 for `groupByApplicationType`), `ruff`/`mypy`/`tsc` all clean. One
  exhaustive-switch compile error was caught and fixed during the `tsc` pass, not by any test:
  `BucketCard.tsx`'s `detailFor()` switches exhaustively over `Dimension` and needed a new
  `"application_type"` case. Two frontend `Application` object-literal fixtures
  (`PortfolioPage.test.tsx`, `tests/component/application-registry.test.tsx`) needed the new
  required field added, also caught by `tsc`, not a test failure. Verified live end-to-end against
  a real running backend and local Postgres (migration applied directly, `alembic current`
  confirmed `039 (head)`): every quickstart.md scenario confirmed via direct API calls (create with
  a type, 422 on an invalid value, explicit-`null` clears via `PATCH` — corrected from an initially
  wrong `PUT` guess in the quickstart draft itself, filter query param), plus a live Playwright
  walkthrough of the Portfolio screen's Group By/Filter by dropdowns showing the real test
  application in its correct COTS bucket. Test application cleaned up afterward. See
  `specs/929-application-type-cots/`.
  JSON files", ADP-81p Option 1's third domain — following ADP-SPEC-044's Business Architecture
  export and ADP-SPEC-045's Application registry export) — full `/speckit.specify` →
  `/speckit.plan` → `/speckit.tasks` → `/speckit.implement` cycle. Unlike its two predecessors, this
  bead had not yet been spec'd at all; three real scope ambiguities were resolved via
  `AskUserQuestion` before writing spec.md, all to the recommended option: (1) an exported
  objective's `status` is the platform's own live `compute_status()`-derived value, not raw stored
  columns, matching what every existing API consumer already sees; (2) `capability_design_links`/
  `value_stream_design_links` (spec 034, deferred by both prior export increments) extend the
  already-shipped `adp.export.business_arch`'s own capability/value-stream files (a new
  `linked_designs` field) rather than living in the new `adp.export.strategy` module or a new file
  location, since a capability/value-stream is the entity that owns the link; (3) the three
  Strategy↔Compliance links added earlier this session (925/927: `objective_control_links`, five
  `initiative_control_*_mapping` tables, `theme_framework_links`) — which postdate the bead's
  original scope — are included in this export increment rather than deferred again. New
  `src/adp/export/strategy.py` exports `strategy/{themes,objectives,initiatives}/<id>.json`: a
  theme's `framework_ids`; an objective's full scalar fields, computed status/status_reason, every
  cross-domain link (capability/value-stream/design/application/control ids), its dependency graph
  (`depends_on_objective_ids`/`blocked_objective_ids`), its full progress history (not a summary),
  and — closing a traceability gap the epic itself called out — the reverse `initiative_ids`
  linking back to every initiative that references it; an initiative's own fields, `objective_ids`,
  and its live (never-cached) compliance-mapping status per linked control. All bulk-fetched via a
  small, fixed number of queries per reconciliation cycle (research.md Decision 4, inherited from
  ADP-SPEC-045's own no-N+1 principle) — **with one recorded, deliberate deviation**: reusing
  `adp.strategy.initiatives.list_initiatives()` as-is (which internally does its own 1+5-query
  N+1 dispatch across the five `control_*_mapping` tables) rather than re-deriving that same
  five-table `target_type` dispatch a second time inside the new export module — judged acceptable
  at this domain's scale and documented in research.md, an inline code comment, and tasks.md rather
  than silently patched over. Reuses `adp.export.common` verbatim (atomic writes, content-diff-aware
  writes so an unchanged entity never rewrites, orphan file cleanup, generic background-loop
  lifecycle) — zero new mechanism, zero new env var (still `ADP_BUSINESS_ARCH_EXPORT_ROOT`/
  `_INTERVAL_SECONDS`, now shared three ways). `src/adp/api/app.py` gained a third
  `start_strategy_export()`/`stop_strategy_export()` pair wired into `_lifespan` alongside the two
  existing export tasks. No new migration, no new table — a pure read projection over
  already-existing Strategy/Compliance schema. 1693 backend tests (was 1682, +11 unit: 6
  serialization, 5 reconciliation via a SQLite fixture; +3 integration, Docker-gated — same
  constraint every export/COMPLY-0x spec this session has hit, written and will run in CI), plus 2
  existing `test_business_arch_serialize.py` tests updated and 2 new ones added for the
  `linked_designs` extension. `ruff`/`mypy` both clean (a spurious multi-file mypy cascade was
  investigated and ruled out as a stale-cache/batch-composition artifact, not a real regression,
  by clearing `.mypy_cache` and confirming the canonical `mypy src/` check stayed clean throughout).
  Verified live end-to-end against a real running backend and local Postgres (env vars pointed at
  a scratch export root, 5-second interval): every quickstart.md scenario confirmed by direct API
  calls plus reading the actual exported JSON off disk — theme/objective/initiative export with
  every relationship populated, the dependency-graph and reverse-initiative-lookup fields, the
  `linked_designs` extension on a real capability, all synthetic test data (theme, 2 objectives,
  1 initiative, 1 capability) deleted afterward and confirmed gone (the linked Design itself,
  `DSN-201`, cannot be deleted via any API — an established, unrelated platform limitation, not a
  gap in this feature). Two real documentation bugs were found and fixed in quickstart.md's own
  draft curls during this live walkthrough — wrong guessed endpoint paths for creating an
  objective dependency (corrected to `POST .../objectives/{objective_id}/depends-on`) and for
  linking an initiative to an objective (corrected to path-param
  `POST .../initiatives/{initiative_id}/objectives/{objective_id}`, no body) — plus one missing
  required field (`level`) in the capability-creation curl for Scenario 5. See
  `specs/928-strategy-export/`.
  tracked as bead ADP-1ox since 925-strategy-compliance-linkage explicitly deferred it) — full
  `/speckit.specify` → `/speckit.plan` → `/speckit.tasks` → `/speckit.implement` cycle for a coarse,
  many-to-many tag between a `StrategicTheme` and a `RegulatoryFramework`, with no fields of its own
  beyond the two references and a timestamp — unlike the two sibling COMPLY-05 links (which carry or
  reference a `compliance_status`), this is a grouping tag, not an assessed relationship. One real
  scope question was put to the user directly during `/speckit.specify` rather than guessed: whether
  this pass ships UI surfacing or stays data-model-and-API-only — resolved to API-only, matching the
  precedent set by `926-framework-versioning-correction`; UI (a tag editor on the Theme screen, a
  reverse-lookup display on the Framework screen) is filed as a separate follow-on bead (`ADP-0md`,
  blocked on this spec). Every structural decision mirrors `925-strategy-compliance-linkage`'s own
  already-shipped precedent one level up rather than inventing a new one: the link lives in
  `adp.strategy` (the domain that already reaches into other domains via read-only mirror tables),
  with the reverse lookup on `adp.compliance.router` importing `adp.strategy.store` through the
  `_get_strategy_session()` dependency 925 already added — reused verbatim, zero new dependency code.
  `StrategicTheme` gains `framework_ids: list[str]`, mirroring `StrategicObjective.control_ids`
  exactly; the reverse lookup returns full `StrategicThemeListResponse` summaries, matching
  `list_objectives_for_control`'s own asymmetric shape (id-list forward, full-summary reverse).
  Duplicate-link (409) and not-found (404) handling reuse the existing `DuplicateLinkError`/
  `LinkNotFoundError` exceptions verbatim — no new exception type. Zero new `ActionType`, zero
  `PERMISSIONS_VERSION` bump, zero `enforcement.py` change — writes reuse the existing
  `("/api/v1/strategy/", WRITE_BUSINESS_ARCH)` prefix rule; the reverse-lookup route is ungated
  beyond general platform read access, matching `GET /controls/{id}/objectives`'s own precedent (a
  `RegulatoryFramework` carries no target-entity sensitivity of its own). One new migration (`037`,
  one table: `theme_framework_links`, composite PK, `ON DELETE CASCADE` on both legs). 22/22 tasks
  complete: migration (verified upgrade→downgrade→upgrade clean), `_row_to_theme` converted to async
  (three call sites updated: `list_themes`, `get_theme`, `create_theme`'s inline construction —
  `update_theme` needed no change, it already delegates to `get_theme`), 10 new unit tests
  (`tests/unit/strategy/test_theme_framework_links.py`), 12 new contract tests
  (`tests/contract/test_theme_framework_links_api.py`, full-stack httpx client against a real
  `create_app()` mirroring 925's own fixture precedent exactly), 3 new integration tests
  (`tests/integration/test_theme_framework_links_api.py`, testcontainers-gated — Docker unavailable
  in this environment, same constraint every COMPLY-0x spec on this branch has hit; written and will
  run in CI). 1682 backend tests total (1679 + the 3 pre-existing, unrelated LLM-stub-vs-real-key
  failures already present before this feature — confirmed environmental, not a regression, by the
  926/twl sessions' own prior investigation), `ruff`/`mypy` clean. Verified live end-to-end against a
  real local Postgres and running backend: every quickstart.md scenario (create, duplicate 409,
  missing-target 404 both directions, many-to-many tagging, empty reverse lookup, removal, repeat-
  delete 404, and — directly against real Postgres FK cascade behavior, not just the SQLite contract
  fixture — deleting a linked Theme and separately a linked Framework, confirming the link row is
  gone in both cases with the surviving side left untouched) all confirmed via direct API calls, with
  every test Theme/Framework/link created during verification cleaned up afterward (confirmed by a
  direct row-count check back to zero). See `specs/927-theme-framework-mapping/`.
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

This project is indexed by GitNexus as **ADP** (25325 symbols, 52271 relationships, 451 execution flows).

> Index stale? Run `node .gitnexus/run.cjs analyze --index-only` from the project root — it auto-selects an available runner. No `.gitnexus/run.cjs` yet? Bootstrap with `npx`, `bunx`, or `pnpm dlx` — e.g. `bunx gitnexus@latest analyze` (npm 11 npx crash; #1939).

## Always Do

- **MUST run impact before editing.** Use `impact({target: "symbolName", direction: "upstream"})` or `node .gitnexus/run.cjs impact "symbolName" --direction upstream --repo .`; report callers, processes, and risk. Never substitute grep for graph analysis.
- **MUST analyze graph changes before committing.** Use `detect_changes({scope: "all"})` (MCP) or `node .gitnexus/run.cjs detect-changes --scope all --repo .` (CLI fallback). `partial: true` or `truncated: true` is not a clean check — a zero means unseen, not unaffected; re-run it. For regression review: `detect_changes({scope: "compare", base_ref: "main"})` or `node .gitnexus/run.cjs detect-changes --scope compare --base-ref "main" --repo .`.
- MUST warn on HIGH/CRITICAL `risk` pre-edit; never use `riskSharedAxes` to waive a HIGH/CRITICAL `risk` warning. Compare File/symbol: MCP File omits axes; Graph-RAG expands File.
- **MUST treat `risk: UNKNOWN` as unresolved, not as low.** An empty caller set is not evidence the symbol is unused — it can also mean the callers are not resolvable by the index (plain-object property access, dynamic dispatch, cross-language calls). `impact` pairs `UNKNOWN` with a `riskNote` saying so. Confirm with a text search before treating the symbol as safe to change or delete; do not proceed on the strength of a zero.
- **MUST use `query({search_query: "concept"})` for concepts/flows, `context({name: "symbolName"})` for a named symbol, or `impact` for blast radius, on read-only callers, dependencies, imports, or execution flow.** Graph first; text search only for empty/`UNKNOWN`/literals.
- For security review, `explain({target: "fileOrSymbol"})` lists taint findings (source→sink flows; needs `analyze --pdg`).

## Never Do

- NEVER edit a function, class, or method before MCP/CLI impact analysis.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis, and never read `UNKNOWN` as an all-clear — it means the walk could not answer, which is the one verdict that requires confirming by other means.
- NEVER rename symbols with find-and-replace — use `rename` which understands the call graph.
- NEVER commit before MCP/CLI graph change analysis.

## Resources

| Resource | Use for |
| --- | --- |
| `gitnexus://repo/ADP/context` | Codebase overview, check index freshness |
| `gitnexus://repo/ADP/clusters` | All functional areas |
| `gitnexus://repo/ADP/processes` | All execution flows |
| `gitnexus://repo/ADP/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
| --- | --- |
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
