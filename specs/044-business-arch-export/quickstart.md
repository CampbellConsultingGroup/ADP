# Quickstart: Continuous Business Architecture Export (ADP-SPEC-044 / ADP-81p.1)

This feature has no HTTP endpoint and no UI — it's a background process. Verification is by configuring it, making changes through the existing API, and inspecting the resulting files.

Assumes API at `http://localhost:8001` with `ADP_AUTH_ENABLED=false`.

## Setup: enable the export

```bash
export ADP_BUSINESS_ARCH_EXPORT_ROOT=/tmp/adp-arch-export
export ADP_BUSINESS_ARCH_EXPORT_INTERVAL_SECONDS=5   # short interval for local testing; production default is longer
# restart the API with these set
```

Without `ADP_BUSINESS_ARCH_EXPORT_ROOT` set, the background task never starts and no files are ever written — confirm this first:

```bash
unset ADP_BUSINESS_ARCH_EXPORT_ROOT
# start the API, wait a few seconds
ls /tmp/adp-arch-export 2>&1
# Expect: No such file or directory — the feature is inert when unconfigured
```

## Scenario 1: First-run bootstrap exports everything that already exists (FR-008)

```bash
# Create a capability, a domain, a value stream with one stage, BEFORE enabling the export
CAP_ID=$(curl -s -X POST http://localhost:8001/api/v1/business/capabilities \
  -H "Content-Type: application/json" \
  -d '{"name":"Risk Assessment","level":1}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# Now enable the export (per Setup above) and restart, then wait one interval
sleep 6

cat "/tmp/adp-arch-export/business-architecture/capabilities/$CAP_ID.json" | python3 -m json.tool
# Expect: the capability's current data, with domain_id/strategic_relevance/maturity_level as explicit null
```

## Scenario 2: A change is reflected within one interval, with nothing else touched (SC-002, Story 2)

```bash
# Record the file's current content and mtime
BEFORE=$(cat "/tmp/adp-arch-export/business-architecture/capabilities/$CAP_ID.json")

curl -s -X PUT "http://localhost:8001/api/v1/business/capabilities/$CAP_ID" \
  -H "Content-Type: application/json" \
  -d '{"maturity_level": 3}' > /dev/null

sleep 6
AFTER=$(cat "/tmp/adp-arch-export/business-architecture/capabilities/$CAP_ID.json")

python3 -c "
import json
print('maturity_level now:', json.loads('''$AFTER''')['maturity_level'])
"
# Expect: 3
```

## Scenario 3: An unchanged entity's file is not rewritten (FR-009)

```bash
STAT_BEFORE=$(stat -c %Y "/tmp/adp-arch-export/business-architecture/capabilities/$CAP_ID.json")
sleep 6   # let at least one more reconciliation cycle pass with no changes
STAT_AFTER=$(stat -c %Y "/tmp/adp-arch-export/business-architecture/capabilities/$CAP_ID.json")

[ "$STAT_BEFORE" == "$STAT_AFTER" ] && echo "OK: file untouched" || echo "FAIL: file rewritten with no data change"
```

## Scenario 4: Deleting an entity removes its file (FR-004, Edge Case)

```bash
curl -s -o /dev/null -X DELETE "http://localhost:8001/api/v1/business/capabilities/$CAP_ID"
sleep 6

test -f "/tmp/adp-arch-export/business-architecture/capabilities/$CAP_ID.json" \
  && echo "FAIL: orphaned file left behind" \
  || echo "OK: file removed"
```

## Scenario 5: A value stream stage's file includes its linked capabilities (FR-011)

```bash
VS_ID=$(curl -s -X POST http://localhost:8001/api/v1/business/value-streams \
  -H "Content-Type: application/json" -d '{"name":"Order-to-Cash"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

STAGE_ID=$(curl -s -X POST "http://localhost:8001/api/v1/business/value-streams/$VS_ID/stages" \
  -H "Content-Type: application/json" -d '{"name":"Quote","position":0}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

CAP2_ID=$(curl -s -X POST http://localhost:8001/api/v1/business/capabilities \
  -H "Content-Type: application/json" -d '{"name":"Pricing","level":1}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

curl -s -X POST "http://localhost:8001/api/v1/business/value-streams/$VS_ID/stages/$STAGE_ID/capabilities" \
  -H "Content-Type: application/json" -d "{\"capability_id\": \"$CAP2_ID\"}" > /dev/null

sleep 6
cat "/tmp/adp-arch-export/business-architecture/value-streams/$VS_ID/stages/$STAGE_ID.json" | python3 -m json.tool
# Expect: "linked_capability_ids": ["<CAP2_ID>"]
```

## Scenario 6: A failed cycle is logged, not silent (SC-004)

```bash
# (Best exercised as a unit/integration test with a mocked filesystem failure rather than
# manually here — confirm by reading the application logs for a WARNING-or-higher
# "business_arch_export" event after deliberately breaking write access, e.g.:
chmod 000 /tmp/adp-arch-export
sleep 6
chmod 755 /tmp/adp-arch-export
# check API server logs for the export-cycle failure event, then confirm the NEXT
# cycle (after permissions are restored) succeeds normally.
```
