# Data Model: Strategy Rollups — Heat Map, Orphan Report, Richer Summary

No new tables, no migration — this feature is entirely read-side (spec.md's Key Entities are explicitly
"derived, non-persisted views").

## Modified Pydantic model (`src/adp/strategy/models.py`)

### `StrategicSummaryResponse` (extended)

Adds six fields to the existing 7, matching the existing `extra="forbid"` convention:

```python
proposed_count: int
active_count: int
at_risk_count: int
achieved_count: int
abandoned_count: int
initiative_count: int
```

Invariant: `proposed_count + active_count + at_risk_count + achieved_count + abandoned_count ==
total_objectives`, joining the two existing invariants already documented on this model.

## New Pydantic models (`src/adp/strategy/models.py`)

### `ThemeStatusCounts` (one heat map row)

```python
class ThemeStatusCounts(BaseModel):
    model_config = ConfigDict(extra="forbid")
    theme_id: str
    theme_name: str
    proposed_count: int
    active_count: int
    at_risk_count: int
    achieved_count: int
    abandoned_count: int
```

### `StrategyHeatMapResponse`

```python
class StrategyHeatMapResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    themes: list[ThemeStatusCounts]
    total_objectives: int
```

## New Pydantic model (`src/adp/business/models.py`)

### `OrphanReportResponse`

Reuses the already-existing `BusinessCapability`/`ValueStream` models directly as list items — no new
per-item model needed.

```python
class OrphanReportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    orphan_capabilities: list[BusinessCapability]
    orphan_value_streams: list[ValueStream]
```

## Store function signatures

### `src/adp/strategy/store.py`

```python
async def get_summary_stats(session: AsyncSession) -> StrategicSummaryResponse
    # extended: existing atomic SQL query gains initiative_count; a new Python-side
    # pass over all objectives (reusing _status_for_objective) tallies the 5 status counts.

async def get_strategy_heatmap(
    session: AsyncSession, theme_id: str | None = None
) -> StrategyHeatMapResponse
    # fetches all themes + all objectives (optionally filtered to one theme_id),
    # computes status per objective via _status_for_objective (Decision 1),
    # groups counts by (theme_id, status).
```

### `src/adp/business/store.py`

```python
async def list_orphan_capabilities(session: AsyncSession) -> list[BusinessCapability]
    # every business_capabilities row whose id has zero rows in the
    # _strategic_objective_capabilities mirror table.

async def list_orphan_value_streams(session: AsyncSession) -> list[ValueStream]
    # same shape, against _strategic_objective_value_streams.
```

## New read-only table mirrors (`src/adp/business/store.py`, no migration — views onto already-existing
physical tables owned by `adp.strategy`)

### `_strategic_objective_capabilities`

| Column | Type | Notes |
|---|---|---|
| `objective_id` | `VARCHAR(36)` | not used by the orphan query, included for parity with the real table |
| `capability_id` | `VARCHAR(36)` | the column the orphan query filters against |

### `_strategic_objective_value_streams`

| Column | Type | Notes |
|---|---|---|
| `objective_id` | `VARCHAR(36)` | not used by the orphan query, included for parity |
| `value_stream_id` | `VARCHAR(36)` | the column the orphan query filters against |

## Router endpoints (new/changed)

`src/adp/strategy/router.py`:
- `GET /api/v1/strategy/summary` — **unchanged path/shape at the type level**, now returns 6 additional
  populated fields (no client migration needed — additive).
- `GET /api/v1/strategy/heatmap?theme_id={optional}` → 200, `StrategyHeatMapResponse`.

`src/adp/business/router.py`:
- `GET /api/v1/business/orphans` → 200, `OrphanReportResponse`.

All three are ungated reads (no `ActionType`), per spec.md FR-008.
