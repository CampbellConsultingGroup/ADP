# Tasks: Immutable LLM Reasoning Store (ADP-SPEC-027)

**Input**: Design documents from `/specs/027-llm-reasoning-store/`
**Prerequisites**: ADP-SPEC-024 (operations table) ✅, ADP-SPEC-023 (shared DB pool) ✅

---

## Phase 1: Database Schema

- [X] T001 Create Alembic migration `src/adp/store/migrations/versions/004_llm_reasoning_log.py`:
  - `llm_reasoning_log` table: `id UUID PK DEFAULT gen_random_uuid()`, `operation_id TEXT NOT NULL`, `option_id TEXT`, `step_name TEXT NOT NULL`, `model_id TEXT NOT NULL`, `reasoning_text TEXT NOT NULL`, `truncated BOOLEAN NOT NULL DEFAULT FALSE`, `prompt_hash TEXT NOT NULL`, `input_tokens INTEGER NOT NULL DEFAULT 0`, `output_tokens INTEGER NOT NULL DEFAULT 0`, `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
  - Index `ix_reasoning_operation` on `(operation_id)`
  - Index `ix_reasoning_option` on `(option_id)` WHERE option_id IS NOT NULL
  - PL/pgSQL function `llm_reasoning_immutable()` that raises for both UPDATE and DELETE
  - `BEFORE UPDATE` trigger `trg_reasoning_no_update`
  - `BEFORE DELETE` trigger `trg_reasoning_no_delete`
  - Run `alembic upgrade head` to apply; verify `\d llm_reasoning_log` shows correct schema
- [X] T002 [P] Verify triggers work: `psql -c "INSERT INTO llm_reasoning_log (operation_id,step_name,model_id,reasoning_text,prompt_hash) VALUES ('test','generate','claude','test rationale','abc');"` then `psql -c "UPDATE llm_reasoning_log SET reasoning_text='tampered' WHERE operation_id='test';"` → expect error P0001; `psql -c "DELETE FROM llm_reasoning_log WHERE operation_id='test';"` → expect error P0001

---

## Phase 2: ReasoningStore + Unit Tests

### Tests (MANDATORY — ART-IV)

- [X] T003 [P] Create `tests/unit/test_reasoning_store.py`: write `test_write_creates_row()` — create in-memory SQLite DB with `llm_reasoning_log` table (without triggers, SQLite has no PL/pgSQL); call `reasoning_store.write(ReasoningRecord(...))`; query the table; assert 1 row with correct field values
- [X] T004 [P] Write `test_list_for_operation_returns_records()`: write 2 records for op-A, 1 for op-B; `list_for_operation("op-A")`; assert 2 records returned, sorted by created_at ascending
- [X] T005 [P] Write `test_list_filters_by_option_id()`: write records for same operation, different option_ids; `list_for_operation(op_id, option_id="OPT-001")`; assert only OPT-001 records returned
- [X] T006 [P] Write `test_reasoning_text_truncated_at_100k()`: write a record with 150,000 char reasoning_text; assert stored text is 100,000 chars and `truncated=True`
- [X] T007 [P] Write `test_prompt_hash_is_sha256()`: write record with known prompt; assert `prompt_hash == hashlib.sha256(known_prompt.encode()).hexdigest()`
- [X] T008 [P] Write `test_list_returns_empty_for_unknown_operation()`: `list_for_operation("DOES-NOT-EXIST")`; assert empty list (not error)

### Implementation

- [X] T009 Create `src/adp/store/reasoning.py`:
  - `ReasoningRecord` dataclass: `operation_id: str`, `step_name: str`, `model_id: str`, `reasoning_text: str`, `prompt_hash: str`, `input_tokens: int = 0`, `output_tokens: int = 0`, `option_id: str | None = None`
  - `_REASONING_MAX_CHARS = 100_000`
  - `_hash_prompt(prompt: str) -> str` — SHA-256 hex of prompt encoded as UTF-8
  - `ReasoningStore` class with `__init__(self, session_factory)`:
    - `async def write(self, record: ReasoningRecord) -> None` — INSERT with truncation
    - `async def list_for_operation(self, operation_id: str, option_id: str | None = None) -> list[dict]` — SELECT with optional filter, ORDER BY created_at ASC
- [X] T010 Edit `src/adp/store/__init__.py`: export `ReasoningStore`, `ReasoningRecord`

**Checkpoint**: `pytest tests/unit/test_reasoning_store.py -q --no-cov` — 6 tests pass

---

## Phase 3: API Endpoint + Contract Tests

### Tests (MANDATORY — ART-IV)

- [X] T011 [P] Create `tests/contract/test_reasoning_api.py`: write `test_list_reasoning_returns_200_with_records()` — mock ReasoningStore returning 2 records; GET `/api/v1/reasoning?operation_id=OP-001`; assert 200 and 2 items in response with `step_name`, `reasoning_text`, `model_id`, `created_at` present; assert `prompt_hash` NOT in response
- [X] T012 [P] Write `test_list_reasoning_empty_returns_empty_list()`: mock returns []; GET `/api/v1/reasoning?operation_id=MISSING`; assert 200 and `{"records": []}` (not 404)
- [X] T013 [P] Write `test_list_reasoning_filters_by_option_id()`: mock; GET with `?operation_id=OP-001&option_id=OPT-001`; assert mock was called with both parameters

### Implementation

- [X] T014 Create `src/adp/api/routers/reasoning.py`:
  - `ReasoningResponse` Pydantic model: `id: str`, `option_id: str | None`, `step_name: str`, `model_id: str`, `reasoning_text: str`, `truncated: bool`, `input_tokens: int`, `output_tokens: int`, `created_at: datetime` — NO `prompt_hash` field
  - `GET /api/v1/reasoning` with query params `operation_id: str`, `option_id: str | None = None`
  - Returns `{"records": list[ReasoningResponse]}` sorted by `created_at` ascending
  - Depends on `get_reasoning_store()` from `adp.api.deps`
- [X] T015 Edit `src/adp/api/deps.py`: add `get_reasoning_store()` singleton dependency using the shared KB session factory
- [X] T016 Edit `src/adp/api/app.py`: import and register `reasoning.router`

**Checkpoint**: `pytest tests/contract/test_reasoning_api.py -q --no-cov` — all pass

---

## Phase 4: Pipeline Integration

- [X] T017 Edit `src/adp/recommendation/steps.py` `generate_step()`: after building each `SolutionOption`, fire-and-forget write to `ReasoningStore` with `step_name="generate"`, `option_id=opt.option_id`, `reasoning_text=opt.rationale`, `prompt_hash=_hash_prompt(f"{system}\n{user}")`, `input_tokens`, `output_tokens` from the LLM response; import `_hash_prompt` from `adp.store.reasoning`; get store via `adp.api.deps.get_reasoning_store()` inside the function (lazy import to avoid circular deps)
- [X] T018 Edit `src/adp/recommendation/steps.py` `analyze_tradeoffs_step()`: after building trade-off entries for each option, fire-and-forget write with `step_name="analyze_tradeoffs"`, `option_id`, `reasoning_text` = newline-joined trade-off rationales, `prompt_hash` from the per-option prompt
- [X] T019 Edit `src/adp/intake/orchestrator.py` `run()`: after successful extraction, fire-and-forget write with `step_name="extract"`, `option_id=None`, `reasoning_text=result_summary`, `prompt_hash=_hash_prompt(submission.text)`, token counts from telemetry span

---

## Phase 5: Polish

- [X] T020 [P] Run `pytest tests/ --ignore=tests/integration -q --no-cov` — full suite clean
- [X] T021 [P] Run `ruff check src/adp/store/reasoning.py src/adp/api/routers/reasoning.py` — clean
- [X] T022 [P] Run `alembic upgrade head` on live DB; `psql -c "SELECT * FROM llm_reasoning_log LIMIT 5;"` — table exists with correct columns
- [X] T023 [P] Manual verification: trigger a recommendation; `psql -c "SELECT step_name, model_id, length(reasoning_text), truncated FROM llm_reasoning_log ORDER BY created_at DESC LIMIT 10;"` — records present

---

## Notes

- Fire-and-forget writes use `asyncio.create_task()` inside async endpoint/step context — reasoning write failures must NOT block the pipeline response
- If `get_reasoning_store()` is not available (e.g. no DB configured), catch the exception and log a warning; never raise
- The `prompt_hash` stored is the SHA-256 hex of the combined system+user prompt bytes — provides auditability without storing potentially large/sensitive prompts
- SQLite test DB uses a TEXT column (not UUID) for `id` with a default `str(uuid.uuid4())` applied in Python — triggers are not testable in SQLite (PL/pgSQL only)
- For the pipeline steps, the `ReasoningStore` singleton is fetched via `adp.api.deps.get_reasoning_store()` which uses the shared KB session factory — no new DB connections
