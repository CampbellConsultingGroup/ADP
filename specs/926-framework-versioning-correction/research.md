# Phase 0 Research: Regulatory Framework Legal Dates & Identity (COMPLY-01a)

**Feature**: 926-framework-versioning-correction
**Date**: 2026-08-19

Both of this spec's genuine scope questions (existing-data preservation, UI-vs-backend-only) were already
resolved directly with the user during `/speckit.specify` (see spec.md Clarifications). This phase resolves
the remaining *implementation* decisions needed to turn spec.md into a concrete schema, store, and API
surface — several of which correct the source document's own drafted specifics against how this codebase
actually shapes things.

## D1 — Primary key and table-naming conventions

**Decision**: `id` columns on both new tables (`framework_application_phase`, `framework_amendment`) are
`String(36)` UUID strings, matching every existing table in this codebase with no exception found
(`regulatory_frameworks`, `controls`, all five `control_*_mapping` tables, `objective_control_links`, all
five `initiative_control_*_mapping` tables). Table names themselves stay exactly as the source document
drafted them — `framework_application_phase` / `framework_amendment`, singular — which, once checked,
already matches this codebase's own real convention for a framework/control-scoped child table
(`control_capability_mapping`, not `control_capability_mappings`; `initiative_control_capability_mapping`,
same). The mismatch was specifically the source document's choice of `Integer` autoincrement PKs, not its
naming.

**Rationale**: `Integer` autoincrement appears nowhere else in this codebase's schema — every table uses a
`str(uuid.uuid4())` identity generated in the store layer, consistent with how `create_control`/
`create_framework` already work. Introducing the one `Integer`-keyed table in the entire schema would be a
new, unjustified pattern for no stated reason in the source document.

**Alternatives considered**: Following the source document's `Integer` PKs literally. Rejected — no
existing store function in this codebase generates or consumes an autoincrementing integer id; every
`_row_to_*` / `create_*` function is written around string ids throughout.

## D2 — Migration must be additive-only against real existing rows

**Decision**: `ALTER TABLE regulatory_frameworks ADD COLUMN ...` for every new field, all nullable except
`status` (which gets a `server_default='in_force'` so every existing row gets a safe, valid value with no
backfill step required). `version`, `effective_date`, `source_url`, `name`, `jurisdiction`, `authority` are
untouched — no rename, no drop, no type change. `regulation_number` carries a `UNIQUE` constraint but stays
nullable — Postgres treats multiple `NULL`s as mutually non-conflicting under a unique constraint, so the
three existing frameworks (all currently unset) do not collide with each other or block the migration.

**Rationale**: Directly implements the user's Clarification-session answer — existing data must not be
lost or require immediate re-entry. The source document's literal migration (`op.drop_column(...,
"version")`, a `NOT NULL` `regulation_number` with no backfill) would either fail outright against the
three real seeded frameworks or destroy their current version text; this migration is additive-only by
construction, so neither failure mode is possible.

**Alternatives considered**: A required `regulation_number` at the schema level, backfilled by a one-time
data migration deriving it from the existing `version` string. Rejected — `version`'s existing values are
not uniformly parseable (GDPR's alone already contains two distinct OJ citation dates run together with no
consistent delimiter), so any automated backfill would guess, not derive, the value — spec.md FR-011
explicitly rules this out.

## D3 — `status` stays a directly-set field, not derived

**Decision**: `status` is a plain `Text` column with a named `CHECK` constraint restricting it to the four
spec.md FR-003 values, set directly through the API — no `compute_*_status()`-style pure function derives
it from `framework_application_phase`/`framework_amendment` rows in this pass.

**Rationale**: The source document's own Open Questions section raised exactly this tension (derive vs.
store) without resolving it. Checked directly against what this pass actually captures: neither new table
records a repeal event, so "repealed" could never be correctly derived from data this spec collects —
attempting partial derivation (deriving three of four values, storing the fourth) would be a worse,
inconsistent design than a single directly-set field. Matches spec.md's Assumptions.

**Alternatives considered**: Deriving `status` fully from phase dates (e.g., "not_yet_applicable" if
`today < min(phase.applies_from_date)`). Rejected for this pass — correct for exactly one of the four
status values, and a partial-derivation design was judged worse than a uniform directly-set field; revisit
once a real repeal-tracking need surfaces.

## D4 — `RegulatoryFrameworkDetail` nests the new child lists, mirroring `controls`

**Decision**: `RegulatoryFrameworkDetail` (already returned by `GET /frameworks/{id}`, already nesting
`controls: list[ControlNode]`) gains `application_phases: list[FrameworkApplicationPhase]` and
`amendments: list[FrameworkAmendment]`, assembled by `get_framework_detail()` the same way it already
assembles the control tree — one additional `SELECT ... WHERE framework_id = ...` per list, ordered by
`applies_from_date` / `effective_date` respectively. Dedicated `POST`/`GET`/`DELETE` sub-resource routes
(mirroring `/frameworks/{id}/controls`'s own shape) still exist for create/list/remove — the nesting on
`RegulatoryFrameworkDetail` is for the "view everything about this framework in one call" case, not a
replacement for the list endpoints.

**Rationale**: `RegulatoryFrameworkDetail` already establishes exactly this shape for `controls` — reusing
it for the two new one-to-many children is a direct, proven, in-codebase precedent rather than a new
response-shape decision.

**Alternatives considered**: Dedicated list endpoints only, no nesting on the detail response. Rejected —
would make `RegulatoryFrameworkDetail` inconsistent with its own existing `controls` field for no reason,
and would cost a caller two extra round-trips to see "everything about this framework."

## D5 — Duplicate-regulation-number and missing-phase/amendment error handling

**Decision**: `DuplicateRegulationNumberError` → HTTP 409 on `create_framework`/`update_framework`,
mirroring `DuplicateControlCodeError`'s existing translation shape exactly. `ApplicationPhaseNotFoundError`
/ `AmendmentNotFoundError` → HTTP 404 on delete, mirroring `MappingNotFoundError`'s existing shape.

**Rationale**: Both are direct reuses of already-established exception-to-HTTP-status patterns in this
same file — no new translation shape invented for this spec.

**Alternatives considered**: A single generic `DuplicateFieldError`/`ChildNotFoundError` shared across
every entity in the domain. Rejected — every other typed exception in `adp.compliance.models` is
one-exception-per-condition (`DuplicateControlCodeError`, `CyclicParentError`, `MappingNotFoundError`, ...);
a generic exception would be the first departure from that convention in this file.

## D6 — Cascade delete, not app-layer blocking

**Decision**: Both new tables' `framework_id` FK carries `ON DELETE CASCADE`, matching `controls`' own
existing cascade-from-framework behavior (migration 032) exactly — deleting a framework silently removes
its application phases and amendments along with its controls, with no additional application-layer
recursion needed (spec.md FR-009).

**Rationale**: `controls.framework_id` already establishes this exact precedent for the same parent
entity; introducing a different (block-on-children) behavior for the two new child types would be an
inconsistent, unjustified departure within the same aggregate.

**Alternatives considered**: None seriously — this is a direct continuation of an already-settled pattern
one level up in the same table.
