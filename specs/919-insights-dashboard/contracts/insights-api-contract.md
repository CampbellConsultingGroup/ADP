# API Contract: Insights Dashboard — Applications Heat Map

## Applications heat map (new, `src/adp/api/routers/portfolio.py`)

| Method | Path | Success | Errors |
|---|---|---|---|
| `GET` | `/api/v1/portfolio/applications-heatmap` | `200` — `ApplicationHeatmapResponse` | — (no permission-based 403; cost gating is field-level, see below) |

```json
{
  "items": [
    {
      "id": "app-01",
      "name": "Policy Admin System",
      "health_score": 4,
      "business_criticality": 5,
      "time_classification": "Invest",
      "cost": 1250000.00
    },
    {
      "id": "app-02",
      "name": "Legacy Claims Batch",
      "health_score": null,
      "business_criticality": 2,
      "time_classification": "Eliminate",
      "cost": null
    }
  ],
  "cost_permitted": true
}
```

When the caller does not hold `READ_APPLICATION_COST`: every entry's `cost` is `null` and the top-level
`cost_permitted` is `false` — the frontend uses this single flag to omit "cost" from the dimension selector
entirely (FR-004), never to distinguish "no cost data" from "no permission" at the per-entry level.

## Permissions

- No route-level gate — every authenticated user can call this endpoint (three of its four dimensions are
  already open reads today, per Ground-Truth Correction 3).
- The `cost`/`cost_permitted` fields are computed per request from `is_permitted(user.role,
  ActionType.READ_APPLICATION_COST)` (Decision 2, `research.md`) — the same permission the existing
  single-application cost endpoint (`application/router.py`'s `_require_cost_read`) already enforces, applied
  here as an inline field-level check rather than a route-level 403.
