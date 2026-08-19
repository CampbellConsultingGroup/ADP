# Tasks: Regulatory Framework Legal Dates & Identity (COMPLY-01a)

**Input**: Design documents from `/specs/926-framework-versioning-correction/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓, quickstart.md ✓

**Tests**: Mandatory (ART-IV, per `.specify/templates/tasks-template.md`). Test tasks appear before their
implementation counterparts in every user-story phase and must be written and verified to fail first.

**Organization**: Tasks grouped by user story (US1 = the correction itself — legal identity + dates on the
framework's own fields, P1 🎯 MVP; US2 = application phases, P2; US3 = amendments, P3). The three stories
touch entirely separate tables and are independently buildable — US2 and US3 share no table, model, or
store function with each other. Both depend on US1 only for `RegulatoryFrameworkDetail`'s two new list
fields existing (T004) before populating them with real data (T012/T018) — everything else in each story
is self-contained.

**A note on what the source document got wrong, resolved before any task below** (spec.md Clarifications,
research.md D1): the document's own justification claimed the field being replaced is `NUMERIC`; it is
actually `VARCHAR(100)` free text, already holding real citation strings for all three currently-tracked
frameworks. Its draft schema used `Integer` autoincrement PKs (this codebase uses `String(36)` UUIDs
everywhere, no exception) and a field, `official_title`, that doesn't exist (the real field is `name`).
Every task below reflects the corrected design, not the document's original text.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 / US2 / US3, per spec.md's priorities (P1/P2/P3)

## Path Conventions

Single project, existing package/files only — no new package, no frontend file touched (plan.md Structure
Decision):
- Backend: `src/adp/compliance/{models,store,router}.py` (all exist, extended); one new migration
- Backend tests: `tests/unit/compliance/test_framework_legal_dates.py` (new),
  `tests/contract/test_framework_legal_dates_api.py` (new),
  `tests/integration/test_framework_legal_dates_api.py` (new)

---

## Phase 1: Setup (Migration)

**Purpose**: Database schema every user story depends on.

- [X] T001 Create Alembic migration in `src/adp/store/migrations/versions/035_framework_legal_dates.py` (`revision = "035"`, `down_revision = "034"`): seven additive columns on `regulatory_frameworks` — `regulation_number` VARCHAR(100) nullable UNIQUE (`uq_regulatory_frameworks_regulation_number`), `celex_number` VARCHAR(50) nullable, `adoption_date`/`oj_publication_date`/`entry_into_force_date`/`consolidated_as_of` DATE nullable, `status` TEXT NOT NULL DEFAULT `'in_force'` with named CHECK `ck_regulatory_frameworks_status` restricting to `('in_force','amended','repealed','not_yet_applicable')`; two new tables per data-model.md — `framework_application_phase` (`id` VARCHAR(36) PK, `framework_id` VARCHAR(36) FK→`regulatory_frameworks.id` ON DELETE CASCADE, `phase_label` VARCHAR(255) NOT NULL, `applies_from_date` DATE NOT NULL, `description` TEXT nullable, `created_at`, index `ix_framework_application_phase_framework_id`) and `framework_amendment` (same shape: `amending_celex` VARCHAR(50) nullable, `amending_title` VARCHAR(255) NOT NULL, `effective_date` DATE nullable, `created_at`, index `ix_framework_amendment_framework_id`); zero existing columns altered, renamed, or dropped (research.md D2); `downgrade()` drops both new tables then the seven added columns/constraints in reverse order

**Checkpoint**: Migration applies cleanly (`alembic upgrade head` then `alembic downgrade -1` then `alembic upgrade head` again) **and**, applied against a database seeded with rows shaped like the three real tracked frameworks (name/jurisdiction/authority/version/effective_date/source_url all populated, every new column absent), every existing field reads back identical and every new column reads as `NULL`/`'in_force'` — this is the load-bearing guarantee the whole spec exists to uphold (spec.md FR-004/SC-001); verified directly in T020, not just asserted here.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: None beyond the Setup migration. Unlike prior COMPLY-0x specs, this feature's three stories
touch three genuinely separate tables (`regulatory_frameworks`' own new columns, `framework_application_phase`,
`framework_amendment`) with no shared model, store table, or query between them — there is no shared
primitive to build here beyond the schema itself. US2 and US3 each depend only on US1's `T004` (the two new
empty-list fields existing on `RegulatoryFrameworkDetail`) before populating them with real queries in
their own phases.

**Checkpoint**: N/A — proceed directly to User Story 1 once T001 is complete.

---

## Phase 3: User Story 1 - Record a framework's legal identity and timeline without losing what's already there (Priority: P1) 🎯 MVP

**Goal**: An architect can record a framework's regulation identity, up to four legal-event dates, and a
status, while every one of that framework's existing fields — and every other tracked framework's fields —
remain exactly as they were.

**Independent Test**: can be fully tested by recording a regulation number and one legal-event date on an
existing tracked framework, confirming its previously-recorded fields are unchanged, and confirming a
framework that never uses any new field behaves exactly as it does today.

### Tests for User Story 1 (write first — ART-IV)

- [X] T002 [P] [US1] Unit tests in `tests/unit/compliance/test_framework_legal_dates.py`: `create_framework()`/`update_framework()` accept and persist the seven new optional fields; a second framework given an already-used `regulation_number` raises `DuplicateRegulationNumberError`; a framework saved with none of the new fields set round-trips with its existing fields completely unchanged and every new field `None`/`status == "in_force"`; `RegulatoryFrameworkCreate`/`Update` with an invalid `status` string raises `ValidationError` (Pydantic `Literal` rejection, before the store is ever called)
- [X] T003 [P] [US1] Contract tests in `tests/contract/test_framework_legal_dates_api.py` (extends `adp.compliance`'s own existing SQLite fixture pattern): `PATCH /frameworks/{id}` with the seven new fields → 200, response includes them and every existing field unchanged; `PATCH` reusing another framework's `regulation_number` → 409; `POST /frameworks` with `status: "bogus"` → 422; `GET /frameworks/{id}` response validates as `RegulatoryFrameworkDetail` and includes `application_phases: []`, `amendments: []` alongside the existing `controls`

### Implementation for User Story 1

- [X] T004 [US1] In `src/adp/compliance/models.py`: `FrameworkStatus = Literal["in_force", "amended", "repealed", "not_yet_applicable"]`; extend `RegulatoryFramework`/`RegulatoryFrameworkCreate`/`RegulatoryFrameworkUpdate` with `regulation_number: str | None` (`max_length=100`), `celex_number: str | None` (`max_length=50`), `adoption_date`/`oj_publication_date`/`entry_into_force_date`/`consolidated_as_of: date | None`, `status: FrameworkStatus = "in_force"` (all `None`/default-optional — data-model.md); extend `RegulatoryFrameworkDetail` with `application_phases: list["FrameworkApplicationPhase"] = []` and `amendments: list["FrameworkAmendment"] = []` (forward refs to the models US2/US3 add — call `RegulatoryFrameworkDetail.model_rebuild()` once both exist, matching this file's existing `ControlNode.model_rebuild()` convention); add `DuplicateRegulationNumberError(regulation_number)` exception mirroring `DuplicateControlCodeError`'s shape
- [X] T005 [US1] In `src/adp/compliance/store.py`: extend `_frameworks` `sa.Table()` with the seven new columns (DML-only, matches migration exactly); extend `_row_to_framework()` to read them; extend `create_framework()`/`update_framework()` to accept and persist the new fields, catching a unique-violation on `regulation_number` → `DuplicateRegulationNumberError` (same catch-and-translate shape already used elsewhere in this codebase for unique violations) (depends on T004)
- [X] T006 [US1] In `src/adp/compliance/router.py`: `POST /frameworks` and `PATCH /frameworks/{framework_id}` (same paths, no change) catch `DuplicateRegulationNumberError` → 409, alongside their existing logic (depends on T005)
- [X] T007 [US1] In `src/adp/compliance/store.py`: `get_framework_detail()` constructs `RegulatoryFrameworkDetail` with `application_phases=[]` and `amendments=[]` placeholders (real population lands in US2/US3's own phases, T012/T018) — makes T003's `GET /frameworks/{id}` contract test pass now, before either child table has any data (depends on T004)

**Checkpoint**: User Story 1 fully functional and independently testable — a framework's legal identity
and dates can be recorded and read via the API, and the three real tracked frameworks are provably
untouched (quickstart.md Scenarios 1–3, 7 (empty-lists case)). Independently demonstrable as the MVP.

---

## Phase 4: User Story 2 - Record that a framework applies in stages (Priority: P2)

**Goal**: An architect can record one or more application phases for a framework with a staged rollout
(e.g., the EU AI Act), and a framework with a single application date needs none.

**Independent Test**: can be fully tested by adding two or more application phases with different
effective dates to one framework, and confirming a framework with zero phases behaves identically to one
that has never used this capability.

### Tests for User Story 2 (write first — ART-IV)

- [X] T008 [P] [US2] Unit tests in `tests/unit/compliance/test_framework_legal_dates.py`: `add_application_phase()` persists and returns a phase; `list_application_phases()` returns phases ordered by `applies_from_date`, and `[]` for a framework that has never had one added; `delete_application_phase()` removes a phase, and raises `ApplicationPhaseNotFoundError` for an unknown `(framework_id, phase_id)` pair
- [X] T009 [P] [US2] Contract tests in `tests/contract/test_framework_legal_dates_api.py`: `POST /frameworks/{id}/application-phases` → 201; `GET .../application-phases` → 200 `FrameworkApplicationPhaseListResponse`, ordered; `DELETE .../application-phases/{phase_id}` → 204, then 404 on repeat; all three routes against an unknown `framework_id` → 404

### Implementation for User Story 2

- [X] T010 [US2] In `src/adp/compliance/models.py`: `FrameworkApplicationPhase` (read model: `id`, `framework_id`, `phase_label`, `applies_from_date`, `description`, `created_at`, `extra="forbid"`) and `FrameworkApplicationPhaseCreate` (`phase_label` max_length=255 + blank-check, `applies_from_date`, `description` optional); `FrameworkApplicationPhaseListResponse` (`items`, `total`); `ApplicationPhaseNotFoundError(phase_id)` — router maps to 404; call `RegulatoryFrameworkDetail.model_rebuild()` once this and T016's model both exist (depends on T004)
- [X] T011 [US2] In `src/adp/compliance/store.py`: `_framework_application_phases` DML-only `sa.Table()` (matches T001's migration schema exactly); `add_application_phase(framework_id, data, session) -> FrameworkApplicationPhase`; `list_application_phases(framework_id, session) -> list[FrameworkApplicationPhase]` (ordered by `applies_from_date`); `delete_application_phase(framework_id, phase_id, session) -> None` (raises `ApplicationPhaseNotFoundError` if no row matched) (depends on T010)
- [X] T012 [US2] In `src/adp/compliance/store.py`: `get_framework_detail()` extended to populate `application_phases` via `list_application_phases()` — replaces T007's `[]` placeholder for this field only (depends on T007, T011)
- [X] T013 [US2] In `src/adp/compliance/router.py`: `POST /frameworks/{framework_id}/application-phases` (404 if `get_framework()` is `None`, else 201); `GET /frameworks/{framework_id}/application-phases` (404 if framework missing, else 200 list); `DELETE /frameworks/{framework_id}/application-phases/{phase_id}` (204, `ApplicationPhaseNotFoundError`→404); both writes under the existing `WRITE_COMPLIANCE` prefix rule (no `enforcement.py` change) (depends on T011)

**Checkpoint**: User Story 2 fully functional and independently testable — a staged-rollout framework can
have multiple phases recorded, and a framework that never uses this capability is completely unaffected
(quickstart.md Scenario 4).

---

## Phase 5: User Story 3 - Record that a framework has been amended over time (Priority: P3)

**Goal**: An architect can record a growing list of amendments to a framework (e.g., DORA's RTS stack)
with no limit, and a framework with no amendments needs none.

**Independent Test**: can be fully tested by adding several amendments to one framework over time and
confirming a framework with none behaves identically to one that has never used this capability.

### Tests for User Story 3 (write first — ART-IV)

- [X] T014 [P] [US3] Unit tests in `tests/unit/compliance/test_framework_legal_dates.py`: `add_amendment()` persists and returns an amendment; `list_amendments()` returns amendments ordered by `effective_date` (nulls last), and `[]` for a framework that has never had one added; `delete_amendment()` removes an amendment, and raises `AmendmentNotFoundError` for an unknown `(framework_id, amendment_id)` pair
- [X] T015 [P] [US3] Contract tests in `tests/contract/test_framework_legal_dates_api.py`: `POST /frameworks/{id}/amendments` → 201; `GET .../amendments` → 200 `FrameworkAmendmentListResponse`, ordered; `DELETE .../amendments/{amendment_id}` → 204, then 404 on repeat; all three routes against an unknown `framework_id` → 404; adding 5 amendments to one framework succeeds with no limit enforced

### Implementation for User Story 3

- [X] T016 [US3] In `src/adp/compliance/models.py`: `FrameworkAmendment` (read model: `id`, `framework_id`, `amending_celex`, `amending_title`, `effective_date`, `created_at`, `extra="forbid"`) and `FrameworkAmendmentCreate` (`amending_celex` optional max_length=50, `amending_title` max_length=255 + blank-check, `effective_date` optional); `FrameworkAmendmentListResponse` (`items`, `total`); `AmendmentNotFoundError(amendment_id)` — router maps to 404; this is the second (and last) model `RegulatoryFrameworkDetail.model_rebuild()` (T010) waits on (depends on T004)
- [X] T017 [US3] In `src/adp/compliance/store.py`: `_framework_amendments` DML-only `sa.Table()` (matches T001's migration schema exactly); `add_amendment(framework_id, data, session) -> FrameworkAmendment`; `list_amendments(framework_id, session) -> list[FrameworkAmendment]` (ordered by `effective_date`, nulls last); `delete_amendment(framework_id, amendment_id, session) -> None` (raises `AmendmentNotFoundError` if no row matched) (depends on T016)
- [X] T018 [US3] In `src/adp/compliance/store.py`: `get_framework_detail()` extended to populate `amendments` via `list_amendments()` — replaces T007's `[]` placeholder for this field only (depends on T007, T017)
- [X] T019 [US3] In `src/adp/compliance/router.py`: `POST /frameworks/{framework_id}/amendments` (404 if `get_framework()` is `None`, else 201); `GET /frameworks/{framework_id}/amendments` (404 if framework missing, else 200 list); `DELETE /frameworks/{framework_id}/amendments/{amendment_id}` (204, `AmendmentNotFoundError`→404); both writes under the existing `WRITE_COMPLIANCE` prefix rule (depends on T017)

**Checkpoint**: All three user stories independently functional — a framework's legal identity, its staged
application, and its amendment history can each be recorded and read via the API, with the three real
tracked frameworks provably untouched throughout.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T020 [P] Integration tests (testcontainers PostgreSQL) in `tests/integration/test_framework_legal_dates_api.py`: seed three rows shaped exactly like the real GDPR/EU AI Act/DORA frameworks (same field values, no new columns set) *before* running migration `035`, confirm every existing field reads back byte-identical afterward and every new column reads `NULL`/`'in_force'` (spec.md FR-004/SC-001 — the direct verification T001's Checkpoint promises); `test_delete_framework_cascades_phases_and_amendments` (add phases + amendments to one framework, delete it, confirm both child tables are empty for that `framework_id`); `test_regulation_number_null_does_not_conflict_across_frameworks` (two frameworks both left without a `regulation_number` save successfully)
- [X] T021 [P] Extend `tests/authz/test_enforcement.py`: `test_reviewer_denied_application_phase_write` / `test_reviewer_denied_amendment_write` (403 for a REVIEWER-role POST to either new sub-resource route, mirroring COMPLY-01's own `test_reviewer_denied_compliance_write` shape — covered by the existing `/api/v1/compliance/` prefix rule, not a new rule)
- [X] T022 Manually run quickstart.md's 8 scenarios against a running local stack (`ADP_AUTH_ENABLED=false`) using the three real tracked frameworks for Scenarios 1–2 (a temporary `regulation_number` set then cleared back to `null` on one real framework, confirmed via direct read before and after) and temporary test frameworks for Scenarios 3–8, cleaned up afterward
- [X] T023 Run the full regression suite: `pytest tests/ --ignore=tests/integration -q`, `ruff check src/`, `mypy src/` — confirm no regressions and no new lint/type errors
- [X] T024 Confirm `adp-generate --check` is clean (schema drift gate — `ArchitectureDescription`'s own schema is untouched by this feature, but the gate must still pass)
- [X] T025 Replace the auto-generated `926-framework-versioning-correction: Added ...` stub entries in `CLAUDE.md` (Active Technologies + Recent Changes) with a proper hand-written implementation narrative at commit time, mirroring `specs/925-strategy-compliance-linkage/tasks.md`'s own final-task precedent

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Empty — nothing shared beyond the Setup migration (see phase note above).
- **User Stories (Phase 3–5)**: All depend on Setup (T001) only. **US1, US2, and US3 touch entirely
  separate tables and share no store function or model with each other** — the only cross-story coupling
  is that US2's T012 and US3's T018 each edit one field of the same `get_framework_detail()` function T007
  (US1) first creates with placeholder values; each replaces only its own field's placeholder, not the
  other's, so the two edits don't conflict even if made in parallel. Priority order (P1 → P2 → P3) is a
  delivery-sequencing choice, not a hard code-level dependency, beyond that.
- **Polish (Phase 6)**: Depends on all three user stories being complete (T020's data-preservation test
  exercises both child tables together; T021 exercises both new write surfaces).

### Within Each User Story

- Tests written and confirmed failing (`ImportError`, or wrong/missing behavior) before implementation (ART-IV).
- Models before store functions; store functions before router endpoints.
- Story complete before moving to the next priority.

### Parallel Opportunities

- T002 and T003 (US1 tests) can run in parallel.
- T008/T009 (US2 tests) and T014/T015 (US3 tests) can all run in parallel with each other and with US1's
  own tasks, once T001 (Setup) and T004 (US1's model extension, needed for the `RegulatoryFrameworkDetail`
  forward refs) land.
- T010–T013 (US2) and T016–T019 (US3) can proceed fully in parallel by two different contributors — no
  shared file conflict beyond the two independent fields on `get_framework_detail()` noted above.
- T020, T021 (Polish) can run in parallel — different files.

---

## Parallel Example: User Story 1

```bash
# Launch both US1 tests together:
Task: "Unit tests for create_framework/update_framework's new fields + DuplicateRegulationNumberError in tests/unit/compliance/test_framework_legal_dates.py"
Task: "Contract tests for PATCH/POST/GET /frameworks[/{id}] in tests/contract/test_framework_legal_dates_api.py"
```

## Parallel Example: User Story 2 + User Story 3 Together (post-US1's T004)

```bash
# Two contributors, or one contributor working both in sequence without cross-dependency:
Task: "US2 — application phases: T008/T009 tests, then T010–T013 implementation"
Task: "US3 — amendments: T014/T015 tests, then T016–T019 implementation"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (migration).
2. Complete Phase 3: User Story 1 (legal identity + dates on the framework's own fields).
3. **STOP and VALIDATE**: Run quickstart.md Scenarios 1–3, 7 against a live stack, using the three real
   tracked frameworks for Scenario 1's data-preservation check.
4. Deploy/demo if ready — the correction itself (the reason this spec exists) already works end to end.

### Incremental Delivery

1. Setup → foundation ready (no separate Foundational phase needed this time).
2. Add US1 → test independently → deploy/demo (MVP!).
3. Add US2 → test independently → deploy/demo (staged-rollout frameworks like the EU AI Act now
   representable).
4. Add US3 → test independently → deploy/demo (amendment stacks like DORA's RTS now representable).
5. Add Polish → the load-bearing data-preservation integration test, authz completeness.

### Parallel Team Strategy

With multiple developers, once T001 (Setup) and T004 (US1's model extension) are done: Developer A takes
US1's remaining tasks (T005–T007); Developer B takes US2 (T008–T013); Developer C takes US3 (T014–T019) —
all three can proceed simultaneously since the tables are disjoint and the only shared file
(`get_framework_detail()`) is touched at disjoint fields.

---

## Notes

- [P] tasks = different files, no dependencies.
- [Story] label maps task to specific user story for traceability.
- Verify tests fail before implementing.
- Commit after each task or logical group.
- Stop at any checkpoint to validate that story independently.
- No frontend task appears anywhere in this file — the resolved Clarification scopes this pass to
  data-model-and-API only; `web/src/compliance/FrameworkForm.tsx`/`FrameworkDetail.tsx` are untouched.
