# API Contract: Objective Progress, Status & Theme Management

All routes under the existing `/api/v1/strategy` prefix (`src/adp/strategy/router.py`), gated by the existing `("/api/v1/strategy/", ActionType.WRITE_BUSINESS_ARCH)` rule for every non-`GET` — no new permission, no new prefix rule.

## Themes — completing the existing lifecycle

| Method | Path | Request | Response | Status | Notes |
|---|---|---|---|---|---|
| `GET` | `/strategy/themes/{theme_id}` | — | `StrategicTheme` | 200 / 404 | New — only list `GET` exists today |
| `PATCH` | `/strategy/themes/{theme_id}` | `StrategicThemeUpdate` | `StrategicTheme` | 200 / 404 | New (FR-013) |
| `DELETE` | `/strategy/themes/{theme_id}` | — | — | 204 / 404 / 409 | New (FR-014, FR-015). 409 body explains which objective(s) still reference it |

`POST /strategy/themes` and `GET /strategy/themes` (list) already exist — extended only insofar as `StrategicThemeCreate`/`StrategicTheme` gain `description`/`owner`/`priority` (FR-012), no route-shape change.

## Objective progress

| Method | Path | Request | Response | Status | Notes |
|---|---|---|---|---|---|
| `POST` | `/strategy/objectives/{objective_id}/progress` | `ObjectiveProgressCreate` | `ObjectiveProgressEntry` | 201 / 404 (objective) / 409 (date exists) | FR-001, FR-002 |
| `GET` | `/strategy/objectives/{objective_id}/progress` | — | `ObjectiveProgressListResponse` | 200 / 404 | FR-003 — full history, ordered by `as_of_date` ascending |
| `PATCH` | `/strategy/objectives/{objective_id}/progress/{as_of_date}` | `ObjectiveProgressUpdate` | `ObjectiveProgressEntry` | 200 / 404 (objective or that date's entry) | FR-002a — the correction path |

`as_of_date` in the URL is an ISO date (`YYYY-MM-DD`), matching the column type directly — no surrogate id needed (research.md Decision 3).

## Objective status

| Method | Path | Request | Response | Status | Notes |
|---|---|---|---|---|---|
| `PATCH` | `/strategy/objectives/{objective_id}/abandon` | `AbandonRequest` | `StrategicObjective` | 200 / 404 | FR-009, FR-010, FR-011. Named `/abandon`, not a generic `/status`, since it's the only settable transition — the URL itself communicates that on-track/at-risk/achieved aren't reachable this way, rather than relying on a reader noticing an accepted-values list |

`GET /strategy/objectives/{id}` and `GET /strategy/objectives` (list) are unchanged in shape — both now include the computed `status` field on every returned objective (data-model.md), which existing consumers gain automatically without a new call.

## Error shape

All error responses use FastAPI's standard `{"detail": "..."}` shape, matching every existing `adp.strategy.router` `HTTPException`. No new error envelope.

## Out of scope for this contract

- No endpoint here returns cross-objective aggregates (counts by status, at-risk totals) — that's the sibling `ADP-d8u.7` feature's `/strategy/heatmap` and enriched `/strategy/summary`, which reads this feature's `status` field but isn't built by it.
- No endpoint accepts AI-extracted progress — human-entered only (spec.md Assumptions).
