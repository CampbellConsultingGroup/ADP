# API Contract: Admin Agent Prompt Management (ADP-SPEC-042)

Router prefix: `/api/v1/admin/agent-prompts`

Auth: All endpoints require `AuthMiddleware` (standard ADP-SPEC-003 middleware) plus `ActionType.MANAGE_AGENT_PROMPTS` (only `PersonaRole.PLATFORM_ADMIN` holds this grant — FR-009). A caller without the permission gets **403** with no prompt content in the body (per Threat Model / User Story 1 Scenario 3 — denial must not leak content).

Confirmation: the confirm and restore endpoints additionally require `ActionType.MANAGE_AGENT_PROMPTS` to be present in `REQUIRES_CONFIRMATION`, enforced the same way as `POST /api/v1/recommendations/{id}/accept` and `POST /api/v1/business/capabilities/{id}/agent-review/{suggestion_id}/accept` (FR-010).

Logging: All mutations emit `logger.info()` with `actor`, `agent_id`, `change_type`, matching the existing mutation-logging convention (ART-VI / ART-IX).

---

## GET /api/v1/admin/agent-prompts

List all six agent prompt registrations with their current effective text (FR-001).

**Response 200** — `AgentPromptListResponse`

```json
{
  "items": [
    {
      "agent_id": "chat_assistant",
      "display_name": "Chat Assistant",
      "active_text": "You are ADP's chat assistant...",
      "is_override": false,
      "version": 0
    },
    {
      "agent_id": "recommendation_generation_no_kb",
      "display_name": "Recommendation — Generation (no knowledge base)",
      "active_text": "...(admin-edited text)...",
      "is_override": true,
      "version": 3
    }
  ]
}
```

`is_override: false` means `active_text` is the built-in fallback constant (FR-002); `version` is `0` in that case (no override row exists yet — see data-model.md §3). `is_override: true` means `active_text` came from `agent_prompt_overrides` and `version` is that row's optimistic-lock token, needed for the confirm request below (FR-012).

**Response 403** — caller lacks `MANAGE_AGENT_PROMPTS`; body contains no agent/prompt data.

---

## GET /api/v1/admin/agent-prompts/{agent_id}/history

Full change history for one agent, newest first (FR-007, User Story 3).

**Response 200** — `PromptHistoryResponse`

```json
{
  "items": [
    {
      "id": 42,
      "agent_id": "chat_assistant",
      "actor": "jdoe@example.com",
      "changed_at": "2026-07-25T14:03:00Z",
      "change_type": "edit",
      "prior_text": "...",
      "new_text": "..."
    }
  ]
}
```

**Response 404** — `agent_id` is not one of the six registered agents (data-model.md §2).
**Response 403** — caller lacks `MANAGE_AGENT_PROMPTS`.

---

## POST /api/v1/admin/agent-prompts/{agent_id}/confirm

Save a new prompt text for `agent_id` and make it active immediately (FR-003, FR-005, FR-010). This is the **only** write path for a manual edit — there is no separate unconfirmed "save draft" request; per research.md Decision 3, the single request either carries a valid `confirmation_id` and commits, or the client never sends it and nothing changes.

**Request** — `PromptEditRequest`

```json
{
  "new_text": "You are ADP's chat assistant, and you must...",
  "expected_version": 2,
  "confirmation_id": "CONFIRM-chat_assistant-2026-07-25T14:03:00Z"
}
```

- `new_text`: rejected if empty or whitespace-only after `.strip()` (FR-004) → **422**.
- `expected_version`: the `version` the editor loaded from `GET /agent-prompts` (`0` if editing a not-yet-overridden agent for the first time). If it no longer matches the current row's `version`, the request is rejected — see 409 below (FR-012).
- `confirmation_id`: required, non-empty (same `field_validator` shape as `SuggestionAcceptRequest`); constructed client-side as `` `CONFIRM-${agentId}-${ISOtimestamp}` `` by `PromptEditor.tsx`, mirroring `web/src/recommend/AcceptDialog.tsx`.

**Response 200** — `PromptChangeResult` (the new `AgentPromptListResponse` item for this agent, with its incremented `version`)

**Response 404** — `agent_id` not registered.
**Response 409** — `expected_version` does not match the current row's `version`: the underlying prompt changed since the editor loaded it (FR-012). Response body includes the current `active_text` and `version` so the client can re-diff rather than silently losing the other admin's change.
**Response 422** — empty/whitespace `new_text`, or missing/blank `confirmation_id`.
**Response 403** — caller lacks `MANAGE_AGENT_PROMPTS`.

**Side effect**: within one DB transaction — upserts `agent_prompt_overrides` (creating it at `version=1` if this is the agent's first-ever override, else updating in place and incrementing `version`) and inserts one `agent_prompt_history` row with `change_type="edit"`. Both writes succeed or fail together (edge case in spec.md).

---

## POST /api/v1/admin/agent-prompts/{agent_id}/restore/{history_id}

Restore a prior version from history as the new active prompt (FR-008). Uses the **identical confirmation gate** as the edit endpoint above (Clarification Session 2026-07-24) — restore is not a lower-friction path.

**Request** — `PromptRestoreRequest`

```json
{
  "expected_version": 3,
  "confirmation_id": "CONFIRM-chat_assistant-restore-42"
}
```

Same `expected_version`/`confirmation_id` semantics as the confirm endpoint. `history_id` identifies which `agent_prompt_history` row's `new_text` to restore (must belong to `agent_id`, else **404**).

**Response 200** — `PromptChangeResult` (same shape as confirm)

**Response 404** — `agent_id` not registered, or `history_id` does not exist / does not belong to `agent_id`.
**Response 409** — version conflict, same semantics as confirm (FR-012).
**Response 422** — missing/blank `confirmation_id`.
**Response 403** — caller lacks `MANAGE_AGENT_PROMPTS`.

**Side effect**: same transaction shape as confirm, but `new_text` is copied from the chosen history row's `new_text`, and the inserted `agent_prompt_history` row has `change_type="restore"` (its own `prior_text`/`new_text` still record the actual before/after of *this* transition, per FR-006 — restoring is itself a new, forward-recorded change, never a rewrite of the past).
