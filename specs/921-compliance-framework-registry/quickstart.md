# Quickstart / Integration Scenarios: Compliance Framework & Control Registry (COMPLY-01)

**Feature**: 921-compliance-framework-registry
**Date**: 2026-08-17

These scenarios drive integration tests and manual acceptance verification. Assumes the API at
`http://localhost:8001` with `ADP_AUTH_ENABLED=false` (dev convention — `X-Actor` header drives identity).

---

## Scenario 1: Register a framework without an effective date (US1, Acceptance Scenario 2)

**Goal**: Verify FR-001, FR-002.

```bash
curl -s -X POST http://localhost:8001/api/v1/compliance/frameworks \
  -H "Content-Type: application/json" -H "X-Actor: alice" \
  -d '{"name":"SOC 2 Type II","jurisdiction":"US","authority":"AICPA","version":"2017 TSC"}' \
  | python3 -m json.tool
# Expect: 201, effective_date == null, source_url == null — not an error.
```

---

## Scenario 2: Build a multi-level control hierarchy (US2, Acceptance Scenarios 1–2)

**Goal**: Verify FR-006, FR-007, FR-011 — the GDPR granularity example from the source doc (Art. 5's six
sub-points vs. Art. 33 standing alone).

```bash
FRAMEWORK_ID=$(curl -s -X POST http://localhost:8001/api/v1/compliance/frameworks \
  -H "Content-Type: application/json" \
  -d '{"name":"GDPR","jurisdiction":"EU","authority":"European Commission","version":"2016/679"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

ART5_ID=$(curl -s -X POST "http://localhost:8001/api/v1/compliance/frameworks/$FRAMEWORK_ID/controls" \
  -H "Content-Type: application/json" \
  -d '{"code":"Art. 5","title":"Principles relating to processing","description":"Broad principles.","position":0}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

for i in a b c d e f; do
  curl -s -X POST "http://localhost:8001/api/v1/compliance/frameworks/$FRAMEWORK_ID/controls" \
    -H "Content-Type: application/json" \
    -d "{\"parent_id\":\"$ART5_ID\",\"code\":\"Art. 5(1)($i)\",\"title\":\"Sub-point $i\",\"description\":\"...\"}" \
    > /dev/null
done

curl -s -X POST "http://localhost:8001/api/v1/compliance/frameworks/$FRAMEWORK_ID/controls" \
  -H "Content-Type: application/json" \
  -d '{"code":"Art. 33","title":"Notification of a personal data breach","description":"Standalone leaf.","position":1}' \
  > /dev/null

curl -s "http://localhost:8001/api/v1/compliance/frameworks/$FRAMEWORK_ID" | python3 -c "
import sys, json
d = json.load(sys.stdin)
top = d['controls']
assert len(top) == 2, top
art5 = next(c for c in top if c['code'] == 'Art. 5')
assert len(art5['children']) == 6, art5
art33 = next(c for c in top if c['code'] == 'Art. 33')
assert art33['children'] == []
print('OK: Art. 5 has 6 children, Art. 33 stands alone as a leaf')
"
```

---

## Scenario 3: Duplicate control code within a framework is rejected (US2, Acceptance Scenario 4; SC-004)

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST \
  "http://localhost:8001/api/v1/compliance/frameworks/$FRAMEWORK_ID/controls" \
  -H "Content-Type: application/json" \
  -d '{"code":"Art. 33","title":"Duplicate code attempt","description":"..."}'
# Expect: 409
```

Same code under a *different* framework must succeed (US2, Acceptance Scenario 3):

```bash
OTHER_FRAMEWORK_ID=$(curl -s -X POST http://localhost:8001/api/v1/compliance/frameworks \
  -H "Content-Type: application/json" \
  -d '{"name":"NIST 800-53 Rev 5","jurisdiction":"US-Federal","authority":"NIST","version":"Rev 5"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

curl -s -o /dev/null -w "%{http_code}\n" -X POST \
  "http://localhost:8001/api/v1/compliance/frameworks/$OTHER_FRAMEWORK_ID/controls" \
  -H "Content-Type: application/json" \
  -d '{"code":"Art. 33","title":"Same code, different framework","description":"..."}'
# Expect: 201
```

---

## Scenario 4: Cycle and cross-framework parent rejection (Edge Cases)

```bash
CTRL_A=$(curl -s -X POST "http://localhost:8001/api/v1/compliance/frameworks/$FRAMEWORK_ID/controls" \
  -H "Content-Type: application/json" \
  -d '{"code":"AC-1","title":"A","description":"..."}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# Self-parent (0-length cycle)
curl -s -o /dev/null -w "%{http_code}\n" -X PATCH "http://localhost:8001/api/v1/compliance/controls/$CTRL_A" \
  -H "Content-Type: application/json" -d "{\"parent_id\":\"$CTRL_A\"}"
# Expect: 422

# Cross-framework parent
FOREIGN_CTRL=$(curl -s -X POST "http://localhost:8001/api/v1/compliance/frameworks/$OTHER_FRAMEWORK_ID/controls" \
  -H "Content-Type: application/json" \
  -d '{"code":"AC-2","title":"B","description":"..."}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

curl -s -o /dev/null -w "%{http_code}\n" -X PATCH "http://localhost:8001/api/v1/compliance/controls/$CTRL_A" \
  -H "Content-Type: application/json" -d "{\"parent_id\":\"$FOREIGN_CTRL\"}"
# Expect: 422
```

---

## Scenario 5: Cascading delete removes an entire subtree (US3, Acceptance Scenario 3; SC-006)

```bash
curl -s -X DELETE "http://localhost:8001/api/v1/compliance/controls/$ART5_ID" -o /dev/null -w "%{http_code}\n"
# Expect: 204

curl -s "http://localhost:8001/api/v1/compliance/frameworks/$FRAMEWORK_ID" | python3 -c "
import sys, json
d = json.load(sys.stdin)
codes = {c['code'] for c in d['controls']}
assert 'Art. 5' not in codes
assert not any(c['code'].startswith('Art. 5(1)') for c in d['controls'])  # children gone too
print('OK: deleting Art. 5 removed all 6 children with it')
"
```

Deleting the framework itself removes everything else that remains:

```bash
curl -s -X DELETE "http://localhost:8001/api/v1/compliance/frameworks/$FRAMEWORK_ID" -o /dev/null -w "%{http_code}\n"
# Expect: 204
curl -s -o /dev/null -w "%{http_code}\n" "http://localhost:8001/api/v1/compliance/frameworks/$FRAMEWORK_ID"
# Expect: 404
```

---

## Scenario 6: Write access requires `WRITE_COMPLIANCE`; reads stay open (research.md D4)

There is no `X-Role` dev-mode override header anywhere in this codebase (confirmed by direct grep — role
comes only from a real JWT, or from `UNAUTHENTICATED_USER`'s fixed `ENTERPRISE_ARCHITECT` fallback when
`ADP_AUTH_ENABLED=false`), so a REVIEWER-role denial cannot be driven by curl headers against a plain dev
server. That check is exercised directly instead, via a role-overridden `TestClient`
(`tests/authz/test_enforcement.py::test_reviewer_denied_compliance_write`):

```bash
.venv/bin/python -m pytest tests/authz/test_enforcement.py -k compliance -v
# Expect: test_reviewer_denied_compliance_write PASSED (403 for a REVIEWER-role POST)
#         test_compliance_write_route_maps_to_action PASSED
#         test_compliance_read_routes_are_ungated PASSED
#         test_compliance_action_grant_matrix PASSED
```

Reads are always open regardless of role (no `READ_COMPLIANCE` action exists at all, matching every other
registry domain):

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8001/api/v1/compliance/frameworks
# Expect: 200
```
