# Quickstart: Application Registry (ADP-SPEC-036)

Assumes API at `http://localhost:8001` with `ADP_AUTH_ENABLED=false`.

## Scenario 1: Create an application

```bash
APP_A=$(curl -s -X POST http://localhost:8001/api/v1/applications \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Customer Portal",
    "vendor": "Acme Corp",
    "primary_owner": "Platform Team",
    "time_classification": "Invest",
    "r_strategy": "Refactor",
    "pace_layer": "Differentiation",
    "health_score": 4
  }' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "App A: $APP_A"
# Expect: 201 with UUID id and all supplied fields
```

## Scenario 2: Validation — blank name

```bash
curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:8001/api/v1/applications \
  -H "Content-Type: application/json" \
  -d '{"name": "   "}'
# Expect: 422
```

## Scenario 3: Validation — invalid TIME classification

```bash
curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:8001/api/v1/applications \
  -H "Content-Type: application/json" \
  -d '{"name": "Test", "time_classification": "Spend"}'
# Expect: 422
```

## Scenario 4: Validation — health_score out of range

```bash
curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:8001/api/v1/applications \
  -H "Content-Type: application/json" \
  -d '{"name": "Test", "health_score": 6}'
# Expect: 422
```

## Scenario 5: List applications (ordered by name)

```bash
curl -s -X POST http://localhost:8001/api/v1/applications \
  -H "Content-Type: application/json" \
  -d '{"name": "Billing Service"}' > /dev/null

curl -s http://localhost:8001/api/v1/applications | python3 -m json.tool
# Expect: items ordered alphabetically — "Billing Service" before "Customer Portal"
```

## Scenario 6: Link application to a business capability with fit score

```bash
# Create or reuse an existing L1 business capability
CAP_ID=$(curl -s -X POST http://localhost:8001/api/v1/business/capabilities \
  -H "Content-Type: application/json" \
  -d '{"name":"Customer Engagement","level":1}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

curl -s -X POST "http://localhost:8001/api/v1/applications/$APP_A/capability-links" \
  -H "Content-Type: application/json" \
  -d "{\"capability_id\": \"$CAP_ID\", \"fit_score\": 3}" | python3 -m json.tool
# Expect: 201 with capability_name "Customer Engagement" and fit_score 3
```

## Scenario 7: 409 on duplicate capability link

```bash
curl -s -o /dev/null -w "%{http_code}" \
  -X POST "http://localhost:8001/api/v1/applications/$APP_A/capability-links" \
  -H "Content-Type: application/json" \
  -d "{\"capability_id\": \"$CAP_ID\", \"fit_score\": 4}"
# Expect: 409
```

## Scenario 8: Update fit score

```bash
curl -s -X PATCH "http://localhost:8001/api/v1/applications/$APP_A/capability-links/$CAP_ID" \
  -H "Content-Type: application/json" \
  -d '{"fit_score": 5}' | python3 -m json.tool
# Expect: 200 with fit_score 5
```

## Scenario 9: Create technical capability hierarchy

```bash
TC_L1=$(curl -s -X POST http://localhost:8001/api/v1/technical-capabilities \
  -H "Content-Type: application/json" \
  -d '{"name":"Data Management"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

TC_L2=$(curl -s -X POST http://localhost:8001/api/v1/technical-capabilities \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"Structured Storage\",\"parent_id\":\"$TC_L1\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

TC_L3=$(curl -s -X POST http://localhost:8001/api/v1/technical-capabilities \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"Relational Database\",\"parent_id\":\"$TC_L2\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

echo "L1=$TC_L1 L2=$TC_L2 L3=$TC_L3"
# Expect: three UUIDs, levels auto-derived (1, 2, 3)
```

## Scenario 10: Reject depth > 3

```bash
curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:8001/api/v1/technical-capabilities \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"Too Deep\",\"parent_id\":\"$TC_L3\"}"
# Expect: 422 (parent is L3; max depth exceeded)
```

## Scenario 11: Reject deleting tech cap with children

```bash
curl -s -o /dev/null -w "%{http_code}" \
  -X DELETE "http://localhost:8001/api/v1/technical-capabilities/$TC_L2"
# Expect: 409 (has child $TC_L3)
```

## Scenario 12: Link application to technical capability (provides + consumes)

```bash
# provides
curl -s -X POST "http://localhost:8001/api/v1/applications/$APP_A/technical-capability-links" \
  -H "Content-Type: application/json" \
  -d "{\"tech_cap_id\": \"$TC_L3\", \"usage_type\": \"provides\"}" | python3 -m json.tool
# Expect: 201

# consumes (same tech cap, different usage_type — allowed)
curl -s -X POST "http://localhost:8001/api/v1/applications/$APP_A/technical-capability-links" \
  -H "Content-Type: application/json" \
  -d "{\"tech_cap_id\": \"$TC_L3\", \"usage_type\": \"consumes\"}" | python3 -m json.tool
# Expect: 201
```

## Scenario 13: Link application to a value stream stage

```bash
VS_ID=$(curl -s -X POST http://localhost:8001/api/v1/business/value-streams \
  -H "Content-Type: application/json" \
  -d '{"name":"Order-to-Cash"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

STAGE_ID=$(curl -s -X POST "http://localhost:8001/api/v1/business/value-streams/$VS_ID/stages" \
  -H "Content-Type: application/json" \
  -d '{"name":"Fulfil Order","position":0}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

curl -s -X POST "http://localhost:8001/api/v1/applications/$APP_A/stage-links" \
  -H "Content-Type: application/json" \
  -d "{\"stage_id\": \"$STAGE_ID\"}" | python3 -m json.tool
# Expect: 201 with stage_name "Fulfil Order"
```

## Scenario 14: Create application integration (A → B)

```bash
APP_B=$(curl -s -X POST http://localhost:8001/api/v1/applications \
  -H "Content-Type: application/json" \
  -d '{"name":"CRM System","time_classification":"Invest"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

INT_ID=$(curl -s -X POST http://localhost:8001/api/v1/integrations \
  -H "Content-Type: application/json" \
  -d "{
    \"source_app_id\": \"$APP_A\",
    \"target_app_id\": \"$APP_B\",
    \"integration_type\": \"API\",
    \"description\": \"Sync customer profiles\"
  }" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

echo "Integration: $INT_ID"
# Expect: 201 with source_app_name "Customer Portal" and target_app_name "CRM System"
```

## Scenario 15: Reject self-integration

```bash
curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:8001/api/v1/integrations \
  -H "Content-Type: application/json" \
  -d "{\"source_app_id\": \"$APP_A\", \"target_app_id\": \"$APP_A\", \"integration_type\": \"API\"}"
# Expect: 422
```

## Scenario 16: List integrations for an application

```bash
curl -s "http://localhost:8001/api/v1/integrations?app_id=$APP_A" | python3 -m json.tool
# Expect: both A→B integration appears; source_app_name and target_app_name populated
```

## Scenario 17: Create B→A integration (bidirectional permitted)

```bash
curl -s -X POST http://localhost:8001/api/v1/integrations \
  -H "Content-Type: application/json" \
  -d "{
    \"source_app_id\": \"$APP_B\",
    \"target_app_id\": \"$APP_A\",
    \"integration_type\": \"event\",
    \"description\": \"Order events pushed back\"
  }" | python3 -m json.tool
# Expect: 201 (B→A is permitted even when A→B already exists)
```

## Scenario 18: Delete application cascades all links

```bash
# Confirm APP_A has capability links, tech cap links, stage links, integrations
curl -s "http://localhost:8001/api/v1/applications/$APP_A/capability-links" | python3 -m json.tool

# Delete APP_A
curl -s -o /dev/null -w "%{http_code}" \
  -X DELETE "http://localhost:8001/api/v1/applications/$APP_A"
# Expect: 204

# Integration from A→B should be gone
curl -s "http://localhost:8001/api/v1/integrations?app_id=$APP_A" | python3 -m json.tool
# Expect: items: [], total: 0
```

## Scenario 19: Link application to a design

```bash
# Assumes at least one design exists in the system
DESIGN_ID=$(curl -s http://localhost:8001/api/v1/designs \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['items'][0]['id'])" 2>/dev/null || echo "")

if [ -n "$DESIGN_ID" ]; then
  APP_C=$(curl -s -X POST http://localhost:8001/api/v1/applications \
    -H "Content-Type: application/json" \
    -d '{"name":"Design-Linked App"}' \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

  curl -s -X POST "http://localhost:8001/api/v1/applications/$APP_C/design-links" \
    -H "Content-Type: application/json" \
    -d "{\"design_id\": \"$DESIGN_ID\"}" | python3 -m json.tool
  # Expect: 201

  curl -s "http://localhost:8001/api/v1/applications/$APP_C/design-links" | python3 -m json.tool
  # Expect: items array contains the design_id
else
  echo "No designs found — create a design first to test design linkage"
fi
```

## Scenario 20: Browser — Applications page

1. Open http://localhost:5173, navigate to "Applications" via the nav bar
2. Click "Add Application" — fill in name "Customer Portal", TIME "Invest", health score 4
3. Save and verify it appears in the list
4. Click the application — see detail with empty links sections
5. Click "Link Business Capability" — select a capability and enter fit score 3 — verify it appears with score
6. Click "Link Technical Capability" — select a tech cap, choose "provides" — verify usage_type shown
7. Navigate to "Integrations" section — add an integration to "CRM System" of type "API"
8. Verify integration appears with source/target names

## Scenario 21: Browser — Technical Capabilities management

1. Navigate to "Technical Capabilities" (sub-page or tab)
2. Create L1 "Data Management"
3. Under it, create L2 "Structured Storage"
4. Under that, create L3 "Relational Database"
5. Verify hierarchy is displayed
6. Attempt to add an L4 under Relational Database — verify rejection message
7. Delete "Relational Database" (leaf) — verify L1 and L2 remain
