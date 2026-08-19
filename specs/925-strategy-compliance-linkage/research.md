# Phase 0 Research: Strategy Domain Linkage — COMPLY-05

**Feature**: 925-strategy-compliance-linkage
**Date**: 2026-08-19

The spec's one genuine scope question (`ThemeFrameworkMapping` now vs. deferred) and its one load-bearing
ground-truth question (Initiative → Objective optionality) were both already resolved during
`/speckit.specify` — see spec.md's Clarifications section. This phase resolves the remaining
*implementation* decisions needed to turn `ObjectiveControlMapping`/`InitiativeControlMapping` into a
concrete schema, store, and API surface.

## D1 — `InitiativeControlMapping`'s target has no single addressable row to FK against

**The gap in the bundle's own proposal**: the bundle describes `InitiativeControlMapping` as "Composite PK
`(initiative_id, control_mapping_id)`" — implying `ControlMapping` is one entity with one ID. It is not.
COMPLY-02 (confirmed by direct inspection of `adp.compliance.store`) implemented `ControlMapping` as **five
separate physical tables** (`control_capability_mapping`, `control_application_mapping`,
`control_design_mapping`, `control_pattern_mapping`, `control_organization_mapping`), each with its own
composite primary key (`control_id` + a target-specific column, or `control_id` alone for the
estate-wide table) and **no synthetic `id` column anywhere**. There is no single `control_mapping_id` to
reference. This is the same four/five-tables-vs-one-polymorphic-table tension COMPLY-02 itself already
resolved (in favor of five FK-enforced tables, to satisfy the platform's stated database-level-integrity
NFR) — not a new problem, but a bundle assumption that didn't survive contact with how that resolution was
actually implemented.

**Decision**: Mirror COMPLY-02's own resolved shape exactly, one level up. `InitiativeControlMapping`
becomes five parallel join tables, one per `ControlMapping` target shape, each with a **composite foreign
key referencing the composite primary key** of its corresponding `control_*_mapping` table (Postgres
supports `FOREIGN KEY (a, b) REFERENCES other_table (a, b)` against a composite PK):

| New table | Composite PK | Composite FK → |
|---|---|---|
| `initiative_control_capability_mapping` | `(initiative_id, control_id, capability_id)` | `control_capability_mapping(control_id, capability_id)` |
| `initiative_control_application_mapping` | `(initiative_id, control_id, application_id)` | `control_application_mapping(control_id, application_id)` |
| `initiative_control_design_mapping` | `(initiative_id, control_id, design_id)` | `control_design_mapping(control_id, design_id)` |
| `initiative_control_pattern_mapping` | `(initiative_id, control_id, pattern_id)` | `control_pattern_mapping(control_id, pattern_id)` |
| `initiative_control_organization_mapping` | `(initiative_id, control_id)` | `control_organization_mapping(control_id)` |

Every table also carries a plain single-column FK `initiative_id → strategy_initiatives.id`, `ON DELETE
CASCADE` on every leg. Deleting the underlying `ControlMapping` row (e.g. via COMPLY-02's existing
`delete_capability_mapping` etc.) cascades automatically to remove the initiative link — no application
code in `adp.compliance.store` needs to change; the cascade is entirely DB-level.

At the API/model layer, an `InitiativeControlMapping` is addressed the same way a `ControlMapping` already
is — `(control_id, target_type, target_id)` — so the five physical tables stay an implementation detail
behind one typed `MappingTargetType`-discriminated interface, exactly mirroring how `ControlMapping` itself
already hides five tables behind one Pydantic model.

**Rationale**: Preserves the platform's stated database-level-referential-integrity NFR (the same NFR that
already drove COMPLY-02 away from a polymorphic table) rather than quietly downgrading to an
application-layer-only check for this one link type. Five tables is more schema surface, but it is the
*same* schema surface COMPLY-02 already committed to, applied consistently rather than abandoned the first
time it got one level more complex.

**Alternatives considered**:
- *Give each `control_*_mapping` table a synthetic `id` column, then one `initiative_control_mapping`
  table with `(initiative_id, control_mapping_id)`.* Rejected — this is a breaking schema change to
  COMPLY-02's already-shipped tables (adds a column every existing store function, test, and migration
  would need to account for) purely to make this one new feature's schema smaller. Not proportionate.
- *One `initiative_control_mapping` table with plain `(initiative_id, control_id, target_type,
  target_id)` columns, validated at the application layer only (no composite FK).* Rejected for the same
  reason COMPLY-02 rejected the polymorphic table originally — Postgres cannot FK-constrain a
  type-discriminated target, so referential integrity for this link would silently regress to
  application-layer-only, the exact outcome COMPLY-02 was designed to avoid.

## D2 — Package placement: `adp.strategy`, not `adp.compliance`, owns the new tables

**Decision**: Both new link concepts live inside `adp.strategy` — `ObjectiveControlMapping` extends
`adp.strategy.store` (alongside the existing `_objective_design_links`/`_objective_application_links`
tables and `design_exists`/`application_exists` helpers from ADP-d8u.2), and `InitiativeControlMapping`
extends `adp.strategy.initiatives` (alongside the existing `_initiative_objective_links` table). Forward
operations (link/unlink, and each entity's own "my linked controls/mappings" read) are exposed as new
routes on the existing `adp.strategy.router`, under the already-registered `("/api/v1/strategy/",
WRITE_BUSINESS_ARCH)` prefix rule — no new `ActionType`, no `enforcement.py` change.

Reverse-lookup routes ("given a Control, which Objectives"; "given a `ControlMapping`, which Initiatives")
live on `adp.compliance.router`, importing `adp.strategy.store`/`adp.strategy.initiatives` functions
through a new `_get_strategy_session()` dependency — the exact mechanism `adp/api/routers/designs.py`
already uses to call `sstore.list_objectives_for_design()` for ADP-d8u.2's own reverse lookup.

Both packages gain narrow, read-only mirror tables of the other side's key columns for existence checks
and JOIN reads, following `adp.strategy.store`'s own established `_designs`/`_applications` mirror-table
idiom (which also carries display columns like `title`/`name`, not just the PK) — `adp.strategy.store`
gains mirror tables for `controls` and the five `control_*_mapping` tables (including their
`compliance_status`/`evidence_ref`/etc. columns, so a live status can be returned directly via JOIN, not a
separately-fetched or duplicated value — see D3). No new cross-package Python import is introduced in
either direction beyond what ADP-d8u.2 and COMPLY-02 already established for their own reverse lookups.

**Rationale**: `ObjectiveControlMapping`/`InitiativeControlMapping` are structurally identical to
`objective_design_links`/`objective_application_links` — a Strategy entity gaining a traceability link into
another domain's already-registry-owned entity. ADP-d8u.2 (migration 028) already established exactly this
shape and this package placement for "Strategy reaches into a foreign domain," including the
zero-cross-package-import discipline via mirror tables. Following it here means COMPLY-05 introduces no new
architectural pattern — it is a direct, fourth application of an already-proven one (Capability/ValueStream
[025], Design/Application [028], and now Control/ControlMapping).

**Alternatives considered**: Own both tables in `adp.compliance` instead, mirroring COMPLY-02's own
"writes live with the governing Control side" placement. Rejected — COMPLY-02's placement makes sense
because `ControlMapping` *is* fundamentally about the Control (the traceability link a Control needs to be
attributable to what it governs). `ObjectiveControlMapping`/`InitiativeControlMapping` are the reverse
shape: they are about *why an Objective/Initiative exists*, which is Strategy's own question to answer
about itself, not Compliance's. Placing them in `adp.strategy` also keeps the direction of package-import
asymmetry consistent platform-wide: `adp.strategy` is already the domain that reaches into other domains
(Business, Application, Design) via its own mirror tables, and other domains' *routers* (not their store
packages) reach back into `adp.strategy.store` for reverse lookups — `adp.compliance.router` doing the same
is a direct continuation of that existing asymmetry, not a new one.

## D3 — Live status via mirror-table JOIN, never a duplicated/synced field

**Decision**: `adp.strategy.store`'s new mirror tables for the five `control_*_mapping` tables include
`compliance_status` (and the other display columns: `evidence_ref`, `assessed_at`, `assessed_by`) as
read-only columns, not just the key columns needed for the FK/existence check. The function backing
"list an Initiative's linked control mappings" performs a live JOIN against these mirror tables (same
physical Postgres database, same session) every time it is called — there is no cached or copied status
value anywhere in the new tables themselves (spec.md FR-008).

**Rationale**: This is the mechanism, not just the intent, behind FR-008 ("the compliance status shown
... MUST always reflect that mapping's current, live `compliance_status`"). Since the new join tables
carry no status column of their own at all, there is no field that *could* drift — the guarantee is
structural, the same way `adp.strategy.store`'s `_designs`/`_applications` mirrors already return live
`title`/`name` on every reverse-lookup call rather than a value captured at link-creation time.

**Alternatives considered**: Denormalize `compliance_status` onto the new link row at link-creation time,
refreshed by a background job or on every compliance-mapping write. Rejected outright — this is exactly the
class of separately-maintained, drift-prone rollup ADR-II (the model is the single source of truth) and
this feature's own "Why" section exist to eliminate; COMPLY-03/04 already established the platform's
convention of computing status live rather than storing a derived copy, and this feature is a direct
extension of that same posture into a new access path, not an exception to it.

## D4 — Addressing an `InitiativeControlMapping`'s target over the API

**Decision**: The link/unlink/reverse-lookup routes address a specific `ControlMapping` the same way
COMPLY-02's own routes already do: `control_id` plus `target_type` (`capabilities` / `applications` /
`designs` / `patterns` / `organization`) plus, for the four entity-targeted shapes, `target_id` — e.g.
`POST /api/v1/strategy/initiatives/{initiative_id}/control-mappings/capabilities/{control_id}/{capability_id}`.
The five physical tables from D1 are selected internally by `target_type`; callers never see or need to
know about the underlying table split.

**Rationale**: Reuses COMPLY-02's own already-proven, already-tested URL shape and target-type vocabulary
verbatim rather than inventing a second addressing scheme for what is conceptually the same "which of five
shapes" problem. A frontend that already renders a `ControlMapping`'s `target_type`/`target_id` (from
COMPLY-02) can pass those same two values straight through to link an Initiative to it, with no translation
step.

**Alternatives considered**: A single opaque composite token (e.g. `"capability:CTRL-1:CAP-2"`) as one path
segment instead of three. Rejected — adds an encode/decode step on both client and server for no benefit
over the existing multi-segment convention every other COMPLY-02 route already uses.

## D5 — Duplicate-link handling

**Decision**: `DuplicateLinkError` → HTTP 409, reusing `adp.strategy.store`'s existing exception and the
exact translation already used by `link_objective_design`/`link_objective_capability` — no new exception
type. `INSERT ... ON CONFLICT` is not used (matches ADP-d8u.2's own precedent of a plain `INSERT` with a
caught unique-violation, not COMPLY-02's D3 upsert-in-place pattern — these links have no mutable payload
of their own to update, only existence, exactly like every other bare Strategy link table).

**Rationale**: `ObjectiveControlMapping`/`InitiativeControlMapping` carry no fields beyond the two (or
three) FK columns and `created_at` — there is nothing to "update in place" the way a `ControlMappingWrite`
upsert needs to. Re-linking an already-linked pair is a genuine duplicate attempt, not an edit, so the bare
existence-link precedent (409 on duplicate) is the correct match, not COMPLY-02's richer-payload upsert
precedent.

**Alternatives considered**: Silent no-op on a duplicate link attempt instead of 409. Rejected — every
existing bare link table in the platform (`objective_capability`, `objective_design_links`, ...) already
409s on a duplicate; a silent no-op here would be a new, inconsistent behavior for no stated requirement.
