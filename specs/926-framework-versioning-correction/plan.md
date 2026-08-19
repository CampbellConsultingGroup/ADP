# Implementation Plan: Regulatory Framework Legal Dates & Identity (COMPLY-01a)

**Branch**: `926-framework-versioning-correction` | **Date**: 2026-08-19 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/926-framework-versioning-correction/spec.md`

## Summary

Corrects `RegulatoryFramework`'s single free-text `version` field, extending it (not replacing it) with a
regulation identity, four independent legal-event dates, a directly-set status, and two new supporting
one-to-many concepts — application phases (staged rollout dates, e.g. the EU AI Act) and amendments
(supplementing legal instruments, e.g. DORA's RTS stack). Sourced from an addendum document authored
outside this codebase; five of its concrete specifics (table/column shapes, a field claimed new that
already exists, a field name that was never real, a wrong screen name, and a migration that would have
failed or destroyed real data) were corrected against the actual, already-shipped, already-populated
implementation before this plan was written (spec.md Clarifications, research.md). Two genuine scope
questions were resolved directly with the user: existing frameworks' current `version` text is preserved
untouched, and this pass is data-model-and-API only — the Compliance screen's UI is unchanged. One new
migration (`035`, additive-only against real existing rows).

## Technical Context

**Language/Version**: Python 3.12 (backend only — no frontend file touched, per the resolved
data-model-and-API-only scope decision)
**Primary Dependencies**: FastAPI ≥ 0.111, SQLAlchemy 2 async (Core), asyncpg, Alembic, Pydantic v2 — all
existing stack; zero new packages
**Storage**: PostgreSQL 16 — one migration (`035`, down_revision `034`): seven new nullable columns (plus
one `NOT NULL DEFAULT`-backed `status`) additively added to the existing `regulatory_frameworks` table,
plus two new child tables (`framework_application_phase`, `framework_amendment`), each `String(36)`-keyed
with `ON DELETE CASCADE` back to their framework — matching every existing table's PK/cascade convention
in this codebase exactly (research.md D1, D6). Zero existing columns altered, renamed, or dropped
(research.md D2) — additive-only against the three real, currently-tracked frameworks.
**Testing**: pytest (unit — no DB, store/model validation incl. the duplicate-`regulation_number` 409 and
missing-phase/amendment 404 semantics; contract — schema/authz shape against a SQLite fixture extending
`adp.compliance`'s own existing fixture pattern; integration — testcontainers PostgreSQL for the
data-preservation guarantee against real pre-existing rows and cascade-delete behavior)
**Target Platform**: Linux server (API) — no browser surface touched this pass
**Project Type**: Web application backend only (existing `src/adp` — `web/` untouched, per scope decision)
**Performance Goals**: standard interactive-CRUD latency; `get_framework_detail()` gains two additional
single-table `SELECT ... WHERE framework_id = ...` queries (application phases, amendments) alongside its
existing controls query — no N+1, same shape as the existing control-tree assembly
**Constraints**: ART-XIII typed contracts (`extra="forbid"` on every boundary model); migration owns
FK/PK/CHECK/UNIQUE constraints, store-layer `Table()` objects DML-only (existing convention); the
migration must be provably additive against the three real seeded frameworks, not just theoretically
non-breaking (quickstart.md Scenario 1 is the direct check for this)
**Scale/Scope**: a handful of frameworks, each with a handful of application phases and a growing-but-small
number of amendments (DORA's RTS stack is the reference case — expected single digits to low tens, not
hundreds); no pagination added to the two new list endpoints, matching every other COMPLY-0x registry
endpoint's own scale assumption

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **ART-I (SDD mandatory)**: ✅ spec.md's two genuine open questions (existing-data preservation,
  UI-vs-backend-only scope) were resolved directly with the user before this plan began; every other
  apparent gap in the source document was resolved by direct code inspection and recorded as a
  Ground-Truth Correction in spec.md's Clarifications, not left ambiguous.
- **ART-II (Model is the single source of truth)**: ✅ this spec's entire purpose — an overloaded
  free-text field that silently mixed a regulation's identity, publication citation, and (for at least one
  real framework) two distinct dates into one string is replaced with typed, individually queryable facts.
- **ART-III / ART-XIII (Machine-readable / Typed contracts)**: ✅ new Pydantic v2 models
  (`FrameworkApplicationPhase(+Create)`, `FrameworkAmendment(+Create)`, `FrameworkStatus` literal),
  `extra="forbid"`; `RegulatoryFramework`/`Create`/`Update`/`Detail` extended, not replaced. OpenAPI
  contract generated, not hand-maintained.
- **ART-IV (TDD)**: ✅ contract + unit tests precede handlers; the additive-migration-against-real-data
  guarantee (spec.md FR-004/SC-001) gets a dedicated integration test using testcontainers PostgreSQL
  seeded with framework rows shaped like the three real ones, run and confirmed to pass before this is
  considered done — not just asserted in prose.
- **ART-V (Security by Design)**: ✅ threat model in spec.md; writes reuse the existing `WRITE_COMPLIANCE`
  permission (no `PERMISSIONS_VERSION` bump — already covers every route this spec adds under the existing
  `/api/v1/compliance/` prefix rule); no new URL-bearing field is introduced in this pass, so the
  `source_url` scheme-validation precedent (this session's own prior security-review finding) has nothing
  new to be reapplied to yet — noted as a residual-risk constraint for whichever future spec adds one.
- **ART-VI (Observability)**: N/A beyond baseline — no AI/LLM step in this feature; standard structured
  request logging already covers every route via the existing FastAPI middleware, matching COMPLY-01's own
  posture.
- **ART-VII (Grounded AI)**: N/A — no AI generation involved.
- **ART-VIII (Human-in-the-loop)**: N/A — every write is already a direct, attributable human action gated
  by `WRITE_COMPLIANCE`; `status` is explicitly a directly-set field in this pass (research.md D3), not an
  automated determination that would need a confirm step.
- **ART-IX (Provenance/Audit)**: `created_at` recorded on both new child tables; no `updated_at` (matches
  COMPLY-02's own mapping-table precedent — a phase/amendment's fields don't change in place, only
  add/remove); no `audit_entries` write, matching COMPLY-01's own confirmed precedent that direct human CRUD
  on registry data does not write to the append-only audit trail.
- **ART-XI (Traceability)**: N/A beyond COMPLY-01's own existing posture — this spec adds descriptive facts
  about a framework, not a new traceability link between domains.
- **ART-XV (Governed schema evolution)**: ✅ additive-only migration `035`, explicitly verified against the
  three real seeded frameworks (not just theoretically additive); no `PERMISSIONS_VERSION` bump.

**Result**: PASS — no violations; Complexity Tracking not required. Every design choice traces to an
existing, directly-confirmed precedent (`controls`' own `String(36)`/cascade/nested-tree shape,
`DuplicateControlCodeError`/`MappingNotFoundError`'s exception-translation shape) rather than the source
document's own drafted specifics, which were corrected against this codebase before being adopted.

## Project Structure

### Documentation (this feature)

```text
specs/926-framework-versioning-correction/
├── plan.md              # This file
├── research.md          # Phase 0 — D1–D6 decisions (PK/naming, additive migration, status
│                         #   not derived, nested detail response, error handling, cascade delete)
├── data-model.md         # Phase 1 — DDL (migration 035) + Pydantic models + store function inventory
├── contracts/
│   └── framework-legal-dates-api.md  # Phase 1 — REST contract (extended routes + 6 new sub-resource routes)
├── quickstart.md         # Phase 1 — integration scenarios covering every acceptance scenario + edge case
├── checklists/
│   └── requirements.md   # Spec quality checklist (passed with zero clarification markers)
└── tasks.md              # Phase 2 output (/speckit.tasks — not created here)
```

### Source Code Changes

```text
src/adp/compliance/                # EXISTING package (COMPLY-01/02/03/04/05) — extended, not replaced
├── models.py                      # + FrameworkStatus literal; + FrameworkApplicationPhase(+Create),
│                                   #   FrameworkAmendment(+Create); + FrameworkApplicationPhase/
│                                   #   AmendmentListResponse; RegulatoryFramework/Create/Update/Detail
│                                   #   extended (7 new optional fields + 2 nested lists on Detail);
│                                   #   + DuplicateRegulationNumberError, ApplicationPhaseNotFoundError,
│                                   #   AmendmentNotFoundError
├── store.py                       # _frameworks Table() gains 7 columns; + 2 new DML-only Table()s;
│                                   #   _row_to_framework() extended; create_/update_framework() extended
│                                   #   (unique-violation catch → DuplicateRegulationNumberError);
│                                   #   + add_/list_/delete_application_phase, add_/list_/delete_amendment;
│                                   #   get_framework_detail() extended (research.md D4)
└── router.py                      # POST/PATCH /frameworks[/{id}] extended (same paths, richer body);
                                    #   GET /frameworks/{id} response gains 2 nested lists;
                                    #   + POST/GET /frameworks/{id}/application-phases,
                                    #   DELETE .../application-phases/{phase_id};
                                    #   + POST/GET /frameworks/{id}/amendments,
                                    #   DELETE .../amendments/{amendment_id}

src/adp/store/migrations/versions/
└── 035_framework_legal_dates.py   # 7 additive columns + CHECK + UNIQUE on regulatory_frameworks,
                                    #   2 new tables, all constraints/indexes (data-model.md)

tests/
├── contract/
│   └── test_framework_legal_dates_api.py   # schema shape, authz (writes gated), 409/404 paths
├── unit/
│   └── compliance/
│       └── test_framework_legal_dates.py   # duplicate-regulation-number, missing-phase/amendment,
│                                            #   zero-phases/zero-amendments is not an error
└── integration/
    └── test_framework_legal_dates_api.py   # testcontainers PostgreSQL: migration applied against rows
                                             #   shaped like the 3 real frameworks confirms zero data loss
                                             #   (FR-004/SC-001), cascade delete removes phases/amendments
```

No `web/` file is touched — the resolved Clarification scopes this pass to data-model-and-API only.

**Structure Decision**: Extends the existing `adp.compliance` package exactly as COMPLY-01 through
COMPLY-04 already did — no new package, no new top-level directory. One new migration (`035`).

## Complexity Tracking

*No Constitution Check violations — this section is not applicable.*
