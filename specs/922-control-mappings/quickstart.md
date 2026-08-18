# Quickstart / Integration Scenarios: Control Mappings (Traceability Links) — COMPLY-02

**Feature**: 922-control-mappings
**Date**: 2026-08-18

These scenarios drive integration tests and manual acceptance verification. Assumes the API at
`http://localhost:8001` with `ADP_AUTH_ENABLED=false` (dev convention — role defaults to
`ENTERPRISE_ARCHITECT`, which holds every action, including `READ_APPLICATION_GOVERNANCE`), a
`RegulatoryFramework`/`Control` already registered (COMPLY-01), and at least one existing `Application`
and `Capability`.

---

## Scenario 1: Map a control to an Application with evidence (US1, Acceptance Scenario 1)

**Goal**: Verify FR-001, FR-004, FR-005.

```bash
curl -s -X PUT "http://localhost:8001/api/v1/compliance/controls/$CONTROL_ID/mappings/applications/$APP_ID" \
  -H "Content-Type: application/json" \
  -d '{"compliance_status":"compliant","evidence_ref":"https://docs.example.com/mfa-rollout","assessed_at":"2026-08-18","assessed_by":"alice"}' \
  | python3 -m json.tool
# Expect: 200, target_type == "application", compliance_status == "compliant"

curl -s "http://localhost:8001/api/v1/applications/$APP_ID/compliance-mappings" | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert d['total'] == 1
assert d['items'][0]['control_id'] == '$CONTROL_ID'
print('OK: mapping visible from the Application side')
"

curl -s "http://localhost:8001/api/v1/compliance/controls/$CONTROL_ID/mappings" | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert any(m['target_type'] == 'application' and m['target_id'] == '$APP_ID' for m in d['items'])
print('OK: mapping visible from the Control side')
"
```

---

## Scenario 2: Map without evidence yet (US1, Acceptance Scenario 2)

**Goal**: Verify FR-004 — evidence is not required.

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X PUT \
  "http://localhost:8001/api/v1/compliance/controls/$CONTROL_ID/mappings/capabilities/$CAP_ID" \
  -H "Content-Type: application/json" -d '{"compliance_status":"not_assessed"}'
# Expect: 200
```

---

## Scenario 3: Estate-wide obligation mapping (US1, Acceptance Scenario 3)

**Goal**: Verify FR-002 — GDPR Art. 30-style standing obligations.

```bash
curl -s -X PUT "http://localhost:8001/api/v1/compliance/controls/$ART30_ID/mappings/organization" \
  -H "Content-Type: application/json" \
  -d '{"compliance_status":"partial","evidence_ref":"records-of-processing-register-v3.xlsx"}' \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert d['target_type'] == 'organization'
assert d['target_id'] is None
print('OK: estate-wide mapping recorded with no single target entity')
"
```

---

## Scenario 4: Same control, multiple independent targets (US1, Acceptance Scenario 4)

**Goal**: Verify FR-006, FR-007 — mapping to a second Application doesn't touch the first.

```bash
curl -s -X PUT "http://localhost:8001/api/v1/compliance/controls/$CONTROL_ID/mappings/applications/$APP2_ID" \
  -H "Content-Type: application/json" -d '{"compliance_status":"non_compliant"}' > /dev/null

curl -s "http://localhost:8001/api/v1/compliance/controls/$CONTROL_ID/mappings" | python3 -c "
import sys, json
d = json.load(sys.stdin)
by_app = {m['target_id']: m['compliance_status'] for m in d['items'] if m['target_type'] == 'application'}
assert by_app['$APP_ID'] == 'compliant'
assert by_app['$APP2_ID'] == 'non_compliant'
print('OK: two independent Application mappings for the same Control')
"
```

---

## Scenario 5: Re-mapping updates in place, never duplicates (US2, Acceptance Scenarios 1–2; FR-007/FR-008; SC-005)

```bash
curl -s -X PUT "http://localhost:8001/api/v1/compliance/controls/$CONTROL_ID/mappings/applications/$APP_ID" \
  -H "Content-Type: application/json" \
  -d '{"compliance_status":"non_compliant","evidence_ref":"gap-found-2026-08-18"}' > /dev/null

curl -s "http://localhost:8001/api/v1/compliance/controls/$CONTROL_ID/mappings" | python3 -c "
import sys, json
d = json.load(sys.stdin)
app_rows = [m for m in d['items'] if m['target_type'] == 'application' and m['target_id'] == '$APP_ID']
assert len(app_rows) == 1, app_rows  # never duplicated
assert app_rows[0]['compliance_status'] == 'non_compliant'
assert app_rows[0]['evidence_ref'] == 'gap-found-2026-08-18'
print('OK: re-mapping updated the existing row, no duplicate created')
"

# Update only evidence_ref, status unaffected
curl -s -X PUT "http://localhost:8001/api/v1/compliance/controls/$CONTROL_ID/mappings/applications/$APP_ID" \
  -H "Content-Type: application/json" -d '{"compliance_status":"non_compliant","evidence_ref":"remediation-in-progress"}' \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert d['compliance_status'] == 'non_compliant'
assert d['evidence_ref'] == 'remediation-in-progress'
print('OK: evidence_ref updated independently')
"
```

---

## Scenario 6: Sensitive read gating — Application mappings require READ_APPLICATION_GOVERNANCE (US3, Acceptance Scenario 3; SC-006)

Exercised via a role-overridden `TestClient`, not plain curl (no `X-Role` dev-mode override header exists
anywhere in this codebase — confirmed by direct grep, same finding as COMPLY-01's own quickstart):

```bash
.venv/bin/python -m pytest tests/authz/test_enforcement.py -k compliance_mapping -v
# Expect:
#   test_reviewer_denied_application_mapping_read PASSED (403 for a role lacking READ_APPLICATION_GOVERNANCE
#     on GET /applications/{id}/compliance-mappings)
#   test_control_mappings_forward_lookup_filters_application_rows PASSED (a caller without
#     READ_APPLICATION_GOVERNANCE sees Capability/Design/Pattern/organization rows on
#     GET /compliance/controls/{id}/mappings but not Application rows — not a 403 on the whole response)
```

Capability/Design/Pattern/organization-targeted mappings stay open regardless of role:

```bash
curl -s -o /dev/null -w "%{http_code}\n" \
  "http://localhost:8001/api/v1/business/capabilities/$CAP_ID/compliance-mappings"
# Expect: 200
```

---

## Scenario 7: Deletion cascades (Edge Cases — Control or target entity removed)

```bash
curl -s -X DELETE "http://localhost:8001/api/v1/compliance/controls/$CONTROL_ID" -o /dev/null -w "%{http_code}\n"
# Expect: 204 (COMPLY-01's existing delete endpoint)

curl -s -o /dev/null -w "%{http_code}\n" \
  "http://localhost:8001/api/v1/compliance/controls/$CONTROL_ID/mappings"
# Expect: 404 — control no longer exists, and every mapping that referenced it is gone with it (verified
# directly against the database in the integration test, not just via this now-404 endpoint)
```

---

## Scenario 8: Manual mapping deletion (research.md D6)

```bash
curl -s -X DELETE \
  "http://localhost:8001/api/v1/compliance/controls/$CONTROL_ID/mappings/capabilities/$CAP_ID" \
  -o /dev/null -w "%{http_code}\n"
# Expect: 204

curl -s -X DELETE \
  "http://localhost:8001/api/v1/compliance/controls/$CONTROL_ID/mappings/capabilities/$CAP_ID" \
  -o /dev/null -w "%{http_code}\n"
# Expect: 404 (already removed)
```

---

## Scenario 9: Pattern target must have kind == "pattern" (research.md D5)

```bash
# STANDARD_ITEM_ID references an existing knowledge_items row with kind == "standard", not "pattern"
curl -s -o /dev/null -w "%{http_code}\n" -X PUT \
  "http://localhost:8001/api/v1/compliance/controls/$CONTROL_ID/mappings/patterns/$STANDARD_ITEM_ID" \
  -H "Content-Type: application/json" -d '{"compliance_status":"not_assessed"}'
# Expect: 422
```
