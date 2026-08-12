# Quickstart: Strategy Domain Card on the Overview Dashboard

Assumes the API is running at `http://localhost:8001` with `ADP_AUTH_ENABLED=false` (dev
convention).

## Scenario 1: Empty state (User Story 1, Acceptance Scenario 3)

Against a fresh database with no strategic objectives or themes:

```bash
curl -s http://localhost:8001/api/v1/strategy/summary | python3 -m json.tool
# Expect: every field 0, HTTP 200 — no error.
```

## Scenario 2: Mini-stats reflect real counts (User Story 1, Acceptance Scenario 1)

```bash
curl -s -X POST http://localhost:8001/api/v1/strategy/themes \
  -H "Content-Type: application/json" -d '{"name":"Growth"}'

THEME_ID=$(curl -s http://localhost:8001/api/v1/strategy/themes | python3 -c "import sys,json; print(json.load(sys.stdin)['items'][0]['id'])")

curl -s -X POST http://localhost:8001/api/v1/strategy/objectives \
  -H "Content-Type: application/json" \
  -d "{\"theme_id\":\"$THEME_ID\",\"owner\":\"Team A\",\"statement\":\"Grow revenue\",\"fiscal_year\":2026,\"period\":\"Q3\"}"

curl -s http://localhost:8001/api/v1/strategy/summary | python3 -m json.tool
# Expect: total_objectives=1, total_themes=1.
```

## Scenario 3: Linkage split (User Story 2)

```bash
OBJ_ID=$(curl -s http://localhost:8001/api/v1/strategy/objectives | python3 -c "import sys,json; print(json.load(sys.stdin)['items'][0]['id'])")
CAP_ID=$(curl -s http://localhost:8001/api/v1/business/capabilities | python3 -c "import sys,json; print(json.load(sys.stdin)['items'][0]['id'])")

# Before linking: this objective counts as unlinked.
curl -s http://localhost:8001/api/v1/strategy/summary | python3 -m json.tool
# Expect: unlinked_count includes this objective.

curl -s -X POST "http://localhost:8001/api/v1/strategy/objectives/$OBJ_ID/capabilities" \
  -H "Content-Type: application/json" -d "{\"capability_id\":\"$CAP_ID\"}"

curl -s http://localhost:8001/api/v1/strategy/summary | python3 -m json.tool
# Expect: this objective now counts in linked_count, not unlinked_count
# (a capability-only link is sufficient — spec.md FR-005).
```

## Scenario 4: Fiscal-period bucketing anchored to the server clock (User Story 3)

```bash
CURRENT_YEAR=$(date +%Y)

# An objective in the current calendar quarter.
curl -s -X POST http://localhost:8001/api/v1/strategy/objectives \
  -H "Content-Type: application/json" \
  -d "{\"theme_id\":\"$THEME_ID\",\"owner\":\"Team B\",\"statement\":\"Current-period objective\",\"fiscal_year\":$CURRENT_YEAR,\"period\":\"FY\"}"

# An objective already past due.
curl -s -X POST http://localhost:8001/api/v1/strategy/objectives \
  -H "Content-Type: application/json" \
  -d "{\"theme_id\":\"$THEME_ID\",\"owner\":\"Team C\",\"statement\":\"Past-due objective\",\"fiscal_year\":$((CURRENT_YEAR - 1)),\"period\":\"FY\"}"

curl -s http://localhost:8001/api/v1/strategy/summary | python3 -m json.tool
# Expect: past_due_count >= 1 (the FY-1 objective), and the FY-current-year objective is
# never past due mid-year (spec.md Edge Cases' FY-special-case rule).
```

## Scenario 5: Invariants hold

```bash
curl -s http://localhost:8001/api/v1/strategy/summary | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert d['linked_count'] + d['unlinked_count'] == d['total_objectives'], 'linkage split mismatch'
assert d['current_period_count'] + d['upcoming_count'] + d['past_due_count'] == d['total_objectives'], 'fiscal split mismatch'
print('invariants hold')
"
```

## Scenario 6: Card renders on the Overview dashboard (User Story 1, Acceptance Scenario 1–2)

Manual/browser check — open the Overview screen and confirm:
1. A fifth "Strategy" card appears in the "Architecture domains" grid, visually matching the
   other four.
2. Its mini-stats match Scenario 2's counts.
3. Clicking its deep-link control navigates to the Strategy screen's Objectives view.

## Scenario 7: Automated regression check

```bash
pytest tests/unit/strategy/ tests/contract/test_strategy_api_contract.py -q
cd web && npx vitest run src/overview/ src/api/strategy.test.ts
npm run test:run
```
