# Phase 0 Research: Derived Compliance Status

No items in Technical Context were left as `NEEDS CLARIFICATION` — this feature is a small, additive
extension of an already-established package (`adp.compliance`, COMPLY-01/COMPLY-02), and every open
question either had a direct precedent already in the codebase or was resolved with the user during
`/speckit.specify` (spec.md's Q1). This document records the concrete decisions made while turning
spec.md into a buildable plan.

## D1: No new HTTP endpoint in this pass

**Decision**: This feature adds no route to `adp.compliance.router` (or anywhere else). It ships the
pure aggregation function and one thin async dispatch helper only.

**Rationale**: spec.md's own Assumptions section states this explicitly, following the source
bundle's stated implementation order verbatim: "`compute_compliance_status()` should be built and
tested as a standalone pure function before it's wired into any store or router." COMPLY-04 (read-side
rollup, out of scope here) is where a caller — and therefore a router change and a sensitivity-gating
decision — first becomes necessary.

**Alternatives considered**: Adding a `GET /api/v1/{capabilities,applications,...}/{id}/compliance-status`
endpoint now, so the function has an immediate consumer. Rejected: it would front-run COMPLY-04's own
design of how derived status is actually surfaced (a single entity lookup vs. part of a larger rollup
payload), and would require deciding the sensitivity-gating question (spec.md's Threat Model residual
risk) before there's any concrete UI need driving that decision — better decided once, deliberately,
in COMPLY-04.

## D2: Function placement — `adp.compliance.store`, not `adp.compliance.models`

**Decision**: Both the pure aggregation function and its thin async dispatch wrapper live in
`src/adp/compliance/store.py`, alongside the four existing `list_mappings_for_{capability,
application,design,pattern}()` functions it composes with.

**Rationale**: Direct precedent check across the codebase's two existing "pure derived-status
function" examples — `adp.strategy.store.compute_status()` (`src/adp/strategy/store.py:320`) and
`adp.application.store.compute_business_value_score()` (`src/adp/application/store.py:721`) — both
live in `store.py`, not `models.py`, despite being pure/no-I/O themselves. `models.py` in this
codebase is reserved for Pydantic model definitions and typed exceptions (confirmed by reading
`adp.compliance.models` directly); derivation logic that operates *over* those models, even when
I/O-free, is store-layer convention. Keeping this function in `store.py` also puts it next to the
four `list_mappings_for_*` functions its dispatch wrapper calls, minimizing import distance.

**Alternatives considered**: `adp.compliance.models` (co-located with the `ComplianceStatus` enum it
returns). Rejected as inconsistent with the two direct precedents above — this codebase does not put
derivation logic in `models.py` regardless of I/O-purity.

## D3: Signature shape — pure aggregation takes already-fetched statuses, not `(entity_type, entity_id)` directly

**Decision**: Two functions, not one:
- `compute_compliance_status(statuses: list[ComplianceStatus]) -> ComplianceStatus` — pure, no I/O,
  the actual aggregation rule from spec.md FR-002–FR-006.
- `get_entity_compliance_status(entity_type: MappingTargetType, entity_id: str, session: AsyncSession)
  -> ComplianceStatus` — a thin async wrapper that calls the appropriate existing
  `list_mappings_for_*` function, extracts each returned `ControlMapping.compliance_status`, and
  passes the resulting list to `compute_compliance_status()`.

The source bundle's own proposed signature, `compute_compliance_status(entity_type, entity_id) ->
ComplianceStatus`, is realized as the *combination* of these two functions, not as one function that
both fetches and aggregates.

**Rationale**: Direct precedent: `adp.strategy.store.compute_status()` itself takes pre-fetched data
(`progress: list[tuple[date, Decimal]]`) as a parameter rather than performing its own database read
— the router/caller does the I/O, the pure function only aggregates. Splitting the two here achieves
exactly what spec.md's Constraints and ART-IV require: the aggregation rule (FR-002–FR-006) is
unit-testable with zero database setup, using plain Python lists of `ComplianceStatus` values, exactly
matching how `tests/unit/strategy/test_objective_status.py` tests `compute_status()` today.

**Alternatives considered**: A single function taking `(entity_type, entity_id, session)` that does
both the fetch and the aggregation inline. Rejected: it would force every unit test of the aggregation
rule itself (the bulk of this feature's test surface, per spec.md SC-001) through an async DB fixture,
which is exactly the friction ART-IV's "standalone pure function" instruction is written to avoid.

## D4: Entity-type dispatch covers exactly the four FK-enforced mapping types

**Decision**: `get_entity_compliance_status()`'s `entity_type` parameter accepts
`MappingTargetType.CAPABILITY | APPLICATION | DESIGN | PATTERN` — the four types with a real owning
entity and an existing `list_mappings_for_*` function. `MappingTargetType.ORGANIZATION` is
deliberately not a valid input to this function (raises `ValueError` if passed, since organization
mappings carry no `entity_id` at all — `list_mappings_for_organization()` does not exist as a
per-entity lookup, only as part of `list_mappings_for_control()`'s cross-table union).

**Rationale**: Direct match to spec.md's Assumptions ("Scope of entity types") and the already-real
shape of `adp.compliance.store`: there is no `list_mappings_for_organization(entity_id)` function to
call, because organization-scoped mappings have no entity to key by (single-column `control_id` PK,
per `specs/922-control-mappings/`'s own documented schema). Estate-wide/framework-level compliance
posture is a different aggregation shape entirely (per-framework, not per-entity) and is explicitly
COMPLY-04's concern.

**Alternatives considered**: Silently returning `NOT_ASSESSED` for an unsupported `entity_type`
rather than raising. Rejected: a silent fallback would be indistinguishable from a genuinely
unassessed entity and would hide a caller's programming error (passing `ORGANIZATION` where a
per-entity lookup was intended) — an explicit `ValueError` surfaces that mistake immediately,
consistent with ART-VI's "failures MUST be surfaced explicitly; silent catch-and-continue is
prohibited" even though this feature has no request/observability surface of its own.

## D5: Aggregation rule, fully specified (supersedes the source bundle's incomplete draft)

**Decision**: Given a non-empty `statuses: list[ComplianceStatus]`:

1. If any status is `NON_COMPLIANT` → `NON_COMPLIANT`.
2. Else if any status is `PARTIAL` or `NOT_ASSESSED` → `PARTIAL`.
3. Else if any status is `COMPLIANT` → `COMPLIANT` (implies the rest, if any, are `NOT_APPLICABLE`,
   since branches 1–2 already excluded every other value).
4. Else (every status is `NOT_APPLICABLE`) → `NOT_APPLICABLE`.

Given an empty list (no mapped controls at all) → `NOT_ASSESSED`.

**Rationale**: This is spec.md FR-002 through FR-006 restated as an exhaustive, order-independent
decision table — branch 4 is the resolution of Q1 (spec.md, resolved by the user: all-Not-Applicable
→ `NOT_APPLICABLE`, not folded into `NOT_ASSESSED`). Written this way, the four non-empty branches are
provably exhaustive and mutually exclusive over the 5-value `ComplianceStatus` enum, closing the gap
the source bundle's own Open Questions section flagged without resolving.

**Alternatives considered**: None beyond spec.md's own Q1, already resolved.

## D6: Test module placement and shape

**Decision**: `tests/unit/compliance/test_compliance_status.py`, containing one test function per
scenario in spec.md's Acceptance Scenarios/Edge Cases/SC-001 (at minimum: single non-compliant among
many compliant; partial/not-assessed mix; all-compliant; compliant+not-applicable mix;
all-not-applicable; empty list; the "new not-assessed mapping downgrades an otherwise-compliant
entity" scenario from User Story 2).

**Rationale**: Directly mirrors `tests/unit/strategy/test_objective_status.py`'s naming and structure
— the established, already-precedented pattern in this codebase for testing a derived-status pure
function standalone, parameter-matrix style, with zero database/async fixture involved.

**Alternatives considered**: Folding these cases into `tests/unit/compliance/test_models.py`.
Rejected: that file is for `RegulatoryFramework`/`Control` Pydantic model validation (COMPLY-01), a
different concern; a dedicated module keeps the aggregation-rule test matrix easy to find and read as
one coherent unit, matching the strategy domain's own precedent of a dedicated file per derived-status
function.
