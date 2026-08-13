# Implementation Plan: Objective ↔ Design/Application Traceability

**Branch**: `917-objective-design-traceability` | **Date**: 2026-08-13 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/917-objective-design-traceability/spec.md`

## Summary

Add two new many-to-many join tables — `objective_design_links` and `objective_application_links` —
extending `adp.strategy`'s existing capability/value-stream link pattern (already in
`models.py`/`store.py`/`router.py`) to close the top-priority open-frontier traceability gap: an
objective today links to capabilities/value streams (Layer 1) but nothing forward to the designs
(Layer 3) or applications (Layer 2) that actually realize it. Both directions are surfaced: forward
(objective → designs/applications) on `ObjectiveDetail.tsx`, reverse (design/application → objectives)
on `C4DesignView.tsx` (per the resolved Clarification — the only design-scoped screen that exists
today) and `ApplicationDetail.tsx` (which already has a real sectioned detail screen).

## Technical Context

**Language/Version**: Python 3.12 (backend); TypeScript 5.x + React 18 (frontend) — both existing
stacks, no new language/version surface.
**Primary Dependencies**: FastAPI ≥ 0.111, SQLAlchemy 2 async (Core, mirroring `adp.strategy.store`'s
existing `sa.Table`/raw-`sa.text()` style — no ORM), Alembic, Pydantic v2, React 18, TanStack Query
v5 — all existing project dependencies. Zero new packages either side.
**Storage**: PostgreSQL 16 — two new join tables via migration 028 (`down_revision = "027"`), no
column changes to any existing table.
**Testing**: pytest (unit + contract, mirroring `test_strategy_store.py`/`test_strategy_api_contract.py`'s
existing in-memory-SQLite fixture convention); Vitest + Testing Library for the two new React
components/panels.
**Target Platform**: Linux server (backend), browser (frontend) — unchanged.
**Project Type**: Web application (existing `src/adp/` backend + `web/` frontend split).
**Performance Goals**: No new performance surface — these are simple indexed join-table reads/writes,
same shape and scale as the six existing traceability link tables already in production.
**Constraints**: Read endpoints (`GET .../objectives` on both the designs and applications routers)
MUST remain ungated per the existing "reads are ungated by default" convention. Write endpoints MUST
fall under the existing `/api/v1/strategy/` prefix's `strategy:write` gate — no new `ActionType`.
**Scale/Scope**: Two new tables, ~6 new store functions, ~8 new endpoints (4 forward link/unlink pairs
across designs+applications, 2 new reverse-lookup GETs, existing `StrategicObjective` model gains 2
fields), 2 new frontend link-editor components + 1 read-only reverse panel.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Applies? | How this feature satisfies it |
|---|---|---|
| ART-I (SDD mandatory) | Yes | This plan, following `spec.md`, precedes all code; `/speckit-tasks` → `/speckit-implement` next. |
| ART-II (model is source of truth) | N/A | No schema/generated-artifact change — link tables are plain join tables, not part of `ArchitectureDescription`. |
| ART-III (machine-readable) | Yes | New Pydantic response fields (`design_ids`/`application_ids`) are typed, `extra="forbid"`, same as every other field on `StrategicObjective`. |
| ART-IV (TDD) | Yes | Store/model/contract tests written and confirmed red before implementation, mirroring ADP-d8u.1/.5/.6's established rhythm in this exact package. |
| ART-V (security by design) | Yes | Threat model in spec.md; no new `ActionType`, reuses existing `strategy:write` gate; reads ungated per existing convention; generic 404s on invalid ids (no enumeration leak). |
| ART-VI (observability) | Yes | Structured `logger.info(...)` on link/unlink, matching every other write in `adp.strategy.router` (no OTel span — this isn't an AI orchestration step, so ART-VI's span requirement doesn't apply; the general logging rule does). |
| ART-VII (grounded AI only) | N/A | No AI-generated content anywhere in this feature's scope. |
| ART-VIII (human-in-the-loop) | N/A | Plain CRUD, not a consequential/irreversible AI-proposed action. |
| ART-IX (provenance/auditability) | Yes | `adp.strategy` has no `AuditEntry`-writing capability (established fact, ADP-d8u.5/.6 — `audit_entries` is coupled to `design_id`/`design_version`, not applicable to link tables). Satisfied via structured `logger.info(...)`, the established precedent for this whole package. |
| ART-X (deterministic validation gating) | N/A | No LLM-as-a-Judge involvement. |
| ART-XI (traceability end to end) | Yes | This feature *is* a traceability extension — referential integrity enforced via FK `ON DELETE CASCADE` both legs, matching every other link table. |
| ART-XII (fixed visual language) | N/A | No diagram/theme rendering touched. |
| ART-XIII (typed contracts) | Yes | All new request/response shapes are Pydantic v2 models with `extra="forbid"`. |
| ART-XIV (reproducible builds) | Yes | `adp-generate --check` run as part of Polish phase, same as every prior feature. |
| ART-XV (schema evolution governed) | Yes | Additive-only migration (two new tables, no existing-table changes) — no breaking change, no major version bump needed. |
| ART-XVI (documentation as code) | N/A | No new stakeholder-facing document generator touched. |

No violations requiring justification — Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/917-objective-design-traceability/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
├── contracts/            # Phase 1 output
└── tasks.md              # Phase 2 output (/speckit-tasks, not this command)
```

### Source Code (repository root)

```text
src/adp/strategy/
├── models.py             # extend: StrategicObjective gains design_ids/application_ids
├── store.py               # extend: two new sa.Table defs (_objective_design_links,
│                           #   _objective_application_links), two new lightweight read-only
│                           #   table mirrors (_designs, _applications, matching
│                           #   adp.business.store's existing _designs precedent), 8 new
│                           #   store functions (link/unlink/list x2 targets, plus 2 reverse
│                           #   lookups called from other packages' routers)
└── router.py               # extend: 8 new endpoints, 2 new cross-package session
                            #   dependencies (_get_store_session, reusing
                            #   _get_application_session which already exists)

src/adp/api/routers/designs.py     # extend: GET /designs/{id}/objectives (reverse lookup,
                                    #   opens a new strategy-scoped session)
src/adp/application/router.py      # extend: GET /applications/{id}/objectives (same pattern)

src/adp/store/migrations/versions/028_objective_design_application_links.py   # new

tests/unit/strategy/test_strategy_store.py            # extend (or a focused sibling file)
tests/unit/strategy/test_strategy_models.py            # extend
tests/contract/test_strategy_api_contract.py           # extend
tests/contract/test_designs_api_contract.py             # extend (reverse lookup)
tests/contract/test_application_api_contract.py          # extend (reverse lookup)

web/src/api/strategy.ts                     # extend: design_ids/application_ids types,
                                              # 8 new hooks
web/src/strategy/ObjectiveDesignLinkEditor.tsx        # new — mirrors
                                              #   ObjectiveCapabilityLinkEditor.tsx
web/src/strategy/ObjectiveApplicationLinkEditor.tsx   # new — same pattern
web/src/strategy/ObjectiveDetail.tsx          # extend: wire in both new editors
web/src/canvas-v2/C4DesignView.tsx            # extend: small collapsible "Traceability"
                                              #   section showing linked objectives
                                              #   (read-only reverse lookup)
web/src/application/ObjectiveLinksPanel.tsx    # new — mirrors CapabilityLinksEditor.tsx's
                                              #   read+link pattern
web/src/application/ApplicationDetail.tsx      # extend: wire in new panel/section
```

**Structure Decision**: No new package or submodule. Per Ground-Truth Correction 4 in spec.md, this
extends the existing `adp.strategy` `models.py`/`store.py`/`router.py` trio directly (currently 1,596
lines combined, well under the ~2,847-line threshold that triggered the `adp.business`→`adp.strategy`
split, and well under ADP-d8u.6's own threshold for choosing a submodule for a *new concept* —
these two tables are the exact same shape as two tables already in these files, not a new concept).
The two reverse-lookup `GET` endpoints live in the *owning* package's existing router
(`adp.api.routers.designs`, `adp.application.router`), per the established "traceability reads are
exposed from both sides, each in its own package" convention already used for
`capability_design_links`/`value_stream_design_links`.

## Complexity Tracking

*No violations — table intentionally empty.*
