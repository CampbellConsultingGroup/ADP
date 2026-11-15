# Implementation Plan: Application Capabilities

**Branch**: `937-application-capabilities` | **Date**: 2026-11-15 | **Spec**: [spec.md](spec.md)
**Input**: `/specs/937-application-capabilities/spec.md` (bead ADP-6et.1, epic ADP-6et).

## Summary

This feature adds an **application capability** catalog (a shared tree, L1–L3) between business and technical capabilities, plus three many-to-many link types, each with level rules enforced in the store:
- business L3 ↔ application L3;
- application L3 → technical L2/L3;
- application L3 realized by applications.

A **derived** "missing technical capability" warning (never stored) shows as a badge and in a gaps list.

Links are edited on the application capability. Business capability, technical capability and application screens show them read-only.

It also covers search, export and the POS seed. Migration `046`. No new permission and no new package.

## Technical Context

**Language/Version**: Python 3.12 (3.11+) and TypeScript 5.x + React 18 (existing).
**Primary Dependencies**: the existing stack (FastAPI, SQLAlchemy 2 async Core, Alembic, Pydantic v2, TanStack Query v5). **Zero new packages.**
**Storage**: PostgreSQL 16, migration `046` (4 tables, 1 expression index).
**Testing**:
- SQLite store suite (written first);
- contract tests through `create_app()`;
- authz completeness;
- search hook and backfill tests;
- export tests;
- Docker-gated migration test;
- vitest component tests.

**Performance Goals**: the list, with counts and warnings, takes a fixed 4 queries regardless of catalog size.
**Constraints**:
- warnings are derived (guard test);
- reads inner-join the far ends (no dangling rows on SQLite);
- literal `by-*` routes come before `/{ac_id}`;
- the old link tables are untouched (FR-013).

**Scale/Scope**: about 1 backend module (~600 lines) plus a router (~300), 1 migration, model additions, search/export/seed changes, about 5 new and 4 touched frontend components, and roughly 70 backend and 20 frontend tests.

## Constitution Check

| Gate | Status | Notes |
|---|---|---|
| ART-I / QG-01 | ✔ | spec.md, bead ADP-6et.1 |
| ART-II Single source of truth | ✔ | Each link stored once; the warning is derived (guard test) |
| ART-IV TDD / QG-04 | ✔ | Store tests before the router and UI; ≥ 85% on the new module |
| ART-V Security | ✔ | `WRITE_APPLICATION` prefix rule; no sensitive fields; ids validated |
| ART-IX Auditability | ✔ | Actor-attributed log lines on every write |
| ART-XI Traceability | ✔ | Reverse lookups from every layer |
| ART-XIII Typed contracts | ✔ | `Literal` levels and warnings, `extra="forbid"` |
| ART-XV Schema evolution | ✔ | Reversible 046, Docker-gated up/down/cascade test |

No violations.

## Project Structure

```text
specs/937-application-capabilities/  plan.md research.md data-model.md quickstart.md contracts/rest-api.md checklists/ tasks.md

src/adp/application/
  models.py                 + ApplicationCapability* models, errors
  store.py                  _biz_caps mirror + level/parent_id; delete_application / delete_technical_capability remove new link rows
  app_capabilities.py       NEW: tables (on store._metadata), CRUD, links, level rules, counts/warnings, reverse lookups, search hooks
  app_capabilities_router.py NEW: /api/v1/application-capabilities
src/adp/api/app.py          include the router
src/adp/authz/enforcement.py + prefix rule
src/adp/search/index.py, backfill.py   ENTITY_APPLICATION_CAPABILITY + backfill
src/adp/export/application_arch.py     application-capabilities/<id>.json
src/adp/store/migrations/versions/046_application_capabilities.py
scripts/seed_retail.py      POS example phase

tests/unit/application/test_app_capabilities_store.py   NEW
tests/contract/test_app_capabilities_api.py             NEW
tests/unit/search/..., tests/unit/export/...            extended
tests/authz/test_enforcement.py                         extended
tests/integration/test_migration_046.py                 NEW (Docker-gated)

web/src/api/appCapabilities.ts                          NEW hooks
web/src/application/AppCapTree.tsx, AppCapForm.tsx, AppCapDetail.tsx, AppCapGaps.tsx   NEW
web/src/application/ApplicationPage.tsx                 + Capabilities tab, focus state
web/src/application/ApplicationDetail.tsx               + Realizes section
web/src/application/TechCapTree.tsx                     + "Used by" on nodes
web/src/business/CapabilityNode.tsx                     + Application capabilities on L3 rows
web/src/application/appCapabilities.test.tsx            NEW
```

**Structure Decision**: a sibling module in `adp.application` (research D1), with the router registered beside `tech_caps_router`.

## Phases

- **Phase 0 (research.md)**: D1–D12, no open unknowns.
- **Phase 1 (data-model.md, contracts/rest-api.md, quickstart.md)**: done.
- **Phase 2 (tasks.md)**: `/speckit.tasks`.

## Complexity Tracking

None.
