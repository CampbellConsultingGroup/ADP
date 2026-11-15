# Quickstart: EA Pattern Adoptions, Conformance & Discovery (936)

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
# backbone on Marketing & Loyalty -> conformant / conformant_with_warnings
# backbone on E-commerce & Digital -> non_conformant
# mesh-to-backbone on E-commerce & Digital -> (transition; see §3)
```

## 2. Why non-conformant (US1)

```bash
ID=<E-commerce backbone adoption id>
curl -s $API/adoptions/$ID/conformance | pyjson "[(f['code'], f['severity'], [e['name'] for e in f['element_refs']]) for f in d['findings']]"
# C1 lists the direct cross-domain integrations (e.g. 'Salesforce Commerce Cloud → SAP S/4HANA')
```

Change one offending integration in the Applications screen (route it via the hub), then re-read: the finding shrinks, because nothing is cached.

## 3. Transition progress (US3)

```bash
curl -s $API/adoptions/<transition id>/conformance | pyjson "d['plateau']"
# {'reached': 'PL1', 'next': 'PL2', 'blocking': ['C2']}
```

## 4. Discovery (US4)

```bash
curl -s $API/ea.integration.point-to-point-mesh/versions/1.0.0/discover | pyjson "(d['match_count'], [e['name'] for m in d['matches'] for e in m['element_refs']][:5])"
curl -s -o /dev/null -w '%{http_code}\n' $API/ea.integration.domain-event-backbone/versions/1.0.0/discover   # 422
```

## 5. Guards (US2)

- A duplicate adoption on the same scope → 409.
- A pin with the wrong element type, an unknown role or a missing element → 422 with reasons.
- A Reviewer creating an adoption → 403 (contract tests).

## 6. UI walkthrough (SC-001, US5)

Patterns → **Adoptions**:
1. The list shows status badges.
2. Open the E-commerce backbone adoption: the status banner, bindings, findings and conformance view appear.
3. **Save as diagram** opens the Diagrams editor with the view.
4. Create a scratch adoption for a portfolio scope, pin the hub, and delete it.

An anti-pattern version's **Discovery** tab lists the matches. The draft editor's **Evaluate against…** returns a report.
