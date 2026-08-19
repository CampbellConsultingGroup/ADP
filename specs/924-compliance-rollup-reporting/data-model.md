# Phase 1 Data Model: Compliance Rollup Reporting

No new table, no new migration. This feature's only "data model" is the shape of two new response
types and one new internal store function pair, all computed on demand from the existing
`RegulatoryFramework`/`Control`/`ControlMapping` tables (COMPLY-01/02) via COMPLY-03's already-built
`compute_compliance_status()`.

## Reused types (unchanged)

- **`ComplianceStatus`**, **`MappingTargetType`**, **`ControlMapping`** (`adp.compliance.models`,
  COMPLY-02) — this feature's inputs.
- **`compute_compliance_status(statuses: list[ComplianceStatus]) -> ComplianceStatus`**
  (`adp.compliance.store`, COMPLY-03) — this feature's core aggregation primitive, called once per
  entity group by the new bucketing helper (research.md D1). Not modified.

## New response types (`src/adp/compliance/models.py`)

### `EntityStatusCounts`

```text
compliant_count: int
partial_count: int
non_compliant_count: int
not_assessed_count: int
not_applicable_count: int
```

A tally of how many distinct entities landed in each of the five `ComplianceStatus` buckets, for
some scope (one framework, or the whole estate). Explicit fields, not `dict[ComplianceStatus, int]`
(research.md D4). Invariant: the five counts always sum to the number of distinct
`(target_type, target_id)` pairs considered in that scope (spec.md FR-002's "cover all five
buckets, showing zero rather than omitting one").

### `FrameworkCoverageRollup` (US1, FR-001/002/003/008)

```text
framework_id: str
entity_counts: EntityStatusCounts
organization_status: ComplianceStatus | None
```

One framework's coverage picture: `entity_counts` is the framework-scoped bucketing of every entity
with at least one control from that framework mapped to it (FR-001 — status computed only from that
framework's own controls, not the entity's cross-framework status). `organization_status` is `None`
when no control in this framework has an estate-wide obligation mapped to it; otherwise it is the
result of feeding every organization-scoped mapping's status for this framework's controls through
`compute_compliance_status()` (a framework can have more than one control with its own
organization-scoped mapping — this is one aggregated line, not a list, per FR-003's "own distinct
status line," not "lines").

### `ComplianceSummaryResponse` (US2, FR-004/005/009)

```text
framework_count: int
coverage_percent: float | None
at_risk_count: int
```

`framework_count` = `count(*)` on `regulatory_frameworks`, unfiltered (frameworks themselves carry no
sensitivity gate — only individual mappings do). `coverage_percent` = 100 × (entities with overall
derived status `COMPLIANT`) / (all distinctly-mapped entities across the whole estate), `None` when
that denominator is zero (FR-009's "no data yet" distinction from a real 0%) — never divides by zero.
`at_risk_count` = count of distinctly-mapped entities whose overall derived status is `NON_COMPLIANT`
or `PARTIAL` (spec.md Assumptions' "at-risk" definition). Both `coverage_percent` and `at_risk_count`
are computed from the *unscoped* (no `framework_id` filter) entity-status bucketing — an entity's
"overall" status here mixes controls from every framework it happens to have mappings from, matching
COMPLY-03's own existing `get_entity_compliance_status()` semantics exactly (that function has never
been framework-scoped; this spec doesn't change that).

## New store functions (`src/adp/compliance/store.py`)

### `get_framework_coverage_rollup`

```text
async get_framework_coverage_rollup(
    framework_id: str,
    include_application: bool,
    session: AsyncSession,
) -> FrameworkCoverageRollup | None
```

Returns `None` if `framework_id` doesn't reference an existing framework (router maps to 404,
mirroring `get_framework_detail`'s own existing None-means-404 convention). Otherwise: fetches
framework-scoped entity rows and organization rows (research.md D3), drops
`MappingTargetType.APPLICATION` rows when `include_application` is `False` (research.md D2), buckets
the entity rows via the shared helper (research.md D1), and separately aggregates the (possibly
filtered) organization rows through `compute_compliance_status()` for `organization_status`.

**Traces to**: spec.md FR-001, FR-002, FR-003, FR-006, FR-007, FR-008; SC-001, SC-003, SC-004, SC-005.

### `get_compliance_summary`

```text
async get_compliance_summary(
    include_application: bool,
    session: AsyncSession,
) -> ComplianceSummaryResponse
```

Fetches `framework_count` via a simple count query, fetches estate-wide (unscoped) entity rows,
drops Application rows when `include_application` is `False`, buckets via the shared helper, and
computes `coverage_percent`/`at_risk_count` from the resulting `EntityStatusCounts`.

**Traces to**: spec.md FR-004, FR-005, FR-006, FR-007, FR-009; SC-002, SC-003, SC-004, SC-005.

### `_bucket_entities_by_status` (private, shared)

```text
_bucket_entities_by_status(
    rows: list[tuple[MappingTargetType, str, ComplianceStatus]],
) -> EntityStatusCounts
```

Pure, no I/O — groups `rows` by `(target_type, target_id)`, calls `compute_compliance_status()` once
per group, tallies into `EntityStatusCounts`. Independently unit-testable with plain Python tuples,
no database required, mirroring `compute_compliance_status()`'s own established testing precedent
(research.md D1).

## State transitions

Not applicable — no persisted state, no transitions. Every value in this feature's two response
types is recomputed from current data on every request (spec.md FR-006).
