# Implementation Plan: Mapping Rationale

**Branch**: `943-mapping-rationale` | **Date**: 2026-11-16 | **Spec**: [spec.md](spec.md)
**Input**: `/specs/943-mapping-rationale/spec.md` (bead ADP-55k.4, spec 4 of 4 in epic ADP-55k). `/speckit-clarify` confirmed four defaults on 2026-11-16.

## Summary

937's realization link (application capability L3 ↔ application) gets two nullable columns in migration `051`: `rationale` (target / tactical / transitional / redundant) and `geography_id` (a region or country; none means everywhere). Existing rows read as unclassified.

938's pure findings engine then:
- classifies each overlap as **needs attention** or **explained**, with reasons: unclassified, redundant, no target, or competing targets (scope by geography containment);
- returns a **redundant** list grouped by business L3;
- adds a TIME-consistency hint.

Everything is derived on read from one snapshot.

UI:
- rationale and geography selects on each realization row, saving on choose;
- the Overlaps tab split into two sections;
- a fourth Redundant tab;
- the Governance overlaps tile counts only overlaps that need attention.

Also: export, seed phase G. No new permission.

## Technical Context

**Language/Version**: Python 3.12 (3.11+) and TypeScript 5.x + React 18 (existing).
**Primary Dependencies**: FastAPI, SQLAlchemy 2 async Core, Alembic, Pydantic v2, TanStack Query v5. **Zero new packages.**
**Storage**: PostgreSQL 16. Migration `051` (`down_revision="050"`) adds 2 columns, 1 CHECK, 1 FK (SET NULL) and 1 index to `app_capability_realizations`. No data change.
**Testing** (test-first):
- pure engine tests: the reason matrix, scope containment, the hint, redundant grouping, retired exclusion and dangling geography;
- SQLite store tests: add with attributes, PATCH semantics (omit vs null), validation, existing rows unclassified;
- contract tests: reviewer 403, 404/422 bodies, the findings shape;
- a guard that no overlap status or reason is stored;
- export test;
- Docker-gated `test_migration_051.py`;
- vitest: realization editor, findings views, Governance tile.

Run `ruff check src/ tests/` before pushing.

**Performance Goals**: no new query on the findings path unless some realization has a geography, and then one geography query. Overlap classification is linear in the mappings.
**Constraints**:
- overlap status is never stored (SC-002/3, guard);
- existing fields of findings and realization reads are unchanged, with additions only;
- the fit-score link is untouched (FR-017).

**Scale/Scope**:
- backend: models +~60 lines, `app_capabilities.py` +~60, router +~40, `cap_analysis.py` +~120, `cap_analysis_models.py` +~50, `cap_analysis_store.py` +~30, `organization/store.py` +~20; plus export and seed edits;
- frontend: a new `RealizationList.tsx`; edits to `AppCapDetail.tsx`, `CapFindingsViews.tsx`, `AppCapabilitiesView.tsx`, `ArchitectureHealthTab.tsx`/`architectureHealth.ts` and `api/application.ts`;
- about 50 backend and 20 frontend tests.

## Constitution Check

| Gate | Status | Notes |
|---|---|---|
| ART-I / QG-01 | ✔ | spec.md, bead ADP-55k.4, clarify session 2026-11-16 |
| ART-II | ✔ | The rationale lives once, on the realization; overlap status and the redundant list are derived on read |
| ART-IV | ✔ | Engine tests first, then store, contract and component tests |
| ART-V | ✔ | `WRITE_APPLICATION` prefix rule; no sensitive data; risk and cost gating in 938 is unchanged |
| ART-IX | ✔ | Create and update log lines with old → new values |
| ART-XIII | ✔ | `Literal` rationale, CHECK backstop, `extra="forbid"` bodies |
| ART-XV | ✔ | Reversible `051`, columns only, with a Docker-gated test |

No violations. Post-design re-check: unchanged.

## Project Structure

```text
specs/943-mapping-rationale/  spec.md plan.md research.md data-model.md quickstart.md contracts/rest-api.md checklists/ tasks.md

src/adp/store/migrations/versions/051_realization_rationale.py   NEW
src/adp/application/store.py                 _app_cap_realizations + rationale, geography_id (no ORM FK)
src/adp/application/app_capability_models.py  Rationale literal, GeoRef, AppRef +, RealizationCreate +, RealizationUpdate NEW
src/adp/application/app_capabilities.py       add_realization(+attrs), update_realization NEW, _apps_by_cap reads attrs + hint
src/adp/application/app_capabilities_router.py  POST extended, PATCH NEW, log lines
src/adp/application/cap_analysis.py           Realization, AppInfo +TIME/7R, snapshot fields, reasons, redundant, consistency_hint
src/adp/application/cap_analysis_models.py    Mapping, OverlapReason, OverlapEntry +, RedundantEntry/Group, CapabilityFindings +
src/adp/application/cap_analysis_store.py     realization attrs, AppInfo TIME/7R, conditional geography index
src/adp/organization/store.py                 geography_level(), geography_index() (public, read-only)
src/adp/export/application_arch.py            "realizations" block on application capability files
scripts/seed_retail.py                        phase G

tests/unit/application/test_cap_analysis_rationale.py   NEW (pure)
tests/unit/application/test_realization_rationale_store.py  NEW (SQLite)
tests/unit/application/test_cap_analysis_not_stored.py  extended (no status/reason columns)
tests/contract/test_realization_rationale_api.py        NEW
tests/unit/export/...application_arch...                extended
tests/integration/test_migration_051.py                 NEW (Docker-gated)

web/src/api/application.ts                    types + useUpdateRealization; findings types
web/src/application/realizationRationale.ts    NEW labels, colours, consistencyHint mirror
web/src/application/RealizationList.tsx (+test)  NEW
web/src/application/AppCapDetail.tsx           use RealizationList
web/src/application/CapFindingsViews.tsx (+test)  overlaps split + reasons; redundant mode
web/src/application/AppCapabilitiesView.tsx    Redundant tab
web/src/governance/architectureHealth.ts / ArchitectureHealthTab.tsx (+tests)  tile counts needs_attention
```

**Structure Decision**: extend 937/938 in place (`adp.application`). Read the geography through two small public functions on the organization store (application → organization, the 940 direction).

## Delivery order (for /speckit.tasks)
1. Migration 051 and the Docker test; table columns.
2. Pure engine, test-first: hint → reasons/scope → overlap status → redundant groups. Then the guard.
3. Snapshot additions and the organization helpers.
4. Store writes (add with attributes, PATCH), test-first on SQLite; realization reads with attributes.
5. Router, contract tests and log lines.
6. Export and seed.
7. Frontend: types and hooks → `realizationRationale.ts` → `RealizationList` → findings views and the Redundant tab → Governance tile.
8. Gates (`ruff check src/ tests/`, mypy, tsc, vitest), a live quickstart with Playwright, CLAUDE.md, GitNexus.

## Complexity Tracking

| Deviation | Why | Simpler alternative rejected |
|---|---|---|
| `geography_id` has a real FK only in the migration, not in SQLAlchemy metadata | `geographies` is on the organization metadata. A cross-metadata FK would force every application fixture to create organization tables (940's `owning_org_unit_id` precedent) | Declaring the FK in metadata: breaks dozens of existing fixtures |
| The geography index is queried only when some realization has a geography | Keeps 938's query count and its existing fixtures unchanged | Always querying: every 938 fixture would need the organization tables |
