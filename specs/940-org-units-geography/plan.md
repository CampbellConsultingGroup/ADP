# Implementation Plan: Org Units and Geography

**Branch**: `940-org-units-geography` | **Date**: 2026-11-15 | **Spec**: [spec.md](spec.md)
**Input**: `/specs/940-org-units-geography/spec.md` (bead ADP-55k.1, spec 1 of 4 in epic ADP-55k).

## Summary

This feature adds two governed reference trees under Business Architecture, in a new `adp.organization` package:
- **Org Units**: enterprise → division → function.
- **Geography**: global → region → country, seeded by migration `048` from a committed ISO 3166 / UN M49 data file.

They are linked many-to-many, and an org unit can have one primary geography.

Applications gain an optional `owning_org_unit_id`, set from the application form, and a **review queue** that maps each free-text `owning_business_unit` value to an org unit in bulk. The free text is never written.

UI:
- a new **Organization** tab (both trees and the Unmatched list);
- an org-unit picker on the application form;
- Portfolio's business-unit grouping uses the link.

No new permission (the `/api/v1/business/` prefix rule) and no new package.

## Technical Context

**Language/Version**: Python 3.12 (3.11+) and TypeScript 5.x + React 18 (existing).
**Primary Dependencies**: FastAPI, SQLAlchemy 2 async Core, Alembic, Pydantic v2, TanStack Query v5. **Zero new packages** (R4: the ISO/M49 data is a committed JSON file, not `pycountry`).
**Storage**: PostgreSQL 16. Migration `048`:
- 3 new tables;
- 1 new column plus FK on `applications`;
- 2 expression unique indexes and 1 partial unique index;
- seeded geography rows.

**Testing**:
- a data-file test;
- SQLite store tests (both trees, links, review queue, FR-013 clearing);
- contract tests via `create_app()` (incl. the reviewer 403 and the application `owning_org_unit_id` 422);
- export, search and backfill tests;
- Docker-gated `test_migration_048.py` (seed counts, CHECKs, cascades, SET NULL, down/up);
- vitest component tests, with CI's frontend job enforcing the coverage ratchet.

**Performance Goals**: list endpoints use a fixed number of queries (rows, counts, links); about 255 geography rows is trivial. The review queue is one GROUP BY.
**Constraints**:
- free text never written (SC-004, test-enforced);
- nothing created without an explicit user action;
- sibling uniqueness enforced in the DB as well as the store;
- `applications` FK only in the migration (R2).

**Scale/Scope**:
- backend: about 1 new package (store ~450 lines, router ~250, models ~150), small edits to `adp.application` models/store/router, export, search, seed and app.py;
- frontend: about 5 new components plus 3 touched;
- roughly 80 backend and 25 frontend tests.

## Constitution Check

| Gate | Status | Notes |
|---|---|---|
| ART-I / QG-01 | ✔ | spec.md, bead ADP-55k.1 |
| ART-II | ✔ | One governed model each; free text kept as the record; the link drives grouping |
| ART-IV | ✔ | Store/data tests before the code, contract tests before routes, component tests before UI |
| ART-V | ✔ | `WRITE_BUSINESS_ARCH` prefix rule; non-sensitive data; bulk resolve logged |
| ART-IX | ✔ | Actor-attributed log lines on every write and resolve |
| ART-XIII | ✔ | `Literal` levels/kinds, ISO code regex, `extra="forbid"` |
| ART-XV | ✔ | Reversible 048 (downgrade drops the seeded rows with their tables), Docker-gated test |

No violations. Post-design re-check: unchanged.

## Project Structure

```text
specs/940-org-units-geography/  spec.md plan.md research.md data-model.md quickstart.md contracts/rest-api.md checklists/ tasks.md

src/adp/organization/__init__.py
src/adp/organization/models.py          NEW
src/adp/organization/store.py           NEW tables (+ narrow applications mirror), hierarchy rules, links, review queue, search hooks
src/adp/organization/router.py          NEW /api/v1/business/{org-units,geographies}
src/adp/organization/data/geographies.json   NEW (UNSD M49 + ISO 3166, source/date header)
src/adp/store/migrations/versions/048_org_units_geography.py
src/adp/application/{models,store,router}.py   + owning_org_unit_id (router validates via organization store)
src/adp/api/app.py                      include router (before business router)
src/adp/search/{index,__init__,backfill}.py    + ENTITY_ORG_UNIT
src/adp/export/business_arch.py         + organization/org-units/*.json, organization/geographies.json
scripts/seed_retail.py                  + org tree, geography links, owning_business_unit values

tests/unit/organization/test_geography_data.py, test_org_store.py
tests/contract/test_organization_api.py
tests/unit/export/..., tests/unit/search/test_backfill.py   extended
tests/integration/test_migration_048.py  (Docker-gated)

web/src/api/organization.ts             NEW hooks
web/src/business/OrganizationTab.tsx, OrgUnitTree.tsx, GeographyTree.tsx, UnmatchedList.tsx   NEW
web/src/business/BusinessPage.tsx       + Organization tab
web/src/application/ApplicationForm.tsx + Owning org unit picker
web/src/portfolio/groupApplications.ts, PortfolioPage.tsx   org-unit-aware grouping (R6)
```

**Structure Decision**: a new sibling package (R1), mirroring the 937 layout. Route prefix under Business.

## Delivery order (for /speckit.tasks)
1. The data file plus its test, then migration 048 plus the Docker test.
2. The organization store (trees → links → review queue), test-first on SQLite.
3. Models, router and app wiring, plus contract tests; then the application field plus validation.
4. Search, export and seed.
5. Frontend: hooks → Organization tab (trees → links → Unmatched) → application picker → Portfolio grouping.
6. Gates, live quickstart with Playwright, CLAUDE.md, GitNexus.

## Complexity Tracking

| Deviation | Why | Simpler alternative rejected |
|---|---|---|
| Geography is not search-indexed (FR-015 narrowed) | About 250 static country names would crowd global search, and nothing in 940 needs it | Indexing it: noise in every search |
