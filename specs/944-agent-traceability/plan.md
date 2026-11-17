# Implementation Plan: Agent Traceability

**Branch**: `944-agent-traceability` | **Date**: 2026-11-16 | **Spec**: [spec.md](spec.md)
**Input**: `/specs/944-agent-traceability/spec.md` (bead ADP-12x, Agentic P3). `/speckit-clarify` 2026-11-16 confirmed three points: the L3 rule, the FR-013 risk rule, and that agent and solution compliance stay separate.

## Summary

Three additions to the 933 agent registry, all in existing packages:

1. **Automates links** from an agent to business L3 capabilities, value stream stages and value chain activities. They are three tables owned by `adp.agentic`, validated through narrow mirrors, with reverse-lookup routes on the agentic router.
2. **Agent as the sixth compliance mapping target** in `adp.compliance`. It follows the COMPLY-02 shape and feeds the derived status, roll-ups and summary. Initiative linkage stays at five types.
3. **The agentic risk band.** A pure function in `adp.agentic.risk` gives an agent's band, embedded in every `Agent` read. A solution's band is the highest among its non-retired agents, added to the solution-agents read. Tools are listed as "not yet considered" until P2.

UI:
- an Automates section, compliance status and a risk band on Agent detail;
- a Risk column in the agent list;
- the solution band, plus each agent's band and compliance status, on the Agents tab;
- "Automated by agents" on capability L3 rows and value stream stages;
- Agent as a target in the control mapping editor.

Also: export, seed and migration `052`. No new permission.

## Technical Context

**Language/Version**: Python 3.12 (3.11+) and TypeScript 5.x + React 18 (existing).
**Primary Dependencies**: FastAPI, SQLAlchemy 2 async Core, Alembic, Pydantic v2, TanStack Query v5. **Zero new packages.**
**Storage**: PostgreSQL 16. Migration `052` (`down_revision="051"`) adds four tables: three link tables and `control_agent_mapping`. It alters nothing.
**Testing** (test-first):
- pure risk tests: the full band matrix, factors, missing classification, solution max, retired exclusion, "No agents";
- SQLite store tests: links, the L3 rule, duplicates, 404s, deletes, ordering and paths; agent mappings, status, roll-ups including agents, and the control list including agents;
- contract tests: reviewer 403, the 404/409/422 bodies, the shapes of `agentic_risk` and `solution_risk`, and the reverse lookups;
- a guard that no risk or band column is stored;
- a guard that initiative dispatch has no AGENT entry;
- export test;
- Docker-gated `test_migration_052.py`;
- vitest: Automates editor, risk display, Agents tab, CapabilityNode expander, mapping editor agent target.

Run `ruff check src/ tests/` before pushing.

**Performance Goals**:
- the risk band costs no query: it is computed from the row already read;
- the Agents tab makes one extra request (bulk statuses);
- the agent export makes two to three bulk queries per cycle.

**Constraints**:
- risk and agent compliance status are never stored (SC-006);
- existing response fields are unchanged, with additions only;
- the solution's own compliance status is untouched (FR-009a);
- `adp.agentic` still imports no other domain package.

**Scale/Scope**:
- backend:
  - agentic store +~200 lines, `risk.py` ~90, models +~70, router +~150;
  - compliance store +~80, router +~70;
  - export +~50, seed +~60;
- frontend:
  - `api/agentic.ts` +hooks, `api/business.ts` +value chain hooks, `api/compliance.ts` +agent;
  - new `AgentAutomates.tsx`, `AgentCompliance.tsx`, `agenticRisk.tsx` (band chip and factors);
  - edits to AgentDetail, AgentsPage, SolutionAgentsPanel, CapabilityNode, ValueStreamDetail, ControlMappingsEditor, InitiativeControlMappingEditor and App.tsx;
- about 70 backend and 25 frontend tests.

## Constitution Check

| Gate | Status | Notes |
|---|---|---|
| ART-I / QG-01 | ✔ | spec.md, bead ADP-12x, clarify session 2026-11-16 |
| ART-II | ✔ | Links and mappings are stored once. The band and the agent compliance status are derived on read (guard tests) |
| ART-IV | ✔ | Pure risk tests first, then store, contract and component tests |
| ART-V | ✔ | `WRITE_APPLICATION` (the agentic prefix rule) and `WRITE_COMPLIANCE`. No sensitive data, so no new read gate |
| ART-IX | ✔ | Create and delete log lines with the actor. Mapping upserts reuse the compliance log lines |
| ART-XIII | ✔ | `Literal` bands and factor codes, the `MappingTargetType` enum, `extra="forbid"` bodies, the CHECK on status |
| ART-XV | ✔ | Reversible `052`, additive only, with a Docker-gated test |

No violations. Post-design re-check: unchanged.

## Project Structure

```text
specs/944-agent-traceability/  spec.md plan.md research.md data-model.md quickstart.md contracts/rest-api.md checklists/ tasks.md

src/adp/store/migrations/versions/052_agent_traceability.py          NEW
src/adp/agentic/store.py            3 link tables + 5 narrow mirrors; link CRUD; reverse lookups; delete_agent clears links
src/adp/agentic/risk.py             NEW pure agent_risk / solution_risk
src/adp/agentic/models.py           AgenticRisk, SolutionAgenticRisk, Automates*, AgentSummary, link bodies; Agent.agentic_risk
src/adp/agentic/router.py           automates routes; reverse lookups; log lines
src/adp/compliance/models.py        MappingTargetType.AGENT; AgentComplianceMappings/Statuses
src/adp/compliance/store.py         control_agent_mapping + agents mirror; upsert/list/delete; status dispatch; roll-up rows
src/adp/compliance/router.py        PUT/DELETE agent mapping; GET /agents/{id}/mappings; GET /agents/statuses
src/adp/export/agentic.py           automates + compliance_mappings
scripts/seed_retail.py              phase D extension; WIPE_TABLES

tests/unit/agentic/test_agentic_risk.py               NEW (pure)
tests/unit/agentic/test_agent_automates_store.py      NEW (SQLite)
tests/unit/agentic/test_agentic_risk_not_stored.py    NEW (guard)
tests/unit/compliance/test_agent_mappings.py          NEW (SQLite)
tests/unit/strategy/...                               AGENT absent from initiative dispatch
tests/contract/test_agent_traceability_api.py         NEW
tests/unit/export/test_agentic_export*.py             extended
tests/integration/test_migration_052.py               NEW (Docker-gated)

web/src/api/agentic.ts                     types (AgenticRisk, AgentAutomates, AgentSummary) + hooks
web/src/api/business.ts                    useValueChains, useValueChain
web/src/api/compliance.ts                  "agent" target; useAgentComplianceMappings, useAgentComplianceStatuses
web/src/agentic/agenticRisk.tsx            NEW RiskBadge + factor list
web/src/agentic/AgentAutomates.tsx (+test) NEW
web/src/agentic/AgentCompliance.tsx (+test) NEW
web/src/agentic/AgentDetail.tsx / AgentsPage.tsx / SolutionAgentsPanel.tsx (+tests)
web/src/business/CapabilityNode.tsx / ValueStreamDetail.tsx (+tests)  automated-by lists
web/src/compliance/ControlMappingsEditor.tsx (+test)  agent target via agent picker; no LinkedInitiatives on agent rows
web/src/strategy/InitiativeControlMappingEditor.tsx   exclude agent
web/src/App.tsx                             pendingAgentId navigation
```

**Structure Decision**: extend `adp.agentic` and `adp.compliance` in place (research R1–R5). Reverse lookups go on the agentic router, and the agent compliance read goes on the compliance router. This keeps both packages free of cross-domain imports.

## Delivery order (for /speckit.tasks)

1. Migration 052 and its Docker test; the metadata tables and mirrors.
2. The pure risk module, test-first, then the not-stored guard. Embed `agentic_risk` and `solution_risk` in the reads.
3. Automates store, test-first on SQLite, then the router, contract tests and log lines.
4. Compliance agent target, test-first: the store, status dispatch, roll-ups and routes; the initiative guard.
5. Export and seed.
6. Frontend: types and hooks → `agenticRisk.tsx` → AgentAutomates → AgentCompliance → AgentDetail, AgentsPage and SolutionAgentsPanel → CapabilityNode and ValueStreamDetail → mapping editors → App navigation.
7. Gates (`ruff check src/ tests/`, mypy, tsc, vitest), a live quickstart with Playwright, CLAUDE.md by hand, GitNexus.

## Complexity Tracking

| Deviation | Why | Simpler alternative rejected |
|---|---|---|
| Reverse lookups for capabilities, stages and activities are served by the agentic router, not the target's router | Keeps `adp.business` free of an `adp.agentic` import (R2) | Business-router routes: cross-package coupling, in a file already past the size threshold |
| The agent compliance read is on the compliance router, not the agentic router | `adp.agentic` imports no other domain package (R5) | Embedding the status in `Agent`: needs a compliance import |
| FKs exist only in the migration | Cross-metadata FKs would force every agentic/compliance fixture to create the business/agentic tables (the 940 precedent) | Metadata FKs: break many existing fixtures |
