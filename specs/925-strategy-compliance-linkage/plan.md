# Implementation Plan: Strategy Domain Linkage — COMPLY-05

**Branch**: `925-strategy-compliance-linkage` | **Date**: 2026-08-19 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/925-strategy-compliance-linkage/spec.md`

## Summary

Link the Compliance domain (COMPLY-01–04: `RegulatoryFramework`/`Control`/`ControlMapping`/derived
status/rollups) back to the existing Strategy domain, via two independent traceability links:
`ObjectiveControlMapping` ("why does this objective exist" — a bare link from a `StrategicObjective` to a
`Control`) and `InitiativeControlMapping` ("the remediation loop" — a `StrategyInitiative` linked to a
specific, already-assessed `ControlMapping`, so a `compliance_status` change becomes attributable to real
closed work). The bundle's third, lower-priority link (`ThemeFrameworkMapping`) was explicitly deferred by
the user during `/speckit.specify` and is tracked as bead `ADP-1ox`, not built here.

Two decisions this plan resolves that the source bundle left structurally underspecified: (1) the bundle
described `InitiativeControlMapping` as referencing one `control_mapping_id`, but COMPLY-02 actually
implemented `ControlMapping` as five separate physical tables with no synthetic ID — resolved by mirroring
COMPLY-02's own five-parallel-tables shape one level up, each with a composite FK against the target
table's composite PK (research.md D1); (2) package placement — both new link types live in `adp.strategy`
(extending the exact pattern ADP-d8u.2 already established for "Strategy reaches into a foreign domain"
via `objective_design_links`/`objective_application_links`), not `adp.compliance`, with reverse-lookup
routes on `adp.compliance.router` importing `adp.strategy.store`/`adp.strategy.initiatives` (research.md
D2) — the same cross-package-import direction ADP-d8u.2 already established via `designs.py` importing
`adp.strategy.store`. Zero new `ActionType`, zero `PERMISSIONS_VERSION` bump — both link types reuse
`WRITE_BUSINESS_ARCH`, held by the identical persona set as `WRITE_COMPLIANCE`. One new migration (`034`,
six tables).

## Technical Context

**Language/Version**: Python 3.12 (backend); TypeScript 5.x + React 18 (frontend) — both existing stacks
**Primary Dependencies**: FastAPI ≥ 0.111, SQLAlchemy 2 async (Core), asyncpg, Alembic, Pydantic v2, React
18, TanStack Query v5 — all existing stack; zero new packages
**Storage**: PostgreSQL 16 — six new tables via migration `034` (down_revision `033`): `objective_control_links`
(composite PK `(objective_id, control_id)`) and five parallel `initiative_control_{capability,application,
design,pattern,organization}_mapping` tables (research.md D1), each with a composite FK against its
corresponding `control_*_mapping` table's own composite PK (migration `033`). `ON DELETE CASCADE` on every
FK leg on every table — no new columns on any existing table.
**Testing**: pytest (unit — no DB, store/link-logic validation incl. duplicate-link and
missing-`ControlMapping`-target 404 semantics; contract — schema/authz shape against a SQLite fixture
wiring `adp.strategy`+`adp.compliance` tables together, mirroring 922's own two-domain fixture precedent;
integration — testcontainers PostgreSQL for real composite-FK cascade behavior across both directions);
Vitest (frontend unit/component for the two new link editors)
**Target Platform**: Linux server (API) + browser (existing web canvas)
**Project Type**: Web application (existing `src/adp` backend + `web/` frontend)
**Performance Goals**: standard interactive-CRUD latency; an Initiative's `control_mappings` read is a
5-table UNION scoped by one `initiative_id`, each a PK-prefix scan (mirrors COMPLY-02's own forward-lookup
performance profile, research.md D1) — no N+1
**Constraints**: ART-XIII typed contracts (`extra="forbid"` on every boundary model); migration owns
FK/PK constraints, store-layer `Table()` objects DML-only (existing convention); `adp.strategy` continues
importing zero other domain packages at the store layer — Control/ControlMapping existence and live-status
reads go through same-physical-DB mirror tables (research.md D2/D3), not a cross-package store call
**Scale/Scope**: a handful of Objective-Control links and Initiative-mapping links per Objective/Initiative
in the near term; no pagination added (matches every prior COMPLY-0x spec's own registry-scale assumption)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **ART-I (SDD mandatory)**: ✅ spec.md's one genuine open question (`ThemeFrameworkMapping` scope) and
  one ground-truth question (Initiative → Objective optionality) were both resolved directly with the
  user/by code inspection before this plan began — zero `[NEEDS CLARIFICATION]` markers remained.
- **ART-II (Model is the single source of truth)**: ✅ the entire point of `InitiativeControlMapping`'s
  design (research.md D3) is that the status shown through a link is *never* a separately stored value —
  it is read live off the `ControlMapping` row on every request, so there is nothing that can drift.
- **ART-III / ART-XIII (Machine-readable / Typed contracts)**: ✅ new Pydantic v2 models
  (`ObjectiveControlLinkCreate`, `ControlMappingRef`, plus a new `ControlMappingNotFoundError`),
  `extra="forbid"`; `MappingTargetType`/`ComplianceStatus` reused from `adp.compliance.models`, not
  redefined. OpenAPI contract generated, not hand-maintained.
- **ART-IV (TDD)**: ✅ contract + unit tests precede handlers; the "link an Initiative to a `ControlMapping`
  that doesn't exist yet → 404, not auto-create" rule and the live-status-via-JOIN guarantee (FR-008) both
  get dedicated unit tests before wiring into the router, matching COMPLY-01's own cycle-check precedent
  for pre-router validation testing.
- **ART-V (Security by Design)**: ✅ threat model already in spec.md; writes reuse the existing
  `WRITE_BUSINESS_ARCH` permission (no `PERMISSIONS_VERSION` bump — already held identically to
  `WRITE_COMPLIANCE` by the three architect personas plus Platform Admin, and the `/api/v1/strategy/`
  prefix rule already covers every new route this spec adds under that prefix); the one new authz surface
  is the reverse-lookup route's inherited `READ_APPLICATION_GOVERNANCE` gate (spec.md FR-013), reusing an
  existing `ActionType` via the existing `require_action_dep`/`_require_governance_read` helper — no new
  `ActionType`.
- **ART-VI (Observability)**: N/A beyond baseline — no AI/LLM step in this feature; standard structured
  request logging already covers every route via the existing FastAPI middleware, matching every prior
  COMPLY-0x spec's own posture.
- **ART-VII (Grounded AI)**: N/A — no AI generation involved.
- **ART-VIII (Human-in-the-loop)**: N/A — every link write is already a direct, attributable human action
  gated by `WRITE_BUSINESS_ARCH`; spec.md FR-009 explicitly rules out any automatic-Initiative-creation
  trigger in this pass.
- **ART-IX (Provenance/Audit)**: `created_at` recorded on every link row; no `audit_entries` write,
  matching COMPLY-01/02's own confirmed precedent that direct human CRUD on registry/traceability domains
  does not write to the append-only audit trail.
- **ART-XI (Traceability)**: ✅ this spec *is* the traceability link between two previously-disconnected
  domains — an element (`StrategicObjective`/`StrategyInitiative`) gaining a satisfies-adjacent relationship
  to the regulatory obligation that motivates or is remediated by it. Referential integrity is DB-FK-
  enforced on every leg, including the composite FK against `ControlMapping`'s own composite PK
  (research.md D1) — the harder case a plain single-column FK couldn't have expressed.
- **ART-XV (Governed schema evolution)**: ✅ additive-only migration `034`; no `PERMISSIONS_VERSION` bump
  (no new `ActionType` — see ART-V above).

**Result**: PASS — no violations; Complexity Tracking not required. Every design choice traces to an
existing, directly-confirmed precedent (COMPLY-02's own five-tables-not-polymorphic resolution applied one
level up; ADP-d8u.2's mirror-table/cross-package-reverse-lookup idiom; `adp.strategy.store`'s existing
`DuplicateLinkError`/`LinkNotFoundError` bare-link pattern) rather than inventing a new one.

## Project Structure

### Documentation (this feature)

```text
specs/925-strategy-compliance-linkage/
├── plan.md              # This file
├── research.md          # Phase 0 — D1–D5 decisions (target-addressing gap, package placement,
│                         #   live-status JOIN, API addressing, duplicate-link handling)
├── data-model.md         # Phase 1 — DDL (6 tables) + Pydantic models + store function inventory
├── contracts/
│   └── strategy-compliance-links-api.md  # Phase 1 — REST contract (both link types + 2 reverse lookups)
├── quickstart.md         # Phase 1 — integration scenarios covering every acceptance scenario + edge case
├── checklists/
│   └── requirements.md   # Spec quality checklist (passed with zero clarification markers)
└── tasks.md              # Phase 2 output (/speckit.tasks — not created here)
```

### Source Code Changes

```text
src/adp/strategy/               # EXISTING package — extended, not replaced
├── models.py                   # + ObjectiveControlLinkCreate; StrategicObjective gains control_ids
├── store.py                    # + _objective_control_links Table(); + _controls_mirror,
│                                #   5x control_*_mapping read-only mirror Table()s (incl. status columns
│                                #   -- research.md D3); + control_exists, link_objective_control,
│                                #   unlink_objective_control, list_objectives_for_control (reverse,
│                                #   called from adp.compliance.router)
├── initiatives.py               # + ControlMappingRef, ControlMappingNotFoundError;
│                                #   StrategyInitiative gains control_mappings; + 5x
│                                #   _initiative_control_*_mapping Table()s; + link_/unlink_
│                                #   initiative_control_mapping, _linked_control_mappings (live JOIN),
│                                #   list_initiatives_for_control_mapping (reverse, called from
│                                #   adp.compliance.router); + ControlMappingNotFoundError
└── router.py                    # + POST/DELETE .../objectives/{id}/controls[/{control_id}],
                                  #   POST/DELETE .../initiatives/{id}/control-mappings/{target_type}/
                                  #   {control_id}[/{target_id}] (both under the existing
                                  #   WRITE_BUSINESS_ARCH prefix rule)

src/adp/compliance/router.py     # + GET /controls/{control_id}/objectives (imports adp.strategy.store
                                  #   via new _get_strategy_session dep, mirrors designs.py's own
                                  #   _get_strategy_session precedent exactly);
                                  # + GET /controls/{control_id}/mappings/{target_type}/{target_id}/
                                  #   initiatives (imports adp.strategy.initiatives; 403 if target_type
                                  #   == application and caller lacks READ_APPLICATION_GOVERNANCE)

src/adp/store/migrations/versions/
└── 034_strategy_compliance_links.py   # 6 tables, all constraints/indexes (data-model.md)

web/src/api/strategy.ts          # + TanStack Query hooks: useLinkObjectiveControl/useUnlink...,
                                  #   useLinkInitiativeControlMapping/useUnlink...
web/src/strategy/
├── ObjectiveControlLinkEditor.tsx   # NEW — mirrors ObjectiveDesignLinkEditor.tsx's exact shape
│                                    #   (useLinkFeedback, pick-a-Control search/select, list + remove)
├── ObjectiveDetail.tsx              # extended: one more "Linked Controls" section, 6th of its kind
├── InitiativeControlMappingEditor.tsx  # NEW — mirrors InitiativeObjectiveLinkEditor.tsx's shape; each
│                                        #   row shows target + live compliance_status badge
└── InitiativeList.tsx               # extended: InitiativeEditForm gains the new editor, alongside the
                                      #   existing InitiativeObjectiveLinkEditor (no dedicated Initiative
                                      #   detail page exists — 916's own established precedent)

web/src/compliance/ControlTree.tsx  # extended: each control row gains a read-only "Linked Objectives"
                                     #   line (GET .../controls/{id}/objectives) alongside the existing
                                     #   ControlMappingsEditor; each mapping row inside
                                     #   ControlMappingsEditor gains a read-only "Linked Initiatives" line
                                     #   (GET .../mappings/{target_type}/{target_id}/initiatives)

tests/
├── contract/
│   └── test_strategy_compliance_links_api.py  # schema, authz-shape (writes gated, reverse-lookup
│                                               #   Application-targeted gate) — SQLite fixture wiring
│                                               #   strategy + compliance tables (mirrors 922's own
│                                               #   two-domain fixture)
├── unit/
│   └── strategy/
│       └── test_control_links.py              # duplicate-link 409, missing-ControlMapping-target 404,
│                                               #   live-status-via-JOIN (mocked/logic-level)
├── integration/
│   └── test_strategy_compliance_links_api.py  # testcontainers PostgreSQL: real composite-FK cascade
│                                               #   (Control delete → Objective link gone; ControlMapping
│                                               #   delete → Initiative link gone), real reverse lookups
└── authz/
    └── test_enforcement.py                    # extended: READ_APPLICATION_GOVERNANCE gate on the new
                                                 #   reverse-lookup route (REVIEWER-role denial case)
```

**Structure Decision**: Extends the existing `adp.strategy` package (models.py/store.py/initiatives.py/
router.py) and `adp.compliance.router` exactly as ADP-d8u.2 and COMPLY-02 already did for their own
cross-domain links — no new package, no new top-level frontend directory. One new migration (`034`).

## Complexity Tracking

*No Constitution Check violations — this section is not applicable.*
