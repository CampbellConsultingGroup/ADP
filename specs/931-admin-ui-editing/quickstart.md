# Quickstart: Admin UI for Editing Scoring Rubric Weights

Assumes API at `http://localhost:8001` with a `PLATFORM_ADMIN`-role token (or
`ADP_AUTH_ENABLED=false` for local no-auth testing).

## Scenario 1: List the one registered rubric, not yet overridden

```bash
curl -s http://localhost:8001/api/v1/admin/scoring-rubrics | python3 -m json.tool
# Expect: 1 item (business_value), is_override: false, version: 0, active_weights matching
# BUSINESS_VALUE_WEIGHTS exactly (0.25/0.25/0.15/0.15/0.10/0.10)
```

## Scenario 2: Edit rejected without confirmation_id

```bash
curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:8001/api/v1/admin/scoring-rubrics/business_value/confirm \
  -H "Content-Type: application/json" \
  -d '{"weights": {"strategic_alignment": 0.30, "revenue_cost_impact": 0.20, "customer_stakeholder_impact": 0.15, "competitive_differentiation": 0.10, "risk_compliance_contribution": 0.15, "evidence_measurability": 0.10}, "expected_version": 0}'
# Expect: 422 (missing confirmation_id)
```

## Scenario 3: Weight set that doesn't sum to 1.0 is rejected

```bash
curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:8001/api/v1/admin/scoring-rubrics/business_value/confirm \
  -H "Content-Type: application/json" \
  -d '{"weights": {"strategic_alignment": 0.30, "revenue_cost_impact": 0.20, "customer_stakeholder_impact": 0.15, "competitive_differentiation": 0.10, "risk_compliance_contribution": 0.15, "evidence_measurability": 0.05}, "expected_version": 0, "confirmation_id": "CONFIRM-bv-badsum"}'
# Expect: 422 (sums to 0.95, not 1.0)
```

## Scenario 4: Confirmed edit takes effect for a real assessment (FR-005, FR-008)

```bash
curl -s -X POST http://localhost:8001/api/v1/admin/scoring-rubrics/business_value/confirm \
  -H "Content-Type: application/json" \
  -d '{"weights": {"strategic_alignment": 0.50, "revenue_cost_impact": 0.10, "customer_stakeholder_impact": 0.10, "competitive_differentiation": 0.10, "risk_compliance_contribution": 0.10, "evidence_measurability": 0.10}, "expected_version": 0, "confirmation_id": "CONFIRM-bv-1"}' \
  | python3 -m json.tool
# Expect: 200, is_override reflected, version: 1

APP_ID=$(curl -s -X POST http://localhost:8001/api/v1/applications \
  -H "Content-Type: application/json" -d '{"name":"Rubric Weight Live Test"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

curl -s -X PUT "http://localhost:8001/api/v1/applications/$APP_ID/business-value-assessment" \
  -H "Content-Type: application/json" \
  -d '{"strategic_alignment":5,"revenue_cost_impact":1,"customer_stakeholder_impact":1,"competitive_differentiation":1,"risk_compliance_contribution":1,"evidence_measurability":5}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['result']['weighted_average'])"
# Expect: 3.4 -- with the overridden weights above (strategic_alignment=0.50, all
# other 5 dimensions=0.10 each), raw = 5*0.50 + 1*0.10 + 1*0.10 + 1*0.10 + 1*0.10
# + 5*0.10 = 2.5 + 0.9 = 3.4. Under the DEFAULT weights (0.25/0.25/0.15/0.15/
# 0.10/0.10) the same scores would instead average to 5*0.25 + 1*0.25 + 1*0.15
# + 1*0.10 + 1*0.15 + 5*0.10 = 1.25+0.25+0.15+0.10+0.15+0.50 = 2.4 -- confirming
# the override is genuinely wired into compute_business_value_score() via
# get_effective_weights(), not stored inertly.
```

## Scenario 5: Concurrent-edit conflict surfaced, not silently overwritten (FR-005)

```bash
curl -s -X POST http://localhost:8001/api/v1/admin/scoring-rubrics/business_value/confirm \
  -H "Content-Type: application/json" \
  -d '{"weights": {"strategic_alignment": 0.25, "revenue_cost_impact": 0.25, "customer_stakeholder_impact": 0.15, "competitive_differentiation": 0.10, "risk_compliance_contribution": 0.15, "evidence_measurability": 0.10}, "expected_version": 1, "confirmation_id": "CONFIRM-bv-2"}' > /dev/null

curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:8001/api/v1/admin/scoring-rubrics/business_value/confirm \
  -H "Content-Type: application/json" \
  -d '{"weights": {"strategic_alignment": 0.40, "revenue_cost_impact": 0.15, "customer_stakeholder_impact": 0.15, "competitive_differentiation": 0.10, "risk_compliance_contribution": 0.10, "evidence_measurability": 0.10}, "expected_version": 1, "confirmation_id": "CONFIRM-bv-stale"}'
# Expect: 409 (expected_version=1 is stale -- the version above is now 2)
```

## Scenario 6: History + restore

```bash
curl -s http://localhost:8001/api/v1/admin/scoring-rubrics/business_value/history | python3 -m json.tool
# Expect: 2 entries, newest first, change_type "edit" both times

# Restore the very first (version 1) weights:
HIST_ID=$(curl -s http://localhost:8001/api/v1/admin/scoring-rubrics/business_value/history \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['items'][-1]['id'])")

curl -s -X POST "http://localhost:8001/api/v1/admin/scoring-rubrics/business_value/restore/$HIST_ID" \
  -H "Content-Type: application/json" \
  -d '{"expected_version": 2, "confirmation_id": "CONFIRM-bv-restore"}' | python3 -m json.tool
# Expect: 200, version: 3, weights matching the very first edit's weights
```

## Scenario 7: Permission denial

```bash
# With a non-PLATFORM_ADMIN token/role:
curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/api/v1/admin/scoring-rubrics \
  -H "Authorization: Bearer <non-admin-token>"
# Expect: 403
```

## Cleanup

```bash
curl -s -X DELETE "http://localhost:8001/api/v1/applications/$APP_ID" -w "\nHTTP:%{http_code}\n"
# Restore business_value to its true hardcoded default afterward if desired --
# there is no "clear override" endpoint in v1 (mirrors ADP-SPEC-042's own scope:
# restore-to-fallback is out of v1, per that spec's Assumptions) -- manually
# restore to a weight set matching BUSINESS_VALUE_WEIGHTS instead.
```
