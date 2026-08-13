# Research: Objective ↔ Design/Application Traceability

## Decision 1: No new package or submodule — extend `models.py`/`store.py`/`router.py` directly

**Decision**: Add `objective_design_links`/`objective_application_links` table defs, store functions,
and router endpoints straight into the existing three `adp.strategy` files.

**Rationale**: Measured directly (`wc -l`): `models.py` (297) + `store.py` (736) + `router.py` (563) =
1,596 lines today, well under the ~2,847-line threshold that triggered the original
`adp.business`→`adp.strategy` split. More importantly, unlike ADP-d8u.6 (which introduced a genuinely
new concept — initiatives, with its own cycle-detection algorithm — and chose a submodule for that
reason), this feature adds two more join tables of the *exact same shape* two already-existing tables in
these files use (`strategic_objective_capabilities`/`strategic_objective_value_streams`). This is "more
of the same," not new surface area; extending the existing files keeps all objective-linking logic in
one place rather than fragmenting it across `store.py` and a submodule for no structural reason.

**Alternatives considered**: A new `traceability.py` submodule (mirroring `initiatives.py`'s shape) —
rejected because there's no shared new concept (like cycle detection) to justify separating it; it would
just be more link-table boilerplate split across two files with no cohesion benefit.

## Decision 2: Design/application existence checks via a lightweight read-only table mirror, not `DesignStore.get()`/full application fetch

**Decision**: Declare `_designs` and `_applications` as minimal `sa.Table` mirrors (id-only, plus a
couple of display columns) inside `adp.strategy.store`'s own `_metadata`, used purely for
existence/JOIN queries via a second, domain-scoped session — never `DesignStore.get()` (which raises
`DesignNotFoundError` and fetches the full `ArchitectureDescription` JSONB) or the full
`adp.application.store.get_application()` call.

**Rationale**: `adp.business.store` already establishes this exact pattern for the same reason
(`_designs = sa.Table("designs", _metadata, sa.Column("id", sa.Text(), primary_key=True), ...)`,
labeled "designs table reference for JOIN queries (read-only; managed by DesignStore migration 001)").
Reusing it keeps existence checks cheap (a single-column `SELECT` against a PK) and consistent with the
codebase's own precedent, rather than introducing a second, heavier way to check "does this id exist."

**Alternatives considered**: Calling `DesignStore.get(design_id)` and catching `DesignNotFoundError` —
rejected as unnecessarily expensive (fetches full JSONB content just to check existence) and
inconsistent with `adp.business.store`'s already-established lighter-weight pattern for the identical
problem.

## Decision 3: Reverse-lookup endpoints live in the *owning* package's router, not `adp.strategy`

**Decision**: `GET /api/v1/designs/{id}/objectives` is added to `src/adp/api/routers/designs.py`;
`GET /api/v1/applications/{id}/objectives` is added to `src/adp/application/router.py`. Both open a new
strategy-scoped session (mirroring `adp.strategy.router`'s own `_get_business_session` pattern, just in
the opposite direction) and call a new public `adp.strategy.store` function
(`list_objectives_for_design`/`list_objectives_for_application`).

**Rationale**: Corrects the source doc's imprecise "`GET /store/designs/{id}/objectives` lives in
`adp.store`" — there is no `adp.store` *router*; `adp.store` is the `DesignStore` persistence class, and
the real HTTP surface for designs already lives in `src/adp/api/routers/designs.py` under
`/api/v1/designs`. Placing the reverse lookup there (and the applications equivalent in
`adp.application.router`) matches the existing "a domain exposes reads about its own entities, even when
the 'why' comes from another domain" convention this session has followed since ADP-d8u.5/.6's
themes/objective work, and the design doc's own §7 UI framing (the reverse panel belongs where the
design/application is viewed, which is that package's own screen).

**Alternatives considered**: A single `adp.strategy` endpoint like
`GET /strategy/designs/{id}/objectives` — rejected because it would put a designs-scoped read under the
strategy prefix, breaking the "reads live with the entity they're about" convention every other reverse
lookup in this codebase already follows (e.g. `GET /objectives/{id}/initiatives` lives under
`/strategy`, but that's because *initiatives* are a strategy concept; designs and applications are not).

## Decision 4: `StrategicObjective` gains `design_ids`/`application_ids` as denormalized bare-id lists

**Decision**: Extend the existing `StrategicObjective` Pydantic model with
`design_ids: list[str] = []` and `application_ids: list[str] = []`, exactly matching the existing
`capability_ids`/`value_stream_ids` fields' shape (bare id lists, not richer ref objects).

**Rationale**: Consistency — every other objective-side link surfaces as a bare id list on this same
model; introducing a different shape (e.g., `list[DesignRef]`) for just these two fields would be an
unexplained inconsistency for no functional benefit, since the frontend already has patterns for
resolving bare ids to display names (`ObjectiveCapabilityLinkEditor.tsx` does this by cross-referencing
`useCapabilities()`'s own full list).

**Alternatives considered**: A richer `DesignRef`-shaped list (a model that already exists in
`adp.business.models`, used by `list_value_stream_designs`) — rejected for the *objective's own* model
field to keep it consistent with its siblings; the *reverse*-lookup response (designs/applications
looking up their objectives) does use the analogous existing `StrategicObjectiveSummary` shape, which
already exists and is what `GET /strategy/objectives` itself returns — no new model needed there either.

## Decision 5: Both new tables ship in one migration (028), no backfill needed

**Decision**: A single new Alembic revision `028_objective_design_application_links.py`
(`down_revision = "027"`) creates both `objective_design_links` and `objective_application_links` in one
pass.

**Rationale**: Matches the source doc's own efficiency note (§6) and the established convention from
migration 008 (which created two link tables — `capability_design_links`/`value_stream_design_links` —
in one revision). Both tables are net-new relationships with zero existing data to migrate.

**Alternatives considered**: None seriously — splitting into two migrations for two additive,
independent tables would only add ceremony with no benefit.
