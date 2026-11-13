# Data Model: Agent Registry Core (933)

Migration **043** (`043_agent_registry.py`, `down_revision = "042"`).

## Change to `applications`

| Change | Detail |
|---|---|
| CHECK `ck_app_application_type` | dropped and re-created as `application_type IS NULL OR application_type IN ('custom','cots','saas','legacy','agentic')` |
| Downgrade | `UPDATE applications SET application_type = NULL WHERE application_type = 'agentic'`, then restore the four-value CHECK |

## `agents` (new)

| Column | Type | Null | Rule |
|---|---|---|---|
| id | String(36) PK | no | UUID, stable (future runtime-registry match key) |
| name | String(255) | no | non-blank; not unique |
| description | Text | yes | |
| owner | String(255) | yes | |
| lifecycle_status | Text | no | CHECK in planned/active/sunset/retired; default 'active' |
| model_provider | String(100) | yes | |
| model_id | String(200) | yes | |
| model_version | String(100) | yes | |
| framework | String(100) | yes | |
| prompt_ref | String(200) | yes | version reference only |
| autonomy_level | SmallInteger | no | CHECK 0–4 |
| human_approval | Text | no | CHECK in none/on_write/on_irreversible/always |
| data_classification_max | Text | yes | CHECK null or in public/internal/confidential/restricted |
| a2a_card_url | Text | yes | http(s) only (app layer) |
| est_cost_per_run | Numeric(12,4) | yes | CHECK null or ≥ 0 |
| runs_per_month | Integer | yes | CHECK null or ≥ 0 |
| external_registry_ref | String(255) | yes | |
| created_at, updated_at | DateTime(tz) | no | |

**Indexes**:
- `ix_agents_autonomy_level`
- `ix_agents_model_provider`
- `ix_agents_lifecycle_status`

## `solution_agents` (new)

| Column | Type | Null | Rule |
|---|---|---|---|
| solution_app_id | String(36) | no | FK `applications.id` ON DELETE CASCADE |
| agent_id | String(36) | no | FK `agents.id` ON DELETE CASCADE |
| role | Text | no | CHECK in orchestrator/worker/reviewer/router |
| position | Integer | no | 0..n-1 within the solution, normalised |
| created_at | DateTime(tz) | no | |

- **Primary key**: `(solution_app_id, agent_id)`. A duplicate membership is rejected with 409.
- **Index**: `ix_solution_agents_agent_id`, for the reverse lookup "which solutions use this agent".

## Invariants

- **Membership target**: only applications with `application_type = 'agentic'` can be targeted. This is enforced in `adp.agentic.store` through the applications mirror, and returns 422.
- **Reclassification**: an agentic application that has memberships cannot be reclassified. This is enforced in `adp.application.store.update_application` and returns 409.
- **Deleting an application**: removes its memberships (CASCADE, plus an explicit delete for SQLite parity). Its agents are never deleted.
- **Deleting an agent**: removes all of its memberships, and the remaining positions in each affected solution are re-normalised.
- **Cost visibility**: `est_cost_per_run` and `runs_per_month` are returned as null, with `cost_visible = false`, to callers without `READ_APPLICATION_COST`. Setting them requires `WRITE_APPLICATION_COST`.

## Pydantic models (`adp.agentic.models`)

**Types**:
- `AutonomyLevel = Annotated[int, Field(ge=0, le=4)]`
- `HumanApproval`, `AgentLifecycle`, `DataClassification`, `SolutionRole`: `Literal` types

**Request and response models**:

| Model | Purpose | Notes |
|---|---|---|
| `AgentCreate` | create an agent | `extra="forbid"`; name stripped and non-blank; `a2a_card_url` http(s) validator; cost ≥ 0 |
| `AgentUpdate` | PATCH an agent | all optional; `model_fields_set` semantics; explicit `null` clears a field |
| `Agent` | full agent record | all columns plus `cost_visible: bool` and `solution_count: int` |
| `AgentSolution` | one solution an agent belongs to | `app_id`, `app_name`, `role`, `position` |
| `AgentDetail` | single-agent response | `Agent` plus `solutions: list[AgentSolution]` |
| `AgentListResponse` | list response | `items`, `total` |
| `SolutionAgentCreate` | add an agent to a solution | `agent_id`, `role` |
| `SolutionAgentUpdate` | change a member's role | `role` |
| `SolutionAgentOrder` | reorder a solution's agents | `agent_ids: list[str]` |
| `SolutionAgent` | one member of a solution | `agent: Agent`, `role`, `position` |
| `SolutionAgentListResponse` | a solution's members | `items`, ordered by position |

**Domain errors**:

| Error | HTTP status |
|---|---|
| `AgentNotFoundError` | 404 |
| `SolutionNotFoundError` | 404 |
| `NotAgenticSolutionError` | 422 |
| `DuplicateSolutionAgentError` | 409 |
| `OrderMismatchError` | 422 |
| `AgenticSolutionHasAgentsError` (in `adp.application.models`) | 409 |
