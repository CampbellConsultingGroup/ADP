---
description: "Task list for 938-capability-model-analysis"
---

# Tasks: Capability Model Analysis

**Input**: Design documents from `/specs/938-capability-model-analysis/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/rest-api.md, quickstart.md

**Tests**: Mandatory (ART-IV). In every phase, test tasks come before their implementation and must fail first. The engine is pure (research R1), so its tests use hand-built `CapabilitySnapshot`s with a fixed `as_of=date(2026, 11, 15)`.

**Organization**: tasks are grouped by user story from spec.md:
- US1: roll-ups (P1)
- US2: lifecycle (P1)
- US3: impact (P1)
- US4: exposure (P2)
- US5: findings (P2)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an incomplete task)
- Paths are from the repo root

---

## Phase 1: Setup

- [X] T001 Confirm the baseline on branch `938-capability-model-analysis`. Run `pytest tests/ --ignore=tests/integration -q`, `ruff check src/`, `mypy src/` and `cd web && npm run test:run`, and record the counts in specs/938-capability-model-analysis/tasks.md Notes (expect ~2318 backend, 685 frontend).
- [X] T002 Run GitNexus impact on `update_technical_capability`, `TechnicalCapability`, `_serialize_technical_capability` and `CapabilityHeatMap` (`node .gitnexus/run.cjs impact <symbol> --direction upstream --repo .`). Record the callers and risk in Notes before editing.

---

## Phase 2: Foundational (blocks every story)

**Purpose**: the lifecycle columns (stored) and the snapshot plus engine skeleton (derived) that every story reads.

### Tests first

- [X] T003 [P] Write tests/unit/application/test_tech_cap_lifecycle.py (SQLite, `astore._metadata.create_all`):
  - create defaults to `lifecycle_status="current"` and `end_of_life_date=None`;
  - create and update accept every value of `emerging|current|contained|retiring|retired`;
  - `TechnicalCapabilityUpdate(lifecycle_status=None)` is rejected;
  - an explicit `end_of_life_date=None` clears the date, and an omitted one leaves it unchanged;
  - a raw `_tech_caps.insert()` without the column gets `"current"` (Python-side default);
  - an invalid status → `ValidationError`.
- [X] T004 [P] Write tests/unit/application/test_cap_analysis_not_stored.py, mirroring tests/unit/patterns/test_no_status_column.py. No column on any table in `adp.application.store._metadata` may match `/rollup|worst|spread|band|exposure|impact|overlap|gap|finding/i`. Migration `047_tech_cap_lifecycle.py` may add only `lifecycle_status` and `end_of_life_date`.
- [X] T005 [P] Write tests/integration/test_migration_047.py (Docker-gated, mirroring tests/integration/test_migration_046.py):
  - upgrade 046 → 047: an existing row becomes `current`/NULL;
  - the CHECK rejects `'bogus'`;
  - downgrade drops both columns;
  - upgrade again.

### Implementation

- [X] T006 Add `TechCapLifecycle = Literal["emerging","current","contained","retiring","retired"]` to src/adp/application/models.py.
  - Add `lifecycle_status: TechCapLifecycle = "current"` and `end_of_life_date: date | None = None` to `TechnicalCapability` and `TechnicalCapabilityCreate`.
  - Add both as optional fields to `TechnicalCapabilityUpdate`, with a validator that rejects an explicit `lifecycle_status=None`.
- [X] T007 Add migration src/adp/store/migrations/versions/047_tech_cap_lifecycle.py (`revision="047"`, `down_revision="046"`). It adds `lifecycle_status TEXT NOT NULL server_default 'current'` with the named CHECK `ck_tech_cap_lifecycle_status`, and `end_of_life_date DATE NULL`. The downgrade drops the CHECK and both columns.
- [X] T008 Make these changes in src/adp/application/store.py:
  - add both columns to `_tech_caps`, with `lifecycle_status` getting a Python-side `default="current"`;
  - map them in the row-to-model conversion used by `get_technical_capability` and `list_technical_capabilities`;
  - write them in `create_technical_capability`;
  - in `update_technical_capability`, write them using `model_fields_set` (as `description` is handled).

  T003 should now pass.
- [X] T009 Create src/adp/application/cap_analysis.py with the frozen `CapabilitySnapshot` dataclass (data-model.md fields, plus `risk_visible` and `cost_visible` bools) and small node/ref types. Include the helpers `path(node_id, tree)`, `children(tree)`, `leaf_l3s(cap_id)` and `expand_technical(tc_ids)` (a technical L2 expands to itself plus its children). No I/O, and no imports from the store.
- [X] T010 Create src/adp/application/cap_analysis_store.py with `build_snapshot(session, *, risk_visible, cost_visible) -> CapabilitySnapshot`, using the fixed queries in research R2.
  - It inner-joins the far ends.
  - It queries `application_risk` only when `risk_visible`, and calls `astore.list_all_costs` only when `cost_visible`.
- [X] T011 Write tests/unit/application/test_cap_analysis_snapshot.py (SQLite). Seed the five POS chains plus one dangling link row. Assert that:
  - the snapshot has the expected maps;
  - the dangling row is absent;
  - with `risk_visible=False` the risk map is empty and no `application_risk` query is executed (assert by recording statements with an SQLAlchemy `before_cursor_execute` listener);
  - the same holds for cost.

**Checkpoint**: lifecycle stored, snapshot built, guard test green.

---

## Phase 3: User Story 1 — Roll-ups up the business tree (P1) 🎯 MVP

**Goal**: health, risk and cost per business capability, as the worst value plus the spread over leaves, excluding Retired applications, with cost and risk gated.
**Independent Test**: seed POS with Store POS at health 2. `GET .../analysis/business-rollup` gives `worst: 2` on the five L3s, their L2 and their L1, and the L2 spread counts 5 leaves at 2.

### Tests first

- [X] T012 [P] [US1] Write the engine tests in tests/unit/application/test_cap_analysis_engine.py (class `TestRiskBand`) for every research R4 rule:
  - each High trigger;
  - each Medium trigger, including end of support exactly 365 days out;
  - Low;
  - Unknown when there is no record or the fields are mixed;
  - end of support equal to `as_of` → High.
- [X] T013 [P] [US1] Write the engine tests (class `TestBusinessRollup`) covering spec US1 scenarios 1–4 and 9:
  - two applications at health 2 and 4 → worst 2 with spread {2:1, 4:1};
  - an L2 with leaves 2, 4 and no-data → worst 2 with spread {2:1, 4:1, no_data:1};
  - a business L3 with no application capability, or whose application capabilities have no realizing application → `worst None` and `no_data`;
  - an unassessed application counts as `unassessed` and never sets the worst value;
  - a Retired application is excluded and listed in `excluded_retired_apps`, while a Sunset one counts;
  - only Retired applications → no data plus the excluded list;
  - one application through two application capabilities and two L3s under different L2s is counted once per capability (edge case);
  - an L1 with no L3 descendants → no data;
  - cost is the sum over distinct applications, plus `apps_without_cost`;
  - the parent cost uses the distinct union, not the sum of children;
  - `via` lists the application capabilities.
- [X] T014 [P] [US1] Write the engine tests (class `TestGating`): a snapshot with `risk_visible=False` gives `risk=None` on every item and `risk_available=False`; the same for cost. When visible, an empty result is `worst None`, never None for the whole metric.
- [X] T015 [P] [US1] Write tests/contract/test_cap_analysis_api.py `test_business_rollup_*` through `create_app()` (fixture order per CLAUDE.md: create the bstore metadata, then astore). Cover:
  - shape per contracts/rest-api.md;
  - enterprise_architect sees risk and cost;
  - with a dependency override to a role without `READ_APPLICATION_COST` (check `adp.authz.permissions` for one, e.g. REVIEWER), `cost_available` is false and `cost` is null on every item, and no TCO digits appear anywhere in the raw response text;
  - the same for risk with a role lacking `READ_APPLICATION_RISK`;
  - each gate holds independently.

### Implementation

- [X] T016 [US1] Add response models to src/adp/application/cap_analysis_models.py (new): `AppVia`, `HealthRollup`, `RiskRollup`, `CostRollup`, `ExposureRollup`, `CapabilityRollup`, `CapabilityRollupResponse` (with `as_of`, `risk_available`, `cost_available`). Use `extra="forbid"` and serialise TCO as a decimal string, matching `ApplicationCost`.
- [X] T017 [US1] Implement `risk_band(risk, as_of)` and `business_rollup(snapshot, as_of)` in src/adp/application/cap_analysis.py, following research R4/R6 and FR-005..FR-010. `exposure` stays None until T037. T012–T014 should now pass.
- [X] T018 [US1] Add `GET /analysis/business-rollup` to src/adp/application/app_capabilities_router.py, registered before `/{ac_id}`.
  - Resolve the user via the existing current-user dependency (as src/adp/api/routers/portfolio.py does).
  - Compute `risk_visible`/`cost_visible` with `is_permitted(user.role, ActionType.READ_APPLICATION_RISK | READ_APPLICATION_COST)`.
  - Build the snapshot and return `business_rollup(..., date.today())`.

  T015 should now pass.
- [X] T019 [P] [US1] Add web/src/api/capAnalysis.ts with types that mirror the contract and a `useCapabilityRollup(enabled)` hook (query key `["cap-analysis","rollup"]`). Invalidate it from 937's `useInvalidating` writes in web/src/api/appCapabilities.ts, plus from the technical capability update and application health, risk and cost mutations in web/src/api/application.ts.
- [X] T020 [US1] Write the component tests in web/src/business/CapabilityHeatMap.test.tsx (extend):
  - the Application health metric colours cells from the mocked roll-up;
  - L2/L1 cells show the worst value and the spread;
  - no-data cells look distinct;
  - a mocked `cost_available:false` renders the Cost option disabled with "not available to you", and no figures;
  - switching metrics triggers no new fetch after the first;
  - the cell detail lists the contributing applications, `via` and the excluded retired applications.
- [X] T021 [US1] Extend web/src/business/CapabilityHeatMap.tsx:
  - add the metrics `health | risk | cost` (exposure in T039);
  - `useCapabilityRollup` is enabled once one of them is chosen;
  - five-step swatches for health (1 = crit … 5 = good), a four-step scale for risk, and a sequential scale for cost (quantiles of the L3 totals);
  - a legend that includes "No data";
  - a title/focus detail panel per cell;
  - a "not allocated" note under the cost legend.

  T020 should now pass.

**Checkpoint**: MVP. The roll-up is visible on the heat map, with redaction proven.

---

## Phase 4: User Story 2 — Record a technical capability's lifecycle (P1)

**Goal**: architects edit the lifecycle; the change is logged, exported and visible.
**Independent Test**: PATCH "Distributed Caching" to `contained`, reload, and see it. An invalid value → 422.

### Tests first

- [X] T022 [P] [US2] Extend the contract tests in tests/contract/test_cap_analysis_api.py (`test_tech_cap_lifecycle_*`):
  - PATCH sets the status and date;
  - GET returns them;
  - `{"lifecycle_status":"bogus"}` → 422;
  - `{"lifecycle_status":null}` → 422;
  - `{"end_of_life_date":null}` clears the date;
  - caplog has exactly one `technical_capability.lifecycle ... from=current to=retiring` line, with none when only the name changes;
  - a role without `WRITE_APPLICATION` → 403 (via tests/authz/test_enforcement.py's existing pattern, if the contract fixture bypasses authz).
- [X] T023 [P] [US2] Extend tests/unit/export/test_application_arch_serialize.py: the technical capability JSON includes `lifecycle_status` and `end_of_life_date` (ISO string or null).
- [X] T024 [P] [US2] Add web/src/application/TechCapForm.test.tsx (new):
  - a lifecycle select with five options;
  - a date input;
  - save sends only the changed fields;
  - clearing the date sends `null`;
  - read-only users see the values without controls.

### Implementation

- [X] T025 [US2] In `update_tech_cap` in src/adp/application/router.py, read the existing capability before updating. When `lifecycle_status` or `end_of_life_date` changes, log `technical_capability.lifecycle id=%s actor=%s from=%s to=%s eol_from=%s eol_to=%s`.
- [X] T026 [P] [US2] Add both fields to `_serialize_technical_capability` in src/adp/export/application_arch.py (date as `isoformat()` or None).
- [X] T027 [P] [US2] Add `lifecycle_status` and `end_of_life_date` to the TechnicalCapability, Create and Update types in web/src/api/application.ts, along with a `TECH_CAP_LIFECYCLE_LABEL` map.
- [X] T028 [US2] Make these UI changes:
  - add the lifecycle select and an end-of-life date input to web/src/application/TechCapForm.tsx;
  - in web/src/application/TechCapTree.tsx, show a lifecycle chip on each row, plus a derived "past end of life" flag when `end_of_life_date <= today` and the status is not `retired` (US2 scenario 5; computed client-side for display only).

  T024 should now pass. Extend web/src/application/TechCapTree.test.tsx for the chip and flag.

**Checkpoint**: the lifecycle is editable and exported, which unblocks US3 and US4.

---

## Phase 5: User Story 3 — Impact of a technical capability (P1)

**Goal**: an upward trace from a technical capability to the application capabilities, applications and business capabilities that depend on it.
**Independent Test**: impact for "Local Data Store with Offline Sync" = exactly Basket Calculation → Store POS → Process Checkout, with its path (SC-002).

### Tests first

- [X] T029 [P] [US3] Write the engine tests (class `TestImpact`) for scenarios 1–4:
  - a technical L3 with one application capability gives the right lists and paths;
  - a technical L2 includes links to itself and to its children, with `via_technical_id`;
  - a business capability reached via two application capabilities is listed once, with two routes;
  - nothing depends → empty lists;
  - retired applications are listed and marked;
  - no cost or risk fields exist on the model.
- [X] T030 [P] [US3] Write the contract tests `test_impact_*`: 404 for an unknown id; the POS chain result; the response JSON has no `tco`, `security_posture` or `risk` keys at any depth.
- [X] T031 [P] [US3] Add web/src/application/TechCapImpactPanel.test.tsx (new):
  - a lazy expander;
  - the "Nothing depends on this technical capability" empty state;
  - business capabilities with an L1 › L2 path and route count;
  - items call the navigation callbacks.

### Implementation

- [X] T032 [US3] Add `ImpactResult` (and its ref types) to src/adp/application/cap_analysis_models.py, and implement `impact(snapshot, tc_id)` in src/adp/application/cap_analysis.py. T029 should now pass.
- [X] T033 [US3] Add `GET /analysis/technical-capabilities/{tc_id}/impact` to src/adp/application/app_capabilities_router.py, returning 404 when `tc_id` is not in the snapshot. It needs no gated data, so build the snapshot with `risk_visible=False, cost_visible=False`. T030 should now pass.
- [X] T034 [US3] Add `useTechCapImpact(tcId)` to web/src/api/capAnalysis.ts.
- [X] T035 [US3] Create web/src/application/TechCapImpactPanel.tsx, reusing the expander pattern from web/src/application/AppCapSummaryList.tsx. Render it on each row in web/src/application/TechCapTree.tsx beside `TechCapUsedBy`.
  - Application capabilities open through `useOpenAppCapability()`.
  - Applications open through the existing application opener, if one exists in App.tsx context; otherwise they are plain text, and the gap is recorded in Notes.
  - Business capabilities open through an opener added to `AppCapNavContext` in web/src/application/appCapNav.tsx, which switches to Business → Capabilities and scrolls to the row (the 043 `focusCapabilityId` precedent).

  T031 should now pass.

**Checkpoint**: P1 complete.

---

## Phase 6: User Story 4 — Technology exposure and dependencies (P2)

**Goal**: business capabilities coloured by the worst effective lifecycle band they depend on, plus a per-L3 dependency list.
**Independent Test**: with offline sync set to Retiring, Process Checkout, its L2 and its L1 show Retiring under Technology exposure; the other four POS L3s show Current.

### Tests first

- [X] T036 [P] [US4] Write the engine tests (`TestEffectiveBand`, `TestExposure`, `TestTechnologyDependencies`):
  - research R5 ordering, with end of life equal to `as_of` → past end of life, 365 days out → retiring, 366 days out → the status itself, and Retired with no date → past end of life;
  - exposure: an L3 with Current plus Retiring technical capabilities → Retiring;
  - a linked technical L2 expands to its children;
  - no chain → no data;
  - L2/L1 use the worst value plus the spread over leaves;
  - dependencies list each technical capability once per application capability, with its band;
  - for an L1/L2, the union over its L3s, with `via_business_capability`.
- [X] T037 [P] [US4] Write the contract tests `test_technology_*`: 404 for an unknown business capability; the POS L3 lists offline sync as retiring; the roll-up's `exposure` is populated for every item.
- [X] T038 [P] [US4] Extend the component tests: in web/src/business/CapabilityHeatMap.test.tsx, the exposure metric's colours and legend; in web/src/business/CapabilityNode.test.tsx, the "Technology dependencies" expander on L3s (lazy, empty state, band chips).

### Implementation

- [X] T039 [US4] Implement `effective_band`, fill `exposure` in `business_rollup`, and add `technology_dependencies(snapshot, cap_id, as_of)` in src/adp/application/cap_analysis.py, with the `TechnologyDependency` models in cap_analysis_models.py. T036 should now pass.
- [X] T040 [US4] Add `GET /analysis/business-capabilities/{cap_id}/technology` to src/adp/application/app_capabilities_router.py. T037 should now pass.
- [X] T041 [US4] Make these UI changes:
  - add `useBusinessTechnology(capId)` to web/src/api/capAnalysis.ts;
  - add the `exposure` metric (five-band scale plus No data) to web/src/business/CapabilityHeatMap.tsx;
  - add a `BusinessCapTechnology` expander in web/src/application/AppCapSummaryList.tsx, rendered on L3 rows in web/src/business/CapabilityNode.tsx beside `BusinessCapAppCaps`.

  T038 should now pass.

---

## Phase 7: User Story 5 — Gaps, overlaps and shared (P2)

**Goal**: rationalization views on Applications → Capabilities.
**Independent Test**: once seeded, Overlaps lists "Apply Promotions" with Xstore POS and Commerce Cloud. Removing the realization clears it (SC-003).

### Tests first

- [X] T042 [P] [US5] Write the engine tests (`TestFindings`) for scenarios 1–5:
  - two application capabilities realized by different applications → an overlap;
  - both by the same application → no overlap;
  - Retired applications don't create an overlap;
  - each gap list, including ancestors in the path;
  - shared at a count of 3 is included and 2 is not;
  - an empty estate → every business L3 is in the gaps, with no errors.
- [X] T043 [P] [US5] Write the contract tests `test_findings_*`: the shape matches the contract; no gated keys appear; a reviewer gets the same lists.
- [X] T044 [P] [US5] Add web/src/application/CapFindingsViews.test.tsx (new):
  - the Overlaps, Gaps (three headed sections) and Shared views render the mocked findings;
  - empty states;
  - Shared is labelled informational;
  - items navigate.

### Implementation

- [X] T045 [US5] Implement `findings(snapshot)` in src/adp/application/cap_analysis.py, with the `CapabilityFindings` models. Define `SHARED_THRESHOLD = 3` as a module constant. T042 should now pass.
- [X] T046 [US5] Add `GET /analysis/findings` to src/adp/application/app_capabilities_router.py. T043 should now pass.
- [X] T047 [US5] Add `useCapabilityFindings()` to web/src/api/capAnalysis.ts. Create web/src/application/CapFindingsViews.tsx. Extend the tab group in web/src/application/AppCapabilitiesView.tsx with Overlaps, Gaps and Shared, keeping the existing Missing technical capability tab. Selecting an application capability uses the existing `setSelectedId`; business capabilities use the T035 opener. T044 should now pass.

---

## Phase 8: Polish & Cross-Cutting

- [X] T048 Make these changes in scripts/seed_retail.py (FR-023):
  - set "Local Data Store with Offline Sync" to `retiring` with an end-of-life date of `2027-06-30`;
  - add the application capability "Online Promotion Evaluation" under Pricing, realized by Salesforce Commerce Cloud and linked to "Apply Promotions", with a technical link to "API Gateway Services" so it raises no 937 warning;
  - give Store POS a risk record with `security_posture="weak"`;
  - confirm Store POS's health assessment yields 2.

  Keep the seed idempotent, as 937's phase is.
- [X] T049 [P] Write a scale check in tests/unit/application/test_cap_analysis_engine.py (`TestScale`): a synthetic snapshot of 500 business capabilities, 500 application capabilities and 2,000 links. `business_rollup` plus `findings` finish in under 0.5 s on the dev box (SC-005 headroom; mark it `@pytest.mark.slow` if that marker exists, otherwise use a generous bound).
- [X] T050 Run the full gates and record the counts in Notes: `pytest tests/ --ignore=tests/integration -q`, `ruff check src/`, `mypy src/`, `adp-generate --check`, `cd web && npx tsc --noEmit && npm run test:run`, and coverage ≥ 85% on cap_analysis*.py.
- [X] T051 Do a live verification:
  - `alembic upgrade head` on local Postgres (5433), check `alembic current` = 047, and run a downgrade/upgrade cycle;
  - reseed;
  - run every quickstart.md step with curl;
  - do a Playwright walkthrough of the heat map's health, risk, cost and exposure metrics, the technical capability lifecycle edit and Impact panel, the L3 technology dependencies, and Overlaps, Gaps and Shared;
  - restore any scratch edits.
- [ ] T052 Update CLAUDE.md Recent Changes (938 entry: what shipped, gotchas). Update bead ADP-6et.2 notes. File follow-on beads for the spec's Out of Scope items that aren't already tracked (Governance roll-up, editable risk mapping, horizon and threshold, history). Run `node .gitnexus/run.cjs analyze --index-only` and `detect-changes --scope compare --base-ref main`.

---

## Dependencies & Execution Order

- **Setup (T001–T002)** → **Foundational (T003–T011)** → all stories.
- **US1 (T012–T021)**: needs Foundational only. This is the MVP.
- **US2 (T022–T028)**: needs Foundational only, so it can run alongside US1. Its backend is small; the stored part is already in Foundational.
- **US3 (T029–T035)**: needs Foundational. T035's business-capability opener is reused by US5.
- **US4 (T036–T041)**: needs US1's `business_rollup` (T017) and the lifecycle (Foundational). Its UI is shared with US1's heat map.
- **US5 (T042–T047)**: needs Foundational, plus the T035 opener for navigation.
- **Polish (T048–T052)**: after the stories it covers. Seed T048 can be done any time after Foundational.

Within each story: tests → models → engine → route → hook → component.

## Parallel Examples

- Foundational: T003, T004 and T005 together; then T006 → T007 → T008, alongside T009.
- US1: T012, T013, T014 and T015 together; T019 alongside T017/T018.
- Across stories: once T017 lands, the engine tests for US3, US4 and US5 (T029, T036, T042) can all be written in parallel. They touch the same test file but different classes, so either write them sequentially or split them into per-story test files.
- Frontend tests T024, T031 and T044 are independent new files.

## Implementation Strategy

1. **MVP**: Setup, Foundational, US1. The roll-up is on the heat map with redaction proven. Stop and demo.
2. Add US2 and US3 to complete the P1 set (lifecycle plus impact, the user's EOL example).
3. Add US4 and US5 for the P2 analysis views.
4. Finish with Polish: seed, scale check, live verification, docs.

## Notes

- **Baseline (T001):** 2318 backend tests (89.33% coverage), 685 frontend tests.
- **GitNexus impact (T002):**
  - `TechnicalCapability`: CRITICAL, up to 172 impacted, across two matching symbols.
  - `_serialize_technical_capability`: CRITICAL, 136 impacted, through the export pipeline.
  - Both changes are additive (new defaulted fields, two new export keys), so existing callers are unaffected. The full suite confirms it.
  - `update_technical_capability` and `CapabilityHeatMap` came back UNKNOWN. Text search confirmed one caller each: the PATCH route, and BusinessPage.
- **Ordering deviation, recorded rather than hidden:**
  - The engine tests for every story (US1, US3, US4 and US5) were written together in `test_cap_analysis_engine.py`, before any engine code. The engine was then implemented in one pass.
  - The contract tests for every story were likewise written together, before the routes.
  - Test-first still held throughout: each test failed (ImportError or 404) before its implementation existed.
- **T035, T047 navigation:**
  - A new `CapabilityNavContext` in `appCapNav.tsx`, provided by App.tsx, opens business capabilities (Business → Capabilities, highlighted), applications (Registry) and technical capabilities (Technical Architecture, scrolled and highlighted).
  - Findings pick application capabilities in place, through a local `AppCapNavContext` override.
- **T048 seed:** the updated seed was NOT run end to end. It hard-wipes the database, and the DB user can't create a scratch database (`permission denied to create database`). The same demo changes were applied to the live local data through the API instead: offline sync Retiring 2027-06-30; Online Promotion Evaluation → Apply Promotions, realized by Salesforce Commerce Cloud; POS posture weak. The seed's syntax and imports were checked.
- **T051 live verification:**
  - Migration 047 applied, downgraded and upgraded on local Postgres (5433).
  - The quickstart curls all matched: Process Checkout health 2, risk high, exposure retiring; impact exactly Basket Calculation → Xstore POS → Process Checkout; the Apply Promotions overlap cleared when the realization was removed and came back when it was re-added.
  - Playwright covered the heat map's health, risk, cost and exposure metrics, the cell detail, the lifecycle select and date, the Impact panel, navigation to the business row, technology dependencies, and Overlaps, Gaps and Shared.
  - A live UI lifecycle edit (Distributed Caching → Retired) turned Apply Promotions to past end of life, and was then reverted.
- **Found live, not by tests:** the spread wording read "4 leafs" and "1 at health 2". It now says "leaves", names the unit on L3s, and has a test.
- **Lifecycle log line in local uvicorn:** not visible, because app INFO logs aren't configured locally. The existing 937 write logs don't appear either. The contract test asserts the line through caplog.
