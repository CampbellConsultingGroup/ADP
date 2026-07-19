# Tasks: Agent Review Toolkit (with Business Capabilities Adapter)

**Feature**: ADP-SPEC-039 | **Branch**: `039-agent-review-toolkit`
**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md) · **Research**: [research.md](./research.md) · **Data model**: [data-model.md](./data-model.md)

## Format: `[ID] [P?] [Story] Description`

- **[P]** = parallelizable (distinct file, no dependency on an incomplete task).
- **[US#]** = user-story phase task. Setup / Foundational / Polish carry no story label.
- Tests are **MANDATORY** (ART-IV): each story's contract/unit tests precede its implementation, written to fail first.

## Path Conventions

Shared toolkit `src/adp/agents/{models,grounding,llm_stub,provenance}.py`; adapter `src/adp/business/{agent_review,models,router}.py`; authz `src/adp/authz/{roles,permissions,enforcement}.py`; tests `tests/{unit/agents,unit/business,contract,authz}/`; web `web/src/agent-review/`, `web/src/api/agentReview.ts`, `web/src/business/CapabilityNode.tsx`.

> **File-contention note**: unlike a migration-chained feature, there is **no schema change** here, so there's no migration-ordering constraint. The real constraint is `src/adp/business/agent_review.py`, `src/adp/business/models.py` (the `CapabilitySuggestion` tagged union grows one suggestion type per story), and `web/src/agent-review/SuggestionCard.tsx` (renders each new type) — all touched across US1–US4 and therefore **sequential**, not `[P]`, even across story phases. `src/adp/business/router.py`'s four endpoints are added **once**, in US1, and never modified again — later stories only change what `agent_review.py` generates and dispatches, not the endpoint surface. Toolkit files (`src/adp/agents/*`), test files, and story-specific web files are distinct and parallelizable.

---

## Phase 1: Setup (Shared Infrastructure)

- [ ] T001 [P] Create the `adp.agents` package with `__init__.py` in src/adp/agents/__init__.py
- [ ] T002 [P] Add shared toolkit models (`GroundingCitation`, `GroundingResult`, `AgentSuggestionStatus`, `AgentReviewOperationStatus`) in src/adp/agents/models.py

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: No user story work can begin until this phase is complete — every story's suggestions are generated, grounded, and accepted through these shared pieces.

- [ ] T003 [P] Unit test: `verify_references()` classifies resolved vs. unresolved citations given a lookup-function map, in tests/unit/agents/test_grounding.py
- [ ] T004 Implement `verify_references()` grounding validator (fails closed on an unrecognized entity type) in src/adp/agents/grounding.py (depends on T003 failing first)
- [ ] T005 [P] Unit test: shared stub LLM client's `chat()` returns an empty choice list with no API key, in tests/unit/agents/test_llm_stub.py
- [ ] T006 Implement `StubLLMClient` in src/adp/agents/llm_stub.py; update src/adp/api/routers/intake.py and src/adp/api/routers/recommend.py to import it instead of their ad hoc local stub classes (depends on T005)
- [ ] T007 [P] Implement `write_suggestion_audit()` (structured log line, `origin="ai"` — business capabilities have no `design_id` for a real `AuditEntry`, matching `adp.business`'s existing logging-only ART-IX convention; a `design_and_store` param supports a future design-centric adapter instead) and `write_suggestion_reasoning()` (`llm_reasoning_log` row via `option_id` — a genuine, queryable, append-only record regardless of adapter) in src/adp/agents/provenance.py
- [ ] T008 Add `ActionType.CONFIRM_AGENT_SUGGESTION` in src/adp/authz/roles.py
- [ ] T009 Bump `PERMISSIONS_VERSION` to `1.5.0` and grant `CONFIRM_AGENT_SUGGESTION` to solution/technical/enterprise architect roles in src/adp/authz/permissions.py (depends on T008)
- [ ] T010 [P] Update the expected-permissions matrix and version-constant assertion in tests/authz/test_permissions.py
- [ ] T011 [P] Generic hooks `useSubmitAgentReview` / `useAgentReviewStatus` (poll, mirroring `useIntakeStatus`'s `refetchInterval` idiom) / `useAcceptSuggestion` / `useRejectSuggestion`, parameterized by base path, in web/src/api/agentReview.ts
- [ ] T012 [P] Generic `AgentReviewButton` component in web/src/agent-review/AgentReviewButton.tsx
- [ ] T013 [P] Generic `SuggestionCard` component (accept/reject, advisory-acknowledgment checkbox when `advisory=true`) in web/src/agent-review/SuggestionCard.tsx
- [ ] T014 [P] Component test: `SuggestionCard` accept/reject calls, disabled-while-pending, advisory checkbox gating accept, in web/tests/component/suggestion-card.test.tsx

**Checkpoint**: Toolkit ready — every user story below builds on T004/T006/T007/T009/T011–T013 without modifying them.

---

## Phase 3: User Story 1 - Flag possible duplicates (Priority: P1) 🎯 MVP

**Goal**: Trigger a review of one capability that can only flag likely duplicates at the same hierarchy level — the full pipeline (context → LLM → grounding → human review) with zero write risk.
**Independent test**: Create two near-identical capabilities at the same level plus an unrelated one at that level; review one near-duplicate; confirm it cites the other (not the unrelated one); accept is a no-op acknowledgment.

### Tests for User Story 1 (MANDATORY — ART-IV)

- [ ] T015 [P] [US1] Contract test: trigger → poll → `flag_duplicate` suggestion citing a real same-level capability id + rationale; accept is a no-op (no DB write); reject marks rejected; trigger requires `SUBMIT_AI_OPERATION`, accept/reject require `CONFIRM_AGENT_SUGGESTION`; unknown capability → 404; **an `LLMClient.chat()` failure (mocked to raise) transitions the operation to `status=failed` with a non-null `error_description`, distinct from the no-API-key empty-result case (FR-021)**, in tests/contract/test_capability_agent_review_api.py
- [ ] T016 [P] [US1] Unit test: duplicate-candidate matching is restricted to the same `level` (no cross-level flags), in tests/unit/business/test_agent_review_duplicates.py

### Implementation for User Story 1

- [ ] T017 [US1] `CapabilitySuggestion` tagged union — all five types' fields per data-model.md, including the `previous_strategic_relevance`/`previous_maturity_level` generation-time snapshot fields that US2 will populate and compare (FR-015) — `CapabilityAgentReviewResponse` (with `error_description`, FR-021), `SuggestionDecisionRequest` models in src/adp/business/models.py
- [ ] T018 [US1] Context assembly for one capability — own fields, domain, direct parent/children, linked stages, linked applications' non-sensitive fields only (`time_classification`/`r_strategy`/`pace_layer`/`health_score`), linked technical capabilities, linked designs, and same-level siblings (for duplicate comparison) — in src/adp/business/agent_review.py
- [ ] T019 [US1] "Business architecture expert" prompt construction + `LLMClient.chat()` call (wrapped in try/except — any exception transitions the operation to `status=failed` with `error_description`, no retry, FR-021 — this is the only `chat()` call site; later stories' suggestion types are parsed from the same response) + `flag_duplicate` suggestion parsing, in src/adp/business/agent_review.py (depends on T018, T006)
- [ ] T020 [US1] Grounding pass over `flag_duplicate` citations via `adp.agents.grounding.verify_references`, marking unresolvable ones advisory, in src/adp/business/agent_review.py (depends on T004, T019)
- [ ] T021 [US1] `POST` trigger, `GET` poll, `POST` accept, `POST` reject endpoints under `/api/v1/business/capabilities/{cap_id}/agent-review`, tracked via the existing `OperationStore` (capability id passed as `design_id`), in src/adp/business/router.py
- [ ] T022 [US1] Register explicit route→action mappings — trigger → `SUBMIT_AI_OPERATION`, accept/reject → `CONFIRM_AGENT_SUGGESTION` (both override the `/api/v1/business/` prefix's `WRITE_BUSINESS_ARCH` default) — in src/adp/authz/enforcement.py
- [ ] T023 [US1] Observability span for the review operation (step name, capability id, operation id, token usage, cost, latency), in src/adp/business/agent_review.py
- [ ] T024 [P] [US1] Web wiring: per-node "Review with AI" affordance on `CapabilityNode` using `AgentReviewButton`/`SuggestionCard`, in web/src/business/CapabilityNode.tsx
- [ ] T025 [US1] Regenerate JSON Schema (`adp-generate`) and confirm the drift gate passes

**Checkpoint**: MVP — duplicate-flagging review works end to end with zero write risk.

---

## Phase 4: User Story 2 - Suggest strategic relevance and maturity classification (Priority: P2)

**Goal**: The first suggestion types that write to the database, on the two lowest-risk fields.
**Independent test**: Review an unclassified capability with rich linked context; confirm `reclassify_strategic_relevance`/`set_maturity_level` suggestions with rationale; accept one → field updates + `origin="ai"` audit entry; reject the other → unchanged.

### Tests for User Story 2 (MANDATORY — ART-IV)

- [ ] T026 [P] [US2] Contract test: `reclassify_strategic_relevance`/`set_maturity_level` suggestions generated with rationale and a `previous_*` snapshot matching the capability's value at generation time; accept writes the field via the existing `update_capability` + an audit entry with `origin="ai"`; reject writes nothing; a suggestion cannot be accepted twice; **accept 409s if the specific snapshotted field changed since generation, but still succeeds if a *different*, unrelated field changed in the meantime (field-scoped, not whole-record — FR-015)**, in tests/contract/test_capability_agent_review_api.py (extends T015's file)
- [ ] T027 [P] [US2] Unit test: accept dispatch calls `update_capability` with exactly the suggested field and value, nothing else; the snapshot comparison reads only the one field named by the suggestion type, in tests/unit/business/test_agent_review_accept.py

### Implementation for User Story 2

- [ ] T028 [US2] Add `reclassify_strategic_relevance` + `set_maturity_level` to suggestion generation, capturing the capability's current value into `previous_strategic_relevance`/`previous_maturity_level` at generation time (FR-015) and stating it in the rationale when already classified, in src/adp/business/agent_review.py
- [ ] T029 [US2] Accept-dispatch for these two types: re-fetch the capability and compare its *current* value for the one field the suggestion targets against the suggestion's `previous_*` snapshot, 409 without writing on a mismatch (FR-015, field-scoped — an unrelated field having changed does not block this); re-check `WRITE_BUSINESS_ARCH` for the target capability (FR-016); then call the existing `update_capability`, in src/adp/business/agent_review.py
- [ ] T030 [US2] Write the structured audit log line and `llm_reasoning_log` row on accept via the `adp.agents.provenance` helpers (depends on T007), in src/adp/business/agent_review.py
- [ ] T031 [P] [US2] Web: render these two suggestion types' current→suggested value distinctly, in web/src/agent-review/SuggestionCard.tsx

**Checkpoint**: US1 and US2 both work independently; the write-and-audit path is proven.

---

## Phase 5: User Story 3 - Suggest a domain assignment (Priority: P3)

**Goal**: The first suggestion type citing a *different* entity type than the capability being reviewed.
**Independent test**: Review an unassigned L1 capability whose context aligns with one domain; confirm `assign_domain` cites that domain's real id; accept updates the capability's domain via the existing assignment path; a below-L1 capability never gets this suggestion type.

### Tests for User Story 3 (MANDATORY — ART-IV)

- [ ] T032 [P] [US3] Contract test: `assign_domain` produced only for L1 capabilities, citing a real domain id; accept calls the existing domain-assignment path + audit entry; a level-2/3 capability review never produces `assign_domain`; **if the capability's domain was assigned by someone else between generation and accept (no longer `NULL`), accept 409s rather than overwriting it (FR-015's degenerate case, research D8)**, in tests/contract/test_capability_agent_review_api.py
- [ ] T033 [P] [US3] Unit test: `assign_domain`'s citation is grounded against `business_domains`, not `business_capabilities` — cross-entity-type grounding, in tests/unit/business/test_agent_review_grounding.py

### Implementation for User Story 3

- [ ] T034 [US3] Add `assign_domain` suggestion generation, gated to L1 capabilities only (FR-012), in src/adp/business/agent_review.py
- [ ] T035 [US3] Register a domain-id lookup function alongside the existing capability-id lookup passed to `verify_references`, in src/adp/business/agent_review.py
- [ ] T036 [US3] Accept-dispatch for `assign_domain`: re-verify the capability's `domain_id` is still `NULL` before writing (409 if not, FR-015's degenerate case), then call the existing `assign_capability_domain`, in src/adp/business/agent_review.py

**Checkpoint**: US1–US3 all work independently; cross-entity grounding is proven.

---

## Phase 6: User Story 4 - Propose a new capability to close a gap (Priority: P4)

**Goal**: The highest-value, highest-complexity suggestion type — creates a new record rather than updating one, grounded on supporting context rather than an existing capability id (since none exists yet for what it proposes).
**Independent test**: Review a capability whose context reveals an uncovered value-stream stage; confirm `propose_new_capability` cites that stage's real id; accept creates a real capability via the existing creation path with correct level/parent and provenance back to the suggestion.

### Tests for User Story 4 (MANDATORY — ART-IV)

- [ ] T037 [P] [US4] Contract test: `propose_new_capability` citing a real supporting entity (e.g. an uncovered value-stream stage); accept creates a capability via the existing `create_capability` (respecting its level/parent-consistency validation) with provenance to the suggestion; an unresolvable supporting citation → advisory, blocked from acceptance without `advisory_acknowledged=true`, in tests/contract/test_capability_agent_review_api.py
- [ ] T038 [P] [US4] Unit test: `propose_new_capability`'s grounding check verifies the cited *supporting-context* id (e.g. the stage), never a "proposed capability id" (which doesn't exist yet), in tests/unit/business/test_agent_review_propose.py

### Implementation for User Story 4

- [ ] T039 [US4] Add `propose_new_capability` suggestion generation, citing supporting context (an uncovered value-stream stage or an ADP-zg3.4 gap-analysis finding), in src/adp/business/agent_review.py
- [ ] T040 [US4] Accept-dispatch for `propose_new_capability`: call the existing `create_capability` with the suggested name/description/level/parent_id, recording provenance back to the operation/suggestion, in src/adp/business/agent_review.py
- [ ] T041 [P] [US4] Web: render `propose_new_capability`'s proposed name/description/level/parent distinctly, in web/src/agent-review/SuggestionCard.tsx

**Checkpoint**: All four user stories work independently — the full suggestion taxonomy is live.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T042 [P] Import-boundary test enforcing SC-005 — `src/adp/agents/` contains zero imports from `adp.business` (or any other single domain module) — in tests/unit/agents/test_toolkit_boundary.py
- [ ] T043 Final `adp-generate` regen + drift gate, covering all five suggestion types
- [ ] T044 Full backend regression (`pytest tests/unit tests/contract tests/authz`) and full web regression (`tsc --noEmit`, `vitest run`, `vite build`)
- [ ] T045 [P] Add an "Agent Review" section to docs/solution-architecture.md describing the toolkit + adapter, mirroring how prior features documented themselves

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Ph1)** → **Foundational (Ph2)** → **User Stories (Ph3–6)** → **Polish (Ph7)**.
- Foundational (T003–T014) blocks **every** story — there is no story that only needs Setup, unlike a feature with independent sensitive/non-sensitive tracks.
- **No migration chain** (this feature adds no schema — see research.md D1), so there is no cross-phase migration-ordering constraint to track.

### Soft cross-story dependencies (functional, not blocking build)

- US3's `assign_domain` and US4's `propose_new_capability` both read the same context-assembly function US1 builds (T018) — they extend it, they don't duplicate it.
- US4's supporting-context grounding is strongest when the existing capability-gap analysis (ADP-zg3.4) has already flagged something for the reviewed capability's neighborhood, but does not require it — an uncovered value-stream stage alone is sufficient supporting evidence.

### Parallel opportunities

- Within Foundational: T003/T005/T007/T010–T014 are all `[P]` (distinct files); T004/T006/T008/T009 have a strict test-then-implement or enum-then-grant ordering.
- Within a story: the `[P]` test tasks and the `[P]` web task run parallel to the sequential `agent_review.py`/`models.py` work.
- Across stories: `agent_review.py`, `business/models.py`, and `SuggestionCard.tsx` are shared and therefore serialized story-to-story; test files are distinct per story and parallelizable.
- Example (US1): T015 + T016 (tests) ∥ start; T024 (web) ∥ T017–T023 (backend).

## Implementation Strategy

- **MVP = User Story 1** (Phase 3): the full pipeline, proven with zero write risk. Ship and demo before proceeding.
- **Then by priority, strictly increasing write-risk**: US2 (single-field write) → US3 (relationship write, cross-entity grounding) → US4 (new-record write, context-only grounding). Each phase is a strictly harder case than the last, so stopping after any of them still leaves a coherent, safe feature.
- **Toolkit reusability is verified, not just asserted**: T042's import-boundary test is the mechanical check that a hypothetical second adapter could reuse `adp.agents` without modification (SC-005) — it should be added and passing well before Polish, ideally right after Foundational, so no story accidentally introduces a `adp.business` dependency into the toolkit along the way.

## Summary

- **Total tasks**: 45 across 7 phases.
- **Per story**: US1=11, US2=6, US3=5, US4=5; Setup=2, Foundational=12, Polish=4.
- **MVP scope**: US1 (T001–T025) — the read-only duplicate-flagging review, end to end.
- **Tests**: mandatory per story (ART-IV) — contract + unit before implementation; Foundational's own toolkit-level unit tests (T003, T005) also precede their implementation.
