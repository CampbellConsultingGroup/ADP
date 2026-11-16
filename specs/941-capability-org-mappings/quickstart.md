# Quickstart: Capability ↔ Org Unit Mappings (941)

Prerequisites:
- `alembic upgrade head` (049) on local Postgres (5433);
- the API on :8001 and Vite on :5173;
- at least one L1 → L2 → L3 business capability chain, and the 940 org units "Retail Co" › "Stores" and "Retail Co" › "E-commerce". Create scratch ones if needed, and delete them afterwards.

```bash
B=http://localhost:8001/api/v1/business
J='content-type: application/json'
# set L1, L2, L3 (capability ids) and RC, ST, EC (org unit ids)
```

## 1. Owner (US1)
```bash
curl -s -X PUT $B/capability-org-mappings/$L2/owner -H "$J" -d "{\"org_unit_id\":\"$RC\"}" | python3 -m json.tool
curl -s -X PUT $B/capability-org-mappings/$L3/owner -H "$J" -d "{\"org_unit_id\":\"$RC\"}" -o /dev/null -w "%{http_code}\n"   # 422
curl -s $B/capability-org-mappings | python3 -c "import sys,json;[print(v['capability_id'],v['effective_owner'],v['owner_inherited_from']) for v in json.load(sys.stdin)['items']]"
```
Expect L3's effective owner to be Retail Co, inherited from L2.

## 2. Performers (US2)
```bash
curl -s -X POST $B/capability-org-mappings -H "$J" -d "{\"capability_id\":\"$L3\",\"org_unit_id\":\"$ST\",\"role\":\"performer\",\"geography_id\":\"geo-DE\"}" -o /dev/null -w "%{http_code}\n"  # 201
curl -s -X POST $B/capability-org-mappings -H "$J" -d "{\"capability_id\":\"$L3\",\"org_unit_id\":\"$ST\",\"role\":\"performer\",\"geography_id\":\"geo-DE\"}" -o /dev/null -w "%{http_code}\n"  # 409
curl -s -X POST $B/capability-org-mappings -H "$J" -d "{\"capability_id\":\"$L2\",\"org_unit_id\":\"$ST\",\"role\":\"performer\"}" -o /dev/null -w "%{http_code}\n"  # 422
```

## 3. Findings (US3)
```bash
curl -s $B/capability-org-mappings/findings | python3 -c "import sys,json;d=json.load(sys.stdin);print(d['counts'])"
curl -s -X POST $B/capability-org-mappings -H "$J" -d "{\"capability_id\":\"$L3\",\"org_unit_id\":\"$EC\",\"role\":\"performer\"}" -o /dev/null
curl -s $B/capability-org-mappings/findings | python3 -c "import sys,json;print([c['capability']['name'] for c in json.load(sys.stdin)['shared_service']])"
```
Expect L3 to become a shared-service candidate after E-commerce is added. Adding Retail Co itself as a performer would fold both units into one branch, so it would no longer be a candidate.

## 4. Footprint (US4)
```bash
curl -s $B/org-units/$RC/footprint | python3 -m json.tool
```
Expect Retail Co's footprint to include L3, attributed to Stores (DE) and E-commerce, plus L2 under "owns".

## 5. Deletes
- Delete the DE geography only on a scratch country: the performer keeps the unit and loses the geography.
- Delete a scratch org unit: its mappings disappear, and the capability falls back to its parent's owner.

## 6. UI (Playwright)
- Business → Capabilities: owner chips (own and inherited), performer chips on L3, and the Organization expander edits.
- Business → Organization → Findings: three lists with counts. Clicking one opens the capability row, focused.
- Org unit detail: the footprint, whose links open capabilities.

Clean up all scratch data afterwards.
