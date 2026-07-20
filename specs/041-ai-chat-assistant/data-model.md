# Data Model: AI Chat Assistant (ADP-SPEC-041)

Unlike Agent Review, this feature adds a real migration (research.md D7) — conversations and messages are persisted, ordinary rows, not transient `OperationStore` payloads. This document covers the migration DDL sketch, the Pydantic v2 models (all `model_config = ConfigDict(extra="forbid")`), the tool registry shape, and the authz additions.

## Migration 022: `chat_conversations` + `chat_messages`

```python
# revision = "022", down_revision = "021"

op.create_table(
    "chat_conversations",
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("actor", sa.String(255), nullable=False, index=True),
    sa.Column("title", sa.String(255), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

op.create_table(
    "chat_messages",
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column(
        "conversation_id", sa.String(36),
        sa.ForeignKey("chat_conversations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    ),
    sa.Column("role", sa.Text, nullable=False),          # "user" | "assistant"
    sa.Column("content", sa.Text, nullable=False),
    sa.Column("citations", sa.JSON, nullable=False, server_default="[]"),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)
```

`citations` stores a JSON list of `GroundingCitation`-shaped objects plus a `verified: bool` per entry (research D-none needed beyond reusing the existing model — see below). Ordered by `created_at` within a conversation; no separate `position` column needed since messages are strictly append-only.

## `adp.chat.models`

```python
from adp.agents.models import GroundingCitation  # reused as-is

class ChatRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class ChatCitation(GroundingCitation):
    """A GroundingCitation plus whether it re-verified successfully (FR-006).
    Unlike Agent Review's advisory/accept-block pair, there is no write to
    block here -- an unverified citation is simply flagged inline."""
    verified: bool


class ChatMessage(BaseModel):
    id: str
    conversation_id: str
    role: ChatRole
    content: str
    citations: list[ChatCitation] = []
    created_at: datetime


class ChatConversationSummary(BaseModel):
    """List-response item (FR-009's own-conversations-only listing)."""
    id: str
    title: str
    created_at: datetime
    updated_at: datetime


class ChatConversationDetail(ChatConversationSummary):
    """Full conversation, all messages, oldest first."""
    messages: list[ChatMessage]


class CreateConversationRequest(BaseModel):
    """Optionally seed a new conversation with its first user message so the
    client doesn't need two round trips (create, then send)."""
    initial_message: str | None = None


class SendMessageRequest(BaseModel):
    content: str

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("content must not be blank")
        return v
```

**Streamed reply wire shape** (SSE, `text/event-stream`, one event per line-delimited JSON payload after `data: `):

```text
data: {"type": "text_delta", "text": "The Merchandising"}

data: {"type": "text_delta", "text": " capability has no"}

data: {"type": "done", "message_id": "...", "citations": [{"entity_type": "business_capability", "entity_id": "...", "verified": true}]}
```

A stream that errors mid-turn emits a final `{"type": "error", "detail": "..."}` event instead of `done`; the partial text already sent is what gets persisted (spec Edge Case: stream interrupted mid-reply).

## `adp.chat.tools` — the read-only tool registry (FR-004)

```python
@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str          # sent to the LLM verbatim, so it can decide when to call this
    input_schema: dict         # JSON Schema for the tool's arguments (Anthropic `tools` param shape)
    handler: Callable[..., Awaitable[dict]]   # (args, caller_role, session(s)) -> JSON-safe result


# Illustrative registry (exact set finalized during task breakdown):
TOOL_REGISTRY: list[ToolDefinition] = [
    ToolDefinition(name="get_capability", ...),        # wraps bstore.get_capability
    ToolDefinition(name="get_application", ...),       # wraps astore's non-sensitive application read
    ToolDefinition(name="get_application_risk", ...),  # gated: READ_APPLICATION_RISK (research D5)
    ToolDefinition(name="get_application_cost", ...),  # gated: READ_APPLICATION_COST
    ToolDefinition(name="get_application_governance", ...),  # gated: READ_APPLICATION_GOVERNANCE
    ToolDefinition(name="portfolio_summary", ...),      # wraps the existing /portfolio/summary aggregate
    ToolDefinition(name="governance_status", ...),      # wraps the existing /governance/status aggregate
]
```

**SC-002's automated check** (mirrors ADP-SPEC-039's `test_toolkit_boundary.py`): a test asserts every `handler` in `TOOL_REGISTRY` resolves to a function whose name matches a read-only prefix (`get_`/`list_`/`_summary`/`_status`) and, more strongly, that none of them call an `INSERT`/`UPDATE`/`DELETE`-issuing store function — verified by import/call-graph inspection, not just naming convention, so the guarantee doesn't silently rot if a handler is later edited to call a write function under a read-sounding name.

A gated tool's handler signature includes the caller's `role`; it returns `{"permitted": False}` (not an error, not a silently-empty result — research D5) when `is_permitted(role, ActionType.READ_APPLICATION_*)` fails, so the assistant can say "I don't have access to show you that" rather than treating an empty result as "no data exists."

## Endpoints (`src/adp/chat/router.py`, new)

| Method | Path | Action | Notes |
|---|---|---|---|
| `POST` | `/api/v1/chat/conversations` | `USE_CHAT_ASSISTANT` (new) | creates a conversation (optionally seeded with `initial_message`), returns `ChatConversationSummary` |
| `GET` | `/api/v1/chat/conversations` | (safe method, unenforced) | lists the caller's own conversations only (FR-009) |
| `GET` | `/api/v1/chat/conversations/{id}` | (safe method, unenforced) | full detail incl. all messages; 404 if not found *or not owned by the caller* (never distinguishes the two — avoids confirming another user's conversation id exists) |
| `POST` | `/api/v1/chat/conversations/{id}/messages` | `USE_CHAT_ASSISTANT` (new) | persists the user message, streams the assistant's reply (SSE), then persists the completed assistant message; 409 if a turn is already in flight for this conversation (FR-011) |

## Authz additions (`src/adp/authz`)

```python
# roles.py
class ActionType(StrEnum):
    ...
    USE_CHAT_ASSISTANT = "use_chat_assistant"   # NEW
```

`USE_CHAT_ASSISTANT` is granted broadly (research D6) — every role that can view a page the chat toggle appears on, not restricted to write-capable roles the way `CONFIRM_AGENT_SUGGESTION` is. `PERMISSIONS_VERSION` bumps accordingly. `enforcement.py`'s `_EXPLICIT_ROUTE_ACTIONS` gains the two POST entries in the table above (the two GETs are never enforced). No changes to `READ_APPLICATION_{RISK,COST,GOVERNANCE}` — the tool layer calls `is_permitted()` against these directly (FR-005), it doesn't need a route-level mapping since there's no dedicated route per sensitive category here.
