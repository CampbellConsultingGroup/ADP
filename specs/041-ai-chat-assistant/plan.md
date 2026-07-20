# Implementation Plan: AI Chat Assistant for Business Architecture Q&A

**Branch**: `041-ai-chat-assistant` | **Date**: 2026-07-20 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/041-ai-chat-assistant/spec.md`

## Summary

A read-only, cross-domain conversational assistant — a new top-level `adp.chat` package, not an `adp.agents` adapter, since its entire value is reading *across* `adp.business`/`adp.application` in one turn, which `adp.agents`' zero-domain-import contract (ADP-SPEC-039 SC-005) structurally forbids. Grounding is two-legged: extend the existing hybrid search index (`adp.search`, ADP-b6o) to cover applications/value-streams/domains for fuzzy questions, plus a small fixed set of read-only tool functions over existing REST/store read paths for precise/aggregate questions semantic search can't answer. Every entity a reply cites is independently re-verified (reusing `adp.agents.grounding`); an unverifiable one is flagged inline rather than blocking anything, since there is no write to block. Sensitive application data (risk/cost/governance) is filtered per the *asking user's own* existing permissions inside the tool layer itself — not a prompt instruction, and not blanket-excluded the way Agent Review's v1 scope cut does it. Replies stream over SSE, the platform's first streaming endpoint; conversation history is persisted (a genuine new migration, unlike Agent Review's transient operations) and scoped per actor. First entry point is a toggle on the Business Capabilities page, built as a reusable module from day one.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.x + React 18 (frontend)
**Primary Dependencies**: FastAPI ≥ 0.111 (`StreamingResponse` for SSE), SQLAlchemy 2 async (Core), asyncpg, Pydantic v2, TanStack Query v5 — all existing stack; no new package for streaming (built on the existing raw-`httpx` `LLMClient`, research D1), no LangGraph (a bounded per-turn retrieval+tool-call loop, not a multi-node graph — same "single-prompt, not a pipeline" philosophy as ADP-SPEC-039 D2, adapted for tool-use)
**Storage**: PostgreSQL 16 — **two new tables** via migration `022` (`chat_conversations`, `chat_messages`; see data-model.md) — the first schema change either Agent Review spec needed to make. Also extends `adp.search`'s existing `searchable_items` table (no schema change there — new entity-type discriminator values, not new columns).
**Testing**: pytest (contract + unit; a genuine migration up/down test in `tests/integration/` — the first this session's chat work needs, unlike 039/040), Vitest (web component tests for the chat panel + SSE consumption, mocking `EventSource`/fetch-stream the way existing tests mock `fetch`)
**Target Platform**: Linux server (API) + browser (web canvas)
**Project Type**: Web application (existing `src/adp` backend + `web/` frontend)
**Performance Goals**: a reply begins streaming before the full answer is generated (SC-005) — no user-visible silent wait the way a poll-based operation has; per-turn context is a bounded recent-message window (research D8), not full unbounded history, so token cost/latency don't grow unboundedly with conversation length
**Constraints**: zero tool functions in the registry capable of a write (SC-002, verified by an automated check, not just naming convention); zero sensitive-category data ever reaches a user without the matching `READ_APPLICATION_*` permission (SC-004); zero cross-user conversation access (SC-003); every reply's entity citations independently verified, unverified ones always visibly marked (SC-001); a stream interruption leaves the conversation in a consistent, resumable state, never a duplicated or corrupted turn
**Scale/Scope**: one new package (`adp.chat`) + `LLMClient` extensions + `adp.search` entity-type extension; 4 user stories; 2 new tables; 1 new authz action; the platform's first streaming endpoint

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **ART-II (Model is source of truth)**: ✅ every answer derives from the live hybrid search index or a live tool call against current store state (FR-002, FR-003) — never a stale cache or a duplicated shadow copy of registry data.
- **ART-III / ART-XIII (Machine-readable / Typed contracts)**: ✅ all new Pydantic v2 models (`extra="forbid"`) — conversation/message shapes, request bodies, streamed-chunk events; new models emit to JSON Schema via `adp-generate`.
- **ART-IV (TDD)**: ✅ contract tests for conversation CRUD, actor-scoping, sensitive-category gating, and the SSE stream contract precede their handlers.
- **ART-V (Security by Design)**: ✅ threat model in spec; sensitive-category filtering enforced inside the tool implementation itself against the asking user's real permissions (FR-005, research D5), not a prompt instruction; tool registry is fixed and read-only by construction (FR-004, SC-002); conversations scoped per actor (FR-009, SC-003).
- **ART-VI (Observability)**: ✅ each chat turn emits a span (retrieval query, tool calls made, token usage, latency) — same attribute categories every other AI orchestration step already emits (FR-007).
- **ART-VII (Grounded AI Only)**: ✅ every cited entity is independently re-verified via the existing `adp.agents.grounding` validator (FR-006); unverified → visibly flagged inline (no accept-gate exists here to block, since nothing is ever written).
- **ART-IX (Provenance/Audit)**: ✅ persisted conversation history is itself the full provenance record of what was asked and answered — no separate `AuditEntry`/log line needed, since this feature performs no mutation of any domain data.
- **ART-XI (Traceability)**: ✅ every reply's citations trace a specific claim back to the retrieval hit or tool call that produced it.
- **ART-XV (Schema Evolution is Governed)**: ✅ migration `022` is reviewed, versioned, up/down-tested — the first genuine schema change either Agent Review spec needed.

**Result**: PASS — no violations; Complexity Tracking not required. Two areas of genuinely new infrastructure (SSE streaming, LLM tool-use) are documented as research decisions (D1, D2), not treated as constitutional exceptions — neither weakens an existing article, they're additive capability this feature happens to be the first to need.

## Project Structure

### Documentation (this feature)

```text
specs/041-ai-chat-assistant/
├── plan.md              # This file
├── research.md          # Phase 0 — decisions (LLMClient extension, SSE, adp.chat's location,
│                         #   retrieval strategy, sensitive-data filtering, new action, migration,
│                         #   sliding-window context)
├── data-model.md         # Phase 1 — migration DDL, Pydantic models, tool registry shape, endpoints
├── checklists/
│   └── requirements.md  # Spec quality checklist (clarifications resolved)
└── tasks.md             # Phase 2 output (/speckit.tasks — not created here)
```

### Source Code Changes

```text
src/adp/chat/                           # NEW top-level package (research D3 -- not under adp.agents)
├── __init__.py
├── models.py           # ChatMessage, ChatConversationSummary/Detail, Create/SendMessageRequest,
│                        #   ChatCitation (GroundingCitation + verified: bool)
├── store.py             # persistence CRUD: create_conversation, append_message, list_conversations
│                        #   (actor-scoped), get_conversation (actor-scoped, 404 either way -- FR-009)
├── tools.py              # TOOL_REGISTRY -- fixed, read-only functions wrapping existing store/
│                         #   aggregate reads; sensitive ones gated by is_permitted() (research D5)
├── retrieval.py           # thin wrapper over adp.search.SearchIndex.hybrid_search across the
│                          #   extended entity-type set
├── orchestrator.py         # per-turn loop: bounded recent-message window (research D8) ->
│                           #   retrieval + tool-use loop via LLMClient's new streaming method ->
│                           #   yield text deltas -> ground citations -> persist assistant message
└── router.py               # FastAPI endpoints, incl. the SSE response (data-model.md's table)

src/adp/llm/client.py                   # + new multi-turn, streaming, tool-use chat method
                                         #   (research D1) -- built on the same raw-httpx pattern
                                         #   the existing chat()/extract() methods already use

src/adp/search/index.py                 # + ENTITY_APPLICATION, ENTITY_VALUE_STREAM,
                                         #   ENTITY_BUSINESS_DOMAIN discriminators (research D4)

src/adp/application/store.py            # + index_entity/unindex_entity wiring for applications
                                         #   (mirrors the existing technical_capability wiring)
src/adp/business/store.py               # + index_entity/unindex_entity wiring for value streams
                                         #   and business domains

src/adp/authz/
├── roles.py            # + ActionType.USE_CHAT_ASSISTANT
└── permissions.py      # broad grant (research D6); PERMISSIONS_VERSION bump

src/adp/authz/enforcement.py            # + 2 explicit route entries: create conversation, send
                                         #   message -> USE_CHAT_ASSISTANT

src/adp/store/migrations/versions/
└── 022_chat_conversations.py           # NEW -- chat_conversations + chat_messages (data-model.md)

generated/                              # regenerated JSON Schema (adp-generate)

web/src/chat/                           # NEW reusable frontend package
├── ChatButton.tsx        # generic toggle, mirrors AgentReviewButton's parameterization
├── ChatPanel.tsx          # message list, input box, SSE stream consumption
└── (adapter wiring lives wherever a page adopts it, not here)

web/src/api/chat.ts                     # NEW typed hooks: useCreateConversation, useConversations,
                                         #   useConversation, useSendMessage (EventSource-based
                                         #   streaming consumer, parameterized like agentReview.ts)

web/src/business/CapabilityTree.tsx     # + chat toggle wired alongside the existing
                                         #   "Review Portfolio" button (FR-013)

tests/
├── unit/chat/             # tool-registry read-only check (SC-002), sliding-window logic,
│                           #   retrieval-extension coverage
├── contract/               # conversation CRUD, actor-scoping (SC-003), sensitive-category
│                           #   gating per category (SC-004), SSE stream contract
├── integration/             # migration 022 up/down -- the first migration test this feature
│                            #   needs, unlike 039/040's zero-schema-change scope
└── authz/                   # route-mapping + role-denial tests for USE_CHAT_ASSISTANT
```

**Structure Decision**: New top-level `src/adp/chat/` package (confirmed to need cross-domain imports by design, per research D3 — deliberately *not* subject to `adp.agents`' zero-domain-import contract, and not placed inside it). Reuses `adp.agents.grounding`/`adp.agents.models.GroundingCitation` and the LLM client factory pattern normally, same as any other consumer of those toolkit pieces. Frontend mirrors the split established by Agent Review: `web/src/chat/` is generic, wired into `web/src/business` for this first entry point.

## Phase 0 — Research & Decisions

Captured in [research.md](./research.md). Key decisions:

1. **Extend `LLMClient`, don't replace it.** Multi-turn message history, SSE streaming, and tool-use are all additive to the Anthropic Messages API request body the client already speaks over raw `httpx` — no switch to the official SDK, which would fragment the client's existing dual-provider (Anthropic / OpenAI-compatible) design for one method.
2. **SSE, not WebSocket.** Each turn is a bounded request/response exchange; SSE reuses the existing bearer-auth model every other endpoint already uses.
3. **New `adp.chat` package, not an `adp.agents` adapter.** Cross-domain reads are this feature's whole point — structurally incompatible with the toolkit's zero-domain-import guarantee, which stays intact for Agent Review and any future single-domain adapter.
4. **Retrieval is two-legged.** Extend `adp.search` (already built for exactly this extension) for fuzzy questions; a fixed read-only tool registry for precise/aggregate ones. `adp.knowledge` (curated organizational knowledge) is a different system, out of scope here.
5. **Sensitive-category filtering lives in the tool implementation**, checked against the asking user's real permissions — never a prompt instruction the model could be talked out of.
6. **One new broadly-granted action, `USE_CHAT_ASSISTANT`**, gates feature availability; sensitivity is handled per-question inside the tools (point 5), not by this outer gate.
7. **Migration `022`** — two new tables, `chat_conversations` + `chat_messages` — a real, ordinary schema addition this feature genuinely needs (persisted, resumable history), unlike Agent Review's transient-operation shape.
8. **Bounded sliding-window context per turn**, full unbounded history always persisted and shown — bounds cost/latency growth without ever discarding what the user can see.

## Implementation Phases

> Setup lands the schema + retrieval-index extension every story needs, then one phase per user story in priority order — each independently shippable and demonstrable.

### Phase 1 — Setup: persistence + retrieval foundation

Migration `022`; `adp.chat.models`/`store.py` (conversation/message CRUD, actor-scoped); `adp.search` entity-type extension + `index_entity` wiring into `adp.application.store`/`adp.business.store`; `ActionType.USE_CHAT_ASSISTANT` + `PERMISSIONS_VERSION` bump; `web/src/chat/` + `api/chat.ts` skeleton. No LLM orchestration yet — covered by store-level and search-index unit tests only.

### Phase 2 — US1 (P1): Single-domain streamed Q&A

`LLMClient`'s new streaming method (research D1), no tool-use yet — grounded only against the search index's existing `business_capability`/`technical_capability` coverage, proving the toggle → conversation → streamed reply → grounded-citation pipeline end to end with the narrowest possible retrieval surface. `POST .../messages` SSE endpoint; `ChatButton`/`ChatPanel` wired on the Business Capabilities page (FR-013). **Ships the full pipeline with the smallest possible scope.**

### Phase 3 — US2 (P2): Cross-domain retrieval + tool-calling

`adp.chat.tools`' `TOOL_REGISTRY` (portfolio summary, governance status, application/capability lookups, sensitive-category variants gated per research D5); the tool-use turn of the orchestration loop (LLM requests a tool → handler runs → result fed back → generation continues → streams); authz tests per sensitive category (SC-004). First exercise of FR-014's "spans business capabilities, applications, portfolio, governance" requirement.

### Phase 4 — US3 (P3): Conversation history, listable and resumable

`GET /conversations` (list, actor-scoped) and `GET /conversations/{id}` (detail, actor-scoped, 404 either way for not-found-or-not-owned — FR-009); resumption in the web panel; migration `022` up/down integration test; cross-user access-denial tests (SC-003). The underlying rows already exist from Phase 1/2 — this phase's job is the read-back/listing/resume UX and its authorization guarantees.

### Phase 5 — US4 (P4): Multi-turn context

Bounded sliding-window history assembly per turn (research D8); follow-up-question test scenarios (referent resolution across turns); long-conversation context-growth test confirming the full history remains stored/visible regardless of what's sent to the model.

### Phase 6 — Polish

`adp-generate` regen + drift gate; SC-002's tool-registry read-only check as an automated test (call-graph inspection, not just a naming convention); full contract/unit/integration regression; a new "AI Chat Assistant" section in `docs/solution-architecture.md`, mirroring how Agent Review documented itself.

## Post-Design Constitution Re-Check

Re-evaluate after data-model.md: confirm (a) `adp.chat` genuinely has no reason to import from `adp.agents` beyond the explicitly-reused pieces (grounding, models, LLM client factory) — it is not becoming a second, parallel toolkit; (b) every reply's citations are grounded before display, unverified ones visibly flagged, never silently trusted; (c) the tool registry contains zero write-capable functions (SC-002, automated, not just documented); (d) every sensitive-category tool call is gated by the matching `READ_APPLICATION_*` permission against the real asking user, with a test per category (SC-004); (e) conversations are actor-scoped end to end, with a cross-user-access test proving it (SC-003); (f) migration `022` has a passing up/down test; (g) new models appear in `generated/` after `adp-generate`. No anticipated violations.
