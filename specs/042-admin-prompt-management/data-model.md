# Data Model: Admin Screen for Managing AI Agent System Prompts

Source: spec.md Key Entities (Agent Prompt Registration, Prompt Change Record) + Clarifications (six agents, restore uses the edit confirmation gate) + research.md Decisions 1, 2, 4.

## 1. Enum additions (code, not a table)

### `PersonaRole.PLATFORM_ADMIN` (src/adp/authz/roles.py)

New value on the existing `PersonaRole` StrEnum, alongside `ENTERPRISE_ARCHITECT`, `SOLUTION_ARCHITECT`, `TECHNICAL_ARCHITECT`, `REVIEWER`.

### `ActionType.MANAGE_AGENT_PROMPTS` (src/adp/authz/roles.py)

New value on the existing `ActionType` StrEnum.

**Grant changes** (src/adp/authz/permissions.py, `PERMISSIONS_VERSION` 1.6.0 → 1.7.0):
- `PERMISSION_GRANTS[PersonaRole.ENTERPRISE_ARCHITECT]`: `frozenset(ActionType)` → `frozenset(ActionType) - {ActionType.MANAGE_AGENT_PROMPTS}`
- `PERMISSION_GRANTS[PersonaRole.PLATFORM_ADMIN]`: `frozenset(ActionType)` (everything Enterprise Architect has today, plus the new action, per research.md Decision 1 — least-surprise for existing `ADPAdministrator` members)
- `REQUIRES_CONFIRMATION`: add `ActionType.MANAGE_AGENT_PROMPTS`

**Group mapping change** (src/adp/auth/tokens.py `_GROUP_ROLE_PRIORITY`, and its web mirror `groupsToRole()` in `web/src/auth/AuthProvider.tsx`): `ADPAdministrator` group → `PersonaRole.PLATFORM_ADMIN` (was `ENTERPRISE_ARCHITECT`).

## 2. `agent_registrations` (static, code-defined — not a DB table)

Not persisted; this is the fixed set of six agents the admin screen enumerates, defined as a Python constant (list of dataclasses/dicts) in `adp.admin.prompt_registry` (relocated from the originally-planned `adp.agents.prompt_registry` during implementation — see research.md Decision 5's "Module location" note), since the set itself is a deploy-time decision (Assumptions: "new agents added as a small follow-up"), not admin-editable data.

| Agent ID | Display Name | Source module | Fallback constant |
|---|---|---|---|
| `chat_assistant` | Chat Assistant | `adp.chat.orchestrator` | `_SYSTEM_PROMPT` |
| `recommendation_generation` | Recommendation — Generation | `adp.recommendation.prompts` | `GENERATION_SYSTEM_PROMPT` |
| `recommendation_generation_no_kb` | Recommendation — Generation (no knowledge base) | `adp.recommendation.prompts` | `GENERATION_SYSTEM_PROMPT_NO_KB` |
| `recommendation_tradeoff` | Recommendation — Trade-off Analysis | `adp.recommendation.prompts` | `TRADEOFF_SYSTEM_PROMPT` |
| `intake_extraction` | Intake Extraction | `adp.llm.client` | `_EXTRACTION_SYSTEM_PROMPT` |
| `agent_review_business_capability` | Agent Review — Business Capability | `adp.business.agent_review` | `_load_system_prompt()` (file + `_FALLBACK_SYSTEM_PROMPT`) |

**Validation rule**: `agent_id` values are fixed string literals matching this table; any `agent_id` not in this set is rejected (404) by every endpoint in contracts/agent-prompts-api.md — this is what keeps FR-001/FR-009 access scoped to a known, bounded set rather than an arbitrary string.

## 3. Table: `agent_prompt_overrides`

One row per agent that currently has an active saved override. Absence of a row for an `agent_id` means "currently using the fallback/default" (FR-002).

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `agent_id` | `TEXT` | PK | One of the six literal values above |
| `prompt_text` | `TEXT` | `NOT NULL`, app-level check: non-empty/non-whitespace after `.strip()` (FR-004) | The currently active override text |
| `updated_by` | `TEXT` | `NOT NULL` | Actor identifier (subject/username from the auth token), same convention as existing audit actor fields |
| `updated_at` | `TIMESTAMPTZ` | `NOT NULL`, server default `now()` | Used for FR-012's optimistic-concurrency check |
| `version` | `INTEGER` | `NOT NULL`, default `1`, incremented on every write | Optimistic-lock token: the editor's PUT/POST includes the `version` it loaded; a mismatch means "changed since you loaded it" (FR-012) — surfaced as a 409, not silently overwritten |

**Lifecycle**: created on first confirmed edit for an `agent_id` (`version=1`); updated in place (not a new row) on every subsequent confirmed edit or restore, with `version` incremented — the row always represents "what's active right now," while every transition is separately recorded in `agent_prompt_history` below. Never deleted by this feature (a restore to the fallback is out of v1 scope per Assumptions — there is always at least one prior version to restore to once an override exists).

## 4. Table: `agent_prompt_history`

Append-only. One row per confirmed edit or confirmed restore (FR-006, FR-007, FR-008). Never updated or deleted (ART-IX).

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `BIGSERIAL` | PK | |
| `agent_id` | `TEXT` | `NOT NULL` | Not a DB-level FK to `agent_prompt_overrides.agent_id` — history must survive even if the override row's lifecycle model ever changes; validated at the app layer against the fixed agent-registration set instead |
| `actor` | `TEXT` | `NOT NULL` | Who made the change |
| `changed_at` | `TIMESTAMPTZ` | `NOT NULL`, server default `now()` | |
| `change_type` | `TEXT` | `NOT NULL`, app-level check `IN ('edit', 'restore')` | Distinguishes a manual edit from a restore-of-prior-version, both of which go through the identical confirmation gate (Clarification Session 2026-07-24) |
| `prior_text` | `TEXT` | `NOT NULL` (may be the fallback constant's text, for the very first override) | Full text before this change |
| `new_text` | `TEXT` | `NOT NULL` | Full text after this change |
| `confirmation_id` | `TEXT` | `NOT NULL` | The caller-supplied confirmation token that authorized this change (ART-VIII attributability) |

**Indexes**: B-tree on `(agent_id, changed_at DESC)` — the access pattern for FR-007 ("view the full change history for any agent") is always agent-scoped and newest-first.

**Invariant** (edge case in spec.md): the write to `agent_prompt_overrides` and the corresponding `INSERT` into `agent_prompt_history` MUST occur in the same DB transaction — a prompt change is never persisted without its history row, and vice versa.

## 5. Entity-to-API-model mapping (Pydantic v2, `extra="forbid"`)

| Spec entity | Field | API model field |
|---|---|---|
| Agent Prompt Registration | stable identifier | `AgentPromptView.agent_id` |
| Agent Prompt Registration | display name | `AgentPromptView.display_name` |
| Agent Prompt Registration | built-in fallback text | `AgentPromptView.fallback_text` |
| Agent Prompt Registration | currently active prompt text | `AgentPromptView.active_text` |
| Agent Prompt Registration | (derived) is override active | `AgentPromptView.is_override` (bool — drives FR-002's "reading from a stored file/default" indicator) |
| Prompt Change Record | which agent | `PromptHistoryEntry.agent_id` |
| Prompt Change Record | actor | `PromptHistoryEntry.actor` |
| Prompt Change Record | timestamp | `PromptHistoryEntry.changed_at` |
| Prompt Change Record | full prior text | `PromptHistoryEntry.prior_text` |
| Prompt Change Record | full new text | `PromptHistoryEntry.new_text` |
| Prompt Change Record | (new) change type | `PromptHistoryEntry.change_type` |

Full request/response contracts (including `confirmation_id` placement and the FR-012 `version` conflict shape) are in [contracts/agent-prompts-api.md](./contracts/agent-prompts-api.md).

## State transitions (per agent)

```text
[no override row]
     │  confirmed edit (change_type=edit)
     ▼
[override row, version=1] ──confirmed edit (version matches)──▶ [override row, version=2] ──...
     │                                                                │
     └────────────────── confirmed restore (change_type=restore) ─────┘
                          (restore also increments version; the *content*
                           written is copied from a chosen agent_prompt_history row,
                           but the transition mechanics are identical to an edit)
```

A version-mismatched edit/restore attempt (FR-012) is rejected with a 409 and does not transition any state — the admin must reload and retry.
