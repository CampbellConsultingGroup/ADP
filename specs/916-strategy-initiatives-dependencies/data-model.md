# Phase 1 Data Model: Strategy Execution Layer — Initiatives & Objective Dependencies

## Entities

### `strategy_initiatives` (new table)

| Column | Type | Notes |
|---|---|---|
| `id` | `String(36)` PK | |
| `name` | `Text`, not null | FR-001 |
| `description` | `Text`, nullable | |
| `owner` | `Text`, nullable | plain string, no `users` table (research.md Decision 3 / Ground-Truth Correction 2) |
| `status` | `Text`, not null, default `'planned'` | CHECK: `status IN ('planned', 'in_progress', 'blocked', 'complete', 'cancelled')` — free enum, no transition constraint (FR-003, per Clarifications) |
| `created_at` / `updated_at` | `DateTime(timezone=True)`, not null | |

### `strategy_initiative_objective_links` (new join table)

| Column | Type | Notes |
|---|---|---|
| `initiative_id` | `String(36)` | FK → `strategy_initiatives.id`, `ON DELETE CASCADE` |
| `objective_id` | `String(36)` | FK → `strategic_objectives.id`, `ON DELETE CASCADE`, indexed (the "other side") |
| `created_at` | `DateTime(timezone=True)`, not null | |

**Primary key**: `(initiative_id, objective_id)`.

### `strategic_objective_dependencies` (new self-referential table)

| Column | Type | Notes |
|---|---|---|
| `objective_id` | `String(36)` | FK → `strategic_objectives.id`, `ON DELETE CASCADE` — the dependent objective |
| `depends_on_objective_id` | `String(36)` | FK → `strategic_objectives.id`, `ON DELETE CASCADE`, indexed — what it depends on |
| `created_at` | `DateTime(timezone=True)`, not null | |

**Primary key**: `(objective_id, depends_on_objective_id)`.
**Application-layer invariant** (not DB-enforced — research.md Decision 2): the graph formed by all rows in this table is always acyclic; `objective_id != depends_on_objective_id` always holds.

## New Pydantic Models (`src/adp/strategy/initiatives.py`)

```text
InitiativeStatus = Literal["planned", "in_progress", "blocked", "complete", "cancelled"]

StrategyInitiative (read model)
  id: str
  name: str
  description: str | None
  owner: str | None
  status: InitiativeStatus
  objective_ids: list[str]   # linked objectives, mirrors StrategicObjective.capability_ids's
                              # own "denormalized list on the read model" convention
  created_at: datetime
  updated_at: datetime

StrategyInitiativeCreate
  name: str                  # required, must not be blank
  description: str | None = None
  owner: str | None = None
  status: InitiativeStatus = "planned"

StrategyInitiativeUpdate
  name: str | None = None
  description: str | None = None
  owner: str | None = None
  status: InitiativeStatus | None = None

StrategyInitiativeListResponse
  items: list[StrategyInitiative]   # summary fields only in practice (no objective_ids
                                      # expansion needed at list scope) -- decide at
                                      # implementation time whether a separate summary
                                      # model is worth it at this table's demo scale;
                                      # default to reusing the same read model, matching
                                      # how StrategicTheme has no separate summary shape
  total: int

ObjectiveDependencyCreate
  depends_on_objective_id: str

ObjectiveDependenciesResponse
  depends_on: list[str]     # objective ids this objective depends on
  blocks: list[str]         # objective ids that depend on this one (FR-008, both directions)
```

Extended existing model (`src/adp/strategy/models.py` is NOT touched — `StrategicObjective`'s read model stays as `915` left it; the "which initiatives serve this objective" list is a separate read, fetched alongside the objective by the frontend, not folded into the `StrategicObjective` Pydantic model itself, keeping `initiatives.py` fully self-contained per Decision 1).

## Relationships

```text
strategy_initiatives (many) ──< strategy_initiative_objective_links >── (many) strategic_objectives
strategic_objectives (self, many-to-many via depends_on) ──< strategic_objective_dependencies
```

No new relationship to any entity outside `adp.strategy` — this feature touches nothing in `adp.business`, `adp.application`, or `adp.store`.

## Store Functions (`src/adp/strategy/initiatives.py`)

```text
create_initiative(body, session) -> StrategyInitiative
get_initiative(initiative_id, session) -> StrategyInitiative | None
list_initiatives(session) -> StrategyInitiativeListResponse
update_initiative(initiative_id, body, session) -> StrategyInitiative | None
delete_initiative(initiative_id, session) -> bool   # unconditional -- FR-011, no in-use block

link_initiative_objective(initiative_id, objective_id, session) -> None   # raises DuplicateLinkError
unlink_initiative_objective(initiative_id, objective_id, session) -> None  # raises LinkNotFoundError
list_objective_initiative_ids(objective_id, session) -> list[str]   # reverse lookup, FR-005

add_objective_dependency(objective_id, depends_on_objective_id, session) -> None
  # raises CycleError (self-dependency or transitive cycle -- FR-007)
remove_objective_dependency(objective_id, depends_on_objective_id, session) -> None
  # raises LinkNotFoundError
get_objective_dependencies(objective_id, session) -> ObjectiveDependenciesResponse
  # both directions -- FR-008

_reaches(start, target, edges) -> bool   # private, pure BFS, no I/O (research.md Decision 2)
_would_create_cycle(objective_id, depends_on_objective_id, session) -> bool   # private, async wrapper: self-check + fetch edges + delegate to _reaches
```

`DuplicateLinkError`/`LinkNotFoundError` are **reused** from `store.py` (already public module-level exceptions there, imported into `initiatives.py` rather than redefined) — the same duplicate-link/missing-link semantics `link_objective_capability`/`unlink_objective_capability` already established. `CycleError` is new, specific to this feature.
