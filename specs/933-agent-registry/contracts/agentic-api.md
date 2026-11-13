# API Contract: `/api/v1/agentic` (933)

**Authorization**:
- All mutating routes require `WRITE_APPLICATION`, through the prefix rule `("/api/v1/agentic/", WRITE_APPLICATION)`.
- Sending `est_cost_per_run` or `runs_per_month` in a create or update body additionally requires `WRITE_APPLICATION_COST`, checked inline; otherwise the response is 403.
- Reads are open. Cost fields are returned only when the caller holds `READ_APPLICATION_COST`; otherwise they are `null` and `cost_visible` is `false`.

## Agents

| Method | Path | Body | Success | Errors |
|---|---|---|---|---|
| GET | `/api/v1/agentic/agents` | query: `autonomy_level`, `autonomy_min`, `model_provider`, `owner`, `lifecycle_status` | 200 `AgentListResponse` (each item includes `solution_count`) | 422 bad filter value |
| POST | `/api/v1/agentic/agents` | `AgentCreate` | 201 `Agent` | 422 validation, 403 cost fields without permission |
| GET | `/api/v1/agentic/agents/{agent_id}` | – | 200 `AgentDetail` (with `solutions[]`) | 404 |
| PATCH | `/api/v1/agentic/agents/{agent_id}` | `AgentUpdate` | 200 `Agent` | 404, 422, 403 (cost) |
| DELETE | `/api/v1/agentic/agents/{agent_id}` | – | 204 (memberships removed) | 404 |

## Solution membership

| Method | Path | Body | Success | Errors |
|---|---|---|---|---|
| GET | `/api/v1/agentic/solutions/{app_id}/agents` | – | 200 `SolutionAgentListResponse` ordered by position | 404 unknown app |
| POST | `/api/v1/agentic/solutions/{app_id}/agents` | `{agent_id, role}` | 201 `SolutionAgentListResponse` (appended at the end) | 404 app/agent, 422 app not agentic or bad role, 409 duplicate |
| PATCH | `/api/v1/agentic/solutions/{app_id}/agents/{agent_id}` | `{role}` | 200 `SolutionAgent` | 404, 422 |
| PUT | `/api/v1/agentic/solutions/{app_id}/agents/order` | `{agent_ids}` | 200 `SolutionAgentListResponse` | 404, 422 when the id list does not match the current members exactly |
| DELETE | `/api/v1/agentic/solutions/{app_id}/agents/{agent_id}` | – | 204 (positions re-normalised) | 404 |

## Changed existing route

| Method | Path | Change |
|---|---|---|
| PATCH | `/api/v1/applications/{app_id}` | `application_type` accepts `"agentic"`. Changing it away from `"agentic"` while the app has agents returns **409**, with a message naming the number of agents. |
| GET | `/api/v1/applications?application_type=agentic` | works as is, through the existing equality filter |

## Example: `AgentDetail`

```json
{
  "id": "6f1c…",
  "name": "Claims Triage Agent",
  "description": "Classifies incoming claims and routes them",
  "owner": "Claims Platform Team",
  "lifecycle_status": "active",
  "model_provider": "Anthropic",
  "model_id": "claude-sonnet-5-5",
  "model_version": "2026-09",
  "framework": "Claude Agent SDK",
  "prompt_ref": "claims-triage@v7",
  "autonomy_level": 2,
  "human_approval": "on_irreversible",
  "data_classification_max": "confidential",
  "a2a_card_url": "https://agents.example.com/claims-triage/.well-known/agent-card.json",
  "est_cost_per_run": "0.0420",
  "runs_per_month": 12000,
  "cost_visible": true,
  "external_registry_ref": null,
  "solution_count": 2,
  "solutions": [
    {"app_id": "a1…", "app_name": "Claims Handling", "role": "worker", "position": 1},
    {"app_id": "b2…", "app_name": "Fraud Review", "role": "reviewer", "position": 0}
  ],
  "created_at": "2026-11-13T10:00:00Z",
  "updated_at": "2026-11-13T10:00:00Z"
}
```
