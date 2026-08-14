# Research: Strategy Rollups — Heat Map, Orphan Report, Richer Summary

## Decision 1: Status breakdown is a Python-side per-row tally, not a SQL `GROUP BY`

**Decision**: Both the heat map and the enriched summary's status-count fields are computed by fetching
the relevant objectives, calling the existing `_status_for_objective(row, session)` helper once per row
(already public in `adp.strategy.store`, already used by `list_objectives()`), and tallying the results
in Python.

**Rationale**: `compute_status()` (ADP-d8u.5) derives status from an objective's target/direction plus a
window of its progress-history trend — it is not a stored column and cannot be `GROUP BY`'d directly in
SQL. `list_objectives()` already establishes the exact pattern this feature needs (loop over objective
rows, call `_status_for_objective` per row); reusing it rather than inventing a second status-computation
path keeps the derivation logic in exactly one place.

**Alternatives considered**: Replicating `compute_status()`'s trend logic as a SQL window function —
rejected as significant, fragile duplication of business logic that already lives correctly in Python,
for a demo-scale dataset where the per-row loop's cost is negligible.

## Decision 2: `initiative_count` joins the existing atomic summary query as one more subquery column

**Decision**: `get_summary_stats()`'s existing single raw-SQL aggregate (`_SUMMARY_STATS_SQL`) gains one
more scalar subquery column: `(SELECT COUNT(*) FROM strategy_initiatives) AS initiative_count`. The 5
status-count fields, by contrast, are added via the Python-side pass from Decision 1 — `get_summary_stats`
now does one atomic SQL query (7 existing fields + `initiative_count`) plus one Python loop (5 status
counts), not two separate round trips per concern.

**Rationale**: `strategy_initiatives` is a plain, unconditional row count with no derived-status complexity
— a trivial addition to the query that already computes `total_objectives`/`total_themes`/etc. the same
way. No circular-import concern: this is a raw SQL string reading a table by name, not a Python
`sa.Table` object import from `adp.strategy.initiatives` (which would create `store.py` → `initiatives.py`
→ `store.py`, since `initiatives.py` already imports several names from `store.py`).

**Alternatives considered**: Importing `adp.strategy.initiatives._initiatives` as a Core `sa.Table` object
into `store.py` for a typed count query — rejected specifically because it would create that circular
import; the raw-SQL-by-table-name approach sidesteps it entirely, consistent with how the rest of
`_SUMMARY_STATS_SQL` already references tables by name in one raw string.

## Decision 3: Heat map response uses explicit per-status fields, not a `dict[str, int]`

**Decision**: `ThemeStatusCounts` (one row of the heat map) has five explicit integer fields
(`proposed_count`, `active_count`, `at_risk_count`, `achieved_count`, `abandoned_count`), not a single
`status_counts: dict[str, int]` field.

**Rationale**: ART-XIII (Typed Contracts Everywhere) — a `dict[str, str]`-keyed field produces a loose
`additionalProperties`-shaped JSON Schema and offers no compile-time guarantee the frontend reads a real
status key rather than a typo. Five named fields match `ObjectiveStatus`'s fixed 5-value set exactly and
generate a fully typed OpenAPI contract, consistent with every other Pydantic model in this codebase.

**Alternatives considered**: A dynamic dict keyed by status string — rejected for the above reason; also
considered a single flat `list[{theme_id, status, count}]` row-per-cell shape — rejected as needing more
client-side reshaping work for no benefit, when the matrix shape the Clarification already resolved on
maps naturally onto one row-per-theme with typed columns.

## Decision 4: Orphan-report cross-package linkage check reuses `adp.strategy`'s own established
lightweight-mirror-table pattern, applied symmetrically in `adp.business`

**Decision**: `adp.business.store` declares two new minimal, read-only `sa.Table` mirrors —
`_strategic_objective_capabilities` and `_strategic_objective_value_streams` (just the two id columns
each needs) — inside its own `_metadata`, used purely to compute "which capability/value-stream ids are
referenced by at least one link row," via a single session (no second cross-package session needed, since
these tables live in the same physical Postgres database).

**Rationale**: This is the exact symmetric counterpart to ADP-d8u.2's `_designs`/`_applications` mirrors
inside `adp.strategy.store` (there, `adp.strategy` needed to know if a design/application id exists;
here, `adp.business` needs to know which capability/value-stream ids are referenced by strategy's link
tables). Same established convention, same rationale, applied in the other direction.

**Alternatives considered**: Having `adp.business.router` open a second, `adp.strategy`-scoped session and
call a public `adp.strategy.store` function — rejected as unnecessary ceremony for what's structurally
identical to the already-established mirror-table pattern already proven to work for this exact kind of
cross-package existence/membership check.

## Decision 5: No new package for either `adp.strategy` or `adp.business`

**Decision**: All backend work extends the existing three-file shape (`models.py`/`store.py`/`router.py`)
in both `adp.strategy` and `adp.business` — no new submodule, no new sibling package.

**Rationale**: `adp.strategy`'s three core files total 1,889 lines pre-feature, comfortably under the
~2,847-line threshold. `adp.business`'s three core files total exactly 2,847 lines pre-feature — right at
the historical threshold — but this feature's orphan-report addition there is a single small `NOT
IN`-shaped read-function pair plus two lightweight mirror tables, not a new domain concept the way
ADP-d8u.6's initiatives (with their own cycle-detection algorithm) were. Mirrors ADP-d8u.2's own "more of
the same, not a new concept" reasoning rather than ADP-d8u.6's "new concept → submodule" reasoning.

**Alternatives considered**: A new `adp.business.orphans` submodule — rejected as unwarranted ceremony for
two functions and two mirror tables with no shared new concept to justify separating them out.
