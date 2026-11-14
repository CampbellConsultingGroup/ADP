# Quickstart: EA Pattern Registry (935)

Prerequisites:
- the local stack is running (`dev-server-up`): API on :8001, web on :5173, Postgres;
- `alembic upgrade head` has reached `044`;
- `scripts/seed_knowledge.py` has been run, so the `PRIN-*` principles exist.

```bash
API=http://localhost:8001/api/v1/patterns
FIX=tests/unit/patterns/fixtures/valid
```

## 1. Import → created / unchanged / rejected (US1)

```bash
curl -s -X POST $API/import -H 'Content-Type: application/yaml' \
  --data-binary @$FIX/ea.data.one-sor-per-capability@1.0.0.yaml | jq '.status, .issues[].code'
# "created", plus "R1.unresolved_principle" (the fixture cites P-SINGLE-SOURCE, a placeholder)
# Re-run the same command → "unchanged"
curl -s -X POST $API/import -H 'Content-Type: application/yaml' \
  --data-binary @tests/unit/patterns/fixtures/invalid/V2.unknown_role.yaml | jq '.status'
# "rejected" (HTTP 422); GET $API lists no new family
```

## 2. Promotion is blocked by unresolved references (US2-6)

```bash
K=ea.data.one-sor-per-capability; V=1.0.0
T() { curl -s -X POST $API/$K/versions/$V/lifecycle -H 'Content-Type: application/json' \
      -d "{\"to\":\"$1\",\"reason\":\"quickstart\",\"confirmation_id\":\"qs-$1\"}"; }
T proposed | jq .lifecycle            # "proposed"
T current  | jq '.detail // .issues'  # 422, R1.unresolved_principle
T draft    | jq .lifecycle            # back to draft
```

## 3. Seed patterns: lifecycle, projection, views (US2–US4)

```bash
python scripts/seed_patterns.py        # 4 patterns imported and promoted to current
curl -s $API | jq '.items[] | [.pattern_key, .version, .lifecycle]'
curl -s localhost:8001/api/v1/knowledge/adp-pattern:ea.integration.domain-event-backbone \
  | jq '.kind, .active'                # "reference_architecture", true
curl -s "$API/ea.integration.domain-event-backbone/versions/1.0.0/views/catalog?depth=2" \
  | jq -r .flowchart                   # header comment, then flowchart LR, ...
```

## 4. Single-current swap and history (US2-3)

1. Download the backbone YAML (`GET .../yaml`), change `version: 1.1.0` and the summary, then import it.
2. Transition it to `proposed`, then to `current`.

Expected:
- `GET $API/ea.integration.domain-event-backbone` → 1.1.0 current, 1.0.0 deprecated;
- the 1.0.0 history ends with a demotion event whose `caused_by_event_id` is set;
- the knowledge item `version` is `1.1.0` and keeps the same id.

## 5. Guards (FR-015, FR-016, US2-7)

```bash
curl -s -o /dev/null -w '%{http_code}\n' -X DELETE \
  localhost:8001/api/v1/knowledge/adp-pattern:ea.integration.domain-event-backbone   # 409
curl -s -o /dev/null -w '%{http_code}\n' -X POST $API/$K/versions/$V/lifecycle \
  -H 'Content-Type: application/json' -d '{"to":"proposed","reason":"x"}'          # 422
# Map a control to the reference-architecture projection (PUT .../mappings/patterns/adp-pattern:...) → 200
```

## 6. Export (US6)

1. Restart the API with `ADP_BUSINESS_ARCH_EXPORT_ROOT=/tmp/adp-export` and `ADP_BUSINESS_ARCH_EXPORT_INTERVAL_SECONDS=5`.
2. Run `ls /tmp/adp-export/patterns/`: there is one `<key>@<version>.yaml` per current version.
3. Run `diff <(curl -s $API/<key>/versions/<v>/yaml) /tmp/adp-export/patterns/<key>@<v>.yaml`: there is no output.

## 7. UI walkthrough (SC-001)

Patterns (Oversight nav):
1. **Import:** paste the fixture YAML.
2. **Version:** check the warnings, then edit the draft so it cites `PRIN-001` instead of the placeholder. Validate, then Save.
3. **Propose:** the dialog requires a reason and the confirm checkbox.
4. **Promote to current:** the version shows as current.
5. **Views:** structure, catalog and traceability render.
6. **Knowledge:** the item shows "Managed by Patterns" with no Edit or Delete.

As a Reviewer (contract tests stand in for this, since dev mode has no role header), no import, edit or lifecycle controls are shown.

## Cleanup

Scratch imports that never left `draft` can be deleted via `DELETE`. Promoted seed patterns are demo data, and `seed_patterns.py` is idempotent.
