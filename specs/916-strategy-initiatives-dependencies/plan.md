# Implementation Plan: Strategy Execution Layer — Initiatives & Objective Dependencies

**Branch**: `916-strategy-initiatives-dependencies` | **Date**: 2026-08-13 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/916-strategy-initiatives-dependencies/spec.md`

## Summary

Adds a strategy-level `StrategyInitiative` entity (name, description, owner, free-enum status) with a many-to-many link to `StrategicObjective`, plus a self-referential `ObjectiveDependency` (`depends_on`) relationship between objectives, rejected at write time if it would create a cycle (direct, chained, or self-referential). Both live in a **new submodule** `src/adp/strategy/initiatives.py` inside the existing `adp.strategy` package — not a new sibling package (resolved by measurement, spec.md's Ground-Truth Correction 1) and not further bloating the existing `models.py`/`store.py`/`router.py` files, which `915-objective-progress-tracking` already extended once this session. `router.py` imports from the new submodule and registers its endpoints on the same, already-existing `router` object.

## Technical Context

**Language/Version**: Python 3.12 (backend); TypeScript 5.x + React 18 (frontend) — both existing stacks, no new language/version surface.
**Primary Dependencies**: FastAPI ≥ 0.111, SQLAlchemy 2 async (Core, mirroring `adp.strategy.store`'s existing `sa.Table`/raw-`sa.text()` style — no ORM), Alembic, Pydantic v2, React 18, TanStack Query v5 — all existing project dependencies. Zero new packages either side.
**Storage**: PostgreSQL 16 — three new tables (`strategy_initiatives`, `strategy_initiative_objective_links`, `strategic_objective_dependencies`). Migration 027 (`down_revision = "026"`).
**Testing**: pytest (backend unit + contract, mirroring `915-objective-progress-tracking`'s established `AsyncMock`/in-memory-SQLite patterns for this exact package), Vitest + Testing Library (frontend).
**Target Platform**: Linux server (existing FastAPI/uvicorn deployment); browser (existing React SPA).
**Project Type**: Web application — one new backend submodule (`src/adp/strategy/initiatives.py`) + extensions to the existing `src/adp/strategy/router.py` and `web/src/strategy/`/`web/src/api/strategy.ts`. No new top-level project.
**Performance Goals**: No new performance requirement beyond existing platform norms. Cycle detection is a bounded graph traversal (at most once per objective in the dependency graph, which is demo-scale per the rest of `adp.strategy`) run synchronously on write, not a background job.
**Constraints**: None beyond existing platform norms (typed boundaries, `extra="forbid"`, ART-IX satisfied by structured logging per `915`'s established precedent for this domain — no `AuditEntry` mechanism exists here).
**Scale/Scope**: Demo-scale (existing seed data has a handful of objectives); no scale concern distinct from the rest of `adp.strategy`.

## Ground-Truth Corrections Carried From Spec *(repeated here because they change this plan's design, not just narrative)*

1. **Package placement resolved by direct measurement**: `src/adp/strategy/{models,store,router}.py` totals 1,434 lines — well under the ~2,847-line threshold that triggered the `adp.business` → `adp.strategy` split. This plan creates a **submodule** (`src/adp/strategy/initiatives.py`), not a new sibling package.
2. **No `users` table exists anywhere in this codebase** (established building the sibling `915-objective-progress-tracking` feature). `strategy_initiatives.owner` is plain `TEXT`, matching `strategic_objectives.owner`/`strategic_themes.owner` — not the bead's originally-proposed `owner_id UUID FK`.
3. **`adp.application.models.TransformationInitiative` is real, confirmed, and deliberately unrelated** — a much thinner shape (`id`/`name`/`description`/`target_date`, no `owner`, no `status`) scoped to application-level transformation tracking. No naming collision risk (different modules); no shared code; this feature's `StrategyInitiative` is a new, independent concept.
4. **No audit mechanism this domain can write a real `AuditEntry` row to** (same fact as `915`'s Ground-Truth Correction 4) — `adp.strategy.router` already established the structured-`logger.info(...)` convention for this package; this feature's writes follow the same pattern, not a new one.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Applies? | How this feature satisfies it |
|---|---|---|
| ART-I (SDD mandatory) | Yes | Follows an approved spec (`spec.md`, checklist 16/16 pass); tasks.md will reference FR-IDs. |
| ART-II (model is source of truth) | Yes | The dependency graph is kept acyclic by construction (rejected at write time) — no downstream consumer needs to re-validate or work around a cycle; nothing here is a hand-maintained derived value. |
| ART-IV (TDD) | Yes | Contract tests for every new endpoint before implementation; a dedicated unit-test file for the pure cycle-detection function (no I/O, table-driven) before it's wired into the store. |
| ART-V (security by design) | Yes | Threat model already in spec.md — reuses the existing `WRITE_BUSINESS_ARCH` gate, no new trust boundary, no secrets, no PII. |
| ART-VII (grounded AI only) | **N/A** | No AI involvement in this feature at all. |
| ART-VIII (human-in-the-loop) | N/A | No consequential/irreversible action gated behind explicit confirmation here — initiative CRUD and dependency links are ordinary planning-data writes, the same tier as every other `adp.strategy` mutation (theme/objective edits), none of which currently carry an ART-VIII confirmation step either. |
| ART-IX (provenance/auditability) | Yes (SHOULD-level, per existing domain precedent) | Initiative and dependency writes emit structured `logger.info(...)` lines, reusing the convention `915-objective-progress-tracking` already established for `adp.strategy` (Ground-Truth Correction 4). |
| ART-XIII (typed contracts) | Yes | All new request/response models are Pydantic v2 with `extra="forbid"`, matching every existing model in `adp.strategy`. |

No violations. **Complexity Tracking is not filled in** — the one structural addition (a new submodule file) is itself the outcome of following the codebase's own documented package-size convention, not a deviation from it.

## Project Structure

### Documentation (this feature)

```text
specs/916-strategy-initiatives-dependencies/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
├── contracts/            # Phase 1 output
│   └── strategy-initiatives-dependencies-api-contract.md
└── tasks.md              # Phase 2 output (/speckit.tasks — not this command)
```

### Source Code (repository root)

```text
src/adp/strategy/
├── initiatives.py     # NEW: StrategyInitiative(+Create/+Update/+ListResponse) and
│                       #   ObjectiveDependency(+Create/+ListResponse) Pydantic models;
│                       #   _initiatives/_initiative_objective_links/_objective_dependencies
│                       #   sa.Table defs; store functions (create/get/list/update/delete
│                       #   initiative, link/unlink initiative-objective, add/remove
│                       #   objective dependency with cycle check, get dependencies both
│                       #   directions); CycleError exception
├── router.py            # EXTEND: import from initiatives.py, register new endpoints on
│                        #   the existing `router` object (no new prefix, no new router)
├── models.py             # unchanged
├── store.py              # unchanged
└── __init__.py            # unchanged

src/adp/store/migrations/versions/
└── 027_strategy_initiatives.py   # NEW: strategy_initiatives, strategy_initiative_objective_links,
                                    #   strategic_objective_dependencies (self-referential, two
                                    #   FKs to strategic_objectives.id, both ON DELETE CASCADE)

tests/unit/strategy/
├── test_initiatives_models.py   # NEW: model validation cases
├── test_initiatives_store.py    # NEW: initiative CRUD, link/unlink, dependency CRUD
└── test_dependency_cycles.py    # NEW: pure cycle-detection unit tests (table-driven, no I/O)

tests/contract/
└── test_strategy_api_contract.py   # EXTEND: new endpoint contract cases

web/src/api/
└── strategy.ts           # EXTEND: initiative types/hooks, dependency types/hooks

web/src/strategy/
├── InitiativeList.tsx         # NEW: create/edit/delete initiatives, link to objectives
├── ObjectiveDetail.tsx        # EXTEND: linked initiatives panel, depends-on/blocks panel
└── *.test.tsx                 # NEW/EXTEND alongside each component above
```

**Structure Decision**: One new backend submodule file inside the domain's existing package (`src/adp/strategy/initiatives.py`) plus one migration — no new package, no new frontend directory (extends `web/src/strategy/` with one new component, matching how `915` added `ObjectiveProgressForm.tsx` alongside the existing files rather than restructuring anything).

## Complexity Tracking

*No entries — Constitution Check passed with no violations requiring justification.*
