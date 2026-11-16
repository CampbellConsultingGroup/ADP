# Tasks: Regional Assessments

**Input**: design documents in `/specs/942-regional-assessments/` (plan.md, spec.md, research.md, data-model.md, contracts/rest-api.md, quickstart.md)
**Tests**: required (constitution ART-IV, TDD). Each test task is written first and must fail before its implementation task.
**Bead**: ADP-55k.3

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: US1–US4 from spec.md (US1 assessments P1, US2 region-specific scope P2, US3 heat map P1, US4 export/seed P3)

---

## Phase 1: Setup

- [X] T001 Confirm the migration head is `049` (`ls src/adp/store/migrations/versions`) and that local Postgres on 5433 is at `049` (`alembic current`).
- [X] T002 List every fixture that creates both bstore or astore metadata and ostore metadata (`grep -rln "ostore._metadata" tests`). The new tables need `business_capabilities` (real or mirror) and `geographies` in the same SQLite file. Confirm each fixture already excludes the ostore `business_capabilities` mirror where another metadata creates it (941 did this).

---

## Phase 2: Foundational (blocks every story)

- [X] T003 Write the Docker-gated `tests/integration/test_migration_050.py`, mirroring `test_migration_049.py`. It covers:
  - upgrade creates the 3 tables with `ck_regional_assessment_maturity` (6 fails), `ck_regional_assessment_content` (both NULL fails) and the note length CHECK;
  - `uq_regional_assessment` (second row for the same pair fails);
  - CASCADE on capability delete (assessments, flag and scope gone), on geography delete (assessments and scope rows gone, flag kept), and from `region_specific_capabilities` to its geographies;
  - downgrade drops the 3 tables, leaves `capability_org_mappings`, and upgrade re-applies.
- [X] T004 Create `src/adp/store/migrations/versions/050_regional_assessments.py` (`revision="050"`, `down_revision="049"`) per data-model.md.
- [X] T005 In `src/adp/organization/store.py`:
  - add `maturity_level` (Integer, nullable) to the `_business_capabilities` mirror;
  - add `_capability_regional_assessments`, `_region_specific_capabilities` and `_region_specific_capability_geographies` matching migration 050 (UniqueConstraint and CheckConstraints included, so SQLite enforces them).

  Run `pytest tests/unit/organization tests/contract/test_organization_api.py tests/contract/test_capability_org_mappings_api.py tests/unit/search tests/unit/export -q` and confirm it is green.
- [X] T006 [P] Add the models from data-model.md to `src/adp/organization/models.py`:
  - `GeoRef`, `RegionalAssessment`;
  - `SetRegionalAssessment` (maturity `Literal[1,2,3,4,5] | None`, note `max_length=1000`, blank → None, validator "Record a maturity score, a note, or both");
  - `RegionalAssessmentListResponse`;
  - `SetRegionScope` (validator: region_specific requires ≥ 1 geography; not region_specific requires none);
  - `RegionScope`, `HeatmapCell` (state Literal), `HeatmapRow`, `RegionalHeatmap`.

  Reuse `LevelRuleError` (422) for Global and level-rule refusals, and `UnknownReferenceError` (422) for unknown geography ids in a body or query.
- [X] T007 [P] Write the guard `tests/unit/organization/test_regional_not_stored.py`:
  - no table in any ADP metadata has a column named like `applicable`, `delta`, `state`, `heatmap`, `scope_needs_update` or `baseline`;
  - migration 050 creates exactly the 3 tables and alters no existing table (no `add_column`, no `alter_column`).

**Checkpoint**: migration and tables exist; models compile; existing suites still green.

---

## Phase 3: User Story 1 — Record maturity per region (P1) 🎯 MVP

**Goal**: record, change and remove a capability × region/country assessment (score and/or note); Global refused; global maturity untouched.
**Independent test**: quickstart §1.

- [X] T008 [P] [US1] Write SQLite store tests in `tests/unit/organization/test_regional_store.py::TestAssessments`. The fixture creates ostore metadata with its own `business_capabilities` mirror (with `maturity_level`) and seeds geography via `geography_seed_rows`. Cover:
  - recording a score for a region and a score plus note for a country;
  - re-recording changes the same row (count stays 1, `updated_at` moves);
  - note-only is accepted;
  - Global → `LevelRuleError` "Global is the capability's baseline maturity";
  - an unknown capability or geography → `OrgNotFoundError`;
  - remove, then remove again → `OrgNotFoundError`;
  - the mirror's `maturity_level` is unchanged after every write (SC-004);
  - listing filters by `capability_id`, ordered by geography name.
- [X] T009 [US1] Create `src/adp/organization/regional.py` with:
  - `set_assessment(cap_id, geo_id, body, session) -> tuple[RegionalAssessment, created: bool]` (select, then insert or update; never touches the capability row);
  - `remove_assessment(cap_id, geo_id, session)`;
  - `list_assessments(session, capability_id=None)`.

  Make T008 pass.
- [X] T010 [P] [US1] Write contract tests in `tests/contract/test_regional_assessments_api.py`. The fixture creates bstore metadata first, then ostore excluding the `business_capabilities` mirror (keeping its `applications` mirror), and seeds capabilities and geography as in 941's contract test. Cover:
  - PUT 200 for create and update;
  - 422 for Global, `{}`, maturity 6 and a 1001-character note;
  - 404 for an unknown capability or geography;
  - DELETE 204, then 404;
  - GET list with the filter;
  - GET `/capabilities/{id}` shows an unchanged `maturity_level`;
  - reviewer → 403 on PUT and DELETE;
  - log lines `regional_assessment.set` and `.remove` include the actor.
- [X] T011 [US1] Add `GET /regional-assessments`, `PUT /regional-assessments/{cap_id}/{geo_id}` and `DELETE /regional-assessments/{cap_id}/{geo_id}` to `src/adp/organization/router.py`, with the log lines from contracts/rest-api.md (note length, not note text). Make T010 pass.

**Checkpoint**: assessments work end to end through the API.

---

## Phase 4: User Story 3 — Compare regions on a heat map (P1)

**Goal**: capability × geography matrix with a baseline column, cell states, deltas, regions by default, up to 12 columns.
**Independent test**: quickstart §3.

- [X] T012 [P] [US3] Write pure tests in `tests/unit/organization/test_regional_analysis.py::TestCells` and `::TestHeatmap`, against a hand-built `RegionalSnapshot`:
  - an assessed cell carries the score, note and `delta = score − baseline`, and `delta` is None when the baseline is None;
  - an unassessed cell → `not_assessed`;
  - Europe assessed but Germany not → the Germany cell is `not_assessed` (no inheritance), and vice versa (no roll-up);
  - L1/L2 rows show only their own assessment;
  - rows follow tree pre-order;
  - default columns are the level-2 geographies by name;
  - requested columns keep their order and drop duplicates;
  - Global, an unknown id or more than 12 columns raise.
- [X] T013 [US3] Create `src/adp/organization/regional_analysis.py`:
  - a frozen `RegionalSnapshot` (reuse `cap_org_analysis._preorder` and its `CapNode`, adding a `baseline` field or a parallel dict);
  - `cell(s, cap_id, geo_id)`, `columns(s, requested)` and `heatmap(s, requested) -> RegionalHeatmap`.

  Add `build_snapshot(session)` (4 queries) to `regional.py`. Make T012 pass.
- [X] T014 [P] [US3] Extend the contract tests: GET `/regional-heatmap` defaults to the 5 regions plus rows; `?geography_ids=` with a country returns that column; 422 for Global, an unknown id and 13 ids; cells reflect a just-recorded assessment (nothing cached).
- [X] T015 [US3] Add `GET /regional-heatmap` to `router.py` (comma-separated `geography_ids`). Make T014 pass.

---

## Phase 5: User Story 2 — Region-specific scope (P2)

**Goal**: flag a capability region-specific with ≥ 1 geography; applicability by containment in both directions; "scope needs updating" after its last geography is deleted.
**Independent test**: quickstart §2 and §4.

- [X] T016 [P] [US2] Write pure tests in `test_regional_analysis.py::TestApplicability`:
  - not region-specific → applicable everywhere;
  - scope Brazil → applicable in Brazil and in the Americas (contains), not in Europe or Germany;
  - scope Americas → applicable in Brazil (inside);
  - a flagged empty scope → applicable nowhere, with `scope_needs_update` true on the row;
  - a not-applicable cell wins over an existing assessment (state `not_applicable`; the assessment is still listed by GET `/regional-assessments`).
- [X] T017 [US2] Add `applicable(s, cap_id, geo_id)` and the row's `region_specific` / `scope_needs_update` flags to `regional_analysis.py`, and use them in `cell`. Make T016 pass.
- [X] T018 [P] [US2] Write store tests in `test_regional_store.py::TestScope` and `::TestDeletes`:
  - set a scope with 2 geographies;
  - replace it with 1;
  - clearing the flag removes the flag and its geographies;
  - a flagged scope with `[]` is refused by the model;
  - Global or an unknown geography in a scope is refused;
  - `delete_geography` removes that geography's assessments and scope rows, keeps the flag, and `get_scope` then reports `scope_needs_update`;
  - assessments or scope rows whose capability is gone never surface (inner join).
- [X] T019 [US2] In `regional.py`, add `get_scope(cap_id, session) -> RegionScope` and `set_scope(cap_id, body, session) -> RegionScope`, replacing the scope in one transaction. In `store.py` `delete_geography`, delete `_capability_regional_assessments` and `_region_specific_capability_geographies` rows for the geography before deleting it (SQLite parity; CASCADE is the safety net). Make T018 pass.
- [X] T020 [P] [US2] Extend the contract tests:
  - GET and PUT `/capability-region-scope/{cap_id}` 200;
  - 422 for flagged-and-empty, Global and an unknown geography;
  - 404 for an unknown capability;
  - reviewer → 403;
  - the `region_scope.set` log line;
  - the heat map shows `not_applicable` for an out-of-scope column.
- [X] T021 [US2] Add the two `/capability-region-scope/{cap_id}` routes to `router.py`. Make T020 pass.

---

## Phase 6: User Story 4 — Export and seed (P3)

- [X] T022 [P] [US4] Extend `tests/unit/export/test_business_arch_serialize.py`: `_serialize_capability(cap, designs, organization, regional)` includes `regional` with region_specific, scope, scope_needs_update and assessments; `EMPTY_REGIONAL` is the default. Update the exact-dict test. Add `TestExportBlock` to `test_regional_analysis.py`.
- [X] T023 [US4] Add `regional_analysis.export_block(s, cap_id)`. In `src/adp/export/business_arch.py`:
  - add `EMPTY_REGIONAL` and a `regional` parameter on `_serialize_capability`;
  - add a `capability_regional` dict on the snapshot;
  - build it best effort in `_fetch_all` from one `regional.build_snapshot`.

  Make T022 pass.
- [X] T024 [US4] In `scripts/seed_retail.py`:
  - add `region_specific_capability_geographies`, `region_specific_capabilities` and `capability_regional_assessments` to `WIPE_TABLES` (never `geographies`);
  - add phase C5, recording assessments for Accept Payment, Replenishment, Financial Management and Human Capital Management. Each gets different scores in Europe, the Americas, geo-DE and geo-BR, and one note;
  - add an L3 "Statutory eSocial Reporting" under Human Capital Management (in `CAPABILITIES`), scoped region-specific to geo-BR.

  Verify every referenced name with the same check used for 941. Do NOT run the seed.

---

## Phase 7: Frontend

- [X] T025 [P] Add types and hooks to `web/src/api/organization.ts`: `useRegionalAssessments(capabilityId?)`, `useSetRegionalAssessment`, `useRemoveRegionalAssessment`, `useRegionalHeatmap(geographyIds)`, `useRegionScope(capabilityId)` and `useSetRegionScope`. All mutations invalidate the `["organization"]` prefix.
- [X] T026 [P] Extract the 5-step `FIVE_STEP` swatches and the `MATURITY_LEVEL_LABEL` usage into `web/src/business/maturityScale.ts`, and switch `CapabilityHeatMap.tsx` to it. `CapabilityHeatMap.test.tsx` must stay green unchanged.
- [X] T027 [P] [US3] Write `web/src/business/RegionalHeatMap.test.tsx`:
  - the baseline column plus region columns;
  - an assessed cell shows its label and ▲/▼ delta;
  - "Not assessed" and "Not applicable" cells;
  - the note in the cell title;
  - adding and removing a country column calls `onColumnsChange`, and the add control is disabled at 12;
  - for writers, clicking a cell opens the editor and saving calls `useSetRegionalAssessment` with `{capabilityId, geographyId, maturity_level, note}`;
  - readers can't open the editor;
  - loading and error states;
  - a "scope needs updating" marker on the row.
- [X] T028 [US3] Create `web/src/business/RegionalHeatMap.tsx` (props `columns: string[] | null`, `onColumnsChange`, `onOpenCapability?`): a `<table>` in an `overflow-x: auto` container, a column picker (regions, plus a filterable country list), and a `CellEditor` from `RegionalAssessmentEditor.tsx`. In `BusinessPage.tsx`, add a "Capabilities | Regional" switch on the Heat Map tab and keep `regionalColumns` state there (session persistence). Make T027 pass.
- [X] T029 [P] [US1] [US2] Write `web/src/business/RegionalAssessmentEditor.test.tsx`:
  - the row expander lists the capability's assessments (geography, label, note);
  - adds one (geography picker without Global, score, note);
  - edits and removes one;
  - the scope editor toggles region-specific, requires at least one geography, and saves;
  - read-only for readers;
  - shows the server's rule message on failure.
- [X] T030 [US1] [US2] Create `web/src/business/RegionalAssessmentEditor.tsx`, exporting `CellEditor`, `RegionalAssessmentsPanel` and `RegionScopeEditor`. Add a "Regions" toggle and expander to `web/src/business/CapabilityNode.tsx`, next to Organization. Make T029 pass, and keep the `CapabilityNode` and `CapabilityTree` tests green.

---

## Phase 8: Polish & cross-cutting

- [X] T031 Run the gates:
  - `pytest tests/ --ignore=tests/integration -q`;
  - **`ruff check src/ tests/`**, `mypy src/adp/ --ignore-missing-imports`, `bandit -r src/adp/ -ll`, `adp-generate --check`;
  - `cd web && npx tsc --noEmit && npx vitest run --coverage` (above the ratchet).

  Fix anything that fails.
- [X] T032 `alembic upgrade head` (050), `downgrade 049`, `upgrade head` on local Postgres (5433). Restart the backend on :8001 and run quickstart §1–§4 with curl on scratch data. Confirm the baseline `maturity_level` is unchanged.
- [X] T033 Playwright walkthrough of quickstart §5 (the regional view, columns surviving a tab switch, cell edit, hover note, the Regions expander and scope). Check that no row or the page itself overflows sideways (the 941 lesson). Fix any bug found, with a regression test. Clean up all scratch data and confirm it is gone.
- [X] T034 Add the 942 Recent Changes entry to `CLAUDE.md` by hand; mark tasks `[X]` with implementation notes here; add a note to bead ADP-55k.3; run `node .gitnexus/run.cjs analyze --index-only` and `detect-changes --scope all`.

---

## Dependencies & Execution Order

- **Setup (T001–T002)** → **Foundational (T003–T007)** → the stories.
- **US1 (T008–T011)** first: it creates `regional.py`.
- **US3 (T012–T015)** depends on US1 (assessments to show) and creates the engine and snapshot.
- **US2 (T016–T021)** depends on the engine (T013) for applicability.
- **US4 (T022–T024)** after US1–US3.
- **Frontend**: T025 and T026 after the routes. T027–T028 after T015. T029–T030 after T011 and T021.
- **Polish (T031–T034)** last.

Within a story: the test task, then its implementation; engine before store before route.

## Parallel examples

- After T006: T007, T008 and T010 together.
- US3: T012 and T014 written together; then T013 and T015.
- US2: T016, T018 and T020 together.
- Frontend: T025, T026, T027 and T029 in parallel.

## Implementation Strategy

- **MVP**: Phases 1–3 (assessments through the API), then the heat map (Phase 4). That pair delivers "see maturity by region".
- **Then**: US2 scope → US4 export/seed → frontend → polish.
- Commit only when the user asks; merge only after CI passes (main has no required checks).

---

## Implementation notes (2026-11-16)

- **Results**:
  - backend 2526 tests (+33), 90.14% coverage;
  - frontend 794 tests, coverage 61.15 / 58.04 / 52.80 / 63.52 (up on all four, above the ratchet);
  - `ruff check src/ tests/`, mypy, bandit, tsc and `adp-generate --check` clean.
- **Migration 050**: upgrade, downgrade, upgrade on local Postgres (5433). `test_migration_050.py` is Docker-gated and runs in CI.
- **Live checks on real Postgres** (all scratch data removed; back to 40 capabilities, 0 assessments, 255 geographies):
  - Global (422) and empty (422) assessments are refused, and re-recording updates the same row;
  - the baseline `maturity_level` is unchanged by every regional write;
  - the default columns are the 5 regions;
  - a Brazil-only capability is not_assessed in the Americas and not_applicable in Europe and Germany;
  - with a baseline of 3, Brazil at 2 shows delta −1;
  - deleting a scoped country keeps the flag, marks it "scope needs updating" and removes that country's assessments;
  - deleting the capability removes its assessments and scope (FK CASCADE on Postgres).
- **Playwright**:
  - the regional view; a Brazil column added, surviving a tab switch;
  - saving and removing a cell;
  - a row name opens the capability, focused;
  - the Regions panel (baseline, assessment, scope);
  - no console errors, no row or page overflow.
- **Bug found live and fixed**: heat map cells mixed the `border` shorthand with `borderStyle` (the dashed "not assessed" cell). React warned that this mis-styles cells on re-render. Cells now use border longhands, with a regression test.
- **Deviations from the plan**:
  - `RegionalSnapshot` reuses 941's `cap_org_analysis._preorder` by converting to its `CapNode`, so the tree order is identical;
  - cell editing for writers uses an inline popover inside the scroll area (padding at the bottom keeps the popover for the last rows visible).
- **Seed**: phase C5 adds 10 assessments and the new L3 "Statutory eSocial Reporting" under Human Capital Management, Brazil-only. References were checked against the seed's own lists and the geography data file; the seed was NOT run. The new tables are in `WIPE_TABLES`.
- **Noted, not changed**: capability rows now carry 8 action buttons, so longer names wrap onto two lines. A future pass could fold the expanders into a menu.
