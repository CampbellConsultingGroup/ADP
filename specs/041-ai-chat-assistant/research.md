# Research & Decisions: AI Chat Assistant (ADP-SPEC-041)

Phase 0 output. Each decision records the choice, rationale, and rejected alternatives.

## D1 — `LLMClient` needs new capabilities (multi-turn, streaming, tool-use); extend it, don't replace it

**Decision**: Add new methods to the existing `adp.llm.client.LLMClient` — a multi-turn, streaming, tool-use-capable chat call — built on the same raw-`httpx` request pattern the client already uses for both its Anthropic and OpenAI-compatible branches, rather than switching to the official `anthropic` Python SDK.

**Rationale**: Read directly from source (`src/adp/llm/client.py`): today's `chat()` takes a single `system`/`user` string pair, is non-streaming, and has no tool-use parameter — verified, not assumed. All three capabilities this feature needs (message history, `"stream": true` + SSE response parsing, `tools`/`tool_choice` + handling `tool_use`/`tool_result` content blocks) are additive to the Anthropic Messages API request body the client already POSTs to; they don't require a different client architecture. Keeping everything on raw `httpx` preserves the client's existing dual-provider design (Anthropic vs. OpenAI-compatible, detected from `base_url`) for this new method too, consistent with how `chat()`/`extract()` already branch.

**Rejected**: Switching to the official `anthropic` SDK for the new method only — its streaming (`client.messages.stream()`) and tool-use ergonomics are genuinely nicer, but it is Anthropic-specific; introducing it for exactly one method while every other method stays on raw `httpx` (to keep OpenAI-compatible support) would leave two different HTTP client patterns in one class for no consistent reason. Revisiting this tradeoff for the whole client is a larger, separate decision outside this spec's scope. Building a bespoke non-Anthropic-shaped streaming/tool protocol — rejected; there's no reason to invent a wire format when the Anthropic Messages API (which the client already speaks) natively supports both.

## D2 — Server-Sent Events (SSE), not WebSocket

**Decision**: The chat reply endpoint streams via SSE (`text/event-stream`, one-directional server→client), implemented with FastAPI's `StreamingResponse` over an async generator — not a WebSocket.

**Rationale**: Each turn is a bounded request/response exchange (send one message, stream back one reply) — there is no need for the client to push additional data mid-stream, which is the case WebSockets are for. SSE reuses the existing request/response/auth-header model every other ADP endpoint already uses (a WebSocket needs its own auth handshake, since browsers can't set arbitrary headers on the initial upgrade request), and degrades simply (the client can always fall back to reading the final persisted message via the normal REST GET if a stream is interrupted — see spec Edge Cases).

**Rejected**: WebSocket — solves a bidirectional-push problem this feature doesn't have, and reopens the auth-header question ADP's existing bearer-token model already answers cleanly for plain HTTP/SSE. Long-polling — no material advantage over SSE and a worse UX (chunked delivery is the whole point).

## D3 — New top-level `adp.chat` package, not inside `adp.agents`

**Decision**: The chat module lives at `src/adp/chat/` (models, store, tools, orchestrator, router), a peer to `adp.business`/`adp.application`/`adp.agents` — not inside `adp.agents`.

**Rationale**: `adp.agents`' entire contract (ADP-SPEC-039 FR-005, SC-005, mechanically enforced by `tests/unit/agents/test_toolkit_boundary.py`) is zero imports from any single domain module. This feature's core value is reading *across* `adp.business` and `adp.application` (and portfolio/governance data) in one turn — a structural violation of that contract by design, not an oversight. Putting chat in a clean new top-level package keeps `adp.agents`' existing guarantee intact for Agent Review and any future single-domain adapter, while giving chat its own room to do the cross-domain thing it actually needs to do. What chat *does* reuse from `adp.agents` — the LLM client factory pattern, `adp.telemetry.spans.ai_step_span`, the `GroundingCitation` model, the grounding-verification function — it imports normally, same as any other consumer.

**Rejected**: Loosening `adp.agents`' domain-agnostic rule to let this one exception in — would weaken the exact guarantee that made a second Agent Review adapter possible without touching the toolkit; not worth trading away for one feature. A per-domain chat adapter under `adp.business` mirroring Agent Review's adapter pattern — doesn't fit, since chat's whole point (per spec Clarifications) is not being scoped to one domain the way an Agent Review adapter is.

## D4 — Retrieval: extend `adp.search` (ADP-b6o) + a fixed read-only tool registry; not `adp.knowledge`, not tool-calling alone

**Decision**: Two complementary mechanisms, both read-only:
1. Extend `adp.search`'s entity-type coverage — add `ENTITY_APPLICATION`, `ENTITY_VALUE_STREAM`, `ENTITY_BUSINESS_DOMAIN` alongside the existing `ENTITY_BUSINESS_CAPABILITY`/`ENTITY_TECHNICAL_CAPABILITY` — and wire `index_entity`/`unindex_entity` into `adp.application.store`'s application CRUD and `adp.business.store`'s value-stream/domain CRUD (mirroring the calls that already exist for capabilities and technical capabilities). Used for fuzzy/conceptual questions via `SearchIndex.hybrid_search()`.
2. A small, fixed, explicitly enumerated set of read-only tool functions in `adp.chat.tools` (e.g. `get_capability`, `get_application`, `portfolio_summary`, `governance_status`), each a thin wrapper around an existing store/aggregate function already used by a REST endpoint. Used for precise/structured/aggregate questions.

**Rationale**: Confirmed by reading `src/adp/search/index.py`: it's a generic, polymorphic hybrid (vector + keyword, RRF-fused) index explicitly designed for exactly this kind of extension ("Extend with value_stream / business_domain" is in its own docstring) — reusing it is a few new discriminator constants and a handful of `index_entity` call sites, not new infrastructure. `adp.knowledge` (ADP-SPEC-005) is a distinct system indexing curated organizational knowledge (principles, patterns, ADRs) for the Recommendation Engine — not live portfolio data — so it's the wrong target for "what does our data say" questions. Semantic search alone is the wrong tool for exact/aggregate questions (spec Clarifications) — "which capabilities have no domain assigned" or a TCO rollup are SQL aggregates, not similarity matches, so the tool-call leg is not optional scaffolding, it's load-bearing for a real class of question this feature must answer.

**Rejected**: Building a new parallel semantic index for chat specifically — `adp.search` already exists and is built for this; a second index would fragment retrieval infrastructure with no benefit. Tool-calling alone, no search extension — makes fuzzy/conceptual questions ("what capabilities relate to returns?") clunky, since the assistant would need a bespoke "search capabilities by keyword" tool that badly reinvents what `adp.search` already does well. Reusing `adp.knowledge`'s retrieval interface for registry data — wrong data source; would require duplicating registry content into the curated knowledge base, creating a second copy of the truth (ART-II).

## D5 — Sensitive-category filtering happens inside the tool implementation, not via prompt instruction

**Decision**: Each tool function that can surface application risk/cost/governance data takes the asking user's role as an argument and calls the existing `is_permitted(role, ActionType.READ_APPLICATION_{RISK,COST,GOVERNANCE})` check before returning that category's data — returning an explicit "not permitted" result (not an error, not silent omission that could be mistaken for "no data exists") when the check fails. The LLM is never asked to self-censor via prompt wording.

**Rationale**: Mirrors D6 from ADP-SPEC-039 (Agent Review excludes sensitive data "by construction, not by permission check" for its narrower blanket-exclusion case) — same principle, adapted: the enforcement point is the code path that can return the data, not the prompt or the model's behavior, so there is no way for a cleverly-worded question to talk the assistant into ignoring an instruction, because the instruction isn't the thing doing the enforcement.

**Rejected**: Filtering after the fact (fetch everything, strip sensitive fields from the LLM's response before displaying it) — the data would already have been sent to the LLM provider, which is the actual point of leakage the mitigation needs to prevent, not just the display. Prompt-level instruction ("don't reveal cost data unless authorized") — exactly the "trusting the LLM to self-censor" pattern the spec's own Threat Model calls out as insufficient.

## D6 — New action `USE_CHAT_ASSISTANT`, granted broadly

**Decision**: One new `ActionType.USE_CHAT_ASSISTANT` gates starting a conversation and sending a message — granted to every role that can view a page the chat toggle appears on (i.e., broadly, not restricted the way `CONFIRM_AGENT_SUGGESTION` is to write-capable roles). `PERMISSIONS_VERSION` bumps accordingly.

**Rationale**: Per FR-015, this outer gate controls feature availability, not data sensitivity — sensitivity is handled per-category, per-question, inside the tools themselves (D5). A broadly-granted action is consistent with the spec's framing of chat as a low-risk, read-only capability available to "a business architect or business person," not a specialist action like triggering Agent Review or confirming a suggestion.

**Rejected**: Reusing `SUBMIT_AI_OPERATION` — that action's existing semantics are "start a tracked, poll-based AI job" (intake, recommend, Agent Review); chat's request/response shape is different enough (streaming, not poll) that overloading the same action would blur what the permission actually gates. No permission at all (treat as a safe/always-open action like a GET) — rejected because starting a conversation and sending a message are both POSTs that create rows, and every existing mutating route in this codebase resolves to an explicit action (enforcement.py's completeness test would fail on an unmapped route) — consistent with existing convention, not a new exception.

## D7 — New migration 022: `chat_conversations` + `chat_messages`

**Decision**: One new Alembic migration, revision `022`, `down_revision = "021"` (current head, confirmed via `alembic heads`), adding two tables: `chat_conversations` (id, actor, title, created_at, updated_at) and `chat_messages` (id, conversation_id FK → chat_conversations.id ON DELETE CASCADE, role, content, citations JSONB, created_at).

**Rationale**: FR-008 requires conversation history to survive a reload and be resumable — a genuine, bounded, ordinary CRUD schema addition, unlike Agent Review's transient operations (which had no such requirement). `ON DELETE CASCADE` from message to conversation avoids orphaned messages if a conversation is ever deleted; citations stored as JSONB alongside the message keep a reply's grounding record next to the text it belongs to, without a separate join table for what is, per message, a small and simple list.

**Rejected**: Storing conversation history inside `OperationStore`/JSONB payloads (the ADP-SPEC-039 pattern) — that store's shape (single-operation status/payload, TTL-bounded) doesn't fit an ever-growing, independently-listable, per-actor collection of conversations each with many messages; forcing it in would be a worse fit than a normal two-table schema purpose-built for exactly this. A single denormalized table (conversation + all its messages as one JSONB blob) — makes appending a new message an increasingly expensive full-row rewrite as a conversation grows, and complicates the FR-009 actor-scoping check versus a straightforward `WHERE actor = :actor` on a dedicated conversations table.

## D8 — Bounded sliding-window context per turn; full history always persisted and shown

**Decision**: Each turn sends the LLM a bounded number of the most recent messages (a fixed count, tuned during implementation) from the conversation, regardless of how long the full stored history is. The complete, unbounded history is always persisted and always shown to the user in the UI — the window only bounds what's sent to the model for generating the *next* reply.

**Rationale**: Directly satisfies spec Edge Case "long conversation / context-window growth" (Story 4, Scenario 2) — bounds token cost and latency growth as a conversation gets long, without ever discarding anything from what the user can see or what's stored.

**Rejected**: Summarizing older turns into a running summary sent instead of raw messages — a reasonable future enhancement, but real added complexity (a second LLM-assisted process, itself subject to the same grounding concerns) not justified for v1 when a fixed window already satisfies every acceptance scenario in the spec. Sending the entire history every turn with no bound — the naive approach, rejected because it's exactly the unbounded-growth problem the edge case exists to prevent.

## Open items for `/speckit.tasks`

- Exact sliding-window turn count (D8) is an implementation-tuning detail, not a schema/contract decision — pick a reasonable default (e.g. last 10 messages) during task breakdown and adjust based on real usage, not a spec change.
- Confirm during implementation whether `ADP-jyu` (the pre-existing `/api/v1/search` 500 bug, spec Assumptions) is resolved before Phase 2 (US1) begins — it blocks even the narrowest single-domain retrieval path.
- Fixed system-prompt wording for the assistant persona is a prompt-engineering detail, iterable without a spec change, same as ADP-SPEC-039's equivalent open item.
