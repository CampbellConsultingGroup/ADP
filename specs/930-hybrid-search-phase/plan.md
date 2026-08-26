# Implementation Plan: Hybrid Search Phase 2 Completion — Stages, Domain Org Unit, Backfill

**Branch**: `930-hybrid-search-phase` | **Date**: 2026-08-26 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/930-hybrid-search-phase/spec.md`

## Summary

Closes the actual remaining gaps in ADP-b6o's hybrid search (bead ADP-7bo), found by direct code
inspection to be narrower than the bead's own stale text implied (see spec.md's Ground-Truth
Correction — value stream and business domain indexing already shipped via 041): (1) index value
stream stages under a new `ENTITY_VALUE_STREAM_STAGE` discriminator, including fixing a latent
cascade-unindex bug where deleting a value stream orphans its stages' index rows; (2) add the
missing `org_unit` field to business domain indexing; (3) extend `adp.search.backfill` from
capability-only to a `reindex_all()` covering all 5 write-hooked entity types; (4) add the test
coverage that doesn't exist today for any of this — new or pre-existing. No new migration.

## Technical Context

**Language/Version**: Python 3.12 (backend only — no frontend file touched; this is a pure
indexing/backfill mechanism with no UI).
**Primary Dependencies**: SQLAlchemy 2 async (Core), pgvector, PostgreSQL full-text search — all
existing (`adp.search`, unchanged dependency surface); zero new packages.
**Storage**: PostgreSQL 16 with pgvector (migration 011, already applied) — no new migration; one
more `entity_type` discriminator value written into the existing polymorphic `searchable_items`
table.
**Testing**: pytest — unit-level "wiring" tests using `monkeypatch` on `adp.business.store.index_entity`/
`unindex_entity` (fast, no Docker, verifies the store passes the correct entity_type/id/text at
every call site — the exact question this feature answers); a new unit test for
`adp.search.backfill.reindex_all()` using a recording fake in place of `default_index()` (avoids
`SearchIndex.upsert`'s Postgres-only `pg_insert(...).on_conflict_do_update(...)`, which cannot
compile against SQLite — confirmed the same constraint 928 hit with a different upsert construct);
Docker-gated integration tests extending `tests/integration/test_search.py`'s existing
`_FakeEmbedder` pattern for the real round-trip over a live Postgres container (written, will run
in CI, same constraint every Docker-gated suite this session has hit locally).
**Target Platform**: Linux server (existing `adp-api` process; `adp.search.backfill` is also a
standalone CLI script, unchanged entry point shape).
**Project Type**: Backend-only addition to the existing web application — no frontend change.
**Performance Goals**: N/A — indexing writes are already best-effort/swallowed-on-failure
(`index_entity`/`unindex_entity`), identical performance envelope to the existing capability/
application/value-stream/domain write hooks.
**Constraints**: Every change must be additive to `adp.business.store` — no existing test may
regress; the cascade-unindex fix (FR-004) must not add a query for the common case of a value
stream with zero stages that meaningfully changes its delete-path cost.
**Scale/Scope**: 2 backend files modified (`adp.business.store`, `adp.search.backfill`), 1 file
modified (`adp.search.index` — new constant), 1 file modified (`adp.search.__init__` — export);
one new unit test file (`tests/unit/business/test_search_indexing.py`), one new unit test file
(`tests/unit/search/test_backfill.py`), extensions to `tests/integration/test_search.py`. No new
production module, no new endpoint, no new table.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Applies? | How this feature satisfies it |
|---|---|---|
| ART-I (SDD Mandatory) | Yes | spec.md (recording the Ground-Truth Correction that changed this feature's real scope) → this plan → tasks.md → implementation, in order. |
| ART-II (Model is Source of Truth) | Yes | No model/schema change; the search index remains a derived, best-effort projection of already-canonical registry data, identical relationship to phase 1. |
| ART-III (Machine-Readable) | Yes | Directly closes a blind spot in the Chat Assistant's own advertised retrieval coverage (`DEFAULT_ENTITY_TYPES` already lists `ENTITY_VALUE_STREAM` — a stage's text was implicitly promised searchable without actually being indexed). |
| ART-IV (TDD) | Yes | FR-009/SC-004 — this feature's central deliverable is closing a total pre-existing test-coverage gap; tasks.md sequences every test before its corresponding implementation task. |
| ART-V (Security by Design) | Yes | Threat model in spec.md confirms zero new trust boundary — reuses phase 1's own best-effort write path unchanged. |
| ART-VI (Observability) | No new obligation | Reuses `index_entity`/`unindex_entity`'s existing warning-log-on-failure behavior verbatim. |
| ART-VII (Grounded AI Only) | No | No AI-generated content involved. |
| ART-VIII (Human-in-the-Loop for Consequence) | No | A structural indexing fix, not a consequential automated action. |
| ART-IX (Provenance/Auditability) | No new obligation | Search-index writes are not part of the audited registry write path (unchanged — this was already true before this feature). |
| ART-X–XII (Validation gating / Traceability / Visual language) | No | Not involved. |
| ART-XIII (Typed Contracts) | Yes | `ENTITY_VALUE_STREAM_STAGE` is a plain typed string constant, matching every sibling discriminator's own contract shape. |
| ART-XIV/XV (Reproducible builds / Schema evolution) | Yes | No migration — schema is unchanged, confirmed in spec.md's Success Criteria. |
| ART-XVI (Documentation as Code) | Yes (SHOULD) | This plan + research.md + data-model.md are the documentation. |

**Initial gate result**: PASS. No article is violated, no Complexity Tracking entry needed.

## Project Structure

### Documentation (this feature)

```text
specs/930-hybrid-search-phase/
├── plan.md              # This file
├── research.md
├── data-model.md
├── quickstart.md
└── tasks.md
```

### Source Code (repository root)

```text
src/adp/
├── search/
│   ├── index.py          # MODIFIED: + ENTITY_VALUE_STREAM_STAGE constant
│   ├── __init__.py        # MODIFIED: + export
│   └── backfill.py        # MODIFIED: + reindex_all(), main() calls it instead of
│                           #   reindex_capabilities()
└── business/
    └── store.py            # MODIFIED: + stage index hooks (add/update/delete/reorder),
                              #   + cascade-unindex fix in delete_value_stream,
                              #   + org_unit added to domain's indexed text

tests/
├── unit/business/
│   └── test_search_indexing.py   # NEW: monkeypatched wiring tests for every
│                                   #   value-stream/stage/domain write-hook path
│                                   #   (new AND pre-existing 041 wiring)
├── unit/search/
│   └── test_backfill.py          # NEW: reindex_all() dispatch/count test via a
│                                   #   recording fake index (SQLite-backed store reads)
└── integration/
    └── test_search.py             # MODIFIED: + Docker-gated round-trip tests for
                                    #   value_stream_stage (new) and confirming
                                    #   application/value_stream/domain (041) still work
```

**Structure Decision**: Existing single-project backend layout — no new module, no new directory
except two new test files following the existing `tests/unit/<domain>/` convention.

## Complexity Tracking

*No violations — table omitted.*
