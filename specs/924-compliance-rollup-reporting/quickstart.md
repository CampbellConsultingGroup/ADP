# Quickstart / Integration Scenarios: Compliance Rollup Reporting — COMPLY-04

**Feature**: 924-compliance-rollup-reporting
**Date**: 2026-08-19

These scenarios drive integration/contract tests and manual acceptance verification. Assumes the API
at `http://localhost:8001` with `ADP_AUTH_ENABLED=false` (dev convention — role defaults to
`ENTERPRISE_ARCHITECT`, which holds every action, including `READ_APPLICATION_GOVERNANCE`), and at
least one `RegulatoryFramework` with several `Control`s, mapped to a mix of entities (COMPLY-01/02).

---

## Scenario 1: Framework coverage rollup reflects a mix of statuses (US1, AS1)

**Goal**: Verify FR-001, FR-002.

```bash
# Map three controls from one framework to a Capability (compliant), an Application
# (non_compliant), and a Design (partial) — then read the rollup.
curl -s "http://localhost:8001/api/v1/compliance/frameworks/$FW_ID/rollup" | python3 -m json.tool
# Expect: entity_counts.compliant_count == 1, non_compliant_count == 1, partial_count == 1,
#         not_assessed_count == 0, not_applicable_count == 0, organization_status == null
```

## Scenario 2: An entity's status is scoped to the framework being rolled up, not blended (US1, AS2)

**Goal**: Verify FR-001's framework-scoping.

```bash
# Map Control A (Framework 1) to Application X with status non_compliant.
# Map Control B (Framework 2) to the SAME Application X with status compliant.
curl -s "http://localhost:8001/api/v1/compliance/frameworks/$FW1_ID/rollup" | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert d['entity_counts']['non_compliant_count'] == 1
print('OK: Application X counts as non-compliant under Framework 1')
"
curl -s "http://localhost:8001/api/v1/compliance/frameworks/$FW2_ID/rollup" | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert d['entity_counts']['compliant_count'] == 1
print('OK: the same Application X counts as compliant under Framework 2 -- never blended')
"
```

## Scenario 3: An estate-wide obligation shows as its own line, not one more entity (US1, AS3)

**Goal**: Verify FR-003.

```bash
curl -s -X PUT "http://localhost:8001/api/v1/compliance/controls/$CTRL_ID/mappings/organization" \
  -H "Content-Type: application/json" -d '{"compliance_status":"partial"}'
curl -s "http://localhost:8001/api/v1/compliance/frameworks/$FW_ID/rollup" | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert d['organization_status'] == 'partial'
print('OK: estate-wide obligation is its own field, not folded into entity_counts')
"
```

## Scenario 4: Application-targeted entities are excluded from a governance-lacking caller's rollup (US1, AS4)

**Goal**: Verify FR-007. Requires a role lacking `READ_APPLICATION_GOVERNANCE` — verified via
`tests/authz/test_enforcement.py`'s role-overridden `TestClient`, matching this session's own
established pattern for authz checks (no dev-mode `X-Role` header exists).

```python
# tests/contract/test_compliance_rollup_api.py (illustrative)
resp_privileged = client.get(f"/api/v1/compliance/frameworks/{fw_id}/rollup")
resp_reviewer = client.get(
    f"/api/v1/compliance/frameworks/{fw_id}/rollup",
    headers={"X-Test-Role": "REVIEWER"},  # test-only override, not a real header
)
assert resp_privileged.json()["entity_counts"]["non_compliant_count"] == 2  # includes the Application
assert resp_reviewer.json()["entity_counts"]["non_compliant_count"] == 1     # Application excluded
```

## Scenario 5: Platform-wide summary card numbers (US2, AS1-3)

**Goal**: Verify FR-004.

```bash
curl -s "http://localhost:8001/api/v1/compliance/summary" | python3 -m json.tool
# Expect: framework_count matches the actual number of registered frameworks,
#         coverage_percent == 100 * (compliant entities) / (all distinctly-mapped entities),
#         at_risk_count == count of entities with overall status non_compliant or partial
```

## Scenario 6: Empty-estate summary reads as "no data," not a misleading 0% (Edge Case)

**Goal**: Verify FR-009.

```bash
# Against a freshly migrated database with zero frameworks/mappings at all:
curl -s "http://localhost:8001/api/v1/compliance/summary" | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert d['framework_count'] == 0
assert d['coverage_percent'] is None
print('OK: coverage_percent is null, not 0.0 -- distinguishable from a real 0%')
"
```

## Scenario 7: A framework with zero mappings shows every bucket at zero (Edge Case)

**Goal**: Verify FR-008.

```bash
curl -s -X POST http://localhost:8001/api/v1/compliance/frameworks \
  -H "Content-Type: application/json" \
  -d '{"name":"Empty Framework","jurisdiction":"Test","authority":"Test","version":"1"}'
# Take the returned id, then:
curl -s "http://localhost:8001/api/v1/compliance/frameworks/$EMPTY_FW_ID/rollup" | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert all(v == 0 for v in d['entity_counts'].values())
assert d['organization_status'] is None
print('OK: an unmapped framework rolls up to all zeros, not an error or an absent framework')
"
```

## Scenario 8: Overview dashboard shows the new Compliance card and deep-links correctly (US2, AS4)

**Goal**: Verify FR-005. Manual/Playwright verification against a running local stack.

1. Navigate to the Overview dashboard.
2. Confirm a "Compliance" domain card is present with the three figures above.
3. Click through from the card.
4. Confirm the click lands on the dedicated Compliance screen
   (`web/src/compliance/CompliancePage.tsx`), not `web/src/governance/ComplianceTab.tsx` (the
   unrelated LLM-Judge validation-exceptions screen).
