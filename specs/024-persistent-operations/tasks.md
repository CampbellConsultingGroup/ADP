# Tasks: Persistent Operation Store (ADP-SPEC-024)

**Input**: Design documents from `/specs/024-persistent-operations/`
**Prerequisites**: ADP-SPEC-023 complete ✅
**Risk**: High — modifies core async operation flow. Each phase must be independently tested.

---

## Phase 1: Setup — Operations Table + Store Class

### Tests (MANDATORY — ART-IV)

- [X] T001 [P] Create `tests/unit/test_operations_store.py`: write `test_create_and_get_returns_operation()` — create an in-memory SQLite DB; instantiate `OperationStore`; call `create("OP-001", "intake", "DSN-001", "actor", {"status": "pending"})`; call `get("OP-001")`; assert returned dict has correct fields
- [X] T002 [P] Write `test_update_changes_status_and_payload()`: create then update status to "completed" and add payload data; assert `get()` returns updated values
- [X] T003 [P] Write `test_get_nonexistent_returns_none()`: `get("MISSING")` returns `None`
- [X] T004 [P] Write `test_delete_expired_removes_old_rows()`: create two operations, one with `expires_at` in the past, one in the future; call `delete_expired()`; assert only the future one remains
- [X] T005 [P] Write `test_mark_stale_running_as_failed()`: create an operation with status "running"; call `mark_stale_running_as_failed("restart")`; assert status is "failed" and error field is set

### Implementation

- [X] T006 Create Alembic migration `alembic/versions/XXXX_add_operations_table.py`: defines `operations` table with columns `id TEXT PK`, `type TEXT`, `design_id TEXT`, `status TEXT DEFAULT 'pending'`, `payload JSONB DEFAULT '{}'`, `actor TEXT DEFAULT 'architect'`, `error TEXT nullable`, `created_at TIMESTAMPTZ DEFAULT now()`, `updated_at TIMESTAMPTZ DEFAULT now()`, `expires_at TIMESTAMPTZ NOT NULL`; creates indexes `ix_ops_design_type_status (design_id, type, status)` and `ix_ops_expires_at (expires_at)`; run `alembic upgrade head` to apply
- [X] T007 Create `src/adp/store/operations.py`: implement `OperationStore` with async methods `create()`, `get()`, `update()`, `update_option_status()` (uses `UPDATE ... WHERE payload->>'status' = 'pending' RETURNING id` for optimistic concurrency), `delete_expired()`, `mark_stale_running_as_failed()`; session factory injected via constructor
- [X] T008 Edit `src/adp/store/__init__.py`: export `OperationStore`
- [X] T009 Edit `src/adp/api/deps.py`: add `async def get_operation_store() -> OperationStore` dependency that returns a singleton `OperationStore` instance using the shared session factory from Move A (ADP-SPEC-023)

**Checkpoint**: `pytest tests/unit/test_operations_store.py -q --no-cov` — 5+ tests pass

---

## Phase 2: Startup Hook + Lifespan

- [X] T010 Edit `src/adp/api/app.py`: replace any existing `@app.on_event("startup")` with a proper `asynccontextmanager` lifespan function; on startup: call `op_store.mark_stale_running_as_failed("server restarted during processing")`; schedule a repeating 10-minute background coroutine calling `op_store.delete_expired()` using `asyncio.create_task` with a loop
- [X] T011 [P] Run `pytest tests/ --ignore=tests/integration -q --no-cov` — all existing tests still pass with new lifespan

---

## Phase 3: Migrate Intake Router

### Tests (MANDATORY — ART-IV)

- [X] T012 [P] [US1] Edit `tests/contract/test_intake_api.py`: update fixture to mock `OperationStore` instead of `_intake_store` dict — replace `rec_module._intake_store.clear()` / direct dict manipulation with `AsyncMock` of `OperationStore` methods; ensure all existing intake contract tests still pass

### Implementation

- [X] T013 [US1] Edit `src/adp/api/routers/intake.py`: remove `_intake_store: dict = {}`; add `Depends(get_operation_store)` parameter to all endpoints that currently use `_intake_store`; replace every `_intake_store[op_id] = {...}` with `await op_store.create(...)` and every `_intake_store.get(op_id)` with `await op_store.get(op_id)`
- [X] T014 [US1] Edit `src/adp/intake/orchestrator.py`: change `ExtractionOrchestrator.run()` signature to accept `OperationStore` instead of `dict[str, Any]`; replace all dict-style writes (`op["status"] = "completed"`) with `await op_store.update(op_id, status="completed", payload_patch={...})`
- [X] T015 [P] Run `pytest tests/contract/test_intake_api.py -q --no-cov` — all pass

**Checkpoint**: `POST /intake` + poll cycle works end-to-end; restart server between POST and poll; poll returns the result

---

## Phase 4: Migrate Recommend Router

### Tests (MANDATORY — ART-IV)

- [X] T016 [P] [US2] Edit `tests/contract/test_recommend_api.py`: update fixture to mock `OperationStore` instead of `_recommend_store` dict; ensure all existing recommend contract tests still pass

### Implementation

- [X] T017 [US2] Edit `src/adp/api/routers/recommend.py`: remove `_recommend_store: dict = {}`; inject `OperationStore` via `Depends(get_operation_store)`; replace dict reads/writes with `OperationStore` calls; for accept/reject use `op_store.update_option_status()` for optimistic concurrency
- [X] T018 [US2] Edit `src/adp/recommendation/orchestrator.py`: change `run()` and `materialize_option()` to accept `OperationStore` instead of `dict`; update all dict-style access accordingly
- [X] T019 [P] Run `pytest tests/contract/test_recommend_api.py -q --no-cov` — all pass

**Checkpoint**: `POST /recommend` + accept cycle works; concurrent accepts return 200 + 409 as expected

---

## Phase 5: Polish

- [X] T020 [P] Run `pytest tests/ --ignore=tests/integration -q --no-cov` — full suite clean
- [X] T021 [P] Run `ruff check src/adp/store/operations.py src/adp/api/routers/intake.py src/adp/api/routers/recommend.py` — clean
- [X] T022 [P] Verify no `_intake_store\|_recommend_store` references remain: `grep -rn "_intake_store\|_recommend_store" src/adp/` returns zero results
- [X] T023 [P] Run `alembic upgrade head` against real DB; verify `\d operations` shows correct schema

---

## Notes

- `update_option_status()` uses PostgreSQL's `jsonb_set()` with a WHERE clause checking current status — this gives concurrency safety without explicit row locks
- The orchestrators currently log JSON with `{"operation": ...}` shape — this logging can stay as-is; only the storage backend changes
- Test mocks for `OperationStore` can use `AsyncMock(spec=OperationStore)` to ensure the interface is correctly mocked
- SQLite (used in contract tests) does not support JSONB or `jsonb_set()` — the `OperationStore` must abstract these operations so SQLite-compatible SQL is used in tests (simple `UPDATE` with full payload replacement)
