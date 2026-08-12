# Contracts: `adp.strategy` API

New router, `prefix="/api/v1/strategy"`, registered in `adp.api.app` alongside every other domain
router. All write endpoints gated by the existing `ActionType.WRITE_BUSINESS_ARCH` (research.md
Decision 3) — reads are ungated, matching `adp.business`'s own convention for capabilities/value
streams/domains.

## Themes

### `POST /api/v1/strategy/themes`
Body: `{"name": "Usage-based pricing"}` → 201, `StrategicTheme`. 409 if a theme with that exact
name already exists (case-sensitive, matching this codebase's existing uniqueness-conflict
convention elsewhere).

### `GET /api/v1/strategy/themes`
→ `{"items": [StrategicTheme, ...], "total": <int>}`.

## Objectives

### `POST /api/v1/strategy/objectives`
Body: `StrategicObjectiveCreate` (`theme_id`, `owner`, `statement`, optional `metric_name`/
`target_value`/`target_unit`/`direction`, `fiscal_year`, `period`) → 201, `StrategicObjective`.
404 if `theme_id` doesn't reference a real theme. 422 if the metric/target/unit/direction group is
partially filled (data-model.md's all-or-nothing validation rule).

### `GET /api/v1/strategy/objectives`
→ `{"items": [StrategicObjectiveSummary, ...], "total": <int>}` — summary omits the full linked-id
lists (FR-008: "enough summary information," not the full detail).

### `GET /api/v1/strategy/objectives/{id}`
→ `StrategicObjective` (full detail, including `capability_ids`/`value_stream_ids`). 404 if not found.

### `PUT /api/v1/strategy/objectives/{id}`
Body: `StrategicObjectiveUpdate` (all fields optional) → `StrategicObjective`. 404 if not found.

### `DELETE /api/v1/strategy/objectives/{id}`
→ 204. Cascades to both join tables (data-model.md). 404 if not found.

## Links

### `POST /api/v1/strategy/objectives/{id}/capabilities`
Body: `{"capability_id": "..."}` → 201, the updated linked-capabilities list. 404 if either the
objective or the capability doesn't exist (research.md Decision 2 — validated via
`adp.business.store.get_capability`). 409 if already linked.

### `DELETE /api/v1/strategy/objectives/{id}/capabilities/{capability_id}`
→ 204. 404 if not linked.

### `POST /api/v1/strategy/objectives/{id}/value-streams`
Same shape as capabilities, substituting `value_stream_id` / `adp.business.store.get_value_stream`.

### `DELETE /api/v1/strategy/objectives/{id}/value-streams/{value_stream_id}`
Same shape.

## Backward compatibility

Entirely new endpoints under a new prefix — no existing endpoint changes, no existing contract
touched.
