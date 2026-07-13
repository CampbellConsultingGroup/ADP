# Implementation Plan: Persistence & Design Store

**Branch**: `002-design-store` | **Date**: 2026-06-27 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/002-design-store/spec.md`

## Summary

Build the durable store for `ArchitectureDescription` records — a PostgreSQL-backed persistence module that saves and versions designs atomically with their audit entries, enforces schema validation on write, prohibits deletion of any version or audit record, and serves indexed traceability queries over requirement-to-element satisfies links. Implemented as a new `adp.store` sub-package extending the existing ADP-SPEC-001 Python package.

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: SQLAlchemy 2.x (async ORM), asyncpg (PostgreSQL async driver), Alembic (migrations), testcontainers[postgres] (PostgreSQL container for integration tests), pydantic-settings (database URL config)  
**Storage**: PostgreSQL 15+ — primary persistence; JSONB for `ArchitectureDescription` content with indexed paths for traceability queries  
**Testing**: pytest ≥ 7, pytest-asyncio, pytest-cov, testcontainers[postgres]; integration tests run against a real PostgreSQL container (no mocking of the storage layer)  
**Target Platform**: Linux server process within the ADP monorepo; same environment as ADP-SPEC-001  
**Project Type**: Python library module (`adp.store` sub-package extending `src/adp/`)  
**Performance Goals**: Single-design read ≤ 1 second for designs with ≤ 500 entities (SC-005, NFR-001)  
**Constraints**: Optimistic concurrency control on version number; append-only audit entries enforced at both ORM and database trigger layers; schema validation on every write (FR-006); no mocking of database in integration tests (ART-IV)  
**Scale/Scope**: Internal platform service; single-tenant for v1; no horizontal scale requirements

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Article(s) | Requirement | Status |
|------|-----------|-------------|--------|
| QG-01 | ART-I, ART-XVI | PR references approved spec/task IDs | ✅ All tasks will reference ADP-SPEC-002 |
| QG-03 | ART-III, ART-XIII, ART-XV | All persisted artifacts validate against published schema; store interface is typed | ✅ FR-006 (schema validation on write); store accepts/returns `ArchitectureDescription`, not raw dicts |
| QG-04 | ART-IV | Tests before implementation; ≥ 85% coverage | ✅ Integration tests with real PostgreSQL; testcontainers approach |
| QG-05 | ART-IV, ART-XIII | Contract tests pass | ✅ Store interface contract tests planned |
| QG-06 | ART-V | SAST clean; dep scan; secret scan | ✅ Database credentials externalized via env vars; no secrets in source |
| QG-09 | ART-V, ART-VIII | No prohibited-action code paths | ✅ Pure persistence; no external actions |
| QG-10 | ART-VI | Structured, correlated logs on new code paths | ⚠️ **Added by plan** — spec did not enumerate ART-VI but the persistence layer IS a runtime service; mutation, validation failure, and traceability query paths MUST emit structured logs |
| QG-13 | ART-VIII, ART-IX | Model mutations write append-only audit entries with origin and actor | ✅ FR-003 / FR-004 are the primary implementation of this gate for the store |
| QG-16 | ART-XI | Referential integrity holds | ✅ Enforced at write time by ADP-SPEC-001 model validator before any write reaches the store |
| QG-18 | ART-II, ART-XIV, ART-XV | Pinned deps; reproducible from clean checkout | ✅ Alembic migrations versioned; deps pinned in pyproject.toml |

**ART-VI addition note**: The spec's Constitutional Articles Touched section omitted ART-VI. The plan adds it because `adp.store` introduces runtime code paths (save, get, query) that MUST emit structured logs per QG-10. Tasks will include a logging task in each user-story phase.

**Constitution Alignment**: No violations. ART-VII (AI), ART-VIII (human-in-loop), ART-X (deterministic gating), ART-XII (visual language) are not in scope — this is a pure persistence module with no AI orchestration and no user interface.

## Project Structure

### Documentation (this feature)

```text
specs/002-design-store/
├── plan.md              # This file
├── research.md          # Phase 0 — decisions and rationale
├── data-model.md        # Phase 1 — persistence schema and store entities
├── contracts/
│   └── store-contract.md   # Phase 1 — Python store interface contract
├── quickstart.md        # Phase 1 — saving and querying a design
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output (/speckit.tasks — not created here)
```

### Source Code (repository root)

```text
src/
└── adp/
    ├── __init__.py               # from ADP-SPEC-001
    ├── models.py                 # from ADP-SPEC-001
    ├── generate.py               # from ADP-SPEC-001
    ├── validate.py               # from ADP-SPEC-001
    └── store/
        ├── __init__.py           # Exports DesignStore, DesignRecord, DesignVersion
        ├── store.py              # DesignStore — primary interface (save, get, query)
        ├── records.py            # SQLAlchemy ORM table definitions
        ├── queries.py            # Traceability query implementations
        ├── migrations/           # Alembic migration scripts
        │   ├── env.py
        │   ├── script.py.mako
        │   └── versions/
        │       └── 001_initial_schema.py
        └── logging.py            # Structured log helpers for store operations (ART-VI)

tests/
├── unit/
│   ├── test_models.py                    # from ADP-SPEC-001
│   ├── test_generate.py                  # from ADP-SPEC-001
│   ├── test_validation.py                # from ADP-SPEC-001
│   ├── test_referential_integrity.py     # from ADP-SPEC-001
│   └── test_store_queries.py             # Unit tests for traceability query logic
└── integration/
    └── test_store.py                     # Full store integration tests (testcontainers)

tests/contract/
└── test_schema.py                        # from ADP-SPEC-001 (unchanged)

alembic.ini                               # Alembic configuration

pyproject.toml                            # Updated with new deps (SQLAlchemy, asyncpg, etc.)
```

**Structure Decision**: Extend the existing single `src/adp/` package with a `store/` sub-package. This keeps the ADP package cohesive, avoids a separate project, and allows `adp.store` to import `adp.models` directly without additional wiring. Integration tests go in a new `tests/integration/` directory alongside the existing `tests/unit/` and `tests/contract/` directories.
