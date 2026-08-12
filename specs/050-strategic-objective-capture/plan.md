# Implementation Plan: Capture Strategic Objectives

**Branch**: `050-strategic-objective-capture` | **Date**: 2026-08-12 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/050-strategic-objective-capture/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

A new top-level backend package, `adp.strategy` (mirroring `adp.diagrams`/`adp.chat`'s established sibling-package convention rather than growing `adp.business`'s already-substantial models/store/router files — 2,847 combined lines), providing CRUD for two new entities: `StrategicTheme` (a small, reusable taxonomy table, precedented directly by `BusinessDomain`) and `StrategicObjective` (theme reference, owner, statement, optional typed metric/target, structured horizon), plus two new many-to-many join tables to `business_capabilities`/`value_streams`, mirroring `capability_design_links`/`value_stream_design_links` exactly. Reuses the existing `WRITE_BUSINESS_ARCH` RBAC action (no new `ActionType`) and the existing `DesignLinkEditor.tsx` filtered-dropdown pattern for both new join relationships on the frontend. `adp.strategy`'s store validates capability/value-stream ids by calling `adp.business.store`'s existing read functions directly (a read-only cross-package call, precedented by Agent Review's own cross-module calls) — never duplicating or bypassing that registry.

## Technical Context

**Language/Version**: Python 3.12 (backend); TypeScript 5.x + React 18 (frontend) — both existing stacks, no new language/version surface.
**Primary Dependencies**: None new. FastAPI, SQLAlchemy 2 async (Core), asyncpg, Alembic, Pydantic v2, React 18, TanStack Query v5 — all existing project dependencies.
**Storage**: PostgreSQL 16 — migration 025 (`down_revision="024"`): two new tables (`strategic_themes`, `strategic_objectives`) and two new join tables (`strategic_objective_capabilities`, `strategic_objective_value_streams`), mirroring migration 008's exact join-table shape (composite PK, `ON DELETE CASCADE` on both legs, one index, `created_at`).
**Testing**: pytest (backend contract/unit tests, mirroring `adp.business`'s own existing router/store test conventions) + Vitest/RTL (frontend, mirroring `DesignLinkEditor`'s and `CapabilityForm`'s existing test conventions where they exist, or the pattern established across specs 046–049 otherwise).
**Target Platform**: Existing `adp-api` process (Linux server) + browser (existing `web/` SPA) — no new deployable.
**Project Type**: Web application — this feature adds to both sides of the existing FastAPI backend + React frontend split.
**Performance Goals**: None specific — ordinary CRUD at the same modest scale every other ADP business-registry entity already assumes (tens to low hundreds of rows).
**Constraints**: Zero changes to the existing `BusinessCapability`/`ValueStream`/`BusinessDomain` models or their existing APIs (spec FR-012) — only new, additive join tables referencing them; reuses the existing `WRITE_BUSINESS_ARCH` action rather than introducing a new one (matching how `business_domains` itself needed no new permission when it was added); the capability/value-stream "search and add" UI mirrors `DesignLinkEditor.tsx`'s established filtered-dropdown pattern, not a new typeahead component.
**Scale/Scope**: 1 new backend package (`adp.strategy`, ~4 files: `models.py`, `store.py`, `router.py`, `__init__.py`), 1 new migration (4 tables), 1 new frontend module (`web/src/strategy/`, mirroring `web/src/business/`'s own file-per-concern convention: a themes list/form, an objectives list, an objective detail/form with two link editors reusing `DesignLinkEditor.tsx`'s pattern), 1 new nav entry.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Applies? | How this feature satisfies it |
|---|---|---|
| ART-I (SDD Mandatory) | Yes | spec.md (16/16 checklist, zero `NEEDS CLARIFICATION`) → this plan → tasks.md (next command) → implementation, in order. |
| ART-II (Model is Source of Truth) | Yes | `StrategicObjective`/`StrategicTheme` become new canonical entities in ADP's own data model, exactly like `BusinessCapability`/`ValueStream`/`BusinessDomain` before them — not documents, not side-channel notes. |
| ART-III (Machine-Readable) | Yes | The feature's entire purpose (spec.md's own framing, from `docs/business_strategy.md`): a structured `StrategicObjective`, not a text blob, is what lets a future heat map/strategy-map view become a *renderable output* of the model. |
| ART-IV (TDD) | Yes | tasks.md will sequence failing backend contract tests and frontend unit tests before each implementation task, matching the established convention across specs 046–049. |
| ART-V (Security by Design) | Yes | Threat model in spec.md: ordinary CRUD over already-authorized business data; both new link types are validated against ADP's real capability/value-stream registries at write time (never free text) — no new trust boundary, no new authorization mechanism. |
| ART-VI (Observability) | Yes | Create/update/delete of an objective, theme, or link is a normal structured-logged mutation, matching every other `adp.business`-adjacent router; no AI step is involved. |
| ART-VII, ART-VIII, ART-IX, ART-X, ART-XI | No | No AI-generated content, no AI proposal to confirm, no new audit-trail obligation beyond ordinary timestamps (matching `BusinessCapability`'s own precedent), no validation gating, no traceability-thread change (spec explicitly scopes out linking objectives to designs/audit in this iteration). |
| ART-XII (Fixed Visual Language) | No | Governs the locked C4 theme specifically. |
| ART-XIII (Typed Contracts) | Yes | New Pydantic v2 models with `extra="forbid"`, matching every other ADP boundary; metric/target/horizon are explicitly typed fields (spec's own core requirement), not free text. |
| ART-XIV, ART-XV (Reproducible builds / Schema evolution) | Yes | Migration 025 is a normal, reversible Alembic step — no generated-schema-drift concern (this data isn't part of `architecture-description.schema.json`). |
| ART-XVI (Documentation as Code) | Yes (SHOULD) | This plan + research.md + data-model.md + contracts/ are the documentation, each decision grounded in a direct read of the precedent it follows. |

**Initial gate result**: PASS. No article is violated. **No Complexity Tracking entry is needed** — every design decision (new sibling package over growing `adp.business`; reusing `WRITE_BUSINESS_ARCH`; reusing `DesignLinkEditor`'s pattern; mirroring migration 008's join-table shape) picks the option that reuses an already-established pattern.

**Post-Phase-1 re-check**: PASS (unchanged) — data-model.md and contracts/ below implement exactly the additive, precedent-following design described above; no new gate is implicated by the detailed design.

## Project Structure

### Documentation (this feature)

```text
specs/050-strategic-objective-capture/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md         # Phase 1 output (/speckit.plan command)
├── quickstart.md         # Phase 1 output (/speckit.plan command)
├── contracts/
│   └── strategy-api.md   # Phase 1 output (/speckit.plan command)
├── checklists/
│   └── requirements.md
└── tasks.md               # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/adp/strategy/                        # NEW package (backend)
├── __init__.py
├── models.py                            # Pydantic v2: StrategicTheme, StrategicThemeCreate,
│                                         #   StrategicObjective, StrategicObjectiveCreate/Update,
│                                         #   StrategicObjectiveListResponse, ObjectiveDirection
│                                         #   (Literal["increase","decrease","reach"]),
│                                         #   ObjectivePeriod (Literal["Q1","Q2","Q3","Q4","FY"])
├── store.py                             # SQLAlchemy Core CRUD against strategic_themes/
│                                         #   strategic_objectives/the two join tables; validates
│                                         #   capability_id/value_stream_id via direct calls into
│                                         #   adp.business.store's existing read functions
└── router.py                            # POST/GET /api/v1/strategy/themes,
                                          #   POST/GET/PUT/DELETE /api/v1/strategy/objectives[/{id}],
                                          #   POST/DELETE .../objectives/{id}/capabilities/{cap_id},
                                          #   POST/DELETE .../objectives/{id}/value-streams/{vs_id}

src/adp/store/migrations/versions/
└── 025_strategic_objectives.py          # NEW migration: 4 tables (down_revision="024")

src/adp/api/app.py                       # MODIFIED: register the new adp.strategy router

web/src/strategy/                        # NEW module (frontend)
├── ThemeList.tsx                        # list + create (mirrors DomainList.tsx's convention)
├── ObjectiveList.tsx                    # list (mirrors ValueStreamList.tsx's convention)
├── ObjectiveForm.tsx                    # create/edit core fields
├── ObjectiveDetail.tsx                  # view one objective + its two link editors
├── ObjectiveCapabilityLinkEditor.tsx     # mirrors DesignLinkEditor.tsx's filtered-dropdown
│                                         #   pattern exactly, adapted for capability targets
├── ObjectiveValueStreamLinkEditor.tsx    # same pattern, adapted for value-stream targets
└── StrategyPage.tsx                     # top-level tab container (mirrors BusinessPage.tsx)

web/src/api/strategy.ts                  # NEW: typed client + TanStack Query hooks, mirroring
                                          #   web/src/api/business.ts's existing hook conventions

web/src/App.tsx, web/src/shell/index.ts, # MODIFIED: new "strategy" AppView + nav entry,
web/src/ui/AppShell.tsx                  #   mirrors the "diagrams" nav entry added in ADP-914.5

tests/unit/strategy/                     # NEW
├── test_strategy_models.py
└── test_strategy_store.py

tests/contract/
└── test_strategy_api_contract.py        # NEW
```

**Structure Decision**: One new backend package (`adp.strategy`, 3 files + `__init__.py`) rather than extending `adp.business`'s already-substantial files — mirrors the `adp.diagrams`/`adp.chat` sibling-package precedent. One new frontend module (`web/src/strategy/`) following `web/src/business/`'s own file-per-concern convention exactly, with the two link editors as near-verbatim mirrors of the proven `DesignLinkEditor.tsx` pattern (adapted for capability/value-stream targets instead of designs) rather than a new component design. A new top-level nav entry (not nested under Business Architecture) since strategic objectives are a distinct entity type with their own lifecycle, not a sub-view of capabilities/value streams/domains.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations — table intentionally omitted.
