# API Contract: Compliance Rollup Reporting — COMPLY-04

**Auth**: Both endpoints below are `GET`s and require no `ActionType` — `enforcement.py`'s
`/api/v1/compliance/` prefix rule only applies to non-`GET` methods (`SAFE_METHODS` are never
enforced), matching every other Compliance-domain read. Both endpoints internally exclude any
Application-targeted entity from their aggregates for a caller lacking
`ActionType.READ_APPLICATION_GOVERNANCE` (spec.md FR-007; research.md D2) — this is row-level
filtering baked into the aggregate numbers, not a route-level 403.

---

## GET /api/v1/compliance/frameworks/{framework_id}/rollup

Framework coverage rollup (US1) — a live count of every entity mapped to this framework's controls,
grouped by that entity's compliance status *with respect to this framework specifically* (FR-001),
plus this framework's estate-wide obligation status as a separate line if one exists (FR-003).

**Response 200** (`FrameworkCoverageRollup`):
```json
{
  "framework_id": "f-gdpr",
  "entity_counts": {
    "compliant_count": 2,
    "partial_count": 1,
    "non_compliant_count": 1,
    "not_assessed_count": 1,
    "not_applicable_count": 0
  },
  "organization_status": "partial"
}
```

`organization_status` is `null` when no control in this framework has an estate-wide obligation
mapped to it at all (data-model.md's distinction between "none exists" and "one exists, currently
Not Assessed").

**Response 404**: `framework_id` does not reference an existing `RegulatoryFramework`.

**Permission-dependent totals**: for a caller lacking `READ_APPLICATION_GOVERNANCE`, every
Application-targeted entity is excluded from `entity_counts` entirely before the counts are
computed — the same `framework_id` can legitimately return different totals to different callers
(FR-007). This is not a bug; the frontend must present it clearly (spec.md's Acceptance Scenario
US1-AS4).

---

## GET /api/v1/compliance/summary

Platform-wide compliance summary (US2) — backs the new Overview dashboard domain card, mirroring
`GET /api/v1/strategy/summary`'s own shape and purpose exactly.

**Response 200** (`ComplianceSummaryResponse`):
```json
{
  "framework_count": 3,
  "coverage_percent": 60.0,
  "at_risk_count": 3
}
```

`coverage_percent` is `null` when zero entities anywhere in the estate have any mapped control at
all (spec.md FR-009 — distinguishing "no data recorded yet" from a genuine 0%). `at_risk_count`
counts every distinctly-mapped entity across the whole estate whose *overall* (not
framework-scoped) derived compliance status is Non-Compliant or Partial.

**Permission-dependent totals**: identical filtering rule as the rollup endpoint above — Application-
targeted entities excluded from every figure for a caller lacking `READ_APPLICATION_GOVERNANCE`.

**No request body, no query parameters, no path parameters.**
