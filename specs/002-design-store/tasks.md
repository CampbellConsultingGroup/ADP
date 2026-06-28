# Tasks: Persistence & Design Store

**Input**: Design documents from `/specs/002-design-store/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: Tests are MANDATORY for all ADP features (ART-IV). Test tasks MUST appear before their implementation counterparts in every user-story phase. Tests MUST be committed and verified to fail before any implementation begins.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on concurrent tasks)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in every description

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Extend the existing `adp` package with store sub-package skeleton and new dependencies

- [ ] T001 Add store dependencies to `pyproject.toml` using minimum-version constraints: `sqlalchemy[asyncio]>=2.0`, `asyncpg>=0.29`, `alembic>=1.13`, `pydantic-settings>=2.0`; add dev deps `pytest-asyncio>=0.23`, `testcontainers[postgres]>=4.0`; run `pip install -e ".[dev]"` and verify; exact versions will be pinned in T049
- [ ] T002 [P] Create directory structure: `src/adp/store/`, `src/adp/store/migrations/`, `src/adp/store/migrations/versions/`, `tests/integration/`
- [ ] T003 [P] Create `tests/integration/__init__.py` (empty) and `tests/unit/test_store_queries.py` placeholder (empty module with docstring)
- [ ] T004 Add `pytest-asyncio` mode configuration to `pyproject.toml`: `asyncio_mode = "auto"` under `[tool.pytest.ini_options]`; verify `pytest` still collects all existing tests without error
- [ ] T005 Initialize Alembic: create `alembic.ini` at repo root pointing to `src/adp/store/migrations/`; create `src/adp/store/migrations/env.py` that reads `ADP_DATABASE_URL` from environment via `pydantic-settings` and connects SQLAlchemy metadata to Alembic

**Checkpoint**: `pip install -e ".[dev]"` succeeds; `pytest --collect-only` shows all 48 existing tests without errors; `alembic --help` resolves

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: ORM table definitions, error hierarchy, migration, trigger, logging helpers, and DesignStore constructor — MUST be complete before any user story begins

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T006 Create `src/adp/store/__init__.py` exporting: `DesignStore`, `DesignRecord`, `DesignVersion`, `VerdictChain` and all exception classes
- [ ] T007 Define exception hierarchy in `src/adp/store/store.py`: `StoreError(Exception)`, `DesignNotFoundError(StoreError)`, `EntityNotFoundError(StoreError)`, `SchemaValidationError(StoreError)`, `ConcurrencyConflictError(StoreError)` — each carries `design_id: str` and a human-readable message; no design content in exception text
- [ ] T008 Define `DesignRecord` and `DesignVersion` dataclasses in `src/adp/store/records.py`: fields per data-model.md Store Interface Entities section; also define SQLAlchemy `Table` objects for `designs`, `design_versions`, and `audit_entries` tables with all columns and constraints from data-model.md; also define `VerdictChain` dataclass in `src/adp/store/records.py` with fields `option: SolutionOption`, `satisfies_requirements: list[Requirement]`, `satisfying_elements: list[Element]`, `verdict: Verdict | None` — types imported from `adp.models`
- [ ] T009 Create initial Alembic migration `src/adp/store/migrations/versions/001_initial_schema.py`: CREATE TABLE `designs`, CREATE TABLE `design_versions` (composite PK `(design_id, version_num)`), CREATE TABLE `audit_entries`, CREATE GIN index on `design_versions.content`, CREATE `deny_audit_mutation()` trigger function, CREATE TRIGGER `audit_entries_immutable` BEFORE UPDATE OR DELETE on `audit_entries`
- [ ] T010 Create `src/adp/store/logging.py`: `log_operation(operation: str, design_id: str, *, version_num: int | None = None, actor: str | None = None, duration_ms: float | None = None, error: Exception | None = None) -> None` — emits a structured JSON log entry at INFO (success) or ERROR (failure); never logs `content` field or database URL
- [ ] T011 Create `src/adp/store/queries.py`: stub functions `query_satisfies(content: dict, requirement_id: str) -> list[dict]`, `query_orphan_requirements(content: dict) -> list[dict]`, `query_verdict_chain(content: dict, option_id: str) -> dict` — all raise `NotImplementedError`; these operate on deserialized content dicts (pure Python, no DB I/O)
- [ ] T012 Create `DesignStore` class in `src/adp/store/store.py`: constructor `__init__(self, database_url: str) -> None` creates an async SQLAlchemy engine; stub methods `save()`, `get()`, `list_versions()`, `query_satisfies()`, `query_orphan_requirements()`, `query_verdict_chain()` all raise `NotImplementedError`
- [ ] T013 Create `tests/integration/conftest.py`: pytest fixtures using `testcontainers[postgres]` — `postgres_container` (session-scoped, starts PostgreSQL container), `db_engine` (session-scoped, creates SQLAlchemy async engine, runs `alembic upgrade head`), `db_session` (function-scoped, opens a transaction with `BEGIN` and issues `ROLLBACK` after each test so committed rows never persist between tests), `store` (function-scoped, returns a `DesignStore` instance that uses the rolling-back `db_session` — ensuring test isolation without database teardown; satisfies ART-IV deterministic tests requirement)

**Checkpoint**: `python -c "from adp.store import DesignStore, StoreError; print('ok')"` succeeds; `alembic upgrade head` (against a test PostgreSQL instance) completes without error

---

## Phase 3: User Story 1 — Save and Retrieve a Design (Priority: P1) 🎯 MVP

**Goal**: A valid `ArchitectureDescription` can be saved and retrieved identically; schema-invalid designs are rejected before any write; non-existent designs raise a clear error.

**Independent Test**: Save the `fixtures/example-adp.json` design, retrieve it by design ID, assert equality. Attempt to save a schema-invalid dict and assert `SchemaValidationError`. Both must pass independently of all other stories.

### Tests for User Story 1 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T014 [P] [US1] Write failing `test_save_and_retrieve_round_trip()` in `tests/integration/test_store.py`: load `fixtures/example-adp.json`, call `await store.save(description, actor="test")`, call `await store.get(description.id)`, assert retrieved equals original
- [ ] T015 [P] [US1] Write failing `test_schema_invalid_design_rejected()` in `tests/integration/test_store.py`: attempt `await store.save()` with an `ArchitectureDescription`-shaped dict missing `schema_version`; assert `SchemaValidationError` is raised and nothing is written to the database
- [ ] T016 [P] [US1] Write failing `test_get_nonexistent_design_raises()` in `tests/integration/test_store.py`: call `await store.get("NONEXISTENT-999")`, assert `DesignNotFoundError` is raised

### Implementation for User Story 1

- [ ] T017 [US1] Implement `save()` in `src/adp/store/store.py`: validate `description` against the published schema (re-validate using `ArchitectureDescription.model_validate(description.model_dump())`; if model_validate raises, wrap in `SchemaValidationError`); INSERT into `design_versions` with `version_num=1`; INSERT or UPDATE `designs.current_version`; wrap in a single `async with session.begin()` transaction; call `log_operation("save", ...)`
- [ ] T018 [US1] Implement `get()` in `src/adp/store/store.py`: SELECT from `design_versions` for `(design_id, version_num)` where `version_num` defaults to `designs.current_version`; deserialize `content` via `ArchitectureDescription.model_validate_json()`; raise `DesignNotFoundError` if no row found; call `log_operation("get", ...)`
- [ ] T018b [US1] Extend `get()` in `src/adp/store/store.py` to detect schema version drift: after deserialization, compare `result.schema_version` against the live `SCHEMA_VERSION` constant from `adp.models`; if they differ, emit a structured log WARNING with `{"schema_mismatch": true, "stored_version": X, "live_version": Y, "design_id": Z}` — retrieval still succeeds and returns the model; write `test_get_logs_warning_on_schema_mismatch()` in `tests/integration/test_store.py` verifying the warning is emitted when versions differ (NFR-002 detection clause)
- [ ] T019 [US1] Verify `test_save_and_retrieve_round_trip`, `test_schema_invalid_design_rejected`, and `test_get_nonexistent_design_raises` all pass; run `adp-generate --check` to confirm ADP-SPEC-001 schema is still clean

**Checkpoint**: `pytest tests/integration/test_store.py -k "us1 or round_trip or invalid or nonexistent" --no-cov` green; `await store.save()` + `await store.get()` working end-to-end against a real PostgreSQL container

---

## Phase 4: User Story 2 — Atomic Audit Trail on Every Mutation (Priority: P1)

**Goal**: Every save writes audit entries atomically in the same transaction; a mid-transaction failure leaves neither the mutation nor the audit entries committed; the database trigger prevents any update/delete on audit entries.

**Independent Test**: Save a design with one `AuditEntry` in `audit_log`; query `audit_entries` directly for that design; assert the entry is present with the correct actor and action. Verify the trigger fires on a direct SQL DELETE attempt.

### Tests for User Story 2 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T020 [P] [US2] Write failing `test_save_writes_audit_entries_atomically()` in `tests/integration/test_store.py`: save a design with one `AuditEntry` in `audit_log`; execute raw SQL `SELECT * FROM audit_entries WHERE design_id = ?`; assert the audit entry row exists with correct actor, action, and origin fields
- [ ] T021 [P] [US2] Write failing `test_audit_trigger_fires_on_delete()` in `tests/integration/test_store.py`: save a design with an audit entry; attempt raw SQL `DELETE FROM audit_entries WHERE id = ?`; assert a database exception is raised containing the message from the trigger (`ART-IX` or `append-only`)
- [ ] T022 [P] [US2] Write failing `test_mutation_rolls_back_without_audit()` in `tests/integration/test_store.py`: save a valid design; simulate a DB-level write failure by providing a second `AuditEntry` with the **same id** as the first (duplicate primary key) — this causes a database `IntegrityError` after the `design_versions` row is inserted but within the same transaction; assert that after the exception, neither the new design version NOR any audit entry is present in the database, confirming full rollback; assert neither the new design version nor the audit entry is committed

### Implementation for User Story 2

- [ ] T023 [US2] Extend `save()` in `src/adp/store/store.py`: within the same `async with session.begin()` transaction that inserts the design version, iterate `description.audit_log` and INSERT each `AuditEntry` into `audit_entries`; if any INSERT fails, the transaction rolls back atomically; add structured log for each audit entry batch write
- [ ] T024 [US2] Add `AuditEntry` insert SQL in `src/adp/store/store.py`: map each `AuditEntry` field to the `audit_entries` table columns per data-model.md; include `design_version` field as the new version number being committed
- [ ] T025 [US2] Verify `test_save_writes_audit_entries_atomically`, `test_audit_trigger_fires_on_delete`, and `test_mutation_rolls_back_without_audit` all pass

**Checkpoint**: `pytest tests/integration/test_store.py -k "audit"` green; QG-13 (append-only audit entries) verifiable

---

## Phase 5: User Story 3 — Immutable Version History (Priority: P2)

**Goal**: Saving a modified design creates a new version; the prior version remains unchanged and retrievable; concurrent saves with a stale `expected_version` are rejected with `ConcurrencyConflictError`; direct SQL UPDATE on `design_versions` is rejected.

**Independent Test**: Save a design (v1), save a modified copy (v2), retrieve both — v1 must equal original, v2 must reflect the change. Attempt `await store.save()` with `expected_version=1` after v2 exists — assert `ConcurrencyConflictError`.

### Tests for User Story 3 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T026 [P] [US3] Write failing `test_second_save_creates_new_version()` in `tests/integration/test_store.py`: save v1, save modified v2, call `list_versions(design_id)`, assert 2 versions returned with correct version numbers
- [ ] T027 [P] [US3] Write failing `test_prior_version_unchanged()` in `tests/integration/test_store.py`: save v1, save v2, retrieve v1 explicitly with `get(design_id, version=1)`, assert retrieved equals original v1 exactly
- [ ] T028 [P] [US3] Write failing `test_optimistic_concurrency_conflict()` in `tests/integration/test_store.py`: save v1, save v2 (now current=2), attempt `await store.save(v1_copy, actor="x", expected_version=1)`, assert `ConcurrencyConflictError` is raised and no new version is created
- [ ] T029 [US3] Write failing `test_design_version_row_is_immutable()` in `tests/integration/test_store.py`: save a design; attempt raw SQL `UPDATE design_versions SET content = '{}' WHERE design_id = ?`; assert either a database constraint or trigger exception is raised

### Implementation for User Story 3

- [ ] T030 [US3] Extend `save()` in `src/adp/store/store.py`: add `expected_version: int | None = None` parameter; when provided, SELECT `designs.current_version` within the same transaction and compare; if mismatch, raise `ConcurrencyConflictError` before any INSERT; increment `version_num` to `current_version + 1` for subsequent saves
- [ ] T031 [US3] Implement `list_versions()` in `src/adp/store/store.py`: SELECT from `design_versions` for `design_id` ordered by `version_num ASC`; return `list[DesignVersion]` with metadata only (no content); raise `DesignNotFoundError` if design does not exist; call `log_operation("list_versions", ...)`
- [ ] T032 [US3] Extend `get()` in `src/adp/store/store.py` to accept `version: int | None`; when `version` is specified, SELECT `design_versions WHERE (design_id, version_num) = (?, ?)`; when `None`, JOIN with `designs.current_version`; raise `DesignNotFoundError` if the specific version does not exist
- [ ] T033 [US3] Verify `test_second_save_creates_new_version`, `test_prior_version_unchanged`, `test_optimistic_concurrency_conflict`, and `test_design_version_row_is_immutable` all pass

**Checkpoint**: `pytest tests/integration/test_store.py -k "version or concurrency or immutable"` green; SC-003 (all prior versions retrievable) verifiable

---

## Phase 6: User Story 4 — Traceability Queries (Priority: P2)

**Goal**: Three typed query methods return correct results from indexed JSONB paths — no prose scanning; empty results are returned (not errors) when nothing matches; `query_verdict_chain` returns the full linked chain in one call.

**Independent Test**: Store the `fixtures/example-adp.json` design; query `query_satisfies("REQ-001")`; assert `ELM-001` and `ELM-002` are returned. Query `query_verdict_chain("OPT-001")`; assert the returned `VerdictChain` contains `VRD-001`. Query `query_satisfies("REQ-999")` (non-existent); assert empty list.

### Tests for User Story 4 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T034 [P] [US4] Write failing `test_query_satisfies_returns_matching_elements()` in `tests/integration/test_store.py`: save the example design, call `await store.query_satisfies(design_id, "REQ-001")`, assert both `ELM-001` and `ELM-002` are in the result; assert result is `list[Element]`
- [ ] T035 [P] [US4] Write failing `test_query_satisfies_returns_empty_for_unknown_requirement()` in `tests/integration/test_store.py`: save the example design, call `await store.query_satisfies(design_id, "REQ-999")`, assert empty list returned (not an exception)
- [ ] T036 [P] [US4] Write failing `test_query_orphan_requirements_identifies_orphans()` in `tests/integration/test_store.py`: save a design with `REQ-002` that appears in no element's or option's `satisfies`, call `await store.query_orphan_requirements(design_id)`, assert `REQ-002` is in the result and `REQ-001` (which is satisfied) is not
- [ ] T037 [P] [US4] Write failing `test_query_verdict_chain_returns_full_chain()` in `tests/integration/test_store.py`: save the example design, call `await store.query_verdict_chain(design_id, "OPT-001")`, assert `chain.option.id == "OPT-001"`, `chain.verdict.id == "VRD-001"`, `"REQ-001"` in `[r.id for r in chain.satisfies_requirements]`
- [ ] T038 [P] [US4] Write failing `test_query_satisfies_unit()` and `test_query_orphans_unit()` and `test_query_verdict_chain_unit()` in `tests/unit/test_store_queries.py` — call the pure Python functions in `src/adp/store/queries.py` directly with a content dict (no database); assert correct elements/requirements are extracted

### Implementation for User Story 4

- [ ] T039 [US4] Implement `query_satisfies(content, requirement_id)` in `src/adp/store/queries.py`: iterate `content["elements"]`; return those whose `satisfies` list contains `requirement_id`; return as list of `Element` model instances
- [ ] T040 [US4] Implement `query_orphan_requirements(content)` in `src/adp/store/queries.py`: collect all IDs from `satisfies` across elements and options; return requirements whose `id` is NOT in that set
- [ ] T041 [US4] Implement `query_verdict_chain(content, option_id)` in `src/adp/store/queries.py`: find the option by `option_id`; collect requirements it satisfies; find elements satisfying those requirements; find the verdict targeting this option; return `VerdictChain`; raise `EntityNotFoundError` if option not found
- [ ] T042 [US4] Implement `query_satisfies()` in `src/adp/store/store.py`: `get()` the latest design version content, pass to `queries.query_satisfies()`; call `log_operation("query_satisfies", ...)`
- [ ] T043 [US4] Implement `query_orphan_requirements()` and `query_verdict_chain()` in `src/adp/store/store.py`: same pattern as T042 — get content from `get()`, delegate to `queries.py` functions; log each operation
- [ ] T043b [P] [US4] Implement `query_by_provenance(content, provenance_value)` in `src/adp/store/queries.py`: return all `Element` and `SolutionOption` objects whose `provenance` field equals `provenance_value`; write `test_query_by_provenance_unit()` in `tests/unit/test_store_queries.py`; wire into `DesignStore.query_by_provenance()` in `src/adp/store/store.py` with a structured log entry (FR-005)
- [ ] T043c [P] [US4] Implement `query_relationships(content, element_id)` in `src/adp/store/queries.py`: return all `Relationship` objects where `source` or `target` equals `element_id`; write `test_query_relationships_unit()` in `tests/unit/test_store_queries.py`; wire into `DesignStore.query_relationships()` in `src/adp/store/store.py` with a structured log entry (FR-005)
- [ ] T044 [US4] Verify `test_query_satisfies_returns_matching_elements`, `test_query_satisfies_returns_empty_for_unknown_requirement`, `test_query_orphan_requirements_identifies_orphans`, `test_query_verdict_chain_returns_full_chain`, and all unit tests in `test_store_queries.py` pass

**Checkpoint**: `pytest tests/integration/test_store.py tests/unit/test_store_queries.py` green; SC-004 (traceability queries return correct results) verifiable

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Coverage, quality gates, type correctness, and ART-VI logging verification

- [ ] T045 [P] Run `pytest --cov=adp --cov-report=term-missing` and verify total line coverage ≥ 85%
- [ ] T045b [P] Write `test_get_latency_500_entities()` in `tests/integration/test_store.py`: construct and save an `ArchitectureDescription` containing exactly 500 entities (distribute across elements, requirements, relationships, and options); time `await store.get(design_id)` using `time.perf_counter()`; assert elapsed < 1.0 seconds; mark the test `@pytest.mark.slow` and add `--slow` flag to the CI pipeline step (SC-005 / NFR-001); identify uncovered lines in `src/adp/store/` and add targeted unit tests in `tests/unit/test_store_queries.py` until threshold is met (QG-04)
- [ ] T046 [P] Run `ruff check src/adp/store/ tests/integration/ tests/unit/test_store_queries.py` and `mypy src/adp/store/`; fix all issues (QG-06)
- [ ] T047 [P] Verify ART-VI logging: write `test_save_emits_structured_log()` in `tests/unit/test_store_queries.py` (or a new `tests/unit/test_store_logging.py`) that calls `log_operation(...)` with all parameter combinations and asserts the JSON log contains `operation`, `design_id`, `duration_ms`; asserts `content` and `database_url` are NOT present in log output (QG-10)
- [ ] T048 [P] Run `bandit -r src/adp/store/ -ll` and `pip-audit --local`; fix any HIGH-severity findings or confirmed CVEs in new dependencies (QG-06, QG-07); also verify via `grep -r "ADP_DATABASE_URL" src/ tests/ fixtures/` that the value is only ever referenced as `os.environ["ADP_DATABASE_URL"]` or similar env lookup — no hardcoded connection string anywhere (QG-08)
- [ ] T049 Run `pip show sqlalchemy asyncpg alembic pydantic-settings pytest-asyncio testcontainers` to capture installed versions; replace the minimum-version constraints from T001 with exact pinned specifiers in `pyproject.toml`; create a fresh venv, run `pip install -e ".[dev]"`, and confirm all imports resolve (QG-18)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup (T001–T005) — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Foundational complete — 🎯 MVP; save/retrieve proves the persistence foundation
- **US2 (Phase 4)**: Depends on US1 `save()` existing (extends it); may begin when T017-T018 are implemented
- **US3 (Phase 5)**: Depends on US1 `save()` and `get()` existing; requires T030 to extend `save()` further
- **US4 (Phase 6)**: Depends on US1 `get()` existing (T018); no dependency on US2 or US3
- **Polish (Phase 7)**: Depends on all desired user stories complete

### User Story Dependencies

- **US1 (P1)**: Can start after Phase 2 — no dependencies on other stories
- **US2 (P1)**: Logically extends US1's `save()` — depends on T017 (save implementation)
- **US3 (P2)**: Extends US1's `save()` and `get()` — depends on T017-T018; no dependency on US2
- **US4 (P2)**: Depends only on US1's `get()` (T018) for content retrieval; no dependency on US2 or US3

### Parallel Opportunities

- T002, T003, T004 (Setup) — parallel: different files
- T014, T015, T016 (US1 tests) — parallel: same file but independent test functions
- T020, T021, T022 (US2 tests) — parallel: independent test functions
- T026, T027, T028, T029 (US3 tests) — parallel: independent test functions
- T034, T035, T036, T037, T038 (US4 tests) — parallel: different files / independent functions
- T039, T040, T041 (US4 queries.py) — parallel: separate functions in same file
- T045, T046, T047, T048 (Polish) — parallel: independent tools

---

## Parallel Example: User Story 4

```bash
# Write all US4 tests in parallel (independent functions):
Task T034: test_query_satisfies_returns_matching_elements
Task T035: test_query_satisfies_returns_empty_for_unknown_requirement
Task T036: test_query_orphan_requirements_identifies_orphans
Task T037: test_query_verdict_chain_returns_full_chain
Task T038: tests/unit/test_store_queries.py unit tests

# Implement query functions in parallel (different functions, same file):
Task T039: queries.query_satisfies()
Task T040: queries.query_orphan_requirements()
Task T041: queries.query_verdict_chain()

# Wire into store (sequential — same file):
T042 → T043 → T044
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T005)
2. Complete Phase 2: Foundational (T006–T013) — CRITICAL: blocks all stories
3. Write US1 tests T014–T016 — verify they fail
4. Implement US1 (T017–T019)
5. **STOP and VALIDATE**: `pytest tests/integration/test_store.py -k "round_trip or invalid or nonexistent"` green
6. `adp-generate --check` still exits 0 (ADP-SPEC-001 unaffected)

### Incremental Delivery

1. Phase 1 + 2 → DB schema and store skeleton ready
2. Phase 3 (US1) → Save and retrieve working (MVP)
3. Phase 4 (US2) → Audit trail enforced atomically
4. Phase 5 (US3) → Immutable versioning active
5. Phase 6 (US4) → Traceability queries operational
6. Phase 7 → All quality gates green

---

## Notes

- [P] tasks = different files or independent functions; no file conflict on concurrent execution
- [Story] label maps each task to its user story and acceptance scenario in spec.md
- Tests MUST fail before implementation; commit the failing test before writing the implementation
- The `testcontainers` fixture is session-scoped (one container per test session); each test runs in a rolled-back transaction to maintain isolation without teardown overhead
- `ADP_DATABASE_URL` MUST be set from environment; never hardcode a connection string
- `adp-generate --check` must remain exit 0 throughout — this feature adds no model changes
- Constitution gates relevant: QG-03, QG-04, QG-05, QG-06, QG-07, QG-08, QG-10, QG-13, QG-16, QG-18
