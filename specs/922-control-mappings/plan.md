# Implementation Plan: Control Mappings (Traceability Links) — COMPLY-02

**Branch**: `922-control-mappings` | **Date**: 2026-08-18 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/922-control-mappings/spec.md`

## Summary

Build the traceability link COMPLY-01's Control registry exists to support: a `Control` becomes
attributable to the Capability, Application, Design, Pattern (knowledge item), or estate-wide obligation it
actually governs, each mapping carrying its own `compliance_status`, evidence pointer, and assessment
metadata. Three structural decisions the source bundle explicitly left open were resolved directly with the
user during `/speckit.specify` (Clarification Session 2026-08-18): five parallel, fully FK-enforced mapping
tables (four entity-targeted + one estate-wide, not one polymorphic table); estate-wide obligations are
in scope; and a mapping's read visibility inherits its target's own existing gate (Application-targeted
mappings require `READ_APPLICATION_GOVERNANCE`, everything else stays ungated). Writes and the
Control-forward lookup live in `adp.compliance` (COMPLY-01's own package, extended not replaced); the four
reverse-lookup endpoints live on each target's own existing router, mirroring ADP-d8u.2's precedent for
cross-package reverse lookups. Zero new runtime packages either side; one new migration (`033`).

## Technical Context

**Language/Version**: Python 3.12 (backend); TypeScript 5.x + React 18 (frontend) — both existing stacks
**Primary Dependencies**: FastAPI ≥ 0.111, SQLAlchemy 2 async (Core), asyncpg, Alembic, Pydantic v2, React 18, TanStack Query v5 — all existing stack; zero new packages
**Storage**: PostgreSQL 16 — five new tables (`control_capability_mapping`, `control_application_mapping`, `control_design_mapping`, `control_pattern_mapping`, `control_organization_mapping`) via migration `033` (down_revision `032` — research.md D8); `ON DELETE CASCADE` on every FK leg (both `control_id` and each target leg); composite PKs on the four entity-targeted tables, single-column PK on the estate-wide table (research.md D1); named `CHECK` constraints on `compliance_status` per table
**Testing**: pytest (unit — no DB, store/model validation incl. upsert-not-duplicate semantics; contract — schema/authz shape; integration — testcontainers PostgreSQL for cascade + cross-table reverse-lookup behavior); Vitest (frontend unit/component, if a UI surface ships in this pass — see Assumptions)
**Target Platform**: Linux server (API) + browser (existing web canvas)
**Project Type**: Web application (existing `src/adp` backend + `web/` frontend)
**Performance Goals**: standard interactive-CRUD latency; the Control-forward lookup (`GET .../mappings`) is a 5-table UNION scoped by one `control_id`, each a PK-prefix (or PK-exact, for the estate-wide table) scan — no N+1
**Constraints**: ART-XIII typed contracts (`extra="forbid"` on every boundary model); migration owns FK/PK/CHECK constraints, store-layer `Table()` objects DML-only (existing convention); `adp.compliance` imports zero other domain packages — target existence/kind validation goes through same-physical-DB mirror tables (research.md D4), not cross-package store calls
**Scale/Scope**: dozens of Controls × up to a handful of mapped targets each in the near term; no pagination added to the forward/reverse lookups in this pass (matches COMPLY-01's own registry-scale assumption — revisit if a Control or entity ever accumulates hundreds of mappings)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **ART-I (SDD mandatory)**: ✅ this plan follows spec.md, which already resolved its 3 open
  `[NEEDS CLARIFICATION]` markers directly with the user before planning began.
- **ART-II (Model is the single source of truth)**: ✅ `compliance_status` is written once, here, as a
  typed row; no separate hand-maintained rollup exists yet (COMPLY-03/04, out of scope) to drift from it.
- **ART-III / ART-XIII (Machine-readable / Typed contracts)**: ✅ new Pydantic v2 models (`ComplianceStatus`,
  `MappingTargetType`, `ControlMapping`, `ControlMappingWrite`), `extra="forbid"`; OpenAPI contract
  generated, not hand-maintained. Same non-`adp-generate`-pipeline category as COMPLY-01 (a standalone typed
  registry, not part of `ArchitectureDescription`'s JSON-Schema generation).
- **ART-IV (TDD)**: ✅ contract + unit tests precede handlers; the upsert-not-duplicate guarantee (FR-008)
  and the pattern-kind check (D5) both get dedicated unit tests before wiring into the router, matching the
  project's validate-before-implement convention (COMPLY-01's cycle/cross-framework checks are the direct
  precedent for this class of pre-router validation testing).
- **ART-V (Security by Design)**: ✅ threat model already in spec.md; writes reuse the existing
  `WRITE_COMPLIANCE` permission (no `PERMISSIONS_VERSION` bump needed — COMPLY-01 already granted it to the
  three architect personas and the `/api/v1/compliance/` prefix rule already covers every route this spec
  adds under that prefix); the one new authz surface is the per-route `READ_APPLICATION_GOVERNANCE` gate on
  Application-targeted mapping reads, reusing an existing `ActionType` via the existing
  `require_action_dep` helper — no new `ActionType`, no `PERMISSIONS_VERSION` bump.
- **ART-VI (Observability)**: N/A beyond baseline — no AI/LLM step in this feature; standard structured
  request logging already covers every route via the existing FastAPI middleware.
- **ART-VII (Grounded AI)**: N/A — no AI generation involved.
- **ART-VIII (Human-in-the-loop)**: N/A — every mapping write is already a direct, attributable human
  action gated by `WRITE_COMPLIANCE` (spec.md FR-015 explicitly rules out a proposal/confirm workflow for
  this pass).
- **ART-IX (Provenance/Audit)**: `created_at` recorded on every mapping (no `updated_at` — spec.md User
  Story 2 Acceptance Scenario 1 explicitly says the prior status is not separately preserved, so there is
  no "last modified" fact beyond the row's current values); no `audit_entries` write, matching COMPLY-01's
  own confirmed precedent that direct human CRUD on registry/traceability domains does not write to the
  append-only audit trail.
- **ART-XI (Traceability)**: ✅ this is the traceability link itself — COMPLY-01's spec.md explicitly named
  this dependency. Referential integrity is DB-FK-enforced on every leg (research.md D1), and the
  Pattern-target `kind` check (D5) closes the one gap a plain FK can't express.
- **ART-XV (Governed schema evolution)**: ✅ additive-only migration `033`; no `PERMISSIONS_VERSION` bump
  (no new `ActionType` introduced — see ART-V above).

**Result**: PASS — no violations; Complexity Tracking not required. Every design choice traces to an
existing, directly-confirmed precedent (`application_capability_links`' composite-PK/CASCADE shape,
`adp.strategy.store`'s mirror-table existence-check idiom, `adp.store.store.DesignStore.save()`'s select-then-branch upsert idiom,
`application/router.py`'s `require_action_dep` sensitive-read gate, ADP-d8u.2's cross-package reverse
lookup) rather than inventing a new pattern.

## Project Structure

### Documentation (this feature)

```text
specs/922-control-mappings/
├── plan.md              # This file
├── research.md          # Phase 0 — D1–D8 decisions (table shape, read gating, upsert, existence
│                         #   validation, pattern-kind check, manual delete, route ownership, migration #)
├── data-model.md         # Phase 1 — DDL + Pydantic models + store function inventory
├── contracts/
│   └── compliance-mappings-api.md  # Phase 1 — REST contract (writes/forward-lookup + 4 reverse-lookups)
├── quickstart.md         # Phase 1 — integration scenarios covering every acceptance scenario + edge case
├── checklists/
│   └── requirements.md   # Spec quality checklist (passed after 3 clarifications resolved)
└── tasks.md              # Phase 2 output (/speckit.tasks — not created here)
```

### Source Code Changes

```text
src/adp/compliance/            # EXISTING package (COMPLY-01) — extended, not replaced
├── models.py                  # + ComplianceStatus, MappingTargetType, ControlMapping(+Write/ListResponse);
│                               #   + ControlNotFoundError, MappingTargetNotFoundError,
│                               #   InvalidPatternTargetError, MappingNotFoundError
├── store.py                   # + 5 mapping Table()s; + 4 narrow mirror Table()s (capabilities/
│                               #   applications/designs/knowledge_items, id-only or id+kind — research.md D4);
│                               #   + get_control, capability_exists, application_exists, design_exists,
│                               #   get_knowledge_item_kind; + upsert_*/delete_*/list_mappings_for_* per
│                               #   target type (data-model.md)
└── router.py                  # + PUT/DELETE .../mappings/{capabilities|applications|designs|patterns}/{id},
                                #   PUT/DELETE .../mappings/organization,
                                #   GET .../controls/{control_id}/mappings (filters Application rows per D2)

src/adp/business/router.py      # + GET /capabilities/{cap_id}/compliance-mappings (imports adp.compliance.store)
src/adp/application/router.py   # + GET /applications/{app_id}/compliance-mappings,
                                 #   dependencies=[Depends(_require_governance_read)] (existing dep, reused)
src/adp/api/routers/            # (designs router — exact module confirmed at task time)
└── designs.py                  # + GET /designs/{design_id}/compliance-mappings
src/adp/api/routers/knowledge.py # + GET /knowledge/{item_id}/compliance-mappings

src/adp/store/migrations/versions/
└── 033_control_mappings.py     # 5 tables, all constraints/indexes (data-model.md)

web/src/api/compliance.ts       # + TanStack Query hooks for mapping CRUD + both lookup directions
web/src/compliance/
└── ControlMappingsEditor.tsx   # NEW shared component (create/update/delete a mapping, target-type
                                 #   picker, status/evidence/assessed-by fields) — one implementation
                                 #   reused everywhere a mapping is edited, mirroring useLinkFeedback's
                                 #   own extract-once-reuse-five-times precedent (ADP-c44) rather than a
                                 #   one-off per target type
web/src/compliance/ControlTree.tsx  # extended: each control row gets a "Mappings" affordance opening
                                     #   ControlMappingsEditor scoped to that control (all 5 target shapes)
web/src/business/CapabilityNode.tsx # extended: reverse-lookup mapped-controls list embedded inline in
                                     #   the expanded row, alongside the existing DesignLinkEditor — no
                                     #   separate Capability detail screen exists (043-capability-heat-map
                                     #   research.md Decision 3 precedent), so this is the row's own home
web/src/application/ApplicationDetail.tsx # extended: reverse-lookup mapped-controls list added as a new
                                           #   section, gated by the same READ_APPLICATION_GOVERNANCE-backed
                                           #   query the existing Governance section already uses
                                           # Design and Pattern reverse-lookup UI placement is an OPEN
                                           # DECISION for /speckit.tasks — neither domain has an established
                                           # single-entity detail screen to embed into (Design's closest
                                           # analog, governance/ComplianceTab.tsx, is reserved for COMPLY-04's
                                           # validation-exceptions rollup, a DIFFERENT "compliance" concept
                                           # from this spec's RegulatoryFramework/Control domain — confirmed
                                           # by reading it directly; must not be conflated or touched here).
                                           # The reverse-lookup API for both (GET /designs/{id}/compliance-
                                           # mappings, GET /knowledge/{id}/compliance-mappings) ships either
                                           # way per FR-012; only their UI surfacing is deferred pending a
                                           # placement decision.

tests/
├── contract/
│   └── test_compliance_mappings_api.py     # schema, authz-shape (writes gated, App reads gated)
├── unit/
│   └── compliance/
│       └── test_mapping_store.py           # upsert-not-duplicate (FR-008), pattern-kind check (D5),
│                                            #   cascade-on-control/target-delete behavior (mocked/logic-level)
├── integration/
│   └── test_compliance_mappings_api.py     # testcontainers PostgreSQL: real cascade delete, real
│                                            #   cross-table reverse lookup, real concurrent-upsert race
└── authz/
    └── test_enforcement.py                 # extended: READ_APPLICATION_GOVERNANCE gate on the new
                                             #   Application-targeted read routes; forward-lookup filtering
```

**Structure Decision**: Extends the existing `adp.compliance` package (models/store/router) rather than a
new package — COMPLY-02 is explicitly the next spec in the same bundle building directly on COMPLY-01's
entities, not a new domain. Four *reverse-lookup* routes land on each target's own existing router
(business/application/designs/knowledge) per research.md D7, each a small additive endpoint importing
`adp.compliance.store` for a same-physical-DB query — mirroring ADP-d8u.2's own precedent exactly. A UI
ships in this pass (confirmed with the user — COMPLY-01 itself shipped API+UI together, and that precedent
is followed here): it extends the existing `web/src/compliance/` surface (a new shared
`ControlMappingsEditor.tsx`, reused everywhere a mapping is created/edited/deleted, mirroring
`useLinkFeedback`'s extract-once precedent) plus small additive sections on `CapabilityNode.tsx` and
`ApplicationDetail.tsx` for reverse-lookup display. Design and Pattern reverse-lookup UI placement is an
open decision left for `/speckit.tasks` (see Project Structure above) — their APIs ship regardless.

## Phase 0 — Research & Decisions

Captured in full in [research.md](./research.md). Key decisions:

1. **Table shapes** (D1): five tables — four composite-PK entity-targeted (`control_capability_mapping`,
   `control_application_mapping`, `control_design_mapping`, `control_pattern_mapping`) plus one
   single-column-PK estate-wide table (`control_organization_mapping`), every FK leg `ON DELETE CASCADE`.
2. **Read gating** (D2): Application-targeted mapping reads require `READ_APPLICATION_GOVERNANCE` via
   `require_action_dep` (reused, not new); the Control-forward lookup filters out Application rows for a
   caller lacking that permission rather than rejecting the whole response.
3. **Upsert mechanism** (D3, revised during implementation): select-then-branch (UPDATE if a row exists,
   else INSERT, self-healing a concurrent-write race by falling back to UPDATE on a unique-violation),
   matching `adp.store.store.DesignStore.save()`'s own idiom. The originally-planned `ON CONFLICT DO
   UPDATE` turned out not to be SQLite-contract-test-portable (`postgresql.insert()` cannot compile
   against the SQLite fixture every compliance contract test uses) — caught by running the contract
   test, not assumed from the plan; see research.md D3 for the full correction.
4. **Existence validation** (D4): narrow same-physical-DB mirror tables inside `adp.compliance.store`,
   extending `adp.strategy.store`'s own `design_exists`/`application_exists` idiom — zero cross-package
   imports.
5. **Pattern-kind validation** (D5): app-layer check against the knowledge_items mirror table's `kind`
   column — a plain FK can't express "and kind == 'pattern'".
6. **Manual mapping deletion** (D6): `DELETE` endpoints added for all five shapes, though not an explicit
   FR — CRUD completeness matching every other join table's unlink endpoint in the platform.
7. **Route ownership** (D7): writes + forward-lookup in `adp.compliance.router`; reverse-lookups on each
   target's own router, mirroring ADP-d8u.2.
8. **Migration number** (D8): `033`, `down_revision "032"` — confirmed against the real chain head.

## Implementation Phases

> One phase per user story, in priority order, per the spec's own P1/P2/P3 slicing. Each phase is
> independently shippable and demonstrable.

### Phase 1 — Setup
Migration `033` (all five tables, every constraint/index); `adp.compliance.models`/`store.py` additions
(enums, `ControlMapping` family, typed exceptions, mirror tables, `get_control`/`*_exists`/
`get_knowledge_item_kind`). No authz plumbing changes needed for writes (existing `WRITE_COMPLIANCE` prefix
rule already covers the new routes); the one new dependency wiring is reusing
`require_action_dep(READ_APPLICATION_GOVERNANCE)` on two new routes.

### Phase 2 — US1 (P1, MVP): Map a control to the entity it governs
`upsert_capability_mapping`/`upsert_application_mapping`/`upsert_design_mapping`/`upsert_pattern_mapping`/
`upsert_organization_mapping` in store.py; the five `PUT .../mappings/...` router endpoints;
`GET .../controls/{control_id}/mappings` forward lookup (with the Application-row filter from D2 already
in place, since a mapping can be created targeting an Application from day one). Frontend: new
`ControlMappingsEditor.tsx` wired into `ControlTree.tsx`'s per-control "Mappings" affordance (create only,
to start). **Ships the core traceability link alone** — a Control can be mapped to any of its five target
shapes and the mapping is retrievable from the Control's own side, per the spec's own "delivers value on
its own" framing.

### Phase 3 — US2 (P2): Update a mapping's assessment over time
No new endpoints — US2 is exercised entirely through the same `PUT` routes from Phase 2 (upsert doubles as
both create and update per D3). This phase is really "prove FR-007/FR-008/FR-010 hold" — dedicated unit
tests for re-mapping-updates-in-place (never duplicates) and independent-field-update (evidence_ref changes
without touching compliance_status), plus the corresponding quickstart Scenario 5. Frontend:
`ControlMappingsEditor.tsx` gains edit-in-place for an existing mapping (reusing the same upsert call).

### Phase 4 — US3 (P3): Trace compliance coverage from either direction
The four reverse-lookup endpoints (`GET /capabilities/{id}/compliance-mappings`,
`GET /applications/{id}/compliance-mappings` gated, `GET /designs/{id}/compliance-mappings`,
`GET /knowledge/{id}/compliance-mappings`) plus `list_mappings_for_capability`/`_application`/`_design`/
`_pattern` in store.py. Application route gets `_require_governance_read` (already defined in that router
from APM US7 — reused, not redefined). Frontend: reverse-lookup sections added to `CapabilityNode.tsx`
(inline row) and `ApplicationDetail.tsx` (new section); Design/Pattern UI placement resolved at
`/speckit.tasks` time (Project Structure note above) — their reverse-lookup APIs ship in this phase
regardless of where/whether a UI surfaces them yet.

### Phase 5 — Polish
`DELETE .../mappings/...` endpoints for all five shapes (D6), wired into `ControlMappingsEditor.tsx` as a
remove action; full integration test suite against testcontainers PostgreSQL (real
cascade-on-Control-delete, real cascade-on-target-delete, real concurrent-upsert race behavior, real
cross-table forward lookup); authz completeness tests extended; Vitest coverage for
`ControlMappingsEditor.tsx` and both extended detail components; `quickstart.md` scenarios run end-to-end
against a live local stack.

## Complexity Tracking

*No violations — table not needed.*

## Open decision carried into `/speckit.tasks`

- **Design and Pattern reverse-lookup UI placement** (confirmed scope: UI ships this pass — see Structure
  Decision above). Capability and Application each have an established home to embed into
  (`CapabilityNode.tsx`'s inline row; `ApplicationDetail.tsx`'s detail page). Design and Pattern do not:
  Design has no single-entity detail screen today (only the diagram editor's element-level
  `InspectionPanel.tsx`), and the one existing screen with "compliance" in its name
  (`governance/ComplianceTab.tsx`) is confirmed — by reading it directly — to be COMPLY-04's future home
  for validation-*exception* rollups (a different "compliance" concept, LLM-as-Judge findings, not this
  spec's `RegulatoryFramework`/`Control` domain) and must not be conflated with or repurposed for this
  spec. Their reverse-lookup APIs (FR-012) ship in Phase 4 regardless; `/speckit.tasks` should decide
  where — or whether — a UI surfaces them in this pass versus a follow-on.
