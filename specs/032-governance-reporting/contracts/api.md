# API Contracts: Governance Reporting Dashboard (ADP-SPEC-032)

All endpoints are read-only. No schema migrations required.

---

## GET /api/v1/governance/status

Per-design governance summary. Aggregates audit and reasoning data.

**Auth**: Bearer token required.

**Response 200**:
```json
{
  "designs": [
    {
      "design_id": "DSN-001",
      "title": "Payment Platform",
      "lifecycle_status": "current",
      "last_activity": "2026-07-04T14:30:00Z",
      "audit_count": 12,
      "accepted_recommendations": 3,
      "reasoning_record_count": 9
    }
  ],
  "total": 5
}
```

**Notes**: Sorted by `last_activity` descending (NULL last). Designs with zero activity still included (zero counts).

---

## GET /api/v1/governance/exceptions

Compliance exceptions — only FAIL and ADVISORY validation findings.

**Auth**: Bearer token required.

**Response 200**:
```json
{
  "exceptions": [
    {
      "design_id": "DSN-003",
      "title": "Legacy Auth Platform",
      "finding_id": "FND-002",
      "finding_summary": "Design violates Zero Trust Security principle: no mTLS between services",
      "severity": "FAIL",
      "source": "security-critic",
      "recorded_at": "2026-06-15T09:00:00Z"
    }
  ],
  "total": 4
}
```

**Notes**: Sorted by severity (FAIL first) then `recorded_at` descending. PASS/INFO findings excluded.

---

## GET /api/v1/governance/activity

Paginated audit log across all designs.

**Auth**: Bearer token required.

**Query parameters**:
- `from_date` (required, ISO 8601 date): start of date range
- `to_date` (required, ISO 8601 date): end of date range — maximum 90-day window from `from_date`
- `action` (optional): filter to specific action string (e.g. `lifecycle-transition`)
- `actor` (optional): filter by actor username
- `page` (optional, default 1)
- `page_size` (optional, default 50, max 200)

**Response 200**:
```json
{
  "entries": [
    {
      "id": "AUD-001",
      "design_id": "DSN-001",
      "design_title": "Payment Platform",
      "actor": "alice",
      "action": "lifecycle-transition",
      "affected_entity": "DSN-001",
      "summary": "Lifecycle: draft → proposed",
      "timestamp": "2026-07-04T14:30:00Z",
      "origin": "human"
    }
  ],
  "total": 47,
  "page": 1,
  "page_size": 50,
  "from_date": "2026-06-04",
  "to_date": "2026-07-04"
}
```

**Response 422**: Date range exceeds 90 days, or `from_date` / `to_date` missing or invalid.

---

## GET /api/v1/governance/activity/export

CSV export of filtered audit entries. Same filters as `/activity` but returns all matching rows (not paginated), bounded by the 90-day window.

**Auth**: Bearer token required.

**Query parameters**: Same as `/activity` (except no `page`/`page_size`).

**Response 200**:
- `Content-Type: text/csv`
- `Content-Disposition: attachment; filename="adp-audit-{from_date}-{to_date}.csv"`

**CSV columns**: `id`, `design_id`, `design_title`, `actor`, `action`, `affected_entity`, `summary`, `timestamp`, `origin`

**Response 422**: Date range exceeds 90 days or dates missing.

---

## Available Action Types (for filter dropdown)

Discovered from codebase (`audit_entries.action` values):

| Action | Description |
|---|---|
| `design-created` | New design created |
| `lifecycle-transition` | Design lifecycle status changed (ADP-SPEC-030) |
| `accept-recommendation` | AI recommendation accepted |
| `reject-requirement-proposal` | Requirement proposal rejected |
| `confirm-requirement` | Requirement proposal confirmed |
| `add-requirement` | Requirement added directly |
| `update-element-technology-tags` | Element technology metadata updated (ADP-SPEC-029) |
| `calm-export` | Design exported as CALM document |
| `validate` | Design validated by LLM-as-a-Judge |
