# Quickstart: Hybrid Search Phase 2 Completion

Verifies the feature end-to-end against a real running backend and a real local Postgres with
pgvector (migration 011 already applied — no new migration for this feature).

## Setup

```bash
VS_ID=$(curl -s -X POST http://localhost:8001/api/v1/business/value-streams \
  -H "Content-Type: application/json" -d '{"name":"Claims Handling"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
```

## Scenario 1: A new stage is discoverable via search

```bash
STAGE_ID=$(curl -s -X POST "http://localhost:8001/api/v1/business/value-streams/$VS_ID/stages" \
  -H "Content-Type: application/json" -d '{"name":"Fraud Triage Zzyx","position":0}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

curl -s "http://localhost:8001/api/v1/search?q=triage+zzyx&entity_types=value_stream_stage" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print([h['entity_id'] for h in d['hits']])"
# Expect: [STAGE_ID]
```

## Scenario 2: Renaming re-indexes

```bash
curl -s -X PUT "http://localhost:8001/api/v1/business/value-streams/$VS_ID/stages/$STAGE_ID" \
  -H "Content-Type: application/json" -d '{"name":"Renamed Wibblewobble"}' > /dev/null

curl -s "http://localhost:8001/api/v1/search?q=wibblewobble&entity_types=value_stream_stage" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print([h['entity_id'] for h in d['hits']])"
# Expect: [STAGE_ID]

curl -s "http://localhost:8001/api/v1/search?q=wibblewobble&entity_types=value_stream_stage" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['hits'][0]['text'])"
# Expect: "Renamed Wibblewobble" -- confirms the index row's TEXT is the new
# name, proving re-indexing happened. (NOTE: do not assert 0 hits for a query
# of the OLD name here -- hybrid_search's vector leg has no similarity
# threshold, so with very few rows of one entity_type in the index it can
# still surface the row for an unrelated query, confirmed live during this
# feature's own verification. That's a pre-existing property of hybrid_search
# shared by every entity type, not something to test around here -- the
# returned `text` field is the reliable signal that re-indexing worked.)
```

## Scenario 3: Direct stage deletion removes it from search

```bash
curl -s -X DELETE "http://localhost:8001/api/v1/business/value-streams/$VS_ID/stages/$STAGE_ID" \
  -w "\nHTTP:%{http_code}\n"

curl -s "http://localhost:8001/api/v1/search?q=wibblewobble&entity_types=value_stream_stage" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d['hits']))"
# Expect: 0
```

## Scenario 4: Deleting the parent value stream removes its stages from search (cascade-unindex fix)

```bash
STAGE2_ID=$(curl -s -X POST "http://localhost:8001/api/v1/business/value-streams/$VS_ID/stages" \
  -H "Content-Type: application/json" -d '{"name":"Cascade Quorble","position":0}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

curl -s "http://localhost:8001/api/v1/search?q=quorble&entity_types=value_stream_stage" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d['hits']))"
# Expect: 1 (confirms it's indexed before deletion)

curl -s -X DELETE "http://localhost:8001/api/v1/business/value-streams/$VS_ID" \
  -w "\nHTTP:%{http_code}\n"

curl -s "http://localhost:8001/api/v1/search?q=quorble&entity_types=value_stream_stage" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d['hits']))"
# Expect: 0 -- this is the bug fix: without it, this would still return 1
```

## Scenario 5: A domain is discoverable by org_unit alone

```bash
DOMAIN_ID=$(curl -s -X POST http://localhost:8001/api/v1/business/domains \
  -H "Content-Type: application/json" \
  -d '{"name":"Unrelated Domain Name Xylophone","classification":"strategic","org_unit":"Claims Operations Wobsnaggle"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

curl -s "http://localhost:8001/api/v1/search?q=wobsnaggle&entity_types=business_domain" \
  | DOMAIN_ID="$DOMAIN_ID" python3 -c "
import json, os, sys
d = json.load(sys.stdin)
print(os.environ['DOMAIN_ID'] in [h['entity_id'] for h in d['hits']])
"
# Expect: True. (NOTE: the result list may also include other domains beyond
# DOMAIN_ID if few business_domain rows exist in this database -- the vector
# leg has no similarity threshold, see Scenario 2's note. DOMAIN_ID being
# present is the assertion that matters, not an exact-match list.)
```

## Scenario 6: Backfill covers all 5 entity types

```bash
python -m adp.search.backfill
# Expect output covering capabilities, applications, value streams, stages, and domains --
# not just "Reindexed N capabilities" as before this feature.
```

## Cleanup

```bash
curl -s -X DELETE "http://localhost:8001/api/v1/business/domains/$DOMAIN_ID" -w "\nHTTP:%{http_code}\n"
# VS_ID and its stages were already deleted in Scenario 4.
```
