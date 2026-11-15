# Quickstart: Capability Model Analysis (938)

Prerequisites:
- local Postgres on 5433;
- `alembic upgrade head` (migration 047);
- `python scripts/seed_retail.py`;
- the API on :8001 and Vite on :5173.

```bash
API=http://localhost:8001/api/v1
```

## 1. Roll-up (US1)

```bash
curl -s $API/application-capabilities/analysis/business-rollup | python3 -m json.tool | less
```

Find "Process Checkout": health `worst: 2` (Store POS), risk `worst: "high"` (posture weak), exposure `worst: "retiring"`. Its L2 "In-Store Transaction Management" and L1 "Sales & Customer Transactions" show health 2, and their spread counts the five POS leaves.

UI: Business → Heat Map. Choose Application health: the POS branch is red up to the L1. Hover a cell to see the contributing applications.

Dev mode runs as enterprise_architect, which holds the cost and risk permissions. The redaction path for callers without them is covered by the contract tests (role override). It can't be curled locally, the same limitation as 931.

## 2. Lifecycle (US2)

```bash
TC=$(curl -s $API/technical-capabilities | python3 -c "import sys,json;print(next(i['id'] for i in json.load(sys.stdin)['items'] if i['name']=='Distributed Caching'))")
curl -s -X PATCH $API/technical-capabilities/$TC -H 'content-type: application/json' \
  -d '{"lifecycle_status":"contained","end_of_life_date":null}'
curl -s -X PATCH $API/technical-capabilities/$TC -H 'content-type: application/json' \
  -d '{"lifecycle_status":"bogus"}'     # 422
```

## 3. Impact (US3)

```bash
TC=$(curl -s $API/technical-capabilities | python3 -c "import sys,json;print(next(i['id'] for i in json.load(sys.stdin)['items'] if i['name']=='Local Data Store with Offline Sync'))")
curl -s $API/application-capabilities/analysis/technical-capabilities/$TC/impact | python3 -m json.tool
```

Expect exactly: Basket Calculation → Oracle Retail Xstore POS → Process Checkout, with its L1 › L2 path (SC-002).

## 4. Exposure (US4)

On the heat map, choose Technology exposure. Process Checkout, its L2 and its L1 show Retiring. Expand "Technology dependencies" on Process Checkout.

## 5. Findings (US5)

```bash
curl -s $API/application-capabilities/analysis/findings | python3 -m json.tool
```

`overlaps` lists "Apply Promotions" with Xstore POS (via Price Rule Evaluation) and Salesforce Commerce Cloud (via Online Promotion Evaluation). Remove that realization (`DELETE $API/application-capabilities/<ac>/applications/<app>`) and re-run: the entry is gone (SC-003). Re-add it afterwards.

UI: Applications → Capabilities → Overlaps / Gaps / Shared.
