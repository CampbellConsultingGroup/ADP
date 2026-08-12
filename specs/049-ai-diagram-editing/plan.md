# Implementation Plan: AI-Assisted Diagram Generation/Editing

**Branch**: `049-ai-diagram-editing` | **Date**: 2026-08-11 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/049-ai-diagram-editing/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Embed `adp.chat`'s existing `ChatButton`/`ChatPanel` (already used on the Capabilities page) inside `DiagramEditorPage.tsx`. The assistant is made diagram-aware not through a new backend tool, but by extending `SendMessageRequest`/`run_turn` with an optional `diagram_context` string — the frontend supplies the diagram's current title/type/DSL fresh on every message, appended into the system prompt exactly the way `run_turn`'s existing hybrid-search `context_block` already grounds capability/application answers. This works uniformly for saved *and* unsaved (ADP-914.7-generated) diagrams alike, since it never depends on a persisted `diagram_id` a tool would need to look up. The assistant is instructed to respond to an edit request with the complete updated DSL in a single fenced code block; the frontend detects that block once streaming completes and calls the editor's existing `applyDsl()` — the same mechanism already used to load a reopened diagram — so the proposal appears in the live, reviewable Canvas/DSL panel with zero new confirmation UI. Nothing is ever auto-saved; the existing Save button remains the only persistence gate. Manual editing is disabled while a request streams (Clarifications), mirroring the codebase's own `disabled={saving}` convention. **Zero new entries in `adp.chat.tools.TOOL_REGISTRY`** — the mechanically-enforced read-only boundary test needs no changes at all.

## Technical Context

**Language/Version**: Python 3.12 (backend); TypeScript 5.x + React 18.3 (frontend) — both existing stacks, no new language/version surface.
**Primary Dependencies**: None new. Reuses `adp.chat`'s existing orchestrator/router/models (ADP-SPEC-041), `web/src/chat/{ChatButton,ChatPanel}.tsx` and `web/src/api/chat.ts`'s `useSendMessage` (already generic/`basePath`-parameterized), and `DiagramEditorPage.tsx`'s existing `useDslSync`/`applyDsl` (ADP-SPEC-046).
**Storage**: No schema change. `diagram_context` is a per-request, ephemeral string — appended to that turn's system prompt only, never persisted as part of the stored `ChatMessage` (a diagram's content changes continuously; "what was in the diagram at the time of a historical message" isn't a requirement this feature needs to satisfy — see Assumptions).
**Testing**: pytest (backend: `run_turn`'s new optional parameter, system-prompt assembly with/without diagram context) + Vitest/RTL (frontend: the new fenced-DSL-extraction pure function, `DiagramEditorPage`'s manual-edit-disabled-while-streaming behavior, `ChatPanel`'s new context-getter prop).
**Target Platform**: Existing `adp-api` process (Linux server) + browser (existing `web/` SPA) — no new deployable.
**Project Type**: Web application — this feature touches both sides of the existing FastAPI backend + React frontend split, unlike ADP-914.6/914.7 (frontend-only). Still zero new dependencies, zero migration.
**Performance Goals**: None specific beyond `adp.chat`'s own existing streaming-response latency expectations — appending one more block of text (the diagram's DSL, already size-capped at 50,000 chars per ADP-SPEC-046) to the system prompt is a bounded, one-time cost per turn, not a new performance surface.
**Constraints**: Zero new `adp.chat.tools.TOOL_REGISTRY` entries (spec Assumptions — stays inside the existing, mechanically-enforced read-only boundary with no changes needed to `tests/unit/chat/test_tools_boundary.py` at all, since nothing new is added to walk); zero new accept/reject UI (spec Assumptions); manual editing disabled during an in-flight request (Clarifications, FR-011); `SendMessageRequest` keeps `extra="forbid"` — the new field is additive and optional, not a breaking change to the existing Capabilities-page chat flow, which simply never supplies it.
**Scale/Scope**: 3 modified backend files (`models.py`, `router.py`, `orchestrator.py` — no new files), ~5 modified/new frontend files (`chat.ts`, `ChatPanel.tsx`, `DiagramEditorPage.tsx`, one new small pure-function module for DSL-block extraction + its test).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Applies? | How this feature satisfies it |
|---|---|---|
| ART-I (SDD Mandatory) | Yes | spec.md (16/16 checklist, 1 clarification resolved) → this plan → tasks.md (next command) → implementation, in order. |
| ART-II (Model is Source of Truth) | Yes (reaffirmed) | The diagram's own DSL source text remains its authoritative representation (ADP-SPEC-046's own framing) — an AI-proposed edit is just another way *that same* authoritative text gets produced, exactly like a manual edit or an ADP-914.7 generator; no second representation is introduced. |
| ART-III (Machine-Readable) | No new obligation | Diagrams are already machine-readable structured data (ADP-SPEC-046); this feature adds a new *way to produce* that data, not a new data shape. |
| ART-IV (TDD) | Yes | tasks.md will sequence failing backend tests (`orchestrator.py`'s new parameter) and frontend tests (DSL-extraction, streaming-disables-editing) before each implementation task. |
| ART-V (Security by Design) | Yes | Threat model re-confirmed in spec.md — no new trust boundary, no new tool, no new write path; the diagram-context string flows through the *same* system-prompt mechanism `context_block` already uses, not a new injection point of a fundamentally different kind. |
| ART-VI (Observability) | Yes | `run_turn`'s existing `ai_step_span("chat_turn", ...)` telemetry wraps this unchanged — a diagram-context-bearing turn is still just a `chat_turn` span, no new span type needed. |
| ART-VII (Grounded AI Only) | Yes, and this is the article this feature exercises most directly | The diagram-context block is the grounding source for both Q&A (US1) and edit proposals (US2) — the same "answer strictly from the context provided" system-prompt instruction (`_SYSTEM_PROMPT`, confirmed by direct read) already governs capability/application answers and now extends naturally to diagram content appended the same way. |
| ART-VIII (Human-in-the-Loop for Consequence) | Yes — the central constraint | FR-006/FR-007: a proposal only ever reaches the editor's *reviewable* state via the existing `applyDsl()`; the pre-existing Save button remains the sole persistence gate, unmodified. No new confirmation UI is built *because* this existing one already satisfies the article, exactly as it already does for hand-typed and ADP-914.7-generated content. |
| ART-IX (Provenance/Auditability) | No new obligation | Unchanged from ADP-SPEC-046/ADP-914.7 — a diagram saved after AI assistance is stored identically to any other; no new audit-trail integration in this iteration. |
| ART-X (Deterministic Validation Gating) | No | No LLM-as-a-Judge verdict for diagrams; the existing DSL parser's error surface (already relied on for every other diagram-content origin) is the only gate, reused unmodified. |
| ART-XI (Traceability) | No | Unchanged — linking diagrams into the requirement→recommendation→verdict thread remains explicitly out of scope. |
| ART-XII (Fixed Visual Language) | No | Governs the locked C4 theme specifically. |
| ART-XIII (Typed Contracts) | Yes | `SendMessageRequest` (Pydantic v2, `extra="forbid"`) gains one new, optional, typed field — the same contract discipline already governing every other ADP boundary. |
| ART-XIV, ART-XV (Reproducible builds / Schema evolution) | No | No migration — `diagram_context` is a request-only field, never persisted. |
| ART-XVI (Documentation as Code) | Yes (SHOULD) | A short note in `web/src/diagrams/README.md` and `src/adp/chat/`'s own module docstrings (mirroring `tools.py`'s existing documentation density) on the diagram-context convention. |

**Initial gate result**: PASS. No article is violated. **No Complexity Tracking entry is needed** — every design decision below picks the option that reuses an existing mechanism (`context_block`, `applyDsl()`, `disabled={saving}`, `ChatButton`/`ChatPanel`) over introducing a new one, and the research below specifically ruled out the more complex alternative (a new `TOOL_REGISTRY` entry requiring a persisted `diagram_id`) because it couldn't satisfy FR-002 for unsaved diagrams.

**Post-Phase-1 re-check**: PASS (unchanged) — data-model.md confirms no persisted entity or schema change; the design stays exactly as additive/reuse-only as the Summary describes.

## Project Structure

### Documentation (this feature)

```text
specs/049-ai-diagram-editing/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md         # Phase 1 output (/speckit.plan command)
├── quickstart.md         # Phase 1 output (/speckit.plan command)
├── contracts/
│   └── chat-diagram-context.md   # Phase 1 output -- the one API contract change
├── checklists/
│   └── requirements.md
└── tasks.md               # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/adp/chat/
├── models.py           # MODIFIED: SendMessageRequest gains
│                        #   `diagram_context: str | None = None`
├── router.py            # MODIFIED: send_message passes body.diagram_context
│                        #   through to run_turn
└── orchestrator.py      # MODIFIED: run_turn gains an optional
                          #   diagram_context param; when present, appended to
                          #   system_prompt alongside new instructions for how
                          #   to respond to an edit request (a single fenced
                          #   DSL code block, nothing else DSL-shaped outside it)

web/src/
├── api/
│   └── chat.ts                    # MODIFIED: useSendMessage's sendMessage()
│                                   #   gains an optional diagramContext param,
│                                   #   included in the POST body
├── chat/
│   └── ChatPanel.tsx               # MODIFIED: new optional getDiagramContext?
│                                   #   prop (a getter, called fresh at send
│                                   #   time -- avoids the stale-closure bug
│                                   #   this file's own useSendMessage doc
│                                   #   comment already warns about)
└── diagrams/
    ├── editor/
    │   └── extractProposedDsl.ts   # NEW: pure function, (assistant response
    │   └── extractProposedDsl.test.ts  #   text) -> proposed DSL string | null
    └── DiagramEditorPage.tsx       # MODIFIED: embeds ChatButton/ChatPanel
                                     #   (mirrors CapabilityTree.tsx's existing
                                     #   embed pattern); getDiagramContext
                                     #   sourced from current title/diagramType/
                                     #   dsl state; on a completed assistant
                                     #   response, extractProposedDsl() + if
                                     #   found, applyDsl(); Canvas/DslPanel
                                     #   editing disabled while isStreaming
                                     #   (FR-011)

tests/unit/chat/
└── test_orchestrator.py            # MODIFIED: new cases for diagram_context
                                     #   present/absent in system prompt assembly
```

**Structure Decision**: No new backend module, no new frontend module — every file touched already exists and already owns the exact responsibility being extended (`orchestrator.py` already assembles `system_prompt` from optional context; `ChatPanel.tsx` is already the generic embed point; `DiagramEditorPage.tsx` already owns `applyDsl`/`isStreaming`-shaped state). One new frontend file: a small, independently-testable pure function for extracting a fenced DSL block from freeform text, kept separate from `DiagramEditorPage.tsx` itself so it can be unit-tested without any component rendering.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations — table intentionally omitted.
