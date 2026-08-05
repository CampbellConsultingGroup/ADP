# Implementation Plan: Continuous Application Registry Export to Versioned Files

**Branch**: `045-application-export` | **Date**: 2026-08-05 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/045-application-export/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Extend ADP-SPEC-044's continuous-export pattern to the Application registry (ADP-81p.2, second domain): an in-process background task periodically reconciles every application, technical capability, transformation initiative, and application-to-application integration — plus, per Clarification Q1, an application's risk/cost/governance/quality records unredacted — against a versioned JSON file tree under the same configured export root, sibling to ADP-SPEC-044's `business-architecture/` subtree. Reuses the same file-per-instance, content-diff-before-write, orphan-cleanup, atomic-write, opt-in background-loop mechanism — the domain-agnostic parts of which are extracted from `adp.export.business_arch` into a new shared `adp.export.common` module (research.md Decision 5) so this feature doesn't duplicate it a second time. No new user-facing screen, no new API endpoint, no new database table, no change to any existing write path.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: FastAPI (extends the existing lifespan hook — one more background task alongside ADP-SPEC-044's), SQLAlchemy 2 async (Core, reusing `adp.application.store`'s existing bulk-list functions plus direct `Table` queries for the tables that have none — research.md Decision 4), `asyncio` (shared background-loop scaffold, research.md Decision 5) — all existing project dependencies; zero new packages required
**Storage**: PostgreSQL 16 (read-only for this feature — no new tables, no migration); filesystem (the exported JSON file tree) is the only new persisted artifact, sibling to ADP-SPEC-044's own
**Testing**: pytest (unit tests for serialization + reconciliation logic against a SQLite-backed application store, mirroring `tests/unit/export/test_business_arch_*.py` conventions; an integration test against a real Postgres container verifying one full reconciliation cycle end-to-end, including the sensitive-category and relationship-embedding behavior)
**Target Platform**: Linux server (existing `adp-api` process — a second background task in the same process, no new deployable)
**Project Type**: Backend-only addition to the existing web application (no frontend change — this feature has no UI)
**Performance Goals**: A full reconciliation cycle completes well within its own interval at the expected data volume (hundreds of applications, low thousands of relationship rows) — no specific throughput target beyond "doesn't fall behind its own schedule," identical framing to ADP-SPEC-044
**Constraints**: Zero added latency on any existing application-registry write path (full periodic reconciliation, not write-path hooks — research.md Decision 1); the feature MUST be inert unless `ADP_BUSINESS_ARCH_EXPORT_ROOT` is already configured (reused, not a second env var) — this feature adds no new configuration surface of its own
**Scale/Scope**: 4 file-bearing entity types (application, technical capability, transformation initiative, app-to-app integration) plus 5 relationship types embedded within them (business-capability links, technical-capability links, value-stream-stage links, domain integrations, initiative links) plus 3 sensitive 1:1 extension records embedded in the application file (risk, cost, governance) plus 1 non-sensitive one (quality); no new database schema; one new domain module plus a refactor extracting shared helpers from the existing one

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Applies? | How this feature satisfies it |
|---|---|---|
| ART-I (SDD Mandatory) | Yes | spec.md (with both clarifications resolved and recorded) → this plan → tasks.md (next command) → implementation, in order. |
| ART-II (Model is Source of Truth) | Yes | Exported files are an explicitly generated, read-only projection of Postgres — identical relationship to ADP-SPEC-044's, and the Application-Business-Capability link deliberately does not duplicate the capability's own data (only its name, for readability) rather than forking a second copy of ADP-SPEC-044's entity. |
| ART-III (Machine-Readable) | Yes | Closes the Application-registry gap the parent epic (ADP-81p) identified as its largest remaining uncovered domain. |
| ART-IV (TDD) | Yes | tasks.md will sequence failing unit tests (serialization for each entity type + sensitive-record embedding + relationship grouping + orphan cleanup) before the implementation, mirroring ADP-SPEC-044's task sequencing exactly. |
| ART-V (Security by Design) | Yes — the central article for this feature | Threat model in spec.md explicitly names the new exposure this feature accepts (sensitive `risk`/`cost`/`governance` data leaving the API's permission gate entirely) as a deliberate, clarified, documented trade-off (Q1) — not a default or an oversight. The shared `adp.export.common` module's path-safety helpers (from ADP-SPEC-044) are reused unchanged, so the file-path injection mitigation is inherited, not re-derived. |
| ART-VI (Observability) | Yes | Reuses ADP-SPEC-044's structured failure-logging behavior via the shared `adp.export.common` module — no new logging design needed. |
| ART-VII (Grounded AI Only) | No | No AI-generated content is involved. |
| ART-VIII (Human-in-the-Loop for Consequence) | No (see spec.md) | This feature introduces no new consequential action a human takes — a passive projection of already-committed data. |
| ART-IX (Provenance/Auditability) | No new obligation | This feature does not mutate the canonical model; the underlying application-registry writes it reflects already go through whatever audit path they already have (unchanged by this feature). |
| ART-X, ART-XI, ART-XII (Validation gating / Traceability / Visual language) | No | No LLM-as-a-Judge verdict, no requirement/recommendation/verdict thread, no diagram rendering involved. |
| ART-XIII (Typed Contracts) | Yes | The exported JSON file shapes are explicitly documented as a contract (`contracts/exported-file-formats.md`), the same pattern ADP-SPEC-044 established for a feature with no HTTP endpoint. |
| ART-XIV / ART-XV (Reproducible builds / Schema evolution) | Yes | No schema migration; the exported file *format* is versioned informally via this spec/plan, same as ADP-SPEC-044. |
| ART-XVI (Documentation as Code) | Yes (SHOULD) | This plan + research.md + data-model.md + contracts/ are the documentation. |

**Initial gate result**: PASS. No article is violated. **One Complexity Tracking entry is warranted** (see below) for the `adp.export.business_arch` refactor — it touches already-shipped, tested code, which is the one design choice in this plan that isn't purely additive.

**Post-Phase-1 re-check**: PASS (unchanged) — data-model.md and contracts/ implement exactly the design described above; the refactor's own regression safety net (ADP-SPEC-044's existing test suite, which must continue passing unchanged post-refactor) is called out explicitly as a task-level requirement in the next command, not left implicit.

## Project Structure

### Documentation (this feature)

```text
specs/045-application-export/
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
│   ├── common.py                      # NEW: shared helpers extracted from business_arch.py
│   │                                   #      (safe path/filename, atomic write, content-diff
│   │                                   #      write, orphan file/dir cleanup, background-loop
│   │                                   #      + start/stop lifecycle)
│   ├── business_arch.py               # MODIFIED (ADP-SPEC-044): refactored to import from
│   │                                   #      common.py instead of defining its own copies;
│   │                                   #      behavior-preserving, existing tests unchanged
│   └── application_arch.py            # NEW: application-registry serialization + bulk-fetch
│                                       #      + reconciliation, using common.py's helpers
├── application/
│   └── store.py                       # existing (ADP-SPEC-036/038) — read-only functions/
│                                       #      Table objects reused, UNTOUCHED
└── api/
    └── app.py                         # MODIFIED: lifespan hook starts/stops a second
                                        #      background task when ADP_BUSINESS_ARCH_EXPORT_ROOT
                                        #      is set (same env var as ADP-SPEC-044 — no new
                                        #      configuration surface for this feature)

tests/
├── unit/
│   └── export/
│       ├── test_business_arch_export.py       # existing (ADP-SPEC-044) — MUST still pass
│       │                                        #      unchanged after the common.py refactor
│       ├── test_export_common.py               # NEW: the extracted shared helpers, tested
│       │                                        #      once instead of duplicated per-domain
│       └── test_application_arch_export.py     # NEW: serialization (incl. sensitive-record
│                                                #      embedding, Decimal-as-string), bulk-fetch
│                                                #      grouping, reconciliation, orphan cleanup
└── integration/
    └── test_application_arch_export_cycle.py   # NEW: one full reconciliation cycle against a
                                                 #      real Postgres container
```

**Structure Decision**: One new domain module (`adp.export.application_arch`), sibling to `adp.export.business_arch`, following the same per-domain module convention. One new shared module (`adp.export.common`) factored out of the existing one (research.md Decision 5) — the only non-purely-additive change in this feature, called out in Complexity Tracking below. The only other existing file touched is `adp.api.app`'s lifespan hook, extended with a second background task. No new package, no new router, no new frontend code, no new database migration. `adp.application.store`'s existing functions and `Table` objects are called/read directly, never changed.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|---------------------------------------|
| Refactoring already-shipped `adp.export.business_arch` (ADP-SPEC-044) to extract shared helpers into `adp.export.common`, rather than leaving it untouched | Avoids duplicating ~150 lines of atomic-write/background-loop/orphan-cleanup logic a second time for this domain, with a third domain (per the parent epic ADP-81p) already anticipated — see research.md Decision 5 for full rationale | Duplicating the helpers into the new module unchanged: rejected because it guarantees the two copies silently drift over time (e.g. a future atomic-write bugfix applied to only one), and defers the same refactor to a future, more time-pressured moment with a third call site to update instead of two. The refactor's risk is bounded by ADP-SPEC-044's existing test suite, which is required (tasks.md) to keep passing unchanged as the regression check. |
