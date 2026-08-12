# Feature Specification: AI-Assisted Diagram Generation/Editing

**Feature Branch**: `049-ai-diagram-editing`
**Created**: 2026-08-11
**Status**: Draft
**Input**: User description: "ADP-914.8: AI-assisted natural-language diagram generation/editing. ADP's own AI Chat Assistant (adp.chat, ADP-SPEC-041) already exists and is the intended integration point per the epic's own direction, rather than porting the vendored diagram-core library's own separate AI system."

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: (always applies)
- **ART-IV** — Test-Driven Development: (always applies)
- **ART-V** — Security by Design: applies — see Threat Model. New AI-touched surface, but reuses `adp.chat`'s existing, already-hardened trust boundary rather than opening a new one.
- **ART-VI** — Observability: applies — this is `adp.chat`'s first diagram-scoped capability; any new tool call is a normal, structured-logged operation like `adp.chat`'s existing tool calls, with the same `ai_step_span()` telemetry convention this codebase already uses everywhere else AI is involved.
- **ART-VII** — Grounded AI Only: **applies directly, for the first time in this diagram feature line** — every prior diagram feature (ADP-SPEC-046, ADP-914.6, ADP-914.7) explicitly had *no* AI-generated content. This one does, and every FR below is written to keep the assistant's output grounded in and traceable to the diagram's own current content (what's actually in the model today), not free invention disconnected from it.
- **ART-VIII** — Human-in-the-Loop for Consequence: applies, and is the central design constraint of this feature — see FR-006/FR-007 and Assumptions. No AI-proposed edit is ever persisted without the user's own separate, already-existing Save action; there is no auto-apply, no auto-save.
- **ART-IX** — Provenance and Auditability: applies at the same level ADP-914.7 already established — the append-only audit trail is not extended for diagram saves in this iteration (unchanged from ADP-SPEC-046's own scope decision); a saved diagram, whether AI-assisted or hand-authored, remains indistinguishable in storage.
- **ART-X** — Deterministic Validation Gating: does not apply in its LLM-as-a-Judge-verdict sense — no verdict/judging step exists for diagrams in this codebase. The existing DSL parser's error surface (already relied on for hand-typed and ADP-914.7-generated content) is the only validation gate, reused unchanged.
- **ART-XI** — Traceability End to End: does not apply — linking diagrams into the requirement→element→recommendation→verdict thread remains out of scope (unchanged from ADP-SPEC-046).
- **ART-XII** — Fixed Visual Language: does not apply — governs the locked C4 theme specifically.
- **ART-XIII** — Typed Contracts: applies — any new tool definition follows `adp.chat.tools`'s existing `ToolDefinition` dataclass convention exactly.
- **ART-XIV, ART-XV**: apply only if a migration turns out to be needed (undetermined until planning — see Assumptions); no schema change is anticipated for the chat-side of this feature.
- **ART-XVI** — Documentation as Code: applies (SHOULD).

## Threat Model *(mandatory — ART-V)*

**Assets at risk**: the diagram content itself (may describe sensitive business processes, integrations, or data architecture — same asset class ADP-SPEC-046's own threat model already covers), and `adp.chat`'s existing trust boundary (its LLM provider call, its conversation store).

**Trust boundaries crossed**: browser → `adp.chat`'s existing API → LLM provider → back to browser — an existing boundary, not a new one. No new external system, no new credential.

**Abuse cases**:
- A user asks the assistant to reveal or act on a diagram they aren't authorized to read → mitigated by reusing the diagram's existing read authorization (whatever mechanism the assistant uses to access diagram content must respect the same access rules the diagram editor itself already enforces — no new, weaker path to diagram content is introduced).
- A malicious or malformed AI-proposed edit is applied directly to the user's editor without any validation → mitigated by the existing DSL parser's error surface, which already runs on every edit to the model regardless of its origin (hand-typed or AI-proposed) — no new escape hatch bypasses it.
- Prompt injection via diagram content itself (e.g., a node label crafted to manipulate the assistant's next response) → residual risk, consistent with how this platform already treats any user-generated content fed back into an LLM context elsewhere (e.g., `adp.chat`'s existing capability/application tool results); not a new class of risk this feature introduces.
- An AI-proposed edit silently overwrites the user's own in-progress unsaved manual edits → mitigated by FR-007 (the proposed edit only ever replaces the *reviewable* editor state, which the user sees change immediately and can further edit or discard by not saving — never a background/invisible mutation) and, for the specific race of manual edits made *while a proposal request is in flight*, by FR-011 (manual editing is disabled for the duration of that request, per Clarifications).

**Residual risk**: the same class already accepted for `adp.chat`'s existing tool-augmented conversations (an LLM call over already-authorized data) and for ADP-914.7's generated content (reviewable-before-save, not auto-persisted) — this feature combines two already-accepted risk postures, it does not introduce a new one.

## Clarifications

### Session 2026-08-11

- Q: When a proposed edit arrives, if the architect made manual edits to the diagram while the assistant was composing its response, should those manual edits be preserved or can they be overwritten? → A: Disable manual editing while a proposal request is in flight (mirrors the existing `disabled={saving}` pattern already used on `DiagramEditorPage.tsx`'s Save button), re-enabled once the response lands or fails.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ask the assistant about the diagram I'm looking at (Priority: P1)

While editing a diagram, an architect opens the chat assistant (the same `ChatButton`/`ChatPanel` pattern already available on the Capabilities page) and asks a question about the diagram currently open — e.g. "what does this diagram represent," "which step has no next step," "summarize this flow." The assistant answers using the diagram's actual current content, not a generic guess.

**Why this priority**: The foundational capability every subsequent scenario depends on — the assistant must be able to see what's actually in the diagram before it can meaningfully discuss or edit it. Also independently valuable on its own (a working Q&A capability, even before any edit capability exists), matching this project's pattern of shipping the smallest complete increment first.

**Independent Test**: Open any diagram (saved or freshly generated but unsaved) with at least one node, open the chat assistant, ask a question whose correct answer depends on the diagram's actual content (e.g., "how many nodes does this diagram have"), and confirm the assistant's answer matches the diagram's real current state — not a hallucinated or generic answer.

**Acceptance Scenarios**:

1. **Given** a diagram open in the editor with 3 named nodes, **When** the architect asks the assistant "what are the steps in this diagram," **Then** the assistant's answer names those same 3 nodes (not different or invented ones).
2. **Given** the architect edits the diagram (adds/renames a node) without saving, **When** they then ask the assistant about the diagram, **Then** the assistant's answer reflects the unsaved, current state of the editor — not the last-saved version.
3. **Given** a brand-new, empty, unsaved diagram (per ADP-SPEC-046's "creatable before content exists" precedent), **When** the architect asks the assistant about it, **Then** the assistant correctly reports it as empty, rather than erroring or inventing content.

---

### User Story 2 - Ask the assistant to make an edit, and review it before saving (Priority: P2)

While editing a diagram, an architect asks the assistant to make a change in natural language — e.g. "add a decision step after Review that branches to Approve or Reject." The assistant's proposed change appears directly in the diagram editor (Canvas and DSL panel both update) for the architect to review, adjust further if needed, and only becomes permanent when they click the editor's existing Save button — exactly as it already works for a manually-typed edit or an ADP-914.7-generated diagram.

**Why this priority**: The generative half of the epic's original ask, building directly on User Story 1's grounding capability. Lower priority than US1 because it depends on US1 already working correctly (the assistant can't propose a sound edit without first correctly understanding the current content), and because US1 alone already delivers real, shippable value.

**Independent Test**: Open a diagram with existing content, ask the assistant for a specific, verifiable change (e.g., "rename the 'Start' node to 'Begin'"), and confirm the editor's Canvas/DSL panel reflect that exact change immediately — while the diagram remains unsaved until the architect's own explicit Save click.

**Acceptance Scenarios**:

1. **Given** a diagram open in the editor, **When** the architect asks the assistant to add a specific, well-defined element (e.g., a new node with a given label, connected to an existing node), **Then** the editor's live model updates to include it, visible in both the Canvas and the DSL panel, without requiring the architect to manually type anything.
2. **Given** the assistant has just proposed a change, **When** the architect does nothing further and navigates away without saving, **Then** the change is not persisted — reopening the diagram shows its last-saved state, unaffected by the proposed (but never saved) edit.
3. **Given** the assistant has just proposed a change, **When** the architect manually adjusts it further (e.g., repositions or relabels the new node) before saving, **Then** their manual adjustment is preserved exactly as it would be after any other edit — the AI origin of the starting point does not restrict further manual editing.
4. **Given** the assistant proposes a change that would result in invalid or unparseable DSL, **When** that proposal is applied to the editor, **Then** the existing DSL parse-error surface (already shown for hand-typed mistakes) displays the error — the invalid content is never silently accepted or saved.

---

### Edge Cases

- What happens if the assistant is asked to edit a diagram type it has no meaningful proposal for (e.g., a very unusual or ambiguous request)? → The assistant may respond conversationally without proposing any edit at all — nothing in the editor changes unless a concrete edit is actually proposed. This is a normal "the assistant declined/couldn't help" outcome, not an error state to specially handle.
- What happens to a diagram's identity (title, type) if the assistant is asked to change those rather than the content? → Out of scope for v1's edit capability — FR-005 scopes proposed edits to the diagram's *content* (nodes/edges/containers), not its title or type, both of which the architect can already change directly via the existing editor controls.
- What happens when a diagram is reopened later, after being saved with an AI-assisted edit? → No different from any other saved diagram (FR-008/Assumptions) — there is no indicator, flag, or provenance record distinguishing an AI-assisted save from a hand-authored one, consistent with ADP-914.7's identical decision for generated diagrams.
- What happens if the user has no permission to save diagrams (no `WRITE_DIAGRAM`)? → The assistant may still be usable for read-only Q&A (User Story 1) if the user can view the diagram at all, but any editor entry point requiring `WRITE_DIAGRAM` today (e.g., reaching the editor to author/save) remains gated exactly as it already is — this feature introduces no new permission and weakens none.
- What happens if the architect tries to manually edit the diagram while a requested proposal is still being composed? → Resolved by Clarifications: manual editing is disabled for the duration of that request (FR-011), so there is no window in which a manual edit and an incoming proposal could race and silently clobber each other.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Users MUST be able to open the AI chat assistant while a diagram is open in the editor, using the same chat interface pattern already available elsewhere in ADP (`ChatButton`/`ChatPanel`).
- **FR-002**: The assistant MUST have access to the diagram's actual current content (its nodes, edges, and structure) — reflecting the live editor state, including unsaved edits — when answering questions or proposing changes about it, not a stale or last-saved-only view.
- **FR-003**: The assistant MUST be able to correctly answer questions about the diagram currently open, grounded in that diagram's real content (ART-VII).
- **FR-004**: The assistant MUST support diagrams in any of the 5 existing types (flowchart, sequence, ERD, UML, architecture) — no type is treated as second-class, consistent with every prior diagram feature's own precedent.
- **FR-005**: When the architect requests a content edit (adding, removing, or changing nodes/edges/containers), the assistant MUST be able to propose one, scoped to the diagram's content — not its title or type.
- **FR-006**: A proposed edit MUST be applied directly to the diagram editor's live, reviewable state (visible in both the Canvas and the DSL panel) — never silently or automatically saved.
- **FR-007**: The diagram MUST only become persisted through the architect's own existing, unmodified Save action — identical to how any manual edit or an ADP-914.7-generated diagram is already saved. No new auto-save or auto-apply-and-persist path is introduced.
- **FR-008**: A proposed edit that would produce invalid or unparseable diagram content MUST surface through the existing parse-error display — never accepted or saved silently.
- **FR-009**: The assistant's access to diagram content MUST NOT introduce any new way to read a diagram that bypasses whatever authorization already governs reaching that diagram in the editor.
- **FR-010**: This feature MUST NOT alter ADP-914.6's persona-aware default-type behavior or ADP-914.7's data-driven generators — both remain independently available and unmodified.
- **FR-011**: While a requested proposal is being composed (from the moment the architect asks for an edit until the assistant's response, successful or not, is received), the diagram editor MUST prevent manual edits to the diagram, re-enabling them once that response completes — eliminating any race between a manual edit and an incoming proposal (Clarifications, 2026-08-11).

### Key Entities

- No new persisted entity. A diagram edited with AI assistance is, once saved, an ordinary `Diagram` record (ADP-SPEC-046) — indistinguishable in storage from a hand-authored or ADP-914.7-generated one (Assumptions).
- Conversation/message data follows `adp.chat`'s own existing model (ADP-SPEC-041) — this feature is not expected to change that model's shape, only what it can be asked about and asked to help with while a diagram is open.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An architect can get a correct, content-grounded answer about the diagram they're currently viewing without leaving the diagram editor or switching context.
- **SC-002**: An architect can describe a specific content change in plain language and see it reflected in the editor without manually authoring the corresponding DSL themselves.
- **SC-003**: 100% of AI-proposed edits remain reviewable and reversible (by simply not saving) before they affect any persisted diagram — zero automatic persistence of AI-proposed content, ever.
- **SC-004**: Editing a diagram with AI assistance is indistinguishable, from the editor's own capability, from editing one entirely by hand — no diagram feature (type support, export, further manual editing) is disabled or degraded when AI assistance has been used.

## Assumptions

- **Two independently-shippable capabilities, in priority order**: read-only Q&A about the open diagram (User Story 1) ships as a complete increment on its own before the edit-proposing capability (User Story 2) is added — matching this project's established MVP-first pattern.
- **No new accept/reject suggestion UI, unlike Agent Review** (ADP-SPEC-039/040) elsewhere in this codebase. A proposed edit flows directly into the diagram editor's already-existing reviewable state (Canvas + DSL panel), and the architect's own pre-existing Save button is the sole confirmation gate — deliberately reusing that mechanism rather than building a second, parallel one, since it already satisfies ART-VIII (Human-in-the-Loop for Consequence) for every other diagram-content-origin in this codebase (hand-typed, ADP-914.7-generated).
- **v1 requires a diagram already open in the editor** — either previously saved, or freshly generated-but-unsaved (ADP-914.7). Starting a brand-new diagram purely from a chat conversation, with no editor open yet, is explicitly deferred to a later iteration; this keeps the diagram's identity (which type, which content) unambiguous throughout every interaction in this iteration.
- **No new persisted entity or provenance marker.** A diagram saved after AI assistance is stored identically to any other diagram (per FR-007/FR-008's edit boundary and Key Entities above) — consistent with the same decision ADP-914.7 already made for generated content, for the same reason: this stays a point-in-time authoring aid, not the start of an ongoing AI-diagram relationship the platform has to track.
- **The exact mechanism by which the assistant obtains the diagram's current content** (a new backend tool call, versus content supplied directly by the frontend as part of the conversation, versus some combination) is intentionally left to the planning phase, not decided here — it is an implementation decision, not a business requirement, and depends on `adp.chat`'s existing conversation/context model (to be confirmed by direct code read during planning, not assumed).
- **Out of scope** (per the originating request): any new write-capable tool in `adp.chat`'s tool registry (would violate its existing, mechanically-enforced read-only boundary); reusing or porting the vendored `diagram-core` library's own separate AI tool-calling system; a new accept/reject suggestion UI mirroring Agent Review; any change to ADP-914.6's persona-aware defaults or ADP-914.7's data-driven generators; any change to `adp.chat`'s existing read-only tools or its conversation/message model beyond adding new diagram-scoped capability; starting a brand-new diagram entirely from a chat conversation with no editor open.
