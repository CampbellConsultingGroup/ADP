"""Unit tests: adp.chat.store CRUD, actor-scoping (ADP-SPEC-041 FR-009)."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.chat import store as chat_store
from adp.chat.models import ChatCitation, ChatRole


@pytest.fixture()
async def session_factory(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/chat.db")
    async with engine.begin() as conn:
        await conn.run_sync(chat_store._metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


async def test_create_conversation_and_append_message(session_factory):
    async with session_factory() as session:
        conv = await chat_store.create_conversation("alice", session, title="Q&A")
        msg = await chat_store.append_message(
            conv.id, ChatRole.USER, "Which capabilities are unclassified?", session,
        )
        await session.commit()

    assert msg.role == ChatRole.USER
    assert msg.content == "Which capabilities are unclassified?"

    async with session_factory() as session:
        detail = await chat_store.get_conversation(conv.id, "alice", session)

    assert detail is not None
    assert len(detail.messages) == 1
    assert detail.messages[0].content == msg.content


async def test_append_message_stores_citations(session_factory):
    async with session_factory() as session:
        conv = await chat_store.create_conversation("alice", session)
        await chat_store.append_message(
            conv.id, ChatRole.ASSISTANT, "The Merchandising capability...", session,
            citations=[
                ChatCitation(entity_type="business_capability", entity_id="CAP-1", verified=True)
            ],
        )
        await session.commit()

    async with session_factory() as session:
        detail = await chat_store.get_conversation(conv.id, "alice", session)

    assert detail is not None
    assert detail.messages[0].citations == [
        ChatCitation(entity_type="business_capability", entity_id="CAP-1", verified=True)
    ]


async def test_get_conversation_returns_none_for_wrong_actor(session_factory):
    async with session_factory() as session:
        conv = await chat_store.create_conversation("alice", session)
        await session.commit()

    async with session_factory() as session:
        detail = await chat_store.get_conversation(conv.id, "bob", session)

    assert detail is None


async def test_get_conversation_returns_none_for_unknown_id(session_factory):
    async with session_factory() as session:
        detail = await chat_store.get_conversation("nope", "alice", session)
    assert detail is None


async def test_list_conversations_scoped_to_actor(session_factory):
    async with session_factory() as session:
        await chat_store.create_conversation("alice", session, title="Alice's chat")
        await chat_store.create_conversation("bob", session, title="Bob's chat")
        await session.commit()

    async with session_factory() as session:
        alice_convs = await chat_store.list_conversations("alice", session)
        bob_convs = await chat_store.list_conversations("bob", session)

    assert [c.title for c in alice_convs] == ["Alice's chat"]
    assert [c.title for c in bob_convs] == ["Bob's chat"]


async def test_append_message_bumps_conversation_updated_at(session_factory):
    async with session_factory() as session:
        conv = await chat_store.create_conversation("alice", session)
        await session.commit()

    async with session_factory() as session:
        await chat_store.append_message(conv.id, ChatRole.USER, "hi", session)
        await session.commit()

    async with session_factory() as session:
        detail = await chat_store.get_conversation(conv.id, "alice", session)

    # SQLite doesn't round-trip tz-awareness on DateTime(timezone=True); compare
    # naive to sidestep that driver quirk rather than the store's own logic.
    assert detail is not None
    assert detail.updated_at.replace(tzinfo=None) >= conv.updated_at.replace(tzinfo=None)
