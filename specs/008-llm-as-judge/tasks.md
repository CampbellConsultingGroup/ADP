# Tasks: LLM-as-a-Judge Validation

**Input**: Design documents from `/specs/008-llm-as-judge/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: Tests are MANDATORY for all ADP features (ART-IV). Test tasks MUST appear before their implementation counterparts in every user-story phase. Tests MUST be committed and verified to fail before any implementation begins.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no file conflicts)
- **[Story]**: Which user story this task belongs to (US1–US5)
- Include exact file paths in every description

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create directory skeleton — no new dependencies needed (all in stack from ADP-SPEC-006/007)

- [x] T001 [P] Create directory structure: `src/adp/validation/`, `tests/validation/`; create `src/adp/validation/__init__.py` (placeholder), `tests/validation/__init__.py` (empty)
- [x] T002 Verify: `python3 -c "import adp.validation; print('ok')"` resolves after reinstall
- [x] T003 [P] Confirm no new packages needed: `python3 -c "import langgraph, opentelemetry, httpx; print('all ok')"` — all in stack from prior specs

**Checkpoint**: `pytest tests/ --ignore=tests/integration -q --no-cov` still passes all existing tests

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data models, pure `gate()` function, prompt templates, telemetry stub, and orchestrator skeleton — MUST be complete before any user story

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T004 Create all validation data models in `src/adp/validation/models.py`: `FindingSeverity(StrEnum)` (`critical`, `major`, `minor`, `advisory`); `VerdictStatus(StrEnum)` with values `PASS = "pass"` (NOT `pass_` — StrEnum stores the string `"pass"` in JSON even though the Python attribute name must differ from the reserved keyword), `FAIL = "fail"`, `INDETERMINATE = "indeterminate"`, `OVERRIDDEN = "overridden"`; add a test asserting `VerdictStatus.PASS.value == "pass"` to prevent regression; `Finding` dataclass (all fields from data-model.md: `finding_id`, `operation_id`, `critic_name`, `element_id`, `severity`, `description`, `citation: CitationRef | None`, `score: float | None`); `GatingThreshold` dataclass (`max_critical=0`, `max_major=3`, `max_minor=10`, `version="1.0.0"`); `CriticOutput` dataclass (all fields from data-model.md); `Verdict` dataclass (all fields from data-model.md including `citations_present: bool`); `ValidationState` TypedDict (all pipeline state fields from data-model.md)
- [x] T005 Implement `gate(findings: list[Finding], thresholds: GatingThreshold, *, llm_critics_ran: bool = True) -> str` in `src/adp/validation/gate.py` with the COMPLETE logic — no `NotImplementedError` stub is needed since `gate()` is pure Python with zero external dependencies: count non-advisory findings by severity (`critical`, `major`, `minor`); if `critical_count > thresholds.max_critical OR major_count > thresholds.max_major OR minor_count > thresholds.max_minor` return `"fail"`; if `llm_critics_ran=False` (all LLM critics failed to run) return `"indeterminate"`; otherwise return `"pass"`; this is a PURE FUNCTION — no side effects, no external calls, no randomness, no imports beyond standard library types (QG-15 / ART-X)
- [x] T006 [P] Create LLM prompt templates in `src/adp/validation/prompts.py`: `CRITIC_SYSTEM_PROMPT_TEMPLATE` (common scoring rubric + response schema per contracts/critic-prompt-contract.md); `standards_user_prompt(elements_summary, standards_summary)`, `principles_user_prompt(elements_summary, principles_summary)`, `pattern_fit_user_prompt(elements_summary, patterns_summary)`, `consistency_user_prompt(elements_summary, prior_solutions_summary)` functions; `SCORING_RUBRIC` constant string (1.0/0.75/0.5/0.25/0.0 anchors)
- [x] T007 [P] Create `ValidationTelemetry` class in `src/adp/validation/telemetry.py`: `emit_span(output: CriticOutput, correlation_id: str | None) -> None` using `opentelemetry.trace`; span name `adp.validation.{output.critic_name}`; attributes: `critic_name`, `retrieved_knowledge_refs` (comma-joined), `input_tokens`, `output_tokens`, `cost_usd`, `latency_ms`, `correlation_id`; API key MUST NOT appear; silently no-ops without OTel exporter
- [x] T008 Create `ValidationOrchestrator` skeleton in `src/adp/validation/orchestrator.py`: `__init__(self, llm, knowledge_retrieval, design_store, thresholds=None, telemetry=None)`; stub `async run(operation_id, design_id, design_version, operation_store, correlation_id=None) -> None` raising `NotImplementedError`; stub `async override_verdict(verdict_id, operation_id, reviewing_actor, justification, operation_store, design_id) -> None` raising `NotImplementedError`

**Checkpoint**: `python3 -c "from adp.validation import ValidationOrchestrator, Verdict, Finding; print('ok')"` succeeds

---

## Phase 3: User Story 1 — Validate a Design and Receive Cited Findings (Priority: P1) 🎯 MVP

**Goal**: Submit a design; 4 LLM critics run in parallel via `asyncio.gather()`; each critic retrieves knowledge and produces cited findings; results aggregate into a `Verdict` with all findings.

**Independent Test**: Mock all 4 critics to return known findings; call orchestrator.run(); assert Verdict contains all findings from all critics; assert every finding produced by a mocked-LLM-critic has a non-None `citation` (FR-002 / ART-VII).

### Tests for User Story 1 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T009 [P] [US1] Write failing `test_standards_critic_produces_cited_findings()` in `tests/validation/test_critics.py`: mock `LLMClient.extract` returning a standards response with 2 findings citing "STD-001" and "STD-002"; call `standards_critic(state, llm=mock_llm, knowledge_retrieval=mock_kr, telemetry=mock_telemetry)`; assert returned `CriticOutput` has 2 `Finding` objects each with a non-None `citation.item_id`
- [x] T010 [P] [US1] Write failing `test_principles_critic_produces_cited_findings()`, `test_pattern_fit_critic_produces_cited_findings()`, `test_consistency_critic_produces_cited_findings()` in `tests/validation/test_critics.py` — same structure as T009 for the other 3 critics; each asserts findings carry citations
- [x] T011 [P] [US1] Write failing `test_full_pipeline_produces_verdict()` in `tests/validation/test_orchestrator.py`: mock all 4 LLM critics; call `orchestrator.run()`; assert `operation_store[op_id]["verdict"]` is a `Verdict` object with `findings` non-empty and each finding has `citation` or is `advisory`
- [x] T012 [P] [US1] Write failing `test_uncited_finding_is_advisory()` in `tests/validation/test_critics.py`: mock LLM returning a finding with `cited_id` NOT in the provided knowledge list; assert resulting finding has `severity=advisory` and `citation=None`; assert it is excluded from the blocking count in gate

### Implementation for User Story 1

- [x] T013 [US1] Implement `standards_critic(state, *, llm, knowledge_retrieval, telemetry) -> CriticOutput` in `src/adp/validation/critics.py`: retrieve `standard` knowledge items via `knowledge_retrieval.hybrid_search(kinds=["standard"])`; build prompt with `standards_user_prompt()`; call `llm.extract()`; parse response into `CriticOutput.findings` — map `cited_id` to `CitationRef` if resolvable (call `knowledge_retrieval.resolve_citation()`); if unresolvable set `citation=None` and `severity=advisory`; derive severity from score via rubric anchors (0.0→critical, 0.25→major, 0.5→major, 0.75→minor, 1.0→no findings); emit telemetry span
- [x] T014 [US1] Implement `principles_critic()`, `pattern_fit_critic()`, `consistency_critic()` in `src/adp/validation/critics.py` — same pattern as T013 with their respective knowledge kinds (`principle`, `pattern`, `prior_solution`) and prompt functions
- [x] T015 [US1] Implement `aggregate(critic_outputs: list[CriticOutput]) -> tuple[list[Finding], float | None, bool]` in `src/adp/validation/aggregator.py`: merge all findings; compute composite_score as mean of non-None scores (returns `None` if all scores are None); set `citations_present = any(f.citation is not None for f in all_findings)`; emit a no-LLM telemetry span with `critic_name="aggregate"`, `composite_score`, and latency (per research Decision 9 span naming convention `adp.validation.aggregate`; cost=0, input_tokens=0 for this non-LLM step)
- [x] T016 [US1] Implement `orchestrator.run()` in `src/adp/validation/orchestrator.py`: load design via store; determine if structural check passes (call `structural_critic()` — stub returning no findings for now); if passes, fan-out `asyncio.gather(standards_critic, principles_critic, pattern_fit_critic, consistency_critic)`; call `aggregate()`; call `gate(findings, thresholds, llm_critics_ran=bool(critic_outputs))`; if gate returns `"indeterminate"`, set `op["status"] = "failed"`, `op["error_description"] = "All LLM critics failed to run; verdict is indeterminate"`, and `verdict.status = VerdictStatus.INDETERMINATE`; build `Verdict`; set `citations_present` on `operation_store[op_id]["span"]["citations_present"]`; emit a no-LLM telemetry span with `critic_name="gate"`, pass/fail/indeterminate result, and latency (per research Decision 9 — `adp.validation.gate`); store verdict; set status `completed` or `failed`
- [x] T017 [US1] Update `src/adp/validation/__init__.py` to export `ValidationOrchestrator`, `Verdict`, `Finding`, `FindingSeverity`, `VerdictStatus`, `GatingThreshold`; verify T009–T012 all pass

**Checkpoint**: `pytest tests/validation/test_critics.py tests/validation/test_orchestrator.py -q --no-cov` green; US1 demonstrable with mocked critics

---

## Phase 4: User Story 2 — Deterministic Pass/Fail Verdict (Priority: P1)

**Goal**: `gate()` is a pure function — calling it twice with identical inputs produces identical output; threshold breaches produce `fail`; advisory findings never block; thresholds snapshot stored in Verdict.

**Independent Test**: Call `gate()` twice with the same inputs; assert results are equal. Change one count past threshold; assert result changes deterministically.

### Tests for User Story 2 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T018 [P] [US2] Write failing `test_gate_is_deterministic()` in `tests/validation/test_gate.py`: call `gate(findings, thresholds)` twice with identical inputs; assert both return the same string; assert calling with empty findings + default thresholds returns `"pass"` (SC-002 / ART-X / QG-15) — this test CANNOT be mocked; it is pure Python
- [x] T019 [P] [US2] Write failing `test_gate_critical_threshold()`, `test_gate_major_threshold()`, `test_gate_minor_threshold()` in `tests/validation/test_gate.py`: assert that 1 critical finding with `max_critical=0` returns `"fail"`; assert 3 major with `max_major=3` returns `"pass"` (equal to threshold); assert 4 major with `max_major=3` returns `"fail"`; assert same for minor
- [x] T020 [P] [US2] Write failing `test_advisory_findings_never_block()` in `tests/validation/test_gate.py`: create 100 advisory findings; call gate with default thresholds; assert result is `"pass"` — advisory findings MUST NEVER block regardless of count
- [x] T021 [P] [US2] Write failing `test_gate_indeterminate_when_no_llm_critics_ran()` in `tests/validation/test_gate.py`: call `gate([], thresholds, llm_critics_ran=False)`; assert result is `"indeterminate"` — cannot gate when no critics ran

### Implementation for User Story 2

- [x] T022 [US2] Verify T005's `gate()` implementation is complete and correct: run `pytest tests/validation/test_gate.py -q --no-cov` and confirm all T018–T021 tests pass; no additional gate logic is needed if T005 is complete; confirm `gate()` has zero imports from LLM, HTTP, or async libraries (it is a pure function); the gate telemetry span is wired in T016 (orchestrator), not in `gate.py` itself

**Checkpoint**: `pytest tests/validation/test_gate.py -q --no-cov` green; `gate()` is demonstrably pure; SC-002 verifiable

---

## Phase 5: User Story 3 — Detect Orphan Elements and Dangling References (Priority: P2)

**Goal**: `structural_critic()` runs before LLM critics; orphan elements (empty `satisfies`) and dangling relationship targets produce `critical` findings; structural failures block LLM critics.

**Independent Test**: Submit a design with one orphan and one dangling reference; run structural_critic directly; assert 2 critical findings returned; run orchestrator.run() with the same design; assert LLM critics were NOT called (mock was never invoked).

### Tests for User Story 3 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T023 [P] [US3] Write failing `test_structural_critic_detects_orphan_element()` in `tests/validation/test_critics.py`: create an `ArchitectureDescription` with one element whose `satisfies` is empty; call `structural_critic(design)`; assert result has at least one `Finding` with `severity=critical`, `element_id` matching the orphan, and `description` mentioning "orphan" or "satisfies"
- [x] T024 [P] [US3] Write failing `test_structural_critic_detects_dangling_reference()` in `tests/validation/test_critics.py`: create a design with a `Relationship` whose `target` is `"ELM-999"` (not in elements list); assert structural_critic returns a `critical` finding mentioning "dangling" or "reference"
- [x] T025 [P] [US3] Write failing `test_structural_check_blocks_llm_critics()` in `tests/validation/test_orchestrator.py`: create a design with an orphan element; mock all LLM critics; call `orchestrator.run()`; assert none of the 4 mocked LLM critics were called; assert verdict status is `fail` with at least one structural finding

### Implementation for User Story 3

- [x] T026 [US3] Implement `structural_critic(design: ArchitectureDescription) -> CriticOutput` in `src/adp/validation/critics.py`: iterate elements — if `element.satisfies == []` add `critical` finding; iterate relationships — if `rel.target` not in `{e.id for e in design.elements}` add `critical` finding; return `CriticOutput` with `critic_name="structural"`, `score=None` (structural has no score), `citation=None` for all findings; emit telemetry span; this is a pure Python function with no LLM call
- [x] T027 [US3] Update `orchestrator.run()` in `src/adp/validation/orchestrator.py` to call `structural_critic(design)` before the asyncio.gather fan-out; if structural findings contain any `critical` findings, skip all LLM critics and immediately gate with `llm_critics_ran=False`; verify T023–T025 pass

**Checkpoint**: `pytest tests/validation/ -q --no-cov` green; SC-001 (orphan detection), QG-16 verifiable

---

## Phase 6: User Story 4 — Override a Verdict with Recorded Justification (Priority: P2)

**Goal**: `override_verdict()` changes a `fail` verdict to `overridden`; empty justification is rejected; override writes an `AuditEntry`; only `fail` verdicts can be overridden.

**Independent Test**: Call `override_verdict()` with empty justification and assert `ValueError`; call with valid justification and assert verdict status changes to `overridden`; assert `AuditEntry` was written with actor and justification.

### Tests for User Story 4 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T028 [P] [US4] Write failing `test_override_requires_non_empty_justification()` in `tests/validation/test_orchestrator.py`: inject a `fail` verdict; call `orchestrator.override_verdict(justification="")` and assert `ValueError` is raised; assert verdict status remains `fail`
- [x] T029 [P] [US4] Write failing `test_override_marks_verdict_overridden()` in `tests/validation/test_orchestrator.py`: inject a `fail` verdict; call `override_verdict(justification="Exception EXC-001 applies", reviewing_actor="sub:reviewer-456")`; assert `verdict.status == "overridden"` and `verdict.overridden_by == "sub:reviewer-456"` and `verdict.override_justification` is non-empty
- [x] T030 [P] [US4] Write failing `test_override_writes_audit_entry()` in `tests/validation/test_orchestrator.py`: after override, assert mock design_store.save was called with a design whose `audit_log` contains an `AuditEntry` with `actor == "sub:reviewer-456"` and `action == "override-validation-verdict"` (QG-13 / FR-006)
- [x] T031 [P] [US4] Write failing `test_cannot_override_pass_verdict()` and `test_cannot_override_indeterminate_verdict()` in `tests/validation/test_orchestrator.py`: assert `ValueError` raised when attempting to override a `pass` or `indeterminate` verdict

### Implementation for User Story 4

- [x] T032 [US4] Implement `orchestrator.override_verdict()` in `src/adp/validation/orchestrator.py`: retrieve verdict from operation_store; validate `status == "fail"` (raise `ValueError` otherwise); validate `justification` is non-empty; set `verdict.status = "overridden"`, `overridden_by`, `override_at`, `override_justification`; load design from store; write `AuditEntry` via ADP-SPEC-004 `write_audit_record()` with `action="override-validation-verdict"`, `actor=reviewing_actor`, `confirmation_id=verdict.verdict_id`; call `design_store.save(design, actor=reviewing_actor)`; verify T028–T031 pass

**Checkpoint**: `pytest tests/validation/test_orchestrator.py -q --no-cov` green; SC-005 (override audit) verifiable; QG-13, QG-14 gates satisfied

---

## Phase 7: User Story 5 — Inspect Each Critic's Telemetry (Priority: P2)

**Goal**: Every validation job emits exactly one span per critic (5 minimum: structural + 4 LLM); all spans share `correlation_id`; each LLM critic span carries retrieved knowledge refs, tokens, cost, and latency.

**Independent Test**: Run full orchestrator with all critics mocked; assert `mock_telemetry.emit_span` called at least 5 times; assert each call's `CriticOutput` carries the `correlation_id`; assert LLM critic spans have non-zero `input_tokens`.

### Tests for User Story 5 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T033 [P] [US5] Write failing `test_five_spans_emitted_per_job()` in `tests/validation/test_orchestrator.py`: run full orchestrator with mocked critics and mocked telemetry; assert `mock_telemetry.emit_span` was called at least 5 times (structural + 4 LLM); assert each call's `CriticOutput` has a non-empty `critic_name` (FR-007 / QG-11)
- [x] T034 [P] [US5] Write failing `test_all_spans_share_correlation_id()` in `tests/validation/test_orchestrator.py`: run with `correlation_id="trace-123"`; assert all emitted `CriticOutput` objects have `correlation_id == "trace-123"` in the telemetry call args (using mock inspection)
- [x] T035 [P] [US5] Write failing `test_failed_critic_span_has_error()` in `tests/validation/test_critics.py`: mock LLM to raise `ConnectionError`; call a critic; assert `CriticOutput.error` is set; assert `emit_span` still called (span emitted on failure as well as success)

### Implementation for User Story 5

- [x] T036 [US5] Implement `ValidationTelemetry.emit_span()` fully in `src/adp/validation/telemetry.py`: OTel span named `adp.validation.{output.critic_name}`; set all attributes from `CriticOutput` plus `correlation_id`; set span status to ERROR if `output.error` is set; silently no-op when no OTel exporter configured
- [x] T037 [US5] Verify all critic functions in `src/adp/validation/critics.py` emit telemetry spans in their `finally` blocks (so spans are emitted even on exception); verify T033–T035 pass

**Checkpoint**: `pytest tests/validation/ -q --no-cov` green; SC-004 (5 spans per job) verifiable; QG-11 gate satisfied

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Coverage, quality gates, ADP-SPEC-003 integration, security, final checks

- [x] T038 [P] Run `pytest tests/validation/ --cov=adp.validation --cov-report=term-missing` and verify ≥ 85% line coverage; add targeted tests for `empty design` (zero elements — structural critic should pass cleanly) and any other uncovered branches; note: `indeterminate` status is already covered by T021 and `all-advisory-pass` is covered by T020 — do not duplicate those tests here (QG-04)
- [x] T038b [P] Write `test_fan_out_completes_structurally()` in `tests/validation/test_orchestrator.py` (`@pytest.mark.slow`): run full orchestrator with all 5 critics mocked to return instantly; time the `await orchestrator.run()` call; assert elapsed < 1.0 seconds (SC-003 structural verification with mocked critics — real latency is bounded by the LLM endpoint in production)
- [x] T038c [P] Extend `test_operations_router_dispatches_validation()` in `tests/api/test_operations.py` (T042): assert the 202 response arrives before the background orchestrator task completes; use `asyncio.create_task()` dispatch and time the POST call to confirm handle is available well within 2 seconds (NFR-001 handle timing structural verification)
- [x] T038d [P] Add a comment block at the top of `src/adp/validation/orchestrator.py` documenting that long-term verdict persistence (NFR-002 v2 scope) will require a `validation_verdicts` database table; for v1 verdicts are accessible within the 24h operation TTL; this comment prevents future developers from silently dropping verdict history during refactoring
- [x] T039 [P] Run `ruff check src/adp/validation/ tests/validation/` and `mypy src/adp/validation/ --python-version 3.12 --ignore-missing-imports`; fix all issues (QG-06)
- [x] T040 [P] Run `bandit -r src/adp/validation/ -ll`; confirm `ADP_LLM_API_KEY` never appears in any log by grepping all `_logger.*` calls (QG-08)
- [x] T041 [P] Extend ADP-SPEC-003's operations router in `src/adp/api/routers/operations.py` to handle `kind=validation`: create a `get_validation_orchestrator()` FastAPI dependency in `src/adp/api/dependencies.py`; dispatch `orchestrator.run()` as background task when `kind=validation`; also extend `ConfirmationPayload` in `src/adp/api/models/confirmation.py` with `verdict_override: bool = False` — mirrors the `proposal_id` extension from ADP-SPEC-006 (T016b there); update confirmation router `src/adp/api/routers/confirmations.py` to call `orchestrator.override_verdict()` when `operation.kind == "validation"` and `confirmation.verdict_override == True`
- [x] T042 [P] Write `test_operations_router_dispatches_validation()` in `tests/api/test_operations.py`: POST `kind=validation`; assert 202 with operation handle; assert validation orchestrator background task created (mock orchestrator)
- [x] T043 [P] Write `test_api_key_never_in_validation_logs()` in `tests/validation/test_orchestrator.py`: run full orchestrator with recognizable fake API key; capture log output; assert fake key does not appear (QG-08 regression guard)
- [x] T044 Run `pytest tests/ --ignore=tests/integration -q --no-cov` confirming all existing tests unaffected; `adp-generate --check` confirms ADP-SPEC-001 schema still drift-free

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Foundational — 🎯 MVP; 4 LLM critics + aggregator + orchestrator.run()
- **US2 (Phase 4)**: Depends on Foundational (gate() must exist as a stub to test); `gate()` itself is pure Python and independent; implement before US1 is completed so critics can call it in US1
- **US3 (Phase 5)**: Depends on US1 `orchestrator.run()` existing; structural critic adds pre-check to existing run()
- **US4 (Phase 6)**: Depends on US1 (verdicts must exist to override); independent of US2/US3/US5
- **US5 (Phase 7)**: Depends on all critics being wired (US1 + US3); telemetry is already stubbed in Foundational
- **Polish (Phase 8)**: Depends on all desired user stories complete

### User Story Dependencies

- **US1 (P1)**: Can start after Phase 2 — no dependencies on other stories (note: depends on US2's `gate()` for orchestrator.run() to work; implement US2 first or wire stub)
- **US2 (P1)**: Can start after Phase 2 — `gate()` is pure Python; fully independent
- **US3 (P2)**: Depends on US1 `orchestrator.run()` (T016); adds structural pre-check
- **US4 (P2)**: Depends on US1 (verdicts exist); independent of US2/US3/US5
- **US5 (P2)**: Depends on US1 + US3 (all 5 critics must exist to test 5-span emission)

### Parallel Opportunities

- T001, T002, T003 (Setup): T001 and T003 parallel — different concerns
- T004, T005, T006, T007, T008 (Foundational): T004/T005/T006/T007 parallel — different files
- T009, T010, T011, T012 (US1 tests): all parallel — different test functions
- T018, T019, T020, T021 (US2 tests): all parallel — pure Python, independent
- T023, T024, T025 (US3 tests): all parallel — independent test functions
- T028, T029, T030, T031 (US4 tests): all parallel — independent test functions
- T033, T034, T035 (US5 tests): all parallel — independent test functions
- T038, T039, T040, T041, T042, T043 (Polish): all parallel — independent tools

---

## Suggested MVP Scope (US1 + US2)

1. Phase 1 + 2 → Foundational skeleton, pure `gate()` function
2. Write US2 tests T018-T021 FIRST (gate is pure; tests need no mocks)
3. Implement US2 T022 (`gate()` function)
4. Write US1 tests T009-T012 — verify they fail
5. Phase 3 US1: 4 LLM critics + aggregator + orchestrator.run()
6. **STOP and VALIDATE**: `pytest tests/validation/ -q` green; verdicts produced with cited findings; gating deterministic

### Full Incremental Delivery

1. Phase 1 + 2 → Foundation + gate()
2. Phase 4 (US2) → Gate verified deterministic **before** any LLM critics are wired
3. Phase 3 (US1) → 4 critics + full pipeline
4. Phase 5 (US3) → Structural pre-check active
5. Phase 6 (US4) → Override with audit
6. Phase 7 (US5) → Telemetry verified
7. Phase 8 → All quality gates green

---

## Notes

- [P] tasks = different files or independent test functions; no file conflict
- Tests MUST fail before implementation; commit the failing test first (ART-IV)
- `gate()` MUST be a pure function — import only standard library types; no async, no HTTP, no side effects (ART-X / QG-15)
- API key MUST NEVER appear in any log, span, or test output (ART-V / QG-08)
- Constitution gates: QG-01, QG-04, QG-06, QG-08, QG-11, QG-12, QG-13, QG-15, QG-16
- `adp-generate --check` must remain exit 0 — no changes to ADP-SPEC-001 model
- Note: Recommend implementing US2 (gate()) BEFORE US1 (critics) so that orchestrator.run() can call a real gate() from the start
