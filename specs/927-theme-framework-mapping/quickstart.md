# Quickstart / Integration Scenarios: Theme–Framework Mapping

**Feature**: 927-theme-framework-mapping
**Date**: 2026-08-26

These scenarios drive integration/contract tests and manual acceptance verification. Assumes the API at
`http://localhost:8001` with `ADP_AUTH_ENABLED=false` (dev convention — role defaults to
`ENTERPRISE_ARCHITECT`, which holds every action), and at least one existing `StrategicTheme` (`$THEME_ID`)
and `RegulatoryFramework` (`$FRAMEWORK_ID`).

---

## Scenario 1: Tag a theme against a framework, confirm from both sides (US1/US2, AS1)

**Goal**: Verify FR-001, FR-004, FR-005.

```bash
curl -s -X POST "http://localhost:8001/api/v1/strategy/themes/$THEME_ID/frameworks" \
  -H "Content-Type: application/json" \
  -d "{\"framework_id\": \"$FRAMEWORK_ID\"}" | python3 -m json.tool
# Expect 201; response is a bare list containing $FRAMEWORK_ID.

curl -s "http://localhost:8001/api/v1/strategy/themes/$THEME_ID" | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert '$FRAMEWORK_ID' in d['framework_ids']
print('OK: framework_ids reflects the tag from the Theme side')
"

curl -s "http://localhost:8001/api/v1/compliance/frameworks/$FRAMEWORK_ID/themes" | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert any(t['id'] == '$THEME_ID' for t in d['items'])
print('OK: reverse lookup reflects the tag from the Framework side')
"
```

## Scenario 2: Duplicate tag is rejected, existing tag unchanged (US1, AS2)

**Goal**: Verify FR-002.

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST \
  "http://localhost:8001/api/v1/strategy/themes/$THEME_ID/frameworks" \
  -H "Content-Type: application/json" \
  -d "{\"framework_id\": \"$FRAMEWORK_ID\"}"
# Expect 409 -- the pair from Scenario 1 is already linked.
```

## Scenario 3: Tagging a nonexistent theme or framework is rejected (US1, AS3)

**Goal**: Verify FR-003.

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST \
  "http://localhost:8001/api/v1/strategy/themes/$THEME_ID/frameworks" \
  -H "Content-Type: application/json" \
  -d '{"framework_id": "FRM-does-not-exist"}'
# Expect 404.

curl -s -o /dev/null -w "%{http_code}\n" -X POST \
  "http://localhost:8001/api/v1/strategy/themes/THM-does-not-exist/frameworks" \
  -H "Content-Type: application/json" \
  -d "{\"framework_id\": \"$FRAMEWORK_ID\"}"
# Expect 404.
```

## Scenario 4: Many-to-many — a theme tagged against multiple frameworks, and vice versa (US2, AS1/AS2)

**Goal**: Verify FR-006.

```bash
curl -s -X POST "http://localhost:8001/api/v1/strategy/themes/$THEME_ID/frameworks" \
  -H "Content-Type: application/json" -d "{\"framework_id\": \"$FRAMEWORK_ID_2\"}"
# Expect 201; $THEME_ID now tagged against two frameworks.

curl -s "http://localhost:8001/api/v1/strategy/themes/$THEME_ID" | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert set(d['framework_ids']) >= {'$FRAMEWORK_ID', '$FRAMEWORK_ID_2'}
print('OK: one theme tagged against two frameworks')
"
```

## Scenario 5: Empty reverse lookup is an empty list, not an error (US2, AS3)

**Goal**: Verify FR-004/FR-005's edge case.

```bash
curl -s "http://localhost:8001/api/v1/compliance/frameworks/$FRESH_FRAMEWORK_ID/themes" | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert d == {'items': [], 'total': 0}
print('OK: a framework with no tags returns an empty list')
"
```

## Scenario 6: Remove a tag; both sides reflect it immediately (US3, AS1)

**Goal**: Verify FR-007, SC-003.

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X DELETE \
  "http://localhost:8001/api/v1/strategy/themes/$THEME_ID/frameworks/$FRAMEWORK_ID"
# Expect 204.

curl -s "http://localhost:8001/api/v1/strategy/themes/$THEME_ID" | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert '$FRAMEWORK_ID' not in d['framework_ids']
print('OK: tag gone from the Theme side')
"

curl -s "http://localhost:8001/api/v1/compliance/frameworks/$FRAMEWORK_ID/themes" | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert not any(t['id'] == '$THEME_ID' for t in d['items'])
print('OK: tag gone from the Framework side too')
"
```

## Scenario 7: Removing a nonexistent tag is rejected (US3, AS2)

**Goal**: Verify FR-008.

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X DELETE \
  "http://localhost:8001/api/v1/strategy/themes/$THEME_ID/frameworks/$FRAMEWORK_ID"
# Expect 404 -- already removed in Scenario 6.
```

## Scenario 8: Deleting a linked theme or framework cascades, orphaning nothing (Edge Cases, FR-009, SC-004)

**Goal**: Verify the migration's `ON DELETE CASCADE` on both legs. Requires the real Postgres constraint
(integration test, testcontainers-gated) rather than the SQLite contract fixture.

```bash
curl -s -X POST "http://localhost:8001/api/v1/strategy/themes/$TEMP_THEME_ID/frameworks" \
  -H "Content-Type: application/json" -d "{\"framework_id\": \"$FRAMEWORK_ID\"}"

curl -s -X DELETE "http://localhost:8001/api/v1/strategy/themes/$TEMP_THEME_ID"
# Deleting the theme must not fail, and must not leave a dangling theme_framework_links row --
# verified directly against the database in the integration test (no API surface exists to list
# link rows independent of a live theme/framework, by design).
```
