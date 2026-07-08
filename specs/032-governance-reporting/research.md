# Research: Governance Reporting Dashboard (ADP-SPEC-032)

## Decision 1: Design Governance Status — Data Sources and Join Strategy (FR-001)

**Decision**: The governance status report joins three tables per design:
1. `audit_entries` (WHERE `design_id = ?`) — `MAX(timestamp)` for last activity, `COUNT(*)` for total activity, `COUNT(*) WHERE action = 'accept-recommendation'` for accepted recommendations
2. `llm_reasoning_log` (WHERE `operation_id` IN operations for this design) — `COUNT(*)` for reasoning records
3. `designs` (WHERE `id = ?`) — lifecycle_status for current status badge

The `llm_reasoning_log` links to designs via the `operations` table (which has `design_id`). The join chain is: `llm_reasoning_log.operation_id → operations.id → operations.design_id`.

**SQL approach**: For a portfolio of N designs, issue a single aggregating query rather than N+1 queries:
```sql
SELECT 
  d.id, d.title, d.lifecycle_status,
  MAX(ae.timestamp) AS last_activity,
  COUNT(ae.id) AS audit_count,
  COUNT(CASE WHEN ae.action = 'accept-recommendation' THEN 1 END) AS accepted_recs,
  COUNT(DISTINCT lrl.id) AS reasoning_count
FROM designs d
LEFT JOIN audit_entries ae ON ae.design_id = d.id
LEFT JOIN operations op ON op.design_id = d.id
LEFT JOIN llm_reasoning_log lrl ON lrl.operation_id = op.id
GROUP BY d.id, d.title, d.lifecycle_status
ORDER BY MAX(ae.timestamp) DESC NULLS LAST
```

**Rationale**: Single aggregating query is faster than per-design queries for N>5 designs. `LEFT JOIN` ensures designs with zero activity still appear.

**Verdict data**: The spec mentions "validation verdict counts" but the current codebase stores verdicts inside design JSONB, not in a separate table. The `audit_entries` table has `action='validate'` entries. For v1, the governance status will count audit entries with action `'validate'` as proxy for reviews. The spec assumption that verdict sourcing comes from audit_entries is validated.

**Alternatives considered**: Scanning design JSONB for verdicts — rejected because it requires full JSONB scan and cannot be aggregated in a single JOIN query.

## Decision 2: Compliance Exceptions — Source of FAIL/ADVISORY Findings (FR-002)

**Decision**: Read validation findings from the design JSONB content (`design_versions.content`). The existing `Finding` model (stored in `ArchitectureDescription.findings[]`) has `severity: "info" | "warning" | "critical"`. Map: `critical` → FAIL, `warning` → ADVISORY.

**Rationale**: The LLM-as-a-Judge layer (ADP-SPEC-008) writes findings into the design's canonical model. They are stored in the JSONB content. For compliance exceptions, we scan the latest version of each design and extract `findings` where `severity IN ('warning', 'critical')`.

**Implementation note**: This requires loading `ArchitectureDescription` for each design and reading `.findings`. For a portfolio of 100 designs this is acceptable at initial load; results cached by the client (staleTime: 5 minutes).

**Alternatives considered**: Creating a separate findings index table — out of scope for this spec; that would be a future optimization.

## Decision 3: Activity Feed — Query Design (FR-003)

**Decision**: Query `audit_entries` directly with `WHERE timestamp BETWEEN :from_date AND :to_date AND (:action_type IS NULL OR action = :action_type)`. Join `designs.title` for the design name. Paginate with OFFSET/LIMIT. The 90-day window is enforced at the API layer.

**SQL**:
```sql
SELECT ae.*, d.title AS design_title
FROM audit_entries ae
JOIN designs d ON d.id = ae.design_id
WHERE ae.timestamp BETWEEN :from_date AND :to_date
  AND (:action IS NULL OR ae.action = :action)
ORDER BY ae.timestamp DESC
LIMIT :limit OFFSET :offset
```

**Rationale**: `audit_entries.timestamp` is not indexed in the current schema. For 100 designs with 12 months of history (~12 entries/design = 1,200 rows), a full scan is acceptable. If the portfolio grows to 1,000+ designs, an index on `(design_id, timestamp)` should be added — noted as a future optimization.

## Decision 4: CSV Export (FR-004)

**Decision**: Same query as FR-003 without pagination. FastAPI returns a `StreamingResponse` with `Content-Type: text/csv` and `Content-Disposition: attachment`. The frontend triggers download via an anchor click (same pattern as CALM export in ADP-SPEC-021).

**90-day enforcement**: If `to_date - from_date > 90 days`, return 422. Computed server-side.

## Decision 5: Action Type Values for Filters

**Decision**: The action type filter dropdown will use the actual string values from `audit_entries.action`. Discovered from codebase scan:
- `design-created`, `lifecycle-transition`, `accept-recommendation`, `reject-requirement-proposal`, `confirm-requirement`, `add-requirement`, `update-element-technology-tags`, `calm-export`, `validate`

These are passed as exact-match filter values.

## Decision 6: Governance Screen Navigation — From Portfolio, Not Main Nav

**Decision**: The Governance screen is accessed via a "Governance" button on the Portfolio screen (ADP-SPEC-031). It is NOT a sixth item in the main `NavBar`. This keeps the main nav to five items (Designs, Intake, Recommendations, Canvas, Knowledge, Portfolio).

**Implementation**: `PortfolioPage.tsx` includes a "Governance Report" button/link that sets `view = "governance"` in App.tsx state. The governance router (`GovernancePage.tsx`) includes a "← Portfolio" back button.

## Decision 7: No New Tables or Migrations

**Decision**: Zero schema changes. All data is read from existing tables.

## Decision 8: Zero New Python Packages

**Decision**: Python `csv` module (stdlib) for CSV generation. No new dependencies.
