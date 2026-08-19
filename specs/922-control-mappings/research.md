# Phase 0 Research: Control Mappings (Traceability Links) — COMPLY-02

**Feature**: 922-control-mappings
**Date**: 2026-08-18

Three structural questions were already resolved by the user directly during `/speckit.specify`
(Clarification Session 2026-08-18, recorded in spec.md) rather than left for this phase: mapping table
shape (four dedicated FK tables), estate-wide obligation support (yes, a fifth no-target-leg shape), and
read-gating (inherit the target's own existing gate). This phase resolves the remaining *implementation*
decisions needed to turn those into a concrete schema, store, and API surface.

## D1 — Table shapes and primary keys

**Decision**: Five tables, mirroring `application_capability_links`' (migration 010) and
`strategic_objective_capabilities`' (migration 025) exact shape:

| Table | Composite PK | Target FK |
|---|---|---|
| `control_capability_mapping` | `(control_id, capability_id)` | `business_capabilities.id` |
| `control_application_mapping` | `(control_id, application_id)` | `applications.id` |
| `control_design_mapping` | `(control_id, design_id)` | `designs.id` |
| `control_pattern_mapping` | `(control_id, pattern_id)` | `knowledge_items.id` |
| `control_organization_mapping` | `control_id` (single-column PK) | — (no target leg) |

`control_id` FKs to `controls.id` with `ON DELETE CASCADE` on every table (mirrors COMPLY-01's own
cascade choice — spec.md FR-009 requires a mapping to never outlive its Control). The four entity-targeted
tables' target-side FK also cascades on delete (target entity deletion removes its mappings, same FR).

**Rationale**: Matches every existing many-to-many join in the codebase exactly (composite PK, FK on both
legs, `ON DELETE CASCADE` both sides) rather than inventing a new shape. `control_organization_mapping`
has no target leg by definition (spec.md FR-002) — a single-column PK on `control_id` means at most one
estate-wide assessment per Control, which is the natural reading of "record *that* Control's estate-wide
assessment" (one Control, one obligation, one current status).

**Alternatives considered**: A composite PK on `control_organization_mapping` with a redundant constant
`scope` column — rejected as needless complexity; `control_id` alone is already unique per row's intended
meaning.

## D2 — Read gating implementation

**Decision**: `require_action_dep(ActionType.READ_APPLICATION_GOVERNANCE)` attached per-route
(`dependencies=[Depends(...)]`) on the *Application-targeted* mapping read routes only — both the
reverse-lookup (`GET /applications/{app_id}/compliance-mappings`) and any Application rows returned by the
forward lookup (`GET /compliance/controls/{control_id}/mappings`, which must filter out
Application-targeted rows for a caller lacking that permission rather than 403 the whole response, since a
control's mappings legitimately span multiple target types with different read gates).

**Rationale**: `require_action_dep` is the platform's existing pattern for gating a sensitive GET (used
identically by `application/router.py`'s `_require_governance_read` for `/applications/{app_id}/governance`
and `/governance/renewals-soon`). Applying it directly to `.../applications/{app_id}/compliance-mappings`
is a straight reuse. The forward lookup is the one genuinely new wrinkle — it must partially filter rather
than binary-gate, since Capability/Design/Pattern/organization rows for the *same* Control stay visible to
a caller who lacks `READ_APPLICATION_GOVERNANCE`. Implemented as a filter in the router (drop
Application-targeted rows before returning) rather than a query-level restriction in the store, keeping the
store free of authorization concerns (matches the codebase's existing separation — stores never see
`ActionType`).

**Alternatives considered**: Gate the whole forward-lookup endpoint behind
`READ_APPLICATION_GOVERNANCE` whenever any Application-targeted mapping exists — rejected, it would hide
non-sensitive mappings from a caller who has every right to see them, contradicting spec.md's User Story 3
Acceptance Scenario 3 and SC-006.

## D3 — Upsert mechanism (FR-007 / FR-008: re-mapping updates, never duplicates)

**Decision (revised during implementation)**: Select-then-branch — check whether a row exists for the
(control_id, target) pair, `UPDATE` if so, else `INSERT`, catching a unique-violation on the `INSERT` branch
and falling back to `UPDATE` (self-healing a concurrent double-write race). This matches
`adp.store.store.DesignStore.save()`'s own existing upsert idiom for the `designs` table exactly.

**Original decision, corrected after hitting a real constraint**: the plan originally called for
`sqlalchemy.dialects.postgresql.insert(...).on_conflict_do_update(...)`, matching `tags.py`'s idiom. Turned
out **not to be a real precedent for this use case** once checked against how those call sites are actually
tested: `tags.py`'s upsert is only ever exercised through a fully-mocked store in its contract test (never a
real DB), and `store/store.py`'s own `on_conflict_do_update`/`on_conflict_do_nothing` usage is reserved for
idempotent, no-real-update inserts (audit log entries — "insert if absent, otherwise no-op"), not for a row
whose *values* genuinely need updating in place. Every COMPLY-01 contract test (the direct precedent for
this spec's own `test_compliance_mappings_api.py`) runs the full router against a **SQLite** (`aiosqlite`)
fixture, not Postgres — and `sqlalchemy.dialects.postgresql.insert()` produces a `postgresql`-dialect-only
`Insert` construct that a SQLite connection cannot compile at all. Caught by actually running the contract
test against the original implementation before treating it as done, not assumed correct from the plan.
Switching to select-then-branch is dialect-portable (works identically against SQLite contract tests and
real Postgres integration tests) and is already an established, tested idiom in this exact codebase for the
same class of problem (`designs` table's own create-or-update), so it's not merely a workaround — it's the
more consistent choice than the one originally planned.

**Alternatives considered**: `adp.strategy.store`'s `DuplicateLinkError`-and-409 pattern (used for bare
Objective↔Capability/ValueStream links) — rejected because those links carry no mutable payload beyond
existence; ours does (`compliance_status`, `evidence_ref`, ...), and spec.md explicitly requires re-mapping
to *update* those fields, not be rejected.

## D4 — Target-existence validation without cross-package imports

**Decision**: Lightweight mirror `sa.Table()` definitions inside `adp.compliance.store`, scoped to only
the columns needed for validation — `capabilities(id)`, `applications(id)`, `designs(id)`,
`knowledge_items(id, kind)` — queried through the same session against the same physical Postgres database.
`Control` existence is checked via a new `get_control(control_id, session) -> Control | None` added to
`adp.compliance.store` itself (same package, no mirror needed — COMPLY-01 already owns this table).

**Rationale**: Direct extension of `adp.strategy.store`'s already-established `design_exists`/
`application_exists` idiom (mirror tables + same-session query, explicitly chosen there specifically to
avoid a second cross-package session for targets that live in the same physical database). Extending that
idiom to capabilities and knowledge_items keeps `adp.compliance` free of any Python import from
`adp.business`, `adp.application`, or `adp.knowledge` — the same zero-domain-import discipline
`adp.chat`'s own tools use for a comparable reason (a package that legitimately spans every other domain
should not create a dependency edge back into any one of them).

**Alternatives considered**: Real cross-package store calls (`bstore.get_capability`, `astore.get_application`,
...) via a second `Depends`-yielded session per package, mirroring how `adp.strategy.router` validates
`capability_id`/`value_stream_id` — rejected as unnecessary plumbing for a read-only existence check
against tables in the same database; reserved in the existing codebase specifically for cases needing the
richer domain object, which existence-checking does not.

## D5 — Pattern target validation (`kind == "pattern"`)

**Decision**: App-layer check against the `knowledge_items` mirror table's `kind` column (from D4) — reject
with 422 if the referenced `knowledge_items` row exists but its `kind` is not `"pattern"`.

**Rationale**: A database FK can confirm the row exists but cannot express "and its `kind` column equals a
specific value" without a more complex composite-FK-to-partial-unique-index construction that no other
table in this codebase uses. An explicit app-layer check is simpler, consistent with the
already-established pattern of app-layer validation for rules a plain FK can't express (COMPLY-01's own
cycle/cross-framework `parent_id` checks are the direct precedent for this class of validation).

## D6 — Manual mapping deletion (not an explicit FR, added for CRUD completeness)

**Decision**: `DELETE` endpoints are provided for all five mapping shapes
(`DELETE /compliance/controls/{control_id}/mappings/{target_type}/{target_id}` and
`DELETE /compliance/controls/{control_id}/mappings/organization`), gated by the same `WRITE_COMPLIANCE`
permission as every other mutation.

**Rationale**: Spec.md's FR list covers create/update (FR-001–FR-010) and cascading auto-removal on
Control/target deletion (FR-009), but says nothing about removing a mapping directly — an omission, not a
prohibition. Every other join table in the platform (`objective_capabilities`, `capability_design_links`,
`application_capability_links`, ...) provides an unlink endpoint, and an architect correcting a
mistakenly-created mapping (e.g. mapped to the wrong Application) has no other way to fix it short of
waiting for the Control or target entity itself to be deleted, which would be a wildly disproportionate
fix. Adding it is a straightforward extension of an already-established pattern, gated by the same
permission as creating the mapping in the first place, so it introduces no new risk surface beyond what
FR-013/FR-014 already cover.

## D7 — Route ownership

**Decision**:
- **Write endpoints** (`PUT`/`DELETE` on every mapping shape) and the **forward read** (`GET` a Control's
  own mappings) live in `adp.compliance.router`, under `/api/v1/compliance/controls/{control_id}/mappings/...`
  — automatically covered by the existing `("/api/v1/compliance/", ActionType.WRITE_COMPLIANCE)` prefix
  rule in `enforcement.py` (no enforcement.py change needed for writes).
- **Reverse read** endpoints (given a target entity, list its mapped Controls) live on each target's own
  existing router: `GET /api/v1/business/capabilities/{cap_id}/compliance-mappings` (business router),
  `GET /api/v1/applications/{app_id}/compliance-mappings` (application router, gated per D2),
  `GET /api/v1/designs/{design_id}/compliance-mappings` (designs router),
  `GET /api/v1/knowledge/{item_id}/compliance-mappings` (knowledge router) — each importing
  `adp.compliance.store` for a same-physical-DB query.

**Rationale**: Control is the "owning" side of every mapping (it is what COMPLY-01 already models as a
first-class entity with its own registry), mirroring `adp.strategy.router`'s existing precedent where
Objective-side link writes (`POST /objectives/{id}/capabilities`) live in the strategy router even though
`capability_id` references a `business` entity. The reverse-lookup placement directly mirrors ADP-d8u.2's
`GET /applications/{app_id}/objectives`, which lives in `application/router.py` and imports
`adp.strategy.store` for its own cross-package, same-session query.

**Alternatives considered**: A single unified `/api/v1/compliance/mappings?target_type=...&target_id=...`
query endpoint instead of four separate reverse-lookup routes on each domain's own router — rejected as
inconsistent with the ADP-d8u.2 precedent this bundle explicitly follows (`docs/speckit-compliance-bundle_1.md`
frames COMPLY-02 as extending the STRAT-01–04-style shape), and it would mean a Capability/Application/
Design/Pattern's own detail screen has to know about a separate top-level Compliance route rather than a
predictable `.../compliance-mappings` sibling of its other reverse-lookup endpoints.

## D8 — Migration number

**Decision**: `033`, `down_revision = "032"` — confirmed against the real on-disk chain (`032` is the
current head; COMPLY-01 shipped it, this is the very next feature).

## Summary of decisions carried into Phase 1

| # | Decision |
|---|---|
| D1 | Five tables: four composite-PK entity-targeted + one single-PK organization-wide, all `ON DELETE CASCADE` both legs |
| D2 | Application-targeted mapping reads gated by `READ_APPLICATION_GOVERNANCE` via `require_action_dep`; forward lookup filters rather than binary-gates |
| D3 | `ON CONFLICT DO UPDATE` upsert, not check-then-branch |
| D4 | Mirror tables in `adp.compliance.store` for capability/application/design/knowledge_item existence — zero cross-package imports |
| D5 | Pattern `kind == "pattern"` validated app-side via the knowledge_items mirror table |
| D6 | Manual `DELETE` endpoints added for CRUD completeness, gated by `WRITE_COMPLIANCE` |
| D7 | Writes + forward-read own by `adp.compliance.router`; reverse-reads live on each target's own router |
| D8 | Migration `033`, `down_revision "032"` |
