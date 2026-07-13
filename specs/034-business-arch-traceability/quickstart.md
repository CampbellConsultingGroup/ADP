# Quickstart: Business Architecture Traceability (ADP-SPEC-034)

**Feature**: 034-business-arch-traceability  
**Generated**: 2026-07-10  
**Prerequisites**: API server running at `http://localhost:8001`, ADP-SPEC-033 capabilities and value streams seeded.

---

## Setup: Seed Required Entities

Before running any scenario, ensure you have:

```bash
# 1. Create a capability to link
CAP=$(curl -sf -X POST http://localhost:8001/api/v1/business/capabilities \
  -H "Content-Type: application/json" \
  -d '{"name": "Order Processing", "level": 1}' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# 2. Create a value stream to link
VS=$(curl -sf -X POST http://localhost:8001/api/v1/business/value-streams \
  -H "Content-Type: application/json" \
  -d '{"name": "Order to Cash", "stakeholder": "Finance"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# 3. Get a design ID (use one that already exists)
DES=$(curl -sf "http://localhost:8001/api/v1/designs?page_size=1" | python3 -c "import sys,json; print(json.load(sys.stdin)['designs'][0]['id'])")

echo "CAP=$CAP  VS=$VS  DES=$DES"
```

---

## Scenario 1: Link a Design to a Capability

```bash
# Link the design to the capability
curl -sf -X POST "http://localhost:8001/api/v1/business/capabilities/$CAP/designs" \
  -H "Content-Type: application/json" \
  -d "{\"design_id\": \"$DES\"}" | python3 -m json.tool

# Expected: 201 with items list containing the design
# Verify: the design appears in the linked list
curl -sf "http://localhost:8001/api/v1/business/capabilities/$CAP/designs" | python3 -m json.tool
```

**Assertion**: Response `items[0].design_id == $DES`.

---

## Scenario 2: Duplicate Link Returns 409

```bash
# Attempt to link the same design again
curl -sf -o /dev/null -w "%{http_code}" \
  -X POST "http://localhost:8001/api/v1/business/capabilities/$CAP/designs" \
  -H "Content-Type: application/json" \
  -d "{\"design_id\": \"$DES\"}"
```

**Assertion**: HTTP 409.

---

## Scenario 3: Reverse Lookup — Design Business Context

```bash
# Get all capabilities and value streams for the design
curl -sf "http://localhost:8001/api/v1/business/designs/$DES/context" | python3 -m json.tool
```

**Assertion**: `capabilities[0].capability_id == $CAP`. `value_streams` is empty (not yet linked).

---

## Scenario 4: Link a Design to a Value Stream

```bash
# Link the design to the value stream
curl -sf -X POST "http://localhost:8001/api/v1/business/value-streams/$VS/designs" \
  -H "Content-Type: application/json" \
  -d "{\"design_id\": \"$DES\"}" | python3 -m json.tool

# Re-check design context — should now show both capability and value stream
curl -sf "http://localhost:8001/api/v1/business/designs/$DES/context" | python3 -m json.tool
```

**Assertion**: `capabilities` has 1 entry, `value_streams` has 1 entry.

---

## Scenario 5: Remove a Capability–Design Link

```bash
# Remove the link
curl -sf -o /dev/null -w "%{http_code}" \
  -X DELETE "http://localhost:8001/api/v1/business/capabilities/$CAP/designs/$DES"

# Verify removed from capability's list
curl -sf "http://localhost:8001/api/v1/business/capabilities/$CAP/designs" | python3 -m json.tool

# Verify removed from design's context
curl -sf "http://localhost:8001/api/v1/business/designs/$DES/context" | python3 -m json.tool
```

**Assertions**: DELETE returns 204. Capability list `items` is empty. Design context `capabilities` is empty.

---

## Scenario 6: Cascade on Capability Delete — No Orphan Links

```bash
# Re-link the design
curl -sf -X POST "http://localhost:8001/api/v1/business/capabilities/$CAP/designs" \
  -H "Content-Type: application/json" \
  -d "{\"design_id\": \"$DES\"}"

# Delete the capability
curl -sf -o /dev/null -w "%{http_code}" \
  -X DELETE "http://localhost:8001/api/v1/business/capabilities/$CAP"

# Verify design context no longer references deleted capability
curl -sf "http://localhost:8001/api/v1/business/designs/$DES/context" | python3 -m json.tool
```

**Assertion**: Design context `capabilities` is empty (cascade removed the link).

---

## Scenario 7 (Browser): Business Context Panel in IntakePage

1. Open `http://localhost:5173`
2. Select a design (or create one)
3. Navigate to the design's intake view (click "Intake" tab)
4. Observe the "Business Context" section at the bottom — if no links exist, it shows an empty state with a link to the Business page
5. Open the Business page → Capabilities tab → select a capability → expand "Linked Designs" → add the current design
6. Return to the design's intake view — the "Business Context" section now shows the capability name with a link to the Business page

---

## Scenario 8 (Browser): Capability Tree — Linked Designs Inline

1. Open Business page → Capabilities tab
2. Expand a Level 1 capability row (click the capability's "Links" button)
3. Click "+ Link Design" → a design picker appears
4. Select a design from the dropdown list → confirm
5. The design appears in the inline "Linked Designs" panel under the capability
6. Click the trash icon next to the design to remove it
7. The linked designs panel returns to empty state
