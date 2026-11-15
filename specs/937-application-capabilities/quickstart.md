# Quickstart: Application Capabilities (937)

Prerequisites: local Postgres (port 5433 on this box), `alembic upgrade head` → `046`, backend on :8001, web on :5173.

1. **Seed**: `python scripts/seed_retail.py` (wipes and reseeds), then `python -m adp.search.backfill`.
2. **Catalog**: open Applications → Capabilities. The "Transaction Processing" branch is there with five L3s. "Loyalty Points Accrual" shows the missing-technical-capability badge and is the only entry in the gaps list.
3. **Depth**: try to add a child to an L3. It is refused (max depth 3).
4. **Level rules** (API):
   ```bash
   B=http://localhost:8001/api/v1/application-capabilities
   curl -s $B | python3 -c "import json,sys;[print(i['level'],i['id'],i['name'],i['warnings']) for i in json.load(sys.stdin)['items']]"
   # link an L2 app capability to a business L3 -> 422 "application capabilities are mapped at L3..."
   # link an L3 app capability to a technical L1 -> 422 "map to a technical capability at L2 or L3"
   ```
5. **Warning lifecycle**: link "Loyalty Points Accrual" to "API Gateway Services". The badge and gaps entry disappear. Remove the link and they return. Nothing blocked the save.
6. **Traceability**:
   - Business → "Accept Payment" shows "Tender Authorization", realized by Oracle Retail Xstore POS.
   - Technical Architecture → "API Gateway Services" shows Tender Authorization and Return Authorization.
   - The Xstore POS application page shows its five realized capabilities.
   - Each item navigates to its capability.
7. **Search**: `curl -s "localhost:8001/api/v1/search?q=Tender&entity_types=application_capability"` returns Tender Authorization first.
8. **Export**: with `ADP_BUSINESS_ARCH_EXPORT_ROOT` set, `applications/application-capabilities/<id>.json` lists the three link sets.
9. **Cascade**: delete a scratch technical capability linked to an application capability. The link is gone and the warning appears.
