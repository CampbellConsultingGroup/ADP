# Quickstart: Requirements Intake

**Branch**: `014-requirements-intake-ui` | **Date**: 2026-07-02
**Prerequisites**: ADP API on :8001 with ADP_DATABASE_URL set; DESIGN-001 exists

---

## Extract Requirements from Text (Bulk Mode)

```bash
# Step 1: Submit text
OP=$(curl -s -X POST http://localhost:8001/api/v1/designs/DESIGN-001/intake \
  -H "Content-Type: application/json" \
  -d '{"mode": "bulk_text", "text": "The system must handle 10,000 concurrent users. The API must be stateless and respond within 200ms at p99. All data at rest must be encrypted."}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['operation_id'])")
echo "Operation: $OP"

# Step 2: Poll until completed
while true; do
  STATUS=$(curl -s http://localhost:8001/api/v1/designs/DESIGN-001/intake/$OP \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['status'])")
  echo "Status: $STATUS"
  if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then break; fi
  sleep 2
done

# Step 3: View proposals
curl -s http://localhost:8001/api/v1/designs/DESIGN-001/intake/$OP \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
for p in d['proposals']:
    print(f\"{p['proposal_id'][:8]}... [{p['kind']}] {p['confidence']:.0%}\")
    print(f\"  Statement: {p['draft_statement']}\")
    print(f\"  Source:    {p['source_excerpt']}\")
    print()
"
```

---

## Confirm a Proposal

```bash
# Confirm as-is
curl -s -X POST \
  http://localhost:8001/api/v1/designs/DESIGN-001/intake/$OP/proposals/{PROPOSAL_ID}/confirm \
  -H "Content-Type: application/json" \
  -d '{}' | python3 -m json.tool

# Confirm with edits
curl -s -X POST \
  http://localhost:8001/api/v1/designs/DESIGN-001/intake/$OP/proposals/{PROPOSAL_ID}/confirm \
  -H "Content-Type: application/json" \
  -d '{"edited_statement": "The system MUST handle 10,000 concurrent users with p99 latency < 200ms"}' \
  | python3 -m json.tool
```

---

## Reject a Proposal

```bash
curl -s -X POST \
  http://localhost:8001/api/v1/designs/DESIGN-001/intake/$OP/proposals/{PROPOSAL_ID}/reject \
  -H "Content-Type: application/json" \
  -d '{}'
```

---

## Add a Requirement Directly (Structured Form)

```bash
curl -s -X POST http://localhost:8001/api/v1/designs/DESIGN-001/requirements \
  -H "Content-Type: application/json" \
  -d '{"statement": "The API must use OAuth 2.0 for authentication", "kind": "non_functional"}' \
  | python3 -m json.tool
```

---

## List All Requirements for a Design

```bash
curl -s http://localhost:8001/api/v1/designs/DESIGN-001/requirements | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f'Total: {d[\"total\"]}')
for r in d['requirements']:
    print(f'  {r[\"id\"]} [{r[\"kind\"]}]: {r[\"title\"]}')
    if r['satisfies']:
        print(f'    Satisfied by: {r[\"satisfies\"]}')
"
```

---

## Web Screen

Navigate to `http://localhost:5173/designs/DESIGN-001/intake` after starting the Vite dev server.

Or click **Requirements** in the workspace header at `http://localhost:5173/designs/DESIGN-001`.
