# Tasks: Application Portfolio Management

**Feature**: ADP-SPEC-038 | **Branch**: `038-application-portfolio-management`
**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md) · **Data model**: [data-model.md](./data-model.md)

## Format: `[ID] [P?] [Story] Description`

- **[P]** = parallelizable (distinct file, no dependency on an incomplete task).
- **[US#]** = user-story phase task. Setup / Foundational / Polish carry no story label.
- Tests are **MANDATORY** (ART-IV): each story's contract/unit tests precede its implementation.

## Path Conventions

Backend `src/adp/application/{models,store,router,rationalization}.py`, migrations `src/adp/store/migrations/versions/`, authz `src/adp/authz/{permissions,roles,enforcement}.py`, tests `tests/{contract,unit,integration}/`, web `web/src/application/`.

> **File-contention note**: `models.py`, `store.py`, and `router.py` are touched by almost every story, so tasks that edit them are **sequential** (not `[P]`) even across stories. Migrations, test files, and web panels are distinct per story and marked `[P]`. Migrations also **chain** (012→…→021), so migration tasks run in number order regardless of `[P]`.

---

## Phase 1: Setup (Shared Infrastructure)

- [ ] T001 [P] Add shared APM enums/Literals (`LifecycleStatus`, `HostingModel`, `DataClassification`, `Disposition`, `Score15 = Annotated[int, Field(ge=1, le=5)]`) in src/adp/application/models.py
- [ ] T002 [P] Add APM test fixtures/factories (application + risk/cost/contract/quality helpers) in tests/application/conftest.py

## Phase 2: Foundational (Blocking Prerequisites)

> Blocks the sensitive-category stories US3 / US4 / US7. Defined once here to avoid three separate `PERMISSIONS_VERSION` bumps.

- [ ] T003 Add sensitive-category permission actions (`READ/WRITE_APPLICATION_COST`, `_RISK`, `_GOVERNANCE`) and bump `PERMISSIONS_VERSION` in src/adp/authz/permissions.py
- [ ] T004 [P] Grant the new APM actions to appropriate roles in src/adp/authz/roles.py
- [ ] T005 Register APM route→action mappings (sensitive endpoints) in src/adp/authz/enforcement.py

---

## Phase 3: User Story 1 - Business-value scores + TIME rationalization view (Priority: P1) 🎯 MVP

**Goal**: Add `business_value`/`business_criticality` to applications and deliver the business-value × technical-health (TIME) quadrant.
**Independent test**: Score apps, retrieve `GET /api/v1/applications/rationalization`, confirm correct quadrant placement and that unassessed apps are listed separately (never placed).

### Tests for User Story 1 (MANDATORY — ART-IV)

- [ ] T006 [P] [US1] Contract test: score update validation (1–5, NULL allowed) + audit written, in tests/contract/test_apm_scores_api.py
- [ ] T007 [P] [US1] Unit test: rationalization quadrant mapping (invest/migrate/tolerate/eliminate) + unassessed exclusion, in tests/unit/test_rationalization.py

### Implementation for User Story 1

- [ ] T008 [US1] Alembic migration 012: add `business_value`, `business_criticality` (SMALLINT NULL, CHECK 1..5) to `applications`, in src/adp/store/migrations/versions/012_apm_business_value.py
- [ ] T009 [US1] Extend Application read/create/update models with the two scores, in src/adp/application/models.py
- [ ] T010 [US1] Store: persist/read scores with audit write, in src/adp/application/store.py
- [ ] T011 [US1] Rationalization projection (single-pass query: `business_value` × `health_score` → quadrant; unassessed list), in src/adp/application/rationalization.py
- [ ] T012 [US1] Endpoints: update scores + `GET /api/v1/applications/rationalization`, in src/adp/application/router.py
- [ ] T013 [P] [US1] Web TIME-quadrant view, in web/src/application/RationalizationView.tsx
- [ ] T014 [US1] Regenerate JSON Schema (`adp-generate`) and confirm drift gate passes

**Checkpoint**: MVP — the rationalization plot works standalone.

---

## Phase 4: User Story 2 - Identity & ownership (Priority: P2)

**Goal**: Owning business unit, business/technical owner split, explicit lifecycle status.
**Independent test**: Set BU + owners + lifecycle; filter registry by BU and by lifecycle status.

### Tests for User Story 2 (MANDATORY — ART-IV)

- [ ] T015 [P] [US2] Contract test: identity fields round-trip, BU + lifecycle filters, audit, in tests/contract/test_apm_identity_api.py

### Implementation for User Story 2

- [ ] T016 [US2] Alembic migration 013: `owning_business_unit`, `business_owner`, `technical_owner`, `lifecycle_status` (+ CHECK + indexes) on `applications`, in src/adp/store/migrations/versions/013_apm_identity.py
- [ ] T017 [US2] Extend Application models with identity fields, in src/adp/application/models.py
- [ ] T018 [US2] Store: identity persistence + filters (by BU, lifecycle_status) + audit, in src/adp/application/store.py
- [ ] T019 [US2] Endpoints: identity update + filtered list, in src/adp/application/router.py
- [ ] T020 [P] [US2] Web identity panel + filters, in web/src/application/ApplicationForm.tsx

---

## Phase 5: User Story 3 - Risk & compliance register (Priority: P3)

**Goal**: `application_risk` (security posture, data classification, regulatory tags, DR/BC, EOL/EOS dates) with sensitive-read authz.
**Independent test**: Record risk incl. past EOS; query out-of-support; confirm a user without `READ_APPLICATION_RISK` cannot read the fields.

### Tests for User Story 3 (MANDATORY — ART-IV)

- [ ] T021 [P] [US3] Contract test: risk CRUD + authz-denied without permission + out-of-support query, in tests/contract/test_apm_risk_api.py
- [ ] T022 [P] [US3] Unit test: out-of-support + expiring-soon date logic, in tests/unit/test_apm_risk_dates.py

### Implementation for User Story 3

- [ ] T023 [US3] Alembic migration 014: `application_risk` table (+ GIN on regulatory_tags, EOS partial index), in src/adp/store/migrations/versions/014_apm_risk.py
- [ ] T024 [US3] ApplicationRisk models (Literals for classification/posture/DR-BC), in src/adp/application/models.py
- [ ] T025 [US3] Store: risk CRUD + out-of-support/expiring queries + audit, in src/adp/application/store.py
- [ ] T026 [US3] Endpoints: risk read/write gated by `READ/WRITE_APPLICATION_RISK`, in src/adp/application/router.py
- [ ] T027 [US3] Extend the no-sensitive-data test to cover risk fields, in tests/unit/test_no_sensitive_data.py
- [ ] T028 [P] [US3] Web risk & compliance panel, in web/src/application/RiskPanel.tsx

---

## Phase 6: User Story 4 - TCO & spend rollups (Priority: P4) — ADP-9x6

**Goal**: `application_cost` (8 buckets × one-time+annual, Decimal), TCO compute, per-BU rollup, run-vs-change.
**Independent test**: Enter costs in two BUs; retrieve per-BU rollup + run-vs-change; change horizon and confirm TCO re-derives without re-entry.

### Tests for User Story 4 (MANDATORY — ART-IV)

- [ ] T029 [P] [US4] Contract test: cost CRUD + Decimal round-trip + authz + per-BU rollup, in tests/contract/test_apm_cost_api.py
- [ ] T030 [P] [US4] Unit test: `TCO = Σ(one-time) + Σ(annual) × horizon` + run-vs-change split, in tests/unit/test_tco.py

### Implementation for User Story 4

- [ ] T031 [US4] Alembic migration 015: `application_cost` (8 buckets × one_time/annual NUMERIC, currency CHAR(3), horizon_years), in src/adp/store/migrations/versions/015_apm_cost.py
- [ ] T032 [US4] ApplicationCost + CostBucket models (Decimal), TCO + run-vs-change computed on read, in src/adp/application/models.py
- [ ] T033 [US4] Store: cost CRUD + per-BU rollup query (joins owning_business_unit) + audit, in src/adp/application/store.py
- [ ] T034 [US4] Endpoints: cost read/write + rollup gated by `READ/WRITE_APPLICATION_COST` (aggregate re-checks permission), in src/adp/application/router.py
- [ ] T035 [P] [US4] Web cost / TCO panel, in web/src/application/CostPanel.tsx

---

## Phase 7: User Story 5 - Technical fit depth (Priority: P5)

**Goal**: hosting model, architecture pattern, tech-debt flags.
**Independent test**: Set hosting model + tech-debt flag; filter for cloud apps and for flagged apps.

### Tests for User Story 5 (MANDATORY — ART-IV)

- [ ] T036 [P] [US5] Contract test: technical-fit fields + hosting/tech-debt filters, in tests/contract/test_apm_techfit_api.py

### Implementation for User Story 5

- [ ] T037 [US5] Alembic migration 016: `hosting_model`, `architecture_pattern`, `tech_debt_flags` (+ CHECK, GIN) on `applications`, in src/adp/store/migrations/versions/016_apm_techfit.py
- [ ] T038 [US5] Extend Application models with technical-fit fields, in src/adp/application/models.py
- [ ] T039 [US5] Store: persistence + filters + audit, in src/adp/application/store.py
- [ ] T040 [US5] Endpoints: technical-fit update + filters; surface flags in technical-health view, in src/adp/application/router.py
- [ ] T041 [P] [US5] Web technical-fit panel, in web/src/application/TechFitPanel.tsx

---

## Phase 8: User Story 6 - Lifecycle & roadmap (Priority: P6)

**Goal**: transformation initiatives + application links with planned disposition; roadmap view.
**Independent test**: Create an initiative, link two apps, retrieve initiative with members + dispositions.

### Tests for User Story 6 (MANDATORY — ART-IV)

- [ ] T042 [P] [US6] Contract test: initiative CRUD + application links + roadmap view, in tests/contract/test_apm_roadmap_api.py

### Implementation for User Story 6

- [ ] T043 [US6] Alembic migration 017: `transformation_initiatives` + `application_initiative_links` (planned_disposition CHECK), in src/adp/store/migrations/versions/017_apm_roadmap.py
- [ ] T044 [US6] TransformationInitiative + link models, in src/adp/application/models.py
- [ ] T045 [US6] Store: initiative CRUD + link management + roadmap query (uses time_classification + retirement dates) + audit, in src/adp/application/store.py
- [ ] T046 [US6] Endpoints: initiatives + links + roadmap, in src/adp/application/router.py
- [ ] T047 [P] [US6] Web roadmap / initiatives view, in web/src/application/RoadmapView.tsx

---

## Phase 9: User Story 7 - Ownership & governance (Priority: P7)

**Goal**: `application_contracts` (terms, renewal date, SLA, sponsor, IT owner, decision rights); renewals-soon; governance authz.
**Independent test**: Record a contract renewing within 90 days; query renewals-soon.

### Tests for User Story 7 (MANDATORY — ART-IV)

- [ ] T048 [P] [US7] Contract test: contract CRUD + renewals-soon + governance authz, in tests/contract/test_apm_governance_api.py

### Implementation for User Story 7

- [ ] T049 [US7] Alembic migration 018: `application_contracts` (renewal_date partial index), in src/adp/store/migrations/versions/018_apm_governance.py
- [ ] T050 [US7] ApplicationContract models, in src/adp/application/models.py
- [ ] T051 [US7] Store: contract CRUD + renewals-soon query + audit, in src/adp/application/store.py
- [ ] T052 [US7] Endpoints: governance read/write gated by `READ/WRITE_APPLICATION_GOVERNANCE`, in src/adp/application/router.py
- [ ] T053 [P] [US7] Web governance / contracts panel, in web/src/application/GovernancePanel.tsx

---

## Phase 10: User Story 8 - Quality & performance signals (Priority: P8)

**Goal**: `application_quality_metrics` (manual, advisory); quality panel; does not override health_score.
**Independent test**: Record metrics; confirm they surface on the quality panel and do not change the technical-health score.

### Tests for User Story 8 (MANDATORY — ART-IV)

- [ ] T054 [P] [US8] Contract test: quality metrics CRUD + advisory (health_score unchanged), in tests/contract/test_apm_quality_api.py

### Implementation for User Story 8

- [ ] T055 [US8] Alembic migration 019: `application_quality_metrics` (CHECK ranges), in src/adp/store/migrations/versions/019_apm_quality.py
- [ ] T056 [US8] ApplicationQualityMetric models, in src/adp/application/models.py
- [ ] T057 [US8] Store: quality CRUD + audit, in src/adp/application/store.py
- [ ] T058 [US8] Endpoints: quality read/write, in src/adp/application/router.py
- [ ] T059 [P] [US8] Web quality panel, in web/src/application/QualityPanel.tsx

---

## Phase 11: Polish & Cross-Cutting Concerns

- [ ] T060 [P] Feeder migration 020 (ADP-33v): `strategic_relevance` (SMALLINT NULL CHECK 1..3) on `business_capabilities` + `technical_capabilities`, in src/adp/store/migrations/versions/020_capability_strategic_relevance.py
- [ ] T061 [P] Feeder migration 021 (ADP-4ga): `maturity_level` (SMALLINT NULL CHECK 1..5) on `business_capabilities`, in src/adp/store/migrations/versions/021_business_capability_maturity.py
- [ ] T062 [P] Publish the APM data dictionary (attribute → category → definition), in specs/038-application-portfolio-management/data-dictionary.md
- [ ] T063 Cascade-delete integration test (application → risk/cost/contract/quality/initiative links), in tests/integration/test_apm_cascade_delete.py
- [ ] T064 Cross-category application detail aggregation (all eight categories in one authorized view), in src/adp/application/router.py
- [ ] T065 Final `adp-generate` regen + drift gate + no-sensitive-data gate + full backend/web test run

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Ph1)** → **Foundational (Ph2)** → **User Stories (Ph3–10)** → **Polish (Ph11)**.
- Foundational (T003–T005) blocks the **sensitive** stories US3/US4/US7 only; US1/US2/US5/US6/US8 need only Setup.
- **Migrations chain** 012→013→…→019 (then feeders 020/021): a later migration's `down_revision` is the previous one, so migration tasks execute in number order even when the surrounding story work parallelizes.

### Soft cross-story dependencies (functional, not blocking build)

- US4 per-BU cost rollup needs US2's `owning_business_unit`.
- US6 roadmap is richer with US2 `lifecycle_status` + US3 EOL dates.
- US7 stakeholder roles complement US2 owners.

### Parallel opportunities

- Within a story: the `[P]` test task(s) and the `[P]` web panel run parallel to backend work.
- Across stories: migration files, test files, and web panels are distinct and parallelizable; **`models.py` / `store.py` / `router.py` edits are serialized** (shared files).
- Example (US1): T006 + T007 (tests) ∥ start; T013 (web) ∥ T008–T012 (backend).

## Implementation Strategy

- **MVP = User Story 1** (Phase 3): the business-value scores + TIME rationalization view deliver the epic's core value alone. Ship and demo before proceeding.
- **Then by priority**: US2 (identity) unblocks rollups; US3 (risk) is the biggest gap and exercises the sensitive-authz path first; US4 (cost) builds on US2; US5–US8 follow.
- **Feeders**: migrations 020 (ADP-33v) and 021 (ADP-4ga) are numbered into this block; at `/speckit.taskstoissues`, reparent beads **ADP-9x6, ADP-33v, ADP-4ga, ADP-zg3.4** under the APM epic so they don't duplicate generated tasks.

## Summary

- **Total tasks**: 65 across 11 phases.
- **Per story**: US1=9, US2=6, US3=8, US4=7, US5=6, US6=6, US7=6, US8=6; Setup=2, Foundational=3, Polish=6.
- **MVP scope**: US1 (T001–T014 minus later-story work) — the rationalization plot.
- **Tests**: mandatory per story (ART-IV) — contract + unit before implementation.
