# Data Model: Governance Reporting Dashboard (ADP-SPEC-032)

## Read-Only Report Entities (no new tables or migrations)

All governance data is derived from existing tables. No schema changes required.

---

### DesignGovernanceRecord (FR-001)

Aggregated per design from `audit_entries` + `operations` + `llm_reasoning_log` + `designs`.

| Field | Type | Source |
|---|---|---|
| design_id | string | `designs.id` |
| title | string | `designs.title` |
| lifecycle_status | string | `designs.lifecycle_status` |
| last_activity | datetime \| null | `MAX(audit_entries.timestamp)` for this design |
| audit_count | int | `COUNT(audit_entries.id)` for this design |
| accepted_recommendations | int | `COUNT WHERE action='accept-recommendation'` |
| reasoning_record_count | int | `COUNT(llm_reasoning_log.id)` via operations for this design |

**Join chain**: `designs` ← `audit_entries.design_id` | `designs` ← `operations.design_id` ← `llm_reasoning_log.operation_id`

---

### ComplianceException (FR-002)

Extracted from `ArchitectureDescription.findings[]` in design JSONB (latest version).

| Field | Type | Source |
|---|---|---|
| design_id | string | `designs.id` |
| title | string | `designs.title` |
| finding_id | string | `Finding.id` |
| finding_summary | string | `Finding.summary` |
| severity | "FAIL" \| "ADVISORY" | `Finding.severity`: `critical`→FAIL, `warning`→ADVISORY |
| source | string \| null | `Finding.source` (which critic/rule triggered it) |
| recorded_at | datetime | `designs.updated_at` (approximation for when the finding was recorded) |

**Filter**: Only include `severity IN ('warning', 'critical')` — `info` findings excluded.

---

### AuditActivityEntry (FR-003)

Direct read from `audit_entries` + `designs.title` join.

| Field | Type | Source |
|---|---|---|
| id | string | `audit_entries.id` |
| design_id | string | `audit_entries.design_id` |
| design_title | string | `designs.title` (JOIN) |
| actor | string | `audit_entries.actor` |
| action | string | `audit_entries.action` |
| affected_entity | string | `audit_entries.affected_entity` |
| summary | string | `audit_entries.summary` |
| timestamp | datetime | `audit_entries.timestamp` |
| origin | string | `audit_entries.origin` |

---

## Data Sources Summary

| Source | Used For |
|---|---|
| `audit_entries` | Activity feed, governance status (last activity, activity count, accepted recs) |
| `designs` | Governance status (lifecycle), activity feed title join |
| `design_versions.content` (JSONB) | Compliance exceptions (Finding objects) |
| `operations` | Reasoning count linkage (design_id → operation_id) |
| `llm_reasoning_log` | Reasoning record count per design |

## TypeScript Interfaces

```typescript
// web/src/api/governance.ts (new file)
interface DesignGovernanceRecord {
  design_id: string; title: string; lifecycle_status: string;
  last_activity: string | null; audit_count: number;
  accepted_recommendations: number; reasoning_record_count: number;
}
interface ComplianceException {
  design_id: string; title: string; finding_id: string;
  finding_summary: string; severity: "FAIL" | "ADVISORY";
  source: string | null; recorded_at: string;
}
interface AuditActivityEntry {
  id: string; design_id: string; design_title: string;
  actor: string; action: string; affected_entity: string;
  summary: string; timestamp: string; origin: string;
}
interface ActivityFeedResponse {
  entries: AuditActivityEntry[]; total: number; page: number; page_size: number;
  from_date: string; to_date: string;
}
```
