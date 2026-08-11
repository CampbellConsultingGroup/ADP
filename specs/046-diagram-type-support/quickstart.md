# Quickstart: Diagram Types Beyond C4 (ADP-SPEC-046)

Assumes API at `http://localhost:8001` with `ADP_AUTH_ENABLED=false` (so `X-Actor` drives the dev-convention actor identity, per `_get_actor`).

## Scenario 1: Create a flowchart diagram, starting empty (Edge Case — creatable before content exists)

```bash
DIAGRAM_ID=$(curl -s -X POST http://localhost:8001/api/v1/diagrams \
  -H "Content-Type: application/json" -H "X-Actor: alice" \
  -d '{"title":"Claims Intake Process","diagram_type":"flowchart"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "DIAGRAM_ID=$DIAGRAM_ID"

curl -s "http://localhost:8001/api/v1/diagrams/$DIAGRAM_ID" | python3 -m json.tool
# Expect: dsl_source == "", diagram_type == "flowchart"
```

## Scenario 2: Author content, save, and reopen with content intact (User Story 1)

```bash
curl -s -X PUT "http://localhost:8001/api/v1/diagrams/$DIAGRAM_ID" \
  -H "Content-Type: application/json" \
  -d '{"dsl_source":"flowchart LR\n  Start((Start)) --> Intake[Log claim]\n  Intake --> Review{Needs review?}\n  Review -->|Yes| Manual[Manual review]\n  Review -->|No| Approve[Auto-approve]\n"}' \
  | python3 -m json.tool

curl -s "http://localhost:8001/api/v1/diagrams/$DIAGRAM_ID" | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert 'Manual review' in d['dsl_source']
print('OK: content persisted')
"
```

## Scenario 3: Create one of each remaining type (sequence, ER, UML, cloud-architecture) — no type is second-class (Acceptance Scenario 3)

```bash
for TYPE in sequence erd uml architecture; do
  ID=$(curl -s -X POST http://localhost:8001/api/v1/diagrams \
    -H "Content-Type: application/json" \
    -d "{\"title\":\"Test $TYPE\",\"diagram_type\":\"$TYPE\"}" \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
  echo "$TYPE -> $ID"
done
```

## Scenario 4: Invalid DSL is rejected clearly (Edge Case — no silent invalid save)

This is enforced entirely client-side (research.md Decision 2) — the vendored `dslFamilies[type].parse()` function runs in the browser before a save is even attempted; the backend never re-validates DSL syntax, only the size cap. Verify at the frontend layer:

```bash
cd web && npx vitest run src/diagrams/core/dsl/flowchart-parser.test.ts
# Expect: malformed-syntax test cases (translated from the vendored library's
# own existing tests) return a parse error, not a silently-accepted empty model.
```

## Scenario 5: List all diagrams (User Story 3 — global, not Design-scoped)

```bash
curl -s http://localhost:8001/api/v1/diagrams | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"{data['total']} diagrams:\")
for item in data['items']:
    print(f\"  {item['diagram_type']:12s} {item['title']}\")
"
# Expect: every diagram created in Scenarios 1-3 appears, regardless of type.
```

## Scenario 6: PNG export via the new endpoint (User Story 2, Decision 3)

```bash
# In practice the SVG comes from the browser's vendored svg-renderer.ts output;
# here a minimal hand-written SVG stands in for it.
curl -s -X POST "http://localhost:8001/api/v1/diagrams/$DIAGRAM_ID/export" \
  -H "Content-Type: application/json" \
  -d '{"svg":"<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"100\" height=\"100\"><rect width=\"100\" height=\"100\" fill=\"blue\"/></svg>"}' \
  -o /tmp/diagram-export.png
file /tmp/diagram-export.png
# Expect: "PNG image data, 100 x 100"
```

## Scenario 7: Delete a diagram, confirm it's gone (no `confirmation_id` gate)

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X DELETE "http://localhost:8001/api/v1/diagrams/$DIAGRAM_ID"
# Expect: 204

curl -s -o /dev/null -w "%{http_code}\n" "http://localhost:8001/api/v1/diagrams/$DIAGRAM_ID"
# Expect: 404
```

## Scenario 8: Existing C4 workspace is unaffected (SC-003 — zero regression)

```bash
pytest tests/ --ignore=tests/integration -q
cd web && npm run test:run
# Expect: unchanged pass rate from before this feature (plus this feature's
# own new tests) — nothing in web/src/canvas/ or adp.renderer imports
# anything from web/src/diagrams/ or adp.diagrams. Note: web/src/canvas/ (C4)
# has no dedicated test files of its own to filter to (`-k "c4 or canvas"`
# / `vitest run src/canvas` both find nothing to run) -- the full suite is
# the actual regression check.
```
