# Phase 1 Data Model: Capture Strategic Objectives

Four new tables via migration 025 (`down_revision="024"`), all in `adp.strategy`'s domain — no
change to any existing table.

## `strategic_themes`

| Column | Type | Notes |
|---|---|---|
| `id` | `String(36)` | PK |
| `name` | `Text`, `NOT NULL`, unique | The taxonomy label (e.g. "Usage-based pricing") |
| `created_at` | `DateTime(timezone=True)`, `NOT NULL` | |

Minimal by design (FR-011's Assumption) — create + list only in v1; no description/classification
field, unlike `BusinessDomain`, since spec.md's Key Entities describe a theme as "a short, reusable
taxonomy label," nothing richer.

## `strategic_objectives`

| Column | Type | Notes |
|---|---|---|
| `id` | `String(36)` | PK |
| `theme_id` | `String(36)`, FK → `strategic_themes.id`, `NOT NULL` | FR-002: never free text |
| `owner` | `Text`, `NOT NULL` | Name or team |
| `statement` | `Text`, `NOT NULL` | The objective's "what and why now" |
| `metric_name` | `Text`, nullable | FR-003: optional, typed metric |
| `target_value` | `Numeric(14, 2)`, nullable | Never float, mirrors ADP-9x6's money precedent generalized |
| `target_unit` | `Text`, nullable | e.g. "days," "%," "$" |
| `direction` | `Text`, nullable, `CHECK (direction IN ('increase','decrease','reach'))` | Mirrors the `SmallInteger` + named-`CHECK` pattern used for `strategic_relevance`/`maturity_level`, adapted to a string set since direction is semantic, not an ordered scale |
| `fiscal_year` | `SmallInteger`, `NOT NULL` | FR-004 |
| `period` | `Text`, `NOT NULL`, `CHECK (period IN ('Q1','Q2','Q3','Q4','FY'))` | FR-004 |
| `created_at` | `DateTime(timezone=True)`, `NOT NULL` | |
| `updated_at` | `DateTime(timezone=True)`, `NOT NULL` | |

**Validation rules** (Pydantic, mirrored at the DB level via the `CHECK` constraints above):
- `metric_name`, `target_value`, `target_unit`, `direction` are all-or-nothing as a group at the
  API layer (a metric with a value but no unit, or a direction with no metric name, is rejected) —
  a data-quality rule not expressible as a single column constraint, enforced in `StrategicObjectiveCreate`'s
  Pydantic validator instead.
- `owner`/`statement` must not be blank (mirrors `BusinessCapabilityCreate`'s own
  `name_must_not_be_blank` validator convention).

**State transitions**: None beyond ordinary create/update/delete — no workflow/status field, per
spec.md's scope (no verdict, no approval gate for this entity).

## `strategic_objective_capabilities` (join)

Mirrors `capability_design_links` (migration 008) exactly, substituting `strategic_objectives` for
`designs`:

| Column | Type | Notes |
|---|---|---|
| `objective_id` | `String(36)`, FK → `strategic_objectives.id`, `ON DELETE CASCADE` | |
| `capability_id` | `String(36)`, FK → `business_capabilities.id`, `ON DELETE CASCADE` | |
| `created_at` | `DateTime(timezone=True)`, server default `now()` | |

Composite PK `(objective_id, capability_id)`; index on `capability_id` (mirrors `ix_cdl_design_id`'s
own choice to index the "other side" of the relationship).

## `strategic_objective_value_streams` (join)

Same shape, substituting `value_streams` for `business_capabilities`:

| Column | Type | Notes |
|---|---|---|
| `objective_id` | `String(36)`, FK → `strategic_objectives.id`, `ON DELETE CASCADE` | |
| `value_stream_id` | `String(36)`, FK → `value_streams.id`, `ON DELETE CASCADE` | |
| `created_at` | `DateTime(timezone=True)`, server default `now()` | |

Composite PK `(objective_id, value_stream_id)`; index on `value_stream_id`.

## Relationships

```text
StrategicTheme  1 ──── * StrategicObjective
StrategicObjective  * ──── * BusinessCapability   (via strategic_objective_capabilities)
StrategicObjective  * ──── * ValueStream           (via strategic_objective_value_streams)
```

Deleting a `StrategicObjective` cascades to both join tables (FR-010 — no orphaned links).
Deleting a `BusinessCapability`/`ValueStream` also cascades to the relevant join table (Edge Case:
"what happens when a linked capability is deleted" — the link simply disappears, matching
`capability_design_links`'s own existing cascade behavior).

## Pydantic models (`src/adp/strategy/models.py`)

```python
ObjectiveDirection = Literal["increase", "decrease", "reach"]
ObjectivePeriod = Literal["Q1", "Q2", "Q3", "Q4", "FY"]

class StrategicTheme(BaseModel):          # read model
class StrategicThemeCreate(BaseModel):    # name only

class StrategicObjective(BaseModel):      # read model, includes linked capability/value-stream ids
class StrategicObjectiveCreate(BaseModel):
class StrategicObjectiveUpdate(BaseModel):  # all fields optional
class StrategicObjectiveListResponse(BaseModel):  # items: list[StrategicObjectiveSummary], total
```

All with `model_config = ConfigDict(extra="forbid")`, matching every other ADP boundary.
