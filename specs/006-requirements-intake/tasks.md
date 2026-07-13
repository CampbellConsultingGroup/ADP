# Tasks: Requirements Intake & Normalization

**Input**: Design documents from `/specs/006-requirements-intake/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: Tests are MANDATORY for all ADP features (ART-IV). Test tasks MUST appear before their implementation counterparts in every user-story phase. Tests MUST be committed and verified to fail before any implementation begins.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no file conflicts)
- **[Story]**: Which user story this task belongs to (US1–US4)
- Include exact file paths in every description

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Install new dependencies, create directory skeleton

- [x] T001 Add intake dependencies to `pyproject.toml` using minimum-version constraints: `httpx>=0.27` (already present from ADP-SPEC-003), `opentelemetry-sdk>=1.25`, `tiktoken>=0.7`; run `pip install -e ".[dev]"` and verify; exact versions pinned in T040
- [x] T002 [P] Create directory structure: `src/adp/intake/`, `tests/intake/`; create `src/adp/intake/__init__.py` (placeholder), `tests/intake/__init__.py` (empty)
- [x] T003 Verify: `python3 -c "import opentelemetry, tiktoken; print('ok')"` resolves after install

**Checkpoint**: `pytest tests/ --ignore=tests/integration -q --no-cov` still passes all existing tests

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data models, LLM client skeleton, and orchestrator stub — MUST be complete before any user story

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T004 Create all intake data models in `src/adp/intake/models.py`: `SubmissionMode(StrEnum)` (`bulk_text`, `structured_form`); `RequirementKind(StrEnum)` (`functional`, `non_functional`, `constraint`, `driver`); `VerificationStatus(StrEnum)` (`verified`, `unverified`); `ProposalStatus(StrEnum)` (`pending`, `confirmed`, `edited_confirmed`, `rejected`, `expired`); `IntakeSubmission` dataclass (fields: `submission_id`, `mode`, `text`, `submitted_by`, `submitted_at`, `operation_id`); `ExtractedProposal` dataclass (all fields from data-model.md); `ExtractionSpan` dataclass (all telemetry fields from data-model.md)
- [x] T005 Create `LLMClient` class in `src/adp/intake/llm.py`: `__init__(self, base_url: str, api_key: str, model: str)` — api_key stored but NEVER logged; `async extract(source_text: str, correlation_id: str | None = None) -> dict[str, Any]` — sends POST to `{base_url}/v1/chat/completions` with the system + user prompt from contracts/llm-prompt-contract.md; returns the raw parsed JSON response; raises `httpx.HTTPError` on network failure; `temperature=0.1`, `response_format={"type":"json_object"}`, `max_tokens=4096`
- [x] T006 [P] Create `ExtractionOrchestrator` stub in `src/adp/intake/orchestrator.py`: `__init__(self, llm_client: LLMClient, ...)` with all constructor parameters from contracts/orchestrator-contract.md; `async run(submission: IntakeSubmission, operation_store: dict[str, Any]) -> None` raises `NotImplementedError`; `async confirm_proposal(...)` raises `NotImplementedError`; `async reject_proposal(...)` raises `NotImplementedError`
- [x] T007 [P] Create `src/adp/intake/parser.py` stub: `LLMResponseParser` class with `parse(raw_response: dict[str, Any], submission_id: str, operation_id: str) -> list[ExtractedProposal]` raising `NotImplementedError`
- [x] T008 [P] Create `src/adp/intake/verifier.py` stub: `SourceExcerptVerifier` with `verify(excerpt: str, source_text: str) -> VerificationStatus` raising `NotImplementedError`; `src/adp/intake/linker.py` stub: `KnowledgeLinker` with `async link(referenced_names: list[str]) -> list[str]` raising `NotImplementedError`; `src/adp/intake/telemetry.py` stub: `IntakeTelemetry` with `emit(span: ExtractionSpan) -> None` raising `NotImplementedError`

**Checkpoint**: `python3 -c "from adp.intake import ExtractionOrchestrator; print('ok')"` succeeds

---

## Phase 3: User Story 1 — Submit Requirements and Receive Extracted Proposals (Priority: P1) 🎯 MVP

**Goal**: Submitting raw text via the operations router creates an async extraction job that returns AI-extracted typed proposals, each with statement, kind, source excerpt, confidence, and verification status.

**Independent Test**: Submit known text containing 3 requirements; mock LLM returns a known JSON response; assert 3 proposals returned with correct fields; assert none is committed to the model; assert source excerpt is verbatim-verified.

### Tests for User Story 1 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T009 [P] [US1] Write failing `test_llm_client_sends_correct_request()` in `tests/intake/test_llm.py`: create `LLMClient` with `httpx.MockTransport` returning a known JSON; assert the outgoing request has the correct URL, temperature=0.1, the system prompt from the contract, and the source text in the user message; assert the API key appears in the Authorization header but is NOT in any log output
- [x] T010 [P] [US1] Write failing `test_parser_extracts_three_proposals()` in `tests/intake/test_parser.py`: provide a known LLM JSON response with 3 requirements; assert `LLMResponseParser.parse()` returns 3 `ExtractedProposal` objects with correct `draft_statement`, `kind`, `source_excerpt`, `confidence`, and `proposed_links` fields; assert `proposal_id` is a non-empty UUID string
- [x] T011 [P] [US1] Write failing `test_verifier_marks_exact_match_as_verified()` and `test_verifier_marks_missing_excerpt_as_unverified()` in `tests/intake/test_verifier.py`: assert `SourceExcerptVerifier.verify("the text", "contains the text here")` returns `VerificationStatus.VERIFIED`; assert `SourceExcerptVerifier.verify("not present", "other content")` returns `VerificationStatus.UNVERIFIED`
- [x] T012 [P] [US1] Write failing `test_orchestrator_run_produces_proposals()` in `tests/intake/test_orchestrator.py`: mock `LLMClient.extract` to return 2 proposals; call `orchestrator.run(submission, operation_store)`; assert `operation_store[operation_id]` has status `completed` and 2 proposals attached; assert proposals have `verification_status` set; assert all proposals have `status == ProposalStatus.PENDING` — this verifies proposals start in the correct initial state (not that confirmation hasn't happened, which is always true in Phase 3)

### Implementation for User Story 1

- [x] T013 [US1] Implement `LLMResponseParser.parse()` in `src/adp/intake/parser.py`: parse `raw_response["choices"][0]["message"]["content"]` as JSON; for each item in `response["requirements"]`, construct an `ExtractedProposal` with a `uuid.uuid4()` proposal_id, `operation_id`, `submission_id`, `draft_statement`, `kind` (validated against `RequirementKind`), `source_excerpt`, `confidence` (clamped 0–1), `proposed_links`; skip items missing required fields (log warning); return list of valid proposals
- [x] T014 [US1] Implement `SourceExcerptVerifier.verify()` in `src/adp/intake/verifier.py`: return `VerificationStatus.VERIFIED` if `excerpt.lower()` is a substring of `source_text.lower()`; otherwise return `VerificationStatus.UNVERIFIED`
- [x] T015 [US1] Implement `ExtractionOrchestrator.run()` in `src/adp/intake/orchestrator.py`: (1) update operation status to `running`; (2) call `self._llm.extract(submission.text, correlation_id)`; (3) call `LLMResponseParser.parse()`; (4) for each proposal call `SourceExcerptVerifier.verify()` and set `verification_status`; (5) attach proposals to `operation_store[operation_id]["proposals"]`; (6) update status to `completed`; on any exception: set status `failed`, set `error_description`; do NOT store or log `submission.text` after step 2
- [x] T015b [US1] After proposals are created in `orchestrator.run()` in `src/adp/intake/orchestrator.py`, set `operation_store[operation_id]["span"]["citations_present"] = any(p.verification_status == VerificationStatus.VERIFIED for p in proposals)`; this bridges ADP-SPEC-006's `verification_status` to ADP-SPEC-003's ART-VII gate (`citations_present`); add `test_citations_present_true_when_any_verified()` and `test_citations_present_false_when_all_unverified()` in `tests/intake/test_orchestrator.py`
- [x] T016 [US1] Update `src/adp/intake/__init__.py` to export `ExtractionOrchestrator`, `IntakeSubmission`, `ExtractedProposal`, `SubmissionMode`; verify T009-T012 all pass

- [x] T016b [US1] Extend ADP-SPEC-003's `ConfirmationPayload` in `src/adp/api/models/confirmation.py`: add `proposal_id: str | None = None` field; update the confirmation router in `src/adp/api/routers/confirmations.py` to pass `confirmation_payload.proposal_id` to `orchestrator.confirm_proposal()` when the operation kind is `intake`; add `test_intake_confirmation_routes_proposal_id()` in `tests/api/test_confirmations.py` asserting the proposal_id is forwarded to the orchestrator (FR-003 / QG-14)
- [x] T016c [US1] Implement `SubmissionMode.STRUCTURED_FORM` path in `src/adp/intake/orchestrator.py`: when `submission.mode == SubmissionMode.STRUCTURED_FORM`, skip LLM extraction entirely and create one `ExtractedProposal` directly from `submission.text` with `confidence=1.0`, `verification_status=VerificationStatus.VERIFIED`, `source_excerpt=submission.text[:200]`, and `kind=RequirementKind.FUNCTIONAL` (default); attach it to the operation and set status `completed`; add `test_structured_form_skips_llm()` in `tests/intake/test_orchestrator.py` asserting `LLMClient.extract` is never called for `structured_form` submissions (FR-001)

**Checkpoint**: `pytest tests/intake/test_llm.py tests/intake/test_parser.py tests/intake/test_verifier.py tests/intake/test_orchestrator.py -q --no-cov` green; SC-003 (results available for review) demonstrable

---

## Phase 4: User Story 2 — Confirm, Edit, or Reject Each Proposed Requirement (Priority: P1)

**Goal**: `confirm_proposal()` writes a typed `Requirement` to the design store and an `AuditEntry`; `reject_proposal()` marks the proposal rejected without entering the model; neither auto-commits without an explicit call.

**Independent Test**: Create 3 mock proposals; confirm one, edit-then-confirm a second, reject a third; assert only 2 Requirement records were written to mock store; assert both confirmations carry actor identity; assert rejected proposal is absent from store.

### Tests for User Story 2 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T017 [P] [US2] Write failing `test_confirm_proposal_writes_requirement()` in `tests/intake/test_orchestrator.py`: call `orchestrator.confirm_proposal(proposal_id, operation_id, actor="sub:abc", edited_statement=None, operation_store, mock_store)`; assert `mock_store.save` was called with a description containing a `Requirement` with `id` matching `REQ-\d{3}` pattern, `description` equal to `draft_statement`, and `provenance` referencing the proposal_id
- [x] T018 [P] [US2] Write failing `test_edit_confirm_uses_edited_statement()` in `tests/intake/test_orchestrator.py`: call `confirm_proposal` with `edited_statement="revised statement"`; assert the `Requirement.description` in the saved design equals `"revised statement"`, not the original `draft_statement`; assert proposal `status == edited_confirmed`
- [x] T019 [P] [US2] Write failing `test_confirm_writes_audit_entry()` in `tests/intake/test_orchestrator.py`: call `confirm_proposal` with `actor="sub:architect-123"`; assert `mock_store.save` was called with a description whose `audit_log` contains an `AuditEntry` with `actor == "sub:architect-123"` and `origin == "human"`
- [x] T020 [P] [US2] Write failing `test_reject_proposal_does_not_write_requirement()` in `tests/intake/test_orchestrator.py`: call `orchestrator.reject_proposal(proposal_id, operation_id, actor="sub:abc", operation_store)`; assert no `Requirement` object was appended to the design's `requirements` list — note: `store.save()` IS expected to be called to write the rejection audit entry (T022); the correct assertion is that the rejected proposal's statement does NOT appear as a `Requirement.description` in the saved design; also assert `operation_store[operation_id]["proposals"][proposal_id]["status"] == "rejected"`

### Implementation for User Story 2

- [x] T021 [US2] Implement `ExtractionOrchestrator.confirm_proposal()` in `src/adp/intake/orchestrator.py`: retrieve proposal from operation_store; validate `status == pending`; use `confirmed_statement or draft_statement` as the requirement description; generate the `RequirementId` by reading `len(design.requirements)` at the time of the `store.save()` call and formatting as `f"REQ-{len(design.requirements) + 1:03d}"`; note that ADP-SPEC-002's optimistic concurrency control prevents duplicate ids — if two architects simultaneously confirm proposals from the same design, the second `store.save()` will raise `ConcurrencyConflictError`; the caller should re-read the design and retry with the updated count; build `Requirement` with `id`, `title` (first 120 chars of statement), `description`, `priority="must"`, `provenance=proposal_id`; build `AuditRecord` with `actor`, `action="confirm-requirement"`, `affected_entity=requirement_id`, `origin="human"`, `confirmation_id=proposal_id`; call `write_audit_record(record, design, store)` (ADP-SPEC-004); call `store.save(design, actor=actor)`; update proposal `status=confirmed`, `confirmed_by`, `confirmed_at`, `requirement_id`; return the created `Requirement`
- [x] T022 [US2] Implement `ExtractionOrchestrator.reject_proposal()` in `src/adp/intake/orchestrator.py`: retrieve proposal; validate `status == pending`; set `status = rejected`; log rejection with actor; do NOT call store.save; build a minimal audit record for the rejection (action="reject-requirement-proposal") and write it to track the decision
- [x] T022b [P] [US2] Write `test_confirm_rejects_empty_statement()` in `tests/intake/test_orchestrator.py`: create a proposal with `draft_statement=""`; call `confirm_proposal()` with `edited_statement=None`; assert a `ValueError` or `pydantic.ValidationError` is raised before `store.save()` commits a `Requirement` to the design (NFR-002 — schema validation before write); the proposal `status` must remain `pending` after the failed confirmation
- [x] T023 [US2] Verify T017–T020 all pass; confirm `adp-generate --check` exits 0 (ADP-SPEC-001 schema unchanged)

**Checkpoint**: `pytest tests/intake/test_orchestrator.py -q --no-cov` green; SC-001 (zero auto-committed requirements) and SC-002 (stable id + confirming actor) verifiable

---

## Phase 5: User Story 3 — Link Requirements to Referenced Capabilities and Principles (Priority: P2)

**Goal**: When extracted text names a known principle or capability, `KnowledgeLinker` resolves it against the ADP-SPEC-005 knowledge base and adds the id to `proposed_links`; these are confirmed or discarded with the proposal.

**Independent Test**: Mock `KnowledgeRetrieval.keyword_search` to return a known item for "Zero Trust"; assert `KnowledgeLinker.link(["Zero Trust"])` returns `["PAT-007"]`; assert `KnowledgeLinker.link(["Unknown Name"])` returns `[]` when search returns no match above threshold.

### Tests for User Story 3 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T024 [P] [US3] Write failing `test_linker_resolves_known_principle()` in `tests/intake/test_linker.py`: mock `KnowledgeRetrieval.keyword_search` returning one result with `relevance_score=0.85` and `citation.item_id="PR-007"`; call `await linker.link(["Zero Trust Architecture"])`; assert result is `["PR-007"]`
- [x] T025 [P] [US3] Write failing `test_linker_returns_empty_below_threshold()` in `tests/intake/test_linker.py`: mock search returning result with `relevance_score=0.5` (below default 0.7 threshold); assert `await linker.link(["Low Match"])` returns `[]`
- [x] T026 [P] [US3] Write failing `test_linker_skips_when_no_knowledge_base()` in `tests/intake/test_linker.py`: create `KnowledgeLinker(knowledge_retrieval=None)`; assert `await linker.link(["any name"])` returns `[]` without raising

### Implementation for User Story 3

- [x] T027 [US3] Implement `KnowledgeLinker.link()` in `src/adp/intake/linker.py`: if `knowledge_retrieval is None`, return `[]`; for each name in the list, call `await self._retrieval.keyword_search(RetrievalQuery(query_text=name, limit=1))`; if result has at least one item with `relevance_score >= self._threshold`, add `result.items[0].citation.item_id` to the output list; return deduplicated list of matched ids
- [x] T028 [US3] Wire `KnowledgeLinker` into `ExtractionOrchestrator.run()` in `src/adp/intake/orchestrator.py`: after verifying each proposal, call `await self._linker.link(proposal.proposed_links)` and overwrite `proposal.proposed_links` with the resolved ids; verify T024–T026 pass

**Checkpoint**: `pytest tests/intake/test_linker.py -q --no-cov` green; SC-005 (≥ 90% link accuracy on known principles) verifiable

---

## Phase 6: User Story 4 — Observe Extraction Telemetry (Priority: P2)

**Goal**: Every extraction job emits exactly one OTel span with all required fields: source char count, proposal count and ids, input/output tokens, estimated cost, latency, model, endpoint, correlation id.

**Independent Test**: Run the orchestrator with a mock LLM returning a known response; assert `IntakeTelemetry.emit` was called exactly once; assert the `ExtractionSpan` passed to it contains all required fields with correct values; assert on-failure emit still fires when the pipeline raises.

### Tests for User Story 4 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T029 [P] [US4] Write failing `test_span_emitted_on_success()` in `tests/intake/test_telemetry.py`: run the full orchestrator with mocked LLM and mocked telemetry; assert `mock_telemetry.emit` was called exactly once; assert the `ExtractionSpan` has non-None `input_tokens`, `output_tokens`, `cost_usd`, `latency_ms`, `proposal_count >= 1`; assert `error is None`
- [x] T030 [P] [US4] Write failing `test_span_emitted_on_failure()` in `tests/intake/test_telemetry.py`: mock `LLMClient.extract` to raise `httpx.ConnectError("unreachable")`; run orchestrator; assert `mock_telemetry.emit` was called once; assert span `error` is not None; assert `proposal_count == 0`
- [x] T031 [P] [US4] Write failing `test_span_never_contains_api_key()` in `tests/intake/test_telemetry.py` and `tests/intake/test_llm.py`: capture all log output during an extraction run; assert the string from `ADP_LLM_API_KEY` env var does NOT appear anywhere in logs or span attributes (QG-08)

### Implementation for User Story 4

- [x] T032 [US4] Implement `IntakeTelemetry.emit()` in `src/adp/intake/telemetry.py`: using `opentelemetry.trace`, create a span named `adp.intake.extraction`; set attributes from `ExtractionSpan` fields; if `span.error` is not None, set span status to ERROR; end the span; the exporter is whatever is configured in the OTel SDK environment (ADP-SPEC-012 owns the exporter); if no exporter is configured (dev/test), the span is a no-op
- [x] T033 [US4] Wire `IntakeTelemetry` into `ExtractionOrchestrator.run()` in `src/adp/intake/orchestrator.py`: start timing before LLM call; count tokens using `tiktoken.get_encoding("cl100k_base")`; after pipeline completes (success or failure), build `ExtractionSpan` and call `self._telemetry.emit(span)`; ensure `emit` is always called even when the pipeline raises (use `try/finally`); verify T029–T031 pass

**Checkpoint**: `pytest tests/intake/test_telemetry.py -q --no-cov` green; SC-004 (one span per job, all required fields) verifiable; QG-11 gate satisfied

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Coverage, quality gates, security verification

- [x] T034 [P] Run `pytest tests/intake/ --cov=adp.intake --cov-report=term-missing` and verify line coverage ≥ 85%; add targeted tests for uncovered branches (e.g., empty LLM response, malformed JSON from LLM) (QG-04)
- [x] T035 [P] Run `ruff check src/adp/intake/ tests/intake/` and `mypy src/adp/intake/`; fix all issues (QG-06)
- [x] T036 [P] Run `bandit -r src/adp/intake/ -ll`; confirm `ADP_LLM_API_KEY` never appears in logs by grepping all `_logger.*` calls in `src/adp/intake/` — assert zero matches for the word "api_key" or "api key" as a logged value (QG-08, spec ART-V)
- [x] T037 [P] Add a conftest or test helper `tests/intake/test_api_key_safety.py` that runs the orchestrator with a recognizable fake API key value; captures log output; asserts the fake key string does NOT appear in any log record — this is a permanent regression guard for QG-08
- [x] T038 [P] Run `pytest tests/ --ignore=tests/integration -q --no-cov` confirming all existing tests (ADP-SPEC-001 through ADP-SPEC-005) remain unaffected
- [x] T038b [P] Write `test_operation_handle_available_immediately()` in `tests/intake/test_orchestrator.py`: dispatch `orchestrator.run(submission, operation_store)` via `asyncio.create_task()` WITHOUT awaiting; immediately assert `operation_store[operation_id]` exists with `status == "pending"`; assert this lookup completes in < 2 seconds (NFR-001 handle timing); also write `test_extraction_completes_within_deadline()`: await full `orchestrator.run()` with a mock LLM returning instantly; assert elapsed < 1 second (SC-003 structural verification — real latency is bounded by the 60s acceptance criterion in production)
- [x] T039 Run `adp-generate --check` to confirm ADP-SPEC-001 schema is drift-free (QG-02)
- [x] T040 Pin new dependency versions in `pyproject.toml`: run `pip show opentelemetry-sdk tiktoken` to capture installed versions; replace minimum-version constraints from T001 with exact pinned specifiers (QG-18)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories; all stub modules + models must exist
- **US1 (Phase 3)**: Depends on Foundational — 🎯 MVP; LLM extraction pipeline produces proposals
- **US2 (Phase 4)**: Depends on US1 (`orchestrator.run()` must exist); extends `orchestrator.py` with confirmation logic
- **US3 (Phase 5)**: Depends on Foundational (linker stub exists); independent of US1/US2 implementation; wired into orchestrator in T028
- **US4 (Phase 6)**: Depends on US1 (`orchestrator.run()` must exist to wire telemetry into); independent of US2/US3
- **Polish (Phase 7)**: Depends on all desired user stories complete

### User Story Dependencies

- **US1 (P1)**: Can start after Phase 2 — no dependencies on other stories
- **US2 (P1)**: Depends on US1 `orchestrator.run()` (T015) so proposals exist to confirm
- **US3 (P2)**: Can start after Phase 2 in parallel with US1 — linker is independent
- **US4 (P2)**: Depends on US1 `orchestrator.run()` (T015) to wire telemetry; independent of US2/US3

### Parallel Opportunities

- T002, T003 (Setup): parallel — different concerns
- T004, T005, T006, T007, T008 (Foundational stubs): parallel — all different files
- T009, T010, T011, T012 (US1 tests): parallel — different test files
- T024, T025, T026 (US3 tests): parallel — independent test functions
- T029, T030, T031 (US4 tests): parallel — independent test functions
- T017, T018, T019, T020 (US2 tests): parallel — independent test functions
- T034, T035, T036, T037, T038 (Polish): parallel — independent tools

---

## Parallel Example: User Story 3 + User Story 4

```bash
# US3 and US4 can be developed in parallel after US1:
Developer A: T024 → T025 → T026 → T027 → T028 (linker)
Developer B: T029 → T030 → T031 → T032 → T033 (telemetry)
```

---

## Implementation Strategy

### MVP First (US1 + US2 Only)

1. Phase 1: Setup (T001–T003)
2. Phase 2: Foundational stubs (T004–T008)
3. Write US1 tests T009–T012 — verify they fail
4. Phase 3: US1 extraction pipeline (T013–T016)
5. Write US2 tests T017–T020 — verify they fail
6. Phase 4: US2 confirmation/rejection (T021–T023)
7. **STOP and VALIDATE**: `pytest tests/intake/ -q` green; SC-001 + SC-002 verified

### Incremental Delivery

1. Phase 1 + 2 → Stubs and models available for import
2. Phase 3 (US1) → LLM extraction pipeline working (MVP)
3. Phase 4 (US2) → Human confirmation gate active; requirements enter model
4. Phase 5 (US3) → Knowledge base links proposed alongside extractions
5. Phase 6 (US4) → Telemetry spans emitted; QG-11 gate satisfied
6. Phase 7 → All quality gates green

---

## Notes

- [P] tasks = different files or independent test functions; no file conflict
- Tests MUST fail before implementation; commit the failing test first (ART-IV)
- `ADP_LLM_API_KEY` MUST NEVER appear in any log, span, test output, or source file — enforce via T037 regression guard
- Source text (`submission.text`) MUST be discarded after LLM extraction — never stored, never logged
- Constitution gates for this feature: QG-01, QG-03, QG-04, QG-06, QG-08, QG-11, QG-13, QG-14, QG-16
- `adp-generate --check` must remain exit 0 — this spec introduces no changes to ADP-SPEC-001's canonical model
