# Quickstart: Business Domain Registry and Stage-Capability Mapping (ADP-SPEC-035)

Assumes API at `http://localhost:8001` with `ADP_AUTH_ENABLED=false`.

## Scenario 1: Create a domain

```bash
curl -s -X POST http://localhost:8001/api/v1/business/domains \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Customer",
    "scope_statement": "In: identity, preferences, contact. Out: billing, collections.",
    "classification": "strategic",
    "org_unit": "Customer Experience",
    "risk_flags": ["PII", "GDPR"]
  }' | python3 -m json.tool
# Expect: 201 with id, name, classification, risk_flags
```

## Scenario 2: List domains

```bash
curl -s http://localhost:8001/api/v1/business/domains | python3 -m json.tool
# Expect: items array ordered by name, each with capability_count (0 initially)
```

## Scenario 3: Create a second domain and get domain detail

```bash
DOMAIN_ID=$(curl -s -X POST http://localhost:8001/api/v1/business/domains \
  -H "Content-Type: application/json" \
  -d '{"name":"Order","classification":"differentiating","org_unit":"Supply Chain"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

curl -s http://localhost:8001/api/v1/business/domains/$DOMAIN_ID | python3 -m json.tool
# Expect: full domain fields + capabilities: []
```

## Scenario 4: Assign an L1 capability to a domain

```bash
# First, create an L1 capability
CAP_ID=$(curl -s -X POST http://localhost:8001/api/v1/business/capabilities \
  -H "Content-Type: application/json" \
  -d '{"name":"Customer Engagement","level":1}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# Assign to Customer domain
curl -s -X PATCH "http://localhost:8001/api/v1/business/capabilities/$CAP_ID/domain" \
  -H "Content-Type: application/json" \
  -d "{\"domain_id\": \"$DOMAIN_ID\"}" | python3 -m json.tool
# Expect: 200 with domain_id and domain_name set on the capability
```

## Scenario 5: Verify domain detail shows the capability

```bash
curl -s "http://localhost:8001/api/v1/business/domains/$DOMAIN_ID" | python3 -m json.tool
# Expect: capabilities array contains Customer Engagement
```

## Scenario 6: Reject L2 capability domain assignment

```bash
L2_CAP=$(curl -s -X POST http://localhost:8001/api/v1/business/capabilities \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"CRM\",\"level\":2,\"parent_id\":\"$CAP_ID\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

curl -s -o /dev/null -w "%{http_code}" \
  -X PATCH "http://localhost:8001/api/v1/business/capabilities/$L2_CAP/domain" \
  -H "Content-Type: application/json" \
  -d "{\"domain_id\": \"$DOMAIN_ID\"}"
# Expect: 422
```

## Scenario 7: Link a capability to a value stream stage

```bash
# Create value stream and stage
VS_ID=$(curl -s -X POST http://localhost:8001/api/v1/business/value-streams \
  -H "Content-Type: application/json" \
  -d '{"name":"Order-to-Cash"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

STAGE_ID=$(curl -s -X POST "http://localhost:8001/api/v1/business/value-streams/$VS_ID/stages" \
  -H "Content-Type: application/json" \
  -d '{"name":"Fulfil Order","position":0}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# Link capability to stage
curl -s -X POST "http://localhost:8001/api/v1/business/value-streams/$VS_ID/stages/$STAGE_ID/capabilities" \
  -H "Content-Type: application/json" \
  -d "{\"capability_id\": \"$CAP_ID\"}" | python3 -m json.tool
# Expect: 201 with items list containing Customer Engagement
```

## Scenario 8: 409 on duplicate stage-capability link

```bash
curl -s -o /dev/null -w "%{http_code}" \
  -X POST "http://localhost:8001/api/v1/business/value-streams/$VS_ID/stages/$STAGE_ID/capabilities" \
  -H "Content-Type: application/json" \
  -d "{\"capability_id\": \"$CAP_ID\"}"
# Expect: 409
```

## Scenario 9: Delete a domain; capability domain_id becomes null

```bash
# Create a throwaway domain and assign a capability
DEL_DOM=$(curl -s -X POST http://localhost:8001/api/v1/business/domains \
  -H "Content-Type: application/json" \
  -d '{"name":"ToDelete","classification":"commodity"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

CAP2=$(curl -s -X POST http://localhost:8001/api/v1/business/capabilities \
  -H "Content-Type: application/json" \
  -d '{"name":"Logistics","level":1}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

curl -s -X PATCH "http://localhost:8001/api/v1/business/capabilities/$CAP2/domain" \
  -H "Content-Type: application/json" \
  -d "{\"domain_id\": \"$DEL_DOM\"}" > /dev/null

# Delete the domain
curl -s -o /dev/null -w "%{http_code}" \
  -X DELETE "http://localhost:8001/api/v1/business/domains/$DEL_DOM"
# Expect: 204

# Capability survives with domain_id null
curl -s "http://localhost:8001/api/v1/business/capabilities/$CAP2" | python3 -m json.tool
# Expect: domain_id: null, domain_name: null
```

## Scenario 10: Browser — Domain tab on Business page

1. Open http://localhost:5173, navigate to Business
2. Click "Domains" tab — expect empty domain list with "Add Domain" button
3. Create a domain: name "Customer", classification "strategic", risk_flags "PII, GDPR"
4. Verify it appears in the list with `capability_count: 0`
5. Click the domain — see detail with empty capability list
6. Switch to Capabilities tab — see L1 nodes without domain badge
7. Click "Assign Domain" on an L1 capability — select "Customer" — verify badge appears
8. Return to Domains tab — domain detail shows the assigned capability

## Scenario 11: Browser — Stage-capability mapping

1. Navigate to Business → Value Streams → open "Order-to-Cash" → "Fulfil Order" stage
2. Expand the "Capabilities" section on the stage
3. Use picker to link "Customer Engagement" capability
4. Verify it appears in the linked list with domain badge "Customer"
5. Click Remove — verify the list is empty
