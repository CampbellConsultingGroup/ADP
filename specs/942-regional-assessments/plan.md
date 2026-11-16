# Implementation Plan: Regional Assessments

**Branch**: `942-regional-assessments` | **Date**: 2026-11-16 | **Spec**: [spec.md](spec.md)
**Input**: `/specs/942-regional-assessments/spec.md` (bead ADP-55k.3, spec 3 of 4 in epic ADP-55k). `/speckit-clarify` was skipped; the spec's Assumptions stand.

## Summary

This feature adds per-region maturity assessments on top of the single capability model. Migration `050` adds:
- `capability_regional_assessments`: a capability and a region or country, with a score from 1 to 5 and/or a variant note, unique per pair;
- a 1:1 `region_specific_capabilities` flag table plus its `region_specific_capability_geographies` scope.

Global maturity stays the untouched baseline. A pure engine over a 4-query snapshot derives applicability (containment in both directions through the geography tree), cell states (assessed with a delta from the baseline, not assessed, not applicable) and the capability × geography matrix. There is no roll-up and no inheritance.

UI:
- a "Regional" view on the Heat Map tab: a `<table>` matrix with a baseline column, regions by default, up to 12 columns, and click-to-edit cells;
- a "Regions" expander on each Capabilities row (assessments and scope).

Also: export block, seed phase C5. No new permission; extends `adp.organization`.

## Technical Context

**Language/Version**: Python 3.12 (3.11+) and TypeScript 5.x + React 18 (existing).
**Primary Dependencies**: FastAPI, SQLAlchemy 2 async Core, Alembic, Pydantic v2, TanStack Query v5. **Zero new packages.**
**Storage**: PostgreSQL 16. Migration `050` (`down_revision="049"`) adds 3 tables, 5 FKs (all CASCADE), 3 CHECKs, 1 unique and 1 plain index. `business_capabilities` is not altered.
**Testing**:
- pure engine tests (applicability containment both ways, cell states and deltas, no inheritance, column defaults and limits, scope-needs-update);
- SQLite store tests (upsert, Global refused, empty refused, scope replace and clear, delete cleanup, baseline untouched);
- contract tests (reviewer 403; 404/422 bodies; heat map query);
- a guard that the global maturity is never written;
- export and seed checks;
- Docker-gated `test_migration_050.py`;
- vitest component tests. Run `ruff check src/ tests/` before pushing (the PR #148 lesson).

**Performance Goals**: one snapshot plus in-memory work; 300 capabilities × 12 columns is 3,600 cells, well under 2 s (SC-002).
**Constraints**:
- global maturity is never written by these routes (SC-004, guard test);
- no capability is duplicated (SC-005);
- cell values only come from exact assessments (FR-012).

**Scale/Scope**:
- backend: `regional.py` ~220 lines, `regional_analysis.py` ~180, models +~90, router +~110, store +~50;
- export and seed edits;
- frontend: `RegionalHeatMap.tsx`, `RegionalAssessmentEditor.tsx`, `maturityScale.ts`, plus edits to `CapabilityHeatMap.tsx`, `BusinessPage.tsx`, `CapabilityNode.tsx`;
- about 60 backend and 25 frontend tests.

## Constitution Check

| Gate | Status | Notes |
|---|---|---|
| ART-I / QG-01 | ✔ | spec.md, bead ADP-55k.3 (clarify skipped by the user; assumptions recorded) |
| ART-II | ✔ | One capability, one baseline; regional data is an overlay; nothing duplicated |
| ART-IV | ✔ | Engine and store tests first, contract tests before routes, component tests before UI |
| ART-V | ✔ | `WRITE_BUSINESS_ARCH` prefix rule; notes rendered as text only |
| ART-IX | ✔ | Actor-attributed log lines on every set, remove and scope change |
| ART-XIII | ✔ | `Literal[1..5]`, `max_length` 1000, `extra="forbid"`, DB CHECKs |
| ART-XV | ✔ | Reversible 050 with a Docker-gated test |

No violations. Post-design re-check: unchanged.

## Project Structure

```text
specs/942-regional-assessments/  spec.md plan.md research.md data-model.md quickstart.md contracts/rest-api.md checklists/ tasks.md

src/adp/store/migrations/versions/050_regional_assessments.py   NEW
src/adp/organization/store.py              + 3 tables; mirror + maturity_level; delete_geography cleanup
src/adp/organization/regional.py           NEW writes (set/remove assessment, set scope), build_snapshot, reads
src/adp/organization/regional_analysis.py  NEW pure: applicability, cells, heat map, export block
src/adp/organization/models.py             + regional models
src/adp/organization/router.py             + /regional-assessments, /regional-heatmap, /capability-region-scope
src/adp/export/business_arch.py            + "regional" block on capability files
scripts/seed_retail.py                     + phase C5; WIPE_TABLES

tests/unit/organization/test_regional_analysis.py        NEW (pure)
tests/unit/organization/test_regional_store.py           NEW (SQLite)
tests/unit/organization/test_regional_not_stored.py      NEW (guard: no derived columns; baseline untouched)
tests/contract/test_regional_assessments_api.py          NEW
tests/unit/export/test_business_arch_serialize.py        extended
tests/integration/test_migration_050.py                  NEW (Docker-gated)

web/src/api/organization.ts                 + regional types and hooks
web/src/business/maturityScale.ts           NEW (shared 5-step swatches, extracted from CapabilityHeatMap)
web/src/business/RegionalHeatMap.tsx (+test)           NEW
web/src/business/RegionalAssessmentEditor.tsx (+test)  NEW (cell editor + row expander + scope editor)
web/src/business/CapabilityHeatMap.tsx      use maturityScale; view switch lives in BusinessPage
web/src/business/BusinessPage.tsx           Capabilities | Regional switch on the Heat Map tab; session column state
web/src/business/CapabilityNode.tsx         + "Regions" expander
```

**Structure Decision**: extend `adp.organization` (R1), with the 941 split: tables in store, logic module, pure engine.

## Delivery order (for /speckit.tasks)
1. Migration 050 and the Docker test; tables, mirror column and fixtures.
2. Pure engine, test-first (applicability → cells → heat map → export block), plus the guards.
3. Store writes and snapshot, test-first on SQLite.
4. Models, routes and contract tests.
5. Export and seed.
6. Frontend: hooks → shared scale → RegionalHeatMap → cell editor → row expander and scope.
7. Gates (`ruff check src/ tests/`), live quickstart with Playwright, CLAUDE.md, GitNexus.

## Complexity Tracking

| Deviation | Why | Simpler alternative rejected |
|---|---|---|
| Region-specific flag in its own 1:1 table, not a capability column | The flag must survive losing its last geography ("scope needs updating"), and a column would touch the CRLF business store, models, router and form | A `business_capabilities.region_specific` column: more files touched for the same behaviour |
| Shared `maturityScale.ts` extracted from `CapabilityHeatMap.tsx` | Both heat maps must use one colour scale | Duplicating the swatches: drifts |
