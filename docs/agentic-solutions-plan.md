# Capturing multi-agent (agentic) solutions in ADP

Planning document for bead **ADP-wma**. Research only, no code. It feeds a later `/speckit.specify` run for each phase below.

## 1. The problem

Every ADP layer assumes the thing that realizes a business capability is **one application**:

| Layer | Today's unit | Where |
|---|---|---|
| Portfolio | `Application` (one row: type, hosting, TIME, 7R, health, value, cost, risk, contracts, quality) | `adp.application` (ADP-SPEC-036/038, 929) |
| Realization | `application_capability_links`, `application_stage_links` | `adp.application.store` |
| Integration | `application_integrations` (app→app, API/event/file/...) | `adp.application.store` |
| Design | C4 `Element` of kind `person/system/container/component` | `adp.models.ElementKind` |
| Compliance | `ControlMapping` targets `capability/application/design/pattern/organization` | `adp.compliance` (COMPLY-02) |

An agentic solution breaks that assumption. One business outcome (for example, "resolve a customer claim") is delivered by an **orchestrator plus N specialist agents**. Each agent has its own:

- model and version;
- prompt and instructions;
- tools (often MCP servers or API wrappers around legacy applications);
- data access;
- autonomy level and human-approval points;
- evaluation evidence and run cost.

Agents are frequently **shared across solutions**, for example a "document classifier" or "policy lookup" agent. The legacy application does not disappear. It usually survives as a **system of record that agents call as a tool**.

The portfolio view stays legible if the solution is still recorded as one Application, but then none of the agent-level facts are captured.

## 2. Prior art (summary)

- **ArchiMate / TOGAF:** The Open Group has no official guidance on agents yet. Practitioner advice (BlueDolphin) varies:
  - model an agent that takes over a human function as a *business role*;
  - model the LLM as an *application component*;
  - link agents to *motivation* elements to record their purpose.

  The AEAF preprint argues that EA metamodels need an explicit "agency layer", with agents as non-human principals bound to a scope by a "charter". This is a useful idea, but it comes from a preprint.
- **A2A Agent Card** (`/.well-known/agent-card.json`): a de facto agent descriptor. Its fields are `name`, `description`, `version`, `provider`, `skills[]` (id, name, description), `capabilities` (streaming, push), input/output modes, interfaces and security schemes. ADP's agent record should be **importable from an Agent Card**, in the same way CALM patterns are importable today (ADP-SPEC-022).
- **MCP:** tools and resources are exposed by servers. This is the natural unit for an agent's "tool" dependency.
- **Agent inventories / registries** (IF4IT, Credo AI, Prefactor): they consistently track:
  - owner, authorized actions, data access, tools and permissions;
  - **autonomy classification** with oversight scaled to it (Singapore IMDA's L0–L4 scale is cited second-hand);
  - links to model, prompt and knowledge-source inventories.

  The NIST AI RMF (GV.1.6) and the EU AI Act both expect an AI system inventory. No consensus autonomy schema exists, so ADP defines its own.

## 3. Options for the core entity

| Option | Description | Verdict |
|---|---|---|
| A. Application sub-type only | Add `application_type = "agentic"`; one row per agent *or* per solution | Too flat. It cannot express composition, shared agents or topology. If one row per agent, it floods the portfolio and breaks capability roll-ups. |
| B. C4 element kind only | Add `ElementKind.AGENT` in Designs | Design-time only, with no portfolio, cost, risk or compliance. `ElementKind` is used in about 21 non-test files (CALM exporter, renderer, theme, C4 filter), so this would be a wide change for a narrow gain. |
| **C. Agentic solution = Application, agents = first-class registry** | The solution stays an `Application` (`application_type = "agentic"`) so all APM, TIME, cost, risk and capability features keep working. A new **Agent** entity holds agent-level facts, linked many-to-many to solutions. | **Recommended.** |

Why C: the portfolio keeps its unit of governance (the solution, which is what gets funded, owned and rationalized), and the agents get the depth they need. This mirrors how the repo already layers 1:1 and link tables around `applications` (risk, cost, contracts, quality, framework tags).

## 4. Recommended data model (target state)

The new package is `adp.agentic`. `adp.agents` is already taken by the internal Agent Review toolkit (039/040).

```
Application (application_type = 'agentic')   ← existing row, existing APM tables
   │  solution_agents (solution_app_id, agent_id, role: orchestrator|worker|reviewer|router, position)
   ▼
Agent ──< agent_relationships (source, target, kind: delegates_to|hands_off_to|reviews|escalates_to, solution_app_id)
   │
   ├──< agent_tools >── Tool (MCP server / API / function; kind, endpoint, auth, side_effects: read|write|irreversible)
   │                      └── tool_application_links >── Application   (legacy system of record behind the tool)
   ├──< agent_capability_links >── BusinessCapability | ValueStreamStage | ValueChainActivity  ("automates")
   └──< agent_knowledge_links >── knowledge_items / data sources
```

**`agents` columns:**
- `id`, `name`, `description`, `owner`, `lifecycle_status`;
- `model_provider`, `model_id`, `model_version`;
- `framework` (for example Claude Agent SDK, LangGraph);
- `prompt_ref` (a version pointer, not the prompt text);
- `autonomy_level` (0–4, see below);
- `human_approval` (none | on_write | on_irreversible | always);
- `data_classification_max`;
- `a2a_card_url`;
- `est_cost_per_run`, `runs_per_month`;
- timestamps.

**Autonomy scale (ADP-defined):**

| Level | Name | Meaning |
|---|---|---|
| 0 | Assistive | Suggests; a human acts. |
| 1 | Supervised | Acts after explicit human approval each time. |
| 2 | Conditional | Acts alone on reversible or low-risk actions; escalates the rest. |
| 3 | Bounded | Acts alone inside a charter; a human reviews after the fact. |
| 4 | Autonomous | Acts alone, with monitoring only. |

A **charter** is the scope statement plus allowed tools plus approval policy, taken from AEAF. It is effectively `description` + `agent_tools` + `human_approval`, so no separate table is needed at first.

**Cross-domain hooks, each reusing an existing precedent:**
- **Compliance:** add `MappingTargetType.AGENT` as a sixth `control_agent_mapping` table (COMPLY-02 shape). EU AI Act obligations attach per agent *or* per solution. `application_framework_tags` (932) already covers the solution level.
- **Risk:** the solution keeps `application_risk`. Agent-level risk is *derived*: maximum autonomy, irreversible tools, and data classification roll up to a "solution agentic risk" indicator (a pure function, like `compute_compliance_status`).
- **Cost:** a solution's TCO gains an "agent run cost" figure, the sum of `est_cost_per_run × runs_per_month` across its agents.
- **Search / chat / export:** `ENTITY_AGENT`, `ENTITY_AGENT_TOOL` and `agentic/<solution>/...` JSON files, mirroring 930/045.

**Designs (C4):** keep `ElementKind` unchanged in the first phases. An agent appears in a Design as a `container` or `component` tagged `agent` and carries an optional `agent_ref` to the registry. Whether to add a real `AGENT` kind is deferred until the registry has proven its shape.

**Diagram:** a new **`agent-topology`** diagram type on Canvas diagram-core. It is generated one-way from registry data, exactly like value stream and value chain diagrams (ADP-o9p A3/A4/A6):

| Element | Kind |
|---|---|
| Orchestrator | hexagon |
| Worker agents | rounded rectangles |
| Tools | cylinders/subroutines, with the legacy apps behind them |
| Human gates | person nodes |
| Edges | relationship kinds |

The type comes with its own `AGENT_TOPOLOGY_STANDARD` in diagram-core (a C2-style reference standard) so that `validate()` can flag, for example, "level-4 agent with an irreversible tool and no human gate".

## 5. The "traditional application → series of agents" migration

This is the case the bead calls out. To model it:

1. The legacy Application stays in the registry. Its `r_strategy` is set (usually *Refactor*/*Replace*), and its TIME quadrant moves towards *Migrate*.
2. The new agentic solution is a separate Application (`application_type = "agentic"`, `lifecycle_status = "planned"`). It is linked to the legacy app by a new `application_supersessions` link (from_app, to_app, status: planned|partial|complete).
3. As each function moves, an agent gains an `automates` link to the capability or stage that the legacy app still serves. The **overlap** (a capability realized by both the legacy app and an agent) is exactly what a capability heat map should show during transition.
4. Where the legacy app survives as a system of record, it appears behind a Tool (`tool_application_links`) rather than disappearing.
5. Transformation initiatives (APM US6 / Strategy 916) track the decomposition waves. No new mechanism is needed.

## 6. Dogfood seed

ADP is itself a multi-agent solution. It makes the obvious seed and demo data:

| Agent | Source |
|---|---|
| Intake extractor | 006 |
| Recommendation engine | 007, LangGraph |
| LLM-as-judge critics | 008, fan-out |
| Chat assistant | 041, tool-using |
| Capability / portfolio Agent Review | 039/040 |

Each already has a known model, prompts (042 prompt management), tools and approval gates (confirmation gates), so the seed exercises every field above with real data.

## 7. Phased delivery (proposed follow-on beads)

| Phase | Scope | Depends on |
|---|---|---|
| **P1 Agent registry core** | `application_type = "agentic"`; `adp.agentic` package; `agents` + `solution_agents` tables; CRUD API + UI (an "Agents" tab on an agentic Application, plus an Agents list); autonomy scale; search hook; ADP dogfood seed | – |
| **P2 Tools & topology** | `tools`, `agent_tools`, `tool_application_links`, `agent_relationships`; `agent-topology` diagram type + generator + diagram-core standard | P1, ADP-o9p A3 (diagram-type plumbing) |
| **P3 Traceability** | `agent_capability_links` (capability / stage / activity); `control_agent_mapping` (sixth COMPLY-02 target); derived agentic-risk indicator | P1; value chains (ADP-nag, done) |
| **P4 Portfolio & governance** | Group By / Filter dimensions (autonomy, model provider, framework); agent run cost in TCO; duplicate/shared-agent report; governance rule set (for example, L3+ needs eval evidence) | P1–P3 |
| **P5 Transformation & interop** | `application_supersessions`; capability overlap view; A2A Agent Card import (like CALM import); `agent_ref` on C4 elements; export + chat retrieval | P1–P3 |

P1 is useful on its own: it answers "which agents do we run, who owns them, on what model, how autonomous".

## 8. Decisions (resolved 2026-11-13)

1. **Option C confirmed:** an agentic solution is an Application (`application_type = "agentic"`), and agents live in their own registry.
2. **Shared agents:** yes. Agents relate to solutions many-to-many through `solution_agents`.
3. **Autonomy scale:** the ADP-defined 0–4 scale in section 4 is adopted.
4. **Prompts:** ADP stores a prompt **version reference** only (`prompt_ref`), never the prompt text.
5. **Runtime:** ADP is a **design-time registry**. `est_cost_per_run` / `runs_per_month` are entered estimates. A link to a runtime agent registry is a possible future addition, once one exists. P1 should make it easy to add: a nullable `external_registry_ref` and a stable agent id, so a future sync can match records without changing the schema.

## Sources

- [AEAF: Agentic Enterprise Architecture Framework (preprint)](https://www.researchsquare.com/article/rs-10943728)
- [BlueDolphin: AI and enterprise architecture, modeling the future](https://info.bluedolphin.io/blog/ai-and-enterprise-architecture-modeling-the-future)
- [A2A Agent Cards overview](https://specification.website/spec/agent-readiness/a2a-agent-cards/)
- [Google Agent Registry JSON schemas](https://docs.cloud.google.com/agent-registry/json-schemas)
- [IF4IT: Govern the inventory of AI agents](https://if4it.org/best-practices/enterprise-ai-governance-best-practices/govern-the-inventory-of-ai-agents/)
- [IF4IT: Classification attributes for the AI agents inventory](https://if4it.org/best-practices/ai-agents-inventory-and-attributes/classification-attributes-for-the-ai-agents-inventory/)
- [Bigeye: What is an agent registry](https://www.bigeye.com/blog/what-is-an-agent-registry)
- [Prefactor: What is an agent registry](https://prefactor.tech/learn/what-is-an-agent-registry)
- [Credo AI: AI agent registry](https://www.credo.ai/ai-agent-registry)
