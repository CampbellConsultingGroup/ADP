# Tasks: AI Recommendation Engine

**Input**: Design documents from `/specs/007-recommendation-engine/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: Tests are MANDATORY for all ADP features (ART-IV). Test tasks MUST appear before their implementation counterparts in every user-story phase. Tests MUST be committed and verified to fail before any implementation begins.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no file conflicts)
- **[Story]**: Which user story this task belongs to (US1–US4)
- Include exact file paths in every description

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Install LangGraph, create directory skeleton

- [x] T001 Add recommendation dependencies to `pyproject.toml` using minimum-version constraints: `langgraph>=0.2`, `langchain-core>=0.2`; run `pip install -e ".[dev]"` and verify; exact versions pinned in T046
- [x] T002 [P] Create directory structure: `src/adp/recommendation/`, `tests/recommendation/`; create `src/adp/recommendation/__init__.py` (placeholder), `tests/recommendation/__init__.py` (empty)
- [x] T003 Verify: `python3 -c "import langgraph, langchain_core; print('ok')"` resolves after install

**Checkpoint**: `pytest tests/ --ignore=tests/integration -q --no-cov` still passes all existing tests

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data models, prompt templates, telemetry stub, and orchestrator skeleton — MUST be complete before any user story

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T004 Create all recommendation data models in `src/adp/recommendation/models.py`: `TradeOffStance(StrEnum)` (`meets`, `partially_meets`, `does_not_meet`); `TradeOffEntry` dataclass (criterion, stance, rationale); `ProposedElement` dataclass (name, kind: ElementKind from ADP-SPEC-001, description, satisfies: list[str]); `SolutionOption` dataclass (all fields from data-model.md including option_id, operation_id, rank, title, rationale, advisory, grounded_on, satisfies, trade_offs, proposed_elements, ranking_score, coverage_score, principle_score, tradeoff_score, status, accepted_by, accepted_at); `RecommendationStep` dataclass (telemetry fields from data-model.md); `RecommendationState` TypedDict (all pipeline state fields from data-model.md)
- [x] T005 [P] Create LLM prompt templates in `src/adp/recommendation/prompts.py`: `GENERATION_SYSTEM_PROMPT` and `generation_user_prompt(requirements_list, knowledge_summary, option_count)` function; `TRADEOFF_SYSTEM_PROMPT` and `tradeoff_user_prompt(option_title, option_rationale, element_names, criteria_list)` function — both per contracts/llm-prompt-contract.md
- [x] T006 [P] Create `RecommendationTelemetry` class in `src/adp/recommendation/telemetry.py`: `emit_step_span(step: RecommendationStep) -> None` using `opentelemetry.trace`; span name pattern `adp.recommendation.{step.step_name}`; attributes from data-model.md RecommendationStep fields; API key MUST NOT appear in any attribute; silently no-ops when no OTel exporter configured
- [x] T007 Create `RecommendationOrchestrator` skeleton in `src/adp/recommendation/orchestrator.py`: `__init__(self, llm_client, knowledge_retrieval, design_store, option_count=3, ranking_weights=(0.4,0.3,0.3), telemetry=None)`; stub `async run(operation_id, design_id, requirement_ids, operation_store, correlation_id=None) -> None` raising `NotImplementedError`; stub `async materialize_option(option_id, operation_id, accepting_actor, operation_store, design_id) -> list` raising `NotImplementedError`

**Checkpoint**: `python3 -c "from adp.recommendation import RecommendationOrchestrator; print('ok')"` succeeds

---

## Phase 3: User Story 1 — Generate Grounded Solution Options (Priority: P1) 🎯 MVP

**Goal**: Submit confirmed requirement ids; the five-step LangGraph pipeline runs asynchronously; result contains 1–3 ranked `SolutionOption` records each with citations, satisfies links, and no auto-commitment to the model.

**Independent Test**: Inject a `RecommendationState` with 2 requirements and mock knowledge retrieval returning 3 items; run the full pipeline; assert 3 options returned, each has `grounded_on` non-empty, options are ordered by rank, `status=pending` on all.

### Tests for User Story 1 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T008 [P] [US1] Write failing `test_retrieve_step_calls_knowledge_retrieval()` in `tests/recommendation/test_steps.py`: inject a mock `KnowledgeRetrieval` returning 2 `RetrievalResultEntry` objects; call the `retrieve` step function with a `RecommendationState` containing 2 requirement ids; assert the mock was called with each requirement as a query; assert `state["retrieved_knowledge"]` contains the returned entries
- [x] T009 [P] [US1] Write failing `test_generate_step_produces_structured_options()` in `tests/recommendation/test_steps.py`: mock `LLMClient.extract` returning a JSON response with 3 options per contracts/llm-prompt-contract.md; call the `generate` step with pre-populated retrieval results; assert `state["candidate_options"]` has 3 `SolutionOption` objects each with non-empty `grounded_on` and `satisfies`; also assert each option has at least one `ProposedElement` in `proposed_elements` with a valid `kind` value from `ElementKind` (`person`, `system`, `container`, or `component`); also test the option count cap: mock LLM returning 5 options when `option_count=3`; assert only 3 options appear in `state["candidate_options"]` — the generate step MUST truncate to `option_count`
- [x] T010 [P] [US1] Write failing `test_rank_step_assigns_sequential_ranks()` in `tests/recommendation/test_steps.py`: inject 3 candidate options with known coverage/principle/tradeoff scores; call the `rank` step; assert options are sorted by descending `ranking_score` with ranks 1, 2, 3 assigned in order
- [x] T011 [P] [US1] Write failing `test_validate_citations_marks_unresolvable_as_advisory()` in `tests/recommendation/test_steps.py`: inject options where opt-A has all citations resolvable and opt-B has one citation that `resolve_citation` returns `None` for; call validate_citations step; assert opt-A has `advisory=False` and opt-B has `advisory=True`
- [x] T012 [P] [US1] Write failing `test_full_pipeline_produces_ranked_options()` in `tests/recommendation/test_orchestrator.py`: run `orchestrator.run()` with mocked LLM and mocked knowledge retrieval; assert `operation_store[op_id]["status"] == "completed"` and `operation_store[op_id]["options"]` contains 3 ranked options none of which have `status=accepted`

### Implementation for User Story 1

- [x] T013 [US1] Implement `retrieve` step function in `src/adp/recommendation/steps.py`: call `knowledge_retrieval.hybrid_search(RetrievalQuery(query_text=req.description, kinds=[pattern, standard, principle], limit=5))` for each requirement; merge and deduplicate by `citation.item_id`; store in `state["retrieved_knowledge"]`; emit telemetry span via `RecommendationTelemetry.emit_step_span()`
- [x] T014 [US1] Implement `generate` step function in `src/adp/recommendation/steps.py`: build knowledge summary from `retrieved_knowledge` entries (id@version, kind, title, excerpt); call LLM with generation prompt from `prompts.py`; parse JSON response into `list[SolutionOption]` with uuid4 `option_id`s; when parsing `proposed_elements[*].kind`, if the LLM returns an unrecognized value (e.g., `"microservice"`), default to `ElementKind.COMPONENT` and log a warning — do NOT raise on invalid kind; set `advisory=False` (citation validation happens later); emit telemetry span with token counts and cost; add `test_generate_defaults_invalid_kind_to_component()` in `tests/recommendation/test_steps.py` asserting this fallback
- [x] T015 [US1] Implement `rank` step function in `src/adp/recommendation/steps.py`: compute `coverage_score = len(option.satisfies) / len(state["requirement_ids"])`; compute `principle_score = mean(e.relevance_score for e in retrieved_knowledge if e.item.kind == "principle" and e.citation.item_id in {ref.item_id for ref in option.grounded_on})`; compute `tradeoff_score = sum(1 for t in option.trade_offs if t.stance == "meets") / max(1, len(option.trade_offs))`; `ranking_score = w_req * coverage + w_principle * principle + w_tradeoff * tradeoff`; sort descending; assign `rank = i+1`; emit no-LLM telemetry span
- [x] T016 [US1] Implement `validate_citations` step function in `src/adp/recommendation/steps.py`: for each option, call `knowledge_retrieval.resolve_citation(ref)` for each `CitationRef` in `grounded_on`; if any returns `None`, set `option.advisory = True`; store validated options in `state["validated_options"]`; emit telemetry span with `advisory_count`
- [x] T017 [US1] Build LangGraph `StateGraph` in `src/adp/recommendation/orchestrator.py`: add nodes `retrieve`, `generate`, `analyze_tradeoffs`, `rank`, `validate_citations` pointing to step functions; add sequential edges; Note: the `analyze_tradeoffs` node is NOT wired yet in this task — it is added by T023 in the US2 phase; build the graph with only the 4 nodes (retrieve, generate, rank, validate_citations) here; compile graph; implement `run()`: first call `await design_store.get(design_id)` and extract the `Requirement` objects matching `requirement_ids` (raise `DesignNotFoundError` if design not found); populate `state["requirements"]` with these objects BEFORE invoking the LangGraph graph (the retrieve step uses `req.description` for search queries); update op status to `running`, create `RecommendationState`, invoke graph, store `validated_options` in operation_store, update status `completed` or `failed`; emit pipeline-level log (not source text, not requirement descriptions)
- [x] T017b [US1] After the validate_citations step completes in `orchestrator.run()` in `src/adp/recommendation/orchestrator.py`, set `operation_store[operation_id].setdefault("span", {})["citations_present"] = any(not opt.advisory for opt in validated_options)`; this bridges ADP-SPEC-007's `advisory` flag to ADP-SPEC-003's ART-VII gate (`citations_present`); add `test_citations_present_true_when_any_non_advisory()` and `test_citations_present_false_when_all_advisory()` in `tests/recommendation/test_orchestrator.py`
- [x] T018 [US1] Update `src/adp/recommendation/__init__.py` to export `RecommendationOrchestrator`, `SolutionOption`, `TradeOffEntry`, `ProposedElement`; verify T008–T012 all pass

**Checkpoint**: `pytest tests/recommendation/test_steps.py tests/recommendation/test_orchestrator.py -q --no-cov` green; SC-001 (all options have citations), SC-003 (async, handle in 2s), SC-004 (spans emitted) verifiable

---

## Phase 4: User Story 2 — Trade-Off Analysis for Each Option (Priority: P1)

**Goal**: Every `SolutionOption` carries a `TradeOffEntry` for every applicable NFR and principle; each entry has an explicit `stance` and rationale; `does_not_meet` entries are surfaced, not suppressed.

**Independent Test**: Inject one candidate option and a list of 3 NFR/principle criteria; call the `analyze_tradeoffs` step; assert the option has 3 `TradeOffEntry` records, one per criterion; assert at least one `does_not_meet` entry when the LLM is mocked to return that stance.

### Tests for User Story 2 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T019 [P] [US2] Write failing `test_tradeoff_step_produces_entry_per_criterion()` in `tests/recommendation/test_steps.py`: mock LLM returning trade-offs with stances for 3 criteria; call `analyze_tradeoffs` step; assert the option has exactly 3 `TradeOffEntry` records with correct criterion names and stances
- [x] T020 [P] [US2] Write failing `test_tradeoff_step_surfaces_does_not_meet()` in `tests/recommendation/test_steps.py`: mock LLM returning one `does_not_meet` stance; assert the entry appears in `option.trade_offs` rather than being filtered out
- [x] T021 [P] [US2] Write failing `test_tradeoff_parse_failure_leaves_empty_list_not_error()` in `tests/recommendation/test_steps.py`: mock LLM returning malformed JSON for trade-offs; assert the option gets `trade_offs=[]` and the pipeline continues (does NOT fail); assert a warning is logged

### Implementation for User Story 2

- [x] T022 [US2] Implement `analyze_tradeoffs` step function in `src/adp/recommendation/steps.py`: for each `SolutionOption` in `state["candidate_options"]`, call LLM with trade-off prompt; "applicable NFRs" = requirements in `state["requirements"]` whose description contains quality-attribute keywords (performance, security, scalability, reliability, availability); also collect principle item names from `state["retrieved_knowledge"]` where `item.kind == "principle"`; pass both as the `criteria_list` in the trade-off prompt; parse `{"trade_offs": [...]}` response into `list[TradeOffEntry]`; on parse failure, set `option.trade_offs = []` and log warning (do NOT fail); emit telemetry span per option batch
- [x] T023 [US2] Wire `analyze_tradeoffs` into the LangGraph pipeline in `src/adp/recommendation/orchestrator.py`: insert between `generate` and `rank` nodes; verify T019–T021 pass

**Checkpoint**: `pytest tests/recommendation/ -q --no-cov` green; SC-002 (trade-off coverage) verifiable

---

## Phase 5: User Story 3 — Accept an Option and Materialize Elements (Priority: P2)

**Goal**: `materialize_option()` converts `ProposedElement` records to canonical `Element` records with `provenance=option_id` and `satisfies` links; writes `AuditEntry`; saves to design store; advisory options require explicit acknowledgment.

**Independent Test**: Call `orchestrator.materialize_option()` with a non-advisory option; assert mock `design_store.save()` was called with a design containing new `Element` records with `provenance == option_id` and `satisfies` matching the option's `satisfies` list; assert `AuditEntry` was written with accepting actor's identity.

### Tests for User Story 3 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T024 [P] [US3] Write failing `test_materialize_creates_elements_with_provenance()` in `tests/recommendation/test_materialization.py`: call `orchestrator.materialize_option()` with a non-advisory option containing one `ProposedElement`; assert mock `design_store.save()` called with a design containing an `Element` with `provenance == option_id`
- [x] T025 [P] [US3] Write failing `test_materialized_elements_carry_satisfies_links()` in `tests/recommendation/test_materialization.py`: option has `satisfies=["REQ-001"]` and `ProposedElement.satisfies=["REQ-001"]`; assert the materialized `Element.satisfies` contains `"REQ-001"` (QG-16 / FR-005)
- [x] T026 [P] [US3] Write failing `test_materialization_writes_audit_entry()` in `tests/recommendation/test_materialization.py`: assert mock design's `audit_log` contains an `AuditEntry` with `actor == accepting_actor` and `origin == "human"` and `action == "accept-recommendation"` (QG-13 / FR-004)
- [x] T027 [P] [US3] Write failing `test_advisory_option_accepted_with_acknowledgment()` in `tests/recommendation/test_materialization.py`: create advisory option (`advisory=True`); call `materialize_option()` without `advisory_acknowledged=True`; assert `ValueError` raised and no store write; call with `advisory_acknowledged=True`; assert materialization succeeds and materialized elements carry a note that acceptance was advisory

### Implementation for User Story 3

- [x] T028 [US3] Implement `orchestrator.materialize_option()` in `src/adp/recommendation/orchestrator.py`: retrieve option from operation_store; validate `status == "pending"`; validate `option.advisory == False OR advisory_acknowledged == True` — if `advisory == True` and `advisory_acknowledged` is not passed as `True`, raise `ValueError` with a message instructing the caller to pass `advisory_acknowledged=True` for advisory options; load design from store; convert each `ProposedElement` → `Element` with new `ElementId` (`ELM-{len(design.elements)+1:03d}`), `provenance=option_id`, `satisfies=proposed_element.satisfies`; validate each element against ADP-SPEC-001 model; write `AuditEntry` via ADP-SPEC-004 `write_audit_record()` with `action="accept-recommendation"`; call `design_store.save(design, actor=accepting_actor)`; mark option `status=accepted`, `accepted_by`, `accepted_at`; return list of created Elements
- [x] T029 [US3] Verify T024–T027 all pass; run `adp-generate --check` to confirm ADP-SPEC-001 schema is still drift-free

**Checkpoint**: `pytest tests/recommendation/test_materialization.py -q --no-cov` green; SC-005 (provenance + satisfies links) verifiable; QG-13, QG-14, QG-16 gates satisfied

---

## Phase 6: User Story 4 — Inspect Each Orchestration Step (Priority: P2)

**Goal**: Every recommendation job emits exactly 5 telemetry spans (one per step) plus a pipeline-level span; all spans share the `correlation_id`; each step span carries the required attributes.

**Independent Test**: Run the full orchestrator with all steps mocked; assert `mock_telemetry.emit_step_span` was called exactly 5 times; assert each call's `RecommendationStep` has non-None `step_name`, `latency_ms`; assert all share the same `correlation_id`.

### Tests for User Story 4 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T030 [P] [US4] Write failing `test_five_spans_emitted_per_job()` in `tests/recommendation/test_orchestrator.py`: run full orchestrator with mocked steps and mocked telemetry; assert `mock_telemetry.emit_step_span` was called exactly 5 times (retrieve, generate, analyze_tradeoffs, rank, validate_citations)
- [x] T031 [P] [US4] Write failing `test_each_span_has_required_fields()` in `tests/recommendation/test_orchestrator.py`: assert every emitted `RecommendationStep` has non-empty `step_name`, `operation_id`, `latency_ms > 0`; for LLM steps assert `input_tokens > 0`
- [x] T032 [P] [US4] Write failing `test_all_spans_share_correlation_id()` in `tests/recommendation/test_orchestrator.py`: run pipeline with `correlation_id="trace-123"`; assert all 5 emitted spans have `correlation_id == "trace-123"` (QG-11 / FR-006)
- [x] T033 [P] [US4] Write failing `test_failure_span_emitted_on_step_error()` in `tests/recommendation/test_orchestrator.py`: mock `generate` step to raise `ConnectionError`; run pipeline; assert at least one span is emitted with `error` field set; assert pipeline status is `failed`

### Implementation for User Story 4

- [x] T034 [US4] Implement `RecommendationTelemetry.emit_step_span()` in `src/adp/recommendation/telemetry.py`: using `opentelemetry.trace`, create child span under parent pipeline span named `adp.recommendation.{step.step_name}`; set all attributes from `RecommendationStep` fields; set span status to ERROR if `step.error` is set; handle missing OTel exporter gracefully (no-op); API key MUST NOT appear in any attribute
- [x] T035 [US4] Verify T030–T033 all pass; confirm all 5 steps wire telemetry correctly

**Checkpoint**: `pytest tests/recommendation/ -q --no-cov` green; SC-004 (5 spans per job, all required fields) verifiable; QG-11 gate satisfied

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Coverage, quality gates, ADP-SPEC-003 integration, security

- [x] T036 [P] Run `pytest tests/recommendation/ --cov=adp.recommendation --cov-report=term-missing` and verify ≥ 85% line coverage; add targeted tests for uncovered branches (e.g., empty retrieval results, 0-requirement input, all options advisory) (QG-04)
- [x] T037 [P] Run `ruff check src/adp/recommendation/ tests/recommendation/` and `mypy src/adp/recommendation/ --python-version 3.12 --ignore-missing-imports`; fix all issues (QG-06)
- [x] T038 [P] Run `bandit -r src/adp/recommendation/ -ll`; verify `ADP_LLM_API_KEY` never appears in logs or span attributes by grepping all `_logger.*` calls and span attribute sets (QG-06, QG-08)
- [x] T039 [P] Extend ADP-SPEC-003's operations router in `src/adp/api/routers/operations.py` to handle `kind=recommendation`: create a `get_recommendation_orchestrator() -> RecommendationOrchestrator` FastAPI dependency function in `src/adp/api/dependencies.py` that reads `ADP_LLM_*` and `ADP_REC_*` from settings and constructs the orchestrator; inject this dependency into the operations and confirmations router handlers — do NOT instantiate the orchestrator inline in route functions; dispatch `orchestrator.run()` as a background task when `kind=recommendation`; update the confirmation router `src/adp/api/routers/confirmations.py` to call `orchestrator.materialize_option()` when `operation.kind == "recommendation"` and `confirmation.option_id` is set
- [x] T040 [P] Write `test_operations_router_dispatches_recommendation()` in `tests/api/test_operations.py`: POST `kind=recommendation` to `/api/v1/operations`; assert 202 returned with operation handle; assert recommendation orchestrator background task was created (mock the orchestrator)
- [x] T041 [P] Run `pytest tests/ --ignore=tests/integration -q --no-cov` confirming all existing tests (ADP-SPEC-001 through ADP-SPEC-006) remain unaffected; run `adp-generate --check` to confirm ADP-SPEC-001 schema drift-free
- [x] T042 [P] Write `test_api_key_never_in_recommendation_logs()` in `tests/recommendation/test_orchestrator.py`: run full orchestrator with a recognizable fake API key; capture log output; assert the fake key does not appear anywhere (QG-08 regression guard, mirrors ADP-SPEC-006's T037)
- [x] T043 [P] Write `test_recommendation_completes_within_60s()` in `tests/recommendation/test_orchestrator.py` (`@pytest.mark.slow`): run full orchestrator with instant mock LLM; time the run; assert elapsed < 1.0 seconds (SC-003 structural verification with mock LLM)
- [x] T044 [P] Write `test_handle_available_within_2s()` in `tests/recommendation/test_orchestrator.py`: dispatch `orchestrator.run()` via `asyncio.create_task()` without awaiting; immediately assert operation handle exists in operation_store with `status == "pending"` (NFR-001 structural verification)
- [x] T045 Pin new dependency versions in `pyproject.toml`: run `pip show langgraph langchain-core` to capture versions; replace minimum-version constraints from T001 with exact pinned specifiers (QG-18)
- [x] T046 [P] Verify complete feature end-to-end by running `adp-generate --check` and the full test suite one final time

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories; models + prompts + telemetry stub must exist
- **US1 (Phase 3)**: Depends on Foundational — 🎯 MVP; 4-step pipeline (excluding trade-off) delivers grounded ranked options
- **US2 (Phase 4)**: Depends on Foundational (step stubs exist); US2's `analyze_tradeoffs` step wires into US1's graph — depends on T017 (StateGraph built)
- **US3 (Phase 5)**: Depends on US1's orchestrator (T017) for `run()` to exist so options are available to accept; independent of US2/US4
- **US4 (Phase 6)**: Depends on all five steps being wired (US1 + US2) to verify 5-span emission; independent of US3
- **Polish (Phase 7)**: Depends on all desired user stories complete

### User Story Dependencies

- **US1 (P1)**: Can start after Phase 2 — no dependencies on US2-US4
- **US2 (P1)**: Depends on US1's `StateGraph` (T017) to wire the new step; tests are independent
- **US3 (P2)**: Depends on US1 `orchestrator.run()` so options exist; independent of US2/US4
- **US4 (P2)**: Depends on all steps being implemented (US1 + US2); tests verify 5-span count

### Parallel Opportunities

- T002, T003 (Setup): parallel — different concerns
- T004, T005, T006, T007 (Foundational stubs): parallel — different files
- T008, T009, T010, T011, T012 (US1 tests): parallel — different test files/functions
- T019, T020, T021 (US2 tests): parallel — independent test functions
- T024, T025, T026, T027 (US3 tests): parallel — independent test functions
- T030, T031, T032, T033 (US4 tests): parallel — independent test functions
- T036, T037, T038, T039, T040, T041, T042, T043, T044 (Polish): parallel — independent tools

---

## Implementation Strategy

### MVP First (US1 + US2 Only)

1. Phase 1 + 2 → Models, prompts, stubs available
2. Write US1 tests T008–T012 — verify they fail
3. Phase 3 US1: retrieve → generate → rank → validate_citations (4-step pipeline without trade-offs)
4. Write US2 tests T019–T021 — verify they fail
5. Phase 4 US2: add analyze_tradeoffs step
6. **STOP and VALIDATE**: `pytest tests/recommendation/ -q` green; all 5 steps wired; options have citations + trade-offs

### Incremental Delivery

1. Phase 1 + 2 → Foundation ready
2. Phase 3 (US1) → Grounded ranked options working (MVP — all governance gates except trade-off)
3. Phase 4 (US2) → Trade-off transparency added
4. Phase 5 (US3) → Element materialization active; acceptance flow complete
5. Phase 6 (US4) → Telemetry inspectability; all QG-11 requirements met
6. Phase 7 → All quality gates green

---

## Notes

- [P] tasks = different files or independent test functions; no file conflict
- Tests MUST fail before implementation; commit failing tests first (ART-IV)
- `ADP_LLM_API_KEY` MUST NEVER appear in any log, span attribute, or test output
- Requirement descriptions and LLM prompt content MUST NOT be logged (organizational IP)
- Constitution gates for this feature: QG-01, QG-04, QG-06, QG-08, QG-11, QG-12, QG-13, QG-14, QG-16
- `adp-generate --check` must remain exit 0 — this spec introduces no changes to ADP-SPEC-001 model
- Note: US1 intentionally builds a 4-step pipeline first (without trade-off analysis); US2 adds the 5th step; this allows US1 tests to run without US2 complete
