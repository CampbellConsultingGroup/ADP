# Implementation Plan: Capability Model Analysis

**Branch**: `938-capability-model-analysis` | **Date**: 2026-11-15 | **Spec**: [spec.md](spec.md)
**Input**: `/specs/938-capability-model-analysis/spec.md` (bead ADP-6et.2, epic ADP-6et).

## Summary

This feature analyses the three-layer capability model that 937 stored. A pure engine (`adp.application.cap_analysis`) runs over a per-request snapshot and computes:
- health, risk and cost roll-ups up the business capability tree, using the worst value plus the spread over leaves and excluding retired applications;
- each technical capability's effective lifecycle band;
- the impact of a technical capability, traced from technical up to business;
- business technology exposure and dependencies;
- gaps, overlaps and shared application capabilities.

Nothing is stored except a new technical capability lifecycle: a status plus an optional end-of-life date (migration `047`). Four new GET routes sit on the 937 router under `/analysis/`. Cost and risk are gated inline and never loaded for callers without the permission.

The UI extends existing screens:
- four new Business heat map metrics, plus a "Technology dependencies" expander on business L3s;
- lifecycle fields and an Impact panel on technical capabilities;
- Overlaps, Gaps and Shared views on Applications → Capabilities.

Zero new packages, no new permission.

## Technical Context

**Language/Version**: Python 3.12 (3.11+) and TypeScript 5.x + React 18 (existing).
**Primary Dependencies**: FastAPI, SQLAlchemy 2 async Core, Alembic, Pydantic v2, TanStack Query v5. All existing; **zero new packages**.
**Storage**: PostgreSQL 16. Migration `047` (`down_revision="046"`) adds 2 columns plus a CHECK on `technical_capabilities`. All analysis is derived.
**Testing**:
- pure engine tests on hand-built snapshots, written first, covering every FR-005..FR-017 rule;
- snapshot builder tests on SQLite;
- contract tests via `create_app()`, including role overrides for the cost and risk redaction;
- a guard test that nothing derived is stored;
- export test;
- Docker-gated `test_migration_047.py`;
- vitest component tests.

**Target Platform**: the existing web app and API.
**Project Type**: web service plus SPA (existing monorepo layout).
**Performance Goals**:
- a fixed 6–8 queries per request, whatever the catalog size (research R2);
- under 2 s at 500 + 500 capabilities and 2,000 links (SC-005);
- heat map metric switches are client-side.

**Constraints**:
- derived results are never stored (guard test);
- gated data is never loaded without the permission;
- reads inner-join the far ends;
- the old app ↔ business/technical link tables are not read by the analysis (937 D5);
- `as_of` is injected for determinism.

**Scale/Scope**: about 2 new backend modules (engine ~350 lines, snapshot builder ~150), about 150 lines of routes, model and store changes for the lifecycle, 1 migration, export and seed changes. About 4 new and 5 touched frontend components. Roughly 70 backend and 25 frontend tests.

## Constitution Check

| Gate | Status | Notes |
|---|---|---|
| ART-I / QG-01 | ✔ | spec.md, bead ADP-6et.2 |
| ART-II Single source of truth | ✔ | Only the lifecycle is stored; every roll-up, band and finding is derived (guard test, R9) |
| ART-IV TDD / QG-04 | ✔ | Engine tests before the snapshot builder, router and UI; ≥ 85% on new modules |
| ART-V Security | ✔ | Threat model in the spec; cost and risk are never queried without the permission (R3); contract tests assert absence for each role |
| ART-VII AI grounding | n/a | No AI step |
| ART-IX Auditability | ✔ | Actor-attributed lifecycle change log line with old and new values (R8) |
| ART-XI Traceability | ✔ | Impact and technology dependency views; every list item navigates |
| ART-XIII Typed contracts | ✔ | `Literal` lifecycle, risk and lifecycle bands; `extra="forbid"` responses |
| ART-XV Schema evolution | ✔ | Reversible additive 047, with a Docker-gated up/down test |

No violations. Post-design re-check: no change. The design adds no table, no permission and no package.

## Project Structure

### Documentation

```text
specs/938-capability-model-analysis/
  spec.md plan.md research.md data-model.md quickstart.md contracts/rest-api.md checklists/requirements.md
  tasks.md   (next: /speckit.tasks)
```

### Source Code

```text
src/adp/application/
  models.py                  + TechCapLifecycle; lifecycle fields on TechnicalCapability/Create/Update
  store.py                   _tech_caps + 2 columns (Python default); create/update/get carry them
  router.py                  update_tech_cap logs lifecycle changes (old -> new)
  cap_analysis.py            NEW pure engine: CapabilitySnapshot, risk_band, effective_band,
                             business_rollup, impact, technology_dependencies, findings
  cap_analysis_store.py      NEW build_snapshot(session, risk_visible, cost_visible)
  cap_analysis_models.py     NEW response models (CapabilityRollupResponse, ImpactResult, ...)
  app_capabilities_router.py + 4 GET /analysis/... routes (before /{ac_id}), inline is_permitted
src/adp/export/application_arch.py   lifecycle fields in _serialize_technical_capability
src/adp/store/migrations/versions/047_tech_cap_lifecycle.py
scripts/seed_retail.py      offline sync Retiring 2027-06-30; Online Promotion Evaluation (Commerce Cloud)
                            -> Apply Promotions; POS risk record (posture weak)

tests/unit/application/test_cap_analysis_engine.py      NEW (pure)
tests/unit/application/test_cap_analysis_snapshot.py    NEW (SQLite)
tests/unit/application/test_cap_analysis_not_stored.py  NEW guard
tests/unit/application/test_tech_cap_lifecycle.py       NEW (store/model)
tests/contract/test_cap_analysis_api.py                 NEW (incl. role redaction)
tests/unit/export/...                                   extended
tests/integration/test_migration_047.py                 NEW (Docker-gated)

web/src/api/application.ts         TechnicalCapability lifecycle fields
web/src/api/capAnalysis.ts         NEW useCapabilityRollup / useTechCapImpact / useBusinessTechnology / useCapabilityFindings
web/src/business/CapabilityHeatMap.tsx   + health/risk/cost/exposure metrics, cell detail
web/src/business/CapabilityNode.tsx      + "Technology dependencies" expander on L3
web/src/application/TechCapForm.tsx      + lifecycle select, end-of-life date
web/src/application/TechCapTree.tsx      + lifecycle chip, past-EOL flag, Impact expander
web/src/application/TechCapImpactPanel.tsx   NEW
web/src/application/AppCapabilitiesView.tsx  + Overlaps / Gaps / Shared tabs
web/src/application/CapFindingsViews.tsx     NEW
```

**Structure Decision**: the existing `adp.application` package and the 937 router (research R7). Engine and snapshot are split as in 936 (research R1).

## Delivery order (for /speckit.tasks)

1. Lifecycle: models, store, migration 047, PATCH logging, export (US2). This unblocks the exposure work.
2. Engine: pure functions plus exhaustive tests, then the snapshot builder (US1, US3–US5 logic).
3. Routes plus contract tests, including redaction for each role.
4. UI, in story order: US1 heat map → US2 form → US3 Impact panel → US4 exposure and dependencies → US5 findings.
5. Seed, guard test, quickstart walkthrough with Playwright, GitNexus refresh.

## Complexity Tracking

None. No constitution violations to justify.
