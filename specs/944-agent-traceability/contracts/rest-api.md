# REST contract: Agent Traceability (944)

Reads are open to every authenticated user.

## Automates links — `/api/v1/agentic` (writes: `WRITE_APPLICATION`, the existing prefix rule)

| Method | Path | Body | Success | Errors |
|---|---|---|---|---|
| GET | `/agents/{agent_id}/automates` | — | 200 `AgentAutomates` | 404 agent |
| POST | `/agents/{agent_id}/automates/capabilities` | `{"capability_id": str}` | 201 `AgentAutomates` | 404 agent/capability; 409 duplicate; 422 "Agents automate business capabilities at L3 only" |
| DELETE | `/agents/{agent_id}/automates/capabilities/{capability_id}` | — | 204 | 404 link |
| POST | `/agents/{agent_id}/automates/stages` | `{"stage_id": str}` | 201 `AgentAutomates` | 404 agent/stage; 409 duplicate |
| DELETE | `/agents/{agent_id}/automates/stages/{stage_id}` | — | 204 | 404 link |
| POST | `/agents/{agent_id}/automates/activities` | `{"activity_id": str}` | 201 `AgentAutomates` | 404 agent/activity; 409 duplicate |
| DELETE | `/agents/{agent_id}/automates/activities/{activity_id}` | — | 204 | 404 link |
| GET | `/capabilities/{capability_id}/agents` | — | 200 `{items: AgentSummary[], total}` | 404 capability |
| GET | `/value-stream-stages/{stage_id}/agents` | — | 200 same | 404 stage |
| GET | `/value-chain-activities/{activity_id}/agents` | — | 200 same | 404 activity |

These are extended, with additions only:
- `GET /agents`, `GET /agents/{id}`, `PATCH /agents/{id}`: every `Agent` gains `agentic_risk`;
- `GET /solutions/{app_id}/agents`: gains `solution_risk`.

All POST bodies use `extra="forbid"`. A reviewer gets 403.

Log lines (INFO, `adp.agentic.router`):
```text
agentic.automates.create agent=<id> kind=capability|stage|activity target=<id> actor=<sub>
agentic.automates.delete agent=<id> kind=... target=<id> actor=<sub>
```

## Agent compliance mappings — `/api/v1/compliance` (writes: `WRITE_COMPLIANCE`)

| Method | Path | Body | Success | Errors |
|---|---|---|---|---|
| PUT | `/controls/{control_id}/mappings/agents/{agent_id}` | `ControlMappingWrite` | 200 `ControlMapping` (`target_type: "agent"`) | 404 control/agent; 422 body |
| DELETE | `/controls/{control_id}/mappings/agents/{agent_id}` | — | 204 | 404 mapping |
| GET | `/agents/{agent_id}/mappings` | — | 200 `{items: ControlMapping[], total, status}` | 404 agent |
| GET | `/agents/statuses?ids=a,b` | — | 200 `{items: [{agent_id, status}]}` (unknown or unmapped ids give `not_assessed`) | 422 more than 200 ids |

These are extended:
- `GET /controls/{id}/mappings` includes agent rows, never filtered by `READ_APPLICATION_GOVERNANCE`;
- `GET /frameworks/{id}/rollup` and `GET /summary` count agents, with no shape change.

Log lines reuse `compliance.mapping.upsert|delete control_id=… target_type=agent target_id=… actor=…`.

## Example: `agentic_risk`

```json
{"band": "high",
 "factors": [{"code": "autonomy", "label": "autonomy 4"},
             {"code": "no_human_approval", "label": "no human approval"}],
 "missing": ["data_classification"],
 "not_considered": ["tool_side_effects"]}
```

## Example: `solution_risk`

```json
{"band": "high", "agents": [{"id": "ag-1", "name": "Chat assistant"}],
 "not_considered": ["tool_side_effects"]}
```
