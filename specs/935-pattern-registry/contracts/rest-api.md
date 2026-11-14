# REST Contract: `/api/v1/patterns` (935)

All responses are JSON unless noted otherwise. Reads are ungated for authenticated users. Writes go through the global `enforce_route_permission` middleware.

| Method & path | Action | Request | Responses |
|---|---|---|---|
| `GET /api/v1/patterns` | — | Query `kind`, `lifecycle`, `tag`, `q`, `limit` (≤ 200, default 100), `offset` | 200 `PatternListResponse`. One row per version, ordered by key, then semver descending |
| `GET /api/v1/patterns/{key}` | — | | 200 `PatternFamily`, 404 |
| `GET /api/v1/patterns/{key}/versions/{version}` | — | | 200 `PatternVersionDetail`, 404 |
| `GET /api/v1/patterns/{key}/versions/{version}/yaml` | — | | 200 `application/yaml`. Body = `to_canonical_yaml(defn)`, with `Content-Disposition: attachment; filename="<key>@<version>.yaml"`. 404 |
| `GET /api/v1/patterns/{key}/versions/{version}/views/{view}` | — | `view` ∈ structure\|catalog\|traceability; query `depth` (1–3, catalog only), `direction` (LR\|TB), `legend` (bool) | 200 `PatternViewResponse`, 404, 422 (bad view or depth) |
| `GET /api/v1/patterns/relations` | — | Query `key` (optional) | 200 `list[PatternRelationRow]` |
| `POST /api/v1/patterns/import` | WRITE_PATTERN | Body: raw YAML (`application/yaml` or `text/plain`), ≤ 256 KB | 201 `PatternImportResult{created}`, 200 `{unchanged}`, 422 `{rejected}` (issues in the body), 413 if too large, 403 |
| `POST /api/v1/patterns/validate` | WRITE_PATTERN | Raw YAML | 200 `PatternValidateResult` (dry run; resolution warnings included; nothing stored) |
| `POST /api/v1/patterns/render` | WRITE_PATTERN | `PatternRenderRequest` JSON | 200 `PatternViewResponse` (structure only; nothing stored), 422 with issues if the YAML is invalid |
| `PUT /api/v1/patterns/{key}/versions/{version}` | WRITE_PATTERN | Raw YAML (same key, version and kind) | 200 `PatternUpdateResult` (see note), 409 not draft, 422 issues or identity change, 404 |
| `POST /api/v1/patterns/{key}/versions/{version}/lifecycle` | GOVERN_PATTERN (explicit rule; requires confirmation) | `LifecycleTransitionRequest` | 200 `PatternVersionDetail`, 409 illegal or concurrent, 422 missing reason/confirmation or promotion blocked (issues), 404, 403 |
| `DELETE /api/v1/patterns/{key}/versions/{version}` | WRITE_PATTERN | | 204, 409 not draft, 404 |

**Note on PUT.** The response is `PatternUpdateResult{version: PatternVersionSummary, issues: list[PatternIssue]}`, so that `ImportStatus` doesn't need an "updated" value. Add it to `registry_models` alongside the models in data-model.md.

**Route order**: `/relations`, `/import`, `/validate` and `/render` are declared before `/{key}`.

**Size limit**: the router reads at most 256 KB + 1 byte of the body and returns 413 above that, before parsing.

## Log lines (ART-IX, GT-3)

```
patterns.import key=%s version=%s status=%s digest=%s actor=%s
patterns.update key=%s version=%s digest_before=%s digest_after=%s actor=%s
patterns.transition key=%s version=%s from=%s to=%s reason=%r confirmation_id=%s actor=%s
patterns.demote key=%s version=%s caused_by=%s actor=%s
patterns.delete key=%s version=%s digest=%s family_deleted=%s actor=%s
patterns.project key=%s knowledge_item_id=%s active=%s
```

## Touched endpoints

| Endpoint | Change |
|---|---|
| `PUT /api/v1/knowledge/{id}`, `DELETE /api/v1/knowledge/{id}` | 409 for registry-managed items |
| `POST /api/v1/knowledge` | 422 if the id starts with `adp-pattern:` |
| `PUT /api/v1/compliance/controls/{id}/mappings/patterns/{pattern_id}` (existing pattern-mapping upsert) | Accepts knowledge kind `reference_architecture` too |

## Frontend client (`web/src/api/patterns.ts`)

Hooks:
- `usePatterns(filters)`
- `usePatternFamily(key)`
- `usePatternVersion(key, version)`
- `usePatternView(key, version, view, opts)`
- `useImportPattern()`
- `useValidatePattern()`
- `useRenderPattern()`
- `useUpdateDraft(key, version)`
- `useTransition(key, version)`
- `useDeleteDraft(key, version)`

Mutations invalidate `["patterns"]` and, on transition, `["knowledge"]`.
