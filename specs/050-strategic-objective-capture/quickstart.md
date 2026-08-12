# Quickstart: Capture Strategic Objectives

Assumes the API is running at `http://localhost:8001` with `ADP_AUTH_ENABLED=false` (dev
convention) and at least one business capability and one value stream already exist.

## Scenario 1: Create a theme, then an objective (User Story 1)

```bash
THEME_ID=$(curl -s -X POST http://localhost:8001/api/v1/strategy/themes \
  -H "Content-Type: application/json" \
  -d '{"name":"Claims automation"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

OBJ_ID=$(curl -s -X POST http://localhost:8001/api/v1/strategy/objectives \
  -H "Content-Type: application/json" \
  -d "{\"theme_id\":\"$THEME_ID\",\"owner\":\"Claims Platform Team\",\"statement\":\"Reduce claims cycle time to improve retention\",\"metric_name\":\"Claims cycle time\",\"target_value\":40,\"target_unit\":\"%\",\"direction\":\"decrease\",\"fiscal_year\":2026,\"period\":\"Q3\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

curl -s "http://localhost:8001/api/v1/strategy/objectives/$OBJ_ID" | python3 -m json.tool
# Expect: every field discrete and typed, not concatenated into one string.
```

## Scenario 2: Required-field validation (Acceptance Scenario 2)

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8001/api/v1/strategy/objectives \
  -H "Content-Type: application/json" \
  -d "{\"theme_id\":\"$THEME_ID\",\"owner\":\"\",\"statement\":\"\",\"fiscal_year\":2026,\"period\":\"Q3\"}"
# Expect: 422 (blank owner/statement rejected)
```

## Scenario 3: Link to a real capability and value stream, registry-validated (User Story 2)

```bash
CAP_ID=$(curl -s http://localhost:8001/api/v1/business/capabilities | python3 -c "import sys,json; print(json.load(sys.stdin)['items'][0]['id'])")
VS_ID=$(curl -s http://localhost:8001/api/v1/business/value-streams | python3 -c "import sys,json; print(json.load(sys.stdin)['items'][0]['id'])")

curl -s -X POST "http://localhost:8001/api/v1/strategy/objectives/$OBJ_ID/capabilities" \
  -H "Content-Type: application/json" -d "{\"capability_id\":\"$CAP_ID\"}" | python3 -m json.tool

curl -s -X POST "http://localhost:8001/api/v1/strategy/objectives/$OBJ_ID/value-streams" \
  -H "Content-Type: application/json" -d "{\"value_stream_id\":\"$VS_ID\"}" | python3 -m json.tool

# Attempt to link a nonexistent capability -- expect 404, not silent acceptance
curl -s -o /dev/null -w "%{http_code}\n" -X POST "http://localhost:8001/api/v1/strategy/objectives/$OBJ_ID/capabilities" \
  -H "Content-Type: application/json" -d '{"capability_id":"nonexistent-id"}'
```

## Scenario 4: Remove a link without affecting the underlying capability (Acceptance Scenario 3)

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X DELETE "http://localhost:8001/api/v1/strategy/objectives/$OBJ_ID/capabilities/$CAP_ID"
# Expect: 204

curl -s "http://localhost:8001/api/v1/business/capabilities/$CAP_ID" -o /dev/null -w "%{http_code}\n"
# Expect: 200 -- the capability itself is untouched
```

## Scenario 5: Delete an objective cascades its links (FR-010)

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X DELETE "http://localhost:8001/api/v1/strategy/objectives/$OBJ_ID"
curl -s -o /dev/null -w "%{http_code}\n" "http://localhost:8001/api/v1/strategy/objectives/$OBJ_ID"
# Expect: 204 then 404
```

## Scenario 6: Automated regression check

```bash
pytest tests/unit/strategy/ tests/contract/test_strategy_api_contract.py -q
cd web && npx vitest run src/strategy/
npm run test:run
```
