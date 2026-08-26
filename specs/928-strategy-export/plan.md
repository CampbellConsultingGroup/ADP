# Implementation Plan: Continuous Strategy Domain Export to Versioned Files

**Branch**: `928-strategy-export` | **Date**: 2026-08-26 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/928-strategy-export/spec.md`

## Summary

Extend the ADP-SPEC-044/045 continuous-export pattern to the Strategy domain (ADP-81p.3, third
domain): an in-process background task periodically reconciles every strategic theme, objective
(with its computed status, full progress history, and every cross-domain link — capabilities,
value streams, designs, applications, regulatory controls, other objectives via dependencies, and
initiatives), and strategy initiative (with its objective links and live compliance-mapping
status) against a versioned JSON file tree under the same configured export root, sibling to the
existing `business-architecture/`/`applications/` subtrees. Reuses `adp.export.common` verbatim
(no refactor needed this time — that extraction already happened in ADP-SPEC-045). Per
Clarification Q2, also extends ADP-SPEC-044's own `_serialize_capability`/`_serialize_value_stream`
with a new `linked_designs` field, closing the one gap both prior increments explicitly deferred.
No new user-facing screen, no new API endpoint, no new database table, no change to any existing
write path.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: FastAPI (extends the existing lifespan hook — a third background task
alongside ADP-SPEC-044/045's), SQLAlchemy 2 async (Core, reusing `adp.strategy.store`/
`adp.strategy.initiatives`'s existing bulk-list functions plus direct `Table` queries for bulk
group-by reads no existing function provides), `asyncio` (shared background-loop scaffold,
reused unchanged from `adp.export.common`) — all existing project dependencies; zero new packages
required
**Storage**: PostgreSQL 16 (read-only for this feature — no new tables, no migration); filesystem
(the exported JSON file tree) is the only new persisted artifact, sibling to ADP-SPEC-044/045's own
**Testing**: pytest (unit tests for serialization + bulk-fetch grouping + reconciliation logic
against a SQLite-backed strategy store, mirroring `tests/unit/export/test_application_arch_*.py`
conventions; unit tests for the `business_arch.py` extension, updating its existing exact-shape
serialization tests to include the new field; an integration test against a real Postgres
container verifying one full reconciliation cycle end-to-end, including every relationship type)
**Target Platform**: Linux server (existing `adp-api` process — a third background task in the
same process, no new deployable)
**Project Type**: Backend-only addition to the existing web application (no frontend change —
this feature has no UI)
**Performance Goals**: A full reconciliation cycle completes well within its own interval at the
expected data volume (low hundreds of themes/objectives/initiatives, low thousands of relationship
rows) — no specific throughput target beyond "doesn't fall behind its own schedule," identical
framing to ADP-SPEC-044/045
**Constraints**: Zero added latency on any existing strategy write path (full periodic
reconciliation, not write-path hooks, same as both prior increments); the feature MUST be inert
unless `ADP_BUSINESS_ARCH_EXPORT_ROOT` is already configured (reused, not a third env var) — this
feature adds no new configuration surface of its own
**Scale/Scope**: 3 file-bearing entity types (theme, objective, initiative) plus roughly a dozen
relationship types embedded within them (theme→framework tags; objective→capability/value-stream/
design/application/control links, objective→objective dependencies in both directions,
objective→initiative reverse links, objective progress history; initiative→objective links,
initiative→compliance-mapping links across 5 target shapes with live status) plus one small,
explicitly-scoped extension to an already-shipped module (`business_arch.py`'s two serialization
functions, +1 field each); no new database schema; one new domain module

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Applies? | How this feature satisfies it |
|---|---|---|
| ART-I (SDD Mandatory) | Yes | spec.md (all three clarifications resolved and recorded) → this plan → tasks.md (next command) → implementation, in order. |
| ART-II (Model is Source of Truth) | Yes | Exported files are an explicitly generated, read-only projection of Postgres — identical relationship to ADP-SPEC-044/045. The objective's exported status is the platform's own single computed value (`compute_status()`, reused directly, not re-derived) — Clarification Q1 means this feature introduces no second definition of "objective status." |
| ART-III (Machine-Readable) | Yes | Closes the Strategy-domain gap the parent epic (ADP-81p) identified as its largest remaining uncovered domain, and the last major traceability gap (objective↔capability/value-stream/design/application/control/framework) the export tree was missing. |
| ART-IV (TDD) | Yes | tasks.md will sequence failing unit tests (serialization for each entity type + bulk-fetch grouping + orphan cleanup + the `business_arch.py` extension) before the implementation, mirroring ADP-SPEC-045's task sequencing exactly. |
| ART-V (Security by Design) | Yes | Threat model in spec.md confirms directly against the permission model that Strategy has no sensitive-category read gate — the simpler ADP-SPEC-044 precedent applies, no residual-risk trade-off to document. |
| ART-VI (Observability) | Yes | Reuses ADP-SPEC-044/045's structured failure-logging behavior via the shared `adp.export.common` module — no new logging design needed. |
| ART-VII (Grounded AI Only) | No | No AI-generated content is involved. |
| ART-VIII (Human-in-the-Loop for Consequence) | No (see spec.md) | This feature introduces no new consequential action a human takes — a passive projection of already-committed data. |
| ART-IX (Provenance/Auditability) | No new obligation | This feature does not mutate the canonical model; the underlying strategy writes it reflects already go through whatever audit path they already have (unchanged by this feature). |
| ART-X, ART-XI, ART-XII (Validation gating / Traceability / Visual language) | No | No LLM-as-a-Judge verdict, no requirement/recommendation/verdict thread, no diagram rendering involved. |
| ART-XIII (Typed Contracts) | Yes | The exported JSON file shapes are explicitly documented as a contract (`contracts/exported-file-formats.md`), the same pattern ADP-SPEC-044/045 established for a feature with no HTTP endpoint. |
| ART-XIV / ART-XV (Reproducible builds / Schema evolution) | Yes | No schema migration; the exported file *format* is versioned informally via this spec/plan, same as ADP-SPEC-044/045. |
| ART-XVI (Documentation as Code) | Yes (SHOULD) | This plan + research.md + data-model.md + contracts/ are the documentation. |

**Initial gate result**: PASS. No article is violated. **One Complexity Tracking entry is
warranted** (see below) for extending the already-shipped `adp.export.business_arch` module —
the one design choice in this plan that isn't purely additive to new files.

**Post-Phase-1 re-check**: PASS (unchanged) — data-model.md and contracts/ implement exactly the
design described above; the `business_arch.py` extension's own regression safety net (its
existing test suite, updated to expect the new field and required to keep passing otherwise
unchanged) is called out explicitly as a task-level requirement in the next command, not left
implicit.

## Project Structure

### Documentation (this feature)

```text
specs/928-strategy-export/
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
│   ├── common.py                      # existing (ADP-SPEC-045) — reused verbatim, untouched
│   ├── business_arch.py               # MODIFIED (ADP-SPEC-044, Clarification Q2): +2 bulk
│   │                                   #      queries (capability_design_links,
│   │                                   #      value_stream_design_links), +1 param each on
│   │                                   #      _serialize_capability/_serialize_value_stream
│   ├── application_arch.py            # existing (ADP-SPEC-045) — untouched
│   └── strategy.py                    # NEW: theme/objective/initiative serialization +
│                                       #      bulk-fetch + reconciliation, using common.py's
│                                       #      helpers. Named without an "_arch" suffix
│                                       #      (unlike its two siblings) since "Strategy" is
│                                       #      not itself an architecture domain.
├── strategy/
│   ├── store.py                       # existing (ADP-d8u.x/COMPLY-05) — read-only functions/
│   │                                   #      Table objects reused, UNTOUCHED
│   └── initiatives.py                 # existing (ADP-d8u.6/COMPLY-05) — read-only functions/
│                                       #      Table objects reused, UNTOUCHED
├── business/
│   └── store.py                       # existing (ADP-SPEC-034) — _cap_design_links/
│                                       #      _vs_design_links Table objects read directly by
│                                       #      business_arch.py's own bulk fetch, UNTOUCHED
└── api/
    └── app.py                         # MODIFIED: lifespan hook starts/stops a third
                                        #      background task when ADP_BUSINESS_ARCH_EXPORT_ROOT
                                        #      is set (same env var as ADP-SPEC-044/045 — no new
                                        #      configuration surface for this feature)

tests/
├── unit/
│   └── export/
│       ├── test_business_arch_serialize.py     # existing — MODIFIED: two tests updated to
│       │                                        #      expect the new linked_designs field
│       ├── test_business_arch_reconciliation.py # existing — MODIFIED if its own fixtures need
│       │                                        #      the new bulk queries mocked/seeded
│       ├── test_strategy_export_serialize.py    # NEW: pure serialization for theme/objective/
│       │                                        #      initiative, incl. computed status and
│       │                                        #      progress history embedding
│       ├── test_strategy_export_reconciliation.py # NEW: bulk-fetch grouping + reconciliation +
│       │                                          #      orphan cleanup
│       └── test_strategy_export_io.py            # NEW, if needed: any strategy-export-specific
│                                                  #      I/O behavior beyond what common.py's
│                                                  #      own tests already cover
└── integration/
    └── test_strategy_export_cycle.py    # NEW: one full reconciliation cycle against a real
                                          #      Postgres container, covering every relationship
                                          #      type in FR-013/014/015/016
```

**Structure Decision**: One new domain module (`adp.export.strategy`), sibling to
`adp.export.business_arch`/`adp.export.application_arch`, following the same per-domain module
convention and reusing `adp.export.common` verbatim. One existing module
(`adp.export.business_arch`) is extended, not replaced, per Clarification Q2 — the only
non-purely-additive change in this feature, called out in Complexity Tracking below. No new
package, no new router, no new frontend code, no new database migration.
`adp.strategy.store`/`adp.strategy.initiatives`/`adp.business.store`'s existing functions and
`Table` objects are called/read directly, never changed.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|---------------------------------------|
| Extending already-shipped `adp.export.business_arch` (ADP-SPEC-044) with a new `linked_designs` field on two of its serialization functions, rather than leaving it untouched | Per Clarification Q2: `capability_design_links`/`value_stream_design_links` (spec 034) link a Business Architecture entity to a Design — neither endpoint is Strategy domain data, so the correct home for this data is the entity that already owns the *other* file location, not a third, ownerless location this feature would otherwise have to invent | A new file location owned by neither domain (e.g. a bare `strategy/design-links.json` list): rejected because it splits a capability's/value-stream's own traceability data across two files a reader has to know to cross-reference, for a relationship that reads naturally as "this capability's own linked designs" — exactly the shape `_serialize_stage`'s existing `linked_capability_ids` parameter already establishes as this codebase's convention for embedding a link array onto the entity that owns it. |

