# Phase 0 Research: Objective Progress Tracking, Lifecycle Status & Theme Management

Every decision below is grounded in a direct read of existing code (cited inline), not assumption — continuing the three corrections already recorded in `plan.md`'s "Ground-Truth Corrections" section (themes already exist as an entity; no `users` table anywhere; the real permission gate is `ActionType.WRITE_BUSINESS_ARCH`; audit is structured logging, not a real `AuditEntry` row).

## Decision 1: Status derivation algorithm

**Decision**: `compute_status(objective, progress_entries) -> ObjectiveStatus` is a pure function in `store.py`, called on every read (inside `get_objective`/`list_objectives`/`list_objectives` summary path), never persisted for its three non-terminal outputs. Logic:

1. If `objective.status == "abandoned"` (the one persisted, human-set value) → return `"abandoned"` immediately, ignore progress entirely.
2. If `objective` has no target (`metric_name`/`target_value`/`target_unit`/`direction` are the all-or-nothing group already validated by `_metric_group_all_or_nothing` — either all four are set or none are) → return `"proposed"` (FR-008: "not measurable," not an error, not a guess).
3. If zero progress entries exist → return `"proposed"` (FR-005: distinct from at-risk).
4. If the latest entry's `actual_value` has reached-or-passed `target_value` in the direction implied by `direction` (`"increase"`: `actual >= target`; `"decrease"`: `actual <= target`; `"reach"`: `actual == target`, compared as `Decimal`, never float, matching the existing `sa.Numeric(14, 2)` column type and the codebase-wide "never floating point" convention already stated in the doc) → return `"achieved"`.
5. Otherwise, look at up to the last 3 entries (oldest to newest of the most recent 3, or fewer if the objective has fewer). Compute the trend: is the most recent value farther from target than the one before it (for however many consecutive pairs exist)? If every available consecutive pair moves away from target → `"at_risk"`. Otherwise → `"active"`.

**Rationale**: This keeps status entirely a function of already-stored data (ART-II), matches the spec's FR-004 through FR-008 exactly, and needs no new persisted field beyond the one genuinely-new column (`status`, which only ever holds `NULL`/`"abandoned"` — see Decision 2).

**Alternatives considered**:
- Persisting a computed status column, updated by a trigger or on every write. Rejected: violates ART-II's "derived from the model, not a separately hand-maintained artifact" more directly than computing on read; also the trend window (N=3) needs to remain adjustable without a migration if it's ever made configurable (Assumptions: not configurable *in this version*, but computing on read keeps that door open cheaply for a later version).
- A percentage-distance threshold for "at risk" instead of directional trend. Rejected: the spec's own FR-007 defines at-risk purely in terms of trend direction ("recent recorded values are trending away from its target"), not distance — a threshold would be inventing a requirement, not implementing the stated one.

## Decision 2: `status` column shape

**Decision**: `strategic_objectives.status` is `TEXT`, **nullable**, with a named CHECK constraint restricting it to exactly one value when set: `'abandoned'`. `NULL` is the resting state for every objective whose status is one of the three derived values — the column exists solely to hold the one value a human can actually set. `status_reason` is `TEXT`, nullable, required at the Pydantic layer (not a DB constraint — the existing `_metric_group_all_or_nothing`-style all-or-nothing validation precedent in `models.py` is the right place for this, not a CHECK) whenever `status = 'abandoned'`.

**Rationale**: Storing a full 5-value CHECK-constrained enum (matching the bead's literal proposal) would create a column that's usually stale (three of its five values are never trustworthy without also checking progress) — a `NULL`-means-"compute it" / `'abandoned'`-means-"trust this" shape makes the derived-vs-manual split visible in the schema itself, not just in application logic.

**Alternatives considered**: A full 5-value `TEXT` + CHECK (`proposed`/`active`/`at_risk`/`achieved`/`abandoned`), written by the store function on every read alongside the derived computation, kept in sync. Rejected: this is the "persist the derived value" option Decision 1 already rejected, restated at the column level — same ART-II concern.

## Decision 3: Same-day correction — API shape

**Decision** (implements spec.md's resolved Clarification): `PATCH /strategy/objectives/{objective_id}/progress/{as_of_date}` edits an existing entry's `actual_value`/`note` in place. No surrogate `id` column is needed on `strategic_objective_progress` — the composite primary key `(objective_id, as_of_date)` the bead already specified is exactly the natural URL key for both the create-conflict check (`POST` to the collection, 409 if the date exists) and the edit (`PATCH` to the specific date).

**Rationale**: Matches the existing `PATCH /objectives/{id}/status`-style per-resource-under-parent shape already planned for the abandon action, and needs no schema change beyond what the bead already specified — the composite PK was never actually a blocker for editability, only for a second *create* on the same date.

**Alternatives considered**: A surrogate UUID `id` PK with a separate unique index on `(objective_id, as_of_date)`, allowing a documented "supersede" pattern (the doc's own §8 open question). Rejected by the resolved clarification: the user chose in-place editing over a systematically-different supersede model, which needs no surrogate key at all.

## Decision 4: Theme `priority` representation

**Decision**: `strategic_themes.priority` is `SmallInteger`, nullable, with a named CHECK constraint `priority IS NULL OR priority BETWEEN 1 AND 5`.

**Rationale**: Directly mirrors the existing `strategic_relevance`/`maturity_level` precedent (`020_capability_strategic_relevance.py`, `021_capability_maturity.py`) — same type, same nullable-with-CHECK shape, same "ordered scale, not free text" rationale migration `025`'s own header comment already draws the theme/objective-field distinction around (`direction`/`period` are semantic CHECK-constrained text; `strategic_relevance`/`maturity_level` are ordered SmallInteger). Priority is an ordered ranking, so it follows the SmallInteger family, not the semantic-text family.

**Alternatives considered**: None seriously — this is a direct, unambiguous precedent match, not a genuine design choice.

## Decision 5: `owner`/`recorded_by` field type

**Decision**: `strategic_themes.owner` and `strategic_object_progress.recorded_by` are both `TEXT`, nullable for `owner` (matches the spec's "optional description, owner, priority" framing — themes can exist without one), **not nullable** for `recorded_by` (every progress entry is recorded by someone, always known from the request's `_get_actor(request)`).

**Rationale**: Already established in `plan.md`'s Ground-Truth Correction 2 — there is no `users` table; every comparable field in this codebase (`strategic_objectives.owner`, `AuditEntry.actor`, `element_technology_tags.owner_team`) is `TEXT`.

## Decision 6: Where `_get_actor` comes from for progress/abandon writes

**Decision**: Reuse `adp.strategy.router`'s existing `_get_actor(request)` helper unchanged — it's already defined, already the exact function every other write in this router calls, and needs no new parameter or variant for progress/theme/abandon endpoints.

**Rationale**: No new code needed; this is a direct reuse, called out explicitly so the plan doesn't accidentally duplicate it.

## Decision 7: Migration structure

**Decision**: One new Alembic revision, `026_objective_progress_status.py` (`down_revision = "025"`), containing three operations: `CREATE TABLE strategic_objective_progress` (composite PK `(objective_id, as_of_date)`, FK `objective_id -> strategic_objectives.id ON DELETE CASCADE`, per FR-016), `ALTER TABLE strategic_themes ADD COLUMN description/owner/priority` (all nullable, no backfill needed — existing rows simply get `NULL`), `ALTER TABLE strategic_objectives ADD COLUMN status/status_reason` (both nullable, no backfill needed — existing objectives have no progress yet, so every one legitimately resolves to `"proposed"` on first read with `status IS NULL`, matching Decision 2 exactly with zero data migration required).

**Rationale**: No backfill is needed anywhere in this migration — a genuine, verified difference from the bead's original assumption (which expected a theme tag-to-FK backfill that turned out to already be done). This is the simplest possible migration: two `ALTER TABLE ADD COLUMN` sets and one `CREATE TABLE`, no data movement.

**Alternatives considered**: None — there's no backfill decision to make once Ground-Truth Correction 1 (themes already exist) is accounted for.
