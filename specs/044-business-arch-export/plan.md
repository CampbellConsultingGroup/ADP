# Implementation Plan: Continuous Business Architecture Export to Versioned Files

**Branch**: `044-business-arch-export` | **Date**: 2026-08-05 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/044-business-arch-export/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Close the "business architecture only lives in Postgres" gap (ADP-81p) for the first domain: an in-process background task periodically reconciles every business capability, value stream, value stream stage (with its linked capability IDs), and business domain against a versioned JSON file tree under a configured export root — one file per entity instance, written only when its content actually changed, with deleted entities' files removed. No new user-facing screen, no new API endpoint, no new database table, and no change to any existing write path — this is a purely additive, read-only background projection, opt-in via a new environment variable.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: FastAPI (lifespan hook to start/stop the background task), SQLAlchemy 2 async (Core, reusing `adp.business.store`'s existing list/get functions), `asyncio` (background task loop) — all existing project dependencies; zero new packages required
**Storage**: PostgreSQL 16 (read-only for this feature — no new tables, no migration); filesystem (the exported JSON file tree) is the only new persisted artifact, and it is itself derived/regenerable, not a system of record
**Testing**: pytest (unit tests for the reconciliation logic against a SQLite-backed business store, mirroring `tests/unit/business/` conventions; an integration test against a real Postgres container verifying one full reconciliation cycle end-to-end)
**Target Platform**: Linux server (existing `adp-api` process — the background task runs in the same process, no new deployable)
**Project Type**: Backend-only addition to the existing web application (no frontend change — this feature has no UI)
**Performance Goals**: A full reconciliation cycle completes well within its own interval at the expected data volume (hundreds of business architecture rows) — no specific throughput target beyond "doesn't fall behind its own schedule"
**Constraints**: Zero added latency on any existing business-architecture write path (research.md Decision 1 — full periodic reconciliation, not write-path hooks); the feature MUST be inert (no background task started, no filesystem writes) unless explicitly configured via `ADP_BUSINESS_ARCH_EXPORT_ROOT`
**Scale/Scope**: 4 entity types (capability, value stream, value stream stage, domain) plus one cross-entity relationship (stage → linked capabilities); no new database schema; the entire feature lives in one new module plus a small lifespan-wiring change

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Applies? | How this feature satisfies it |
|---|---|---|
| ART-I (SDD Mandatory) | Yes | spec.md → this plan → tasks.md (next command) → implementation, in order; the FR-011 scope gap found during planning was corrected in spec.md itself (not silently implemented beyond what the spec said), per Article I's "a change to behavior MUST be reflected as a change to its specification." |
| ART-II (Model is Source of Truth) | Yes | The exported files are an explicitly generated, read-only projection of Postgres — exactly the same "generated artifact, never hand-edited, source stays authoritative" relationship `architecture-description.schema.json` already has to `models.py`. |
| ART-III (Machine-Readable) | Yes | This is the entire point of the feature — closing the gap where business architecture data is queryable only via direct DB access, not as versioned, diffable files. |
| ART-IV (TDD) | Yes | tasks.md will sequence a failing unit test (reconciliation logic: write-if-changed, skip-if-unchanged, delete-if-gone) before the reconciliation function itself. |
| ART-V (Security by Design) | Yes | Threat model in spec.md covers the new automatic/continuous exposure shape (vs. ADP-SPEC-011's manual, per-item export) and explicitly draws the scope boundary against sensitive application data categories for future increments. |
| ART-VI (Observability) | Yes | research.md Decision 5 — every reconciliation cycle's failure is a structured log event (FR-006); no new metric/span is warranted (this isn't an AI orchestration step, and the existing `/metrics` surface doesn't need a new gauge for a v1 background job whose only consumer today is logs). |
| ART-VII (Grounded AI Only) | No | No AI-generated content is involved. |
| ART-VIII (Human-in-the-Loop for Consequence) | No (see spec.md) | This feature introduces no new consequential action a human takes — it is a passive projection of already-committed data, not a new write path requiring its own confirmation gate. |
| ART-IX (Provenance/Auditability) | No new obligation | This feature does not mutate the canonical model (ART-II) and so writes no new audit entry of its own; the underlying business-architecture writes it reflects already go through whatever audit path they already have (largely none today, unchanged by this feature). |
| ART-X, ART-XI, ART-XII (Validation gating / Traceability / Visual language) | No | No LLM-as-a-Judge verdict, no requirement/recommendation/verdict thread, no diagram rendering involved. |
| ART-XIII (Typed Contracts) | Yes | The exported JSON file shapes are explicitly documented as a contract (contracts/exported-file-formats.md) even though there is no HTTP endpoint — they are this feature's actual external interface, consumed by tools/AI reading the filesystem directly. |
| ART-XIV / ART-XV (Reproducible builds / Schema evolution) | Yes | No schema migration; the exported file *format* is new and versioned informally via this spec/plan, not via `adp-generate` (out of that generator's scope, same as other FastAPI-boundary-only features in this codebase). |
| ART-XVI (Documentation as Code) | Yes (SHOULD) | This plan + research.md + data-model.md + contracts/ are the documentation. |

**Initial gate result**: PASS. No article is violated. No Complexity Tracking entries are needed — every design decision in research.md picks the *simpler* of the alternatives considered (periodic reconciliation over event hooks, filesystem-as-state over a new table, in-process task over a new service), not a more complex one requiring justification.

**Post-Phase-1 re-check**: PASS (unchanged) — data-model.md and contracts/ below implement exactly the additive, read-only, zero-new-schema design described above; no new gate is implicated by the detailed design.

## Project Structure

### Documentation (this feature)

```text
specs/044-business-arch-export/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md         # Phase 1 output (/speckit.plan command)
├── quickstart.md         # Phase 1 output (/speckit.plan command)
├── contracts/            # Phase 1 output (/speckit.plan command)
│   └── exported-file-formats.md
├── checklists/
│   └── requirements.md
└── tasks.md               # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/adp/
├── export/
│   ├── bundle.py                      # existing (ADP-SPEC-011, untouched)
│   └── business_arch.py               # NEW: reconciliation logic + background task loop
├── business/
│   └── store.py                       # existing (ADP-SPEC-033/034/035) — read-only functions reused, UNTOUCHED
└── api/
    └── app.py                         # MODIFIED: lifespan hook starts/stops the background task when ADP_BUSINESS_ARCH_EXPORT_ROOT is set

tests/
├── unit/
│   └── export/
│       └── test_business_arch_export.py   # NEW: reconciliation logic — write-if-changed, skip-if-unchanged,
│                                            #      delete-if-gone, stage linked-capability inclusion, path-safety
└── integration/
    └── test_business_arch_export_cycle.py  # NEW: one full reconciliation cycle against a real Postgres container
```

**Structure Decision**: A single new module (`adp.export.business_arch`), sibling to the existing `adp.export.bundle` (ADP-SPEC-011), following this codebase's established per-domain module convention. No new package, no new router, no new frontend code (this feature has no UI), no new database migration. The only existing file touched is `adp.api.app`'s lifespan hook, to start/stop the background task — every other file in the "MODIFIED" sense is untouched by this feature; `adp.business.store`'s existing read functions are called, not changed.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

*(No entries — see Constitution Check above.)*
