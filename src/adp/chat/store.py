"""AI Chat Assistant store — async SQLAlchemy CRUD (ADP-SPEC-041).

Persists conversations and messages via migration 022. All functions accept
an AsyncSession and are called from the router inside
`async with session_factory() as session: ...` blocks, mirroring every
other domain store in this codebase (adp.business.store,
adp.application.store).

FR-009: every read function here is actor-scoped by construction -- there
is no "get any conversation" function, only "get this actor's conversation",
so a cross-user access bug can't be introduced by a caller forgetting to
filter.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from adp.chat.models import (
    ChatCitation,
    ChatConversationDetail,
    ChatConversationSummary,
    ChatMessage,
    ChatRole,
)

_DEFAULT_TITLE = "New conversation"

_metadata = sa.MetaData()

_conversations = sa.Table(
    "chat_conversations",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("actor", sa.String(255), nullable=False),
    sa.Column("title", sa.String(255), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

_messages = sa.Table(
    "chat_messages",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("conversation_id", sa.String(36), nullable=False),
    sa.Column("role", sa.Text(), nullable=False),
    sa.Column("content", sa.Text(), nullable=False),
    sa.Column("citations", sa.JSON(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)


# ── Module-level session factory (set by deps or tests) ──────────────────────

_engine: Any = None
_session_factory: Any = None


def _get_session_factory() -> async_sessionmaker:
    global _engine, _session_factory
    if _session_factory is None:
        db_url = os.environ.get(
            "ADP_DATABASE_URL", "postgresql+asyncpg://adp_user:adp_pass@127.0.0.1:5432/adp"
        )
        _engine = create_async_engine(db_url, echo=False)
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _session_factory


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _row_to_message(row: Any) -> ChatMessage:
    return ChatMessage(
        id=row.id,
        conversation_id=row.conversation_id,
        role=ChatRole(row.role),
        content=row.content,
        citations=[ChatCitation.model_validate(c) for c in (row.citations or [])],
        created_at=row.created_at,
    )


def _row_to_summary(row: Any) -> ChatConversationSummary:
    return ChatConversationSummary(
        id=row.id, title=row.title, created_at=row.created_at, updated_at=row.updated_at,
    )


async def create_conversation(
    actor: str, session: AsyncSession, *, title: str = _DEFAULT_TITLE
) -> ChatConversationSummary:
    conv_id = str(uuid.uuid4())
    now = _now()
    await session.execute(
        _conversations.insert().values(
            id=conv_id, actor=actor, title=title, created_at=now, updated_at=now,
        )
    )
    return ChatConversationSummary(id=conv_id, title=title, created_at=now, updated_at=now)


async def append_message(
    conversation_id: str,
    role: ChatRole,
    content: str,
    session: AsyncSession,
    *,
    citations: list[ChatCitation] | None = None,
) -> ChatMessage:
    """Append a message and bump the conversation's updated_at. Does not
    itself check actor ownership -- callers that accept a caller-supplied
    conversation_id (the router) MUST call get_conversation first (FR-009)."""
    msg_id = str(uuid.uuid4())
    now = _now()
    citations = citations or []
    await session.execute(
        _messages.insert().values(
            id=msg_id,
            conversation_id=conversation_id,
            role=role.value,
            content=content,
            citations=[c.model_dump(mode="json") for c in citations],
            created_at=now,
        )
    )
    await session.execute(
        _conversations.update()
        .where(_conversations.c.id == conversation_id)
        .values(updated_at=now)
    )
    return ChatMessage(
        id=msg_id, conversation_id=conversation_id, role=role, content=content,
        citations=citations, created_at=now,
    )


async def set_title_if_default(title: str, conversation_id: str, session: AsyncSession) -> None:
    """Sets the conversation's title only if it's still the default
    placeholder -- called by the orchestrator after a conversation's first
    message, not a general-purpose rename endpoint. Idempotent: a second
    call (e.g. a retried request) is a no-op once the title has changed."""
    await session.execute(
        _conversations.update()
        .where(_conversations.c.id == conversation_id, _conversations.c.title == _DEFAULT_TITLE)
        .values(title=title[:255], updated_at=_now())
    )


async def get_conversation(
    conversation_id: str, actor: str, session: AsyncSession
) -> ChatConversationDetail | None:
    """Actor-scoped: returns None for a conversation that doesn't exist *or*
    isn't owned by this actor -- the two cases are never distinguished
    (SC-003), so a caller can't tell which one occurred from this alone."""
    result = await session.execute(
        sa.select(_conversations).where(
            _conversations.c.id == conversation_id, _conversations.c.actor == actor
        )
    )
    row = result.mappings().first()
    if row is None:
        return None

    msgs_result = await session.execute(
        sa.select(_messages)
        .where(_messages.c.conversation_id == conversation_id)
        .order_by(_messages.c.created_at)
    )
    messages = [_row_to_message(m) for m in msgs_result.mappings().all()]

    return ChatConversationDetail(
        id=row["id"], title=row["title"], created_at=row["created_at"],
        updated_at=row["updated_at"], messages=messages,
    )


async def list_conversations(actor: str, session: AsyncSession) -> list[ChatConversationSummary]:
    """Actor-scoped listing (FR-009) -- there is no unscoped variant."""
    result = await session.execute(
        sa.select(_conversations)
        .where(_conversations.c.actor == actor)
        .order_by(_conversations.c.updated_at.desc())
    )
    return [_row_to_summary(row) for row in result.mappings().all()]
