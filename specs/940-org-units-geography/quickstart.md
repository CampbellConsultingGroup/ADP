# Quickstart: Org Units and Geography (940)

Prerequisites:
- `alembic upgrade head` (048) on local Postgres (5433);
- the API on :8001 and Vite on :5173.

```bash
B=http://localhost:8001/api/v1/business
```

## 1. Geography is seeded (US2)
```bash
curl -s $B/geographies | python3 -c "import sys,json;d=json.load(sys.stdin)['items'];print(len(d));print([g['path'] for g in d if g['code']=='DE'])"
```
Expect about 255 rows, and Germany under Global › Europe.

## 2. Build the org tree (US1)
```bash
RC=$(curl -s -X POST $B/org-units -H 'content-type: application/json' -d '{"name":"Retail Co"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")
ST=$(curl -s -X POST $B/org-units -H 'content-type: application/json' -d "{\"name\":\"Stores\",\"parent_id\":\"$RC\"}" | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")
curl -s -X POST $B/org-units -H 'content-type: application/json' -d "{\"name\":\"stores\",\"parent_id\":\"$RC\"}" -o /dev/null -w "%{http_code}\n"   # 409
```

## 3. Operating geographies (US3)
```bash
curl -s -X POST $B/org-units/$ST/geographies -H 'content-type: application/json' -d '{"geography_id":"geo-DE"}' -o /dev/null -w "%{http_code}\n"  # 201
curl -s $B/geographies/geo-DE/org-units | python3 -m json.tool
```

## 4. Review queue (US4)
Set `owning_business_unit` on a few applications (PATCH), then:
```bash
curl -s $B/org-units/unmatched | python3 -m json.tool
curl -s -X POST $B/org-units/unmatched/resolve -H 'content-type: application/json' -d "{\"value\":\"Store Systems\",\"org_unit_id\":\"$ST\"}"
```
Expect `updated_count` equal to that value's count, the value gone from the list, and the applications' `owning_business_unit` unchanged.

## 5. UI (US1–US5)
- Business Architecture → **Organization**: the Org Units tree, Geography tree and Unmatched list.
- The application form's **Owning org unit** picker.
- Portfolio → group by Ownership / Business Unit: linked applications under the org unit; others "… (unmatched)".

Clean up scratch org units and links afterwards. Seeded geographies stay.
