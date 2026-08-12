# Quickstart: AI-Assisted Diagram Generation/Editing (ADP-914.8)

Assumes the web dev server and API are running (`cd web && npm run dev`; API with a configured
`ADP_LLM_API_KEY`, matching `adp.chat`'s existing setup) and at least one diagram exists.

## Scenario 1: Ask the assistant about the open diagram (User Story 1)

1. Open an existing diagram with at least 2 named nodes.
2. Open the chat assistant (new button in the diagram editor, mirroring the Capabilities page's).
3. Ask: "what are the steps in this diagram?"
4. Expect: the assistant's answer names the actual nodes present, not invented ones.

## Scenario 2: Unsaved content is reflected (User Story 1, Acceptance Scenario 2)

1. With the diagram from Scenario 1 still open, manually add a new node without saving.
2. Ask the assistant "how many steps does this diagram have now?"
3. Expect: the answer includes the newly-added, unsaved node — not the last-saved count.

## Scenario 3: Request an edit and review it before saving (User Story 2)

1. Ask the assistant: "rename the 'Start' node to 'Begin'."
2. Expect: the Canvas and DSL panel update immediately to reflect the rename, with nothing
   requiring the user to type DSL by hand.
3. Navigate away without clicking Save.
4. Reopen the diagram — expect: it shows its last-saved state, unaffected by the proposed (never
   saved) rename.

## Scenario 4: Manual edits are locked out while a request is in flight (Clarifications, FR-011)

1. Ask the assistant for an edit.
2. While the response is streaming (before it completes), attempt to manually edit a node.
3. Expect: the Canvas/DSL panel do not accept the manual edit until the response completes, then
   editing is available again immediately.

## Scenario 5: Invalid proposed DSL surfaces the existing parse-error display (Edge Case, FR-008)

Not straightforward to trigger deliberately against a real LLM — verified instead via
`extractProposedDsl.test.ts` + `DiagramEditorPage.test.tsx` feeding a deliberately-malformed fenced
block through the same code path and confirming the existing `parseErrors` UI appears, exactly as
it already does for a hand-typed mistake.

## Scenario 6: Automated regression check

```bash
pytest tests/unit/chat/ -q
cd web && npx vitest run src/diagrams/editor/extractProposedDsl.test.ts src/diagrams/DiagramEditorPage.test.tsx
npm run test:run
# Expect: all green, zero regressions.
```
