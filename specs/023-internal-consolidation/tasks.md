# Tasks: Internal Architecture Consolidation (ADP-SPEC-023)

**Input**: Design documents from `/specs/023-internal-consolidation/`
**Prerequisites**: All complete ✅
**Risk**: Zero user-visible changes. Full test suite must pass after every phase.

---

## Phase 1: Move A — Single DB Connection Pool

- [X] T001 Read `src/adp/api/deps.py` and understand the existing `get_design_store()` pattern; add `async def get_kb_session()` async generator that yields a SQLAlchemy `AsyncSession` from the same `_engine` as the design store (create if not already created); use `os.environ.get("ADP_DATABASE_URL", ...)` — same URL as the design store
- [X] T002 Edit `src/adp/api/routers/knowledge.py`: remove `_engine`, `_session_factory`, `_get_session_factory()`, and `_get_db_session()` (lines ~55-75); replace all `Depends(_get_db_session)` with `Depends(get_kb_session)` imported from `adp.api.deps`; add `from adp.api.deps import get_kb_session` at top
- [X] T003 Edit `src/adp/api/routers/calm.py`: remove the `_get_kb_session()` wrapper function (which currently delegates to `knowledge._get_db_session`); replace `Depends(_get_kb_session)` with `Depends(get_kb_session)` imported from `adp.api.deps`
- [X] T004 [P] Run `pytest tests/ --ignore=tests/integration -q --no-cov` — all tests pass after Move A

---

## Phase 2: Move B — Audit Utility Relocation

- [X] T005 Read `src/adp/audit/writer.py` to understand its current contents; add `def next_audit_id(design: Any) -> str` as a public function implementing the same logic as the current `_next_audit_id` in `adp.intake.orchestrator` (reads `design.audit_log`, finds max numeric suffix, returns next ID like `AUD-{N:03d}`)
- [X] T006 Edit `src/adp/intake/orchestrator.py`: add `from adp.audit.writer import next_audit_id` at the top; add `_next_audit_id = next_audit_id` backward-compat alias immediately after; remove the original `_next_audit_id` function definition
- [X] T007 Edit `src/adp/recommendation/orchestrator.py`: change `from adp.intake.orchestrator import _next_audit_id` to `from adp.audit.writer import next_audit_id as _next_audit_id`
- [X] T008 Edit `src/adp/api/routers/calm.py`: change `from adp.intake.orchestrator import _next_audit_id` to `from adp.audit.writer import next_audit_id as _next_audit_id`
- [X] T009 [P] Run `pytest tests/ --ignore=tests/integration -q --no-cov` — all tests pass after Move B

---

## Phase 3: Move C — LLMClient Relocation

- [X] T010 Create `src/adp/llm/__init__.py` as an empty module marker
- [X] T011 Create `src/adp/llm/client.py` by copying the full content of `src/adp/intake/llm.py` (including `_EXTRACTION_SYSTEM_PROMPT`, `_is_anthropic`, `_strip_code_fence`, and `LLMClient` with all methods `extract`, `chat`, `_call_anthropic`, `_call_anthropic_chat`, `_call_openai_compatible`, `_call_openai_compatible_chat`)
- [X] T012 Replace `src/adp/intake/llm.py` content with a backward-compatible re-export only: `from adp.llm.client import LLMClient as LLMClient; from adp.llm.client import _EXTRACTION_SYSTEM_PROMPT as _EXTRACTION_SYSTEM_PROMPT` — preserving any other names used by the intake module
- [X] T013 Edit `src/adp/api/routers/recommend.py`: update `from adp.intake.llm import LLMClient` to `from adp.llm.client import LLMClient`
- [X] T014 Edit `src/adp/api/routers/config.py`: update LLMClient import path to `adp.llm.client`
- [X] T015 Edit `src/adp/recommendation/steps.py`: check for any direct `adp.intake.llm` imports and update to `adp.llm.client`
- [X] T016 [P] Run `pytest tests/ --ignore=tests/integration -q --no-cov` — all tests pass after Move C

---

## Phase 4: Validation

- [X] T017 [P] Run `ruff check src/adp/` — clean
- [X] T018 [P] Verify: `grep -rn "from adp.intake.llm import LLMClient" src/adp/` returns only the re-export line in `src/adp/intake/llm.py` itself
- [X] T019 [P] Verify: `grep -rn "from adp.intake.orchestrator import _next_audit_id" src/adp/` returns only the backward-compat alias line in `src/adp/intake/orchestrator.py`
- [X] T020 [P] Verify: `grep -rn "_get_session_factory\|_get_db_session" src/adp/api/routers/knowledge.py` returns zero results

---

## Notes

- Do not delete `src/adp/intake/llm.py` — the re-export must remain for backward compatibility with any external tools or scripts
- The backward-compat alias `_next_audit_id = next_audit_id` in `intake/orchestrator.py` can be removed in a future cleanup spec once all callers have been updated
- The `adp.calm.importer` CLI creates its own SQLAlchemy engine intentionally — it runs outside FastAPI context and has no access to `adp.api.deps`. This is correct behaviour and must NOT be changed in this spec.
