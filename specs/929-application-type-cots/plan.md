# Implementation Plan: Application Type (COTS/Custom/SaaS/Legacy) Grouping Dimension

**Branch**: `929-application-type-cots` | **Date**: 2026-08-26 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/929-application-type-cots/spec.md`

## Summary

Add one new nullable, bounded-enum field, `application_type` (`custom`/`cots`/`saas`/`legacy`), to
the existing `Application` entity — following the exact precedent `hosting_model` (ADP-SPEC-038,
migration 016) already set on the same model: a nullable `TEXT` column with a `CHECK` constraint
and a filter index, a Pydantic `Literal` on `Application`/`ApplicationCreate`/`ApplicationUpdate`,
a create/update/filter code path in `adp.application.store`/`router`, an editable dropdown in
`ApplicationForm.tsx`, a conditional read line in `ApplicationDetail.tsx`, and — closing the loop —
a sixth Group By/Then By/Filter by dimension on the Application Portfolio screen
(`web/src/portfolio/groupApplications.ts`), plus inclusion in `adp.export.application_arch`'s
existing per-application export so file-based AI/tool consumers see it too. No new table, no new
endpoint, no new screen.

## Technical Context

**Language/Version**: Python 3.12 (backend); TypeScript 5.x + React 18 (frontend) — both existing
stacks, no new language/version surface.
**Primary Dependencies**: FastAPI ≥ 0.111, SQLAlchemy 2 async (Core), asyncpg, Alembic, Pydantic
v2, React 18, TanStack Query v5 — all existing project dependencies; zero new packages either side.
**Storage**: PostgreSQL 16 — one additive migration (`039`, `down_revision="038"`): one nullable
`TEXT` column + `CHECK` constraint + one filter index on the existing `applications` table,
mirroring migration `016`'s own `hosting_model` addition line-for-line.
**Testing**: pytest (unit tests for the new model field's validation + store create/update/filter
behavior; contract tests for the create/update/list API paths, mirroring
`tests/contract/test_apm_techfit_api.py`'s own `hosting_model` test shapes); Vitest (unit tests for
`groupByApplicationType`/`groupApplications` dispatch in `groupApplications.test.ts`, and
`ApplicationForm.tsx`'s new field).
**Target Platform**: Linux server (existing `adp-api` process) + browser (existing `web/` SPA) — no
new deployable either side.
**Project Type**: Web application (existing FastAPI backend + Vite/React frontend) — this feature
touches both, unlike 928 (backend-only).
**Performance Goals**: N/A — a single indexed equality-filterable column on an existing table at
existing (low-thousands) row counts; no new query pattern, no aggregation.
**Constraints**: Strictly additive — every existing `Application` record's `application_type` is
`NULL` post-migration (no backfill), and every existing caller that doesn't reference the new field
continues to behave identically (confirmed by the full existing test suite passing unmodified).
**Scale/Scope**: One new field on one existing entity; touches 2 backend modules
(`adp.application.models`, `adp.application.store`) + 1 backend router param + 1 migration + 1
export module (`adp.export.application_arch`) + 3 frontend files
(`web/src/api/application.ts`, `web/src/application/ApplicationForm.tsx` +
`ApplicationDetail.tsx`, `web/src/portfolio/groupApplications.ts`) — no new files anywhere except
the migration itself.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Applies? | How this feature satisfies it |
|---|---|---|
| ART-I (SDD Mandatory) | Yes | spec.md → this plan → tasks.md → implementation, in order — the bead itself was not yet spec'd. |
| ART-II (Model is Source of Truth) | Yes | `application_type` lives on the canonical `applications` table in Postgres, same as every other Application field; the frontend/export are read projections of it, never a second source. |
| ART-III (Machine-Readable) | Yes | FR-009 adds the field to `adp.export.application_arch`'s existing per-application export (ADP-SPEC-045) so file-based AI/tool consumers see it, not just interactive API/UI callers. |
| ART-IV (TDD) | Yes | tasks.md sequences failing unit/contract/frontend tests before each implementation task, mirroring `hosting_model`'s own original test shapes (`test_invalid_hosting_model_rejected`, `test_filter_by_hosting_model`) applied to the new field. |
| ART-V (Security by Design) | Yes | Threat model in spec.md confirms `application_type` is the same low-sensitivity tier as `hosting_model`/`pace_layer` (no `READ_APPLICATION_*` gate, matching those two fields exactly) — no new permission surface. |
| ART-VI (Observability) | No new obligation | A plain column write through an already-instrumented route; no new logging/metrics needed. |
| ART-VII (Grounded AI Only) | No | No AI-generated content involved. |
| ART-VIII (Human-in-the-Loop for Consequence) | No | A architect-entered classification field, not a consequential automated action. |
| ART-IX (Provenance/Auditability) | No new obligation | Application writes already flow through the existing (unaudited-at-this-granularity) CRUD path — unchanged by this feature, same as every other scalar field added to this entity historically. |
| ART-X–XII (Validation gating / Traceability / Visual language) | No | Not involved. |
| ART-XIII (Typed Contracts) | Yes | `application_type` is a typed Pydantic `Literal` end-to-end (backend model → OpenAPI → generated TS types), identical contract discipline to every sibling field. |
| ART-XIV/XV (Reproducible builds / Schema evolution) | Yes | One forward + reverse Alembic migration (039), reversible cleanly (drops the column/constraint/index), matching `016`'s own reversibility. |
| ART-XVI (Documentation as Code) | Yes (SHOULD) | This plan + research.md + data-model.md are the documentation; no separate doc needed beyond that (a UI-facing field, not a new concept requiring external docs). |

**Initial gate result**: PASS. No article is violated, no Complexity Tracking entry needed — this
is a strictly additive, single-field extension following an exact existing precedent on the same
entity.

## Project Structure

### Documentation (this feature)

```text
specs/929-application-type-cots/
├── plan.md              # This file
├── research.md
├── data-model.md
├── quickstart.md
└── tasks.md
```

### Source Code (repository root)

```text
src/adp/
├── application/
│   ├── models.py                    # MODIFIED: + ApplicationType literal, + field on
│   │                                 #   Application/ApplicationCreate/ApplicationUpdate
│   ├── store.py                     # MODIFIED: + column on _applications table, +
│   │                                 #   _row_to_application/create_application/
│   │                                 #   update_application/list_applications filter
│   └── router.py                    # MODIFIED: + application_type query param on
│                                     #   GET /api/v1/applications
├── export/
│   └── application_arch.py          # MODIFIED: + application_type in
│                                     #   _serialize_application()
└── store/migrations/versions/
    └── 039_application_type.py      # NEW: nullable TEXT column + CHECK + index,
                                      #   mirroring migration 016's hosting_model shape

web/src/
├── api/
│   └── application.ts               # MODIFIED: + ApplicationType type, + field on
│                                     #   Application/ApplicationCreate interfaces
├── application/
│   ├── ApplicationForm.tsx          # MODIFIED: + Application Type dropdown
│   └── ApplicationDetail.tsx        # MODIFIED: + conditional read line
└── portfolio/
    └── groupApplications.ts         # MODIFIED: + "application_type" Dimension,
                                      #   + groupByApplicationType, wired into
                                      #   ALL_DIMENSIONS/DIMENSION_LABELS/groupApplications

tests/
├── unit/application/                # MODIFIED: model validation tests
├── contract/test_apm_techfit_api.py # MODIFIED: + application_type create/update/filter/
                                      #   invalid-value tests (mirrors hosting_model's own)
└── unit/export/
    └── test_application_arch_serialize.py  # MODIFIED: + application_type in expected dict

web/src/portfolio/groupApplications.test.ts  # MODIFIED: + groupByApplicationType tests
                                              #   (no ApplicationForm.tsx test file exists
                                              #   today -- confirmed by direct ls -- so no
                                              #   frontend form test needs updating)
```

**Structure Decision**: Existing single-project layout (`src/adp/` backend, `web/` frontend,
`tests/` for backend, co-located `*.test.ts(x)` for frontend) — no new module, no new directory.
Every change is additive to an already-existing file except the one new migration.

## Complexity Tracking

*No violations — table omitted.*
