# Research: Hybrid Search Phase 2 Completion

## D1: Stage indexing mirrors value stream's own write-hook shape exactly

**Decision**: `add_stage`/`update_stage`/`delete_stage` gain `index_entity`/`unindex_entity` calls
at the identical point in each function that `create_value_stream`/`update_value_stream`/
`delete_value_stream` already do, using `build_text(name, description)` — the same two-field
convention every sibling entity (capability, value stream, application) already uses.

**Rationale**: A stage is structurally identical in shape to a value stream (`name` + nullable
`description`) — there is no reason to invent a different indexing convention for it.

## D2: `reorder_stages` needs its own handling, not just the three CRUD functions

**Decision**: `reorder_stages` (a bulk delete-some/update-rest operation, not exposed as
add/update/delete individually) gets its own inline indexing: for each stage deleted (not in the
incoming list), `unindex_entity`; for each stage updated (in the incoming list, since the function
already rewrites `name`/`description`/`position` unconditionally for every surviving stage),
`index_entity` with its current text.

**Rationale**: `reorder_stages` is a genuine fourth write path distinct from the three CRUD
functions — confirmed by direct read that it can rename a stage as a side effect of reordering
(`.values(name=stage_item.name, description=stage_item.description, position=position)`), so a
naive "only wire the three CRUD functions" approach would silently miss this path and leave stale
index text after a reorder-with-rename. Re-indexing *every* surviving stage on every reorder call
(not just ones whose text actually changed) is a deliberate simplicity choice — `index_entity`'s
upsert is idempotent and cheap relative to the already-O(n) loop `reorder_stages` runs per call, so
computing a "did this one actually change" diff would add complexity for no measurable benefit at
this entity's expected scale (a handful of stages per value stream).

## D3: Cascade-unindex fix — read stage ids before the cascading delete, not after

**Decision**: `delete_value_stream` queries `_stages.c.id` for the value stream being deleted
*before* issuing the `DELETE` (which the DB-level `ON DELETE CASCADE` FK will apply to `_stages`
transparently), then calls `unindex_entity(ENTITY_VALUE_STREAM_STAGE, stage_id, session)` for each
one found, after the value stream's own delete+unindex.

**Rationale**: Once the cascading `DELETE FROM value_streams WHERE id = ...` commits, the stage
rows are already gone from Postgres — but their ids are never needed again after that point, only
for the search-index cleanup, so reading them just before the delete (not "at delete time" via
some trigger) is the correct and only order that works with a plain FK-CASCADE (no `RETURNING`
capture needed, since ADP doesn't use one here and adding one would be an unrelated, larger change
to this function's shape).

**Alternatives considered**: Switch the FK from `ON DELETE CASCADE` to application-level explicit
stage deletion (calling `delete_stage()` per stage, which already unindexes) — rejected: this would
be a real schema/behavior change (removing a DB-level guarantee this system already relies on)
merely to route around a test/consistency gap that a two-line pre-read query solves without
touching the schema at all.

## D4: `reindex_all()` is a new function, not a `reindex_capabilities()` rename

**Decision**: Add `reindex_all(session) -> dict[str, int]` (a per-entity-type count, not just a
single total — more useful for an operator diagnosing a partial backfill) as a new function in
`adp.search.backfill`; keep `reindex_capabilities()` in place internally (called by `reindex_all()`
for its two entity types) rather than deleting it, since it is still a coherent, independently
useful unit; change `main()` to call `reindex_all()` instead.

**Rationale**: The bead's literal phrasing ("`reindex_capabilities` → `reindex_all`") reads as "the
script's effective entry point changes", which `main()` calling the new function satisfies exactly,
without forcing an unnecessary rename/deletion of a function that remains a correct, coherent unit
on its own (and is a smaller, easier-to-read building block for `reindex_all` to call rather than
inlining its body).

**Alternatives considered**: A single `int` return (total count only) — rejected in favor of a
per-type breakdown dict, since an operator re-running a backfill after a partial failure benefits
from seeing *which* entity type came up short, and the marginal cost of building a dict instead of
incrementing one counter is negligible.

## D5: Backfill reads applications/value-streams/stages/domains directly, no new bulk store function

**Decision**: `reindex_all()` calls `astore.list_applications()`, `bstore.list_value_streams()` +
a direct `sa.select(bstore._stages)` (no existing "all stages across all value streams" bulk
function, confirmed by grep — same situation `928`'s `business_arch.py` hit for the identical
table, resolved there identically), and `bstore.list_domains_full()`.

**Rationale**: Every one of these already exists except the all-stages read, which mirrors the
exact precedent `adp.export.business_arch._fetch_all()` already established for this same
`_stages` table — reusing that precedent rather than adding a new store function for a single
internal caller.

## D6: Testing strategy — monkeypatch for wiring, Docker-gated integration for the real round-trip

**Decision**: Two tiers, matching this session's established pattern for anything touching
pgvector/pg-only SQL:
1. **Unit "wiring" tests** (`tests/unit/business/test_search_indexing.py`): monkeypatch
   `adp.business.store.index_entity`/`unindex_entity` (imported directly into that module's
   namespace, so patching `bstore.index_entity` intercepts every call site) to recording stubs, run
   the real store functions against a SQLite fixture (`bstore._metadata.create_all` — the
   `searchable_items` table itself is irrelevant to this tier since the real `index_entity` is
   never invoked), and assert the correct `(entity_type, entity_id, text)` triples were recorded at
   each call site — including the pre-existing 041 wiring (value stream, domain), closing Ground-
   Truth Correction #6 for code this feature didn't otherwise touch.
2. **Docker-gated integration tests** (`tests/integration/test_search.py`, extended): the real SQL
   round-trip, `SearchIndex(embedder=_FakeEmbedder())` against a live Postgres container — the file
   already has this exact fixture shape for capabilities; extending it with
   `ENTITY_VALUE_STREAM_STAGE` (and confirming `ENTITY_APPLICATION`/`ENTITY_VALUE_STREAM`/
   `ENTITY_BUSINESS_DOMAIN` also round-trip, since none of them had a single test before this
   feature) needs zero new fixture machinery.

**Rationale**: `SearchIndex.upsert()` uses `sqlalchemy.dialects.postgresql.insert(...)
.on_conflict_do_update(...)`, which cannot compile against SQLite at all (the same class of
dialect-portability problem `928`'s implementation notes recorded for a different Postgres-only
upsert construct) — so a SQLite-backed unit test can only ever verify that the *store* code called
`index_entity` correctly, never that the underlying SQL round-trips, which is exactly why both
tiers are needed and neither one alone would be sufficient.

## D7: `reindex_all()`'s own unit test avoids the same dialect problem via a recording fake, not SQLite

**Decision**: `tests/unit/search/test_backfill.py` monkeypatches
`adp.search.backfill.default_index` to return a small in-test fake object exposing an async
`upsert(entity_type, entity_id, text, session)` that appends to a list — never touching real
`SearchIndex`/pgvector/Postgres-dialect SQL at all — while the entity data itself comes from a real
SQLite-backed `bstore`/`astore` fixture (identical `_metadata.create_all()` pattern to every other
store-level unit test in this codebase).

**Rationale**: Same dialect-compilation blocker as D6 — `reindex_all()`'s own correctness (does it
call upsert for every entity of every type, with the right text) is fully unit-testable this way
without needing Postgres at all; the real upsert SQL path is already covered by D6's Docker-gated
tier.
