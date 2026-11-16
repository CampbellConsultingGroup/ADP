# Quickstart: Regional Assessments (942)

Prerequisites:
- `alembic upgrade head` (050) on local Postgres (5433);
- the API on :8001 and Vite on :5173;
- an existing L3 business capability. Create a scratch L3 and use it for region scope, and delete it afterwards.

```bash
B=http://localhost:8001/api/v1/business
J='content-type: application/json'
# set CAP (capability id) and SCRATCH (a scratch L3 id)
```

## 1. Assess by region (US1)
```bash
curl -s -X PUT $B/regional-assessments/$CAP/geo-m49-150 -H "$J" -d '{"maturity_level":4}' | python3 -m json.tool
curl -s -X PUT $B/regional-assessments/$CAP/geo-BR -H "$J" -d '{"maturity_level":2,"note":"eSocial reporting is manual"}' -o /dev/null -w "%{http_code}\n"  # 200
curl -s -X PUT $B/regional-assessments/$CAP/geo-m49-150 -H "$J" -d '{"maturity_level":5}' -o /dev/null -w "%{http_code}\n"  # 200, same row
curl -s -X PUT $B/regional-assessments/$CAP/geo-001 -H "$J" -d '{"maturity_level":3}' -w " %{http_code}\n"   # 422 Global
curl -s -X PUT $B/regional-assessments/$CAP/geo-DE -H "$J" -d '{}' -w " %{http_code}\n"                       # 422 empty
curl -s "$B/regional-assessments?capability_id=$CAP" | python3 -c "import sys,json;print(json.load(sys.stdin)['total'])"  # 2
curl -s $B/capabilities/$CAP | python3 -c "import sys,json;print(json.load(sys.stdin)['maturity_level'])"  # unchanged baseline
```

## 2. Region-specific scope (US2)
```bash
curl -s -X PUT $B/capability-region-scope/$SCRATCH -H "$J" -d '{"region_specific":true,"geography_ids":["geo-BR"]}' | python3 -m json.tool
curl -s -X PUT $B/capability-region-scope/$SCRATCH -H "$J" -d '{"region_specific":true,"geography_ids":[]}' -w " %{http_code}\n"  # 422
```

## 3. Heat map (US3)
```bash
curl -s "$B/regional-heatmap" | python3 -c "import sys,json;d=json.load(sys.stdin);print([c['name'] for c in d['columns']])"   # 5 regions
curl -s "$B/regional-heatmap?geography_ids=geo-m49-019,geo-m49-150,geo-BR,geo-DE" | python3 -c "
import sys,json;d=json.load(sys.stdin)
for r in d['rows']:
    if r['capability']['id'] in ('$CAP','$SCRATCH'): print(r['capability']['name'], r['baseline'], [(c['state'], c['maturity_level'], c['delta']) for c in r['cells']])"
```
Expect:
- CAP is assessed in Europe (5, delta vs baseline) and Brazil (2, with a note), and not assessed elsewhere;
- SCRATCH is applicable in the Americas and Brazil (not assessed), and not applicable in Europe and Germany.

## 4. Deletes
- Delete a scratch country used in a scope: the scope shows `scope_needs_update`.
- Delete the scratch capability: its assessments and scope go too.

## 5. UI (Playwright)
- Heat Map → Regional: baseline column plus regions; add Brazil and Germany columns; the choice survives a tab switch.
- Click a cell to record a score and note; hover shows the note; ▲/▼ shows against the baseline.
- Capabilities → a row's Regions expander lists and edits assessments and the region-specific scope.

Clean up all scratch data afterwards.
