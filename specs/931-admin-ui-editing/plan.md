# Implementation Plan: Admin UI for Editing Scoring Rubric Weights

**Branch**: `931-admin-ui-editing` | **Date**: 2026-08-26 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/931-admin-ui-editing/spec.md`

## Summary

New admin-only surface for editing the Business Value assessment rubric's weights without a code
deploy — architecturally a near-literal mirror of ADP-SPEC-042's Agent Prompt Management, per the
bead's own explicit instruction, adapted only where the underlying data shape differs (a validated
dict of six named float weights, not free text). New `adp.admin.rubric_registry` (mirrors
`prompt_registry`) registers one rubric (`business_value`) today, extensible without a schema
change for any future rubric. New migration adds `rubric_weight_overrides`/`rubric_weight_history`
(mirroring `agent_prompt_overrides`/`agent_prompt_history`'s exact shape). New
`ActionType.MANAGE_SCORING_RUBRICS`, granted only to `PersonaRole.PLATFORM_ADMIN` (explicitly
excluded from Enterprise Architect's wildcard, identical to `MANAGE_AGENT_PROMPTS`'s own
precedent). `compute_business_value_score()` gains an optional `weights` parameter (stays pure/
no-I/O); its two existing callers resolve the effective weights via a new
`get_effective_weights()` before calling it (self-contained, no session param -- mirrors
`get_effective_prompt()`'s exact signature and role).
New "Scoring Rubrics" nav entry/screen, sibling to "Agent Prompts".

## Technical Context

**Language/Version**: Python 3.12 (backend); TypeScript 5.x + React 18 (frontend) — both existing
stacks, no new language/version surface.
**Primary Dependencies**: FastAPI ≥ 0.111, SQLAlchemy 2 async (Core), asyncpg, Alembic, Pydantic
v2, React 18, TanStack Query v5 — all existing project dependencies; zero new packages either
side.
**Storage**: PostgreSQL 16 — one new migration (`040`, `down_revision="039"`): two new tables,
`rubric_weight_overrides` (PK `rubric_id`, `weights JSONB`, `updated_by`, `updated_at`, `version`)
and `rubric_weight_history` (append-only, `id BIGSERIAL` PK, `rubric_id`, `actor`, `changed_at`,
`change_type` CHECK `IN ('edit','restore')`, `prior_weights JSONB`, `new_weights JSONB`,
`confirmation_id`) — line-for-line structural mirror of migration 023, substituting `weights
JSONB` for `prompt_text TEXT`.
**Testing**: pytest (unit tests for the rubric registry, the validator, `get_effective_weights()`,
`compute_business_value_score()`'s new optional parameter; contract tests for the full admin API
full-stack against SQLite, mirroring `tests/contract/test_admin_prompts_contract.py`'s own shape
exactly — confirm/history/restore/version-conflict/permission-denial); Vitest (new component tests
for `RubricEditor.tsx`/`ScoringRubricsPage.tsx` — no `PromptEditor.test.tsx`/`AdminPage.test.tsx`
exists today to mirror, confirmed by direct `find`, so this feature's own frontend tests are the
first component-level coverage either admin screen has).
**Target Platform**: Linux server (existing `adp-api` process) + browser (existing `web/` SPA) — no
new deployable either side.
**Project Type**: Web application (existing FastAPI backend + Vite/React frontend).
**Performance Goals**: N/A — an admin-only, low-frequency write path; identical envelope to
ADP-SPEC-042.
**Constraints**: `compute_business_value_score()` MUST remain synchronous and I/O-free (spec.md
FR-008) — its own docstring already establishes this as a deliberate design invariant shared with
`adp.strategy.store.compute_status()`; this feature must not weaken that, only add an optional
parameter with a backward-compatible default.
**Scale/Scope**: 1 new migration, 1 new backend package addition (`adp.admin.rubric_registry`,
`adp.admin.rubric_service` — siblings to the existing `prompt_registry`/`service`), 1 new router,
2 files modified (`adp.authz.roles`/`permissions`, `adp.authz.enforcement`), 2 files modified
(`adp.application.models`/`store` — the optional `weights` param + effective-weights resolution at
the two call sites), 1 new frontend API client, 2 new frontend components + 1 new page, 3 files
modified (`web/src/shell/index.ts`, `web/src/ui/AppShell.tsx`, `web/src/App.tsx`).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Applies? | How this feature satisfies it |
|---|---|---|
| ART-I (SDD Mandatory) | Yes | spec.md → this plan → tasks.md → implementation, in order — the bead was not yet spec'd. |
| ART-II (Model is Source of Truth) | Yes | The override table is the single source of "what weights are active right now"; `compute_business_value_score()` never reads a second, competing source. |
| ART-III (Machine-Readable) | No new obligation | An admin-tuning surface, not a registry entity export. |
| ART-IV (TDD) | Yes | tasks.md sequences failing unit/contract/frontend tests before each implementation task, mirroring ADP-SPEC-042's own task sequencing. |
| ART-V (Security by Design) | Yes | Threat model in spec.md; new admin-only permission, identical shape to `MANAGE_AGENT_PROMPTS`. |
| ART-VI (Observability) | No new obligation | Plain writes through an already-instrumented route. |
| ART-VII (Grounded AI Only) | No | Not involved. |
| ART-VIII (Human-in-the-Loop for Consequence) | Yes | Confirmation-gated (`confirmation_id`, `REQUIRES_CONFIRMATION`), identical mechanism to `MANAGE_AGENT_PROMPTS`. |
| ART-IX (Provenance/Auditability) | Yes | Append-only `rubric_weight_history`, never updated/deleted — same guarantee as `agent_prompt_history`. |
| ART-X–XII (Validation gating / Traceability / Visual language) | No | Not involved. |
| ART-XIII (Typed Contracts) | Yes | Pydantic v2 models end-to-end, `extra="forbid"`, matching every sibling admin model. |
| ART-XIV/XV (Reproducible builds / Schema evolution) | Yes | One forward+reverse migration (040), reversible cleanly. |
| ART-XVI (Documentation as Code) | Yes (SHOULD) | This plan + research.md + data-model.md + contracts/. |

**Initial gate result**: PASS. No article is violated, no Complexity Tracking entry needed — this
is a structural mirror of an already-approved pattern, adapted for a different data shape.

## Project Structure

### Documentation (this feature)

```text
specs/931-admin-ui-editing/
├── plan.md
├── research.md
├── data-model.md
├── contracts/
│   └── scoring-rubrics-api.md
├── quickstart.md
└── tasks.md
```

### Source Code (repository root)

```text
src/adp/
├── admin/
│   ├── rubric_registry.py       # NEW: mirrors prompt_registry.py
│   ├── rubric_models.py         # NEW: mirrors admin/models.py
│   └── rubric_service.py        # NEW: mirrors admin/service.py
├── api/routers/
│   └── admin_rubrics_router.py  # NEW: mirrors admin_prompts_router.py
├── application/
│   ├── models.py                 # MODIFIED: no field change -- BUSINESS_VALUE_WEIGHTS
│   │                              #   stays as the fallback constant, unchanged
│   └── store.py                  # MODIFIED: compute_business_value_score() gains an
│                                  #   optional `weights` param; the two call sites
│                                  #   resolve effective weights first
├── authz/
│   ├── roles.py                  # MODIFIED: + ActionType.MANAGE_SCORING_RUBRICS
│   ├── permissions.py            # MODIFIED: PERMISSIONS_VERSION bump, grant/exclude
│   └── enforcement.py            # MODIFIED: + prefix rule
└── store/migrations/versions/
    └── 040_rubric_weight_management.py  # NEW

web/src/
├── api/
│   └── adminRubrics.ts           # NEW: mirrors adminPrompts.ts
├── admin/
│   ├── ScoringRubricsPage.tsx    # NEW: mirrors AdminPage.tsx
│   ├── RubricEditor.tsx          # NEW: mirrors PromptEditor.tsx (numeric-per-
│   │                              #   dimension form + live sum indicator instead
│   │                              #   of a free-text textarea)
│   └── RubricHistory.tsx         # NEW: mirrors PromptHistory.tsx
├── shell/index.ts                # MODIFIED: + "scoring-rubrics" AppView
├── ui/AppShell.tsx               # MODIFIED: + ADMIN nav entry + TITLES entry
└── App.tsx                       # MODIFIED: + case "scoring-rubrics"

tests/
├── unit/admin/
│   └── test_rubric_registry.py       # NEW
├── unit/application/
│   └── test_business_value_score.py  # MODIFIED: + optional-weights-param tests
├── contract/
│   └── test_admin_rubrics_contract.py  # NEW: mirrors test_admin_prompts_contract.py
├── integration/
│   └── test_admin_rubrics_flow.py      # NEW: mirrors test_admin_prompts_flow.py
│                                         #   (Docker-gated, real Postgres -- an edit
│                                         #   takes effect for the very next assessment,
│                                         #   no restart/redeploy)
└── authz/
    └── test_permissions.py            # MODIFIED: PERMISSIONS_VERSION bump fallout

web/src/admin/ScoringRubricsPage.test.tsx  # NEW (no equivalent test exists for
web/src/admin/RubricEditor.test.tsx        #   AdminPage.tsx/PromptEditor.tsx today --
                                            #   confirmed by direct find, research.md D6)
```

**Structure Decision**: Existing single-project layout — no new top-level module; every new file
is a sibling to an already-shipped ADP-SPEC-042 file of the same role.

## Complexity Tracking

*No violations — table omitted.*
