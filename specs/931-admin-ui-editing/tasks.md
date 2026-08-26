# Tasks: Admin UI for Editing Scoring Rubric Weights

**Input**: Design documents from `/specs/931-admin-ui-editing/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓,
quickstart.md ✓

**Tests**: Mandatory (ART-IV).

**Organization**: One cohesive feature, mirroring ADP-SPEC-042's own organization: Foundational
(migration + registry + authz) blocks everything; US1 (edit) and US2 (history/restore) share almost
all the same backend service/router code, so they're implemented together rather than as
independently-shippable slices (matching 042's own precedent — see that spec's tasks.md
Organization note).

## Format: `[ID] [P?] [Story] Description`

## Path Conventions

- Backend: `src/adp/admin/{rubric_registry,rubric_models,rubric_service}.py` (new),
  `src/adp/api/routers/admin_rubrics_router.py` (new), `src/adp/authz/{roles,permissions,
  enforcement}.py` (modified), `src/adp/application/store.py` (modified),
  `src/adp/store/migrations/versions/040_rubric_weight_management.py` (new)
- Frontend: `web/src/api/adminRubrics.ts` (new), `web/src/admin/{ScoringRubricsPage,RubricEditor,
  RubricHistory}.tsx` (new), `web/src/shell/index.ts`, `web/src/ui/AppShell.tsx`, `web/src/App.tsx`
  (modified)
- Tests: `tests/unit/admin/test_rubric_registry.py` (new),
  `tests/unit/application/test_business_value_score.py` (modified),
  `tests/contract/test_admin_rubrics_contract.py` (new),
  `tests/integration/test_admin_rubrics_flow.py` (new, Docker-gated),
  `tests/authz/test_permissions.py` (modified), `web/src/admin/*.test.tsx` (new)

---

## Phase 1: Foundational (Migration + Registry + Authz)

- [X] T001 Create `src/adp/store/migrations/versions/040_rubric_weight_management.py`:
  `rubric_weight_overrides`/`rubric_weight_history` tables, mirroring migration 023's exact shape
  with `weights`/`prior_weights`/`new_weights` as `JSONB` instead of `TEXT`
- [X] T002 [P] Add `ActionType.MANAGE_SCORING_RUBRICS` to `src/adp/authz/roles.py`; update
  `src/adp/authz/permissions.py` (`PERMISSIONS_VERSION` 1.9.0 → 1.10.0, exclude from Enterprise
  Architect's wildcard, add to `REQUIRES_CONFIRMATION`); add the prefix rule to
  `src/adp/authz/enforcement.py`
- [X] T003 [P] Unit tests in `tests/authz/test_permissions.py` (extending existing
  pinned-version/completeness assertions, mirroring the 042/COMPLY-0x precedent for a
  `PERMISSIONS_VERSION` bump): Enterprise Architect lacks `MANAGE_SCORING_RUBRICS`; Platform Admin
  has it
- [X] T004 [P] Create `src/adp/admin/rubric_registry.py` (mirrors `prompt_registry.py`):
  `RubricRegistration` dataclass (`rubric_id`, `display_name`, `dimension_labels`,
  `fallback_provider`, `validate`), `RUBRIC_REGISTRATIONS` tuple with the one `business_value`
  entry, `get_registration()`, `get_effective_weights()` (mirrors `get_effective_prompt()`
  including its fall-back-on-any-error resilience property)
- [X] T005 [P] Unit tests in `tests/unit/admin/test_rubric_registry.py`: the `business_value`
  validator accepts a valid weight set, rejects a wrong dimension count / an out-of-range weight /
  a sum that doesn't total 1.0 (with epsilon tolerance for float representation);
  `get_effective_weights()` falls back to `BUSINESS_VALUE_WEIGHTS` on no-override and on a
  DB-resolution failure alike

**Checkpoint**: Migration applies; permission grants correct; registry/validator/effective-lookup
all correct in isolation.

---

## Phase 2: User Story 1 — Edit rubric weights (Priority: P1)

### Tests (write first — ART-IV)

- [X] T006 [P] [US1] Unit tests in `tests/unit/application/test_business_value_score.py`
  (extending the existing file): `compute_business_value_score()` with an explicit `weights`
  argument uses it instead of `BUSINESS_VALUE_WEIGHTS`; every existing test in this file (no
  `weights` argument) continues to pass unmodified, confirming the default-parameter
  backward-compatibility guarantee
- [X] T007 [P] [US1] Contract tests in `tests/contract/test_admin_rubrics_contract.py` (mirroring
  `test_admin_prompts_contract.py`'s exact shape): list (default + after override), confirm edit
  (valid, invalid-sum 422, missing-confirmation 422, version-conflict 409, unknown-rubric 404),
  permission-denial 403

### Implementation

- [X] T008 [US1] Add optional `weights` parameter to `compute_business_value_score()` in
  `src/adp/application/store.py`; wire `await rubric_registry.get_effective_weights("business_value")` into
  both `get_business_value_assessment` and `upsert_business_value_assessment` before calling it
  (depends on T004; T006 must fail first)
- [X] T009 [US1] Create `src/adp/admin/rubric_models.py` (mirrors `admin/models.py`):
  `RubricView`, `RubricListResponse`, `RubricEditRequest` (with the confirmation_id/weights
  validators), `RubricRestoreRequest`, `RubricChangeResult`, `RubricVersionConflictError`,
  `RubricHistoryEntry`, `RubricHistoryResponse`
- [X] T010 [US1] Create `src/adp/admin/rubric_service.py` (mirrors `admin/service.py`):
  `list_rubrics()`, `save_weights()` (validates via the registration's own `validate()` before
  writing, same single-transaction override+history pattern), `RubricVersionConflict`,
  `UnknownRubricError` (depends on T004, T009; T007 must fail first)
- [X] T011 [US1] Create `src/adp/api/routers/admin_rubrics_router.py` (mirrors
  `admin_prompts_router.py`): `GET ""`, `POST "/{rubric_id}/confirm"`, gated by
  `require_action_dep(ActionType.MANAGE_SCORING_RUBRICS)` (depends on T010)
- [X] T012 [US1] Register the new router in `src/adp/api/app.py` (mirrors
  `admin_prompts_router.router` registration)

**Checkpoint**: T006/T007 pass; every existing business-value-assessment test still passes
unmodified.

---

## Phase 3: User Story 2 — History + restore (Priority: P2)

### Tests (write first — ART-IV)

- [X] T013 [P] [US2] Contract tests in `tests/contract/test_admin_rubrics_contract.py`: history
  returns newest-first; restore applies the identical confirmation/version-conflict gate as edit,
  and correctly copies a chosen history row's `new_weights` forward as a new `change_type="restore"`
  entry

### Implementation

- [X] T014 [US2] Add `get_history()`/`restore_weights()`/`HistoryEntryNotFoundError` to
  `src/adp/admin/rubric_service.py` (mirrors `service.py`'s own restore logic) (depends on T010;
  T013 must fail first)
- [X] T015 [US2] Add `GET "/{rubric_id}/history"` and `POST "/{rubric_id}/restore/{history_id}"` to
  `admin_rubrics_router.py` (depends on T014)

**Checkpoint**: T013 passes.

---

## Phase 4: Frontend

### Tests (write first — ART-IV)

- [X] T016 [P] Component tests in `web/src/admin/RubricEditor.test.tsx` (new — no existing
  `PromptEditor.test.tsx` to mirror, research.md D6): renders current weights, blocks Save when the
  sum isn't ~100%, shows the confirmation dialog, handles a 409 conflict by offering to reload
- [X] T017 [P] Component tests in `web/src/admin/ScoringRubricsPage.test.tsx` (new): lists
  registered rubrics, selecting one shows Edit/History tabs

### Implementation

- [X] T018 [P] Create `web/src/api/adminRubrics.ts` (mirrors `adminPrompts.ts`): types + TanStack
  Query hooks (`useRubrics`, `useRubricHistory`, `useConfirmRubricEdit`,
  `useRestoreRubricVersion`)
- [X] T019 [US1] Create `web/src/admin/RubricEditor.tsx` (mirrors `PromptEditor.tsx`'s
  confirmation/version-conflict mechanics; a numeric input per dimension + a live running-sum
  indicator instead of a `<textarea>`, per research.md D6) (depends on T018; T016 must fail first)
- [X] T020 [P] [US2] Create `web/src/admin/RubricHistory.tsx` (mirrors `PromptHistory.tsx`)
  (depends on T018)
- [X] T021 Create `web/src/admin/ScoringRubricsPage.tsx` (mirrors `AdminPage.tsx`) (depends on
  T019, T020; T017 must fail first)
- [X] T022 Add `"scoring-rubrics"` to `AppView` (`web/src/shell/index.ts`); add the nav entry +
  `TITLES` entry to the `ADMIN` array in `web/src/ui/AppShell.tsx`; add the `case
  "scoring-rubrics":` render branch to `web/src/App.tsx` (depends on T021)

**Checkpoint**: T016/T017 pass; the new nav entry appears only for `platform_admin`.

---

## Phase 5: Polish

- [X] T023 [P] Run `ruff check src/adp/`, `mypy src/adp/`, and the full backend test suite
  (`pytest tests/ --ignore=tests/integration -q`) — confirm zero regressions
- [X] T024 [P] Run `tsc` and the full frontend test suite (`npm run test:run` in `web/`) — confirm
  zero regressions
- [X] T025 Walk through every scenario in `quickstart.md` against a real local Postgres + running
  backend with migration 040 applied; confirm each scenario's stated expectation holds (including
  Scenario 4's actual computed `weighted_average` — recompute by hand and compare, not just eyeball
  it), then clean up any created test data afterward
- [X] T026 Live-verify the new "Scoring Rubrics" nav entry/screen via a running frontend dev server
  or Playwright, including the confirmation dialog and the sum-validation UI behavior

---

## Dependencies & Execution Order

- Phase 1 (Foundational) blocks everything.
- Phase 2 (US1) blocks Phase 3 (US2) — both live in the same new service/router files.
- Phase 4 (Frontend) depends on Phase 2 + 3 (needs the real API contract to build against).
- Phase 5 depends on all prior phases.

## Notes

- Every new backend file has a named ADP-SPEC-042 sibling it mirrors structurally (research.md D1);
  deviations are only where the data shape genuinely differs (JSONB weights + a per-rubric
  validator vs. free text).
- `[Story]` labels map to spec.md's two user stories for traceability.
