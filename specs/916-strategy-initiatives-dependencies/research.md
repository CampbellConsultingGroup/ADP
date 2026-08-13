# Phase 0 Research: Strategy Execution Layer — Initiatives & Objective Dependencies

Every decision below is grounded in a direct read of existing code, continuing the four corrections already recorded in `plan.md`'s "Ground-Truth Corrections" section.

## Decision 1: Submodule wiring — `initiatives.py` + the existing `router`

**Decision**: `src/adp/strategy/initiatives.py` is a new file holding this feature's Pydantic models, `sa.Table` defs, and store functions (mirroring `store.py`'s own style exactly — same `_now()`/`_rowcount()` helpers reused by importing them from `store.py` rather than duplicating, and critically the **same `_metadata` object** imported from `store.py` rather than a fresh `sa.MetaData()` — every existing test fixture's `sstore._metadata.create_all` needs to pick up these new tables too, since linking an initiative to an objective needs both `_objectives` and `_initiatives` present in the same in-memory-SQLite test database). `router.py` imports the store functions and models from `initiatives.py` and adds new `@router.post`/`@router.get`/etc. handlers directly onto the **same** `router = APIRouter(prefix="/api/v1/strategy", ...)` object already defined there — no second router, no new URL prefix.

**Rationale**: Keeps the "submodule inside `adp.strategy`" decision (spec.md Ground-Truth Correction 1) from becoming a second axis of API surface — every route stays under `/api/v1/strategy/`, gated by the exact same existing `ActionType.WRITE_BUSINESS_ARCH` prefix rule, with zero `adp.authz.enforcement` changes needed. `models.py`/`store.py` stay untouched, avoiding re-bloating the two files `915` already extended once this session.

**Alternatives considered**: Adding everything directly into the existing `models.py`/`store.py`/`router.py` (no new file). Rejected: this is exactly the "keep growing the same three files forever" pattern the bead's own §3.2 decision was raised to avoid — the line-count measurement (1,434 lines, Ground-Truth Correction 1) was taken specifically to decide *whether* to keep doing that, and going with a submodule is the natural reading of that decision once it clearly wasn't "sibling package" either.

## Decision 2: Cycle-detection algorithm

**Decision**: Split into a pure reachability check and a thin async DB-fetching wrapper, mirroring `store.py`'s own `compute_status()` precedent (a pure function operating on pre-fetched data, not one that queries mid-traversal):

- `_reaches(start: str, target: str, edges: dict[str, list[str]]) -> bool` — pure, no I/O. Breadth-first traversal starting at `start`, following `edges[node]` outward, `set`-tracked so it's bounded by the graph's total node count and always terminates. Returns whether `target` is reachable from `start`.
- `_would_create_cycle(objective_id, depends_on_objective_id, session) -> bool` — async. Self-dependency (`objective_id == depends_on_objective_id`) short-circuits `True` immediately, no query needed. Otherwise fetches every existing `(objective_id, depends_on_objective_id)` row from `strategic_objective_dependencies` into an in-memory adjacency dict, then delegates to `_reaches(depends_on_objective_id, objective_id, edges)` — treating a dependency edge `(X, Y)` as "X depends on Y", if `Y` can already reach `X` through existing edges, adding `(X, Y)` would close a cycle (`X` depends on `Y` depends on ... depends on `X`).

**Rationale**: This is the standard "would adding this edge create a cycle in a DAG" check — reachability from the new edge's target back to its source. It's the one piece of business logic FR-007 requires that isn't expressible as a database constraint (a `CHECK` can't reason about the transitive closure of a self-referential table), so it lives in `initiatives.py`-style application code, exactly as the bead itself already anticipated ("flag this explicitly in code review as the one piece of business logic here that isn't DB-enforced"). Separating `_reaches` from the DB fetch keeps the actual graph-traversal logic (the part worth testing exhaustively — direct/chained/self cycles, non-cyclic additions) fully unit-testable with plain Python dicts, no session fixture, no async test machinery — exactly how `compute_status()`'s own test suite (`test_objective_status.py`) stayed dependency-free.

**Alternatives considered**: A recursive CTE query run directly against Postgres to compute reachability. Rejected: adds a second, SQL-dialect-specific code path alongside every other `adp.strategy` store function's plain `sa.select`/Core style, and — per the existing test-infrastructure precedent (`tests/unit/strategy/test_strategy_store.py`'s own header comment, `AsyncMock`-based tests exist specifically because SQLite can't run Postgres-only syntax) — would be untestable at the fast in-memory-SQLite unit layer this package's tests already rely on for everything except the one Postgres-only aggregate query (`get_summary_stats`). A small, pure, testable BFS in Python is simpler and keeps the whole package on one test strategy.

## Decision 3: Table shapes

**Decision**:

`strategy_initiatives` — `id` (String(36) PK), `name` (Text, not null), `description` (Text, nullable), `owner` (Text, nullable — Ground-Truth Correction 2), `status` (Text, CHECK'd to the fixed 5-value set, not null, default `'planned'`), `created_at`/`updated_at` (DateTime).

`strategy_initiative_objective_links` — composite PK `(initiative_id, objective_id)`, both `String(36)` FK'd `ON DELETE CASCADE` to their respective parents, `created_at` — the exact join-table shape every prior `adp.strategy` join table already uses (migration 025's `strategic_objective_capabilities`, migration 026's implicit pattern).

`strategic_objective_dependencies` — composite PK `(objective_id, depends_on_objective_id)`, **both** columns FK'd `ON DELETE CASCADE` to `strategic_objectives.id` (two separate FK constraints against the same parent table — standard, needs two distinct constraint names since Postgres/SQLAlchemy auto-naming would otherwise collide), `created_at`.

**Rationale**: Direct continuation of the composite-PK/CASCADE/one-index shape `025`/`026` already established. The two-FK-to-the-same-table shape for `strategic_objective_dependencies` is unusual only in that it's self-referential, not in its actual DDL — Postgres has no special restriction on two FKs from one table pointing at the same parent, as long as the constraint names are distinct.

## Decision 4: Reverse lookups

**Decision**: Three read paths this feature needs beyond simple CRUD:
- An objective's linked initiatives (reverse of "initiative → objectives it serves") — a plain `SELECT initiative_id FROM strategy_initiative_objective_links WHERE objective_id = ...` then a batch fetch, mirroring `store.py`'s own `_linked_capability_ids`/`_linked_value_stream_ids` helpers exactly.
- An objective's "depends on" list — `SELECT depends_on_objective_id FROM strategic_objective_dependencies WHERE objective_id = ...`.
- An objective's "blocks" list (the reverse direction — what depends on *it*) — `SELECT objective_id FROM strategic_objective_dependencies WHERE depends_on_objective_id = ...`.

**Rationale**: All three are single indexed-column lookups against tables already sized for exactly this access pattern — no new query technique, just the established "helper function returning a list of ids, called from the read-model assembly function" convention `store.py` already uses for every other relationship in this package.

## Decision 5: Migration structure

**Decision**: One new Alembic revision, `027_strategy_initiatives.py` (`down_revision = "026"`), creating all three tables in one migration (no backfill — every table here is genuinely new, no existing data to migrate).

**Rationale**: Matches `025`'s and `026`'s own precedent of grouping a feature's full table set into one revision rather than splitting across several.
