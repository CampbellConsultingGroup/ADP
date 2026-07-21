# Feature Specification: AI Chat Assistant for Business Architecture Q&A

**Feature Branch**: `041-ai-chat-assistant`
**Created**: 2026-07-20
**Status**: Draft
**Input**: User description: "Add a chat option on the Business Capability screen to allow a business architect or business person to ask questions." Follow-up: does this belong on a single page or should it be a capability available across the system? Resolved via clarification: read-only Q&A (no writes, distinct from Agent Review), grounded across business capabilities, applications, portfolio, and governance data (not limited to one domain), with persisted conversation history and real-time streamed replies. First entry point is the Business Capabilities page, built as a system-wide-capable service from day one — mirrors how Agent Review (ADP-SPEC-039/040) shipped one adapter first while keeping its toolkit reusable.

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: (always applies) — this spec precedes implementation.
- **ART-II** — The Model is the Single Source of Truth: the assistant never writes, but every answer MUST be derived from the live canonical stores (via the hybrid search index or read-only tool calls) at the time of the question, never a stale cache or a duplicated shadow copy of business/application data.
- **ART-III** — Everything is Machine-Readable: conversation, message, and tool-call payloads are all typed and schema-emitted.
- **ART-IV** — Test-Driven Development: (always applies) — contract tests for the chat module precede its handlers.
- **ART-V** — Security by Design: the assistant reads across business, application, portfolio, and governance data — including sensitive application categories (risk, cost, governance) if the asking user holds the relevant permission. See Threat Model.
- **ART-VI** — Observability is Not Optional: each chat turn (retrieval query, tool calls made, token usage, latency) MUST emit a span exactly like every other AI orchestration step.
- **ART-VII** — Grounded AI Only: every entity a reply cites MUST be independently verified against the database before being presented as a normal citation; an unverifiable one MUST be visibly marked unverified rather than silently trusted.
- **ART-IX** — Provenance and Auditability: persisted conversation history is itself the audit trail for "who asked what, when, and what the assistant said" — no separate `AuditEntry`/log line is needed since nothing mutates.
- **ART-XI** — Traceability End to End: a reply's factual claims MUST trace back to the specific retrieval hit or tool call that produced them.
- **ART-XIII** — Typed Contracts Everywhere: all boundary payloads (start-conversation, send-message, streamed-chunk, conversation/message list) are Pydantic v2 models with `extra="forbid"`.
- **ART-XV** — Schema Evolution is Governed: unlike Agent Review, this feature *does* add new tables (persisted conversations/messages) via a governed Alembic migration.
- **ART-XVI** — Documentation as Code: the chat module's shared interface (retrieval + tool-registry contract) is documented alongside this spec so a second page's entry point can be built without re-deriving it.

*Not engaged*: ART-VIII (Human-in-the-Loop for Consequence) — there is no consequence to gate; the assistant performs no write of any kind, unlike Agent Review, which this feature is deliberately scoped not to duplicate. ART-X (Deterministic Validation Gating) — no pass/fail gate. ART-XII (Fixed Visual Language) — no diagram rendering change. ART-XIV — no distinctive reproducibility concern beyond the universal gates.

## Threat Model *(mandatory — ART-V)*

**Assets at risk**: this is a materially larger read surface than any single existing AI feature — business capabilities, applications (including sensitive risk/cost/governance records when the asking user is permitted), portfolio aggregates, and governance findings. Nothing is written, but a broad, cross-domain conversational surface increases the chance of an unintended data-exposure path if grounding or permission-filtering is done wrong.

**Trust boundaries crossed**: browser → API (start conversation, send message) → retrieval (`adp.search`) and read-only tool calls (existing REST/store read paths) → LLM provider (context and tool results sent out for reply generation) → streamed back to the browser → conversation persisted to the database.

**Abuse cases**:
- *Prompt injection via indexed entity text*: a capability/application `description` contains text crafted to make the assistant claim things it shouldn't, including trying to talk it into revealing sensitive data → **Mitigation**: sensitive-category filtering happens at the tool/retrieval layer based on the asking user's actual permissions, not by trusting the LLM to self-censor; a tool function refuses to return cost/risk/governance data to a caller who doesn't hold the matching `READ_APPLICATION_*` permission, regardless of what the conversation asks for.
- *Cross-user conversation leakage*: a user reads or lists another user's conversation history → **Mitigation**: conversations are scoped to the creating actor at the API layer; list/get endpoints filter by the authenticated caller, with no shared/global conversation view in v1.
- *Tool-calling scope creep*: a compromised or adversarial prompt tries to get the assistant to invoke a tool outside its intended read-only purpose → **Mitigation**: the tool registry exposed to the LLM is a small, fixed, explicitly enumerated set of read-only functions; structurally, no function in that registry is capable of performing a write, so this isn't a prompt-discipline problem to police at runtime.
- *Sensitive-data leakage via persisted history*: because conversations are stored, anyone with direct database access could see synthesized sensitive figures outside the normal API's permission checks → **Mitigation**: this is an existing operational/DB-access-control concern (no new plaintext-secret exposure); conversation rows carry the same actor scoping the API enforces, and no new direct-DB-read surface is introduced.
- *Cost/abuse via unbounded usage*: unlike a single bounded Agent Review operation, a chat conversation can run indefinitely with many turns, each re-running retrieval and an LLM call → **Mitigation**: reuse existing telemetry/span tracking for cost visibility (ART-VI); a bounded per-turn context window (Edge Cases) limits unbounded growth. Explicit rate-limiting beyond telemetry is out of scope for v1, mirroring Agent Review's equivalent assumption.

**Residual risk**: the assistant can still produce a wrong or misleading answer built from correctly-retrieved, correctly-permission-filtered data (a reasoning error, not a grounding or authorization failure). Accepted because this is inherently an advisory conversational tool, not a system of record — the human reading it is expected to apply judgment, and nothing it says can itself mutate anything.

## Clarifications

### Session 2026-07-20

- **Q: Should the assistant be able to write to the database (e.g., propose the same kind of suggestions Agent Review does), or strictly read-only?** → **A:** Strictly read-only. No grounding/citation/accept-dispatch machinery is needed; this feature complements Agent Review rather than duplicating its write path. A user who wants to act on something the assistant surfaces uses Agent Review or the manual edit UI, not this feature.
- **Q: Should the assistant's context be limited to the page it's opened from (Business Capabilities), or span multiple domains?** → **A:** Cross-domain from the start — business capabilities, applications, portfolio aggregates, and governance data are all in scope, regardless of which page's toggle opened the conversation. This is the central way this feature differs from Agent Review's deliberately narrow, direct-links-only context.
- **Q: How should conversation history behave across page reloads and sessions?** → **A:** Persisted. A conversation and its full message history survive a reload or a new session for the same user, and past conversations can be listed and resumed. This requires new tables (a governed migration), unlike Agent Review's transient `OperationStore`-based operations.
- **Q: What should the UI entry point look like?** → **A:** A contextual toggle button on the page, matching the existing "Review"/"Review Portfolio" pattern, not a persistent app-wide panel or a change to the shared app shell. First entry point is the Business Capabilities page.
- **Q: How should the assistant gather cross-domain context for a given question, given that pulling everything into every prompt (the portfolio review's approach) won't scale to a whole-system Q&A tool?** → **A:** A combination, not semantic search alone: (a) extend the existing hybrid search index (`adp.search`, ADP-b6o — vector + keyword, RRF-fused) to cover applications, value streams, and business domains, for fuzzy/conceptual questions; and (b) give the assistant a small, fixed set of read-only tool calls over the existing REST/store read paths (portfolio aggregates, governance status, precise lookups), for exact/structured questions semantic search can't answer well (e.g. "which capabilities have no domain assigned", "what's our TCO exposure"). `adp.knowledge` (ADP-SPEC-005's curated principles/patterns/decisions index) is a distinct system and out of scope here — it indexes organizational knowledge, not live portfolio data.
- **Q: How should a reply reach the user?** → **A:** Real-time token streaming (SSE), not the submit-then-poll pattern every other AI feature in ADP uses. This is new infrastructure — no existing endpoint streams today — accepted because a poll-based cross-domain chat reply would feel broken compared to a normal chat product, and observed cross-domain LLM latency (the portfolio review took 55–95s for one large prompt) makes waiting silently unacceptable turn over turn.
- **Q: Should sensitive application data (risk, cost, governance) be excluded from the assistant's context entirely, the way Agent Review excludes it regardless of the reviewing user's permissions?** → **A:** No — filtered per the *asking user's own* existing permissions instead, not blanket-excluded. Agent Review's blanket exclusion was an explicit v1 scope-reduction to avoid touching the sensitive-category authz gates on its first ship; this feature's stated use cases explicitly include cost/risk/governance questions ("what's our TCO exposure"), which blanket exclusion would defeat. Each sensitive-category tool call enforces the same `READ_APPLICATION_{RISK,COST,GOVERNANCE}` permission the equivalent REST endpoint already enforces, evaluated against the asking user, not a fixed policy. *(This is a security-relevant design call resolved here rather than left open — flagged for explicit confirmation before implementation begins.)*
- **Q: Is there a known blocker this feature depends on?** → **A:** Yes — `/api/v1/search` (the endpoint over `adp.search`) currently 500s under some conditions (embedding provider unavailable, empty `entity_types`; tracked as `ADP-jyu`, open). This spec's retrieval leg depends on that endpoint's underlying index being reliable; fixing `ADP-jyu` is a prerequisite for this spec's implementation, not something this spec re-fixes as part of its own scope.

## User Scenarios & Testing *(mandatory)*

> Ordered by increasing technical risk rather than write-risk (nothing here writes) — each story proves a harder piece of the pipeline: single-domain streaming Q&A first, then cross-domain retrieval/tool-calling, then persistence, then multi-turn memory.

### User Story 1 - Ask a grounded question, get a streamed answer (Priority: P1)

A business architect on the Business Capabilities page opens the chat toggle and asks a question answerable from business capability data alone (e.g., "which L1 capabilities have no strategic relevance set?"). The assistant streams back a grounded answer, citing the specific capabilities it references.

**Why this priority**: The foundational slice — proves the toggle → conversation → streamed reply → grounded-citation pipeline end to end, using only the domain and retrieval coverage (`business_capability`) that already exists in `adp.search` today, before any new retrieval or tool-calling work lands.

**Independent Test**: Open the chat on the Business Capabilities page, ask a question with a clear, checkable answer against seeded capability data; confirm the reply streams incrementally (not as one blocked response) and cites real capability ids that resolve.

**Acceptance Scenarios**:

1. **Given** the chat is opened on the Business Capabilities page, **When** a question is asked, **Then** the reply begins streaming to the client before the full answer is generated.
2. **Given** a reply that references specific capabilities, **When** the message completes, **Then** each cited capability id is independently verified to exist; an unverifiable one is visibly marked unverified rather than presented as a normal citation.
3. **Given** a question with no answer supported by the available data, **When** the assistant replies, **Then** it says so rather than fabricating an answer.

---

### User Story 2 - Cross-domain question spanning applications, portfolio, and governance (Priority: P2)

The same architect asks a question that can't be answered from business capability data alone — e.g., "which applications support this capability, and what's their health score?" or "are any of our retail applications past end-of-support?". The assistant retrieves and/or calls tools across domains to answer, respecting the asking user's own sensitive-category permissions.

**Why this priority**: The distinguishing capability of this feature versus Agent Review — proves cross-domain retrieval-index extension and the read-only tool-calling layer, including permission-aware filtering of sensitive application data.

**Independent Test**: Ask a question requiring application data not covered by Story 1's index; confirm the reply correctly pulls application fields. Ask a question requiring cost/risk/governance data as a user without the matching permission; confirm that category is omitted or the assistant declines, never silently included.

**Acceptance Scenarios**:

1. **Given** a question referencing applications linked to a capability, **When** the assistant replies, **Then** it correctly retrieves and cites the relevant application data.
2. **Given** a question requiring a sensitive application category (risk, cost, or governance), **When** the asking user holds the matching `READ_APPLICATION_*` permission, **Then** the reply may include that data; **when** they do not, **Then** the reply omits it or explicitly declines rather than including it.
3. **Given** a question requiring an exact/aggregate answer (e.g. a count or a TCO rollup) that semantic search alone cannot reliably produce, **When** the assistant replies, **Then** it uses a read-only tool call to the existing aggregate endpoint rather than approximating from retrieved text.

---

### User Story 3 - Conversation history persists across sessions (Priority: P3)

The architect closes the chat panel (or the browser) and returns later. Their conversation — and any others they've had — are still there, listed and resumable.

**Why this priority**: Lower technical risk than Stories 1–2 (a bounded CRUD/schema addition) despite being high user-value, so it lands after the harder retrieval/streaming plumbing is proven, matching the "safest, most foundational slice first" philosophy this platform already follows for AI features.

**Independent Test**: Have a conversation, reload the page (or start a new session as the same user); confirm the conversation and its full message history are still present and can be continued. Confirm a second user cannot see the first user's conversations.

**Acceptance Scenarios**:

1. **Given** a conversation with several messages, **When** the page is reloaded, **Then** the full message history is still visible and the conversation can be continued.
2. **Given** a user with multiple past conversations, **When** they open the chat, **Then** they can see and resume any of their own past conversations.
3. **Given** two different users, **When** either lists or opens conversations, **Then** neither can see or open the other's.

---

### User Story 4 - Follow-up questions use conversation context (Priority: P4)

Within one conversation, the architect asks a follow-up question that only makes sense in light of an earlier turn (e.g., turn 1: "tell me about the Merchandising capability"; turn 3: "what about its applications?", where "its" refers back to turn 1's subject).

**Why this priority**: The most conversational (as opposed to single-shot Q&A) capability, and the one most sensitive to context-window growth — appropriately last, since Stories 1–3 must all work before multi-turn coherence is worth testing.

**Independent Test**: Ask a question, then a follow-up that omits the subject and relies on the prior turn; confirm the reply correctly resolves the referent rather than asking the user to repeat themselves or answering a different, ungrounded question.

**Acceptance Scenarios**:

1. **Given** an established conversation subject from an earlier turn, **When** a follow-up question omits that subject, **Then** the assistant's reply correctly resolves it from conversation history.
2. **Given** a long-running conversation that exceeds the practical context window for a single LLM call, **When** a new message is sent, **Then** the assistant still replies coherently using a bounded recent-turn window, and the full (unbounded) history remains visible to the user regardless of what was sent to the model.

### Edge Cases

- **Stream interrupted mid-reply** (network drop, browser/tab closed): the partially generated message is persisted as-is (or marked incomplete); the conversation is left in a consistent, resumable state — the next message does not error or duplicate work.
- **Tool-call failure** (a read-only lookup errors — e.g. a downstream store is briefly unavailable): the assistant surfaces a graceful "couldn't retrieve that" for the affected part of the answer rather than crashing the turn or fabricating a substitute answer.
- **Question requires a write** (e.g. "reclassify this capability's maturity" or "delete this application"): the assistant explicitly declines and points to Agent Review or the manual edit UI — this feature performs no writes, ever, and must not create a second implicit write path by "just doing what's asked."
- **Concurrent messages in one conversation** (a second message sent before the first's stream finishes): serialized per conversation — a conversation processes one in-flight turn at a time.
- **Ambiguous cross-domain question with no clear retrieval match**: the assistant says it doesn't have grounded information to answer rather than guessing from a low-confidence retrieval hit.
- **Long conversation / context-window growth**: only a bounded recent-turn window is sent to the LLM per turn (Story 4, Scenario 2); this is a performance/cost bound, not a change to what's stored or shown to the user.
- **Sensitive-category question from an unauthorized user**: the reply omits or declines that category outright — it must not reveal that the data exists (e.g. a figure, or "I can't show you that") in a way that discloses more than a plain absence would.

## Requirements *(mandatory)*

### Functional Requirements

**Chat module (`adp.chat`)**

- **FR-001**: System MUST provide a way to start a conversation and send a message within it, streaming the assistant's reply back to the client incrementally rather than as a single complete response — distinct from every other AI feature in ADP, which uses submit-then-poll.
- **FR-002**: The assistant MUST answer strictly from real data retrieved via the hybrid search index or fetched via explicit read-only tool calls, and MUST NOT write to any table other than this feature's own conversation/message history.
- **FR-003**: System MUST extend the existing hybrid search index (`adp.search`, ADP-b6o) to cover applications, value streams, and business domains (in addition to the business/technical capabilities it already covers), so cross-domain retrieval uses one index rather than a parallel one.
- **FR-004**: System MUST expose a fixed, explicitly enumerated set of read-only tool functions the assistant may call for precise/structured questions semantic search cannot reliably answer (e.g. portfolio aggregates, governance status, exact entity lookups); this set MUST contain no function capable of performing a write.
- **FR-005**: Every tool function that reads a sensitive application data category (risk, cost, or governance) MUST enforce the same permission (`READ_APPLICATION_RISK` / `READ_APPLICATION_COST` / `READ_APPLICATION_GOVERNANCE`) the equivalent REST endpoint already enforces, evaluated against the asking user — never a blanket inclusion or exclusion. *(Resolved 2026-07-20.)*
- **FR-006**: Every entity a reply cites MUST be independently verified to exist, reusing the existing grounding validator; an unverifiable citation MUST be visibly marked unverified in the reply rather than presented as a normal, trusted citation.
- **FR-007**: System MUST emit an observability span for each chat turn (retrieval query issued, tool calls made, token usage, latency), consistent with every other AI orchestration step in the platform.
- **FR-008**: System MUST persist conversation history — every message, both user and assistant, including the assistant's citations — so a conversation survives a page reload and can be resumed in a later session. *(Resolved 2026-07-20 — requires new tables; see Key Entities.)*
- **FR-009**: System MUST scope conversation history to the actor who created it; a user MUST NOT be able to list or read another user's conversations.
- **FR-010**: The web layer MUST provide a reusable chat panel/toggle component parameterized the same way the Agent Review components are, so a second page can adopt the same chat capability without duplicating the component.
- **FR-011**: A single conversation MUST process at most one in-flight message turn at a time; a second message sent while a reply is streaming MUST be rejected or queued, not processed concurrently against the same conversation history.
- **FR-012**: When a question would require a write to answer as asked (e.g. "reclassify this," "delete that"), the assistant MUST decline rather than attempting it — this feature has no write path to fall back on, by design.

**Business Capabilities entry point**

- **FR-013**: The Business Capabilities page MUST provide a contextual toggle (matching the existing "Review"/"Review Portfolio" pattern) that opens the chat panel.
- **FR-014**: From this entry point, the assistant's retrieval/tool-calling MUST be able to answer questions spanning business capabilities, applications, portfolio aggregates, and governance findings — not limited to business capability data alone. This is the requirement that most distinguishes this feature's scope from Agent Review's deliberately narrow, direct-links-only context.

**Permissions**

- **FR-015**: Starting a conversation and sending a message MUST be gated by a dedicated action-based permission, granted broadly (every role that can view the relevant pages), since the feature performs no write and each sensitive-category read is independently gated per FR-005 — the outer gate controls feature availability, not data sensitivity.

### Key Entities *(include if feature involves data)*

- **ChatConversation** (new, persisted): id, owning actor, an auto-derived or default title, created/updated timestamps.
- **ChatMessage** (new, persisted): id, conversation id, role (user/assistant), content, the assistant message's citations (if any), created timestamp.
- **ToolCallResult** (module-level, not persisted): the result of one read-only tool invocation within a turn — which tool, its arguments, and what it returned — feeding the assistant's reply and this spec's grounding/citation requirements.
- **BusinessCapability, BusinessDomain, ValueStreamStage, Application, TechnicalCapability** (all existing): read via the extended hybrid search index and/or tool calls.
- **Portfolio aggregates, governance findings** (existing, read via new tool functions, not new entities): the same data `/api/v1/portfolio/summary` and `/api/v1/governance/*` already expose.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every reply that cites a specific entity has that citation independently verified against the database; an unverifiable one is always visibly marked unverified, never presented as a normal, trusted citation.
- **SC-002**: Zero tool functions exposed to the assistant perform a write — verified by an automated check over the tool registry (mirroring Agent Review's import-boundary check), not just documentation.
- **SC-003**: A user attempting to list or open another user's conversation is refused, in 100% of cases, verified by authorization tests.
- **SC-004**: A user without a given sensitive application-data permission (risk, cost, or governance) never receives that category's data in a chat reply, verified by an authorization test per category, mirroring the existing REST-endpoint tests for the same permissions.
- **SC-005**: A reply begins streaming to the client before the full answer is generated, in every successful turn — never delivered as one blocking response.
- **SC-006**: A conversation and its full message history persist across a browser reload and a new session for the same actor, in 100% of cases.
- **SC-007**: All new boundary payloads pass schema validation with zero schema-drift-check failures in CI.

## Assumptions

- **`ADP-jyu` (the existing `/api/v1/search` 500 bug) is fixed before or alongside this spec's implementation.** This spec depends on `adp.search` being reliable; fixing that bug is a prerequisite, not part of this spec's own functional scope.
- **New database tables are required** (`chat_conversations`, `chat_messages`) via a governed Alembic migration — unlike Agent Review, this feature cannot reuse a transient `OperationStore` shape, since persisted, resumable history is an explicit requirement (FR-008).
- **Streaming is new infrastructure.** No existing ADP endpoint streams a response today; this spec introduces the platform's first SSE (or equivalent) endpoint. The plan phase determines the exact transport and how it interacts with the existing LLM client, which has no streaming method today.
- **Sensitive-category filtering reuses existing permissions.** No new `READ_APPLICATION_*`-style action types are introduced; FR-005 reuses the three that already exist.
- **One entry point delivered, the module built for reuse.** This spec ships the chat module and exactly one page's toggle (Business Capabilities); a second page's entry point is a future, near-zero-cost follow-up once the module exists, not part of this spec — mirroring how Agent Review shipped one adapter first with reusability proven at the interface level rather than by building a second instance.
- **No cross-conversation learning.** Unlike the recommendation engine's accepted/rejected-decision capture (ADP-SPEC-019), this feature does not have conversations influence each other; multi-turn memory (Story 4) is scoped to a single conversation's own history.
- **Reused LLM provider configuration.** The same `ADP_LLM_ENDPOINT`/`ADP_LLM_API_KEY`/model-selection configuration already used by intake, recommendation, and Agent Review is reused; no new provider integration.
- **Cost/token tracking remains at its current state** (same caveat as Agent Review) — existing gaps in LLM cost estimation are not fixed by this feature.
