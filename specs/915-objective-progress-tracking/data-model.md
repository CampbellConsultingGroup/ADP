# Phase 1 Data Model: Objective Progress Tracking, Lifecycle Status & Theme Management

## Entities

### `strategic_objective_progress` (new table)

| Column | Type | Notes |
|---|---|---|
| `objective_id` | `String(36)` | FK → `strategic_objectives.id`, `ON DELETE CASCADE` (FR-016) |
| `as_of_date` | `Date` | part of composite key — one entry per objective per date |
| `actual_value` | `Numeric(14, 2)` | matches `strategic_objectives.target_value`'s existing precision; never floating point |
| `note` | `Text`, nullable | free text entered by the recording owner |
| `recorded_by` | `Text`, not null | from `_get_actor(request)` — see research.md Decision 5 |
| `created_at` | `DateTime(timezone=True)`, not null | set once, on insert; unchanged by a later edit (FR-002a edits `actual_value`/`note` only) |

**Primary key**: `(objective_id, as_of_date)`.
**Index**: none beyond the PK — every read is either "all entries for one objective" (PK's leading column already serves that) or "one entry by objective+date" (the PK itself).

**Validation rules** (Pydantic, `extra="forbid"`):
- `actual_value` required, any `Decimal`.
- `as_of_date` required on create; immutable on edit (not a field on the update model at all — FR-002a: "the date is fixed once recorded").
- `note` optional, reasonable max length (500, matching `LifecycleTransitionRequest.note`'s existing precedent).

**State transitions**: None — a progress entry is created once, may be edited (value/note only) any number of times afterward, and is removed only as a cascade of its parent objective being deleted. It has no independent lifecycle.

### `strategic_objectives` (existing table, extended)

New columns:

| Column | Type | Notes |
|---|---|---|
| `status` | `Text`, nullable | CHECK: `status IS NULL OR status = 'abandoned'` (research.md Decision 2) |
| `status_reason` | `Text`, nullable | required at the Pydantic layer whenever `status = 'abandoned'`; otherwise must be absent |

**Derived field** (not a column — computed on every read, per research.md Decision 1): `computed_status: ObjectiveStatus` = `"proposed" | "active" | "at_risk" | "achieved" | "abandoned"`. The response model exposes this single field to API consumers as `status` (the read-model's public name); the persisted column backing it is an internal store-layer detail, not separately exposed.

**Validation rules** (extending the existing model):
- Setting `status` via the API only ever accepts the literal `"abandoned"`, always paired with a non-blank `status_reason` — any other attempted value is a 400 (FR-011), enforced by a dedicated `AbandonRequest` model (below) rather than reusing `StrategicObjectiveUpdate` for this action, so the "only abandoned is settable" rule is a type-level fact, not a runtime check on a broader model.

### `strategic_themes` (existing table, extended)

New columns:

| Column | Type | Notes |
|---|---|---|
| `description` | `Text`, nullable | |
| `owner` | `Text`, nullable | plain string, no `users` table (research.md Decision 5) |
| `priority` | `SmallInteger`, nullable | CHECK: `priority IS NULL OR priority BETWEEN 1 AND 5` (research.md Decision 4) |

**Validation rules**: `priority`, if provided, must be an integer 1–5 (enforced by both the DB CHECK and a Pydantic `Field(ge=1, le=5)` for an immediate 422 rather than a 500 on a DB constraint violation).

## New Pydantic Models (`src/adp/strategy/models.py`)

```text
ObjectiveStatus = Literal["proposed", "active", "at_risk", "achieved", "abandoned"]

ObjectiveProgressEntry (read model)
  objective_id: str
  as_of_date: date
  actual_value: Decimal
  note: str | None
  recorded_by: str
  created_at: datetime

ObjectiveProgressCreate
  as_of_date: date
  actual_value: Decimal
  note: str | None = Field(default=None, max_length=500)

ObjectiveProgressUpdate
  actual_value: Decimal
  note: str | None = Field(default=None, max_length=500)
  # no as_of_date field at all -- FR-002a: date is fixed once recorded

ObjectiveProgressListResponse
  items: list[ObjectiveProgressEntry]
  total: int

AbandonRequest
  status_reason: str = Field(min_length=1, max_length=500)
  # no `status` field -- the action IS "abandon", nothing else is acceptable (FR-011)

StrategicThemeUpdate
  description: str | None = None
  owner: str | None = None
  priority: int | None = Field(default=None, ge=1, le=5)
  # name is NOT editable in this version (not asked for in spec; avoids re-litigating
  # the existing DuplicateThemeNameError uniqueness path for a field nobody asked to change)
```

Extended existing models:

```text
StrategicTheme (read model)          + description, owner, priority
StrategicThemeCreate                 + description, owner, priority (all optional, matching FR-012)
StrategicObjective (read model)      + status: ObjectiveStatus (the computed field, research.md Decision 1),
                                        status_reason: str | None
StrategicObjectiveSummary            + status: ObjectiveStatus  (list views need the status too, per SC-001
                                        "visible at a glance wherever the objective appears")
```

## Relationships

```text
strategic_themes (1) ──< (many) strategic_objectives         [existing, unchanged]
strategic_objectives (1) ──< (many) strategic_objective_progress   [new, CASCADE]
```

No new relationship to any entity outside `adp.strategy` — this feature touches nothing in `adp.business`, `adp.application`, or `adp.store`.
