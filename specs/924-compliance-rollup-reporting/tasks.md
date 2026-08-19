# Tasks: Compliance Rollup Reporting

**Input**: Design documents from `/specs/924-compliance-rollup-reporting/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Mandatory for all ADP features (ART-IV). Test tasks appear before their implementation counterparts in every phase and MUST be verified to fail before implementation begins.

**Organization**: Grouped by user story (spec.md) to enable independent implementation and testing of each. Both stories share one Foundational bucketing primitive (research.md D1) but are otherwise independent — US1 (framework rollup) and US2 (platform summary) touch disjoint query functions, disjoint router endpoints, and disjoint frontend files.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 / US2, per spec.md's priorities (P1/P2)

## Path Conventions

Single project, existing package/files only — no new package, no new migration (plan.md's Structure Decision):
- Backend: `src/adp/compliance/{models,store,router}.py` (all already exist, extended)
- Backend tests: `tests/unit/compliance/test_rollup.py` (new), `tests/contract/test_compliance_rollup_api.py` (new)
- Frontend: `web/src/api/compliance.ts`, `web/src/compliance/FrameworkDetail.tsx`, `web/src/overview/OverviewPage.tsx` (all already exist, extended)

---

## Phase 1: Setup

- [X] T001 [P] Create empty test file stub `tests/unit/compliance/test_rollup.py` (module docstring referencing COMPLY-04/spec.md, imports of the not-yet-defined `EntityStatusCounts`/`FrameworkCoverageRollup`/`ComplianceSummaryResponse` from `adp.compliance.models` and `_bucket_entities_by_status`/`get_framework_coverage_rollup`/`get_compliance_summary` from `adp.compliance.store` — expected to fail to import until Foundational/US1/US2 land)
- [X] T002 [P] Create empty test file stub `tests/contract/test_compliance_rollup_api.py` (mirroring `tests/contract/test_compliance_mappings_api.py`'s SQLite fixture shape: `cstore._metadata.create_all`, seeded mirror-table rows)

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: No user-story work can begin until this phase is complete — both stories call the same bucketing primitive this phase creates.

- [X] T003 [P] Add `EntityStatusCounts` model (`compliant_count`/`partial_count`/`non_compliant_count`/`not_assessed_count`/`not_applicable_count`, all `int`) to `src/adp/compliance/models.py` (data-model.md)
- [X] T004 [P] Foundational unit tests in `tests/unit/compliance/test_rollup.py` for `_bucket_entities_by_status()`: an empty row list produces all-zero counts; multiple entities each with multiple mapped-control rows land in the correct bucket per `compute_compliance_status()`'s own decision table (reusing COMPLY-03's function unmodified); two different `target_id`s of the same `target_type` are correctly kept as separate entities, never merged (research.md D1)
- [X] T005 Implement `_bucket_entities_by_status(rows: list[tuple[MappingTargetType, str, ComplianceStatus]]) -> EntityStatusCounts` in `src/adp/compliance/store.py`: group by `(target_type, target_id)`, call `compute_compliance_status()` once per group, tally into `EntityStatusCounts` — make T004 pass (depends on T003)

**Checkpoint**: Foundation ready — the shared bucketing primitive is correct and independently tested. User-story implementation can now begin.

---

## Phase 3: User Story 1 - See a framework's compliance coverage at a glance (Priority: P1) 🎯 MVP

**Goal**: For a given `RegulatoryFramework`, show a live count of entities at each compliance-status bucket (scoped to that framework's own controls), plus its estate-wide obligation status as a separate line if one exists.

**Independent Test**: Map several controls from one framework to several entities with a mix of compliance statuses, then view that framework's coverage rollup and confirm the counts match (spec.md US1 Acceptance Scenarios; quickstart.md Scenarios 1–4, 7).

### Tests for User Story 1 (MANDATORY — ART-IV, write first, confirm failing)

- [X] T006 [P] [US1] Unit tests in `tests/unit/compliance/test_rollup.py` for `get_framework_coverage_rollup()` (SQLite fixture, mirroring `test_compliance_status.py`'s dispatch-test style): a mix of five entities across the five statuses buckets correctly (FR-001/002, spec.md US1 AS1); an entity with controls mapped from two different frameworks counts toward each framework's own bucket independently, never blended (FR-001, US1 AS2, quickstart Scenario 2); an estate-wide (`organization`-scoped) mapping produces `organization_status` as its own field, never counted in `entity_counts` (FR-003, US1 AS3); a framework with zero mapped controls returns every bucket at zero and `organization_status is None` (FR-008, Edge Cases, quickstart Scenario 7); an unknown `framework_id` returns `None`
- [X] T007 [P] [US1] Contract tests in `tests/contract/test_compliance_rollup_api.py` for `GET /api/v1/compliance/frameworks/{framework_id}/rollup`: 200 with correct `entity_counts`/`organization_status`; 404 for an unknown framework; an Application-targeted entity is excluded from every count for a caller lacking `READ_APPLICATION_GOVERNANCE`, included for one who holds it (FR-007, US1 AS4, quickstart Scenario 4 — mirror `tests/authz/test_enforcement.py`'s role-overridden `TestClient` pattern for the permission-denied case)

### Implementation for User Story 1

- [X] T008 [P] [US1] Add `FrameworkCoverageRollup` model (`framework_id: str`, `entity_counts: EntityStatusCounts`, `organization_status: ComplianceStatus | None`) to `src/adp/compliance/models.py` (data-model.md; depends on T003)
- [X] T009 [US1] Implement `_framework_entity_rows(framework_id, session)` (JOIN each of the four entity-targeted mapping tables to `controls` on `control_id`, filtered by `controls.framework_id`, unioned in Python) and `_framework_organization_rows(framework_id, session)` (same JOIN shape against `control_organization_mapping`) in `src/adp/compliance/store.py` (research.md D3)
- [X] T010 [US1] Implement `get_framework_coverage_rollup(framework_id, include_application, session) -> FrameworkCoverageRollup | None` in `src/adp/compliance/store.py`: `None` if the framework doesn't exist; else drop `APPLICATION`-tagged rows from T009's entity rows when `include_application` is `False` (research.md D2), call `_bucket_entities_by_status()` (T005) for `entity_counts`, and aggregate the organization rows (filtered the same way) through `compute_compliance_status()` directly for `organization_status` (`None` if that list is empty) — make T006 pass (depends on T005, T008, T009)
- [X] T011 [US1] Implement `GET /api/v1/compliance/frameworks/{framework_id}/rollup` in `src/adp/compliance/router.py`: `user: AuthenticatedUser = Depends(get_current_user)` (mirrors `list_control_mappings`'s existing dependency), compute `include_application = is_permitted(user.role, ActionType.READ_APPLICATION_GOVERNANCE)`, call T010, 404 if `None` — make T007 pass (depends on T010)
- [X] T012 [P] [US1] Add `EntityStatusCounts`/`FrameworkCoverageRollup` TS types and a `useFrameworkRollup(frameworkId)` hook to `web/src/api/compliance.ts` (mirrors `useStrategySummary()`'s single-`useQuery` shape in `web/src/api/strategy.ts`)
- [X] T013 [US1] Add a rollup display block to `web/src/compliance/FrameworkDetail.tsx`: the five status-bucket counts, plus the estate-wide obligation line only when `organization_status` is not `null` (depends on T012)
- [X] T014 [P] [US1] Component tests for the rollup display block in `web/src/compliance/FrameworkDetail.test.tsx`: renders all five bucket counts; renders the estate-wide obligation line only when present; renders nothing extra when absent

**Checkpoint**: User Story 1 fully functional and independently testable — quickstart.md Scenarios 1–4, 7.

---

## Phase 4: User Story 2 - See the platform's overall compliance posture without opening Compliance (Priority: P2)

**Goal**: A platform-wide summary — total framework count, overall coverage percentage, and at-risk entity count — reachable from the Overview dashboard.

**Independent Test**: With a mix of frameworks and mapped entities across several compliance statuses, load the Overview dashboard and confirm the summary card's figures match direct inspection of the underlying data (spec.md US2 Acceptance Scenarios; quickstart.md Scenarios 5, 6, 8).

### Tests for User Story 2 (MANDATORY — ART-IV, write first, confirm failing)

- [X] T015 [P] [US2] Unit tests in `tests/unit/compliance/test_rollup.py` for `get_compliance_summary()`: `framework_count` matches the number of registered frameworks (US2 AS1); `coverage_percent` computed correctly from a mix of entities' *overall* (cross-framework) derived statuses (FR-004, US2 AS2); `coverage_percent is None` when zero entities anywhere have any mapped control (FR-009, Edge Cases, quickstart Scenario 6 — never a bare `0.0`); `at_risk_count` counts entities whose overall status is Non-Compliant or Partial (US2 AS3)
- [X] T016 [P] [US2] Contract tests in `tests/contract/test_compliance_rollup_api.py` for `GET /api/v1/compliance/summary`: 200 with correct figures; an Application-targeted entity is excluded from every figure for a caller lacking `READ_APPLICATION_GOVERNANCE` (FR-007)

### Implementation for User Story 2

- [X] T017 [P] [US2] Add `ComplianceSummaryResponse` model (`framework_count: int`, `coverage_percent: float | None`, `at_risk_count: int`) to `src/adp/compliance/models.py` (data-model.md)
- [X] T018 [US2] Implement `_estate_entity_rows(session)` in `src/adp/compliance/store.py`: identical JOIN shape to `_framework_entity_rows` (T009) but with no `framework_id` filter at all — every entity-targeted mapping row across the whole estate (research.md D3)
- [X] T019 [US2] Implement `get_compliance_summary(include_application, session) -> ComplianceSummaryResponse` in `src/adp/compliance/store.py`: `framework_count` via a plain count query on `regulatory_frameworks`; drop `APPLICATION`-tagged rows from T018's rows when `include_application` is `False`; call `_bucket_entities_by_status()` (T005); `coverage_percent = None` if the total entity count is 0, else `100 * compliant_count / total`; `at_risk_count = non_compliant_count + partial_count` — make T015 pass (depends on T005, T017, T018)
- [X] T020 [US2] Implement `GET /api/v1/compliance/summary` in `src/adp/compliance/router.py`, same `include_application` permission wiring as T011 — make T016 pass (depends on T019)
- [X] T021 [P] [US2] Add `ComplianceSummaryResponse` TS type and a `useComplianceSummary()` hook to `web/src/api/compliance.ts`
- [X] T022 [US2] Add a `"compliance"` entry to `OverviewPage.tsx`'s `DOMAINS` array in `web/src/overview/OverviewPage.tsx`: mini-stats for framework count / coverage % / at-risk count, `shield` icon (already used for Compliance's own nav entry), deep-link tile navigating to the `"compliance"` view (mirrors the Strategy card's shape exactly) (depends on T021)
- [X] T023 [P] [US2] Tests for the new Compliance card in `web/src/overview/OverviewPage.test.tsx`, mirroring the existing "OverviewPage: Strategy domain card" describe block: renders the three figures; the deep-link tile navigates to `"compliance"`, not `"governance"` (FR-005, quickstart Scenario 8)

**Checkpoint**: Both user stories independently functional.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [X] T024 [P] Manually run quickstart.md's 8 scenarios against a running local stack (`ADP_AUTH_ENABLED=false`); Scenario 4/9's permission-denied case is exercised via `tests/authz`'s role-overridden `TestClient` (T007/T016) rather than curl, matching this session's own established precedent (no dev-mode `X-Role` header exists)
- [X] T025 Run the full regression suite: `pytest tests/ --ignore=tests/integration -q`, `ruff check src/`, `mypy src/`, `cd web && npx vitest run && npx tsc --noEmit` — confirm no regressions and no new lint/type errors
- [X] T026 Confirm `adp-generate --check` is clean (schema drift gate)
- [X] T027 Replace the auto-generated `924-compliance-rollup-reporting: Planned...` stub entries in `CLAUDE.md` (Active Technologies + Recent Changes) with a proper hand-written implementation narrative at commit time, mirroring `specs/915-objective-progress-tracking/tasks.md`'s own T038 precedent

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS both user stories (both call `_bucket_entities_by_status()`, T005).
- **User Stories (Phase 3–4)**: Both depend on Foundational only. **US1 and US2 are independent of each other** — different query functions (`_framework_entity_rows`/`_framework_organization_rows` vs. `_estate_entity_rows`), different store functions, different router endpoints, different frontend files (`FrameworkDetail.tsx` vs. `OverviewPage.tsx`). Either can be built first, or both in parallel by different contributors.
- **Polish (Phase 5)**: Depends on both user stories being complete.

### Within Each User Story

- Tests written and confirmed failing (import error, or wrong/missing behavior) before implementation (ART-IV).
- Row-fetch queries before the store function that composes them; store function before the router endpoint; backend endpoint before the frontend hook that calls it; hook before the component that uses it.
- Story complete before moving to the next priority (though, unlike this session's prior single-function features, US1 → US2 here has no code-level ordering constraint — priority order is a delivery-sequencing choice, not a dependency).

### Parallel Opportunities

- T001 and T002 (Setup) can run in parallel.
- T003 and T004 (Foundational: model + its own test) can be drafted in parallel, though T004 will fail to import until T003 lands.
- Once Foundational (T003–T005) is complete, **all of US1 (Phase 3) and US2 (Phase 4) can proceed in parallel** — they share no file except `src/adp/compliance/models.py` (T008 vs. T017) and `store.py` (T009/T010 vs. T018/T019), which are additive, non-overlapping edits to those files and can be sequenced by a single contributor without conflict, or coordinated across two.
- Within US1: T006/T007 (tests) in parallel; T012 (frontend types/hook) in parallel with backend implementation (T009–T011) since it only needs the *contract*, not the running backend, to be drafted against.
- Within US2: same pattern — T015/T016 in parallel; T021 in parallel with T018–T020.

---

## Parallel Example: Foundational Phase

```bash
# Launch Foundational's model and its test together (test will 404/ImportError until the model lands, which is expected — confirms the "before" half of ART-IV's red/green cycle):
Task: "Add EntityStatusCounts model to src/adp/compliance/models.py"
Task: "Foundational unit tests for _bucket_entities_by_status() in tests/unit/compliance/test_rollup.py"
```

## Parallel Example: US1 + US2 Together (post-Foundational)

```bash
# Two contributors, or one contributor working both in sequence without cross-dependency:
Task: "US1 — framework rollup: T006/T007 tests, then T008–T014 implementation"
Task: "US2 — platform summary: T015/T016 tests, then T017–T023 implementation"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks both stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: An architect can view any framework's live coverage rollup — the higher-priority, more load-bearing capability per spec.md's own prioritization (US1 "Why this priority": "the entire reason a derived status exists... the more load-bearing capability").
5. Deploy/demo if ready — US2's summary card is a compact derivative view of the same underlying data and can genuinely ship later without US1 being incomplete.

### Incremental Delivery

1. Complete Setup + Foundational → shared bucketing primitive ready.
2. Add User Story 1 → test independently → deploy/demo (MVP!).
3. Add User Story 2 → test independently → deploy/demo.
4. Polish → quickstart walked, full suite green, narrative committed.

### Parallel Team Strategy

With two contributors: both complete Setup + Foundational together, then one takes US1 and the other US2 — genuinely independent from that point on (no shared file conflict beyond additive edits to `models.py`/`store.py`, easily sequenced).

---

## Notes

- [P] tasks = different files/assertions, no dependency on an incomplete task.
- [Story] label maps task to specific user story for traceability.
- This feature has no schema, migration, or new `ActionType` — Foundational is deliberately light.
- Verify each story's tests fail (import error or wrong result) before implementing that story.
- Commit after each task or logical group.
- Stop at any checkpoint to validate a story independently.
