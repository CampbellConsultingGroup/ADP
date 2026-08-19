# Quickstart / Integration Scenarios: Strategy Domain Linkage — COMPLY-05

**Feature**: 925-strategy-compliance-linkage
**Date**: 2026-08-19

These scenarios drive integration/contract tests and manual acceptance verification. Assumes the API at
`http://localhost:8001` with `ADP_AUTH_ENABLED=false` (dev convention — role defaults to
`ENTERPRISE_ARCHITECT`, which holds every action), and at least one `RegulatoryFramework`/`Control` with
an existing `ControlMapping` (COMPLY-01/02), plus an existing `StrategicObjective` and `StrategyInitiative`
(050/916).

---

## Scenario 1: Link an Initiative directly to a compliance gap, no Objective involved (US1, AS1/AS2)

**Goal**: Verify FR-001, FR-004, FR-005.

```bash
# Assume $CONTROL_ID / $APP_ID already have a non_compliant ControlMapping (COMPLY-02).
curl -s -X POST \
  "http://localhost:8001/api/v1/strategy/initiatives/$INITIATIVE_ID/control-mappings/applications/$CONTROL_ID/$APP_ID" \
  | python3 -m json.tool
# Expect 201; response includes one ControlMappingRef with
# target_type == "application", compliance_status == "non_compliant".

curl -s "http://localhost:8001/api/v1/strategy/initiatives" | python3 -c "
import sys, json
d = json.load(sys.stdin)
init = next(i for i in d['items'] if i['id'] == '$INITIATIVE_ID')
assert len(init['control_mappings']) == 1
assert init['objective_ids'] == []
print('OK: Initiative linked to a compliance gap with zero Objectives involved')
"
```

## Scenario 2: Live status — no separately-drifting field on the link (US1, AS3)

**Goal**: Verify FR-008, research.md D3.

```bash
# Re-assess the same ControlMapping to compliant (ordinary COMPLY-02 flow, not this feature).
curl -s -X PUT "http://localhost:8001/api/v1/compliance/controls/$CONTROL_ID/mappings/applications/$APP_ID" \
  -H "Content-Type: application/json" \
  -d '{"compliance_status": "compliant", "assessed_by": "alice"}'

curl -s "http://localhost:8001/api/v1/strategy/initiatives" | python3 -c "
import sys, json
d = json.load(sys.stdin)
init = next(i for i in d['items'] if i['id'] == '$INITIATIVE_ID')
assert init['control_mappings'][0]['compliance_status'] == 'compliant'
print('OK: status shown through the Initiative link updated with zero writes to the link itself')
"
```

## Scenario 3: Reverse lookup from the compliance gap's own side (US1, AS1/AS5)

**Goal**: Verify FR-007 reverse direction, contracts.md.

```bash
curl -s \
  "http://localhost:8001/api/v1/compliance/controls/$CONTROL_ID/mappings/applications/$APP_ID/initiatives" \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert d['total'] == 1
assert d['items'][0]['id'] == '$INITIATIVE_ID'
print('OK: the compliance gap itself shows which Initiative is remediating it')
"
```

## Scenario 4: Reverse lookup is gated the same as the underlying mapping (FR-013)

**Goal**: Verify a `REVIEWER`-role caller lacking `READ_APPLICATION_GOVERNANCE` cannot see the
Application-targeted reverse lookup, mirroring COMPLY-02's own gating.

```bash
# Via a role-overridden TestClient in tests/authz/test_enforcement.py (no dev-mode X-Role header
# exists in this codebase — 921's own established verification approach), not curl:
#   REVIEWER role -> GET .../mappings/applications/{app_id}/initiatives -> 403
```

## Scenario 5: Unlink removes the link without touching either side (US1 AS4 / US2 AS3)

```bash
curl -s -X DELETE \
  "http://localhost:8001/api/v1/strategy/initiatives/$INITIATIVE_ID/control-mappings/applications/$CONTROL_ID/$APP_ID"
# Expect 204.
curl -s "http://localhost:8001/api/v1/strategy/initiatives" | python3 -c "
import sys, json
d = json.load(sys.stdin)
init = next(i for i in d['items'] if i['id'] == '$INITIATIVE_ID')
assert init['control_mappings'] == []
print('OK: unlinked; Initiative itself untouched')
"
```

## Scenario 6: ObjectiveControlMapping — why an objective exists (US2, AS1/AS2)

**Goal**: Verify FR-001, FR-002, FR-014 (multiplicity).

```bash
curl -s -X POST "http://localhost:8001/api/v1/strategy/objectives/$OBJECTIVE_ID/controls" \
  -H "Content-Type: application/json" -d "{\"control_id\": \"$CONTROL_ID\"}"
# Expect 201, body == updated control_ids list containing $CONTROL_ID.

curl -s -X POST "http://localhost:8001/api/v1/strategy/objectives/$OBJECTIVE_ID/controls" \
  -H "Content-Type: application/json" -d "{\"control_id\": \"$CONTROL_ID_2\"}"
# Expect 201, control_ids now has both.

curl -s "http://localhost:8001/api/v1/compliance/controls/$CONTROL_ID/objectives" | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert any(o['id'] == '$OBJECTIVE_ID' for o in d['items'])
print('OK: reverse lookup from the Control side sees the Objective')
"
```

## Scenario 7: Duplicate link rejected, missing entity 404s (FR-011, research.md D5)

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST \
  "http://localhost:8001/api/v1/strategy/objectives/$OBJECTIVE_ID/controls" \
  -H "Content-Type: application/json" -d "{\"control_id\": \"$CONTROL_ID\"}"
# Expect 409 (already linked from Scenario 6).

curl -s -o /dev/null -w "%{http_code}\n" -X POST \
  "http://localhost:8001/api/v1/strategy/initiatives/$INITIATIVE_ID/control-mappings/applications/$CONTROL_ID/does-not-exist"
# Expect 404 -- no ControlMapping row exists for that (control, target) pair yet.
```

## Scenario 8: Cascade delete removes dependent links, not the other side (FR-011, edge cases)

```bash
curl -s -X DELETE "http://localhost:8001/api/v1/compliance/controls/$CONTROL_ID"
# Deletes the Control -- cascades to objective_control_links and every
# initiative_control_*_mapping row referencing it (via control_*_mapping's own cascade).

curl -s "http://localhost:8001/api/v1/strategy/objectives/$OBJECTIVE_ID" | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert '$CONTROL_ID' not in d['control_ids']
print('OK: Objective itself survives; only the dangling link is gone')
"
```

---

**Cleanup**: delete any temporary Framework/Control/Objective/Initiative created for these scenarios;
leave pre-existing real data untouched (matches every prior COMPLY-0x verification pass in this session's
history).
