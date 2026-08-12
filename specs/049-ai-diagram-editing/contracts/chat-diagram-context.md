# Contract: `POST /api/v1/chat/conversations/{conversation_id}/messages` — `diagram_context`

The only API surface change in this feature: one new, optional, additive field on the existing
send-message endpoint (ADP-SPEC-041). No new endpoint, no breaking change to the existing
Capabilities-page chat flow, which simply never sends this field.

## Request body (extends existing `SendMessageRequest`)

```json
{
  "content": "add a decision step after Review that branches to Approve or Reject",
  "diagram_context": "Diagram title: Quote to Bind\nDiagram type: flowchart\n\nCurrent DSL:\nflowchart LR\n  Start((Start)) --> Review[Review]\n  Review --> Bind[Bind]\n"
}
```

- `content` (string, required, unchanged): the user's message text.
- `diagram_context` (string, optional, **new**): present only when the chat panel is embedded in
  the diagram editor (`DiagramEditorPage.tsx`) and a diagram is open. Built by the frontend from
  the diagram's own live state (title, type, current DSL — saved or not), assembled fresh
  immediately before each send (never a stale, closed-over value — research.md Decision 4's
  stale-closure caution). Absent entirely for every other existing chat embedding (e.g., the
  Capabilities page) — no caller there needs to change.

## Response (unchanged)

Still an SSE stream of `{"type": "text_delta", "text": "..."}` / `{"type": "error", "detail":
"..."}` events, identical to today. No new event type — the fenced-DSL-block convention
(research.md Decision 3) is a plain-text pattern within the existing `text_delta` stream, not a new
protocol element. The frontend detects it client-side only after the stream completes.

## Backward compatibility

- Omitting `diagram_context` entirely (every existing caller) behaves identically to today —
  `run_turn`'s new parameter defaults to `None`, and the system prompt is assembled exactly as it
  already is.
- `SendMessageRequest` keeps `extra="forbid"` — no other new fields are silently accepted.
