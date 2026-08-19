# Phase 0 Research: Compliance Rollup Reporting

No item in Technical Context was left as `NEEDS CLARIFICATION` — the one genuinely open design
question (sensitivity gating of the aggregates) was resolved with the user during `/speckit.specify`
(spec.md Q1). This document records the concrete decisions made turning spec.md into a buildable
plan, grounded in two direct precedents already in the codebase: `918-strategy-rollups`' theme ×
status matrix (`GET /strategy/heatmap`) and `051-strategy-landing-card`'s Overview domain card
(`GET /strategy/summary`).

## D1: Shared bucketing helper, reused by both endpoints

**Decision**: One new private function in `adp.compliance.store`:

```text
_bucket_entities_by_status(
    rows: list[tuple[MappingTargetType, str, ComplianceStatus]],
) -> EntityStatusCounts
```

Groups `rows` by `(target_type, target_id)`, calls `compute_compliance_status()` (COMPLY-03,
unmodified) once per group on that group's list of `ComplianceStatus` values, and tallies the results
into the five-field `EntityStatusCounts` value object. Both `get_framework_coverage_rollup()` (US1)
and `get_compliance_summary()` (US2) call this same helper — the only thing that differs between them
is *which rows* they feed it (framework-scoped vs. estate-wide).

**Rationale**: This is the direct, deliberate analog of `918-strategy-rollups`' own established
pattern — `get_strategy_heatmap()` calls the same per-row `_status_for_objective()` status computation
already used by `list_objectives()`, tallying by theme in Python, because status "isn't a
SQL-aggregable column." `ComplianceStatus` is exactly the same shape of problem:
`compute_compliance_status()` is a pure Python function over a list of enum values, not something
Postgres can `GROUP BY` directly. Sharing one bucketing helper between both endpoints (rather than
duplicating the group-then-aggregate loop twice) follows this session's own established
"extract-once, reuse" discipline (e.g. `useLinkFeedback`, `checkMetricFields` from this codebase's own
prior history).

**Alternatives considered**: A single combined function returning both a framework's rollup and the
estate-wide summary in one call. Rejected: the two have different callers (one keyed by
`framework_id`, one global) and different permission-gating call sites in the router; forcing them
through one function would make the router's FR-007 filtering logic (D2 below) harder to reason
about, not easier.

## D2: Filter-before-aggregate, not filter-after-fetch — a deliberate contrast with COMPLY-02's own precedent

**Decision**: The `READ_APPLICATION_GOVERNANCE` filtering for this feature happens *before* the
bucketing helper runs, not after. Both new store functions accept a plain positional
`include_application: bool` parameter, computed by the router from
`is_permitted(user.role, ActionType.READ_APPLICATION_GOVERNANCE)` and passed in — when `False`, every
`MappingTargetType.APPLICATION`-tagged row is dropped from the raw row list before it ever reaches
`_bucket_entities_by_status()` (D1).

**Rationale**: COMPLY-02's own precedent (`list_control_mappings` in `adp.compliance.router`) filters
*after* the store call, on the final flat `list[ControlMapping]`, because that endpoint does no
aggregation at all — filtering the last mile, in the router, is sufficient and keeps the store
function itself permission-agnostic. This feature is different in one structural way: aggregation
(the bucketing/grouping) happens *inside* the store layer, not the router. If filtering happened
after the store call here, it would have to operate on already-aggregated *counts*, which cannot be
un-aggregated back into "remove exactly this one entity's contribution" — filtering must happen on
the raw per-mapping rows, before grouping, which means it must happen either inside the store function
or be threaded into it as a parameter. Passing `include_application` in is the smaller, more explicit
change, and keeps `_bucket_entities_by_status()` itself permission-agnostic and independently testable
(spec.md SC-003's reproducibility guarantee), with the permission *decision* still made once, in the
router, exactly where every other permission check in this codebase already lives.

**Alternatives considered**: Two separate store functions per endpoint (one for
`include_application=True`, one for `False`). Rejected: pure duplication of the JOIN query and the
bucketing call for a single boolean's difference — the parameter is simpler and matches how
`get_entity_compliance_status()` (COMPLY-03) already takes its `entity_type` as a plain argument
rather than needing per-type function variants.

## D3: Two new JOIN queries, not a reuse of `list_mappings_for_control`

**Decision**: Two new queries in `adp.compliance.store`:
- `_framework_entity_rows(framework_id, session)`: for each of the four entity-targeted mapping
  tables, `SELECT target_column, compliance_status FROM <mapping_table> JOIN controls ON
  <mapping_table>.control_id = controls.id WHERE controls.framework_id = :framework_id`, unioned in
  Python (four small queries, same shape `list_mappings_for_control` already uses for its own
  five-way union — this reuses that *pattern*, not that *function*, since the filter key differs:
  `framework_id` via a join, not a direct `control_id` equality). A fifth query does the same join
  against `control_organization_mapping`, kept separate from the four entity-typed ones (spec.md
  FR-003 — organization-scoped rows are never entities, never fed into the same bucketing pass as the
  other four).
- `_estate_entity_rows(session)`: identical shape, no `WHERE controls.framework_id = ...` filter at
  all — every entity-targeted mapping row across the whole estate, regardless of which framework its
  control belongs to (needed for US2's "overall derived compliance status," which per spec.md's own
  Assumptions is explicitly *not* framework-scoped, unlike US1's rollup).

**Rationale**: `list_mappings_for_control(control_id, session)` is scoped to one `control_id` at a
time — reusing it here would mean fetching every control in a framework first, then calling it once
per control (N+1 queries for a framework with N controls), which is exactly the query-shape mistake
`918-strategy-rollups`' own research.md flagged and avoided for its theme × status matrix. A direct
`JOIN ... WHERE controls.framework_id = :id` (or no filter at all, for the estate-wide case) fetches
everything needed in four (or five, or eight for the unfiltered estate case) queries total, regardless
of how many controls exist — matching this codebase's established preference for join-based bulk
reads over per-row round trips (`adp.portfolio`'s and `918`'s own precedent).

**Alternatives considered**: One giant `UNION ALL` SQL query across all four/five tables in a single
round trip. Rejected as premature optimization for demo-scale data (matching `918-strategy-rollups`'
own explicit Assumption: "no materialized view or index-backed optimization in this pass") — four or
five small, readable, independently-testable queries composed in Python is more consistent with
`adp.compliance.store`'s own existing style (`list_mappings_for_control`'s five separate `SELECT`s,
not one `UNION`) than introducing a new SQL idiom for this one feature.

## D4: Response model shapes — explicit fields, mirroring `ThemeStatusCounts` exactly

**Decision**:

```text
class EntityStatusCounts(BaseModel):        # internal value object AND the shared shape
    model_config = ConfigDict(extra="forbid")
    compliant_count: int
    partial_count: int
    non_compliant_count: int
    not_assessed_count: int
    not_applicable_count: int

class FrameworkCoverageRollup(BaseModel):
    model_config = ConfigDict(extra="forbid")
    framework_id: str
    entity_counts: EntityStatusCounts
    organization_status: ComplianceStatus | None   # None = no estate-wide obligation mapped
                                                      # to any control in this framework (FR-003)

class ComplianceSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    framework_count: int
    coverage_percent: float | None   # None = zero mapped entities at all, distinct from 0.0
                                       # (spec.md Edge Cases: "no data yet" vs. a real 0%)
    at_risk_count: int
```

**Rationale**: Directly mirrors `adp.strategy.models.ThemeStatusCounts`'s own documented reasoning —
"Explicit fields, not a `dict[str, int]`, per ART-XIII" — so every field is independently typed and
validated, and a client can't receive a key it didn't expect. `organization_status` as `| None` rather
than a zeroed/default status value correctly distinguishes "no estate-wide obligation exists for this
framework" from "one exists and its status happens to be, say, Not Assessed" — collapsing those two
would silently misrepresent a framework with no organization-scoped mapping at all as having one.
`coverage_percent` as `float | None` for the identical reason, resolving spec.md's own named edge
case (an empty estate must never render as an indistinguishable 0%).

**Alternatives considered**: Reusing `ComplianceStatus` as a `dict[ComplianceStatus, int]` for the
counts. Rejected for the same reason `918-strategy-rollups` rejected it for `ThemeStatusCounts` —
explicit fields are simpler to consume from the frontend without an enum-keyed-dict adapter, and match
this package's own established convention exactly.

## D5: Endpoint placement and permission wiring

**Decision**: Both endpoints live in `adp.compliance.router`, mirroring `918`'s
`GET /strategy/heatmap` and `051`'s `GET /strategy/summary` both living in `adp.strategy.router` (not
a cross-domain aggregator like `adp.portfolio`, since — unlike Portfolio's own summary, which
genuinely spans Application+Design data — this feature's data is entirely within the Compliance
domain's own tables). Both take `user: AuthenticatedUser = Depends(get_current_user)` as a parameter
(the exact same dependency `list_control_mappings` already uses) to compute the
`include_application` boolean via `is_permitted(...)` before calling the store function (D2). Neither
endpoint requires a new `ActionType` — both are reads, and per COMPLY-02's own established convention,
`enforcement.py`'s `/api/v1/compliance/` prefix rule only applies to non-`GET` methods (`SAFE_METHODS`
are never enforced), so no route-level permission dependency is added at all; the
`READ_APPLICATION_GOVERNANCE` check is purely the inline row-filtering decision already established.

**Rationale**: Consistent placement with every other Compliance-domain read; no new package, no new
router file — matches this feature's own `plan.md` Scale/Scope ("zero new tables... zero new
`ActionType`").

**Alternatives considered**: A route path under each individual entity type's own router (mirroring
how COMPLY-02's *reverse-lookup* endpoints live on each target's own router). Rejected: those
reverse-lookup routes exist because they answer "what controls map to *this one already-known
entity*" — naturally owned by that entity's router. This feature's rollups answer "what does *this
framework* (or the whole estate) look like," a Control-and-Framework-centric question with no single
owning entity router to attach to — exactly the same reasoning that already placed every *other*
Control-mapping-write and forward-lookup route in `adp.compliance.router` itself (COMPLY-02's own
`research.md D7`).

## D6: Frontend placement

**Decision**: US1's rollup display is a new block on `FrameworkDetail.tsx` (the screen an architect
is already looking at when they want a specific framework's coverage), fetched via a new
`useFrameworkRollup(frameworkId)` hook. US2's summary card is a new `DOMAINS` array entry on
`OverviewPage.tsx`, fetched via a new `useComplianceSummary()` hook — both new hooks added to the
already-existing `web/src/api/compliance.ts`, mirroring `useStrategySummary()`'s own shape in
`web/src/api/strategy.ts` exactly (a single `useQuery` call, no polling, standard TanStack Query
defaults already used everywhere else in this file).

**Rationale**: Directly matches `051-strategy-landing-card`'s own precedent (`OverviewPage.tsx`'s
`DOMAINS` array, `shield` icon already established for Compliance's own nav entry in `AppShell.tsx`
from COMPLY-01) for the summary card, and matches this session's own established convention of adding
a new read-side view to an already-existing detail screen (`ApplicationComplianceMappings.tsx` on
`ApplicationDetail.tsx`, `CapabilityComplianceMappings` on `CapabilityNode.tsx`) for the per-framework
rollup.

**Alternatives considered**: A dedicated new "Rollup" tab/screen inside Compliance. Rejected as
unnecessary scope beyond what spec.md's User Story 1 actually asks for ("view that framework's
coverage rollup") — `FrameworkDetail.tsx` is already the screen that shows one framework's detail, and
the rollup is additional detail about that same framework, not a separate concern needing its own
navigation entry.
