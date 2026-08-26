# Data Model: Admin UI for Editing Scoring Rubric Weights

## 1. Enum additions (code, not a table)

### `ActionType.MANAGE_SCORING_RUBRICS` (`src/adp/authz/roles.py`)

New value on the existing `ActionType` StrEnum, alongside `MANAGE_AGENT_PROMPTS`.

**Grant changes** (`src/adp/authz/permissions.py`, `PERMISSIONS_VERSION` 1.9.0 → 1.10.0):
- `PERMISSION_GRANTS[PersonaRole.ENTERPRISE_ARCHITECT]`: `frozenset(ActionType) -
  {ActionType.MANAGE_AGENT_PROMPTS}` → `frozenset(ActionType) - {ActionType.MANAGE_AGENT_PROMPTS,
  ActionType.MANAGE_SCORING_RUBRICS}` (identical exclusion pattern, one more entry).
- `PERMISSION_GRANTS[PersonaRole.PLATFORM_ADMIN]`: already `frozenset(ActionType)` — the new
  action flows through with zero edit needed there.
- `REQUIRES_CONFIRMATION`: add `ActionType.MANAGE_SCORING_RUBRICS`.

**Prefix rule** (`src/adp/authz/enforcement.py`, `_PREFIX_ROUTE_ACTIONS`):
`("/api/v1/admin/scoring-rubrics", ActionType.MANAGE_SCORING_RUBRICS)` — same "reads included, not
just writes" treatment as the `MANAGE_AGENT_PROMPTS` prefix rule, same rationale (an admin surface
gates the whole thing).

## 2. `RUBRIC_REGISTRATIONS` (static, code-defined — `adp.admin.rubric_registry`)

Not persisted — mirrors `AGENT_REGISTRATIONS`'s own "the registered set itself is a deploy-time
decision" framing.

| Rubric ID | Display Name | Dimensions | Fallback | Validator |
|---|---|---|---|---|
| `business_value` | Business Value Assessment | the 6 `BusinessValueDimension` keys, each with a display label (e.g. `strategic_alignment` → "Strategic Alignment") | `adp.application.models.BUSINESS_VALUE_WEIGHTS` | exactly these 6 keys present, each weight `∈ [0, 1]`, sum `== 1.0 ± 1e-6` |

**Validation rule** (mirrors `agent_id`'s own "unknown → 404" precedent): a `rubric_id` not in this
set is rejected 404 by every endpoint.

## 3. Table: `rubric_weight_overrides`

One row per rubric currently running a saved override. Absence of a row means "using the
fallback."

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `rubric_id` | `TEXT` | PK | One of the registered values above |
| `weights` | `JSONB` | `NOT NULL` | The currently active override, e.g. `{"strategic_alignment": 0.3, ...}` |
| `updated_by` | `TEXT` | `NOT NULL` | Actor identifier |
| `updated_at` | `TIMESTAMPTZ` | `NOT NULL`, server default `now()` | |
| `version` | `INTEGER` | `NOT NULL`, default `1`, incremented on every write | Optimistic-lock token, identical semantics to `agent_prompt_overrides.version` |

## 4. Table: `rubric_weight_history`

Append-only. One row per confirmed edit or restore.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `BIGSERIAL` | PK | |
| `rubric_id` | `TEXT` | `NOT NULL` | Not a DB-level FK — same "history must survive the override row's own lifecycle" reasoning as `agent_prompt_history.agent_id` |
| `actor` | `TEXT` | `NOT NULL` | |
| `changed_at` | `TIMESTAMPTZ` | `NOT NULL`, server default `now()` | |
| `change_type` | `TEXT` | `NOT NULL`, app+DB check `IN ('edit', 'restore')` | |
| `prior_weights` | `JSONB` | `NOT NULL` | May be the fallback constant's weights, for the very first override |
| `new_weights` | `JSONB` | `NOT NULL` | |
| `confirmation_id` | `TEXT` | `NOT NULL` | ART-VIII attributability |

**Indexes**: B-tree on `(rubric_id, changed_at DESC)` — identical access-pattern rationale to
`agent_prompt_history`'s own index.

**Invariant**: the write to `rubric_weight_overrides` and the `INSERT` into `rubric_weight_history`
occur in the same DB transaction (identical to ADP-SPEC-042's own invariant).

## 5. `compute_business_value_score()` signature change (`adp.application.store`)

```python
def compute_business_value_score(
    scores: dict[BusinessValueDimension, int],
    weights: dict[BusinessValueDimension, float] | None = None,
) -> BusinessValueAssessmentResult:
    effective_weights = weights if weights is not None else BUSINESS_VALUE_WEIGHTS
    raw_score = sum(scores[dim] * effective_weights[dim] for dim in BUSINESS_VALUE_DIMENSIONS)
    ...  # unchanged otherwise
```

New `get_effective_weights(rubric_id: str) -> EffectiveWeights` in `adp.admin.rubric_registry`
(mirrors `get_effective_prompt(agent_id)`'s signature exactly -- self-contained, no
caller-supplied session, per that module's own established rationale for being invoked directly
from deep inside business logic), including its "any DB-resolution failure falls back to the
hardcoded default, not just 'no row found'" resilience property -- a transient DB blip must not
break every business-value assessment platform-wide.

## 6. Entity-to-API-model mapping (Pydantic v2, `extra="forbid"`, `adp.admin.rubric_models`)

| Concept | Field | API model field |
|---|---|---|
| Rubric Registration | stable identifier | `RubricView.rubric_id` |
| Rubric Registration | display name | `RubricView.display_name` |
| Rubric Registration | dimension labels | `RubricView.dimension_labels: dict[str, str]` |
| Rubric Registration | currently active weights | `RubricView.active_weights: dict[str, float]` |
| Rubric Registration | (derived) is override active | `RubricView.is_override: bool` |
| Rubric Registration | current version | `RubricView.version: int` |
| Rubric Weight Change Record | which rubric | `RubricHistoryEntry.rubric_id` |
| Rubric Weight Change Record | actor/timestamp/type | `RubricHistoryEntry.{actor,changed_at,change_type}` |
| Rubric Weight Change Record | full prior/new weights | `RubricHistoryEntry.{prior_weights,new_weights}` |

Full request/response contracts in [contracts/scoring-rubrics-api.md](./contracts/scoring-rubrics-api.md).

## State transitions (per rubric)

Identical to ADP-SPEC-042's own state diagram (data-model.md §"State transitions"), substituting
"weights" for "prompt text" throughout — no new transition shape.
