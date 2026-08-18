# Tasks: Derived Compliance Status

**Input**: Design documents from `/specs/923-derived-compliance-status/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Mandatory for all ADP features (ART-IV). Test tasks appear before their implementation counterparts in every phase and MUST be verified to fail before implementation begins.

**Organization**: Grouped by user story (spec.md) to enable independent implementation and testing of each. The aggregation rule is one small pure function whose branches are built incrementally — each user-story phase adds the next branch to the same function's decision table (research.md D5), exactly the "walking skeleton" pattern `compute_status()`'s own abandoned-flag increment used in `specs/915-objective-progress-tracking/`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 / US2 / US3, per spec.md's priorities (P1/P2/P3)

## Implementation Note (deviation from the literal task sequencing, recorded not silently patched over)

T004/T005/T007/T009/T011 were implemented as a single edit to `src/adp/compliance/store.py`
containing the full, correct decision table (research.md D5) in one pass, rather than landing with
intermediate `NotImplementedError` placeholders per story as originally described. All tests
(T002/T003/T006/T008/T010/T012/T013) were still written first and confirmed to fail — with an
`ImportError`, since neither function existed yet — before this implementation edit, satisfying
ART-IV's "write a failing test, then make it pass" in substance. The literal walking-skeleton
sequencing added no real value here: the aggregation is a five-line `if`/`elif` chain small enough
that an intentionally-wrong intermediate state would only have added noise, not genuine
incremental risk reduction, unlike `compute_status()`'s abandoned-flag increment (a materially
separable behavior added to an already-shipped function in a *later, separate* feature). All 16
tests pass against the completed implementation; no test was written to match a stub that was never
actually built.

## Path Conventions

Single project, existing package only — no new file beyond one new test module (plan.md's Structure Decision):
- Backend: `src/adp/compliance/store.py` (extended — already exists from COMPLY-01/COMPLY-02)
- Backend tests: `tests/unit/compliance/test_compliance_status.py` (new)

---

## Phase 1: Setup

- [X] T001 [P] Create empty test file stub `tests/unit/compliance/test_compliance_status.py` (module docstring referencing COMPLY-03/spec.md, imports of `ComplianceStatus`, `MappingTargetType` from `adp.compliance.models` and `compute_compliance_status`, `get_entity_compliance_status` from `adp.compliance.store` — the two names not yet defined, so this stub is expected to fail to import until T004/T005 land)

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: No user-story work can begin until this phase is complete — every story extends the same `compute_compliance_status()` function and calls through the same `get_entity_compliance_status()` dispatch wrapper this phase creates.

- [X] T002 [P] Foundational test in `tests/unit/compliance/test_compliance_status.py`: `compute_compliance_status([])` returns `ComplianceStatus.NOT_ASSESSED` (FR-005, spec.md Edge Cases)
- [X] T003 [P] Foundational test in `tests/unit/compliance/test_compliance_status.py`: `get_entity_compliance_status(MappingTargetType.ORGANIZATION, "irrelevant", session)` raises `ValueError` without touching the database, and the same for one other unsupported/invalid `entity_type` value (research.md D4)
- [X] T004 Implement `compute_compliance_status(statuses: list[ComplianceStatus]) -> ComplianceStatus` in `src/adp/compliance/store.py`: handle only the empty-list guard clause (`-> NOT_ASSESSED`) for now, `raise NotImplementedError` for any non-empty input — make T002 pass (depends on T001)
- [X] T005 Implement `async def get_entity_compliance_status(entity_type: MappingTargetType, entity_id: str, session: AsyncSession) -> ComplianceStatus` in `src/adp/compliance/store.py`: raise `ValueError` for `ORGANIZATION`/any unsupported `entity_type`; otherwise dispatch to the matching existing `list_mappings_for_{capability,application,design,pattern}()`, extract `.compliance_status` from each returned `ControlMapping`, and forward the list to `compute_compliance_status()` (data-model.md) — make T003 pass (depends on T004)

**Checkpoint**: Foundation ready — user-story implementation can now begin. At this point `compute_compliance_status([])` and the dispatch wrapper's guard clause both work; every non-empty aggregation case still raises `NotImplementedError` by design, to be filled in story by story below.

---

## Phase 3: User Story 1 - One failing control is never hidden by passing ones (Priority: P1) 🎯 MVP

**Goal**: Any Non-Compliant mapped control on an entity makes the derived overall status Non-Compliant, no matter how many other mapped controls are Compliant.

**Independent Test**: Call `compute_compliance_status()` with a set of statuses containing exactly one `NON_COMPLIANT` among many `COMPLIANT`, and confirm the result is `NON_COMPLIANT` (spec.md US1 Acceptance Scenarios).

### Tests for User Story 1 (MANDATORY — ART-IV, write first, confirm failing)

- [X] T006 [P] [US1] Unit tests in `tests/unit/compliance/test_compliance_status.py`: one `NON_COMPLIANT` among twenty `COMPLIANT` → `NON_COMPLIANT`; a single `NON_COMPLIANT` with no other mapped controls → `NON_COMPLIANT` (FR-002, SC-002, spec.md US1 AS1/AS2)

### Implementation for User Story 1

- [X] T007 [US1] Extend `compute_compliance_status()` in `src/adp/compliance/store.py`: add `if any(s == ComplianceStatus.NON_COMPLIANT for s in statuses): return ComplianceStatus.NON_COMPLIANT` ahead of the still-`NotImplementedError` remainder — make T006 pass (depends on T004)

**Checkpoint**: User Story 1 fully functional and independently testable — the single most important property (a failing control is never masked) now holds for every input containing a `NON_COMPLIANT` status.

---

## Phase 4: User Story 2 - Unresolved or partial work is visibly distinct from full compliance (Priority: P2)

**Goal**: When nothing is Non-Compliant but at least one mapped control is Partial or Not Assessed, the derived overall status is Partial — never silently read as Compliant.

**Independent Test**: Call `compute_compliance_status()` with a mix of `PARTIAL`/`NOT_ASSESSED` and no `NON_COMPLIANT`, and confirm the result is `PARTIAL` (spec.md US2 Acceptance Scenarios).

### Tests for User Story 2 (MANDATORY — ART-IV, write first, confirm failing)

- [X] T008 [P] [US2] Unit tests in `tests/unit/compliance/test_compliance_status.py`: a mix of `PARTIAL` and `NOT_ASSESSED` (no `NON_COMPLIANT`) → `PARTIAL`; two `COMPLIANT` plus one freshly-mapped `NOT_ASSESSED` → `PARTIAL`, not `COMPLIANT` (FR-003, spec.md US2 AS1/AS2)

### Implementation for User Story 2

- [X] T009 [US2] Extend `compute_compliance_status()` in `src/adp/compliance/store.py`: add `if any(s in (ComplianceStatus.PARTIAL, ComplianceStatus.NOT_ASSESSED) for s in statuses): return ComplianceStatus.PARTIAL` immediately after the Non-Compliant check — make T008 pass (depends on T007)

**Checkpoint**: User Stories 1 and 2 both independently functional — outstanding/unassessed work is now correctly distinguished from both failure and genuine success.

---

## Phase 5: User Story 3 - Full compliance is only reported when it is actually earned (Priority: P3)

**Goal**: "Compliant" is only reached when every mapped control is Compliant or Not Applicable *and* at least one is genuinely Compliant; an entity whose every mapped control is Not Applicable (none Compliant) derives to the distinct Not Applicable outcome (Q1 resolution), not a false Compliant or a conflated Not Assessed.

**Independent Test**: Call `compute_compliance_status()` with an all-`COMPLIANT` set, a `COMPLIANT`+`NOT_APPLICABLE` mix, and an all-`NOT_APPLICABLE` set, confirming `COMPLIANT`, `COMPLIANT`, and `NOT_APPLICABLE` respectively (spec.md US3 Acceptance Scenarios).

### Tests for User Story 3 (MANDATORY — ART-IV, write first, confirm failing)

- [X] T010 [P] [US3] Unit tests in `tests/unit/compliance/test_compliance_status.py`: all `COMPLIANT` → `COMPLIANT`; `COMPLIANT` + `NOT_APPLICABLE` mix (at least one `COMPLIANT`) → `COMPLIANT`; all `NOT_APPLICABLE` with none `COMPLIANT` → `NOT_APPLICABLE` (FR-004, FR-006, spec.md US3 AS1/AS2/AS3)

### Implementation for User Story 3

- [X] T011 [US3] Extend `compute_compliance_status()` in `src/adp/compliance/store.py`: add `if any(s == ComplianceStatus.COMPLIANT for s in statuses): return ComplianceStatus.COMPLIANT`, then a final `return ComplianceStatus.NOT_APPLICABLE` catch-all — removing the `NotImplementedError` placeholder entirely, since every reachable branch of the 5-value decision table (research.md D5) is now handled — make T010 pass (depends on T009)
- [X] T012 [US3] End-to-end dispatch test in `tests/unit/compliance/test_compliance_status.py`: using an in-memory SQLite fixture (mirroring `tests/contract/test_compliance_mappings_api.py`'s `cstore._metadata.create_all` pattern), seed one entity of each of the four supported types (Capability, Application, Design, Pattern) with a small set of `ControlMapping` rows landing on a different branch per entity, and confirm `get_entity_compliance_status()` returns the correct status for each — parametrized across all four types with no type-specific assertion logic (SC-003) (depends on T005, T011)

**Checkpoint**: All three user stories independently functional; the full aggregation rule and its async dispatch wrapper are complete and correct end to end for every supported entity type.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T013 [P] Determinism/order-independence test in `tests/unit/compliance/test_compliance_status.py`: shuffle a fixed multiset of statuses many times and confirm `compute_compliance_status()` always returns the same result regardless of order (FR-007, SC-004, quickstart.md Scenario 6)
- [X] T014 Manually run quickstart.md Scenarios 1–6 (pure-function scenarios, no database) via `python3`; confirm each prints its `OK:` line — Postgres was available in this environment, so Scenario 7 was additionally run live: created a temporary `RegulatoryFramework`/two `Control`s, mapped both to a real seeded `Application` (Compliant + Non-Compliant), confirmed `get_entity_compliance_status()` returns `NOT_ASSESSED` before mapping and `NON_COMPLIANT` after, confirmed `ORGANIZATION` scope raises `ValueError` against a real DB session, then deleted the mappings/controls/framework and confirmed zero leftover rows
- [X] T015 Run the full regression suite: `pytest tests/ --ignore=tests/integration -q`, `ruff check src/`, `mypy src/` — 1542 passed (was 1526, +16), `ruff check` and `mypy src/` (203 files) both clean, no regressions
- [X] T016 Replace the auto-generated `923-derived-compliance-status: Planned...` stub entries in `CLAUDE.md` (Active Technologies + Recent Changes) with a proper hand-written implementation narrative at commit time, mirroring `specs/915-objective-progress-tracking/tasks.md`'s own T038 precedent

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS every user story (all three extend the same `compute_compliance_status()` function and call through the same `get_entity_compliance_status()` wrapper this phase creates).
- **User Stories (Phase 3–5)**: All depend on Foundational. Unlike a typical feature, US1 → US2 → US3 here are also *sequentially* dependent on each other's implementation task (T007 → T009 → T011), since all three extend the same function body's decision table in the fixed order research.md D5 specifies (Non-Compliant, then Partial/Not-Assessed, then Compliant/Not-Applicable) — this mirrors ADP's own precedent for this exact situation in `specs/915-objective-progress-tracking/` (US2's abandoned-flag check built directly on US1's `compute_status()`). Each story's *tests*, however, remain independently meaningful and independently reviewable.
- **Polish (Phase 6)**: Depends on all three user stories being complete.

### Within Each User Story

- Tests written and confirmed failing (import error or wrong/`NotImplementedError` result) before implementation (ART-IV).
- Implementation task makes that story's tests — and only that story's tests — newly pass; earlier stories' tests must still pass unchanged (regression check).
- Story complete before moving to the next priority.

### Parallel Opportunities

- T002 and T003 (Foundational tests) can be written in parallel — different assertions, same file, no shared state.
- Each user story's single test task (T006, T008, T010) has no parallel sibling within its own phase (one task covers that story's whole scenario set) but can be *drafted* in parallel with an adjacent story's test task by a second contributor, since all three land in the same file — coordinate to avoid a merge conflict, or serialize as written above.
- T013 (determinism test) can be written any time after T011, in parallel with T012.

---

## Parallel Example: Foundational Phase

```bash
# Launch both Foundational tests together (before either implementation task):
Task: "Foundational test: compute_compliance_status([]) returns NOT_ASSESSED in tests/unit/compliance/test_compliance_status.py"
Task: "Foundational test: get_entity_compliance_status() raises ValueError for ORGANIZATION in tests/unit/compliance/test_compliance_status.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: `compute_compliance_status()` correctly flags any Non-Compliant control as the overall status — the single highest-value property this feature exists to deliver — even though the function still raises `NotImplementedError` for the Partial/Compliant/Not-Applicable-only cases at this point (acceptable for an MVP checkpoint within one feature branch; not for a merge — Polish gates on all three stories).

### Incremental Delivery

1. Complete Setup + Foundational → guard clauses (empty list, unsupported entity type) working.
2. Add User Story 1 → the risk-gate property (never mask a failure) working and tested.
3. Add User Story 2 → outstanding/unassessed work correctly distinguished from success.
4. Add User Story 3 → full aggregation rule complete for every reachable input, including the Q1 resolution; end-to-end dispatch verified across all four entity types.
5. Polish → determinism proven, quickstart walked, full suite green, narrative committed.

### Parallel Team Strategy

Not recommended for this feature beyond Foundational: because US1/US2/US3 build the *same* function's decision table in a fixed, spec-mandated order (research.md D5), a second contributor cannot productively start US3's implementation before US1/US2 land without recreating the same sequential edits. Test-writing (T006/T008/T010) may still be drafted ahead of time by different contributors if coordinated to avoid file conflicts.

---

## Notes

- [P] tasks = different assertions/files, no dependency on an incomplete task.
- [Story] label maps task to specific user story for traceability.
- This feature has no schema, router, or frontend change — Foundational is deliberately light (no migration, no model file edit) since `ComplianceStatus`/`MappingTargetType`/`ControlMapping` already exist from COMPLY-01/COMPLY-02.
- Verify each story's tests fail (import error, wrong result, or `NotImplementedError`) before implementing that story's branch.
- Commit after each task or logical group.
- Stop at any checkpoint to validate story independently.
