# API Contract: Objective ↔ Design/Application Traceability

## Objective → Design links (`src/adp/strategy/router.py`, prefix `/api/v1/strategy`)

| Method | Path | Body | Success | Errors |
|---|---|---|---|---|
| `POST` | `/objectives/{objective_id}/designs` | `{"design_id": str}` | `201` — `list[str]` (the objective's full `design_ids`) | `404` objective not found; `404` design not found; `409` duplicate link |
| `DELETE` | `/objectives/{objective_id}/designs/{design_id}` | — | `204` | `404` link not found |

## Objective → Application links

| Method | Path | Body | Success | Errors |
|---|---|---|---|---|
| `POST` | `/objectives/{objective_id}/applications` | `{"application_id": str}` | `201` — `list[str]` (the objective's full `application_ids`) | `404` objective not found; `404` application not found; `409` duplicate link |
| `DELETE` | `/objectives/{objective_id}/applications/{application_id}` | — | `204` | `404` link not found |

Both write pairs are gated by the existing `/api/v1/strategy/` prefix rule (`strategy:write` /
`ActionType.WRITE_BUSINESS_ARCH`) — no new `ActionType`.

## Reverse lookups (ungated reads)

| Method | Path | Success | Errors |
|---|---|---|---|
| `GET` | `/api/v1/designs/{design_id}/objectives` | `200` — `StrategicObjectiveListResponse` (`{items, total}`) | `404` design not found |
| `GET` | `/api/v1/applications/{application_id}/objectives` | `200` — `StrategicObjectiveListResponse` | `404` application not found |

## `StrategicObjective` response (extended)

`GET /api/v1/strategy/objectives/{id}` and every other endpoint returning a full `StrategicObjective`
now also include:

```json
{
  "...": "...",
  "capability_ids": ["..."],
  "value_stream_ids": ["..."],
  "design_ids": ["DSN-001", "DSN-014"],
  "application_ids": ["..."],
  "...": "..."
}
```

## Error message conventions (matching existing capability/value-stream link endpoints exactly)

- `404` on unknown `objective_id`: `f"Objective {objective_id!r} not found"`
- `404` on unknown `design_id`: `f"Design {design_id!r} not found"`
- `404` on unknown `application_id`: `f"Application {application_id!r} not found"`
- `409` duplicate: `f"Link ({objective_id!r}, {design_id!r}) already exists"` (from the reused
  `DuplicateLinkError`)
- `404` unlink-not-found: `f"Link ({objective_id!r}, {design_id!r}) not found"` (from the reused
  `LinkNotFoundError`)
