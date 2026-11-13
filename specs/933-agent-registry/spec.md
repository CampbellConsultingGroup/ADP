# Feature Specification: Agent Registry Core (Agentic Solutions P1)

**Feature Branch**: `933-agent-registry`
**Created**: 2026-11-13
**Status**: Draft
**Input**: User description: "ADP-hii — Agent registry core. Capture agentic solutions (an Application of type agentic) and the AI agents that make them up: model, prompt version, autonomy level, human approval and cost estimates, shared across solutions. P1 of docs/agentic-solutions-plan.md (ADP-wma)."

## Background and Resolved Decisions

The planning bead ADP-wma (see `docs/agentic-solutions-plan.md`) established that a solution delivered by a set of cooperating AI agents should not be squeezed into ADP's one-row-per-application model. The user confirmed these five decisions on 2026-11-13. They are inputs to this spec, not open questions:

1. An **agentic solution is an Application** with a new application type, "agentic". It keeps every existing portfolio capability: TIME, 7R, health, value, cost, risk, capability links and framework tags. The **agents that make it up live in their own registry**.
2. **Agents may be shared**: one agent can be part of several solutions.
3. **Autonomy** is recorded on ADP's own 0–4 scale (Assistive, Supervised, Conditional, Bounded, Autonomous).
4. ADP records a **prompt version reference** only, never the prompt text.
5. ADP is a **design-time registry**. Run cost and volume are entered estimates. A future link to a runtime agent registry is anticipated, so each agent carries an optional external registry reference. Synchronisation with such a registry is out of scope.

Out of scope for this feature (later phases, already filed as beads):
- tools and agent-to-agent topology, plus the topology diagram (ADP-a00);
- agent→capability "automates" links and compliance mappings (ADP-12x);
- portfolio grouping and governance rules (ADP-g58);
- supersession of legacy applications and Agent Card import (ADP-ys5);
- runtime registry sync (ADP-jrv).

## Clarifications

### Session 2026-11-13

- Q1: Can only "agentic" applications have agents, or any application (for example, a CRM with an embedded copilot)? → A: **Agentic only.** Reclassifying an application away from "agentic" is rejected while it still has agents. Embedded copilots on traditional applications may be revisited later.
- Q2: Should agent cost estimates be hidden from users without the application-cost read permission? → A: **Yes, gated like application cost.** Cost fields are omitted for those users, and the rest of the agent stays visible.

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: (always applies)
- **ART-IV** — Test-Driven Development: (always applies)
- **ART-II** — The Model is the Single Source of Truth: agents become canonical, governed records instead of free-text notes on an application's description. A shared agent exists exactly once, however many solutions use it.
- **ART-III** — Everything is Machine-Readable: agents and solution memberships are exported as machine-readable files alongside the existing application export, and are discoverable through platform search.
- **ART-V** — Security by Design: in scope. A new write surface is added, and agent records carry data-classification and cost information (see Threat Model).
- **ART-VII** — Grounded AI Only: not in scope. This feature records information *about* AI agents and invokes no AI itself.
- **ART-IX** — Provenance and Auditability: agent create, update and delete actions, and membership changes, are audited the same way application changes are.
- **ART-XI** — Traceability End to End: establishes the solution→agent link that later phases extend to capabilities, controls and topology.
- **ART-XIII** — Typed Contracts Everywhere: autonomy level, human-approval policy, solution role and lifecycle status are closed value sets, not free text.
- **ART-XV** — Schema Evolution is Governed: one additive schema change. No existing data is altered, and "agentic" is added to the application-type value set.

## Threat Model *(mandatory — ART-V)*

**Assets at risk**:
- The integrity of the agent inventory, which is used for AI governance and regulatory reporting (EU AI Act and NIST AI RMF inventory expectations).
- Agent cost estimates.
- The record of which agents handle which data classification.

**Trust boundaries crossed**: browser → API only. No new external integration: an Agent Card URL is stored as a reference and is never fetched by this feature.

**Abuse cases**:
- **Unauthorised changes to the inventory.** A user without application-write permission creates, edits or deletes agents → the same permission that governs editing applications governs editing agents.
- **Hiding a risky agent.** A user understates a high-autonomy agent's autonomy level or data classification → this cannot be prevented technically at design time. It is mitigated by audit history on every change (who changed what, when).
- **Script injection through links.** A malicious URL is stored in the Agent Card or prompt reference fields and rendered as a clickable link → only `http`/`https` URLs are accepted and rendered as links (the 921 `source_url` precedent).
- **Prompt leakage.** A user pastes full prompt text into the prompt-reference field → the field is defined and labelled as a version reference with a short length limit, so ADP does not become a store of prompt text.
- **Dangling references.** An agent is deleted while still part of solutions, or a solution is deleted while it has agents → membership links are removed with either side, and a shared agent survives the deletion of any one solution.

**Residual risk**: self-reported attribute accuracy (autonomy, classification, cost) is inherent to a design-time registry and is accepted. Verification against runtime reality is deferred to the runtime-registry link (ADP-jrv).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Record an agentic solution and its agents (Priority: P1)

An architect is documenting a new claims-handling solution built as an orchestrator agent plus three specialist agents. They create (or reclassify) the solution as an Application of type "agentic". Then they register each agent with its owner, model, framework, prompt version, autonomy level, human-approval policy, maximum data classification and cost estimates, and add each one to the solution with its role (orchestrator, worker, reviewer or router) in order.

**Why this priority**: this is the minimum that answers the governance questions the plan exists for: which agents make up this solution, who owns them, what they run on, and how autonomous they are. Every later phase builds on these records.

**Independent Test**: create an agentic application, register four agents, add them to it with roles, then reload the application and confirm that the agents, their roles, their order and every attribute are shown exactly as entered.

**Acceptance Scenarios**:

1. **Given** an application of type "agentic", **When** the architect registers an agent with all attributes and adds it to the solution as "orchestrator", **Then** the solution's Agents view lists that agent with its role, model, autonomy level and approval policy.
2. **Given** a solution with three agents, **When** the architect changes their order, **Then** the new order persists across reloads.
3. **Given** an agent in a solution, **When** the architect removes it from the solution, **Then** it no longer appears in that solution but remains in the registry.
4. **Given** an agent being registered, **When** an autonomy level outside 0–4, an unknown approval policy or role, or a non-http(s) Agent Card URL is supplied, **Then** the save is rejected with a message naming the invalid field and nothing is stored.
5. **Given** the same agent, **When** the architect tries to add it to the same solution a second time, **Then** the attempt is rejected as a duplicate.

---

### User Story 2 - See every agent across the estate, including shared ones (Priority: P2)

A head of architecture or AI governance lead opens a single Agents list showing every registered agent across all solutions. They filter it by autonomy level, model provider, owner and lifecycle status. Opening any agent shows every solution it is part of, so a shared agent (for example, a "policy lookup" agent used by three solutions) is visibly shared.

**Why this priority**: an estate-wide inventory is what regulators and AI-governance frameworks expect, and it is the first view that shows agent reuse. It depends on records existing (US1), but it is independently valuable once they do.

**Independent Test**: register five agents across two solutions, with one shared between both. Confirm that the list shows five agents, that filtering by autonomy level 3+ returns only the matching ones, and that the shared agent's detail lists both solutions.

**Acceptance Scenarios**:

1. **Given** agents in several solutions, **When** the user opens the Agents list, **Then** every agent appears exactly once with its owner, model provider, autonomy level, lifecycle status and number of solutions.
2. **Given** the Agents list, **When** the user filters by autonomy level and/or model provider, **Then** only matching agents are shown.
3. **Given** an agent used by two solutions, **When** the user opens it, **Then** both solutions are listed with the agent's role in each, and each links to the solution.
4. **Given** an agent that belongs to no solution, **When** the user views the list, **Then** it is still shown and identified as unassigned.

---

### User Story 3 - Agents are discoverable and exported like other architecture records (Priority: P3)

Users find agents through the platform's search, the same way they find applications and capabilities. AI tools and file-based consumers that read ADP's exported architecture files receive agent records and solution memberships alongside the existing application export.

**Why this priority**: it keeps agents first-class across the platform rather than being visible only on their own screen. It is lower priority because the registry is useful without it.

**Independent Test**: register an agent named "Claims Triage Agent", search for "claims triage" and confirm it is returned. Wait for the export cycle and confirm that the agent's file exists with its attributes and solution memberships. Delete the agent and confirm that both the search result and the file disappear.

**Acceptance Scenarios**:

1. **Given** a newly registered or renamed agent, **When** a user searches by its name or description, **Then** the agent is returned and reflects its current name.
2. **Given** a deleted agent, **When** a user searches for it, **Then** it is no longer returned.
3. **Given** the periodic architecture export, **When** it runs, **Then** each agent has a machine-readable record with its attributes and the solutions it belongs to, and the files of deleted agents are removed.

---

### Edge Cases

- **Agentic solution deleted:** its memberships are removed. Its agents remain in the registry, and an agent left in no solution shows as unassigned.
- **Agent deleted while in solutions:** it is removed from every solution. The user is told how many solutions it was part of before confirming.
- **Application reclassified from "agentic" to another type while it still has agents:** the change is rejected until its agents are removed (decided in Clarifications, Q1).
- **Agent with no model information** (for example, still being designed): allowed. Model provider, model and version are optional, while autonomy level and approval policy are required (every agent must state them).
- **Two agents with the same name:** allowed, since different teams may reuse names. They are distinguished by owner and identifier, not by name.
- **Cost estimates missing:** allowed. Absent estimates are shown as "not estimated", never as zero.
- **Shared agent's role:** the role is held per solution, so the same agent can be a "worker" in one solution and a "reviewer" in another.
- **Retired agent still in solutions:** allowed and shown with its retired status, because a solution may still reference an agent being phased out.

## Requirements *(mandatory)*

### Functional Requirements

**Agentic solutions**
- **FR-001**: The application type value set MUST include "agentic", alongside custom, COTS, SaaS and legacy. It MUST be selectable wherever application type is set and usable wherever applications are grouped or filtered by type.
- **FR-002**: Only applications of type "agentic" MUST be able to have agents. Agents are managed from those applications' Agents view (decided in Clarifications, Q1).

**Agent records**
- **FR-003**: Users with application-write permission MUST be able to create, view, edit and delete agents.
- **FR-004**: Each agent MUST record:
  - **Required:** name, autonomy level (0–4) and human-approval policy (none, on write actions, on irreversible actions, or always).
  - **Optional:** description, owner, lifecycle status (planned, active, sunset or retired; default active), model provider, model identifier, model version, agent framework, prompt version reference, maximum data classification handled, Agent Card URL, estimated cost per run, estimated runs per month, and external registry reference.
- **FR-005**: The system MUST present the autonomy scale with its names and meanings:

  | Level | Name | Meaning |
  |---|---|---|
  | 0 | Assistive | Suggests only; a human acts |
  | 1 | Supervised | Acts only after explicit human approval each time |
  | 2 | Conditional | Acts alone on reversible or low-risk actions and escalates the rest |
  | 3 | Bounded | Acts alone within its stated scope; reviewed after the fact |
  | 4 | Autonomous | Acts alone with monitoring only |

- **FR-006**: The prompt version reference MUST be limited to a short identifier (at most 200 characters) and labelled as a version reference, not prompt content.
- **FR-007**: The Agent Card URL MUST accept only `http`/`https` URLs, and MUST be rendered as a link only when it is one.
- **FR-008**: Cost-per-run and runs-per-month estimates MUST be non-negative when provided. Agent cost estimates MUST be visible only to users who are permitted to read application cost information, and are omitted for everyone else (decided in Clarifications, Q2).

**Solution membership**
- **FR-009**: Users MUST be able to add an existing agent to an agentic solution with a role (orchestrator, worker, reviewer or router). They MUST also be able to change its role, reorder the solution's agents, and remove an agent from a solution.
- **FR-010**: An agent MUST be able to belong to any number of solutions, holding an independent role and position in each. It MUST NOT be added to the same solution twice.
- **FR-011**: Deleting a solution MUST remove its memberships without deleting its agents. Deleting an agent MUST remove all of its memberships.

**Estate-wide view**
- **FR-012**: The system MUST provide an Agents list of every agent, filterable by autonomy level, model provider, owner and lifecycle status, and showing each agent's solution count.
- **FR-013**: An agent's detail MUST list every solution it belongs to, with its role in each.

**Platform integration**
- **FR-014**: Agents MUST be included in platform search, and kept current on create, rename/edit and delete. Existing agents MUST be included when the search index is rebuilt.
- **FR-015**: Agents and solution memberships MUST be included in the periodic machine-readable architecture export. Files for deleted agents MUST be removed. Cost estimates follow the same treatment as application cost in that export.
- **FR-016**: Every agent and membership change MUST be recorded in the audit trail with actor and time.

**Seed data**
- **FR-017**: The platform's demo/seed data MUST include ADP itself as an agentic solution with its own agents: intake extraction, recommendation, LLM-as-judge critics, chat assistant and agent review. This lets every field be demonstrated with real values.

### Key Entities

- **Agentic Solution**: an existing Application whose type is "agentic". It keeps all existing application attributes and assessments, and owns an ordered set of agent memberships.
- **Agent**: a registered AI agent, independent of any single solution. It holds identity, ownership, lifecycle, model (provider, identifier, version), framework, prompt version reference, autonomy level, human-approval policy, maximum data classification, Agent Card URL, cost estimates and an optional external registry reference.
- **Solution Membership**: the link between one agentic solution and one agent. It carries the agent's role in that solution and its position in the solution's order. It is unique per solution–agent pair.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An architect can record a solution with four agents, including every required attribute, in under 10 minutes without leaving ADP.
- **SC-002**: For any agent, a user can answer "which solutions use this agent, and in what role?" from a single screen.
- **SC-003**: A governance lead can produce the list of all agents at autonomy level 3 or above in under 30 seconds.
- **SC-004**: 100% of invalid entries (out-of-range autonomy, unknown policy or role, non-http(s) Agent Card URL, negative cost, duplicate membership) are rejected with a message naming the field, and none are partially saved.
- **SC-005**: Deleting a solution never deletes a shared agent, verified for agents shared by two or more solutions.
- **SC-006**: A newly registered agent is findable through platform search and present in the next architecture export cycle.

## Assumptions

- **Permissions:** agent writes reuse the existing application-write permission. No new role or permission is introduced, and agent reads are open like application reads, except cost estimates (FR-008).
- **Data classification** uses the same vocabulary already used for applications' data classification on the Risk & Compliance record.
- **No AI-assisted entry:** agents are entered by hand. Agent Card import is ADP-ys5.
- **Cost not in TCO yet:** agent cost estimates are recorded but not yet added to the solution's total cost of ownership. That roll-up is ADP-g58.
- **No portfolio dimensions yet:** existing portfolio screens gain "agentic" as an application-type value automatically. Agent-specific dimensions (autonomy, model provider) are ADP-g58.
- **Designs untouched:** C4 diagrams and design elements are unchanged by this feature. Linking design elements to agents is ADP-ys5.
