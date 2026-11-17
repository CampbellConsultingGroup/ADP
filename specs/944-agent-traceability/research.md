# Research: Agent Traceability (944)

All decisions below come from reading the code on main at ad98e2d. There were no open NEEDS CLARIFICATION items after `/speckit-clarify`.

## R1. Automates links live in `adp.agentic`, with narrow mirrors

- **Decision**: three link tables live on `adp.agentic.store`'s metadata. The store validates the targets through narrow same-database mirror tables:
  - `business_capabilities`: id, name, level, parent_id;
  - `value_stream_stages`: id, value_stream_id, name;
  - `value_streams`: id, name;
  - `value_chain_activities`: id, value_chain_id, name, category;
  - `value_chains`: id, name.

  The real FKs (CASCADE on both legs) exist only in migration `052`. The metadata declares plain columns.
- **Rationale**: the links are edited on the agent (FR-004), and `adp.agentic` imports no other domain package (933 D2/D10). Mirrors are the established way to keep that contract (`adp.strategy`, `adp.organization`, `adp.compliance`). Declaring cross-metadata FKs would force every agentic fixture to create the business tables (the 940 `owning_org_unit_id` precedent).
- **Alternatives**: putting the links in `adp.business` was rejected. It makes business own agent data, and business would then have to import or mirror `agents`.
- **Gotcha**: fixtures that create both the bstore and agstore metadata must create bstore first. agstore's mirrors are then skipped by `checkfirst`. This is the same order rule already documented for astore/agstore and astore/ostore.

## R2. Reverse lookups are served by the agentic router

- **Decision**: three read routes under `/api/v1/agentic/`:
  - `GET /capabilities/{cap_id}/agents`;
  - `GET /value-stream-stages/{stage_id}/agents`;
  - `GET /value-chain-activities/{activity_id}/agents`.

  Each returns agent summaries. A target that doesn't exist gives 404, checked through the mirror.
- **Rationale**: the precedent is for reverse lookups to sit on the target's router, which imports the owning store. Here that would make `adp.business` import `adp.agentic`. Keeping them on the agentic router avoids that coupling, and the frontend simply calls a different path.
- **Alternatives**: adding them to `adp.business.router` was rejected (cross-package import, and the business router file is already past the size threshold).

## R3. L3 rule enforced in the store

- **Decision**: `add_capability_link` reads the mirror's `level`. Anything other than 3 raises `LevelRuleError` → 422 "Agents automate business capabilities at L3 only".
- **Rationale**: same as 937 and 941. An FK can't check the far row's level.

## R4. Agent as the sixth compliance target, in `adp.compliance`

- **Decision**:
  - add `MappingTargetType.AGENT = "agent"`;
  - add `control_agent_mapping` (control_id, agent_id, the shared mapping columns), plus a narrow `agents` mirror (id, name) on the cstore metadata;
  - add `upsert_agent_mapping`, `list_mappings_for_agent` and `delete_agent_mapping`;
  - extend `list_mappings_for_control`, `get_entity_compliance_status` (and `_SUPPORTED_ENTITY_TYPES`), `_framework_entity_rows` and `_estate_entity_rows`;
  - add the routes PUT/DELETE `/controls/{control_id}/mappings/agents/{agent_id}`.
- **Rationale**: this is exactly the COMPLY-02 shape. Roll-ups only count entities by status, not by type, so agents are counted with no response-shape change (SC-005).
- **Gotcha**: cstore's `agents` mirror collides with agstore's full `agents` table in fixtures that create both, as `applications` already does. Create agstore first, then cstore.

## R5. The agent-side compliance read lives on the compliance router

- **Decision**: `GET /api/v1/compliance/agents/{agent_id}/mappings` returns `{items, total, status}`. `status` comes from `get_entity_compliance_status(AGENT, …)`. A second route, `GET /api/v1/compliance/agents/statuses?ids=a,b,c`, returns the derived status for each id. Ids with no mappings come back `not_assessed`. The solution's Agents tab uses it (FR-009a).
- **Rationale**: the agentic router can't import compliance (R1), so the read stays where the data lives. One bulk call keeps the Agents tab at one request, instead of one request per agent.
- **Alternatives**: embedding the status in the agent read model was rejected because it needs a cross-package import.

## R6. Initiative linkage stays at five target types

- **Decision**: no `initiative_control_agent_mapping` table. The strategy router has a literal route for each of the five target types, so `AGENT` can't reach `_MIRROR_BY_TARGET_TYPE`. A test asserts that `_LINK_TABLE_BY_TARGET_TYPE` has no AGENT key, so the omission is deliberate.
- **Frontend**:
  - `ControlMappingsEditor` hides `LinkedInitiatives` on agent rows;
  - `InitiativeControlMappingEditor`'s target-type choices exclude `agent`;
  - `MAPPING_PATH_SEGMENT.agent = "agents"`.

## R7. The agentic risk indicator is a pure function, embedded in reads

- **Decision**: a new module `adp.agentic.risk` with no I/O:
  - `agent_risk(autonomy_level, human_approval, data_classification_max) -> AgenticRisk`;
  - `solution_risk(members: list[(agent_id, agent_name, lifecycle_status, AgenticRisk)]) -> SolutionAgenticRisk`.
- **Rule** (FR-013, confirmed in clarification). `sensitive` means confidential or restricted:
  - `high` if autonomy ≥ 3 and (approval == "none" or sensitive);
  - else `medium` if autonomy ≥ 2 or sensitive;
  - else `low`.
- **Factors**, a closed set of codes with labels. The band lists only the factors that set it:
  - `autonomy` ("autonomy 3");
  - `no_human_approval` ("no human approval");
  - `sensitive_data` ("restricted data").
- **Also listed**: `missing` has `data_classification` when the classification is null. `not_considered` is always `["tool_side_effects"]` (N1).
- **Solution**: the highest band among non-retired members, with the names of the agents at that band. With no such member, `band = null` ("No agents").
- **Where it appears**: `Agent` gains `agentic_risk`, computed in `_row_to_agent`, so the list, detail and membership reads all carry it with no extra query. `SolutionAgentListResponse` gains `solution_risk`.
- **Rationale**: derived on read and never stored (ART-II, SC-006), following the `compute_compliance_status` and 938 band precedents. Embedding it in reads gives the agent-list column (FR-017) for free.
- **Guard**: a test asserts that migration `052` and the agentic metadata have no column named like `risk` or `band`.

## R8. UI

- **Agent detail** gets an **Automates** section with three groups:
  - **Business capabilities**: a select of L3 capabilities, labeled by path, from `useCapabilities()`;
  - **Value stream stages**: a Value stream → Stage picker, from `useValueStreams()` / `useValueStream(id)`;
  - **Value chain activities**: a Value chain → Activity picker, with new `useValueChains()` / `useValueChain(id)` hooks in `api/business.ts`. No value chain UI exists yet, so these are its first frontend hooks.

  Choosing a value saves it at once (the ADP-w7z convention), and each row has a Remove button. The section also shows the agent's **Compliance** (status, then the mappings with control and framework) and its **Agentic risk** (band and factors).
- **Agents list**: a Risk column.
- **SolutionAgentsPanel**: a solution band banner, plus a risk band and compliance status per member.
- **CapabilityNode**: an "Automated by agents" expander, loaded on expand, on L3 rows.
- **ValueStreamDetail**: the agents for each stage, loaded with the stage.
- **ControlMappingsEditor**: Agent becomes a target type, picked from `useAgents()` instead of free-text id entry.
- **Navigation**: an agent link opens the Agents view on that agent. This reuses App.tsx's existing view switch and adds a pending-agent id, following the pending-adoption precedent from 939.

## R9. Export and seed

- **Export**: `adp.export.agentic._serialize_agent` adds `automates` (`capabilities`, `stages`, `activities`, each with id and name) and `compliance_mappings` (control_id, control_code, framework_id, framework_name, compliance_status). These are bulk-fetched, two to three queries per cycle, so there's no N+1. `adp.export` may import any domain package.
- **Seed** (phase D, extended):
  - add an L2 "Architecture Management" under "IT & Data", with L3s "Requirements Capture", "Solution Option Analysis" and "Design Validation";
  - link ADP's agents to them;
  - find or create an "EU AI Act" framework and the control "Art. 50 — Transparency obligations", and map the chat assistant to it as `partial`;
  - add `agent_capability_links`, `agent_stage_links`, `agent_activity_links` and `control_agent_mapping` to WIPE_TABLES before `agents`.

  Frameworks are not wiped, so the seed reuses any existing framework with that name. It isn't run locally (it hard-wipes the database).

## R10. Migration `052`

One reversible migration, `down_revision = "051"`, that only adds tables:
- `agent_capability_links`, `agent_stage_links`, `agent_activity_links`: composite PK, CASCADE on both legs, and an index on the target column;
- `control_agent_mapping`: the 033 shape, with CHECK `ck_control_agent_mapping_status` and CASCADE on both legs.

A Docker-gated `test_migration_052.py` covers upgrade, downgrade and the cascades.
