# Quickstart: EA Pattern Registry (935)

Verified live on 2026-11-14 against local Postgres (127.0.0.1:5433), backend on :8001 with `ADP_AUTH_ENABLED=false`, and the Vite dev server on :5173.

Prerequisites:
- `alembic upgrade head` has reached `044`;
- `scripts/seed_knowledge.py` has been run, so the `PRIN-*` principles exist.

The commands use Python rather than `jq`, which is not installed on the dev box.

```bash
API=http://localhost:8001/api/v1/patterns
K=ea.integration.domain-event-backbone
pyjson() { python3 -c "import json,sys; d=json.load(sys.stdin); print($1)"; }
```

## 1. Seed, catalog, projection (US1, US3)

```bash
python scripts/seed_patterns.py        # 4 imported and promoted to current; a re-run reports "already current"
curl -s $API | pyjson "[(i['pattern_key'], i['lifecycle']) for i in d['items']]"
curl -s "localhost:8001/api/v1/knowledge/adp-pattern:$K" | pyjson "(d['kind'], d['version'], d['metadata']['managed_by'])"
# ('reference_architecture', '1.0.0', 'pattern-registry')
```

Run the seed before importing anything with a seeded key@version. The 934 unit fixtures share keys with the seed but cite placeholder principles, so their digests differ: importing a fixture first makes the seed's import of that key@version fail (`I1`, or `I2` once proposed).

## 2. Import outcomes (US1)

```bash
FIX=tests/unit/patterns/fixtures
curl -s -X POST $API/import -H 'Content-Type: application/yaml' \
  --data-binary @"$FIX/valid/ea.data.one-sor-per-capability@1.0.0.yaml" | pyjson "(d['status'], [i['code'] for i in d['issues']])"
# ('rejected', ['I2.version_immutable'])  -- same key@version as the current seed, different digest
curl -s -o /dev/null -w '%{http_code}\n' -X POST $API/import -H 'Content-Type: application/yaml' \
  --data-binary @"$FIX/invalid/V2.unknown_role-relationship.yaml"     # 422, nothing stored
```

## 3. Governed swap and rollback (US2, US3)

1. Download the backbone YAML (`GET $API/$K/versions/1.0.0/yaml`), change it to `version: 1.1.0`, import it, then transition it to `proposed` and then `current`. Each transition body is `{"to": ..., "reason": ..., "confirmation_id": ...}`.
2. Check the result:
   - the family shows `1.1.0 current`, `1.0.0 deprecated`;
   - 1.0.0's last history event is `current → deprecated` with `caused_by_event_id` set;
   - the knowledge item `adp-pattern:$K` now has `version: 1.1.0` and the same id.
3. Promote `1.0.0` back to `current` (rollback). 1.1.0 becomes deprecated, and the projection returns to 1.0.0.
4. Clean up: a deprecated scratch version cannot be deleted through the API (only drafts can). It was removed directly with `DELETE FROM ea_pattern_version WHERE ...` (cascade).

## 4. Guards (FR-010, FR-015)

```bash
curl -s -o /dev/null -w '%{http_code}\n' -X DELETE "localhost:8001/api/v1/knowledge/adp-pattern:$K"            # 409
curl -s -o /dev/null -w '%{http_code}\n' -X POST $API/$K/versions/1.0.0/lifecycle \
  -H 'Content-Type: application/json' -d '{"to":"deprecated","reason":"x"}'                          # 422 (no confirmation_id)
```

## 5. Views and knowledge retrieval (US4, SC-004)

```bash
for v in structure catalog traceability; do curl -s "$API/$K/versions/1.0.0/views/$v?depth=2" | pyjson "d['flowchart'].splitlines()[0]"; done
```

The traceability view shows the seed's principles by title ("API First Design", "Loose Coupling and High Cohesion").

`KnowledgeRetrieval(...).hybrid_search(RetrievalQuery(query_text="event backbone decoupled cross-domain integration"))` returns `adp-pattern:ea.integration.domain-event-backbone` first.

## 6. Export (US6)

Running `adp.export.patterns.run_reconciliation_cycle(<dir>, session)` against the live DB writes four `<key>@<version>.yaml` files. Each is byte-identical (`cmp`) to `GET .../yaml`. In a running server the same cycle is enabled by `ADP_BUSINESS_ARCH_EXPORT_ROOT`.

## 7. UI walkthrough (SC-001, Playwright)

On the Patterns screen (Oversight section):
- The catalog lists the four current patterns.
- The backbone's Views tab renders the structure (platform role as a stadium) and the catalog (focus highlighted, anti-pattern as a hexagon, labelled relation edges).
- **Knowledge** shows "Managed by Patterns →" on the projections, with no Edit or Delete, and the link opens Patterns.
- **Import pattern** with a scratch `9.0.0`:
  - the draft opens with the family version switcher;
  - Propose: the dialog's Submit is disabled until a reason is entered and the box ticked;
  - the version becomes Proposed, and History shows the reason, actor and generated confirmation UUID.
- Clean up: Return to draft, then Delete.

Reviewer, SA and TA gating is covered by contract tests, since dev mode has no role-override header.

**Known limitation:** diagram-core draws straight edges. Two edges between the same pair of nodes (`publishes`/`delivers`) overlap their labels, and self-loop hints are barely visible. Tracked as a follow-on bead.
