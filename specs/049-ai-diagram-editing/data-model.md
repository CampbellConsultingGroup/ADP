# Phase 1 Data Model: AI-Assisted Diagram Generation/Editing

No new persisted entity, no database table, no migration (research.md Decision 2). This feature's
only "data model" changes are to two existing, already-typed request/parameter shapes — both
additive, both optional, both backward-compatible with every existing caller.

## `SendMessageRequest` (existing, `src/adp/chat/models.py`) — extended

```python
class SendMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str
    diagram_context: str | None = None   # NEW
```

`diagram_context`, when present, is a plain-text block assembled by the frontend:

```text
Diagram title: <title>
Diagram type: <flowchart|sequence|erd|uml|architecture>

Current DSL:
<the diagram's current dsl_source text, or the live unsaved DSL if editing a
 not-yet-saved diagram>
```

**Validation rules**: None beyond the existing `content_must_not_be_blank` validator (unchanged).
`diagram_context` has no length cap of its own beyond the diagram's own existing `dsl_source` size
cap (50,000 chars, ADP-SPEC-046) that produced it — no new limit needs enforcing here.

**Not persisted**: `chat_store.append_message` continues to store only `content` (research.md
Decision 2) — `diagram_context` is consumed by `run_turn` for that turn's system-prompt assembly
and discarded afterward, exactly like `context_block`'s hybrid-search hits already are today.

## `run_turn` (existing, `src/adp/chat/orchestrator.py`) — extended signature

```python
async def run_turn(
    *,
    conversation_id: str,
    history: list[ChatMessage],
    user_content: str,
    diagram_context: str | None = None,   # NEW
    chat_session: AsyncSession,
    biz_session: AsyncSession,
    app_session: AsyncSession,
    kb_session: AsyncSession,
    role: PersonaRole,
    llm_client: Any,
) -> AsyncIterator[dict[str, Any]]:
```

When `diagram_context` is not `None`, it is appended to `system_prompt` (after the existing
`context_block`) alongside a fixed instruction block telling the assistant how to respond to an
edit request (research.md Decision 3) — both additions are unconditional text concatenation, not a
new prompt-registry key (spec.md's existing `effective_prompt` lookup, ADP-SPEC-042, is untouched).

## `extractProposedDsl` (new, `web/src/diagrams/editor/extractProposedDsl.ts`)

```ts
function extractProposedDsl(responseText: string, diagramType: DiagramType): string | null
```

A pure function: looks for a single fenced code block in `responseText` whose info-string matches
`diagramType` (or, as a fallback, any fenced block if the assistant omits the info-string — a
reasonable-default tolerance, not a hard requirement on the model's output format) and returns its
contents, trimmed. Returns `null` when no such block is found (a plain conversational answer, per
spec.md's Edge Cases — "the assistant may respond conversationally without proposing any edit at
all").

**Validation rules**: None of its own — the extracted text is handed to the *existing* `applyDsl()`
unchanged, which already surfaces parse errors for invalid content (FR-008, unchanged behavior).

**Relationships**: None to any persisted entity. Purely a text-transform between two ephemeral
values: an LLM's streamed response and the diagram editor's own already-existing `dsl` state.
