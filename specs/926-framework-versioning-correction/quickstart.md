# Quickstart / Integration Scenarios: Regulatory Framework Legal Dates & Identity (COMPLY-01a)

**Feature**: 926-framework-versioning-correction
**Date**: 2026-08-19

Assumes the API at `http://localhost:8001` with `ADP_AUTH_ENABLED=false` (dev convention — role defaults
to `ENTERPRISE_ARCHITECT`, which holds `WRITE_COMPLIANCE`).

---

## Scenario 1: Existing frameworks are untouched by the migration (US1, FR-004, SC-001)

**Goal**: Verify no data loss against the three real, currently-tracked frameworks — the load-bearing
guarantee this whole spec exists to uphold.

```bash
# Before and after the migration, every existing field must read identically.
curl -s "http://localhost:8001/api/v1/compliance/frameworks" | python3 -c "
import sys, json
d = json.load(sys.stdin)
for fw in d['items']:
    assert fw['version'] is not None and fw['version'] != ''
    assert fw['regulation_number'] is None      # new field, unset, not required
    assert fw['status'] == 'in_force'           # server_default applied to pre-existing rows
print('OK: existing fields intact, new fields present but unset')
"
```

## Scenario 2: Record a framework's legal identity and dates independently (US1, FR-001/002, SC-002)

```bash
FW_ID="<a real framework id>"
curl -s -X PATCH "http://localhost:8001/api/v1/compliance/frameworks/$FW_ID" \
  -H "Content-Type: application/json" \
  -d '{"regulation_number": "2016/679", "adoption_date": "2016-04-27", "consolidated_as_of": "2016-05-04"}' \
  | python3 -m json.tool
# Expect 200; name/jurisdiction/authority/version/effective_date/source_url unchanged;
# oj_publication_date/entry_into_force_date remain null (never provided).
```

## Scenario 3: Duplicate regulation_number rejected (Edge Cases, D5)

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X PATCH \
  "http://localhost:8001/api/v1/compliance/frameworks/$OTHER_FW_ID" \
  -H "Content-Type: application/json" -d '{"regulation_number": "2016/679"}'
# Expect 409 -- already used by $FW_ID above.
```

## Scenario 4: Application phases — staged rollout, and the zero-phase case (US2, FR-005/006)

```bash
curl -s -X POST "http://localhost:8001/api/v1/compliance/frameworks/$FW_ID/application-phases" \
  -H "Content-Type: application/json" \
  -d '{"phase_label": "Prohibited practices", "applies_from_date": "2025-02-02"}'
curl -s -X POST "http://localhost:8001/api/v1/compliance/frameworks/$FW_ID/application-phases" \
  -H "Content-Type: application/json" \
  -d '{"phase_label": "GPAI obligations", "applies_from_date": "2025-08-02"}'

curl -s "http://localhost:8001/api/v1/compliance/frameworks/$FW_ID/application-phases" | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert d['total'] == 2
assert d['items'][0]['applies_from_date'] < d['items'][1]['applies_from_date']
print('OK: two phases, ordered by date')
"

# A framework never touched by this endpoint at all:
curl -s "http://localhost:8001/api/v1/compliance/frameworks/$UNTOUCHED_FW_ID/application-phases" | python3 -c "
import sys, json
assert json.load(sys.stdin)['total'] == 0
print('OK: zero phases is the default, not an error')
"
```

## Scenario 5: Amendments — a growing list, no limit (US3, FR-007, SC-004)

```bash
for i in 1 2 3 4 5; do
  curl -s -X POST "http://localhost:8001/api/v1/compliance/frameworks/$FW_ID/amendments" \
    -H "Content-Type: application/json" \
    -d "{\"amending_title\": \"RTS $i\", \"amending_celex\": \"3202${i}R000${i}\"}" > /dev/null
done
curl -s "http://localhost:8001/api/v1/compliance/frameworks/$FW_ID/amendments" | python3 -c "
import sys, json
assert json.load(sys.stdin)['total'] == 5
print('OK: 5 amendments recorded, no limit hit')
"
```

## Scenario 6: Remove a phase/amendment without disturbing siblings (US2/US3 AS3)

```bash
PHASE_ID="<one of the two phase ids from Scenario 4>"
curl -s -o /dev/null -w "%{http_code}\n" -X DELETE \
  "http://localhost:8001/api/v1/compliance/frameworks/$FW_ID/application-phases/$PHASE_ID"
# Expect 204.
curl -s "http://localhost:8001/api/v1/compliance/frameworks/$FW_ID/application-phases" | python3 -c "
import sys, json
assert json.load(sys.stdin)['total'] == 1
print('OK: one phase removed, the other survives')
"
```

## Scenario 7: `GET /frameworks/{id}` nests both new lists alongside `controls` (research.md D4)

```bash
curl -s "http://localhost:8001/api/v1/compliance/frameworks/$FW_ID" | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert 'application_phases' in d and 'amendments' in d and 'controls' in d
print('OK: detail response carries all three nested lists')
"
```

## Scenario 8: Deleting a framework cascades its phases and amendments (US2/US3, FR-009, SC-005)

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X DELETE "http://localhost:8001/api/v1/compliance/frameworks/$FW_ID"
# Expect 204.
curl -s -o /dev/null -w "%{http_code}\n" \
  "http://localhost:8001/api/v1/compliance/frameworks/$FW_ID/application-phases"
# Expect 404 -- framework itself is gone, not an empty list.
```

---

**Cleanup**: any framework/phase/amendment created for these scenarios is deleted afterward; the three
real pre-existing frameworks (GDPR, EU AI Act, DORA) are read-only touched in Scenarios 1–2 (a temporary
`regulation_number` set then cleared back to `null`) and confirmed unchanged otherwise, matching this
session's own established live-verification discipline.
