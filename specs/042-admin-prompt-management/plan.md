# Implementation Plan: Admin Screen for Managing AI Agent System Prompts

**Branch**: `042-admin-prompt-management` | **Date**: 2026-07-25 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/042-admin-prompt-management/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Give authorized administrators a single screen to view, edit, confirm, and revert the system prompts that drive ADP's six AI agent call sites (Chat Assistant, Recommendation generation, Recommendation generation no-KB fallback, Recommendation trade-off, Intake extraction, Agent Review) — without a code deploy. Technically: a new `PersonaRole.PLATFORM_ADMIN` + `ActionType.MANAGE_AGENT_PROMPTS` permission pair (closing the `ENTERPRISE_ARCHITECT` wildcard-grant gap so no architect role auto-inherits it), two new tables (`agent_prompt_overrides`, `agent_prompt_history`) that sit in front of the existing hardcoded prompt constants as an additive override layer, a shared `adp.admin.prompt_registry` lookup module each of the five non-Agent-Review call sites adopts, and a reused `confirmation_id` human-confirmation gate (per ART-VIII) that governs both edits and restores identically. A new admin-only page in `web/src/admin/` is gated on the new role at the route level.

## Technical Context

**Language/Version**: Python 3.12 (backend); TypeScript 5.x + React 18 (frontend)
**Primary Dependencies**: FastAPI ≥ 0.111, SQLAlchemy 2 async (Core), asyncpg, Alembic, Pydantic v2, python-jose (existing OIDC/JWT stack); React 18, TanStack Query v5, Vite 5 — all existing project dependencies; zero new packages required
**Storage**: PostgreSQL 16 — two new tables (`agent_prompt_overrides`, `agent_prompt_history`) via Alembic migration `023_agent_prompt_management.py`; existing hardcoded Python prompt constants remain as the untouched default/fallback layer
**Testing**: pytest (contract tests under `tests/contract/`, unit tests under `tests/unit/`, `tests/authz/test_enforcement.py` extended for the new permission), Vitest (`web/` unit/component tests) — matching existing project conventions; TDD per ART-IV (failing test before implementation)
**Target Platform**: Linux server (existing Azure Container Apps deployment — `adp-api` container app, no new infrastructure)
**Project Type**: Web application (existing FastAPI backend + React/Vite frontend, same repo layout as every prior ADP feature)
**Performance Goals**: SC-002 — a prompt edit takes effect for the next AI operation in under 2 minutes end-to-end (edit → confirm → next call uses new text); no new latency budget beyond one additional indexed point-lookup per AI call (negligible next to the existing DB round-trips those call sites already make for context/knowledge retrieval)
**Constraints**: FR-005 — a saved, confirmed change MUST take effect without a code deployment or process restart; per research.md Decision 5, no in-memory cache/TTL is introduced for v1 (avoids a staleness window, since one more point lookup is not a meaningful cost)
**Scale/Scope**: 6 agent prompt registrations in v1; a small, trusted administrator population (today's `ADPAdministrator` Keycloak group); `agent_prompt_history` grows by one row per edit/restore — expected low volume (tens to low hundreds of rows/year), no partitioning or archival needed

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Applies? | How this feature satisfies it |
|---|---|---|
| ART-I (SDD Mandatory) | Yes | spec.md → this plan → tasks.md (next command) → implementation, in order; PR will reference spec + task IDs (QG-01). |
| ART-II (Model is Source of Truth) | No | This feature does not touch `ArchitectureDescription`/`models.py`; it manages operational config (prompt text), not the canonical design model. |
| ART-III (Machine-Readable) | Yes | Prompt registrations and history are typed DB rows (Pydantic-validated at the API boundary), not opaque files — extends the one existing file-backed precedent (`agent_review`'s Markdown file) to a uniform, queryable store for all six agents. |
| ART-IV (TDD) | Yes | tasks.md will sequence a failing contract/unit test before each endpoint/service function, per project convention; `tests/authz/test_enforcement.py` gets new cases for `MANAGE_AGENT_PROMPTS`. |
| ART-V (Security by Design) | Yes | Threat model already in spec.md (assets, trust boundaries, 3 abuse cases, residual risk). New permission is least-privilege (distinct from architect roles, per Clarification Q1) rather than reusing an existing broad grant. |
| ART-VI (Observability) | Yes (light) | Standard structured logging on the new endpoints (correlation ID, actor, agent ID); this is a low-volume admin CRUD path, not an AI orchestration step, so no new span/token-usage telemetry is required (that already exists at the call sites that *consume* the prompt). |
| ART-VII (Grounded AI Only) | No | This feature edits prompt *text*; it does not generate or commit AI recommendations to the canonical model itself. |
| ART-VIII (Human-in-the-Loop for Consequence) | Yes | FR-010 (edit) and FR-008 (restore) both require the existing `confirmation_id` explicit-confirmation pattern (QG-14); an unconfirmed edit/restore never takes effect. |
| ART-IX (Provenance and Auditability) | Yes | `agent_prompt_history` is append-only, records actor/timestamp/before/after (FR-006), matching the audit-entry convention (QG-13). Edge case in spec.md requires the prompt write and its history row to succeed or fail together (single transaction). |
| ART-X (Deterministic Validation Gating) | No | No LLM-as-a-Judge verdict involved. |
| ART-XI (Traceability End to End) | No | No canonical-model element/requirement/recommendation/verdict thread involved. |
| ART-XII (Fixed Visual Language) | No | No diagram/C4 rendering involved. |
| ART-XIII (Typed Contracts Everywhere) | Yes | All new endpoints use Pydantic v2 request/response models with `extra="forbid"`, matching every other ADP router. |
| ART-XIV / ART-XV (Reproducible builds / Schema evolution) | Yes | New migration is additive (two new tables, no altered columns on existing tables) — backward-compatible, no data migration of existing rows needed. |
| ART-XVI (Documentation as Code) | Yes (SHOULD) | This plan + data-model.md + contracts/ are the documentation; no separate hand-written doc needed. |

**Flagged deliberate change requiring explicit sign-off (not a constitutional violation, but a policy change under this project's own convention)**: `PERMISSION_GRANTS[PersonaRole.ENTERPRISE_ARCHITECT]` currently is the wildcard `frozenset(ActionType)` — literally every action, present and future. Satisfying Clarification Q1 ("no architect role, including Enterprise Architect, gains admin-screen access solely by virtue of that role") requires narrowing this one grant to `frozenset(ActionType) - {ActionType.MANAGE_AGENT_PROMPTS}`. This is a one-line, deliberate weakening of an existing "all actions" invariant, called out here per this project's stated rule that "any change [to `PERMISSION_GRANTS`] requires a `PERMISSIONS_VERSION` bump and a spec update" (`1.6.0` → `1.7.0`). See Complexity Tracking below.

**Initial gate result**: PASS. No article is violated; the one flagged item is a documented, intentional policy change (not a workaround), tracked in Complexity Tracking per the project's existing convention rather than as a constitutional exception.

**Post-Phase-1 re-check**: PASS (unchanged) — data-model.md and contracts/ (below) implement exactly the additive, typed, append-only design described above; no new gate is implicated by the detailed design.

## Project Structure

### Documentation (this feature)

```text
specs/042-admin-prompt-management/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md         # Phase 1 output (/speckit.plan command)
├── quickstart.md         # Phase 1 output (/speckit.plan command)
├── contracts/            # Phase 1 output (/speckit.plan command)
│   └── agent-prompts-api.md
├── checklists/
│   └── requirements.md
└── tasks.md              # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/adp/
├── agents/
│   ├── __init__.py                    # existing (ART-VII toolkit: LLM stub, grounding validator — zero domain imports)
│   └── prompt_registry.py             # NEW: get_effective_prompt(agent_id) -> override row if present, else existing constant
├── admin/                             # NEW package
│   ├── __init__.py
│   ├── models.py                      # AgentPromptView, PromptEditRequest, PromptRestoreRequest, PromptHistoryEntry (Pydantic v2, extra="forbid")
│   └── service.py                     # list_agents(), get_history(agent_id), save_prompt(...), restore_prompt(...)
├── api/routers/
│   └── admin_prompts_router.py        # NEW: GET /api/v1/admin/agent-prompts, GET .../{agent_id}/history, POST .../{agent_id}/confirm, POST .../{agent_id}/restore/{history_id}
├── authz/
│   ├── roles.py                       # MODIFIED: + PersonaRole.PLATFORM_ADMIN, + ActionType.MANAGE_AGENT_PROMPTS
│   └── permissions.py                 # MODIFIED: PERMISSIONS_VERSION 1.6.0 -> 1.7.0; ENTERPRISE_ARCHITECT grant narrowed; PLATFORM_ADMIN grant added; MANAGE_AGENT_PROMPTS added to REQUIRES_CONFIRMATION
├── auth/
│   └── tokens.py                      # MODIFIED: _GROUP_ROLE_PRIORITY — ADPAdministrator -> PersonaRole.PLATFORM_ADMIN (was ENTERPRISE_ARCHITECT)
├── store/migrations/versions/
│   └── 023_agent_prompt_management.py # NEW: agent_prompt_overrides, agent_prompt_history tables (down_revision = "022")
├── chat/orchestrator.py               # MODIFIED: use prompt_registry instead of _SYSTEM_PROMPT constant directly
├── recommendation/prompts.py          # MODIFIED: 3 constants (GENERATION_SYSTEM_PROMPT, GENERATION_SYSTEM_PROMPT_NO_KB, TRADEOFF_SYSTEM_PROMPT) become fallbacks read via prompt_registry
├── llm/client.py                      # MODIFIED: _EXTRACTION_SYSTEM_PROMPT usages (lines ~391, ~439) routed via prompt_registry
└── business/agent_review.py           # MODIFIED: _load_system_prompt() generalized to call prompt_registry (keeps file-backed default as its fallback)

tests/
├── contract/
│   └── test_admin_prompts_contract.py # NEW: request/response shape + confirmation_id + permission-gate contract tests
├── unit/
│   └── agents/
│       └── test_prompt_registry.py    # NEW: override-present vs fallback, empty-prompt rejection, concurrent-edit conflict detection
├── authz/
│   ├── test_permissions.py            # MODIFIED: PLATFORM_ADMIN grant, ENTERPRISE_ARCHITECT no longer auto-grants MANAGE_AGENT_PROMPTS
│   └── test_enforcement.py            # MODIFIED: route-permission completeness gate covers new router
└── integration/
    └── test_admin_prompts_flow.py     # NEW: edit -> confirm -> next AI call uses new prompt; restore -> confirm -> history entry recorded

web/src/
├── admin/                             # NEW directory
│   ├── AdminPage.tsx                  # agent list, per-agent override/default indicator (FR-002)
│   ├── PromptEditor.tsx               # edit + confirm-dialog flow (mirrors web/src/recommend/AcceptDialog.tsx's confirmation_id pattern)
│   └── PromptHistory.tsx              # history list + restore-with-confirm
├── api/
│   └── adminPrompts.ts                # NEW: typed client for the 4 endpoints above
├── auth/AuthProvider.tsx              # MODIFIED: groupsToRole() maps ADPAdministrator -> "platform_admin"
└── ui/AppShell.tsx                    # MODIFIED: new nav section (below "Architecture"), gated on useAuth().user.role === "platform_admin"; new AppView = "admin"; TITLES entry
```

**Structure Decision**: Standard ADP web-application layout (existing `src/adp/` backend + `web/src/` frontend, per every prior feature 002–041). No new top-level project or repo is introduced. `prompt_registry.py` lives in the new `adp.admin` package (alongside `models.py`/`service.py`), **not** `adp.agents` — during implementation, `adp.agents`' own mechanically-enforced boundary test (`tests/unit/agents/test_toolkit_boundary.py`, ADP-SPEC-039: zero imports from any single domain module, so a second adapter can reuse that toolkit unmodified) correctly failed once `prompt_registry.py`'s deferred import of `adp.business.agent_review` was added under `src/adp/agents/`. `prompt_registry`'s entire purpose — knowing about every agent, including domain-specific ones — is the opposite of that toolkit's domain-agnostic contract, so it was relocated to `adp.admin` rather than weakening the boundary test. This corrects the original plan, which had not yet surfaced this conflict. The frontend mirrors the existing per-domain page convention (`web/src/business/`, `web/src/application/`) with a new `web/src/admin/` directory, per research.md Decision 6 — a distinct admin-only page rather than a tab folded into an existing page, since this surface is gated by a different permission than everything else in the app.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Narrowing `PERMISSION_GRANTS[PersonaRole.ENTERPRISE_ARCHITECT]` from the wildcard `frozenset(ActionType)` to an explicit exclusion set (`frozenset(ActionType) - {MANAGE_AGENT_PROMPTS}`) — a deliberate weakening of an existing "Enterprise Architects can do everything" invariant, requiring a `PERMISSIONS_VERSION` bump (1.6.0 → 1.7.0) | Clarification Q1 explicitly requires that no architect role — including Enterprise Architect — gains admin-screen access solely by virtue of that role. Because the existing grant is a live wildcard over the `ActionType` enum, simply adding a new `PersonaRole` for admins does not by itself prevent Enterprise Architects from also getting the new action automatically. | Leaving the wildcard grant untouched and adding `PLATFORM_ADMIN` alongside it was rejected: the new action would still auto-flow to every Enterprise Architect through the existing wildcard, directly violating the resolved clarification — this isn't a style choice, it's the only way to make Q1 actually true. |

