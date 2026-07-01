# Tasks: Identity, Authorization & Audit Trail

**Input**: Design documents from `/specs/004-identity-authz/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: Tests are MANDATORY for all ADP features (ART-IV). Test tasks MUST appear before their implementation counterparts in every user-story phase. Tests MUST be committed and verified to fail before any implementation begins.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story. This spec is a pure Python library — no HTTP or database required for any test.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no file conflicts)
- **[Story]**: Which user story this task belongs to (US1–US4)
- Include exact file paths in every description

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create directory skeleton and `__init__.py` files — no logic yet

- [x] T001 [P] Create `src/adp/authz/` and `src/adp/audit/` directories; create `src/adp/authz/__init__.py` (placeholder exporting nothing) and `src/adp/audit/__init__.py` (placeholder exporting nothing)
- [x] T002 [P] Create `tests/authz/` directory and `tests/authz/__init__.py` (empty)
- [x] T003 Verify `python3 -c "from adp import authz, audit; print('ok')"` succeeds after editable install

**Checkpoint**: `python3 -c "import adp.authz, adp.audit"` resolves; `pytest tests/unit/ tests/contract/ -q --no-cov` still passes all 62 existing tests

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core enums and the `PermissionDeniedError` exception class — MUST be complete before any user story

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T004 Create `src/adp/authz/roles.py`: define `PersonaRole(StrEnum)` with values `enterprise_architect`, `solution_architect`, `technical_architect`, `reviewer`; define `ActionType(StrEnum)` with all eight values from data-model.md (`read_design`, `write_design`, `submit_ai_operation`, `confirm_recommendation`, `override_verdict`, `add_finding`, `amend_standard`, `manage_roles`)
- [x] T005 Create `PermissionDeniedError(Exception)` in `src/adp/authz/permissions.py`: fields `role: PersonaRole`, `action: ActionType`, `message: str`; `__init__(self, role, action, message)` sets all three; `__str__` returns the message; no dependency on HTTP or FastAPI
- [x] T006 Create `PERMISSIONS_VERSION = "1.0.0"` constant in `src/adp/authz/permissions.py`

**Checkpoint**: `python3 -c "from adp.authz.roles import PersonaRole, ActionType; from adp.authz.permissions import PermissionDeniedError; print('ok')"` succeeds

---

## Phase 3: User Story 1 — Sign In via the Identity Provider (Priority: P1) 🎯 MVP

**Goal**: ADP never stores primary credentials; unrecognized role strings are rejected before any permission check runs; the `PersonaRole` enum is closed.

**Independent Test**: Attempt to construct a `PersonaRole` from an unrecognized string — assert `ValueError`. Grep the entire `src/adp/authz/` and `src/adp/audit/` source tree for any pattern that could store a password, token, or secret — assert zero matches. Both tests run with no infrastructure.

### Tests for User Story 1 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T007 [P] [US1] Write failing `test_unrecognized_role_raises()` in `tests/authz/test_permissions.py`: call `PersonaRole("super_admin")`; assert `ValueError` is raised; call `PersonaRole("enterprise_architect")`; assert it succeeds — confirms the enum is closed and unrecognized roles are rejected (spec US1 scenario 4, FR-001 corollary); also write `test_invalid_role_bypasses_no_permission()`: assert that calling `PersonaRole("attacker")` raises `ValueError` before any call to `is_permitted` can be made — this proves NFR-001 (authorization MUST NOT be bypassable by the client) structurally: the enum's closed set is the bypass prevention
- [x] T008 [P] [US1] Write `test_no_credential_storage_in_authz()` in `tests/authz/test_permissions.py`: use `subprocess.run(["grep", "-rn", "-E", "password=|secret=|api_key=|Bearer |private_key|ADP_.*_SECRET", "src/adp/authz/", "src/adp/audit/", "tests/authz/"])` and assert zero matching lines — uses assignment/value context to avoid false positives from `__hash__` or field names; covers source AND test fixtures per QG-08 (FR-002)

### Implementation for User Story 1

- [x] T009 [US1] Update `src/adp/authz/__init__.py` to export `PersonaRole`, `ActionType`; verify `test_unrecognized_role_raises` and `test_no_credential_storage_in_authz` pass

**Checkpoint**: `pytest tests/authz/test_permissions.py::test_unrecognized_role_raises tests/authz/test_permissions.py::test_no_credential_storage_in_authz --no-cov -q` green; FR-001 and FR-002 demonstrably satisfied

---

## Phase 4: User Story 2 — Persona-Based Permission Enforcement (Priority: P1)

**Goal**: `is_permitted(role, action)` returns the correct boolean for all 32 role×action combinations matching the permission table in the spec; `require_action(role, action)` raises `PermissionDeniedError` for denied combinations; a denied attempt is observable (logged at WARNING level).

**Independent Test**: Exhaustive parametrized test over all 32 (role, action) pairs — assert each returns the correct boolean per the spec's permission table. Separately, assert `require_action` raises on a denied pair and does not raise on a permitted pair.

### Tests for User Story 2 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T010 [P] [US2] Write failing `test_permission_table_completeness()` in `tests/authz/test_permissions.py`: parametrize over all 32 (PersonaRole, ActionType) pairs using `@pytest.mark.parametrize`; for each, call `is_permitted(role, action)` and assert it matches the exact `True`/`False` value from the spec's permission matrix table — this test is the machine-executable form of the spec's governance table
- [x] T011 [P] [US2] Write failing `test_require_action_raises_on_denied()` and `test_require_action_passes_on_permitted()` in `tests/authz/test_permissions.py`: call `require_action(PersonaRole.REVIEWER, ActionType.WRITE_DESIGN)` and assert `PermissionDeniedError` is raised with the correct `role` and `action` fields; call `require_action(PersonaRole.REVIEWER, ActionType.READ_DESIGN)` and assert no exception

### Implementation for User Story 2

- [x] T012 [US2] Implement `PERMISSION_GRANTS: dict[PersonaRole, frozenset[ActionType]]` in `src/adp/authz/permissions.py`: each entry maps exactly one role to the set of permitted actions per the spec table; all four roles must be present; unrecognized roles not in the dict get no permissions
- [x] T013 [US2] Implement `is_permitted(role: PersonaRole, action: ActionType) -> bool` in `src/adp/authz/permissions.py`: returns `action in PERMISSION_GRANTS.get(role, frozenset())`; never raises
- [x] T014 [US2] Implement `require_action(role: PersonaRole, action: ActionType) -> None` in `src/adp/authz/permissions.py`: calls `is_permitted`; if `False`, raises `PermissionDeniedError(role, action, f"{role} is not permitted to {action}")`; also emits `logging.getLogger("adp.authz").warning(...)` with role and action for observability (spec US2 scenario 1: "denial MUST be observable")
- [x] T015 [US2] Update `src/adp/authz/__init__.py` to export `is_permitted`, `require_action`, `PermissionDeniedError`; verify `test_permission_table_completeness`, `test_require_action_raises_on_denied`, `test_require_action_passes_on_permitted` all pass

**Checkpoint**: `pytest tests/authz/test_permissions.py --no-cov -q` green; SC-002 (100% of forbidden actions rejected; 100% of permitted actions allowed) verifiable by the 32-pair parametrized test

---

## Phase 5: User Story 3 — Per-Action Confirmation Before Consequential Operations (Priority: P2)

**Goal**: `requires_confirmation(action)` returns `True` for the four confirmation-required actions and `False` for the remaining four; `require_action` behaviour does not change — confirmation checking is a separate concern handled by callers.

**Independent Test**: Call `requires_confirmation` for all eight action types; assert exactly `{confirm_recommendation, override_verdict, amend_standard, manage_roles}` return `True`.

### Tests for User Story 3 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T016 [P] [US3] Write failing `test_requires_confirmation_set()` in `tests/authz/test_permissions.py`: parametrize over all eight `ActionType` values; for each, call `requires_confirmation(action)` and assert it returns `True` only for `confirm_recommendation`, `override_verdict`, `amend_standard`, `manage_roles`; assert it returns `False` for all others (spec US3 / FR-004 / QG-14)

### Implementation for User Story 3

- [x] T017 [US3] Add `REQUIRES_CONFIRMATION: frozenset[ActionType]` constant in `src/adp/authz/permissions.py` containing the four confirmation-required actions: `{ActionType.CONFIRM_RECOMMENDATION, ActionType.OVERRIDE_VERDICT, ActionType.AMEND_STANDARD, ActionType.MANAGE_ROLES}`
- [x] T018 [US3] Implement `requires_confirmation(action: ActionType) -> bool` in `src/adp/authz/permissions.py`: returns `action in REQUIRES_CONFIRMATION`
- [x] T019 [US3] Update `src/adp/authz/__init__.py` to export `requires_confirmation`; verify `test_requires_confirmation_set` passes

**Checkpoint**: `pytest tests/authz/test_permissions.py::test_requires_confirmation_set --no-cov -q` green; FR-004 (per-action confirmation; one approval MUST NOT generalize) structurally enforced

---

## Phase 6: User Story 4 — Audit Trail for Every Consequential Action (Priority: P2)

**Goal**: `write_audit_record(record, design, store)` appends a valid `AuditEntry` to the design's `audit_log` and returns the generated entry ID; it raises `ValueError` if a confirmation-required action omits the `confirmation_id`; it rejects summaries exceeding 240 characters.

**Independent Test**: Call `write_audit_record` with a mock `DesignStore`; assert `store.save` was called with a description containing an `AuditEntry` with the correct `actor`, `action`, `origin`, and `affected_entity`; call with a confirmation-required action and no `confirmation_id` and assert `ValueError`.

### Tests for User Story 4 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T020 [P] [US4] Write failing `test_write_audit_record_appends_entry()` in `tests/authz/test_audit.py`: create a mock `DesignStore` using `unittest.mock.AsyncMock`; call `await write_audit_record(record, design, mock_store)` with a valid `AuditRecord` (`action=ActionType.WRITE_DESIGN`, no `confirmation_id`); assert `mock_store.save` was called once; assert the saved description's `audit_log` contains exactly one `AuditEntry` with `actor == record.actor`, `action == "write_design"`, `origin == "human"`, and `affected_entity == record.affected_entity`
- [x] T021 [P] [US4] Write failing `test_write_audit_record_rejects_missing_confirmation_id()` in `tests/authz/test_audit.py`: call `await write_audit_record(AuditRecord(action=ActionType.CONFIRM_RECOMMENDATION, confirmation_id=None, ...), design, mock_store)`; assert `ValueError` is raised; assert `mock_store.save` was NOT called
- [x] T022 [P] [US4] Write failing `test_write_audit_record_rejects_long_summary()` in `tests/authz/test_audit.py`: call with `summary="x" * 241`; assert `ValueError` is raised
- [x] T023 [P] [US4] Write failing `test_audit_entry_id_is_returned()` in `tests/authz/test_audit.py`: assert that `write_audit_record` returns a non-empty string that matches the `AuditEntryId` pattern `^AUD-\d{3}$`

### Implementation for User Story 4

- [x] T024 [US4] Create `AuditRecord` dataclass in `src/adp/audit/writer.py`: fields `actor: str`, `action: ActionType`, `affected_entity: str`, `summary: str`, `origin: Literal["human", "ai"]`, `confirmation_id: str | None = None`; import `ActionType` from `adp.authz.roles`
- [x] T025 [US4] Implement `write_audit_record(record: AuditRecord, design: ArchitectureDescription, store: DesignStore) -> str` (async) in `src/adp/audit/writer.py`: validate `summary` length ≤ 240; validate `confirmation_id` is not `None` when `requires_confirmation(record.action)` is `True`; generate `audit_entry_id` by finding the maximum existing `AUD-NNN` integer in `design.audit_log` (default 0 if empty), incrementing by 1, and formatting as `AUD-{n:03d}` — do NOT use `len(audit_log)` as it is incorrect when entries have non-sequential IDs; note that ADP-SPEC-001 enforces a 3-digit cap (AUD-001 through AUD-999 per design); a design exceeding 999 audit entries requires a model amendment to ADP-SPEC-001; create `AuditEntry` from `adp.models` with the record fields; append to `design.audit_log`; call `await store.save(design, actor=record.actor)`; return `audit_entry_id`
- [x] T026 [US4] Update `src/adp/audit/__init__.py` to export `AuditRecord`, `write_audit_record`; verify all four US4 tests pass

**Checkpoint**: `pytest tests/authz/test_audit.py --no-cov -q` green; SC-004 (100% of committed mutations have audit entries; zero unconfirmed consequential writes) verifiable

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Coverage, quality gates, integration verification

- [x] T027 [P] Run `pytest tests/authz/ --cov=adp.authz --cov=adp.audit --cov-report=term-missing --no-cov-on-fail` and verify line coverage ≥ 85% across both new modules; add targeted tests for uncovered branches (e.g., empty `PERMISSION_GRANTS.get` fallback, warning log emission) (QG-04)
- [x] T028 [P] Run `ruff check src/adp/authz/ src/adp/audit/ tests/authz/` and `mypy src/adp/authz/ src/adp/audit/`; fix all issues (QG-06)
- [x] T029 [P] Run `bandit -r src/adp/authz/ src/adp/audit/ -ll`; assert zero HIGH-severity findings; confirm no secrets in source or test fixtures via `grep -rn "password=\|secret=\|api_key=\|Bearer \|private_key" src/adp/authz/ src/adp/audit/ tests/authz/` returns zero lines (QG-06, QG-08, FR-006)
- [x] T030 Run full test suite `pytest tests/ -q --no-cov` confirming all existing tests (ADP-SPEC-001, ADP-SPEC-002) remain unaffected and all new authz tests pass
- [x] T031 Verify `adp-generate --check` still exits 0 — this spec adds no model changes to ADP-SPEC-001 (QG-02)
- [x] T032 [P] Add `PERMISSIONS_VERSION` assertion to `test_permission_table_completeness` in `tests/authz/test_permissions.py`: assert `from adp.authz.permissions import PERMISSIONS_VERSION; assert PERMISSIONS_VERSION == "1.0.0"` — ensures any permission matrix change must also bump the version constant

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories; enums and exception must exist before any test imports them
- **US1 (Phase 3)**: Depends on Foundational (enums exist) — 🎯 MVP; validates the fundamental governance invariant (no credential storage)
- **US2 (Phase 4)**: Depends on Foundational (enums + PermissionDeniedError exist); independent of US1
- **US3 (Phase 5)**: Depends on US2 (permission table implementation exists); `requires_confirmation` is a sibling function in the same module
- **US4 (Phase 6)**: Depends on Foundational (ActionType enum) and US3 (`requires_confirmation` used by `write_audit_record`); independent of US1/US2
- **Polish (Phase 7)**: Depends on all desired user stories complete

### User Story Dependencies

- **US1 (P1)**: Can start after Phase 2 (enums available) — no dependencies on other stories
- **US2 (P1)**: Can start after Phase 2 — no dependency on US1
- **US3 (P2)**: Depends on US2 having defined `PERMISSION_GRANTS` (T012) so the test can verify `requires_confirmation` is consistent with the permission table
- **US4 (P2)**: Depends on US3 (T017-T018 define `REQUIRES_CONFIRMATION` and `requires_confirmation()` used in `write_audit_record`)

### Parallel Opportunities

- T001, T002 (Setup): parallel — different directories
- T007, T008 (US1 tests): parallel — independent test functions in same file
- T010, T011 (US2 tests): parallel — independent test functions
- T020, T021, T022, T023 (US4 tests): parallel — independent test functions
- T027, T028, T029, T031, T032 (Polish): parallel — independent tools and files

---

## Parallel Example: User Story 4

```bash
# Write all US4 tests in parallel (independent scenarios):
Task T020: test_write_audit_record_appends_entry
Task T021: test_write_audit_record_rejects_missing_confirmation_id
Task T022: test_write_audit_record_rejects_long_summary
Task T023: test_audit_entry_id_is_returned

# Implement in sequence (same file: src/adp/audit/writer.py):
T024 (AuditRecord) → T025 (write_audit_record) → T026 (exports + verify)
```

---

## Implementation Strategy

### MVP First (US1 + US2 Only)

1. Phase 1: Setup (T001–T003)
2. Phase 2: Foundational enums + exception (T004–T006)
3. Write US1 tests T007–T008 — verify they fail
4. US1 implementation T009
5. Write US2 tests T010–T011 — verify they fail
6. US2 implementation T012–T015
7. **STOP and VALIDATE**: `pytest tests/authz/ -q` green; 32-pair permission table verified
8. `adp-generate --check` exits 0

### Incremental Delivery

1. Phase 1 + 2 → Enum types and exception available for import by ADP-SPEC-003
2. US1 → Credential-free invariant verified at source-scan level
3. US2 → Full permission table enforcement; ADP-SPEC-003 can import `require_action`
4. US3 → Confirmation requirement enforcement; ADP-SPEC-003 can import `requires_confirmation`
5. US4 → Audit writer operational; ADP-SPEC-003 confirmation router can call `write_audit_record`
6. Polish → All quality gates green

---

## Notes

- [P] tasks = different files or independent test functions; no file conflict on concurrent execution
- Tests MUST fail before implementation; commit the failing test first (ART-IV)
- The permission table in `T012` MUST be a literal transcription of the spec's matrix — any divergence is a spec violation, not a code bug; T010's 32-pair test is the machine-readable spec
- `PERMISSIONS_VERSION` MUST be bumped whenever the permission table changes; T032 enforces this
- No secrets, tokens, or credentials in any file under `src/adp/authz/` or `src/adp/audit/` (FR-006 / QG-08)
- Constitution gates for this feature: QG-01, QG-04, QG-05, QG-06, QG-08, QG-09, QG-13, QG-14
- `adp-generate --check` must remain exit 0 — this spec adds no changes to ADP-SPEC-001's canonical model
- SC-003 replay prevention ("one confirmation MUST NOT authorize multiple actions") is enforced by ADP-SPEC-003's `operations_store.mark_confirmed()`, not by this spec; this spec's contribution to SC-003 is `requires_confirmation()` identifying which action types need confirmation — no replay prevention task is needed here
