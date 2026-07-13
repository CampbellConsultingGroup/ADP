# Data Model: Design Lifecycle Management (ADP-SPEC-030)

## Extended: `ArchitectureDescription` (Pydantic model — in JSONB)

Five new optional fields added to the canonical model. Backward compatible — existing designs in JSONB load with `None` defaults for all lifecycle fields.

| Field | Type | Default | Notes |
|---|---|---|---|
| lifecycle_status | `LifecycleStatus` enum | `"draft"` | One of: draft, proposed, current, deprecated, decommissioned |
| proposed_date | `datetime \| None` | `None` | When the design was first submitted for governance |
| current_since | `datetime \| None` | `None` | When the design entered Current status |
| review_due | `datetime \| None` | `None` | Scheduled date for next architecture review |
| retirement_date | `datetime \| None` | `None` | When the design was or will be decommissioned |

**New: `LifecycleStatus` (StrEnum)**

```
draft         → initial state; work in progress
proposed      → formally submitted for governance
current       → approved active system or pattern
deprecated    → superseded or scheduled for replacement
decommissioned → retired; no longer operates
```

## Extended: `designs` Table (indexed columns — derived from canonical model)

New columns added via Alembic migration. These mirror the `ArchitectureDescription` lifecycle fields for fast portfolio queries without parsing JSONB.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| lifecycle_status | TEXT | NOT NULL DEFAULT 'draft' | B-tree indexed |
| proposed_date | TIMESTAMPTZ | nullable | |
| current_since | TIMESTAMPTZ | nullable | |
| review_due | TIMESTAMPTZ | nullable | B-tree indexed (for overdue queries) |
| retirement_date | TIMESTAMPTZ | nullable | |

**Indexes**:
- B-tree on `lifecycle_status` — `WHERE lifecycle_status = 'current'` in list queries (SC-002)
- B-tree on `review_due` — `WHERE review_due < now() AND lifecycle_status = 'current'` for overdue indicator (SC-004)

## Transition Graph (FR-004)

```
         ┌──────────────────────────────────────────────┐
         │  Reset to Draft (any → draft, with confirm)  │
         └──────────────────────────────────────────────┘
              ↓
   draft ──→ proposed ──→ current ──→ deprecated ──→ decommissioned
              ↑__________↗                  ↑_________↗
              (rejection/    (reinstatement from deprecated)
               rework)
```

Implemented as a Python dict in the transition endpoint:
```python
VALID_TRANSITIONS = {
    "draft":          {"proposed"},
    "proposed":       {"current", "draft"},
    "current":        {"deprecated"},
    "deprecated":     {"decommissioned", "current"},
    "decommissioned": set(),          # terminal (except reset)
}
# "Reset to Draft" is always valid from any non-draft status (with confirmation flag)
```

## Auto-Date Rules (FR-005)

| Transition | Auto-set field | Condition |
|---|---|---|
| Any → Proposed | `proposed_date` | Only if `proposed_date` is currently None |
| Any → Current | `current_since` | Only if `current_since` is currently None |
| Any → Decommissioned | `retirement_date` | Only if `retirement_date` is currently None |

`review_due` is never auto-set — it requires explicit architect input.
