# Tasks: Application Type Grouping Dimension

**Input**: Design documents from `/specs/929-application-type-cots/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, quickstart.md ✓

**Tests**: Mandatory (ART-IV). Test tasks appear before their implementation counterparts.

**Organization**: One cohesive feature — User Story 1 (settable field) and User Story 2 (groupable
dimension) are both P1 and interdependent (neither delivers the bead's value alone), so they are
implemented together rather than as two independently-shippable slices.

## Format: `[ID] [P?] [Story] Description`

## Path Conventions

- Backend: `src/adp/application/models.py`, `src/adp/application/store.py`,
  `src/adp/application/router.py`, `src/adp/export/application_arch.py`,
  `src/adp/store/migrations/versions/039_application_type.py` (new)
- Frontend: `web/src/api/application.ts`, `web/src/application/ApplicationForm.tsx`,
  `web/src/application/ApplicationDetail.tsx`, `web/src/portfolio/groupApplications.ts`
- Tests: `tests/unit/application/` (model), `tests/contract/test_apm_techfit_api.py` (router),
  `tests/unit/export/test_application_arch_serialize.py`,
  `web/src/portfolio/groupApplications.test.ts`

---

## Phase 1: Foundational (Migration + Model)

- [X] T001 Create `src/adp/store/migrations/versions/039_application_type.py`: nullable `TEXT`
  column + `CHECK` constraint + filter index on `applications`, mirroring migration `016`'s
  `hosting_model` shape (`down_revision="038"`)
- [X] T002 [P] Add `ApplicationType = Literal["custom", "cots", "saas", "legacy"]` and the
  `application_type` field to `Application`/`ApplicationCreate`/`ApplicationUpdate` in
  `src/adp/application/models.py`
- [X] T003 [P] Unit tests in `tests/unit/application/` (new or existing model test file):
  `application_type` accepts all 4 valid values, rejects an invalid one (422 at the API layer,
  `ValidationError` at the model layer), defaults to `None` when omitted

**Checkpoint**: Migration applies cleanly (upgrade + downgrade); model validates correctly.

---

## Phase 2: User Story 1 — Set/clear/filter-reject via the API (Priority: P1)

### Tests (write first — ART-IV)

- [X] T004 [P] [US1] Contract tests in `tests/contract/test_apm_techfit_api.py` (mirroring
  `test_filter_by_hosting_model`/`test_invalid_hosting_model_rejected` exactly): create with each
  of the 4 values, update clears with explicit `null`, invalid value → 422, `GET
  ?application_type=cots` filters correctly
- [X] T005 [P] [US1] Unit test in `tests/unit/export/test_application_arch_serialize.py`:
  `_serialize_application()` includes `application_type` (both a set value and `None`)

### Implementation

- [X] T006 [US1] Add `application_type` column to `_applications` table def in
  `src/adp/application/store.py` (depends on T001)
- [X] T007 [US1] Add `application_type` to `_row_to_application`, `create_application`,
  `update_application`'s field-clear loop, and `list_applications`'s optional filter (depends on
  T002, T006)
- [X] T008 [US1] Add `application_type: Optional[str] = Query(default=None)` query param to `GET
  /api/v1/applications` in `src/adp/application/router.py`, passed through to
  `list_applications()` (depends on T007)
- [X] T009 [US1] Add `"application_type": app.application_type` to
  `_serialize_application()` in `src/adp/export/application_arch.py` (depends on T002)

**Checkpoint**: T004/T005 pass; every existing `hosting_model`/APM test still passes unmodified.

---

## Phase 3: User Story 2 — Group/filter by type on the Application Portfolio screen (Priority: P1)

### Tests (write first — ART-IV)

- [X] T010 [P] [US2] Unit tests in `web/src/portfolio/groupApplications.test.ts`:
  `groupByApplicationType` buckets in fixed Custom→COTS→SaaS→Legacy order, untyped apps land in
  `unclassified`; `groupApplications("application_type", ...)` dispatches correctly

### Implementation

- [X] T011 [P] [US2] Add `ApplicationType` type + `application_type` field to `Application`/
  `ApplicationCreate` interfaces in `web/src/api/application.ts`
- [X] T012 [US2] Add `"application_type"` to `Dimension`, `DIMENSION_LABELS`, `ALL_DIMENSIONS`, and
  a `groupByApplicationType()` function + switch-case in
  `web/src/portfolio/groupApplications.ts` (depends on T011; T010 must fail first)
- [X] T013 [P] [US2] Add an "Application Type" dropdown to `web/src/application/ApplicationForm.tsx`
  (4 options + "— none —", matching the existing Hosting Model dropdown's shape) (depends on T011)
- [X] T014 [P] [US2] Add a conditional read line for `application_type` to
  `web/src/application/ApplicationDetail.tsx` (matching `pace_layer`'s own conditional-render
  convention) (depends on T011)

**Checkpoint**: Portfolio screen's Group By/Then By/Filter by dropdowns each show 6/9/9 options;
same-dimension cross-tab rule still holds; T010 passes.

---

## Phase 4: Polish

- [X] T015 [P] Run `ruff check src/adp/`, `mypy src/adp/`, and the full backend test suite
  (`pytest tests/ --ignore=tests/integration -q`) — confirm zero regressions
- [X] T016 [P] Run `tsc` and the full frontend test suite (`npm run test:run` in `web/`) — confirm
  zero regressions
- [X] T017 Walk through every scenario in `quickstart.md` against a real local Postgres + running
  backend with migration 039 applied; confirm each scenario's stated expectation holds, then clean
  up any created test application afterward
- [X] T018 Live-verify Scenario 5 (Portfolio screen) via a running frontend dev server or
  Playwright

---

## Dependencies & Execution Order

- Phase 1 (Foundational) blocks everything.
- Phase 2 (US1) and Phase 3 (US2) can proceed in parallel once Phase 1 is done (different files:
  backend store/router/export vs. frontend api/form/detail/portfolio), but both must complete
  before Phase 4.
- Within each phase: tests before implementation (ART-IV).

## Notes

- No task retires or duplicates existing `hosting_model` code — every task either adds a new
  parallel field/branch or extends an existing loop/switch with one more case.
- `[Story]` labels map to spec.md's two P1 user stories for traceability.
