# Quickstart / Integration Scenarios: Regulatory Framework Tags for Application Risk & Compliance

**Feature**: 932-regulatory-framework-tags
**Date**: 2026-10-07

These scenarios drive integration/contract tests and manual acceptance verification. Assumes the
API at `http://localhost:8001` with `ADP_AUTH_ENABLED=false` (dev convention — role defaults to
`ENTERPRISE_ARCHITECT`, which holds every action), an existing `Application` (`$APP_ID`), and two
existing `in_force`-or-`amended` `RegulatoryFramework`s (`$FRAMEWORK_ID_1`, `$FRAMEWORK_ID_2`).

---

## Scenario 1: Tag an application with real frameworks, confirm it persists (US1, AS1)

**Goal**: Verify FR-001, FR-002, FR-004.

```bash
curl -s -X PUT "http://localhost:8001/api/v1/applications/$APP_ID/risk" \
  -H "Content-Type: application/json" \
  -d "{\"regulatory_tags\": [\"$FRAMEWORK_ID_1\", \"$FRAMEWORK_ID_2\"]}" | python3 -m json.tool
# Expect 200; regulatory_tags echoes both ids.

curl -s "http://localhost:8001/api/v1/applications/$APP_ID/risk" | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert set(d['regulatory_tags']) == {'$FRAMEWORK_ID_1', '$FRAMEWORK_ID_2'}
print('OK: tags persisted across reload')
"
```

## Scenario 2: Replace the tag set (US1, AS2)

**Goal**: Verify full-replace semantics (research.md D2) — removing one, adding a different one.

```bash
curl -s -X PUT "http://localhost:8001/api/v1/applications/$APP_ID/risk" \
  -H "Content-Type: application/json" \
  -d "{\"regulatory_tags\": [\"$FRAMEWORK_ID_2\"]}" | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert d['regulatory_tags'] == ['$FRAMEWORK_ID_2']
print('OK: only the newly-submitted set remains')
"
```

## Scenario 3: Unknown framework id is rejected (FR-002)

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X PUT "http://localhost:8001/api/v1/applications/$APP_ID/risk" \
  -H "Content-Type: application/json" \
  -d '{"regulatory_tags": ["00000000-0000-0000-0000-000000000000"]}'
# Expect 422. Application's actual tags from Scenario 2 remain unchanged (no partial write).
```

## Scenario 4: A `repealed`/`not_yet_applicable` framework cannot be newly tagged (FR-001/FR-002)

**Setup**: `$REPEALED_FRAMEWORK_ID` is an existing framework with `status: "repealed"` (or
`"not_yet_applicable"`).

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X PUT "http://localhost:8001/api/v1/applications/$APP_ID/risk" \
  -H "Content-Type: application/json" \
  -d "{\"regulatory_tags\": [\"$FRAMEWORK_ID_2\", \"$REPEALED_FRAMEWORK_ID\"]}"
# Expect 422 -- the whole write is rejected, including the otherwise-valid $FRAMEWORK_ID_2.
```

## Scenario 5: A framework that becomes repealed *after* being tagged is not retroactively removed (Edge Case)

```bash
# $FRAMEWORK_ID_2 is already tagged on $APP_ID from Scenario 2.
curl -s -X PUT "http://localhost:8001/api/v1/compliance/frameworks/$FRAMEWORK_ID_2" \
  -H "Content-Type: application/json" -d '{"status": "repealed"}' -o /dev/null -w "%{http_code}\n"
# Expect 200.

curl -s -X PUT "http://localhost:8001/api/v1/applications/$APP_ID/risk" \
  -H "Content-Type: application/json" \
  -d "{\"regulatory_tags\": [\"$FRAMEWORK_ID_2\"]}" | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert d['regulatory_tags'] == ['$FRAMEWORK_ID_2']
print('OK: re-submitting an already-linked, now-repealed id is not rejected')
"
# Revert for cleanup:
curl -s -X PUT "http://localhost:8001/api/v1/compliance/frameworks/$FRAMEWORK_ID_2" \
  -H "Content-Type: application/json" -d '{"status": "in_force"}' -o /dev/null -w "%{http_code}\n"
```

## Scenario 6: Deleting a framework removes it from every application's tags (US3, AS1; FR-005)

```bash
# Create a scratch framework, tag it onto $APP_ID, then delete it.
SCRATCH_FID=$(curl -s -X POST "http://localhost:8001/api/v1/compliance/frameworks" \
  -H "Content-Type: application/json" \
  -d '{"name":"Scratch Test Framework","jurisdiction":"Test","authority":"Test","version":"1"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

curl -s -X PUT "http://localhost:8001/api/v1/applications/$APP_ID/risk" \
  -H "Content-Type: application/json" \
  -d "{\"regulatory_tags\": [\"$FRAMEWORK_ID_2\", \"$SCRATCH_FID\"]}" -o /dev/null -w "%{http_code}\n"

curl -s -X DELETE "http://localhost:8001/api/v1/compliance/frameworks/$SCRATCH_FID" -o /dev/null -w "%{http_code}\n"
# Expect 204.

curl -s "http://localhost:8001/api/v1/applications/$APP_ID/risk" | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert '$SCRATCH_FID' not in d['regulatory_tags']
assert '$FRAMEWORK_ID_2' in d['regulatory_tags']
print('OK: deleted framework's tag is gone; the other survives untouched')
"
```

## Scenario 7: Zero tags is a valid, unremarkable state (FR-007)

```bash
curl -s -X PUT "http://localhost:8001/api/v1/applications/$APP_ID/risk" \
  -H "Content-Type: application/json" -d '{"regulatory_tags": []}' | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert d['regulatory_tags'] == []
print('OK: zero tags round-trips cleanly')
"
```

## Scenario 8: Frontend — picker only offers in_force/amended frameworks, shows real names (US1/US2)

Manual browser check (Playwright), since this is a UI-facing requirement:
1. Open the Risk & Compliance tab for `$APP_ID`.
2. Confirm the framework picker lists only frameworks whose status is `in_force` or `amended` —
   a `repealed` or `not_yet_applicable` framework (e.g. the one toggled in Scenario 5, reverted
   back to `in_force` at the end) must not appear as a *selectable* option while repealed.
3. Select two frameworks, Save, reload the page, confirm both show by **name** (not a raw id).
4. Confirm the separate "Regulatory Compliance" tab (`ApplicationComplianceMappings.tsx`,
   COMPLY-02 control mappings) is unaffected — still shows its own, unrelated content (FR-008).
