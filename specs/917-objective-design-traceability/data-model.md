# Data Model: Objective ↔ Design/Application Traceability

## New tables (migration 028)

### `objective_design_links`

| Column | Type | Notes |
|---|---|---|
| `objective_id` | `VARCHAR(36)` | FK → `strategic_objectives.id`, `ON DELETE CASCADE`, part of composite PK |
| `design_id` | `TEXT` | FK → `designs.id`, `ON DELETE CASCADE`, part of composite PK, indexed (the "other side," matching `capability_design_links`'s `ix_cdl_design_id` precedent) |
| `created_at` | `TIMESTAMPTZ` | `server_default=now()` |

PK: `(objective_id, design_id)`. `design_id` is `TEXT` (not `VARCHAR(36)`), matching
`capability_design_links.design_id`'s exact type (migration 008) — `designs.id` values are `DSN-NNN`
strings of variable, non-UUID length.

### `objective_application_links`

| Column | Type | Notes |
|---|---|---|
| `objective_id` | `VARCHAR(36)` | FK → `strategic_objectives.id`, `ON DELETE CASCADE`, part of composite PK |
| `application_id` | `VARCHAR(36)` | FK → `applications.id`, `ON DELETE CASCADE`, part of composite PK, indexed |
| `created_at` | `TIMESTAMPTZ` | `server_default=now()` |

PK: `(objective_id, application_id)`.

Both tables follow the composite-PK-omitted-in-Python-metadata convention already established in
`adp.strategy.store` (`_objective_capabilities`/`_objective_value_streams`/`_progress`): the
`sa.Table` Python declarations in `store.py` omit `primary_key=True` on individual columns (PK/FK
constraints live only in the Alembic migration); the SQLite unit-test fixture adds the matching
`CREATE UNIQUE INDEX` DDL manually, same as every other join table's test fixture in this package.

## Existing-table read-only mirrors (new in `adp.strategy.store`, no migration — these are views onto
already-existing physical tables)

### `_designs` (mirrors `adp.business.store`'s own precedent, id-only + display fields)

| Column | Type | Notes |
|---|---|---|
| `id` | `TEXT` | PK |
| `title` | `TEXT` | for future display use (not required by this feature's endpoints, included for parity with `adp.business.store`'s own `_designs` shape) |

### `_applications`

| Column | Type | Notes |
|---|---|---|
| `id` | `VARCHAR(36)` | PK |
| `name` | `VARCHAR(255)` | display field |

## Modified Pydantic models (`src/adp/strategy/models.py`)

### `StrategicObjective` (extended)

Adds two fields, matching `capability_ids`/`value_stream_ids`'s existing shape exactly:

```python
design_ids: list[str] = []
application_ids: list[str] = []
```

No other existing model changes.

## New Pydantic models (`src/adp/strategy/models.py`)

### `ObjectiveDesignLinkCreate` / `ObjectiveApplicationLinkCreate`

Mirrors the existing `ObjectiveCapabilityLinkCreate`/`ObjectiveValueStreamLinkCreate` shape exactly:

```python
class ObjectiveDesignLinkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    design_id: str

class ObjectiveApplicationLinkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    application_id: str
```

No new response model is needed for the reverse-lookup endpoints — they return the already-existing
`StrategicObjectiveListResponse` (`{items: StrategicObjectiveSummary[], total: int}`), the exact same
shape `GET /api/v1/strategy/objectives` itself already returns.

## Store function signatures (`src/adp/strategy/store.py`)

```python
async def link_objective_design(objective_id: str, design_id: str, session: AsyncSession) -> None
async def unlink_objective_design(objective_id: str, design_id: str, session: AsyncSession) -> None
async def design_exists(design_id: str, session: AsyncSession) -> bool

async def link_objective_application(objective_id: str, application_id: str, session: AsyncSession) -> None
async def unlink_objective_application(objective_id: str, application_id: str, session: AsyncSession) -> None
async def application_exists(application_id: str, session: AsyncSession) -> bool

async def list_objectives_for_design(design_id: str, session: AsyncSession) -> StrategicObjectiveListResponse
async def list_objectives_for_application(application_id: str, session: AsyncSession) -> StrategicObjectiveListResponse
```

`link_objective_design`/`link_objective_application` raise `DuplicateLinkError` on conflict (already
public in `store.py`, reused — not redefined); `unlink_*` raise `LinkNotFoundError` (also already
public, reused). `get_objective()`'s existing SELECT (used to build the full `StrategicObjective`
response) is extended to also populate `design_ids`/`application_ids` via two more subqueries, mirroring
how it already populates `capability_ids`/`value_stream_ids`.

## Router endpoints (new)

`src/adp/strategy/router.py`:
- `POST /api/v1/strategy/objectives/{id}/designs` (body: `ObjectiveDesignLinkCreate`) → 201, returns
  `objective.design_ids` (bare list, matching the existing capability/value-stream link endpoints'
  return shape)
- `DELETE /api/v1/strategy/objectives/{id}/designs/{design_id}` → 204
- `POST /api/v1/strategy/objectives/{id}/applications` (body: `ObjectiveApplicationLinkCreate`) → 201,
  returns `objective.application_ids`
- `DELETE /api/v1/strategy/objectives/{id}/applications/{application_id}` → 204

`src/adp/api/routers/designs.py`:
- `GET /api/v1/designs/{id}/objectives` → 200, `StrategicObjectiveListResponse`; 404 if design not found

`src/adp/application/router.py`:
- `GET /api/v1/applications/{id}/objectives` → 200, `StrategicObjectiveListResponse`; 404 if
  application not found

## New cross-package session dependencies

`src/adp/strategy/router.py` gains `_get_store_session` (a new second, `adp.store`-scoped session
dependency, mirroring the existing `_get_business_session`) used only to validate `design_id`
existence via `adp.strategy.store.design_exists`; `_get_application_session` (naming already reserved
by `adp.business.router`'s own precedent for a *different* purpose — this feature's version lives in
`adp.strategy.router` and validates `application_id` existence via `application_exists`).

`src/adp/api/routers/designs.py` and `src/adp/application/router.py` each gain a new
`_get_strategy_session` dependency (opening a session against `adp.strategy.store`'s own session
factory) used only by their new reverse-lookup `GET` endpoint.
