# Quickstart: Continuous Strategy Domain Export (ADP-81p.3)

This feature has no HTTP endpoint and no UI — it's a background process, extending the same one ADP-SPEC-044/045 started. Verification is by configuring it, making changes through the existing API, and inspecting the resulting files.

Assumes API at `http://localhost:8001` with `ADP_AUTH_ENABLED=false`.

## Setup: enable the export

Reuses the exact same env vars as ADP-SPEC-044/045 — this feature does not introduce a third, separately-configured destination or interval:

```bash
export ADP_BUSINESS_ARCH_EXPORT_ROOT=/tmp/adp-arch-export
export ADP_BUSINESS_ARCH_EXPORT_INTERVAL_SECONDS=5   # short interval for local testing
# restart the API with these set
```

## Scenario 1: A theme, objective, and its progress history export correctly (FR-001, FR-011, FR-012)

```bash
THEME_ID=$(curl -s -X POST http://localhost:8001/api/v1/strategy/themes \
  -H "Content-Type: application/json" -d '{"name":"Operational Excellence"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

OBJ_ID=$(curl -s -X POST http://localhost:8001/api/v1/strategy/objectives \
  -H "Content-Type: application/json" \
  -d "{\"theme_id\":\"$THEME_ID\",\"owner\":\"Alice\",\"statement\":\"Cut incident MTTR\",\"metric_name\":\"MTTR (hrs)\",\"target_value\":2,\"target_unit\":\"hours\",\"direction\":\"decrease\",\"fiscal_year\":2026,\"period\":\"Q1\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

curl -s -X POST "http://localhost:8001/api/v1/strategy/objectives/$OBJ_ID/progress" \
  -H "Content-Type: application/json" \
  -d '{"as_of_date":"2026-02-01","actual_value":6}' > /dev/null

sleep 6

cat "/tmp/adp-arch-export/strategy/objectives/$OBJ_ID.json" | python3 -m json.tool
# Expect: theme_id == THEME_ID, metric fields all set, status computed (not null/omitted),
#         progress == [{"as_of_date":"2026-02-01","actual_value":"6", ...}] (a JSON string).
```

## Scenario 2: Objective dependencies export in both directions (FR-013)

```bash
OBJ_ID_2=$(curl -s -X POST http://localhost:8001/api/v1/strategy/objectives \
  -H "Content-Type: application/json" \
  -d "{\"theme_id\":\"$THEME_ID\",\"owner\":\"Bob\",\"statement\":\"Reduce alert noise\",\"fiscal_year\":2026,\"period\":\"Q1\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

curl -s -X POST "http://localhost:8001/api/v1/strategy/objectives/$OBJ_ID/depends-on" \
  -H "Content-Type: application/json" -d "{\"depends_on_objective_id\":\"$OBJ_ID_2\"}" > /dev/null

sleep 6

python3 -c "
import json
a = json.load(open('/tmp/adp-arch-export/strategy/objectives/$OBJ_ID.json'))
b = json.load(open('/tmp/adp-arch-export/strategy/objectives/$OBJ_ID_2.json'))
assert a['depends_on_objective_ids'] == ['$OBJ_ID_2']
assert b['blocked_objective_ids'] == ['$OBJ_ID']
print('OK: both directions of the dependency exported correctly')
"
```

## Scenario 3: A strategy initiative's objective link and live compliance-mapping status export correctly (FR-014, FR-015)

```bash
INIT_ID=$(curl -s -X POST http://localhost:8001/api/v1/strategy/initiatives \
  -H "Content-Type: application/json" -d '{"name":"Remediate MFA gap"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

curl -s -X POST "http://localhost:8001/api/v1/strategy/initiatives/$INIT_ID/objectives/$OBJ_ID" > /dev/null

sleep 6

python3 -c "
import json
init = json.load(open('/tmp/adp-arch-export/strategy/initiatives/$INIT_ID.json'))
obj = json.load(open('/tmp/adp-arch-export/strategy/objectives/$OBJ_ID.json'))
assert init['objective_ids'] == ['$OBJ_ID']
assert '$INIT_ID' in obj['initiative_ids']
print('OK: both directions of the initiative-objective link exported correctly')
"
```

*(A full compliance-mapping live-status check requires a seeded `RegulatoryFramework`/`Control`/`ControlMapping` — covered by the integration test against a real Postgres container, mirroring `test_strategy_compliance_links_api.py`'s own fixture precedent, rather than a curl-only quickstart step here.)*

## Scenario 4: Deleting an objective removes its file and any dependent link data (FR-004, Edge Cases)

```bash
curl -s -X DELETE "http://localhost:8001/api/v1/strategy/objectives/$OBJ_ID_2" > /dev/null
sleep 6
test ! -f "/tmp/adp-arch-export/strategy/objectives/$OBJ_ID_2.json" && echo "OK: file removed"

python3 -c "
import json
a = json.load(open('/tmp/adp-arch-export/strategy/objectives/$OBJ_ID.json'))
assert a['depends_on_objective_ids'] == []
print('OK: the dangling dependency reference is gone too, not left stale')
"
```

## Scenario 5: `linked_designs` is added to ADP-SPEC-044's own capability/value-stream files (Clarification Q2, FR-016)

```bash
CAP_ID=$(curl -s -X POST http://localhost:8001/api/v1/business/capabilities \
  -H "Content-Type: application/json" -d '{"name":"Claims Intake","level":1}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

DSN_ID=$(curl -s -X POST http://localhost:8001/api/v1/designs \
  -H "Content-Type: application/json" -d '{"title":"Claims Intake Service"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

curl -s -X POST "http://localhost:8001/api/v1/business/capabilities/$CAP_ID/designs" \
  -H "Content-Type: application/json" -d "{\"design_id\":\"$DSN_ID\"}" > /dev/null

sleep 6

cat "/tmp/adp-arch-export/business-architecture/capabilities/$CAP_ID.json" | python3 -m json.tool
# Expect: linked_designs == ["<DSN_ID>"] -- a field that did not exist on this file before
#         this increment, added to the already-shipped business_arch export module.
```

## Scenario 6: Unchanged data is not rewritten (FR-009)

```bash
STAT1=$(stat -c %Y "/tmp/adp-arch-export/strategy/objectives/$OBJ_ID.json" 2>/dev/null || stat -f %m "/tmp/adp-arch-export/strategy/objectives/$OBJ_ID.json")
sleep 6
STAT2=$(stat -c %Y "/tmp/adp-arch-export/strategy/objectives/$OBJ_ID.json" 2>/dev/null || stat -f %m "/tmp/adp-arch-export/strategy/objectives/$OBJ_ID.json")
[ "$STAT1" = "$STAT2" ] && echo "OK: file not rewritten when nothing changed"
```
