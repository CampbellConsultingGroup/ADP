# Tasks: Agent Traceability (944)

**Input**: `specs/944-agent-traceability/` (plan.md, spec.md, research.md, data-model.md, contracts/rest-api.md, quickstart.md)
**Tests**: required. The constitution's ART-IV and the plan both call for test-first work: write each test task before its implementation task and confirm it fails.

Format: `- [ ] T### [P?] [US?] description (file)`. `[P]` means the task touches a different file and depends on nothing still open in its phase.

## Phase 1: Setup

- [X] T001 Write migration `052_agent_traceability.py` (`down_revision="051"`), as in data-model.md:
  - `agent_capability_links`, `agent_stage_links` and `agent_activity_links`, each with a composite PK, CASCADE FKs on both legs and an index on the target column;
  - `control_agent_mapping`, in the 033 shape, with CHECK `ck_control_agent_mapping_status`, CASCADE on both legs and index `ix_control_agent_mapping_agent_id`;
  - a downgrade that drops all four in reverse order.

  (src/adp/store/migrations/versions/052_agent_traceability.py)
- [X] T002 [P] Write a Docker-gated migration test: upgrade → downgrade → upgrade, the CHECK rejecting a bad status, and cascades from agent, capability, stage, activity and control. Mirror `test_migration_051.py`. (tests/integration/test_migration_052.py)

## Phase 2: Foundational

- [X] T003 Add the metadata tables to the agentic store:
  - the three link tables, as plain columns with no ForeignKey;
  - narrow mirrors: `business_capabilities` (id, name, level, parent_id), `value_stream_stages` (id, value_stream_id, name, position), `value_streams` (id, name), `value_chain_activities` (id, value_chain_id, name, category, position) and `value_chains` (id, name);
  - a comment recording the fixture order rule: create the bstore metadata before the agstore metadata.

  (src/adp/agentic/store.py)
- [X] T004 [P] In the compliance package:
  - add `AGENT = "agent"` to `MappingTargetType`, plus the models `AgentComplianceMappings` (items, total, status) and `AgentComplianceStatuses` (items of `{agent_id, status}`) (src/adp/compliance/models.py);
  - add the `control_agent_mapping` table (`*_mapping_columns()`) and a narrow `agents` mirror (id, name) (src/adp/compliance/store.py).
- [X] T005 [P] Add an `"agent"` member to `MappingTargetType`, and set `TARGET_TYPE_LABEL.agent = "Agent"` and `MAPPING_PATH_SEGMENT.agent = "agents"`. (web/src/api/compliance.ts, web/src/compliance/ControlMappingsEditor.tsx)

**Checkpoint**: the backend imports cleanly, and the existing suites still pass. Check `pytest tests/unit/compliance tests/unit/agentic tests/contract/test_compliance* tests/contract/test_agentic*`, and fix any fixture that now needs the create order.

## Phase 3: User Story 1 — What an agent automates (P1) 🎯 MVP

**Goal**: link an agent to business L3 capabilities, value stream stages and value chain activities, and see the agents from the target's side.
**Independent test**: quickstart steps 1–2 and the CapabilityNode expander.

### Tests

- [X] T006 [P] [US1] Write the SQLite store tests (fixture: create the bstore metadata, then agstore):
  - add and list for each kind, with context: the capability path [L1, L2], the stage's value stream, the activity's chain and category;
  - the L3 rule (L1 and L2 raise `LevelRuleError`);
  - duplicate → `DuplicateLinkError`;
  - unknown agent or target → not found;
  - remove, and remove of a missing link → not found;
  - `delete_agent` clears the agent's links;
  - the reverse lookups, each sorted by agent name, plus a 404 for an unknown target;
  - the ordering rules from data-model.md.

  (tests/unit/agentic/test_agent_automates_store.py)
- [X] T007 [P] [US1] Write the contract tests:
  - POST/DELETE for each kind: 201/204, 404, 409, and the 422 body naming the L3 rule;
  - an extra body field → 422;
  - a reviewer → 403;
  - GET `/agents/{id}/automates` and the three reverse-lookup routes;
  - the log lines.

  (tests/contract/test_agent_traceability_api.py)

### Implementation

- [X] T008 [US1] Add the models `CapabilityLinkCreate`, `StageLinkCreate` and `ActivityLinkCreate` (`extra="forbid"`), `AutomatesCapability`, `AutomatesStage`, `AutomatesActivity`, `AgentAutomates` and `AgentSummary`, and the errors `LevelRuleError`, `TargetNotFoundError`, `DuplicateLinkError` and `LinkNotFoundError`. (src/adp/agentic/models.py)
- [X] T009 [US1] Implement in the agentic store:
  - `get_automates(agent_id)` (paths are built from the mirror's parent ids);
  - `add_capability_link`, which enforces L3 from the mirror's level, plus `add_stage_link`, `add_activity_link` and the matching `remove_*`;
  - `list_agents_for_capability`, `list_agents_for_stage` and `list_agents_for_activity`;
  - extend `delete_agent` to delete its link rows explicitly.

  Reads inner-join the mirrors, so dangling rows never surface. (src/adp/agentic/store.py)
- [X] T010 [US1] Add the routes `/agents/{id}/automates`, POST/DELETE for capabilities, stages and activities, and GET `/capabilities/{id}/agents`, `/value-stream-stages/{id}/agents` and `/value-chain-activities/{id}/agents`. Map the errors to 404/409/422, and log `agentic.automates.create|delete` with the actor. (src/adp/agentic/router.py)
- [X] T011 [P] [US1] Frontend API:
  - add the types `AgentAutomates` and `AgentSummary`, and the hooks `useAgentAutomates`, `useAddAutomates(kind)`, `useRemoveAutomates(kind)`, `useCapabilityAgents`, `useStageAgents` and `useActivityAgents`, invalidating the agent's automates and the reverse keys (web/src/api/agentic.ts);
  - add `useValueChains()` and `useValueChain(id)`, which call the existing `/api/v1/business/value-chains` routes (web/src/api/business.ts).
- [X] T012 [P] [US1] Write the component test for AgentAutomates: the three groups render with context; choosing an L3 saves at once; a stage is chosen through Value stream → Stage, and an activity through Value chain → Activity; an error resets the select; Remove works. (web/src/agentic/AgentAutomates.test.tsx)
- [X] T013 [US1] Implement AgentAutomates: the three groups, save on choose (ADP-w7z), selects disabled while saving, and L3 capabilities only, labeled by path. (web/src/agentic/AgentAutomates.tsx)
- [X] T014 [US1] Render `<AgentAutomates>` in AgentDetail, above Solutions. (web/src/agentic/AgentDetail.tsx)
- [X] T015 [P] [US1] Add an "Automated by agents" expander on L3 rows of CapabilityNode, loaded on expand. Each agent opens the Agents view. Add a test. (web/src/business/CapabilityNode.tsx, CapabilityNode.test.tsx)
- [X] T016 [P] [US1] List the agents for each stage in ValueStreamDetail, read only, using `useStageAgents`. (web/src/business/ValueStreamDetail.tsx)
- [X] T017 [US1] Add a `pendingAgentId` to App.tsx, with an `openAgent(id)` passed through the existing nav context. AgentsPage accepts `initialAgentId`, following the 939 pending-adoption precedent. (web/src/App.tsx, web/src/agentic/AgentsPage.tsx, web/src/application/appCapNav.tsx)

**Checkpoint**: US1 works on its own.

## Phase 4: User Story 2 — Compliance controls on agents (P1)

**Goal**: map controls to agents. An agent's status is derived, counted in roll-ups, and kept separate from the solution's status.
**Independent test**: quickstart steps 3–4.

### Tests

- [X] T018 [P] [US2] Write the SQLite tests (fixture: create agstore, then cstore):
  - `upsert_agent_mapping` inserts, then updates in place;
  - unknown control or agent → not found;
  - `list_mappings_for_agent`;
  - `list_mappings_for_control` includes agent rows;
  - `get_entity_compliance_status(AGENT)` takes the worst status, and gives `not_assessed` with no mappings;
  - the framework roll-up and the summary count agents, and the counts of existing entities are unchanged;
  - delete, and delete of a missing mapping → not found;
  - the bulk statuses.

  (tests/unit/compliance/test_agent_mappings.py)
- [X] T019 [P] [US2] Extend the contract tests:
  - PUT/DELETE `/controls/{id}/mappings/agents/{agent_id}`, with 404s and a reviewer 403;
  - GET `/agents/{id}/mappings` (with `status`) and `/agents/statuses?ids=`, including the over-200 → 422 case;
  - the control list never filters agent rows for a caller without the governance permission.

  (tests/contract/test_agent_traceability_api.py)
- [X] T020 [P] [US2] Add a guard: `_LINK_TABLE_BY_TARGET_TYPE` and `_MIRROR_BY_TARGET_TYPE` have no AGENT key, and no strategy route accepts an agent target. (tests/unit/strategy/test_initiative_agent_excluded.py)

### Implementation

- [X] T021 [US2] Implement in the compliance store:
  - `agent_exists`, `upsert_agent_mapping` (through `_upsert_entity_mapping`), `list_mappings_for_agent`, `delete_agent_mapping` and `get_agent_statuses(ids)`;
  - add AGENT to `_SUPPORTED_ENTITY_TYPES` and to the `get_entity_compliance_status` dispatch;
  - add an agent block to `list_mappings_for_control`, `_framework_entity_rows` and `_estate_entity_rows`, inner-joining the agents mirror;
  - delete agent mapping rows in `delete_control`, if the other mapping tables are handled there explicitly.

  (src/adp/compliance/store.py)
- [X] T022 [US2] Add the routes PUT/DELETE `/controls/{control_id}/mappings/agents/{agent_id}` (`WRITE_COMPLIANCE`, `compliance.mapping.*` log lines), GET `/agents/{agent_id}/mappings` and GET `/agents/statuses` (comma-separated ids, at most 200). Register `/agents/statuses` before `/agents/{agent_id}/...`. (src/adp/compliance/router.py)
- [X] T023 [P] [US2] Add the hooks `useAgentComplianceMappings(agentId)` and `useAgentComplianceStatuses(ids)`. Agent mapping writes invalidate both, plus the control's mappings. (web/src/api/compliance.ts)
- [X] T024 [P] [US2] Write and implement AgentCompliance: the derived status badge (reusing `STATUS_LABEL`/`STATUS_COLOR`), then each mapping with its control code, framework, status and evidence. The empty state is "No controls mapped". Render it in AgentDetail. (web/src/agentic/AgentCompliance.tsx, AgentCompliance.test.tsx, AgentDetail.tsx)
- [X] T025 [US2] Update the mapping editors:
  - **ControlMappingsEditor**: for the Agent target, pick from `useAgents()` instead of a free-text id; agent rows show the agent's name and no `LinkedInitiatives`; add a test;
  - **InitiativeControlMappingEditor**: exclude `agent` from its target types.

  (web/src/compliance/ControlMappingsEditor.tsx, ControlMappingsEditor.test.tsx, web/src/strategy/InitiativeControlMappingEditor.tsx)
- [X] T026 [US2] Show each agent's compliance status in SolutionAgentsPanel, with one `useAgentComplianceStatuses` call (FR-009a). The application's own Regulatory Compliance tab stays unchanged. (web/src/agentic/SolutionAgentsPanel.tsx)

**Checkpoint**: US1 and US2 both work.

## Phase 5: User Story 3 — Agentic risk (P2)

**Goal**: a derived risk band on each agent and each agentic solution.
**Independent test**: quickstart step 5.

### Tests

- [X] T027 [P] [US3] Write the pure tests for `agent_risk`:
  - the full matrix of autonomy 0–4 × approval (4 values) × classification (4 values + null) against FR-013;
  - the factor codes and labels for each band; `missing` when the classification is null; `not_considered == ["tool_side_effects"]`.

  For `solution_risk`: max over members, retired excluded, planned and sunset included, the names at the top band, and `band: null` for none or all retired. (tests/unit/agentic/test_agentic_risk.py)
- [X] T028 [P] [US3] Write the guard: migration `052` and every agentic and compliance metadata table have no column whose name contains `risk` or `band`, or that would store a derived status for agents. (tests/unit/agentic/test_agentic_risk_not_stored.py)
- [X] T029 [P] [US3] Extend the contract tests: `agentic_risk` on list, detail and PATCH responses; `solution_risk` on `GET /solutions/{id}/agents`; and the band changing after a PATCH, with nothing to refresh. (tests/contract/test_agent_traceability_api.py)

### Implementation

- [X] T030 [US3] Add the models `RiskFactor`, `AgenticRisk` and `SolutionAgenticRisk` with `Literal` bands and codes. Add `Agent.agentic_risk` and `SolutionAgentListResponse.solution_risk`. (src/adp/agentic/models.py)
- [X] T031 [US3] Implement `agent_risk()` and `solution_risk()` as pure functions with no I/O, following the data-model.md rules. (src/adp/agentic/risk.py)
- [X] T032 [US3] Compute `agentic_risk` in `_row_to_agent`, and `solution_risk` in `list_solution_agents` and the router's response. (src/adp/agentic/store.py, src/adp/agentic/router.py)
- [X] T033 [P] [US3] Add the frontend types, plus a `RiskBadge` (high, medium, low or "No agents", using tokens) and a `RiskFactors` list that includes the missing and not-considered notes. Add a test. (web/src/api/agentic.ts, web/src/agentic/agenticRisk.tsx, agenticRisk.test.tsx)
- [X] T034 [US3] Show the band:
  - **AgentDetail**: badge and factors;
  - **AgentsPage**: a Risk column;
  - **SolutionAgentsPanel**: a solution banner (band, the agents that set it, "tool side effects not yet considered"), and a badge on each member.

  Extend the tests. (web/src/agentic/AgentDetail.tsx, AgentsPage.tsx, SolutionAgentsPanel.tsx, agentic.test.tsx)

**Checkpoint**: US1–US3 all work.

## Phase 6: User Story 4 — Export and seed (P3)

- [X] T035 [P] [US4] Write the export test first: an agent with links and mappings is serialized with `automates` (capabilities, stages, activities, each with id and name) and `compliance_mappings` (control_id, control_code, framework_id, framework_name, compliance_status). An agent with neither gets empty lists. (tests/unit/export/test_agentic_export.py, or the existing agentic export test)
- [X] T036 [US4] Implement the export, bulk-fetching the links and mappings in two to three queries per cycle. (src/adp/export/agentic.py)
- [X] T037 [US4] Extend seed phase D:
  - add the L2 "Architecture Management" under "IT & Data", with L3s "Requirements Capture", "Solution Option Analysis" and "Design Validation";
  - link the ADP agents to them;
  - find or create the "EU AI Act" framework and the control "Art. 50" ("Transparency obligations"), and map the chat assistant as `partial`;
  - add the four new tables to WIPE_TABLES before `agents`.

  Don't run it locally. (scripts/seed_retail.py)

## Phase 7: Polish

- [X] T038 Gates: `.venv/bin/ruff check src/ tests/`, `mypy src/`, `adp-generate --check`, `pytest tests/ --ignore=tests/integration -q`, and in `web/`: `npx tsc --noEmit` and `npm run test:run`.
- [X] T039 Apply migration `052` locally (`alembic upgrade head`; ask first if anything is unexpected). Restart the backend, run every quickstart step with curl and Playwright, then clean up all scratch data.
- [X] T040 Add a hand-written Recent Changes entry to CLAUDE.md, not with `update-agent-context.sh`, and flip "planned" to implemented in its Active Technologies line. (CLAUDE.md)
- [X] T041 Run `node .gitnexus/run.cjs analyze --index-only`, then `detect-changes --scope all`. File beads for follow-ons: initiative linkage for agent mappings, a value chain activity screen with its agents, and the tool factor in P2 (ADP-a00, as a note).

## Dependencies

- Phase 1 → Phase 2 → stories.
- US1, US2 and US3 depend only on Phase 2, and are independent of each other. They share `test_agent_traceability_api.py`, `models.py`, `agentic.ts`, AgentDetail and SolutionAgentsPanel, so edits to the same file run in sequence.
- US4 depends on US1 and US2, since it exports their data.
- Polish comes last.

## Parallel examples

- Phase 2: T004 ∥ T005 (backend and frontend).
- US1: T006 ∥ T007 ∥ T011 ∥ T012. Then T015 ∥ T016 once T011 is done.
- US2: T018 ∥ T019 ∥ T020 ∥ T023.
- US3: T027 ∥ T028 ∥ T029 ∥ T033.

## Implementation strategy

The MVP is US1: the automates links, with both directions of lookup. US2 (compliance) is the second P1 increment. US3 adds the derived risk band, and US4 adds export and seed. Each story ends at a checkpoint with the suites passing.
