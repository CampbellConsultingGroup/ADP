# Phase 0 Research: AI-Assisted Diagram Generation/Editing

`spec.md` deliberately left one question to this phase: exactly how the assistant obtains the
diagram's current content. That question, and three others discovered while resolving it, are
answered below — all grounded in direct reads of `adp.chat`'s actual code, not assumed from its
description.

## Decision 1: Diagram context is frontend-supplied per-request, not fetched via a new backend tool

**Decision**: Extend `SendMessageRequest` with an optional `diagram_context: str | None = None`
field. The frontend builds this string (title, type, current DSL) from the diagram editor's own
live state and sends it fresh with every message while the chat panel is embedded in
`DiagramEditorPage.tsx`. `run_turn` appends it to that turn's system prompt, in the same place and
manner its existing `context_block` (built from `retrieval.retrieve_context()`'s hybrid-search
hits) already grounds capability/application answers.

**Rationale**: Directly confirmed by reading `orchestrator.py`'s `run_turn` and `adp.chat.tools`
that a new `TOOL_REGISTRY` entry — the initially-plausible design sketched during specification —
cannot satisfy spec.md's FR-002 ("reflecting the live editor state, including unsaved edits"). A
tool the model calls needs an argument to call it *with* (e.g., a `diagram_id`), but an
ADP-914.7-generated diagram that hasn't been saved yet has no id at all — there is nothing for such
a tool to look up. A tool-based design would work for saved diagrams and silently fail (or need an
awkward special case) for unsaved ones, directly contradicting an explicit requirement. Since the
frontend *already holds* the diagram's full current content in memory regardless of save state
(it's literally the editor's own React state), having it supply that content directly sidesteps
the whole problem — and this also means **zero changes are needed to
`adp.chat.tools.TOOL_REGISTRY`** or its mechanically-enforced read-only boundary test
(`tests/unit/chat/test_tools_boundary.py`), since nothing new is added for it to walk.

**Alternatives considered**:
- A new `get_diagram(diagram_id)` tool, mirroring `get_capability`/`get_application` — rejected
  per the rationale above (can't cover unsaved diagrams, which spec.md explicitly requires
  covering).
- Indexing diagram content into `adp.search`'s existing polymorphic hybrid-search index (the same
  one `retrieval.retrieve_context()` already queries for capabilities/applications/value
  streams/domains) so it would surface automatically — rejected: diagrams were deliberately *not*
  added to that index when it was last extended (confirmed: the index's own entity-type list has
  no diagram discriminator), and semantic retrieval is the wrong fit anyway for "the one specific
  diagram currently open" — that's exact, not semantic, context, and indexing would also reintroduce
  the "no id for an unsaved diagram" problem in a different form (nothing to index yet).
- Encoding diagram context into the visible message `content` string itself (e.g., a hidden prefix)
  — rejected: pollutes the conversation history a user actually reads, and duplicates content on
  every turn in the persisted `ChatMessage` row for no benefit over a request-only field that's
  never stored (Decision 2).

## Decision 2: Diagram context is never persisted with the stored message

**Decision**: `diagram_context` lives only on the `SendMessageRequest`/`run_turn` call for that one
turn — it is folded into the system prompt sent to the LLM, but `chat_store.append_message` keeps
storing only the user's actual typed `content`, unchanged.

**Rationale**: A diagram's content changes continuously as the architect edits it — "what was in
the diagram at the moment of this historical message" isn't a requirement spec.md asks for (its
FRs are about the *current* interaction, not a historical record), and persisting a potentially
large DSL blob (up to the existing 50,000-char cap, ADP-SPEC-046) with every single chat message
would be pure storage bloat for data that's already fully reconstructable from the diagram itself
at read time, if ever needed. Keeping it request-only also means zero schema change — confirmed by
checking `ChatMessage`'s model shape, which has no room for it today and needs none added.

**Alternatives considered**:
- Snapshotting `diagram_context` onto the stored message row — rejected per the rationale above;
  would also require a migration for no requirement it serves.

## Decision 3: The assistant's edit proposal is a fenced DSL code block, detected client-side after streaming completes

**Decision**: The system prompt (appended alongside the diagram context, only when it's present)
instructs the assistant: when asked to modify the diagram, respond with the complete updated DSL
in a single fenced code block (info-string = the diagram's type, e.g. ` ```flowchart `), and
nothing else DSL-shaped outside it. A new, small, independently-testable pure function,
`extractProposedDsl(responseText, diagramType)`, looks for exactly that pattern once the SSE stream
finishes (never mid-stream, to avoid acting on partial/incomplete DSL) and returns the extracted
text or `null`. `DiagramEditorPage.tsx` calls the existing `applyDsl()` when a match is found.

**Rationale**: This is a plain-text convention layered on top of `adp.chat`'s *already-existing*
streaming plain-text response — it requires no change to the SSE event protocol
(`text_delta`/`error`), no new tool-call round-trip, and reuses `applyDsl()` exactly as it already
works when reopening a saved diagram (parses full DSL text, replaces the live model wholesale) —
satisfying FR-006 with no new mechanism. "Complete DSL, not a diff" matches how `applyDsl()`
already operates (and how ADP-914.7's generators already hand off full `DiagramModel`s), so this is
consistent with every other diagram-content-origin already in this codebase, not a new pattern
introduced just for AI content.

**Alternatives considered**:
- A structured JSON response (e.g., a tool-call-shaped "propose_edit" payload) instead of a fenced
  code block in plain text — rejected: would require the model to actually call a tool (reopening
  Decision 1's "needs an id" problem, or requiring a no-op/context-only tool purely to carry a
  structured return type, which is more machinery for the same outcome) rather than just replying
  in the same free-text channel it already uses for every other answer.
- A diff/patch format instead of the complete DSL — rejected: `applyDsl()` has no diff-application
  mode today (confirmed by reading `useDslSync`), and building one would be new, untested surface
  for a benefit (smaller model output) this feature's scale doesn't need — diagrams are already
  size-capped at 50,000 chars, well within normal LLM output limits.

## Decision 4: Manual editing disabled during a request, reusing an existing pattern exactly

**Decision**: `DiagramEditorPage.tsx`'s `Canvas`/`DslPanel` become non-interactive whenever
`useSendMessage`'s `isStreaming` is `true` (already returned by that hook today), re-enabled the
moment it resolves — regardless of whether the turn ends in a proposal, a plain answer, or an
error.

**Rationale**: Resolves the Clarifications session's concurrent-edit race (Option B). `isStreaming`
already exists and is already used by `ChatPanel.tsx` for its own UI (disabling its send button);
reusing the same flag to also gate the diagram editor's own interactivity is a one-line addition to
an existing, already-correct state value — not a new state machine. Confirmed by direct read that
this mirrors `DiagramEditorPage.tsx`'s own existing `<button onClick={handleSave} disabled={saving}>`
convention for its Save button — the same "disable during in-flight async work" idiom already used
in this exact file, now applied to a second in-flight operation.

**Alternatives considered**: none seriously — this was the Clarifications session's already-decided
answer; this section records *how* it's implemented, confirming the mechanism (`isStreaming`)
genuinely exists and needs no new plumbing to read.
