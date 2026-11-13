# Quickstart: Agent Registry Core (933)

These steps assume the API is on `:8001` with `ADP_AUTH_ENABLED=false` (the dev user is Enterprise Architect and holds every permission, including cost), and that migration 043 has been applied (`alembic upgrade head`).

```bash
API=http://localhost:8001/api/v1
```

## 1. Create an agentic solution

```bash
APP=$(curl -s -X POST $API/applications -H 'content-type: application/json' \
  -d '{"name":"Claims Handling (scratch)","application_type":"agentic"}' | jq -r .id)
```

## 2. Register agents (US1)

```bash
ORCH=$(curl -s -X POST $API/agentic/agents -H 'content-type: application/json' -d '{
  "name":"Claims Orchestrator","owner":"Claims Platform","model_provider":"Anthropic",
  "model_id":"claude-sonnet-5-5","framework":"Claude Agent SDK","prompt_ref":"claims-orch@v3",
  "autonomy_level":2,"human_approval":"on_irreversible","data_classification_max":"confidential",
  "est_cost_per_run":0.05,"runs_per_month":10000}' | jq -r .id)
TRIAGE=$(curl -s -X POST $API/agentic/agents -H 'content-type: application/json' -d '{
  "name":"Claims Triage Agent","autonomy_level":3,"human_approval":"none"}' | jq -r .id)
```

**Expect 422** for each of these:
- `"autonomy_level":5`
- `"human_approval":"sometimes"`
- `"a2a_card_url":"javascript:alert(1)"`
- `"est_cost_per_run":-1`

## 3. Build the solution

```bash
curl -s -X POST $API/agentic/solutions/$APP/agents -H 'content-type: application/json' \
  -d "{\"agent_id\":\"$ORCH\",\"role\":\"orchestrator\"}"
curl -s -X POST $API/agentic/solutions/$APP/agents -H 'content-type: application/json' \
  -d "{\"agent_id\":\"$TRIAGE\",\"role\":\"worker\"}"
curl -s -X PUT  $API/agentic/solutions/$APP/agents/order -H 'content-type: application/json' \
  -d "{\"agent_ids\":[\"$TRIAGE\",\"$ORCH\"]}"           # → positions 0,1 swapped
```

**Expect**:
- Adding the same agent again returns **409**.
- Adding an agent to a non-agentic application returns **422**.

## 4. Reclassification guard (Clarification Q1)

```bash
curl -s -o /dev/null -w '%{http_code}\n' -X PATCH $API/applications/$APP \
  -H 'content-type: application/json' -d '{"application_type":"custom"}'   # → 409
```

## 5. Estate-wide list and shared agents (US2)

Create a second agentic application, `APP2`, and add `$TRIAGE` to it as `reviewer`. Then:

```bash
curl -s "$API/agentic/agents?autonomy_min=3" | jq '.items[].name'          # → Claims Triage Agent only
curl -s $API/agentic/agents/$TRIAGE | jq '.solutions'                      # → both apps, worker + reviewer
```

## 6. Delete semantics

```bash
curl -s -X DELETE $API/applications/$APP2     # → 204
curl -s $API/agentic/agents/$TRIAGE | jq '.solution_count'                 # → 1 (agent survives)
```

## 7. Search and export (US3)

```bash
curl -s "$API/search?q=claims%20triage&entity_types=agent" | jq   # → entity_type "agent" hits
# (the search endpoint defaults to capability types only; pass entity_types for any other type)
ls $ADP_BUSINESS_ARCH_EXPORT_ROOT/agentic/agents/   # after one export interval
```

## 8. Cost gating (Clarification Q2)

This is verified by contract tests that override the role to one that lacks `READ_APPLICATION_COST`:
- the response has `est_cost_per_run: null` and `cost_visible: false`;
- a PATCH that sets `est_cost_per_run` returns 403.

No curl path exists for this check: dev mode has no role-override header (the 931 precedent).

## 9. UI walkthrough

1. Applications → open the scratch app → **Agents** tab → add, re-role and reorder agents.
2. **Agents** nav → filter by autonomy and provider → open the shared agent → both solutions are listed.
3. Delete the agent → the confirmation discloses the solution count.

## Cleanup

Delete the scratch applications and agents, then confirm the counts are back to their baseline.
