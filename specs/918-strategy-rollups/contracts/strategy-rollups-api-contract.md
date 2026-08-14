# API Contract: Strategy Rollups

## Enriched summary (`src/adp/strategy/router.py`)

| Method | Path | Success | Notes |
|---|---|---|---|
| `GET` | `/api/v1/strategy/summary` | `200` — `StrategicSummaryResponse` | Same path, same 7 existing fields, plus 6 new: `proposed_count`, `active_count`, `at_risk_count`, `achieved_count`, `abandoned_count`, `initiative_count`. Purely additive — no client migration required. |

## Strategy heat map (new)

| Method | Path | Success | Errors |
|---|---|---|---|
| `GET` | `/api/v1/strategy/heatmap` | `200` — `StrategyHeatMapResponse` | — |
| `GET` | `/api/v1/strategy/heatmap?theme_id={id}` | `200` — same shape, `themes` narrowed to the one matching theme (empty list if `theme_id` doesn't exist) | — |

```json
{
  "themes": [
    {
      "theme_id": "...", "theme_name": "Growth",
      "proposed_count": 2, "active_count": 5, "at_risk_count": 1,
      "achieved_count": 3, "abandoned_count": 0
    }
  ],
  "total_objectives": 11
}
```

## Orphan report (new, `src/adp/business/router.py`)

| Method | Path | Success | Errors |
|---|---|---|---|
| `GET` | `/api/v1/business/orphans` | `200` — `OrphanReportResponse` | — |

```json
{
  "orphan_capabilities": [ /* full BusinessCapability objects, id/name/level/... */ ],
  "orphan_value_streams": [ /* full ValueStream objects */ ]
}
```

## Permissions

All three endpoints are ungated reads — no `ActionType`, consistent with every other rollup/aggregate
endpoint already in this codebase (spec.md FR-008).
