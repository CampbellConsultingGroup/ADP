# REST contract: Mapping Rationale (943)

Base: `/api/v1/application-capabilities`. Reads are open to every authenticated user. Writes need `WRITE_APPLICATION` (the existing prefix rule); a reviewer gets 403.

| Method | Path | Body | Success | Errors |
|---|---|---|---|---|
| POST | `/{ac_id}/applications` (extended) | `{"app_id": str, "rationale"?: "target"\|"tactical"\|"transitional"\|"redundant"\|null, "geography_id"?: str\|null}` | 201 `ApplicationCapabilityDetail` | 404 capability/application; 409 duplicate; 422 not L3, bad rationale, unknown geography, Global |
| PATCH | `/{ac_id}/applications/{app_id}` (new) | `{"rationale"?: …\|null, "geography_id"?: str\|null}`. An omitted field is unchanged; an explicit `null` clears it | 200 `ApplicationCapabilityDetail` | 404 link not found; 422 bad rationale, unknown geography, Global, or an empty body |
| GET | `/{ac_id}` (extended) | — | `realized_by[]` items gain `rationale`, `geography`, `hint` | — |
| GET | `/analysis/findings` (extended) | — | `overlaps[]` gain `status`, `reasons[]` and `applications[].mappings[]`; a new top-level `redundant[]` | — |

Example overlap entry:

```json
{
  "business": {"id": "…", "name": "Apply Promotions", "level": 3, "path": ["…"]},
  "status": "needs_attention",
  "reasons": [{"code": "unclassified", "application_ids": ["app-ecom"]}],
  "applications": [
    {"id": "app-pos", "name": "Store POS", "via": [{"id": "ac-1", "name": "Promotion Evaluation", "level": 3}],
     "mappings": [{"via": {"id": "ac-1", "name": "Promotion Evaluation", "level": 3},
                   "rationale": "target", "geography": null, "hint": null}]}
  ]
}
```

Log lines (INFO, `adp.application.app_capabilities_router`):
- An add keeps 937's existing `app_capability.link.create` line.
- When the add carries a rationale or geography, it also logs an update line from `None`.

```text
app_capability.link.create kind=application id=<ac> target=<app> actor=<sub>
app_capability.realization.update ac=<id> app=<id> rationale=<old>-><new> geography=<old>-><new> actor=<sub>
```
