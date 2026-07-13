# Quickstart: Architecture Recommendation Screen

**Branch**: `018-recommendation-screen` | **Date**: 2026-07-02
**Prerequisites**: ADP running on :8001; DESIGN-001 exists with ≥ 1 confirmed requirement

---

## Request Recommendations

```bash
# Start the pipeline
OP=$(curl -s -X POST http://localhost:8001/api/v1/designs/DESIGN-001/recommend \
  -H "Content-Type: application/json" \
  -d '{"requirement_ids": ["REQ-001", "REQ-002", "REQ-003"]}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['operation_id'])")
echo "Operation: $OP"

# Poll until completed
while true; do
  STATUS=$(curl -s "http://localhost:8001/api/v1/designs/DESIGN-001/recommend/$OP" \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['status'])")
  echo "Status: $STATUS"
  [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ] && break
  sleep 3
done

# View options
curl -s "http://localhost:8001/api/v1/designs/DESIGN-001/recommend/$OP" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f'Summary: {d[\"result_summary\"]}')
for o in d['options']:
    adv = ' [ADVISORY]' if o['advisory'] else ''
    print(f'  #{o[\"rank\"]} {o[\"title\"]}{adv}  score={o[\"ranking_score\"]:.2f}')
    for tf in o['trade_offs']:
        icon = {'meets':'✅','partially_meets':'⚠️','does_not_meet':'❌'}[tf['stance']]
        print(f'    {icon} {tf[\"criterion\"]}')
    print(f'    Proposed: {[e[\"name\"] for e in o[\"proposed_elements\"]]}')
"
```

---

## Accept an Option

```bash
OPT_ID=$(curl -s "http://localhost:8001/api/v1/designs/DESIGN-001/recommend/$OP" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['options'][0]['option_id'])")

# Accept with confirmation (ART-VIII)
curl -s -X POST \
  "http://localhost:8001/api/v1/designs/DESIGN-001/recommend/$OP/options/$OPT_ID/accept" \
  -H "Content-Type: application/json" \
  -d '{"confirmation_id": "ACCEPT-DESIGN-001", "advisory_acknowledged": false}' \
  | python3 -m json.tool

# For advisory options, set advisory_acknowledged=true
```

---

## Web Screen

Navigate to `http://localhost:5173` → Intake screen → click **[Recommendations]** in the nav header → select requirements → click **Get Recommendations** → review options → click **Accept this option** on your preferred option.

---

## What Happens With an Empty Knowledge Base

If the knowledge base has not been indexed (`adp-reindex` has not been run):
- All options will have `advisory: true`
- The advisory warning is displayed on each option card
- You must check "I understand this option lacks full knowledge-base grounding" before accepting
- Accepting still materialises elements — they'll have valid provenance links but grounding citations will be empty

To populate the knowledge base, run `adp-reindex` with a configured Git source containing architecture patterns.
