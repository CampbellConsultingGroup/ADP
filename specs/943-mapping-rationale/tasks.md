# Tasks: Mapping Rationale (943)

**Input**: Design documents from `/specs/943-mapping-rationale/`.
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/rest-api.md, quickstart.md.
**Tests**: required (constitution ART-IV, test-first). Each test task comes before the code it covers and must fail first.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

- [X] T001 Write the Docker-gated migration test in `tests/integration/test_migration_051.py`, mirroring `test_migration_050.py`. It must cover:
  - upgrade adds `rationale` and `geography_id` to `app_capability_realizations`;
  - the CHECK refuses `'maybe'`;
  - the FK sets `geography_id` to NULL when its geography is deleted;
  - existing rows read NULL/NULL;
  - downgrade removes both columns and upgrade reapplies cleanly.
- [X] T002 Create migration `src/adp/store/migrations/versions/051_realization_rationale.py` (`down_revision = "050"`). Add:
  - `rationale TEXT NULL` with CHECK `ck_app_cap_realization_rationale`;
  - `geography_id VARCHAR(36) NULL` with FK `fk_app_cap_realization_geography` → `geographies.id` ON DELETE SET NULL;
  - index `ix_app_cap_realizations_geography_id`.

  Downgrade drops these in reverse order.
- [X] T003 Add `rationale` (Text, nullable) and `geography_id` (String(36), nullable, **no** ForeignKey; research R1) to `_app_cap_realizations` in `src/adp/application/store.py`.

## Phase 2: Foundational (blocks every story)

- [X] T004 [P] Write tests for the two organization helpers in `tests/unit/organization/test_geography_helpers.py`, on SQLite with `ostore._metadata`:
  - `geography_level(id)` returns 1, 2 or 3, or None for an unknown id;
  - `geography_index(session)` returns `{id: (parent_id, name, code)}` for every geography.
- [X] T005 Implement `geography_level()` and `geography_index()` in `src/adp/organization/store.py`. They are public and read-only.
- [X] T006 [P] Add the shared models to `src/adp/application/app_capability_models.py`:
  - a `Rationale = Literal["target","tactical","transitional","redundant"]` type;
  - `GeoRef {id, name, code|None}`;
  - `AppRef` gains `rationale: Rationale | None = None`, `geography: GeoRef | None = None` and `hint: str | None = None`.

## Phase 3: User Story 1 — Classify why an application realizes a capability (P1) 🎯 MVP

**Goal**: set, change and clear the rationale and geography on a realization; existing realizations read as unclassified.
**Independent test**: quickstart steps 1–3.

### Tests (write first, must fail)

- [X] T007 [P] [US1] Write store tests in `tests/unit/application/test_realization_rationale_store.py`, on SQLite with astore metadata, plus ostore's `geographies` when it's needed. They must cover:
  - an existing realization reads `rationale=None, geography=None`;
  - `add_realization` with a rationale and geography stores them;
  - `update_realization`:
    - sets, changes and clears each field independently: an omitted field is unchanged, an explicit None clears it;
    - an unknown link raises not found;
    - an unknown geography raises 422 "not found";
    - a level-1 geography raises 422 "No geography already means everywhere";
  - `realized_by` returns the geography's name and code;
  - a dangling geography id reads as None (research R3);
  - removing a realization removes its attributes.
- [X] T008 [P] [US1] Write contract tests in `tests/contract/test_realization_rationale_api.py`, mirroring the fixture in `test_app_capabilities_api.py`. They must cover:
  - POST `/{ac_id}/applications` with `rationale` and `geography_id` returns 201 with them in `realized_by`;
  - PATCH `/{ac_id}/applications/{app_id}` returns 200; the omit-vs-null semantics hold;
  - an empty PATCH body gives 422;
  - a bad rationale gives 422, Global gives 422, and an unknown link gives 404;
  - a reviewer gets 403 on PATCH;
  - the log line `application_capability.realization.update` carries old→new values (`caplog`).
- [X] T009 [P] [US1] Write a test for `consistency_hint()`, covering every rationale × TIME combination, in `tests/unit/application/test_cap_analysis_rationale.py`:
  - target + Eliminate gives "TIME says Eliminate";
  - target + Migrate gives "TIME says Migrate";
  - redundant + Invest gives "TIME says Invest";
  - anything else gives None.

### Implementation

- [X] T010 [US1] Add `RealizationCreate.rationale/geography_id` (optional) and a new `RealizationUpdate` (`extra="forbid"`, both optional, at least one field set) in `src/adp/application/app_capability_models.py`.
- [X] T011 [US1] Add a pure `consistency_hint(rationale, time_classification)` in `src/adp/application/cap_analysis.py`, so it passes T009.
- [X] T012 [US1] In `src/adp/application/app_capabilities.py`:
  - add `_validate_geography(geo_id, session)`, which uses the lazy-imported `ostore.geography_level`;
  - extend `add_realization(ac_id, app_id, session, *, rationale=None, geography_id=None)`;
  - add `update_realization(ac_id, app_id, changes: dict, session) -> tuple[old, new]`;
  - make `_apps_by_cap` select `rationale`, `geography_id` and the application's `time_classification`, then resolve the geography (`GeoRef`, via `ostore.geography_index` only when an id is present) and the hint.

  Passes T007.
- [X] T013 [US1] In `src/adp/application/app_capabilities_router.py`:
  - pass the new POST fields through, and add them to the create log line;
  - add `PATCH /{ac_id}/applications/{app_id}`, using `model_fields_set` for omit-vs-null, with log line `application_capability.realization.update` (old→new).

  Passes T008.
- [X] T014 [P] [US1] In `web/src/api/appCapabilities.ts` (the actual home of these types; findings types are in `web/src/api/capAnalysis.ts`):
  - add `Rationale`, `GeoRef`, and `AppRef.rationale/geography/hint`;
  - add `useUpdateRealization(acId)` (PATCH), which invalidates the app-cap detail, the summaries and the findings queries;
  - extend `useAddRealization` with optional fields.
- [X] T015 [P] [US1] Create `web/src/application/realizationRationale.ts` with `RATIONALE_LABEL` and a colour per rationale. *Deviation:* there is no client `consistencyHint()`. The server's hint shows after every save-on-choose refetch (see research R6), so the labels are covered through `RealizationList.test.tsx` and `CapFindingsViews.test.tsx` instead of a separate test file.
- [X] T016 [US1] Write a component test first, in `web/src/application/RealizationList.test.tsx`, covering:
  - rows show the rationale and geography selects;
  - choosing a rationale calls PATCH immediately with `{rationale}`;
  - "Unclassified" sends `{rationale: null}`;
  - choosing a geography sends `{geography_id}`; "Everywhere" sends null;
  - the hint shows when TIME disagrees;
  - the add row sends the optional rationale and geography;
  - readers see text only.
- [X] T017 [US1] Implement `web/src/application/RealizationList.tsx`. The geography options come from `useGeographies()`, with regions before countries and Global omitted (reuse 942's `assessableGeographies`). Replace the "Realized by applications" generic list in `web/src/application/AppCapDetail.tsx` with it.
- [X] T018 [US1] Show the rationale chip and geography on the application's own capability list (`web/src/application/AppCapSummaryList.tsx`), read from the current application's `realized_by` entry. Add a test.

**Checkpoint**: realizations can be classified and scoped in the UI and the API.

## Phase 4: User Story 2 — Overlaps flag only what isn't explained (P1)

**Goal**: overlaps get a derived status and reasons; the Governance tile counts only those needing attention.
**Independent test**: quickstart step 4.

### Tests (write first, must fail)

- [X] T019 [P] [US2] Write engine tests in `tests/unit/application/test_cap_analysis_rationale.py`, building `CapabilitySnapshot`s by hand. They must cover:
  - all unclassified gives `needs_attention` with an `unclassified` reason, and no `no_target`;
  - one redundant gives a `redundant` reason naming the application;
  - all classified with no target gives `no_target`;
  - two targets of different applications, both everywhere, give `competing_targets`;
  - targets in Europe and the Americas give `explained`;
  - a target in Europe and a target in Germany (inside Europe) give `competing_targets`;
  - one application that is target through two application capabilities is not competing;
  - target, transitional, and tactical in Brazil give `explained`;
  - a retired target doesn't count;
  - a dangling geography counts as everywhere;
  - multiple reasons are all listed;
  - ordering is needs attention first, then by name;
  - existing 938 fields are unchanged (`via`).
- [X] T020 [P] [US2] Extend `tests/unit/application/test_cap_analysis_snapshot.py`:
  - the snapshot carries `realizations` attributes and `AppInfo.time_classification/r_strategy`;
  - the geography index is empty and **not queried** when no realization has a geography; count the statements, or check that a fixture without organization tables still works;
  - it is populated when one does.
- [X] T021 [P] [US2] Extend `tests/contract/test_cap_analysis_api.py`: `/analysis/findings` overlaps carry `status`, `reasons` and `applications[].mappings`. Extend `tests/unit/application/test_cap_analysis_not_stored.py`: no `status`, `reasons` or `overlap` columns on any table.

### Implementation

- [X] T022 [US2] In `src/adp/application/cap_analysis_models.py`:
  - add `Mapping`, `OverlapReason` (code Literal) and `RedundantEntry`/`RedundantGroup`;
  - extend `AppVia.mappings`, `OverlapEntry.status/reasons` and `CapabilityFindings.redundant` (default `[]`).
- [X] T023 [US2] In `src/adp/application/cap_analysis.py`:
  - add a `Realization` dataclass;
  - `AppInfo` gains `time_classification` and `r_strategy` (defaulting to None, so existing constructors keep working);
  - `CapabilitySnapshot` gains `realizations` and a `geo_parent`/geography-info mapping (defaulting to empty);
  - add `_scopes_overlap(a, b, snapshot)` (containment both ways; unknown = everywhere);
  - add `_overlap_reasons()`;
  - `findings()` builds mappings, reasons and status, ordering needs attention first.

  Passes T019.
- [X] T024 [US2] In `src/adp/application/cap_analysis_store.py`:
  - select `rationale` and `geography_id` with the realization pairs;
  - select `time_classification` and `r_strategy` into `AppInfo`;
  - call `ostore.geography_index()` only when some realization has a geography.

  Passes T020 and T021.
- [X] T025 [P] [US2] In `web/src/api/application.ts`, add the findings types: `OverlapReason`, `Mapping`, and `OverlapEntry.status/reasons`, plus `applications[].mappings`.
- [X] T026 [US2] Update `web/src/application/CapFindingsViews.test.tsx` first, then `CapFindingsViews.tsx`. The overlaps mode shows:
  - a "Needs attention (n)" section, first, then "Explained (n)";
  - reason chips with application names;
  - each application with its rationale chip, its geography and the hint.
- [X] T027 [US2] Update `web/src/governance/architectureHealth.test.ts` and `ArchitectureHealthTab.test.tsx` first. Then make `architectureHealth.ts` and `ArchitectureHealthTab.tsx` count `status === "needs_attention"` for the Overlaps tile, with "n explained" as the subtext.

**Checkpoint**: classified overlaps move to Explained, and the Governance tile agrees.

## Phase 5: User Story 3 — Redundancy view (P2)

**Goal**: a Redundant tab listing redundant mappings with TIME and 7R context and the hint.
**Independent test**: quickstart step 5.

- [X] T028 [P] [US3] Write engine tests for `redundant` groups in `tests/unit/application/test_cap_analysis_rationale.py`:
  - grouped by business L3, ordered by name;
  - a mapping that reaches no business L3 goes in a last `business: null` group;
  - retired applications are excluded;
  - a single-application capability marked redundant is still listed;
  - entries carry TIME, 7R and the hint;
  - an empty portfolio gives `[]`.
- [X] T029 [US3] Build `redundant` in `findings()` in `src/adp/application/cap_analysis.py` (passes T028). Extend the contract test in `tests/contract/test_cap_analysis_api.py` with a `redundant[]` case.
- [X] T030 [US3] Write the test first, in `web/src/application/CapFindingsViews.test.tsx`, then add `mode="redundant"` to `CapFindingsViews.tsx`:
  - groups and entries with TIME/7R and the hint;
  - a "No redundant mappings." empty state;
  - each entry opens the application capability through `CapabilityNavContext`/`AppCapNavContext`.
- [X] T031 [US3] Add the fourth tab, "Redundant", beside Overlaps, Gaps and Shared in `web/src/application/AppCapabilitiesView.tsx`, and test it.

## Phase 6: User Story 4 — Export and seed (P3)

- [X] T032 [P] [US4] Write the test first, in `tests/unit/export/test_application_arch_serialize.py`: the application capability file has `realizations: [{application_id, rationale, geography}]`, sorted by application id; `realized_by_application_ids` is unchanged; a dangling geography gives null.
- [X] T033 [US4] Implement it in `src/adp/export/application_arch.py`. Extend the existing bulk realization query with `rationale` and `geography_id`, and resolve geographies through one `geography_index` call (no N+1).
- [X] T034 [US4] Add seed phase G to `scripts/seed_retail.py`:
  - Apply Promotions is explained: Store POS target, Commerce Cloud tactical in the Americas;
  - one overlap needs attention (a mapping is left unclassified);
  - one mapping is marked redundant.

  Write it through the store or API helpers the seed already uses. Do **not** run it against the local database.

## Phase 7: Polish & Cross-Cutting

- [X] T035 Run the gates:
  - `.venv/bin/pytest tests/ --ignore=tests/integration -q`;
  - `.venv/bin/ruff check src/ tests/`;
  - `.venv/bin/mypy src/`;
  - `.venv/bin/adp-generate --check`;
  - `cd web && npx tsc --noEmit -p . && npx vitest run`.
- [X] T036 Apply migration 051 to the local database (`alembic upgrade head`), and run downgrade then upgrade. Then walk through quickstart.md with curl and Playwright. Restore every changed rationale and geography to null.
- [X] T037 Add the 943 Recent Changes entry to `CLAUDE.md` by hand (do not use `update-agent-context.sh`; it truncates older entries). Then run `node .gitnexus/run.cjs analyze --index-only` and `detect-changes`. Mark the tasks done here, and add a note to bead ADP-55k.4.

## Dependencies

- Setup (T001–T003) → Foundational (T004–T006) → US1.
- **US2** needs T003 and T006, plus the snapshot changes (T023/T024). It is independent of the US1 UI.
- **US3** needs US2's engine and models (T022/T023).
- **US4** needs T003 and T005.

## Parallel examples

- **Phase 2**: T004 and T006.
- **US1 tests**: T007, T008 and T009 together. Then the frontend tasks T014 and T015 run alongside the backend tasks T010–T013.
- **US2 tests**: T019, T020 and T021 together. T025 runs alongside T023.

## Implementation strategy

The MVP is US1 plus US2, both P1: classify mappings, and stop intended variation being flagged. US3 and US4 follow in the same branch.
