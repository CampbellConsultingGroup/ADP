# Feature Specification: Agent Traceability — what an agent automates, which controls govern it, and how risky its solution is

**Feature Branch**: `944-agent-traceability`
**Created**: 2026-11-16
**Status**: Draft
**Bead**: ADP-12x (Agentic P3 in `docs/agentic-solutions-plan.md` §7; depends on ADP-hii / 933, merged)
**Input**: User description: "944 agent-traceability (ADP-12x)". The bead says: "agent_capability_links ('automates') to business capability / value stream stage / value chain activity; sixth COMPLY-02 mapping target control_agent_mapping (MappingTargetType.AGENT) for EU AI Act etc.; derived pure-function 'solution agentic risk' indicator (max autonomy, irreversible tools, data classification)."

## Background and Resolved Decisions

933 added a registry of AI agents. Each agent belongs to one or more agentic solutions (Applications with type "agentic"), and records its autonomy level (0–4), human-approval policy and highest data classification. What the registry can't answer yet:
- **what business work** an agent does;
- **which regulatory controls** apply to it (the EU AI Act attaches obligations to an AI system, not only to the application around it);
- **how risky** an agentic solution is, taken as a whole.

This spec adds three things, one for each question.

| # | Decision |
|---|---|
| Plan §4 | An agent **automates** business capabilities, value stream stages and value chain activities. The overlap between a legacy application and an agent on one capability is how a "traditional application → series of agents" migration shows up (plan §5). |
| Plan §4 | Compliance gets a **sixth mapping target, Agent**, with the same shape as the five existing targets (status, evidence, assessed by and assessed at). |
| Plan §4 | The solution keeps its own application risk record. The **agentic risk** indicator is derived on read by a pure function and never stored, like `compute_compliance_status`. |
| N1 | The "irreversible tools" factor depends on tools, which arrive in P2 (ADP-a00). P2 is not a dependency of this spec and is itself waiting on diagram-core plumbing (ADP-o9p). **This spec computes the indicator from what agents record today** (autonomy, human approval, data classification), and the result names tools as a factor not yet considered. P2 adds that factor without changing the result's shape. |

Ground-truth checks against the code (main at ad98e2d, migration head `051`):

| # | Fact | Consequence |
|---|---|---|
| GT-1 | `agents` records `autonomy_level` (0–4), `human_approval` (none / on_write / on_irreversible / always), `data_classification_max` (public / internal / confidential / restricted, optional) and `lifecycle_status` (planned / active / sunset / retired) (`src/adp/agentic/models.py:18-21`, `store.py:42-60`) | These are the indicator's inputs. No new agent fields are needed |
| GT-2 | `adp.agentic` deliberately imports no other domain package (`src/adp/agentic/models.py:5`, 933 research D2/D10) | Checking that a target exists and is at the right level goes through narrow same-database mirror tables, the precedent used by `adp.strategy` and `adp.organization` |
| GT-3 | The targets exist: `business_capabilities` (levels 1–3), `value_stream_stages` and `value_chain_activities` (`src/adp/business/store.py:64`, `:115`, `:182`) | Three link kinds, one per target type |
| GT-4 | Compliance mappings are five parallel tables with the same columns, `MappingTargetType` has five values (`src/adp/compliance/models.py:387`), and each target type has PUT/DELETE routes under `/controls/{id}/mappings/...` (`src/adp/compliance/router.py:431-620`) | Agent is a sixth table, value and route pair, with the same write gate (`WRITE_COMPLIANCE`) |
| GT-5 | `get_entity_compliance_status` dispatches over the four per-entity types (`compliance/store.py:1048`). 924's framework roll-up and estate summary gather rows from those same four types (`:1121`, `:1239`) | Agents are added to all three, so an agent has a derived compliance status and is counted in roll-ups |
| GT-6 | 925 links strategy initiatives to mappings through five parallel `initiative_control_*_mapping` tables. The mapping editor shows the linked initiatives on every row (`web/src/compliance/ControlMappingsEditor.tsx:130`) | Initiative linkage for agent mappings is **out of scope**. The editor must not offer it on agent rows |
| GT-7 | The Agent detail screen shows the agent's fields and its solutions (`web/src/agentic/AgentDetail.tsx:118`). Agentic applications have an Agents tab (`SolutionAgentsPanel.tsx`) | The automates links and compliance status go on Agent detail. The solution's risk indicator goes on the Agents tab |
| GT-8 | Business capabilities and value stream stages have screens (`CapabilityNode.tsx`, `ValueStreamDetail.tsx`). Value chain activities have **no screen** yet (ADP-o9p will add one) | Reverse lookups show on capability rows and stages. For activities they are API only in this spec |
| GT-9 | The agent export writes `agentic/agents/<id>.json` with the agent's solutions (`src/adp/export/agentic.py:31`) | The file gains the agent's automates links and compliance mappings |

## Clarifications

### Session 2026-11-16

- Q: At which business capability levels can an agent be linked as "automates"? → A: L3 only, as for 937 realizations and 941 performers (FR-002).
- Q: Is the FR-013 agentic risk rule right? → A: Yes, as written. It is a fixed first rule; making it editable belongs to the ADP-6ky follow-on.
- Q: Does an agentic solution's derived compliance status take in its agents' mappings? → A: No. They stay separate. The solution's Agents tab shows each agent's own status beside it (FR-009a).

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: (always applies)
- **ART-IV** — Test-Driven Development: (always applies)
- **ART-II** — Single Source of Truth: each automates link and each compliance mapping is stored once. The agentic risk indicator and an agent's compliance status are derived on read and never stored.
- **ART-V** — Security by Design: automates links use the existing `WRITE_APPLICATION` rule for `/api/v1/agentic/`, and agent mappings use `WRITE_COMPLIANCE`. No new permission.
- **ART-IX** — Auditability: every link and mapping write is logged with the actor.
- **ART-XIII** — Typed Contracts: link kinds, mapping target type and risk bands are closed sets.
- **ART-XV** — Schema Evolution: one reversible migration (`052`) that adds tables only.
- **ART-VII** (AI grounding): not engaged.

## Threat Model *(mandatory — ART-V)*

Low risk. Automates links and the risk indicator are architecture classification data, readable by every platform user, like the agents themselves. The indicator reads no cost, risk or governance data that has its own sensitive-category gate, so it doesn't add one. Compliance mappings on agents follow the existing rule for non-application targets: readable by everyone, writable with `WRITE_COMPLIANCE`. Agents are not Applications, so `READ_APPLICATION_GOVERNANCE` doesn't apply to them.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Record what an agent automates (Priority: P1)

An architect opens an agent and records the business work it automates: one or more business capabilities, value stream stages or value chain activities. From a capability or a stage, anyone can see which agents automate it.

**Why this priority**: it is the traceability the registry is missing, and the basis for seeing a migration from an application to agents.

**Independent Test**: link an agent to a business L3 capability and to a value stream stage. Both show on the agent, and the agent shows on the capability row and the stage.

**Acceptance Scenarios**:

1. **Given** an agent, **When** an architect links it to a business L3 capability, **Then** the link is saved at once and listed on the agent with the capability's path.
2. **Given** that link, **When** anyone views the capability row, **Then** it lists the agent as automating it, and choosing the agent opens it.
3. **Given** an agent, **When** an architect links it to a value stream stage or a value chain activity, **Then** the link is saved and listed on the agent with its stream or chain name.
4. **Given** an attempt to link to a business L1 or L2 capability, **When** it is submitted, **Then** it is refused with a message naming the rule.
5. **Given** an existing link, **When** it is added again, **Then** it is refused as a duplicate. **When** it is removed, **Then** it disappears from both sides.
6. **Given** a reviewer, **When** they try to add or remove a link, **Then** they are refused.

---

### User Story 2 — Map compliance controls to an agent (Priority: P1)

A compliance lead maps a control (for example, an EU AI Act transparency obligation) to a specific agent, records its status and evidence, and sees the agent's derived compliance status.

**Why this priority**: AI regulation attaches obligations to the AI system itself. Today a control can only be mapped to the solution as a whole.

**Independent Test**: map one control as compliant and another as non-compliant to the same agent. The agent shows non-compliant, and the framework roll-up counts the agent.

**Acceptance Scenarios**:

1. **Given** a control, **When** a compliance lead maps it to an agent with a status, **Then** the mapping is saved, listed on the control with the agent's name, and listed on the agent.
2. **Given** an agent with several mappings, **When** it is viewed, **Then** its compliance status is derived by the existing rule (worst status wins) and shown on Agent detail.
3. **Given** agent mappings, **When** the framework roll-up and the compliance summary are read, **Then** agents are counted alongside capabilities, applications, designs and patterns.
4. **Given** a mapping to an agent that doesn't exist, **When** it is submitted, **Then** it is refused as not found.
5. **Given** an agent mapping row in the control's mapping editor, **When** it is shown, **Then** it offers no initiative linkage.

---

### User Story 3 — See how risky an agentic solution is (Priority: P2)

On an agentic solution's Agents tab, and on each agent, an architect sees an agentic risk band (high, medium, low) with the factors behind it.

**Why this priority**: it turns registry facts into a judgment architects can act on. It depends on no new data entry.

**Independent Test**: a solution with one level-4 agent with no human approval shows **high**, naming that agent and those factors. Making the agent require approval on every action lowers it.

**Acceptance Scenarios**:

1. **Given** an agent, **When** it is viewed, **Then** it shows its agentic risk band and the factors that set it.
2. **Given** an agentic solution, **When** its Agents tab is viewed, **Then** it shows the solution's band, which is the highest band among its non-retired agents, and names the agents that set it.
3. **Given** a solution with no agents, or only retired agents, **When** it is viewed, **Then** it shows "No agents" instead of a band.
4. **Given** an agent with no data classification recorded, **When** its band is computed, **Then** it uses the other factors and lists "data classification not recorded".
5. **Given** any band, **When** it is shown, **Then** it notes that tool side effects are not yet considered.
6. **Given** a change to an agent's autonomy, approval policy, classification or lifecycle, **When** the solution is viewed again, **Then** the band reflects it, with nothing stored to refresh.

---

### User Story 4 — Export and seed (Priority: P3)

The agent's export file carries its automates links and compliance mappings. The demo data shows them.

**Independent Test**: after an export cycle, an agent with links and mappings has both in its file. After seeding, ADP's own agents automate capabilities and one has an EU AI Act mapping.

**Acceptance Scenarios**:

1. **Given** an agent with automates links and compliance mappings, **When** the export runs, **Then** its file lists both, with ids and names.
2. **Given** the seed, **When** it runs, **Then** the ADP solution's agents automate business capabilities, and at least one agent has an EU AI Act control mapping.

---

### Edge Cases

- **Deleting an agent** removes its automates links and its compliance mappings, and never the targets or controls.
- **Deleting a capability, stage, activity or control** removes the links and mappings that point at it, and never the agent.
- **Retired agents** keep their links and mappings, and they are shown. They are left out of the solution's risk band.
- **An agent in several solutions** has one band. Each solution it belongs to counts it.
- **A capability automated by an agent and realized by an application** is allowed and expected during migration. This spec only shows both. Overlap analysis is P5.
- **Planned and sunset agents** count towards the solution's band. Only retired agents are left out.

## Requirements *(mandatory)*

### Functional Requirements

**Automates links (US1)**
- **FR-001**: An agent can be linked to any number of business capabilities, value stream stages and value chain activities. Each link records only the two ends and when it was made.
- **FR-002**: Business capability links are allowed only to **L3** capabilities. Other levels are refused with a message naming the rule.
- **FR-003**: A duplicate link is refused. A link to an agent or target that doesn't exist is refused as not found.
- **FR-004**: Links are added and removed on the agent. Adding a link saves on choose, following the ADP-w7z convention.
- **FR-005**: The agent lists its links grouped by kind, each with context: the capability's path, or the stage's value stream, or the activity's value chain and category.
- **FR-006**: Business capability rows and value stream stages show the agents that automate them, read only, and each agent opens its detail. Value chain activities expose the same list through the API only (GT-8).
- **FR-007**: Writes need `WRITE_APPLICATION` (the `/api/v1/agentic/` rule). Reads are open to every authenticated user.

**Compliance (US2)**
- **FR-008**: Controls can be mapped to agents with the same fields and upsert behavior as the other entity targets.
- **FR-009**: An agent's compliance status is derived by the existing rule over its mappings, and shown on Agent detail with its mappings.
- **FR-009a**: An agentic solution's own compliance status is unchanged: it is derived from the solution's own mappings only and never includes its agents' mappings. The solution's Agents tab shows each agent's compliance status beside it, so nothing is counted twice.
- **FR-010**: The framework roll-up and the compliance summary include agents as a target type.
- **FR-011**: The control's mapping editor offers Agent as a target type. Agent rows offer no initiative linkage (GT-6).
- **FR-012**: Agent mapping writes need `WRITE_COMPLIANCE`. Reads are open, as for capability, design and pattern mappings.

**Agentic risk (US3)**
- **FR-013**: An agent's band is derived from its own fields:
  - **high**: autonomy 3 or 4, **and** either human approval is "none" or its data classification is confidential or restricted;
  - **medium**: otherwise, autonomy 2 or more, **or** data classification confidential or restricted;
  - **low**: everything else.
- **FR-014**: The result lists the factors that set the band (for example "autonomy 4", "no human approval", "restricted data"), any missing inputs ("data classification not recorded"), and the factors not yet considered ("tool side effects").
- **FR-015**: A solution's band is the highest band among its non-retired agents. It names the agents at that band. With no such agent it is "No agents".
- **FR-016**: The band is computed on read by a pure function and never stored.
- **FR-017**: The band is shown on Agent detail, on the solution's Agents tab, and as a column in the agent list.

**Export and seed (US4)**
- **FR-018**: The agent export file adds `automates` (per kind, ids and names) and `compliance_mappings` (control, framework, status).
- **FR-019**: The seed links ADP's own agents to the capabilities they automate and maps at least one EU AI Act control to one agent.

**Unchanged**
- **FR-020**: Existing agent, solution membership and compliance mapping behavior is unchanged except for the additions above. The solution's own application risk record is untouched.

### Key Entities

- **Agent capability link**: an agent and a business L3 capability. "This agent automates this capability."
- **Agent stage link**: an agent and a value stream stage.
- **Agent activity link**: an agent and a value chain activity.
- **Agent control mapping**: a control and an agent, with compliance status, evidence reference, assessed by and assessed at.
- **Agentic risk** (derived, never stored): a band (high / medium / low, or "No agents" for a solution), the factors that set it, missing inputs, and factors not yet considered.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For any agent, an architect can see everything it automates and every control that governs it on one screen, without opening any other.
- **SC-002**: For any business capability or value stream stage, the agents that automate it are visible from the capability or stage itself.
- **SC-003**: Every agentic solution shows a risk band, or "No agents", and every band names the agents and factors behind it.
- **SC-004**: Changing an agent's autonomy, approval policy, classification or lifecycle changes its solution's band the next time it's viewed, with no refresh step.
- **SC-005**: Compliance roll-ups count agents, and no previously counted entity changes its count.
- **SC-006**: No stored field holds an agentic risk band or an agent compliance status (checked by a guard test).

## Assumptions

- **Business capability links are L3 only**, like 937's realization links and 941's performers (the user's guidance: L1 is navigation only, roll-ups come from the leaves). Confirmed in clarification.
- **The risk rule in FR-013** is a first fixed rule, like 938's risk band. Making it editable is left to the same follow-on as 938's (ADP-6ky). Confirmed in clarification.
- **Agent and solution compliance stay separate** (FR-009a). Confirmed in clarification.
- **The indicator ignores tools for now** (N1). P2 adds "irreversible tool without a human gate" as a factor, and moves "tool side effects" from "not yet considered" to the factors.
- **Retired agents are left out** of the solution band. Planned and sunset agents count, because they are in, or about to be in, the solution.
- **The links are edited on the agent only.** Capability, stage and activity sides are read only.
- **Not in this spec**: initiative linkage for agent mappings (GT-6); a value chain activity screen (ADP-o9p); overlap analysis between agents and applications (P5, ADP-ys5); governance tiles and portfolio dimensions for agents (P4, ADP-g58); chat retrieval and search changes.
