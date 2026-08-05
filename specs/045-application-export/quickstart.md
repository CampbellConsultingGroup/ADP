# Quickstart: Continuous Application Registry Export (ADP-SPEC-045 / ADP-81p.2)

This feature has no HTTP endpoint and no UI — it's a background process, extending the same one ADP-SPEC-044 started. Verification is by configuring it, making changes through the existing API, and inspecting the resulting files.

Assumes API at `http://localhost:8001` with `ADP_AUTH_ENABLED=false`.

## Setup: enable the export

Reuses the exact same env vars as ADP-SPEC-044 — this feature does not introduce a second, separately-configured destination or interval:

```bash
export ADP_BUSINESS_ARCH_EXPORT_ROOT=/tmp/adp-arch-export
export ADP_BUSINESS_ARCH_EXPORT_INTERVAL_SECONDS=5   # short interval for local testing
# restart the API with these set
```

## Scenario 1: First-run bootstrap exports an application with all its extension records (FR-008, FR-010, FR-015–017)

```bash
APP_ID=$(curl -s -X POST http://localhost:8001/api/v1/applications \
  -H "Content-Type: application/json" \
  -d '{"name":"Claims Processing","time_classification":"Invest"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

curl -s -X PUT "http://localhost:8001/api/v1/applications/$APP_ID/risk" \
  -H "Content-Type: application/json" \
  -d '{"security_posture":"adequate","data_classification":"confidential"}' > /dev/null

curl -s -X PUT "http://localhost:8001/api/v1/applications/$APP_ID/cost" \
  -H "Content-Type: application/json" \
  -d '{"acquisition":{"one_time":"2000.50","annual":"0"}}' > /dev/null

sleep 6

cat "/tmp/adp-arch-export/applications/applications/$APP_ID.json" | python3 -m json.tool
# Expect: risk.security_posture == "adequate", cost.acquisition.one_time == "2000.50"
#         (a JSON string, not a float), governance and quality present as
#         all-null records (never omitted, never populated).
```

## Scenario 2: An application's relationships to other in-scope entities appear in its file (FR-011)

```bash
CAP_ID=$(curl -s -X POST http://localhost:8001/api/v1/business/capabilities \
  -H "Content-Type: application/json" -d '{"name":"Claims Intake","level":1}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

curl -s -X POST "http://localhost:8001/api/v1/applications/$APP_ID/capability-links" \
  -H "Content-Type: application/json" -d "{\"capability_id\": \"$CAP_ID\", \"fit_score\": 4}" > /dev/null

sleep 6
cat "/tmp/adp-arch-export/applications/applications/$APP_ID.json" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(data['linked_business_capabilities'])
"
# Expect: [{'capability_id': '<CAP_ID>', 'capability_name': 'Claims Intake', 'fit_score': 4}]
```

## Scenario 3: A transformation initiative's file shows its member applications, and vice versa (FR-013)

```bash
INITIATIVE_ID=$(curl -s -X POST http://localhost:8001/api/v1/transformation-initiatives \
  -H "Content-Type: application/json" -d '{"name":"Legacy Claims Retirement"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

curl -s -X POST "http://localhost:8001/api/v1/applications/$APP_ID/initiative-links" \
  -H "Content-Type: application/json" \
  -d "{\"initiative_id\": \"$INITIATIVE_ID\", \"planned_disposition\": \"retire\"}" > /dev/null

sleep 6

cat "/tmp/adp-arch-export/applications/transformation-initiatives/$INITIATIVE_ID.json" | python3 -m json.tool
# Expect: "members": [{"app_id": "<APP_ID>", "app_name": "Claims Processing", "planned_disposition": "retire"}]

cat "/tmp/adp-arch-export/applications/applications/$APP_ID.json" | python3 -c "
import sys, json
print(json.load(sys.stdin)['initiative_links'])
"
# Expect: [{'initiative_id': '<INITIATIVE_ID>', 'initiative_name': 'Legacy Claims Retirement', 'planned_disposition': 'retire'}]
```

## Scenario 4: An application-to-application integration gets its own file (FR-012)

```bash
APP2_ID=$(curl -s -X POST http://localhost:8001/api/v1/applications \
  -H "Content-Type: application/json" -d '{"name":"Policy Admin"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

INTG_ID=$(curl -s -X POST http://localhost:8001/api/v1/integrations \
  -H "Content-Type: application/json" \
  -d "{\"source_app_id\": \"$APP_ID\", \"target_app_id\": \"$APP2_ID\", \"integration_type\": \"API\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

sleep 6
cat "/tmp/adp-arch-export/applications/integrations/$INTG_ID.json" | python3 -m json.tool
# Expect: source_app_name == "Claims Processing", target_app_name == "Policy Admin"
```

## Scenario 5: Deleting an application removes its file and its integration record (FR-004, Edge Case)

```bash
curl -s -o /dev/null -X DELETE "http://localhost:8001/api/v1/applications/$APP_ID"
sleep 6

test -f "/tmp/adp-arch-export/applications/applications/$APP_ID.json" \
  && echo "FAIL: orphaned application file left behind" \
  || echo "OK: application file removed"
```

## Scenario 6: An unchanged application's file is not rewritten (FR-009)

```bash
STAT_BEFORE=$(stat -c %Y "/tmp/adp-arch-export/applications/technical-capabilities/$TC_ID.json" 2>/dev/null || echo none)
sleep 6
STAT_AFTER=$(stat -c %Y "/tmp/adp-arch-export/applications/technical-capabilities/$TC_ID.json" 2>/dev/null || echo none)

[ "$STAT_BEFORE" == "$STAT_AFTER" ] && echo "OK: file untouched" || echo "FAIL: file rewritten with no data change"
```
