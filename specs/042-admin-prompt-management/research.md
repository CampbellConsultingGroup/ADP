# Research: Admin Screen for Managing AI Agent System Prompts

## Decision 1 — Permission model: a new `PLATFORM_ADMIN` role, not a bolt-on flag

**Decision**: Add `PersonaRole.PLATFORM_ADMIN` (new enum value) and `ActionType.MANAGE_AGENT_PROMPTS` (new enum value). Grant `MANAGE_AGENT_PROMPTS` to `PLATFORM_ADMIN` only. Remap the `ADPAdministrator` Keycloak group (currently falls through to `PersonaRole.ENTERPRISE_ARCHITECT` in `adp/auth/tokens.py`'s `_GROUP_ROLE_PRIORITY`, highest priority) to `PLATFORM_ADMIN` instead, and give `PLATFORM_ADMIN` a grant set covering all existing actions *plus* `MANAGE_AGENT_PROMPTS`, so an admin loses nothing they have today.

**Rationale — a real conflict this spec's clarification creates**: `src/adp/authz/permissions.py` currently grants `PersonaRole.ENTERPRISE_ARCHITECT: frozenset(ActionType)` — literally *every* action type, present and future, by construction. Any new `ActionType` added to the enum is automatically granted to Enterprise Architects with zero code change, because `frozenset(ActionType)` is evaluated at import time over the live enum. This directly contradicts the resolved Clarification Q1 ("no ordinary architect role — including Enterprise Architect — gains admin-screen access solely by virtue of that role"). Introducing a new `PersonaRole` distinct from `ENTERPRISE_ARCHITECT` does not, by itself, fix this — the new action still auto-flows to Enterprise Architects through the wildcard grant regardless of what other role also gets it.

**The concrete, minimal-diff fix**: change `PersonaRole.ENTERPRISE_ARCHITECT`'s grant from the wildcard `frozenset(ActionType)` to an explicit `frozenset(ActionType) - {ActionType.MANAGE_AGENT_PROMPTS}` (or an explicitly enumerated set, to be decided at implementation time — the `-` form is less error-prone since it doesn't require re-enumerating every existing action and automatically continues covering future non-admin actions the way the wildcard did). This is a deliberate, one-line weakening of an existing "all actions" invariant and MUST be called out explicitly in the PR (per this project's own convention: "Any change [to `PERMISSION_GRANTS`] requires a `PERMISSIONS_VERSION` bump and a spec update" — bump `1.6.0` → `1.7.0`).

**Alternatives considered**:
- *Reuse `MANAGE_CONFIG` (existing enterprise-architect-gated permission)* — rejected per Clarification Q1's explicit resolution; also does not solve the underlying wildcard-grant conflict (Enterprise Architects already have `MANAGE_CONFIG` via the wildcard too — reusing it would not actually restrict access to a distinct admin population at all).
- *Add a boolean `is_platform_admin` flag on the user model instead of a new role* — rejected: this project's authz model is uniformly role→action-grant based (`PersonaRole` + `ActionType` + `PERMISSION_GRANTS`); a parallel flag-based check would be a second, inconsistent authorization mechanism alongside the existing one, harder to reason about and audit.
- *Give `PLATFORM_ADMIN` only `MANAGE_AGENT_PROMPTS` and nothing else (a narrow, admin-only role with no architecture permissions)* — considered, but rejected for v1: `ADPAdministrator` group members today are, in practice, the same people as Enterprise Architects (the group was created as a superset/synonym), and stripping their existing capabilities the moment this feature ships would be a surprising regression unrelated to this feature's actual goal. `PLATFORM_ADMIN` = "everything Enterprise Architect has, plus prompt management" is the least-surprising shape; a more restrictive dedicated admin persona can be a later, separate change if ever needed.

## Decision 2 — Storage: a new DB-backed override table, not runtime git commits

**Decision**: Add a new table, `agent_prompt_overrides` (one row per agent per currently-active override; see data-model.md), plus an append-only `agent_prompt_history` table for every change (including restores). The *existing* hardcoded Python constants (`chat.orchestrator._SYSTEM_PROMPT`, `recommendation.prompts.{GENERATION_SYSTEM_PROMPT, GENERATION_SYSTEM_PROMPT_NO_KB, TRADEOFF_SYSTEM_PROMPT}`, `llm.client._EXTRACTION_SYSTEM_PROMPT`, and `business.agent_review`'s file+fallback) are left entirely untouched and become each agent's "default/fallback" (FR-002) — read only when no DB override row exists for that agent. This means the feature is purely additive: deleting all override rows returns the platform to exactly today's behavior.

**Rationale**: FR-006 (full before/after history), FR-007 (view history), FR-008 (attributed revert), and FR-012 (detect concurrent-edit conflicts) all need queryable, timestamped, attributable records — a relational table with the existing audit-entry conventions (`adp.audit.writer`, `AuditEntry`-style attribution) is the natural fit and is exactly how every other consequential mutation in this codebase is already recorded. Committing prompt text to git from a *running production container* was considered and rejected: it would require the deployed API container to hold git write credentials (directly contrary to this session's own hardening work minimizing what credentials live where — Key Vault-only secrets, no ambient git push access from the running app), and git commits are not natively queryable/joinable the way a DB table is for building the history UI (Story 3) or detecting concurrent edits (FR-012).

**Alternatives considered**:
- *Runtime git commits* (rejected — see above; also no natural place to enforce the FR-009 permission check or FR-012 optimistic-lock check without re-implementing them outside git anyway).
- *A single mutable `agent_prompt_overrides` row per agent with no separate history table, relying on the DB's own row-level audit/CDC* — rejected: this project doesn't have row-level CDC infrastructure, and re-adding it just for this feature is disproportionate; a small, explicit history table matches the existing `audit_entries` pattern already in the schema and is trivial to query.

## Decision 3 — Confirmation mechanism: reuse the existing `confirmation_id` pattern verbatim

**Decision**: The prompt-change-confirm endpoint takes a Pydantic request body with a required, non-empty `confirmation_id: str` field (same `field_validator` shape as `SuggestionAcceptRequest` in `adp/business/models.py` and `AcceptOptionRequest` in `adp/recommendation`), and `ActionType.MANAGE_AGENT_PROMPTS` is added to the existing `REQUIRES_CONFIRMATION` frozenset in `adp/authz/permissions.py`. Per Clarification Session 2026-07-24 (restore requires the same confirmation gate as edit), restore is not a separate, lower-friction code path: `POST .../restore/{history_id}` takes the identical `confirmation_id`-bearing request shape as the edit-confirm endpoint, so there is exactly one enforcement point (one `REQUIRES_CONFIRMATION` check, one `field_validator`) for "change the active prompt," regardless of whether the new text comes from the editor or from history.

**Rationale**: this is a verbatim, already-proven pattern in this exact codebase (export, recommendation accept, agent-review suggestion accept all use it identically) — Article VIII requires "explicit, attributable human confirmation," and this project's established mechanism for that is a non-empty caller-supplied `confirmation_id` validated server-side, paired with a client-side UI step (a confirm dialog) that constructs it (e.g. `` `CONFIRM-${agentId}-${changeAttemptId}` ``) — not a heavier two-phase "draft then separately publish" state machine. Reusing it exactly avoids inventing a second confirmation mechanism.

**Alternatives considered**:
- *A two-step draft/publish workflow (save as draft, then a separate "Publish" action on a stored draft)* — rejected: heavier than every other consequential action in this codebase, and the spec's User Story 2 Scenario 3 ("an administrator edits a prompt but does not complete the confirmation step... the prior prompt remains active and unchanged") is fully satisfied by the existing single-request-with-confirmation_id pattern (if the request never fires, or fires without a valid confirmation_id, nothing is written) — a persisted draft state isn't needed to satisfy that scenario.

## Decision 4 — Agent registration set for v1

**Decision**: six registrations, matching the originating bead's literal enumeration plus Agent Review:

| Agent ID | Source module | Existing constant/pattern |
|---|---|---|
| `chat_assistant` | `adp.chat.orchestrator` | `_SYSTEM_PROMPT` |
| `recommendation_generation` | `adp.recommendation.prompts` | `GENERATION_SYSTEM_PROMPT` |
| `recommendation_generation_no_kb` | `adp.recommendation.prompts` | `GENERATION_SYSTEM_PROMPT_NO_KB` |
| `recommendation_tradeoff` | `adp.recommendation.prompts` | `TRADEOFF_SYSTEM_PROMPT` |
| `intake_extraction` | `adp.llm.client` | `_EXTRACTION_SYSTEM_PROMPT` |
| `agent_review_business_capability` | `adp.business.agent_review` | `_load_system_prompt()` / `docs/system_prompt_sr_bus_arch.md` + `_FALLBACK_SYSTEM_PROMPT` |

**Rationale**: the bead's own text enumerates all three `recommendation.prompts` constants by name, not a summarized "one recommendation prompt" — treating `GENERATION_SYSTEM_PROMPT_NO_KB` as a distinct registration (rather than silently coupling it to `GENERATION_SYSTEM_PROMPT`) is more correct, since it's used on a different code path (no-knowledge-base fallback) and an admin tuning the main generation prompt should not be surprised that it silently changed the no-KB variant too, or vice versa.

**Alternatives considered**: collapsing the two `GENERATION_SYSTEM_PROMPT*` constants into one editable slot — rejected as described above (different code path, different behavior; conflating them removes an admin's ability to tune them independently, which is exactly the kind of gap the feature exists to close).

## Decision 5 — "Take effect without a redeploy" mechanism

**Decision**: a small shared helper in a new module `adp.admin.prompt_registry` (generalizing `agent_review._load_system_prompt`'s shape) that each of the five other call sites invokes to get the *effective* prompt for their agent ID: query `agent_prompt_overrides` for an active row; if present, return it; else return the module's own existing constant/loader. No in-process cache with a TTL is introduced for v1 — every AI operation already does at least one DB round-trip elsewhere in its flow (e.g. loading capability/design/portfolio context), so one more indexed point lookup by primary key is not a meaningful new cost, and it trivially satisfies "next AI operation uses the new prompt" (Story 2, Scenario 4) with no staleness window to reason about at all — simpler than introducing and then having to justify a cache TTL.

**Alternatives considered**: an in-memory cache (mirroring the existing 5-minute JWKS cache) — rejected for v1 as unnecessary complexity; revisit only if the point-lookup is ever shown to matter for latency in practice.

**Module location, corrected during implementation**: originally planned as `adp.agents.prompt_registry` (this decision's module was placed under the ADP-SPEC-039 toolkit package by association, since it generalizes that package's `agent_review._load_system_prompt`). Implementation surfaced a real conflict: `adp.agents` has a mechanically-enforced test (`tests/unit/agents/test_toolkit_boundary.py`) asserting zero imports from any single domain module, so a second future adapter can reuse the toolkit unmodified (ADP-SPEC-039 FR-005/SC-005). `prompt_registry` necessarily imports `adp.business.agent_review` (and `adp.chat`, `adp.recommendation`, `adp.llm`) as fallback providers — the opposite of that contract. Moved to `adp.admin.prompt_registry` instead of weakening the boundary test.

## Decision 6 — Web UI shape

**Decision**: a new `AppView = "admin"`, a new top-level nav section (below "Architecture") rendered only when `useAuth()`'s `user.role === "platform_admin"`, and a new `web/src/admin/` directory (`AdminPage.tsx`, `PromptEditor.tsx`, `PromptHistory.tsx`) mirroring the existing per-domain page structure (`web/src/business/`, `web/src/application/`) rather than being folded into an existing page (unlike the LLM-model-selector, which is a tab inside Intake — this feature is explicitly a *distinct, admin-only* surface per FR-001/FR-009, so it should not share a page with non-admin-facing settings).

**Rationale**: matches every other domain's existing page-per-area convention in `web/src/`; keeps the admin-only gate at the page/route level (simplest to reason about and test) rather than needing a second, tab-level permission check inside a shared page.

## Decision 7 — Migration numbering

**Decision**: next Alembic migration is `023_agent_prompt_management.py` (`down_revision = "022"`), adding both new tables in one migration (they are introduced and used together; no reason to split).
