# Data Model: Agent Traceability (944)

## New tables (migration `052`, `down_revision = "051"`)

### `agent_capability_links`
| Column | Type | Rule |
|---|---|---|
| agent_id | String(36) | PK, FK → agents.id CASCADE |
| capability_id | String(36) | PK, FK → business_capabilities.id CASCADE; index `ix_agent_capability_links_capability_id` |
| created_at | timestamptz | not null |

The capability must be level 3, checked in the store (`LevelRuleError`).

### `agent_stage_links`
| Column | Type | Rule |
|---|---|---|
| agent_id | String(36) | PK, FK → agents.id CASCADE |
| stage_id | String(36) | PK, FK → value_stream_stages.id CASCADE; index `ix_agent_stage_links_stage_id` |
| created_at | timestamptz | not null |

### `agent_activity_links`
| Column | Type | Rule |
|---|---|---|
| agent_id | String(36) | PK, FK → agents.id CASCADE |
| activity_id | String(36) | PK, FK → value_chain_activities.id CASCADE; index `ix_agent_activity_links_activity_id` |
| created_at | timestamptz | not null |

### `control_agent_mapping` (the COMPLY-02 shape)
| Column | Type | Rule |
|---|---|---|
| control_id | String(36) | PK, FK → controls.id CASCADE |
| agent_id | String(36) | PK, FK → agents.id CASCADE; index `ix_control_agent_mapping_agent_id` |
| compliance_status | TEXT | not null; CHECK `ck_control_agent_mapping_status` (the five statuses) |
| evidence_ref | TEXT | null |
| assessed_at | DATE | null |
| assessed_by | TEXT | null |
| created_at | timestamptz | not null |

**In SQLAlchemy metadata**, the link tables and `control_agent_mapping` declare plain columns with no `ForeignKey`. The FKs exist only in the migration (research R1/R4).

**Deletes**: the store functions delete the rows explicitly, so SQLite behaves the same as Postgres. The CASCADEs are a safety net.
- `delete_agent` deletes the agent's link rows.
- The `adp.compliance` side deletes `control_agent_mapping` rows when a control is deleted. When an agent is deleted, Postgres CASCADE removes its mappings. On SQLite, reads inner-join the `agents` mirror, so dangling rows never surface.

## Changed enum

`MappingTargetType` gains `AGENT = "agent"` in the backend and in `web/src/api/compliance.ts`. Initiative linkage stays at five types (research R6).

## Derived (never stored)

```text
RiskFactor            code: autonomy | no_human_approval | sensitive_data, label: str
AgenticRisk           band: high | medium | low
                      factors: RiskFactor[]                  (only those that set the band)
                      missing: ["data_classification"]?      (when the classification is null)
                      not_considered: ["tool_side_effects"]   (always, until P2)
SolutionAgenticRisk   band: high | medium | low | null        (null = "No agents")
                      agents: [{id, name}]                    (non-retired agents at that band)
                      not_considered: ["tool_side_effects"]

Agent (read, +)                 agentic_risk: AgenticRisk
SolutionAgentListResponse (+)   solution_risk: SolutionAgenticRisk

AutomatesCapability   id, name, level (3), path: [L1 name, L2 name]
AutomatesStage        id, name, value_stream_id, value_stream_name
AutomatesActivity     id, name, category (primary|support), value_chain_id, value_chain_name
AgentAutomates        capabilities[], stages[], activities[]

AgentSummary (reverse lookups)  id, name, lifecycle_status, autonomy_level, agentic_risk

AgentComplianceMappings   items: ControlMapping[], total, status: ComplianceStatus
AgentComplianceStatuses   items: [{agent_id, status}]
```

## Rules

- **Band** (FR-013). `sensitive` = data classification confidential or restricted:
  - **high**: autonomy ≥ 3 and (approval none or sensitive);
  - **medium**: otherwise, autonomy ≥ 2 or sensitive;
  - **low**: everything else.
- **Factors**, by band:
  - high lists `autonomy` and whichever of `no_human_approval` / `sensitive_data` hold;
  - medium lists `autonomy` when it is ≥ 2, and `sensitive_data` when it holds;
  - low lists none.
- **Solution band**: the maximum over members whose lifecycle isn't `retired`. Planned and sunset members count.
- **Agent compliance status**: `compute_compliance_status` over the agent's mappings. With no mappings it is `not_assessed`. It never feeds the solution's own status (FR-009a).
- **Ordering**:
  - capabilities by path, then name;
  - stages by value stream name, then stage position;
  - activities by value chain name, then category (primary first), then position;
  - reverse lookups by agent name.
