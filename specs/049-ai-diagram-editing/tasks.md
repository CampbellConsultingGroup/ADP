# Tasks: AI-Assisted Diagram Generation/Editing

**Input**: Design documents from `/specs/049-ai-diagram-editing/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/chat-diagram-context.md, quickstart.md

**Tests**: Tests are MANDATORY for all ADP features (ART-IV). Test tasks appear before their implementation counterparts in every phase and MUST be confirmed to fail before implementation begins.

**Organization**: Two independently-testable user stories (read-only Q&A, edit-proposal-and-review) on top of a shared Foundational phase both need (the `diagram_context`/`onComplete` plumbing from `DiagramEditorPage.tsx` through `ChatPanel.tsx`/`chat.ts` to `adp.chat`'s backend).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2)
- File paths are exact and relative to the repo root

---

## Phase 1: Setup

**Purpose**: Confirm the plan's assumptions still hold against the live repo before editing (no new dependencies for this feature — see plan.md Technical Context).

- [x] T001 Confirm `src/adp/chat/models.py`'s `SendMessageRequest` still has only `content: str` (research.md's premise); confirm `src/adp/chat/orchestrator.py`'s `run_turn` still assembles `system_prompt` from `effective_prompt` + `context_block` exactly as read during planning; confirm `web/src/chat/ChatPanel.tsx`'s `handleSend()` still calls `sendMessage(targetId, text)` with exactly two arguments; confirm `web/src/api/chat.ts`'s `useSendMessage` still accumulates `streamedText` via functional `setState` only (no local full-text variable yet); confirm `web/src/diagrams/DiagramEditorPage.tsx`'s Save button is still `disabled={saving}` (the pattern FR-011 mirrors) and `web/src/business/CapabilityTree.tsx`'s `ChatButton`/`ChatPanel` embed is still the pattern to mirror. No file changes — read-only; stop and re-plan if any premise has drifted since planning.

**Checkpoint**: Plan's file-level assumptions reconfirmed — safe to proceed.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The `diagram_context`/`onComplete` plumbing from the browser to `adp.chat`'s system prompt and back — both user stories depend on it existing before either can be demonstrated end-to-end.

**⚠️ CRITICAL**: Neither user story can be built until diagram content can reach the system prompt (US1 and US2 both need it) and a completed response can be reported back to a caller (US2 needs it; harmless plumbing for US1 to have in place).

### Backend: `diagram_context` reaches the system prompt

- [x] T002 [P] Extend `tests/unit/chat/test_orchestrator.py` — new failing test cases for `run_turn`: (a) when called with `diagram_context="Diagram title: X\n..."`, the `system` argument passed to `llm_client.chat_stream(...)` contains that diagram-context text; (b) when `diagram_context` is omitted (or `None`), the assembled `system` argument is byte-for-byte identical to today's behavior (a regression guard for every existing, non-diagram chat caller — e.g. the Capabilities page). Confirm both fail (`run_turn` doesn't accept the parameter yet).
- [x] T003 In `src/adp/chat/models.py`: add `diagram_context: str | None = None` to `SendMessageRequest` (keeps `extra="forbid"` — purely additive).
- [x] T004 In `src/adp/chat/router.py`'s `send_message`: pass `body.diagram_context` through to `orchestrator.run_turn(...)`.
- [x] T005 In `src/adp/chat/orchestrator.py`: add `diagram_context: str | None = None` to `run_turn`'s signature; define a fixed instruction constant (e.g. `_DIAGRAM_EDIT_INSTRUCTIONS`) telling the assistant to respond to an edit request with the complete updated DSL in a single fenced code block, nothing else DSL-shaped outside it (research.md Decision 3); when `diagram_context` is present, append both it and `_DIAGRAM_EDIT_INSTRUCTIONS` to `system_prompt` after the existing `context_block`. Run T002 and confirm both cases now pass.
- [x] T006 Run `pytest tests/unit/chat/ -q` — confirm all green, zero regressions in `test_orchestrator.py`'s pre-existing cases or any other chat test file.

### Frontend: `diagramContext`/`onComplete` reach and leave `sendMessage`

- [x] T007 [P] Create `web/src/api/chat.test.ts` (new file) — failing tests for `useSendMessage`'s `sendMessage`, mocking `global.fetch` to return a minimal SSE-shaped stream: (a) when called with a `diagramContext` argument, the POST body's JSON includes `diagram_context` matching it; (b) when called without one, the POST body has no `diagram_context` key at all (regression guard — existing callers like `ChatPanel`'s current Capabilities-page usage must be byte-for-byte unaffected); (c) when called with an `onComplete` callback and the stream completes successfully (only `text_delta` events, no `error`), `onComplete` is invoked exactly once with the full accumulated text; (d) when the stream includes an `error` event, `onComplete` is NOT invoked. Confirm all fail (neither parameter exists yet).
- [x] T008 In `web/src/api/chat.ts`'s `sendMessage`: add optional `diagramContext?: string` and `onComplete?: (fullText: string) => void` parameters; include `diagram_context` in the POST body only when `diagramContext` is provided (`JSON.stringify(diagramContext ? { content, diagram_context: diagramContext } : { content })`); accumulate a local `let fullText = ""` alongside the existing `setStreamedText` functional update on each `text_delta` event; track whether an `error` event or thrown (non-abort) exception occurred; in the `finally` block, call `onComplete?.(fullText)` only when no error/exception occurred. Run T007 and confirm all 4 cases pass.
- [x] T009 Run `cd web && npx vitest run src/api/chat.test.ts` — confirm green.
- [x] T010 Run `cd web && npx tsc --noEmit && npm run test:run` — confirm clean/green, zero regressions from the foundational changes alone (nothing yet consumes the new parameters, so existing behavior must be completely unaffected).

**Checkpoint**: `diagram_context` can reach the system prompt from a raw `sendMessage` call, and a completed reply can be reported back via `onComplete` — both proven in isolation, independent of either user story's UI existing yet.

---

## Phase 3: User Story 1 - Ask the assistant about the diagram I'm looking at (Priority: P1) 🎯 MVP

**Goal**: The chat assistant, embedded in the diagram editor, answers questions grounded in the diagram's actual current (possibly unsaved) content.

**Independent Test**: Render `ChatPanel` with a `getDiagramContext` prop and confirm `sendMessage` is called with that getter's freshly-invoked value; render `DiagramEditorPage` (mocking `ChatButton`/`ChatPanel`) and confirm the `getDiagramContext` function it passes down returns a string reflecting the current title/type/DSL state.

### Tests for User Story 1 (MANDATORY — ART-IV)

- [x] T011 [P] [US1] Create `web/src/chat/ChatPanel.test.tsx` (new file) — `vi.mock("../api/chat")`; failing test cases: (a) `ChatPanel` accepts an optional `getDiagramContext?: () => string | undefined` prop; (b) when the user sends a message, `sendMessage` is called with that getter's *current* return value as its third argument — verified by mocking `getDiagramContext` to return different strings across two separate sends and asserting each call captured the value current *at send time*, not a stale one (guards against the exact stale-closure bug class `useSendMessage`'s own doc comment already warns about); (c) when no `getDiagramContext` prop is given, `sendMessage` is called with `undefined` as that argument (matches today's Capabilities-page usage, unaffected). Confirm all fail (the prop doesn't exist yet).
- [x] T012 [P] [US1] Extend `web/src/diagrams/DiagramEditorPage.test.tsx` — `vi.mock("../chat/ChatButton")` and `vi.mock("../chat/ChatPanel")` (lightweight mocks capturing their props); failing test case: `DiagramEditorPage` renders a `ChatButton`/`ChatPanel`, and the `getDiagramContext` function passed to the mocked `ChatPanel`, when invoked, returns a string containing the current title, the diagram type, and the current DSL content (assert via `.toContain(...)` on each). Confirm this fails (`DiagramEditorPage` doesn't embed chat yet).

### Implementation for User Story 1

- [x] T013 [US1] In `web/src/chat/ChatPanel.tsx`: add `getDiagramContext?: () => string | undefined` to `Props`; in `handleSend()`, change `await sendMessage(targetId, text);` to `await sendMessage(targetId, text, getDiagramContext?.());`. Run T011 and confirm all 3 cases pass.
- [x] T014 [US1] In `web/src/diagrams/DiagramEditorPage.tsx`: import and embed `ChatButton`/`ChatPanel` (mirrors `CapabilityTree.tsx`'s `showChat`/toggle pattern — a new local `showChat` state), passing `getDiagramContext={() => \`Diagram title: ${title}\nDiagram type: ${diagramType}\n\nCurrent DSL:\n${dsl}\`}`. Run T012 and confirm it passes.
- [x] T015 [US1] Run `cd web && npx vitest run src/chat/ChatPanel.test.tsx src/diagrams/DiagramEditorPage.test.tsx && npx tsc --noEmit` — confirm all green, zero regressions.

**Checkpoint**: User Story 1 fully functional and independently testable — the assistant can be asked about the currently-open diagram's real content. Shippable MVP increment on its own.

---

## Phase 4: User Story 2 - Ask the assistant to make an edit, and review it before saving (Priority: P2)

**Goal**: A proposed edit (a fenced DSL block in the assistant's reply) is applied to the live, reviewable editor state; manual editing is locked while a request is in flight (Clarifications, FR-011).

**Independent Test**: Call `extractProposedDsl()` directly against fixture response text and assert extraction/fallback/null-when-absent behavior; render `DiagramEditorPage` (mocking `ChatPanel`) and invoke its `onAssistantReply`/`onStreamingChange` props directly to assert the DSL panel updates and Canvas/DslPanel interactivity toggles accordingly.

### Tests for User Story 2 (MANDATORY — ART-IV)

- [x] T016 [P] [US2] Create `web/src/diagrams/editor/extractProposedDsl.test.ts` (new file) — failing tests for `extractProposedDsl(responseText, diagramType)`: a fenced block whose info-string matches `diagramType` (e.g. ` ```flowchart ... ``` ` for `"flowchart"`) is extracted, trimmed; a fenced block with no info-string is extracted as a fallback when no type-matching block exists; plain conversational text with no fenced block returns `null`; multiple fenced blocks — the first one is used (a documented, deterministic choice, not an error). Confirm the test run fails (the module doesn't exist yet).
- [x] T017 [P] [US2] Extend `web/src/chat/ChatPanel.test.tsx` — failing test cases: (a) `ChatPanel` accepts optional `onAssistantReply?: (text: string) => void` and `onStreamingChange?: (isStreaming: boolean) => void` props; (b) `onStreamingChange` is called with `true` when a send begins and `false` once it completes (success or error alike — this is about editor lockout timing, not success/failure); (c) `onAssistantReply` is invoked with the completed response text after a successful send (wired through `sendMessage`'s new `onComplete` from T008/T013), and is NOT invoked when the send errors (matches `onComplete`'s own already-tested error-suppression from T007). Confirm all fail.
- [x] T018 [US2] Extend `web/src/diagrams/DiagramEditorPage.test.tsx` — failing test cases: (a) invoking the mocked `ChatPanel`'s `onAssistantReply` prop with text containing a fenced DSL block matching the diagram's type causes the DSL panel's textarea value to update to the extracted content; (b) invoking it with plain conversational text (no fenced block) leaves the DSL panel unchanged. Depends on `ChatPanel`'s mock supporting `onAssistantReply` (T017's test shape) — write after T017. Confirm both fail.
- [x] T019 [US2] Extend `web/src/diagrams/DiagramEditorPage.test.tsx` — failing test cases: invoking the mocked `ChatPanel`'s `onStreamingChange(true)` makes the Canvas/DSL panel non-interactive (assert via a `disabled`/`aria-disabled` attribute or equivalent on the DSL panel's textarea, matching whatever concrete mechanism T023 implements); `onStreamingChange(false)` re-enables them. Confirm both fail.

### Implementation for User Story 2

- [x] T020 [US2] Create `web/src/diagrams/editor/extractProposedDsl.ts` (new file) — implements the extraction/fallback/null/first-of-multiple behavior per T016. Run T016 and confirm it passes.
- [x] T021 [US2] In `web/src/chat/ChatPanel.tsx`: add `onAssistantReply?: (text: string) => void` and `onStreamingChange?: (isStreaming: boolean) => void` to `Props`; pass `onComplete={onAssistantReply}` into the `sendMessage(...)` call in `handleSend()`; add a `useEffect` watching `isStreaming` that calls `onStreamingChange?.(isStreaming)` on change. Run T017 and confirm it passes.
- [x] T022 [US2] In `web/src/diagrams/DiagramEditorPage.tsx`: pass an `onAssistantReply` handler to `ChatPanel` that calls `extractProposedDsl(text, diagramType)` (T020) and, when non-null, calls the existing `applyDsl(extracted)`. Run T018 and confirm it passes.
- [x] T023 [US2] In `web/src/diagrams/DiagramEditorPage.tsx`: add a local `chatBusy` state, updated via an `onStreamingChange` handler passed to `ChatPanel`; disable the Canvas/DslPanel's interactivity while `chatBusy` is true (concrete mechanism: whatever minimal prop/attribute change achieves non-interactivity on those two components — e.g. a `readOnly`/`disabled` passthrough — chosen to match T019's assertion). Run T019 and confirm it passes.
- [x] T024 [US2] Run `cd web && npx vitest run src/diagrams/editor/extractProposedDsl.test.ts src/chat/ChatPanel.test.tsx src/diagrams/DiagramEditorPage.test.tsx && npx tsc --noEmit` — confirm all green, zero regressions.

**Checkpoint**: Both user stories independently functional — an architect can ask about a diagram (US1) and ask for an edit that appears in reviewable state with manual editing safely locked out during the request (US2).

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Documentation (ART-XVI) and full-suite regression confirmation, backend and frontend.

- [x] T025 [P] Add a short note to `web/src/diagrams/README.md` on the AI-assistant integration (mirrors the `persona.ts`/`generators.ts` notes already there): the `getDiagramContext`/`onAssistantReply`/`onStreamingChange` props, the fenced-DSL-block convention, and that nothing is ever auto-saved. Add a matching note to `src/adp/chat/orchestrator.py`'s module docstring on the `diagram_context` parameter, mirroring `tools.py`'s existing documentation density.
- [x] T026 Run `pytest tests/ --ignore=tests/integration -q`, `ruff check src/`, `mypy src/` — confirm all clean, zero regressions across the whole backend, not just `tests/unit/chat/`.
- [x] T027 Run `cd web && npx tsc --noEmit` and `npm run test:run` — confirm clean/green across the whole frontend, not just the touched files.
- [x] T028 Walk through quickstart.md Scenarios 1–4 to confirm end-to-end behavior beyond the unit-test level. No browser-automation tool was available in this session (dev servers up on :5173/:8001, nothing to drive a click-through) — same situation as ADP-914.6/ADP-914.7. Substituted with equivalent automated coverage, not skipped: Scenario 1 (grounded Q&A) ≡ `ChatPanel.test.tsx`'s `getDiagramContext` tests + `DiagramEditorPage.test.tsx`'s context-content test + `test_orchestrator.py`'s `diagram_context`-reaches-system-prompt tests (T002) — the full click→context→prompt chain is unit-tested end to end. Scenario 2 (unsaved content reflected) ≡ confirmed by direct code read that `getDiagramContext()` reads the live `dsl` variable (derived from in-memory `model` state), never a `savedId`-gated fetch — an unsaved diagram's content is structurally the *only* thing it could return. Scenario 3 (edit proposal reviewed before save) ≡ `DiagramEditorPage.test.tsx`'s "applies an extracted fenced DSL block" + "leaves the DSL panel unchanged" tests, combined with the pre-existing (ADP-SPEC-046) Save-flow tests proving nothing persists without an explicit Save click. Scenario 4 (manual-edit lockout) ≡ the streaming-lockout test (T019/T023). Scenario 5 (invalid DSL) is explicitly unit-test-only per its own text. Scenario 6 ≡ T026/T027, just run.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS both user stories. Its backend half (T002–T006) and frontend half (T007–T010) touch entirely disjoint files and can proceed in parallel with each other.
- **User Story 1 (Phase 3)**: Depends on Foundational (needs `sendMessage`'s `diagramContext` parameter to exist, T008). No dependency on User Story 2.
- **User Story 2 (Phase 4)**: Depends on Foundational (needs `sendMessage`'s `onComplete` parameter, T008) **and** on User Story 1's `ChatPanel`/`DiagramEditorPage` embedding already existing (T013/T014) — US2's new props (`onAssistantReply`/`onStreamingChange`) extend the *same* `ChatPanel` instance US1 already wired into `DiagramEditorPage`, not a second one.
- **Polish (Phase 5)**: Depends on both user stories being complete.

### Parallel Opportunities

- T002 (backend Foundational test) and T007 (frontend Foundational test) touch entirely disjoint files — fully parallel.
- Within US2, T016/T020 (`extractProposedDsl` — a pure function, no dependency on `ChatPanel` changes) can be written and implemented fully in parallel with T017/T021 (`ChatPanel`'s new props) — they only converge at T022/T023, which need both.
- T025 (README/docstring) can run alongside T026/T027 once both stories are implemented.

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (Setup) → Phase 2 (Foundational: `diagram_context`/`onComplete` plumbing, backend and frontend).
2. Complete Phase 3 (User Story 1) → grounded Q&A about the open diagram alone is a complete, shippable increment per spec.md.
3. **STOP and VALIDATE**: run T015, confirm quickstart.md Scenarios 1–2 pass.
4. Optionally stop here — User Story 2 is a lower-priority, independent addition that reuses (not replaces) US1's embedding.

### Incremental Delivery

1. Setup + Foundational → `diagram_context`/`onComplete` plumbing proven in isolation.
2. Add User Story 1 → test independently → MVP.
3. Add User Story 2 → test independently → full feature.
4. Polish → documentation + full-suite regression confirmation, backend and frontend.

## Notes

- No `[Story]` label on Setup/Foundational/Polish tasks, per the required task format.
- Every implementation task follows a task confirmed to fail first (ART-IV): T002→T003–T005, T007→T008, T011→T013, T012→T014, T016→T020, T017→T021, T018→T022, T019→T023.
- This feature touches 3 backend files (no new files) and 4 frontend files (2 new: `chat.test.ts`, `ChatPanel.test.tsx`, `extractProposedDsl.ts`+`.test.ts` — 3 new files total; `chat.ts`/`ChatPanel.tsx`/`DiagramEditorPage.tsx` modified) — zero new dependencies, zero migration, despite being the first feature in this line to touch the backend since ADP-SPEC-046.
