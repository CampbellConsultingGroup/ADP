# Quickstart: Insights Dashboard — Applications Heat Map

Manual/curl verification scenarios. Assumes a running local stack (`ADP_AUTH_ENABLED=false`, backend on
`:8001`, frontend on `:5173`) with the seeded retail application set (`scripts/seed_retail.py`).

## 1. Applications heat map, all-open dimensions (User Story 1)

```bash
curl -s localhost:8001/api/v1/portfolio/applications-heatmap | python3 -m json.tool
# → every seeded application appears exactly once in "items"; health_score/business_criticality/
#   time_classification are populated where assessed, null where not (never a false default)
```

## 2. Cost gating (User Story 2, FR-004)

```bash
# Under ADP_AUTH_ENABLED=false the dev caller is ENTERPRISE_ARCHITECT, which holds every action —
# confirm cost_permitted is true and cost values are populated for apps with a cost record:
curl -s localhost:8001/api/v1/portfolio/applications-heatmap | python3 -c \
  "import json,sys; d=json.load(sys.stdin); print(d['cost_permitted'], [i['cost'] for i in d['items']])"

# To exercise the denied path, run the same request as a role without READ_APPLICATION_COST
# (e.g. with ADP_AUTH_ENABLED=true and a token for a non-architect persona) and confirm every
# item's "cost" is null and "cost_permitted" is false.
```

## 3. Browser walkthrough

- Confirm a new top-level nav entry (sibling to Overview, not under Architecture) opens the dashboard
  (User Story 3).
- Confirm the heat map renders one cell per seeded application, colored by health score by default.
- Switch the dimension selector through business criticality and TIME classification: cells recolor in
  place, no navigation, no visible network delay.
- If the logged-in persona holds `READ_APPLICATION_COST`: confirm "cost" appears as a selectable dimension
  and recolors correctly; if not, confirm it is absent from the selector entirely.
- Confirm an application with no value for the selected dimension renders as a distinct "unclassified" cell,
  never colored the same as an actual low/high value.
