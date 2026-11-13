# Implementation Plan: Agent Registry Core (Agentic Solutions P1)

**Branch**: `933-agent-registry` | **Date**: 2026-11-13 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/933-agent-registry/spec.md` (bead ADP-hii; planning doc `docs/agentic-solutions-plan.md`)

## Summary

This feature adds a registry of AI agents and links them, many-to-many, to applications of a new application type, "agentic".
- **Backend**: a new sibling package `adp.agentic` with two tables (`agents`, `solution_agents`) added by migration 043. The same migration widens the application-type CHECK.
- **Membership rules**: an agent can be added only to agentic applications. An agentic application cannot be reclassified while it has agents.
- **Cost estimates**: shown only to users with application-cost read permission, and settable only with cost-write permission.
- **Platform integration**: agents are added to search, the periodic export and the demo seed (ADP itself as an agentic solution).
- **Frontend**: a top-level Agents screen (list, filters, detail, form) and an Agents tab on agentic applications.

Every structural choice mirrors an already-shipped precedent; see [research.md](research.md) D1–D11.

## Technical Context

**Language/Version**: Python 3.12 (backend); TypeScript 5.x + React 18 (frontend). Both are existing stacks.
**Primary Dependencies**: FastAPI ≥ 0.111, SQLAlchemy 2 async (Core), asyncpg, Alembic, Pydantic v2; React 18, TanStack Query v5. All are existing, with **zero new packages**.
**Storage**: PostgreSQL 16. Migration `043` (`down_revision="042"`) adds two new tables and re-creates one CHECK constraint on `applications`.
**Testing**:
- pytest: unit tests (models, store, against a SQLite fixture), contract tests (full `create_app()` through httpx), authz tests, and a Docker-gated migration integration test.
- Vitest: component and unit tests.
**Target Platform**: Linux server + browser (the existing ADP deployment).
**Project Type**: web service + SPA (existing `src/adp` + `web/`).
**Performance Goals**:
- Agents list < 1 s for ≤ 1,000 agents. `solution_count` is computed with one grouped query, with no N+1.
- Agent detail uses one join for solutions.
**Constraints**:
- `adp.agentic` imports no other domain package; it uses mirror tables (D2).
- No new ActionType.
- Cost-field gating is enforced at the router, never only in the UI.
**Scale/Scope**: tens to low thousands of agents per estate. 10 new routes, 1 changed route, about 6 new frontend components.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Gate | Status | Notes |
|---|---|---|
| QG-01 Spec-driven (ART-I) | ✅ | spec.md, with clarifications resolved; bead ADP-hii |
| QG-02/18 Schema drift / reproducible (ART-II/XIV) | ✅ | `adp.models` is untouched, so `adp-generate --check` is unaffected (D11) |
| QG-03 Versioned schemas (ART-XV) | ✅ | One additive migration with a reversible downgrade (agentic rows are nulled on downgrade) |
| QG-04 Tests ≥ 85% coverage (ART-IV) | ✅ planned | Tests are written first for each user story |
| QG-05 Contract tests | ✅ planned | Every route in contracts/agentic-api.md has a contract test |
| QG-06/07/08 SAST / deps / secrets (ART-V) | ✅ | No new dependency; `a2a_card_url` is http(s)-only on both ends |
| QG-09 Permission-gated mutations | ✅ | Prefix rule `/api/v1/agentic/` → `WRITE_APPLICATION`, plus inline cost gates; the authz completeness test is extended |
| QG-10 Structured logs (ART-VI) | ✅ | `agentic.*` log lines with actor on every mutation |
| QG-11/12/15 AI spans / grounding / gating | N/A | No AI invoked |
| QG-13 Audit (ART-IX) | ✅ with precedent | Actor-attributed structured logs, the same as application, business, compliance and strategy; `audit_entries` is design-coupled (D6) |
| QG-14 Human confirmation | N/A | No consequential AI action. Deleting an agent uses the UI's existing confirm-dialog pattern, with the solution count disclosed |
| QG-16 Referential integrity (ART-XI) | ✅ | FK CASCADE in the migration, plus explicit deletes for SQLite parity; no orphan memberships |
| QG-17 Theme | N/A | |

No violations, so the Complexity Tracking section is empty.

**Post-design re-check (after Phase 1)**: unchanged. The design adds no gate exposure beyond the table above.

## Project Structure

### Documentation (this feature)

```text
specs/933-agent-registry/
├── spec.md
├── plan.md              # this file
├── research.md          # D1–D11
├── data-model.md
├── quickstart.md
├── contracts/agentic-api.md
├── checklists/requirements.md
└── tasks.md             # /speckit.tasks
```

### Source Code (repository root)

```text
src/adp/
├── agentic/                         # NEW package (adp.agents is taken)
│   ├── __init__.py
│   ├── models.py                    # Agent*, SolutionAgent*, Literals, domain errors, URL validator
│   ├── store.py                     # _metadata, agents, solution_agents, applications mirror; CRUD + membership + search hooks
│   └── router.py                    # /api/v1/agentic; inline READ/WRITE_APPLICATION_COST checks
├── application/
│   ├── models.py                    # ApplicationType += "agentic"; AgenticSolutionHasAgentsError
│   ├── store.py                     # solution_agents mirror; reclassify guard; explicit membership delete on app delete
│   └── router.py                    # map AgenticSolutionHasAgentsError → 409
├── authz/enforcement.py             # prefix rule /api/v1/agentic/ → WRITE_APPLICATION
├── search/{index.py,__init__.py,backfill.py}   # ENTITY_AGENT + backfill loop
├── export/agentic.py                # NEW: agentic/agents/<id>.json
├── api/app.py                       # include router; start/stop agentic export
└── store/migrations/versions/043_agent_registry.py   # NEW
scripts/seed_retail.py               # WIPE_TABLES + ADP agentic solution + 5 agents

tests/
├── unit/agentic/test_models.py, test_store.py
├── unit/application/test_agentic_reclassify_guard.py
├── unit/search/test_backfill.py (extended), unit/export/test_agentic_export.py
├── contract/test_agentic_api.py
├── authz/test_enforcement.py (extended)
└── integration/test_migration_043.py   # Docker-gated, runs in CI

web/src/
├── api/agentic.ts                   # NEW hooks: useAgents, useAgent, useCreateAgent, useUpdateAgent, useDeleteAgent, useSolutionAgents, add/update/reorder/remove
├── api/application.ts               # ApplicationType += "agentic"
├── agentic/                         # NEW
│   ├── AgentsPage.tsx               # list + filters (autonomy, min autonomy, provider, owner, lifecycle)
│   ├── AgentForm.tsx                # create/edit; autonomy scale with names + meanings (FR-005)
│   ├── AgentDetail.tsx              # attributes + solutions list; delete w/ solution-count disclosure
│   ├── SolutionAgentsPanel.tsx      # Agents tab on agentic application: add/role/reorder/remove
│   └── autonomy.ts                  # scale labels/meanings constant
├── ui/url.ts                        # NEW shared isHttpUrl (extracted from compliance/FrameworkDetail.tsx)
├── application/{ApplicationForm,ApplicationDetail}.tsx   # "agentic" option/label; Agents tab when agentic
├── portfolio/groupApplications.ts   # Agentic bucket (last)
├── shell/index.ts, ui/AppShell.tsx, App.tsx              # "Agents" nav view
└── tests alongside (*.test.tsx)
```

**Structure Decision**: the existing single backend package tree (`src/adp`) plus the `web/` SPA, with the new domain as the sibling package `adp.agentic`, following the `adp.compliance` precedent (D1).

## Phasing (for /speckit.tasks)

1. **Foundation**: migration 043, `ApplicationType` widening (backend and the four frontend lists), the `adp.agentic` skeleton, the authz prefix rule, and router registration.
2. **US1 (P1)**: agent CRUD, membership (add, role, reorder, remove), the reclassify guard, cost gating, `AgentForm`, `SolutionAgentsPanel`, and the Agents tab.
3. **US2 (P2)**: list filters plus `solution_count`, `AgentDetail` with its solutions, the Agents nav view, and the "unassigned" indicator.
4. **US3 (P3)**: search hooks plus backfill, the export module plus lifespan wiring.
5. **Polish**: seed (FR-017), quickstart walkthrough, CLAUDE.md "Recent Changes" entry, and the full quality gates (pytest, ruff, mypy, vitest, tsc, `adp-generate --check`).

## Complexity Tracking

None.
