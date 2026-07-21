# Tasks: AI Chat Assistant for Business Architecture Q&A

**Feature**: ADP-SPEC-041 | **Branch**: `041-ai-chat-assistant`
**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md) · **Research**: [research.md](./research.md) · **Data model**: [data-model.md](./data-model.md)

## Format: `[ID] [P?] [Story] Description`

- **[P]** = parallelizable (distinct file, no dependency on an incomplete task).
- **[US#]** = user-story phase task. Setup / Foundational / Polish carry no story label.
- Tests are **MANDATORY** (ART-IV): each story's contract/unit tests precede its implementation, written to fail first.

## Path Conventions

New chat module `src/adp/chat/{models,store,tools,retrieval,orchestrator,router}.py`; `LLMClient` extension `src/adp/llm/client.py`; search-index extension `src/adp/search/index.py` + wiring in `src/adp/application/store.py`/`src/adp/business/store.py`; authz `src/adp/authz/{roles,permissions,enforcement}.py`; migration `src/adp/store/migrations/versions/022_chat_conversations.py`; tests `tests/{unit/chat,unit,contract,authz,integration}/`; web `web/src/chat/`, `web/src/api/chat.ts`, `web/src/business/CapabilityTree.tsx`.

> **File-contention note**: unlike Agent Review, this feature *does* have a migration (`022`, no chain conflicts — it's the only pending one). The real sequential constraints are `src/adp/chat/orchestrator.py` (grows US1 → US2 tool-use → US4 sliding-window, each building on the last) and `src/adp/chat/router.py` (grows US1 create/send → US3 list/get) — both touched across multiple story phases and therefore sequential, not `[P]`, even though they're each edited within only one phase at a time. `web/src/chat/ChatPanel.tsx` similarly grows Foundational (skeleton) → US1 (streamed rendering) → US3 (resume list). Toolkit-adjacent files (`adp/chat/models.py`, `store.py`, `tools.py`), test files, and story-specific files not listed above are distinct and parallelizable.

---

## Phase 1: Setup

- [x] T001 [P] Create the `adp.chat` package with `__init__.py` in src/adp/chat/__init__.py
- [x] T002 [P] Alembic migration `022` (`down_revision="021"`) adding `chat_conversations` and `chat_messages` per data-model.md's DDL sketch, in src/adp/store/migrations/versions/022_chat_conversations.py — verified up/down against the real dev Postgres before writing the automated test (T009).

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: No user story work can begin until this phase is complete — every story streams through the `LLMClient` extension, persists through the store CRUD, and is gated by the new permission built here.

- [x] T003 [P] Unit test: `LLMClient`'s new streaming method yields incremental text-delta chunks from a mocked SSE response and correctly serializes multi-turn message history + an (initially empty) `tools` parameter, in tests/unit/test_llm_client_streaming.py — also covers tool-use event accumulation (accumulated `input_json_delta` fragments parsed into a single `tool_use` event).
- [x] T004 Implement the new multi-turn, streaming, tool-use-capable chat method on `LLMClient`, built on the existing raw-`httpx` pattern (research D1), in src/adp/llm/client.py (depends on T003 failing first) — both Anthropic (SSE `event:`/`data:` framing) and OpenAI-compatible (`data: {...}`/`[DONE]` framing) branches implemented, mirroring the existing dual-provider `chat()`/`extract()` split.
- [x] T005 [P] Unit test: `ChatMessage`/`ChatConversationSummary`/`ChatConversationDetail`/`ChatCitation` round-trip and reject unknown fields (`extra="forbid"`), in tests/unit/chat/test_models.py
- [x] T006 [P] Add `ChatRole`, `ChatCitation`, `ChatMessage`, `ChatConversationSummary`, `ChatConversationDetail`, `SendMessageRequest` per data-model.md, in src/adp/chat/models.py — **`CreateConversationRequest`/`initial_message` dropped during implementation**: it didn't actually save a round trip (the create endpoint returns plain JSON, not a stream -- only send-message streams), so a client would need to call send-message again regardless. Conversation creation is now a bare POST with no body (mirrors the existing bodyless Agent Review trigger endpoints); a sensible title is derived from the first message when it's appended (US1, T020) instead.
- [x] T007 [P] Unit test: conversation/message CRUD — create, append, get, list — each scoped to the creating actor; a non-owner's `get`/`list` never returns another actor's rows, in tests/unit/chat/test_store.py
- [x] T008 Implement `adp.chat.store` (`create_conversation`, `append_message`, `get_conversation`, `list_conversations`, all actor-scoped per FR-009) in src/adp/chat/store.py (depends on T002, T006, T007 failing first)
- [x] T009 [P] Migration `022` up/down integration test (apply, verify both tables + FK/cascade, downgrade cleanly), in tests/integration/test_migration_022.py — uses its own dedicated testcontainer rather than the shared session-scoped `db_engine` fixture, since downgrading below head would corrupt state for every other integration test in the same session.
- [x] T010 Add `ActionType.USE_CHAT_ASSISTANT` in src/adp/authz/roles.py
- [x] T011 Bump `PERMISSIONS_VERSION` (to `1.6.0`) and grant `USE_CHAT_ASSISTANT` broadly, including Reviewer (every role that can view a page the chat toggle appears on — research D6) in src/adp/authz/permissions.py (depends on T010)
- [x] T012 [P] Update the expected-permissions matrix and version-constant assertion in tests/authz/test_permissions.py
- [x] T013 [P] Generic hooks (`useCreateConversation`, `useConversations`, `useConversation`, `useSendMessage`) in web/src/api/chat.ts — consumes the SSE stream via `fetch()` + a manual `ReadableStream` reader, **not** the browser's `EventSource`, since `EventSource` cannot send the `Authorization` header this API requires. `useSendMessage(basePath)` takes `conversationId` as an explicit argument to `sendMessage(id, content)` rather than closing over a prop/state value — a real stale-closure bug was caught here (see T016) where calling `sendMessage` immediately after `setConversationId(...)` used the pre-update `null` id, since a just-called `setState` doesn't take effect until the next render.
- [x] T014 [P] Generic `ChatButton` toggle component, mirroring `AgentReviewButton`'s shape, in web/src/chat/ChatButton.tsx
- [x] T015 [P] Generic `ChatPanel` component skeleton (message list, input box, incremental streamed-text rendering, past-conversations list) in web/src/chat/ChatPanel.tsx
- [x] T016 [P] Component test: `ChatPanel` renders streamed text incrementally as chunks arrive and disables the input while a turn is in flight, in web/tests/component/chat-panel.test.tsx — this test caught the stale-closure bug above (the send-message call never fired at all until fixed); custom fetch stub used instead of the shared `mockFetch` helper, since it always JSON-serializes and this endpoint streams raw `text/event-stream`.

**Checkpoint**: Foundational ready — every user story below builds on T004/T008/T011/T013–T015 without modifying their contracts.

---

## Phase 3: User Story 1 - Ask a grounded question, get a streamed answer (Priority: P1) 🎯 MVP

**Goal**: The full pipeline — toggle → conversation → streamed reply → grounded citation — proven with the narrowest possible retrieval scope (business/technical capabilities, the search index's existing coverage), before any cross-domain or tool-calling work lands.
**Independent test**: Open the chat on the Business Capabilities page, ask a question with a clear, checkable answer against seeded capability data; confirm the reply streams incrementally and cites real capability ids that resolve.

### Tests for User Story 1 (MANDATORY — ART-IV)

- [x] T017 [P] [US1] Contract test: create conversation (with or without `initial_message`) → send message → SSE response streams `text_delta` events followed by a `done` event carrying citations; an unresolvable citation is marked `verified: false`, never silently trusted; a mocked LLM-call failure mid-turn emits an `error` event and leaves the conversation resumable, in tests/contract/test_chat_api.py — 5 tests (no `initial_message` param — dropped per T006's note); all pass first run against SQLite-backed chat/biz/app stores with retrieval mocked (pgvector requires real Postgres) and the LLM client patched at `adp.chat.router._make_chat_llm_client`.
- [x] T018 [P] [US1] Unit test: the orchestrator grounds reply citations via the existing `adp.agents.grounding.verify_references`, marking unresolved ones `verified: false` rather than discarding or blocking (there is no accept-gate here to block), in tests/unit/chat/test_orchestrator.py — 4 tests (resolved/unresolved citation, title-from-first-message, LLM-failure error event), all pass.

### Implementation for User Story 1

- [x] T019 [US1] Orchestrator: assemble context via `adp.chat.retrieval` (querying only the search index's existing `business_capability`/`technical_capability` coverage for now), call `LLMClient`'s new streaming method with no tools, yield text deltas, ground citations, persist the completed assistant message, in src/adp/chat/orchestrator.py (depends on T004, T008) — ruff/mypy clean. Caught and self-fixed 3 design bugs before running any test: a broken actor-scoped re-fetch (fixed by taking `history` as an explicit param instead), a single-shared-session-for-cross-domain-lookups bug (fixed via separate `biz_session`/`app_session` params, mirroring agent_review.py), and a reference to a nonexistent `astore.technical_capability_exists()` (corrected to the real `astore.get_technical_capability()`).
- [x] T020 [US1] `POST /api/v1/chat/conversations` (create, no body) and `POST /api/v1/chat/conversations/{id}/messages` (SSE send, `StreamingResponse`) endpoints in src/adp/chat/router.py — also added GET list/detail (pulled forward from US3/T034 since store support already existed from Foundational; trivial to add alongside). Sessions for the streaming turn are opened fresh inside the generator itself (session-factory deps), not the request-scoped `Depends` session, since that would close before the StreamingResponse body is actually consumed. Also added `StubLLMClient.chat_stream` (src/adp/agents/llm_stub.py) so local dev without an LLM key gets a graceful explanatory reply instead of a connection-error `error` event.
- [x] T021 [US1] Register explicit route→action mappings — both POSTs → `USE_CHAT_ASSISTANT` — in src/adp/authz/enforcement.py — verified via the existing route-completeness test (`test_every_mutating_route_maps_to_an_action`), 28/28 authz tests pass.
- [x] T022 [US1] Observability span per chat turn (retrieval query, token usage, latency), in src/adp/chat/orchestrator.py — done as part of T019 (`ai_step_span("chat_turn", ...)` wraps the whole turn; input/output token counts set as span attributes).
- [x] T023 [P] [US1] Web wiring: chat toggle on the Business Capabilities page using `ChatButton`/`ChatPanel` (FR-013), in web/src/business/CapabilityTree.tsx — mirrors the existing "Review Portfolio" toggle pattern exactly. `tsc --noEmit` clean; all 94 web tests pass (including the pre-existing `CapabilityTree.test.tsx`).
- [x] T024 [US1] Regenerate JSON Schema (`adp-generate`) and confirm the drift gate passes — `adp-generate --check` exits 0 with no output; chat models aren't part of the generated canonical-model schema set, so no drift.

**Checkpoint**: MVP — single-domain streamed Q&A works end to end.

---

## Phase 4: User Story 2 - Cross-domain question spanning applications, portfolio, and governance (Priority: P2)

**Goal**: The distinguishing capability versus Agent Review — cross-domain retrieval-index extension and read-only tool-calling, including permission-aware filtering of sensitive application data.
**Independent test**: Ask a question requiring application data; confirm the reply correctly pulls it. Ask a question requiring cost/risk/governance data as a user without the matching permission; confirm that category is omitted or declined, never silently included.

### Tests for User Story 2 (MANDATORY — ART-IV)

- [x] T025 [P] [US2] Contract test: a question referencing linked applications correctly retrieves/cites application data; a sensitive-category question (risk, cost, governance) is answered when the caller holds the matching `READ_APPLICATION_*` permission and declined/omitted when they don't — one scenario per category (SC-004), in tests/contract/test_chat_api.py (extends T017's file) — 7 new tests. Two new fake LLM clients: `_ToolCallingLLMClient` (scripted reply after a tool call, for the application-citation scenario) and `_EchoToolResultLLMClient` (echoes the REAL `dispatch_tool` result back as its reply text, so the test asserts on what the actual permission-gated handler returned, not a stand-in). Role simulation uses `app.dependency_overrides[get_current_user]` — the same seam `tests/authz/test_enforcement.py` already uses — which required changing how `send_message` obtains `role` (see T031's note).
- [x] T026 [P] [US2] Unit test: a `TOOL_REGISTRY` sensitive-category handler returns `{"permitted": false}` for an unauthorized role rather than raising an error or silently returning an empty result, in tests/unit/chat/test_tools.py — 11 tests covering all three sensitive handlers × denied/permitted, `get_capability`/`get_application` found/not-found, `dispatch_tool`'s unknown-tool path, and `anthropic_tool_specs()` registry coverage.

### Implementation for User Story 2

- [x] T027 [P] [US2] Add `ENTITY_APPLICATION`, `ENTITY_VALUE_STREAM`, `ENTITY_BUSINESS_DOMAIN` discriminators in src/adp/search/index.py — also exported from `adp.search.__init__`.
- [x] T028 [US2] Wire `index_entity`/`unindex_entity` into application create/update/delete (mirroring the existing `technical_capability` wiring), in src/adp/application/store.py (depends on T027) — applications had no search-index wiring at all before this (only `technical_capability` did); confirmed via `pytest tests/unit tests/contract tests/authz` (782 passed) that the best-effort try/except swallows the expected "no such table: searchable_items" on SQLite test fixtures, same as the pre-existing capability/tech-cap wiring already did.
- [x] T029 [US2] Wire `index_entity`/`unindex_entity` into value-stream and business-domain create/update/delete, in src/adp/business/store.py (depends on T027)
- [x] T030 [US2] `TOOL_REGISTRY` — `get_capability`, `get_application`, `get_application_risk`/`get_application_cost`/`get_application_governance` (each gated via `is_permitted(role, ActionType.READ_APPLICATION_*)` — research D5), `portfolio_summary`, `governance_status`, in src/adp/chat/tools.py — the aggregate tools call the existing router functions (`adp.api.routers.portfolio.get_portfolio_summary`, `adp.api.routers.governance.get_governance_status`) directly rather than duplicating their raw-SQL queries; each handler takes `**_: Any` so one `dispatch_tool(name, args, role, sessions={...})` call site works regardless of which session(s) a given tool actually needs.
- [x] T031 [US2] Extend the orchestrator's turn loop to handle tool-use (the LLM requests a tool → dispatch to `TOOL_REGISTRY` → result fed back → generation continues → streaming resumes), in src/adp/chat/orchestrator.py (depends on T019, T030) — bounded by `_MAX_TOOL_ROUNDS = 5` as a safety net against a pathological loop. `run_turn` gained `kb_session` (a fourth session, for the two aggregate tools that read the canonical design store via `adp.api.deps`'s shared "kb" session factory) and `role: PersonaRole` parameters. Also extended `_CITATION_PATTERN`/the system prompt to cover `application`/`value_stream`/`business_domain` citations, not just the two US1 entity types, with matching grounding lookups. **Design correction caught before writing any test**: `role` must come from `router.py`'s `Depends(get_current_user)` (bound to a route parameter), not a manual `request.state.user` read like `_get_actor` uses — only the former is overridable via `app.dependency_overrides`, which is what let T025's permission-denial contract tests simulate a non-privileged role at all.
- [x] T032 [US2] Extend `adp.chat.retrieval` to query the newly-covered entity types, in src/adp/chat/retrieval.py (depends on T027) — `DEFAULT_ENTITY_TYPES` now lists all five `adp.search` entity-type constants instead of two hardcoded strings.

**Checkpoint**: US1 and US2 work independently; cross-domain answers correctly respect sensitive-category permissions.

---

## Phase 5: User Story 3 - Conversation history persists across sessions (Priority: P3)

**Goal**: History that was already being written since Foundational (T008) becomes listable and resumable, with proven per-actor access control.
**Independent test**: Have a conversation, reload the page (or start a new session as the same user); confirm the conversation and its full message history are still present and can be continued. Confirm a second user cannot see the first user's conversations.

### Tests for User Story 3 (MANDATORY — ART-IV)

- [x] T033 [P] [US3] Contract test: listing/opening one's own conversations succeeds; a second user's attempt to list or open the first user's conversation is refused — 404 either way (not-found vs. not-owned are never distinguished), never a 403 that would confirm the id exists (SC-003), in tests/contract/test_chat_api.py (extends T017's file) — 2 tests, using distinct `X-Actor` headers (`alice`/`bob`) since auth is disabled in tests; also confirms `bob` sending a message to `alice`'s conversation is a 404, not just list/get.

### Implementation for User Story 3

- [x] T034 [US3] `GET /api/v1/chat/conversations` (list, actor-scoped) and `GET /api/v1/chat/conversations/{id}` (detail, actor-scoped) endpoints in src/adp/chat/router.py — already built in T020 (pulled forward from this task during US1, since the store-layer actor-scoping it exposes already existed from Foundational/T008 — trivial to add both GETs alongside the two POSTs rather than come back to `router.py` a second time).
- [x] T035 [P] [US3] Web: list and resume past conversations in `ChatPanel`, in web/src/chat/ChatPanel.tsx — already built in T015 (Foundational) as part of the initial `ChatPanel` skeleton (`showHistory` toggle + `useConversations` list + click-to-resume), since a "past conversations" affordance was part of the component's original design, not an afterthought bolted on for US3.

**Checkpoint**: US1–US3 work independently; conversation history is durable, listable, and access-controlled.

---

## Phase 6: User Story 4 - Follow-up questions use conversation context (Priority: P4)

**Goal**: Multi-turn coherence within a conversation, bounded so cost/latency don't grow unboundedly with conversation length.
**Independent test**: Ask a question, then a follow-up that omits the subject and relies on the prior turn; confirm the reply correctly resolves the referent. Confirm a long conversation still replies coherently while its full history remains stored and visible.

### Tests for User Story 4 (MANDATORY — ART-IV)

- [x] T036 [P] [US4] Contract test: a follow-up question correctly resolves a referent from an earlier turn in the same conversation; a conversation exceeding the sliding-window size still produces a coherent reply, and `GET .../conversations/{id}` still returns the complete, untruncated history regardless of what was sent to the model, in tests/contract/test_chat_api.py (extends T017's file) — 2 tests, using a `_RecordingLLMClient` that captures the actual `messages` payload sent, so the follow-up test asserts the prior turn's real content was included (not just that the endpoint returned 200), and the long-conversation test seeds 25 real persisted messages then confirms both `len(seen_messages) < 26` (windowed) and `len(GET ... .messages) == 27` (untruncated).
- [x] T037 [P] [US4] Unit test: the sliding-window selector returns only the last N messages for LLM context regardless of full history length, in tests/unit/chat/test_orchestrator.py (extends T018's file) — 3 tests: `_windowed_history` pass-through under the window size, truncation over it, and an end-to-end `run_turn` test (25 real persisted messages, `_RecordingLLMClient` captures what was actually sent) proving the persisted-vs-sent distinction, not just the pure-function slice.

### Implementation for User Story 4

- [x] T038 [US4] Bounded sliding-window message-history selection per turn (research D8) in src/adp/chat/orchestrator.py (depends on T019) — `_CONTEXT_WINDOW_SIZE = 10` (research's suggested "last 10 messages" default), applied via `_windowed_history()` at the one call site in `run_turn`; `history` itself (fetched by the router, persisted by the store) is never truncated -- only the slice built for the LLM request is.

**Checkpoint**: All four user stories work independently — the full chat capability is live.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [x] T039 [P] Automated check that every `TOOL_REGISTRY` handler is read-only — call-graph inspection confirming no handler calls an `INSERT`/`UPDATE`/`DELETE`-issuing store function, not just a naming-convention check (SC-002, mirrors ADP-SPEC-039's `test_toolkit_boundary.py`), in tests/unit/chat/test_tools_boundary.py — 3 tests: naming-contract check, no handler directly contains a write idiom, and (the real call-graph check) resolves every function each handler calls — including ones imported inline inside the handler body, this codebase's established deferred-import pattern — and inspects THOSE functions' own source for `.insert()`/`.update()`/`.delete()`.
- [x] T040 Final `adp-generate` regen + drift gate — `adp-generate --check` exits 0.
- [x] T041 Full backend regression (`pytest tests/unit tests/contract tests/authz tests/integration`) and full web regression (`tsc --noEmit`, `vitest run`, `vite build`) — backend: 795 passed, 5 pre-existing failures unrelated to this feature (an `asyncio.get_event_loop()` `RuntimeError` in `adp.export.bundle`/`adp.renderer.orchestrator`, neither of which imports anything from `adp.chat` or `adp.search` — confirmed via `git stash`/`git stash pop` that these fail identically on the pre-041 commit). Web: `tsc --noEmit` clean, 94/94 vitest passed, `vite build` succeeds (only the pre-existing chunk-size/dynamic-import warnings `client.ts` already had, now also flagged for the new `chat.ts`).
- [x] T042 [P] Add an "AI Chat Assistant" section to docs/solution-architecture.md describing the module + its two-legged retrieval strategy, mirroring how Agent Review documented itself — inserted between the existing "Agent Review" and "Data Architecture" sections.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Ph1)** → **Foundational (Ph2)** → **User Stories (Ph3–6)** → **Polish (Ph7)**.
- Foundational (T003–T016) blocks **every** story — there is no story that only needs Setup.
- **Migration chain**: `022` is the only pending migration (`down_revision="021"`, the current head) — no ordering conflict to reconcile with concurrent work.

### Soft cross-story dependencies (functional, not blocking build)

- US2's tool-use loop (T031) and US4's sliding-window selection (T038) both extend the same orchestrator turn loop US1 builds (T019) — they extend it, they don't duplicate it.
- US3's list/detail endpoints (T034) expose history that Foundational (T008) and US1 (T019) are already writing — no new write path, purely a read-back/access-control surface.

### Parallel opportunities

- Within Foundational: T003/T005/T007/T009/T012–T016 are all `[P]` (distinct files); T004/T006/T008/T010/T011 have a strict test-then-implement or migration-then-CRUD ordering.
- Within a story: `[P]` test tasks and story-specific web tasks run parallel to the sequential `orchestrator.py`/`router.py` work.
- Across stories: `orchestrator.py` and `router.py` are shared and therefore serialized story-to-story; test files are distinct per concern and parallelizable within a phase.
- Example (US1): T017 + T018 (tests) ∥ start; T023 (web) ∥ T019–T022 (backend).

## Implementation Strategy

- **MVP = User Story 1** (Phase 3): the full streaming pipeline, proven with the narrowest retrieval scope. Ship and demo before proceeding.
- **Then by priority, increasing technical risk** (not write-risk — nothing here writes domain data): US2 (cross-domain retrieval + tool-calling, the hardest new-infrastructure lift) → US3 (a bounded CRUD/access-control surface over history already being written) → US4 (multi-turn context bounding). Each phase is independently demonstrable, so stopping after any of them leaves a coherent, safe feature.
- **SC-002's read-only tool-registry check** (T039) is the mechanical proof that the tool layer can never become a write path, mirroring ADP-SPEC-039's SC-005 import-boundary check — added in Polish once the registry (built in US2) is complete, not asserted only in review.

## Summary

- **Total tasks**: 42 across 7 phases.
- **Per story**: US1=8, US2=8, US3=3, US4=3; Setup=2, Foundational=14, Polish=4.
- **MVP scope**: US1 (T001–T024) — single-domain streamed Q&A with grounded citations, end to end.
- **Tests**: mandatory per story (ART-IV) — contract + unit before implementation; Foundational's own shared-infrastructure tests (T003, T005, T007, T009) also precede their implementation.
