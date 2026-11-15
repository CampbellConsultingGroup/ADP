# Quickstart: EA Pattern Adoptions, Conformance & Discovery (936)

Verified live on 2026-11-14 against local Postgres (127.0.0.1:5433) after a full reseed. Actual results are noted inline.

Prerequisites:
- `alembic upgrade head` (045);
- then, in order: `python scripts/seed_retail.py --yes`, `python scripts/seed_knowledge.py`, `python scripts/seed_patterns.py`;
- backend on :8001 with `ADP_AUTH_ENABLED=false`.

The commands use Python rather than `jq` (not installed).

```bash
API=http://localhost:8001/api/v1/patterns
pyjson() { python3 -c "import json,sys; d=json.load(sys.stdin); print($1)"; }
```

## 1. Demo adoptions and their status (US1, US2)

```bash
curl -s "$API/adoptions?with_status=true" | pyjson "[(a['name'], a['scope_name'], a['status']) for a in d['items']]"
# Marketing & Loyalty — event backbone   -> conformant
# E-commerce & Digital — event backbone  -> non_conformant
# E-commerce & Digital — mesh migration  -> non_conformant (plateau PL1 -> PL2)
# (all resolve to the seed patterns' 1.1.0, which supersedes 1.0.0)
```

## 2. Why non-conformant (US1)

```bash
ID=<E-commerce backbone adoption id>
curl -s $API/adoptions/$ID/conformance | pyjson "[(f['code'], f['severity'], [e['name'] for e in f['element_refs']]) for f in d['findings']]"
# E:R1 [Adyen Payments, Algolia Search]  -- not publishing to the hub
# C1   [Akeneo PIM → Algolia Search, Manhattan Active OMS → Blue Yonder WMS,
#       Manhattan Active OMS → SAP S/4HANA, Manhattan Active OMS → Snowflake Data Cloud,
#       Salesforce Commerce Cloud → Snowflake Data Cloud]
```

Change one offending integration in the Applications screen (route it via the hub), then re-read: the finding shrinks, because nothing is cached.

## 3. Transition progress (US3)

```bash
curl -s $API/adoptions/<transition id>/conformance | pyjson "d['plateau']"
# {'reached': 'PL1', 'next': 'PL2', 'blocking': ['C2']}
```

## 4. Discovery (US4)

```bash
curl -s $API/ea.integration.point-to-point-mesh/versions/1.1.0/discover | pyjson "(d['match_count'], [e['name'] for m in d['matches'] for e in m['element_refs']][:5])"
# -> 5 (the five direct cross-domain integrations above). 1.0.0 reports 16: its all()-based
#    selector also counts every integration touching the domainless hub (spec Edge Cases).
curl -s -o /dev/null -w '%{http_code}\n' $API/ea.integration.domain-event-backbone/versions/1.1.0/discover   # 422
```

## 5. Guards (US2)

- A duplicate adoption on the same scope → 409.
- A pin with the wrong element type, an unknown role or a missing element → 422 with reasons.
- A Reviewer creating an adoption → 403 (contract tests).

## 6. UI walkthrough (SC-001, US5)

Reports come back in 0.02–0.27 s (SC-005).

Patterns → **Adoptions**:
1. The list shows status badges.
2. Open the E-commerce backbone adoption: the status banner, bindings, findings and conformance view appear.
3. **Save as diagram** opens the Diagrams editor with the view.
4. Create a scratch adoption for a portfolio scope, pin the hub, and delete it.

An anti-pattern version's **Discovery** tab lists the matches. The draft editor's **Evaluate against…** returns a report.

**Known limitation:** diagram-core's auto-layout can draw role groups overlapping, and bidirectional publish/deliver edges overlap their labels (ADP-n4e).

**Gotcha found live:** the Vite dev server's HMR served a stale `labels.ts` after a series of edits (blank page, "does not provide an export named SCOPE_LABELS"). Restarting Vite fixed it; `tsc` and the tests were correct throughout.
