# Quickstart: Strategy Rollups

Manual/curl verification scenarios. Assumes a running local stack (`ADP_AUTH_ENABLED=false`, backend on
`:8001`) with a few themes, objectives across several statuses, a strategy initiative, and a mix of
linked/unlinked capabilities and value streams.

## 1. Enriched summary (User Story 3)

```bash
curl -s localhost:8001/api/v1/strategy/summary | python3 -m json.tool
# → confirm proposed_count/active_count/at_risk_count/achieved_count/abandoned_count sum to
#   total_objectives, and initiative_count matches GET /api/v1/strategy/initiatives's total
```

## 2. Strategy heat map (User Story 1)

```bash
curl -s localhost:8001/api/v1/strategy/heatmap | python3 -m json.tool
# → every theme appears exactly once, including any theme with zero objectives (all-zero row);
#   sum of every cell across every theme equals total_objectives

THEME={theme_id}
curl -s "localhost:8001/api/v1/strategy/heatmap?theme_id=$THEME" | python3 -m json.tool
# → themes list narrowed to just that one theme's row
```

## 3. Orphan report (User Story 2)

```bash
curl -s localhost:8001/api/v1/business/orphans | python3 -m json.tool
# → orphan_capabilities/orphan_value_streams list only items with zero strategic_objective_*
#   link rows; link one via POST /api/v1/strategy/objectives/{id}/capabilities and re-run --
#   that capability must disappear from the list
```

## 4. Browser walkthrough

- Open Strategy → Heat Map tab: confirm the theme × status matrix renders, and selecting a theme filter
  narrows it.
- Open Business → Capability Map: confirm an unlinked capability shows a "no strategic linkage" badge,
  and toggling the orphan filter narrows the tree to just orphaned capabilities.
- Open Business → Value Streams: confirm the same badge + filter behavior for value streams.
- Open Overview: confirm the existing Strategy card now shows the status breakdown and initiative count.
