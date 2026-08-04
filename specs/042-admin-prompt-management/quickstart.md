# Quickstart: Admin Screen for Managing AI Agent System Prompts (ADP-SPEC-042)

Assumes API at `http://localhost:8001` with a `PLATFORM_ADMIN`-role token (or `ADP_AUTH_ENABLED=false` for local no-auth testing — the permission gate is still exercised in Scenario 6 below with a non-admin token).

## Scenario 1: List all six agents, none overridden yet

```bash
curl -s http://localhost:8001/api/v1/admin/agent-prompts | python3 -m json.tool
# Expect: 6 items (chat_assistant, recommendation_generation, recommendation_generation_no_kb,
#   recommendation_tradeoff, intake_extraction, agent_review_business_capability),
#   each with is_override: false and version: 0
```

## Scenario 2: Edit rejected without confirmation_id

```bash
curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:8001/api/v1/admin/agent-prompts/chat_assistant/confirm \
  -H "Content-Type: application/json" \
  -d '{"new_text": "You are a helpful assistant.", "expected_version": 0}'
# Expect: 422 (missing confirmation_id)
```

## Scenario 3: Confirmed edit takes effect (FR-003, FR-005, FR-010, User Story 2 Scenario 1-2)

```bash
curl -s -X POST http://localhost:8001/api/v1/admin/agent-prompts/chat_assistant/confirm \
  -H "Content-Type: application/json" \
  -d '{
    "new_text": "You are ADP'"'"'s chat assistant. Always cite grounding sources.",
    "expected_version": 0,
    "confirmation_id": "CONFIRM-chat_assistant-2026-07-25T14:00:00Z"
  }' | python3 -m json.tool
# Expect: 200, is_override: true, version: 1

curl -s http://localhost:8001/api/v1/admin/agent-prompts | python3 -c \
  "import sys,json; items=json.load(sys.stdin)['items']; a=[i for i in items if i['agent_id']=='chat_assistant'][0]; print(a['active_text'])"
# Expect: the new text — confirms the effective-prompt lookup (adp.admin.prompt_registry)
# reads the override, not the hardcoded fallback constant, with no restart (FR-005)
```

## Scenario 4: Reject empty prompt (FR-004, User Story 2 Scenario 5)

```bash
curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:8001/api/v1/admin/agent-prompts/chat_assistant/confirm \
  -H "Content-Type: application/json" \
  -d '{"new_text": "   ", "expected_version": 1, "confirmation_id": "CONFIRM-chat_assistant-empty"}'
# Expect: 422
```

## Scenario 5: Concurrent-edit conflict surfaced, not silently overwritten (FR-012, User Story 2 Scenario 6)

```bash
# Admin A loaded version 1. Meanwhile admin B already saved version 2 (simulate):
curl -s -X POST http://localhost:8001/api/v1/admin/agent-prompts/chat_assistant/confirm \
  -H "Content-Type: application/json" \
  -d '{"new_text": "Admin B'"'"'s edit.", "expected_version": 1, "confirmation_id": "CONFIRM-chat_assistant-B"}' > /dev/null

# Admin A now tries to save against their stale expected_version=1:
curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:8001/api/v1/admin/agent-prompts/chat_assistant/confirm \
  -H "Content-Type: application/json" \
  -d '{"new_text": "Admin A'"'"'s edit.", "expected_version": 1, "confirmation_id": "CONFIRM-chat_assistant-A"}'
# Expect: 409 — admin A's edit is rejected with the current text/version, not silently discarded or blindly overwritten
```

## Scenario 6: Non-admin denied, no content leaked (FR-009, User Story 1 Scenario 3)

```bash
curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer <enterprise-architect-token>" \
  http://localhost:8001/api/v1/admin/agent-prompts
# Expect: 403 — an Enterprise Architect token is rejected; PLATFORM_ADMIN is a distinct
# permission not implied by any architect role (Clarification Session 2026-07-24, Q1)
```

## Scenario 7: View history and restore a prior version (FR-007, FR-008, User Story 3)

```bash
curl -s http://localhost:8001/api/v1/admin/agent-prompts/chat_assistant/history | python3 -m json.tool
# Expect: 2 entries (both edits from Scenario 3 and Scenario 5), newest first,
# each with actor, changed_at, change_type: "edit", prior_text, new_text

HIST_ID=$(curl -s http://localhost:8001/api/v1/admin/agent-prompts/chat_assistant/history \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['items'][-1]['id'])")

# Restoring requires the SAME confirmation gate as an edit (Clarification Session 2026-07-24, Q4):
curl -s -o /dev/null -w "%{http_code}" \
  -X POST "http://localhost:8001/api/v1/admin/agent-prompts/chat_assistant/restore/$HIST_ID" \
  -H "Content-Type: application/json" \
  -d '{"expected_version": 2}'
# Expect: 422 (missing confirmation_id — restore is not a lower-friction path)

curl -s -X POST "http://localhost:8001/api/v1/admin/agent-prompts/chat_assistant/restore/$HIST_ID" \
  -H "Content-Type: application/json" \
  -d "{\"expected_version\": 2, \"confirmation_id\": \"CONFIRM-chat_assistant-restore-$HIST_ID\"}" \
  | python3 -m json.tool
# Expect: 200; a NEW history entry is recorded with change_type: "restore" (not a silent rewrite of the past)
```

## Scenario 8: Audit/history storage failure edge case (spec.md Edge Cases)

```bash
# (Integration-test only, not a curl scenario: stop the DB mid-request, or mock a failure
# in the history-insert step, and confirm the override write is rolled back — a prompt
# change and its history row succeed or fail together, in the same transaction.)
```

## Scenario 9: Browser — Admin Prompt Management page

1. Log in as a user in the `ADPAdministrator` Keycloak group; confirm a new nav section appears below "Architecture" (not visible when logged in as a plain Enterprise Architect).
2. Open the admin page — see all 6 agents listed, each labeled "Default" or "Custom" (FR-002).
3. Edit the Intake Extraction prompt, click Save — verify a distinct confirmation dialog appears (not an immediate save) explaining this changes live AI behavior platform-wide (FR-010).
4. Confirm — verify a success indication and the list updates to show "Custom" for that agent.
5. Navigate away mid-edit on a different agent without saving — verify a "discard unsaved changes?" warning appears (FR-011).
6. Open History for the edited agent — verify the edit appears with your username and timestamp; click Restore on the original entry — verify the same confirmation dialog appears before it takes effect.
