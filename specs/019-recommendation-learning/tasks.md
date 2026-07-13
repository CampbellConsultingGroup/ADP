# Tasks: Recommendation Learning and Knowledge Capture

**Input**: Design documents from `/specs/019-recommendation-learning/`
**Prerequisites**: All complete ✅

---

## Phase 1: Setup

- [X] T001 Add `knowledge_source: str = "knowledge_base"` field to `SolutionOption` dataclass in `src/adp/recommendation/models.py`; also add it to `RecommendationState` TypedDict with default `"knowledge_base"`; add `knowledge_source: str` field to `SolutionOptionResponse` Pydantic model in `src/adp/api/routers/recommend.py`

---

## Phase 2: US1 — Recommendations Without Prior Knowledge

### Tests (MANDATORY — ART-IV)

- [X] T002 [P] [US1] Write failing `test_generate_options_without_kb()` in `tests/unit/test_recommend_no_kb.py`: call `generation_user_prompt()` with an empty knowledge summary; assert the returned prompt does NOT contain "cite at least one knowledge item" (that instruction must be removed when KB is empty); also test `generation_system_prompt_for_empty_kb()` exists and instructs LLM to generate from requirements alone
- [X] T003 [P] [US1] Write failing `test_validate_citations_no_kb_not_advisory()` in `tests/unit/test_recommend_no_kb.py`: create a `SolutionOption` with `knowledge_source="requirements_only"` and empty `grounded_on`; call `validate_citations_step` with a stub KnowledgeRetrieval; assert `option.advisory == False` after the step

### Implementation

- [X] T004 [US1] Update `src/adp/recommendation/prompts.py`: add `GENERATION_SYSTEM_PROMPT_NO_KB` constant that instructs the LLM to generate options from requirements alone without requiring citations; update `generation_user_prompt()` to accept `has_knowledge: bool` parameter — when `False`, use the no-KB prompt and do NOT include the citations instruction; the `knowledge_summary` is still passed as "No prior knowledge base entries available — generate options based on requirements alone"
- [X] T005 [US1] Update `src/adp/recommendation/steps.py` `generate_step()`: check if `retrieved_knowledge` is empty; if so, set `knowledge_source = "requirements_only"` on each generated option and pass `has_knowledge=False` to `generation_user_prompt()`; set `knowledge_source = "knowledge_base"` when KB had entries
- [X] T006 [US1] Update `validate_citations_step()` in `src/adp/recommendation/steps.py`: add guard `if option.knowledge_source == "requirements_only": continue` — skip advisory marking entirely for requirements-only options; only mark advisory when `knowledge_source == "knowledge_base"` and citations fail or are unresolvable
- [X] T007 [P] [US1] Update `_map_option_to_response()` in `src/adp/api/routers/recommend.py` to map `opt.knowledge_source` to `SolutionOptionResponse.knowledge_source`
- [X] T008 [P] [US1] Update `web/src/recommend/OptionCard.tsx`: replace the generic `⚠ ADVISORY` warning text with a `knowledge_source`-aware label — when `knowledge_source === "requirements_only"`: show a blue/neutral info box "Generated from requirements — no prior knowledge base entries available"; when `advisory === true` AND `knowledge_source === "knowledge_base"`: show the existing amber advisory warning (citation issue); remove the advisory check from the OptionCard when knowledge_source is "requirements_only"
- [X] T009 [P] [US1] Update TypeScript `SolutionOption` interface in `web/src/api/recommend.ts`: add `knowledge_source: string` field

**Checkpoint**: With empty KB, `POST /recommend` returns options with `knowledge_source: "requirements_only"` and `advisory: false`; UI shows blue info box not amber warning

---

## Phase 3: US2 — Accept with Reason + Knowledge Write

### Tests (MANDATORY — ART-IV)

- [X] T010 [P] [US2] Write failing `test_accept_with_reason_writes_kb_item()` in `tests/contract/test_recommend_api.py` (new test): mock KB write; seed a pending option; POST accept with `{"confirmation_id": "CONF", "advisory_acknowledged": false, "acceptance_reason": "Aligns with our standard"}`; assert KB write was called with `item_type: "accepted_recommendation"` and the reason in metadata
- [X] T011 [P] [US2] Write failing `test_accept_without_reason_still_succeeds()`: POST accept with no `acceptance_reason` field; assert 200 and KB write called with default reason

### Implementation

- [X] T012 [US2] Update `AcceptOptionRequest` in `src/adp/api/routers/recommend.py`: add `acceptance_reason: str | None = None` field
- [X] T013 [US2] Add `_write_knowledge_item_async(item_dict: dict, store)` helper in `src/adp/api/routers/recommend.py`: creates a `KnowledgeItem` with `[0.0] * 1536` placeholder embedding; calls `KnowledgeIndex.upsert_item()` with a DB session; wraps in try/except — on any exception, logs a warning and returns silently (fire-and-forget)
- [X] T014 [US2] Update `accept_option()` in `src/adp/api/routers/recommend.py`: after `materialize_option()` succeeds, call `asyncio.create_task(_write_knowledge_item_async({...}, store))` with `item_type: "accepted_recommendation"`, `title: option.title`, `full_text: f"{option.rationale}\n\nElements: {[e.name for e in option.proposed_elements]}\nReason: {reason}"`, `metadata: {"item_type": "accepted_recommendation", "option_id": option_id, "satisfies": option.satisfies, "reason": reason}`
- [X] T015 [P] [US2] Update `web/src/recommend/AcceptDialog.tsx`: add optional "Acceptance reason (optional)" textarea below the elements list; include `acceptance_reason` in the request body passed to `onConfirm`; update `AcceptOptionRequest` TypeScript type to include `acceptance_reason?: string`

---

## Phase 4: US3 — Reject with Reason + Knowledge Write

### Tests (MANDATORY — ART-IV)

- [X] T016 [P] [US3] Write failing `test_reject_option_returns_200()` in `tests/contract/test_recommend_api.py`: seed a pending option; POST to reject endpoint with `{"rejection_reason": "Too complex"}`; assert 200; assert option status is "rejected"
- [X] T017 [P] [US3] Write failing `test_reject_blank_reason_returns_422()`: POST with `{"rejection_reason": ""}`; assert 422
- [X] T018 [P] [US3] Write failing `test_reject_already_rejected_returns_409()`: seed a rejected option; POST reject; assert 409
- [X] T019 [P] [US3] Write failing `test_reject_writes_kb_item()`: mock KB write; POST reject with reason; assert KB write called with `item_type: "rejected_recommendation"`

### Implementation

- [X] T020 [US3] Add `RejectOptionRequest(rejection_reason: str)` Pydantic model with `@field_validator` requiring non-empty to `src/adp/api/routers/recommend.py`; add `POST /{design_id}/recommend/{operation_id}/options/{option_id}/reject` endpoint: validate reason non-empty; look up option (404 if missing); 409 if already actioned; set `option.status = "rejected"`; fire-and-forget KB write with `item_type: "rejected_recommendation"`; return `{"option_id": ..., "status": "rejected"}`
- [X] T021 [P] [US3] Add `useRejectOption(designId: string, operationId: string)` hook to `web/src/api/recommend.ts`: `useMutation` POST to `.../reject` with `{rejection_reason: string}`; on success: invalidate `["recommend-status", ...]` (so rejected option disappears from pending list)
- [X] T022 [US3] Create `web/src/recommend/RejectDialog.tsx`: modal with required "Rejection reason" textarea (min 10 chars); "Cancel" and "Confirm Reject" buttons — Confirm disabled until reason ≥ 10 chars; accessible `aria-label`
- [X] T023 [US3] Update `web/src/recommend/OptionCard.tsx`: add "Reject" button alongside "Accept" for pending options; wire to `RejectDialog`; on reject success: option shows "Rejected" status badge; add rejected options to a "Rejected Options" section below the options list (same visual pattern as "Rejected Requirements" in Intake)

---

## Phase 5: Polish

- [X] T024 [P] Run `pytest tests/ --ignore=tests/integration -q --no-cov` — all 359+ tests pass
- [X] T025 [P] Run `ruff check src/adp/recommendation/ src/adp/api/routers/recommend.py` — clean
- [X] T026 [P] Run `cd web && npm run tsc` — zero TypeScript errors
- [X] T027 [P] Verify live: start server; submit requirements; assert options appear without KB; accept one with reason; check KB via `adp-reindex` dry-run or direct DB query

---

## Notes

- T013 (`_write_knowledge_item_async`) requires `KnowledgeIndex` + `KnowledgeItem` from `adp.knowledge`; import lazily inside the function to avoid startup errors when knowledge module is misconfigured
- Zero-vector embedding `[0.0] * 1536` is intentional — allows text storage without `sentence-transformers`; `adp-reindex` will replace with real embeddings
- The reject endpoint does NOT use `confirmation_id` (unlike accept) — rejection is less consequential
- `asyncio.create_task()` requires a running event loop; in FastAPI async handlers this is always the case
