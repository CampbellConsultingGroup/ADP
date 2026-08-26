# Quickstart: Application Type Grouping Dimension

Verifies the feature end-to-end against a real running backend (`uvicorn adp.api.app:app`) and a
real local Postgres with migration `039` applied.

## Scenario 1: Create an application with a type, confirm round-trip

```bash
APP_ID=$(curl -s -X POST http://localhost:8001/api/v1/applications \
  -H "Content-Type: application/json" \
  -d '{"name":"Claims Legacy Mainframe","application_type":"legacy"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

curl -s http://localhost:8001/api/v1/applications/$APP_ID | python3 -m json.tool
# Expect "application_type": "legacy"
```

## Scenario 2: Invalid value rejected with 422

```bash
curl -s -X POST http://localhost:8001/api/v1/applications \
  -H "Content-Type: application/json" \
  -d '{"name":"Bad Type Test","application_type":"opensource"}' \
  -w "\nHTTP:%{http_code}\n"
# Expect HTTP:422
```

## Scenario 3: Update clears the value with an explicit null

```bash
curl -s -X PATCH http://localhost:8001/api/v1/applications/$APP_ID \
  -H "Content-Type: application/json" -d '{"application_type":null}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['application_type'])"
# Expect: None
```

## Scenario 4: Filter query param

```bash
curl -s -X PATCH http://localhost:8001/api/v1/applications/$APP_ID \
  -H "Content-Type: application/json" -d '{"application_type":"cots"}' > /dev/null

curl -s "http://localhost:8001/api/v1/applications?application_type=cots" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print([a['id'] for a in d['items']])"
# Expect the list to include APP_ID
```

## Scenario 5: Portfolio screen grouping dimension (frontend, manual/Playwright)

1. Open the Application Portfolio screen.
2. Select "Application Type" in the Group By dropdown.
3. Confirm 4 ordered buckets (Custom-Built, COTS, SaaS, Legacy/Mainframe) plus a trailing
   "Unclassified" bucket for any application with no type set.
4. Select "Application Type" in both Group By and Then By — confirm it reverts to the flat
   single-axis view (same-dimension rule, unchanged from ADP-3wa).
5. Select "Application Type" in Filter by, pick "COTS" — confirm only COTS-typed applications
   remain, composing correctly with any active Group By.

## Cleanup

```bash
curl -s -X DELETE http://localhost:8001/api/v1/applications/$APP_ID -w "\nHTTP:%{http_code}\n"
```
