"""Unit tests: adp.chat.orchestrator.run_turn grounding behavior (ADP-SPEC-041 US1).

Retrieval (adp.search.hybrid_search) requires a real pgvector-backed
Postgres session that SQLite cannot provide at all, so it's mocked at the
call site here rather than exercised against a fake index -- consistent
with how the contract tests for this feature will need to do the same.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.authz.roles import PersonaRole
from adp.business import store as bstore
from adp.chat import orchestrator
from adp.chat import store as chat_store
from adp.chat.models import ChatMessage, ChatRole


class _FakeLLMClient:
    """Yields a fixed event sequence, ignoring the actual request content."""

    def __init__(self, events: list[dict]):
        self._events = events

    async def chat_stream(self, *, messages, system, tools=None, correlation_id=None):
        for event in self._events:
            yield event


def _text_events(*texts: str, prompt_tokens=1, completion_tokens=1) -> list[dict]:
    events = [{"type": "text_delta", "text": t} for t in texts]
    events.append({
        "type": "done", "stop_reason": "end_turn",
        "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
    })
    return events


@pytest.fixture()
async def sessions(tmp_path):
    chat_engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/chat.db")
    async with chat_engine.begin() as conn:
        await conn.run_sync(chat_store._metadata.create_all)
    biz_engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/biz.db")
    async with biz_engine.begin() as conn:
        await conn.run_sync(bstore._metadata.create_all)

    chat_factory = async_sessionmaker(chat_engine, expire_on_commit=False)
    biz_factory = async_sessionmaker(biz_engine, expire_on_commit=False)
    yield chat_factory, biz_factory
    await chat_engine.dispose()
    await biz_engine.dispose()


async def _mk_capability(biz_factory, cap_id: str, name: str = "Merchandising") -> None:
    now = datetime.now(timezone.utc)
    async with biz_factory() as session:
        await session.execute(
            bstore._capabilities.insert().values(
                id=cap_id, name=name, description=None, level=1, parent_id=None,
                position=0, created_at=now, updated_at=now,
            )
        )
        await session.commit()


async def test_run_turn_marks_resolved_citation_verified(sessions):
    chat_factory, biz_factory = sessions
    await _mk_capability(biz_factory, "CAP-1")

    async with chat_factory() as chat_session:
        conv = await chat_store.create_conversation("alice", chat_session)
        await chat_session.commit()

    llm = _FakeLLMClient(_text_events(
        "The Merchandising capability [business_capability:CAP-1] is unclassified."
    ))

    events = []
    with patch("adp.chat.retrieval.retrieve_context", new=AsyncMock(return_value=[])):
        async with chat_factory() as chat_session, biz_factory() as biz_session:
            async for event in orchestrator.run_turn(
                conversation_id=conv.id, history=[], user_content="Tell me about Merchandising",
                chat_session=chat_session, biz_session=biz_session, app_session=biz_session,
                kb_session=biz_session, role=PersonaRole.ENTERPRISE_ARCHITECT,
                llm_client=llm,
            ):
                events.append(event)

    done = events[-1]
    assert done["type"] == "done"
    assert done["citations"] == [
        {"entity_type": "business_capability", "entity_id": "CAP-1", "verified": True}
    ]

    async with chat_factory() as chat_session:
        detail = await chat_store.get_conversation(conv.id, "alice", chat_session)
    assert detail is not None
    assistant_msg = detail.messages[-1]
    assert "[business_capability:CAP-1]" not in assistant_msg.content
    assert assistant_msg.citations[0].verified is True


async def test_run_turn_marks_unresolved_citation_unverified(sessions):
    chat_factory, biz_factory = sessions

    async with chat_factory() as chat_session:
        conv = await chat_store.create_conversation("alice", chat_session)
        await chat_session.commit()

    llm = _FakeLLMClient(_text_events(
        "This relates to [business_capability:CAP-99-invented]."
    ))

    events = []
    with patch("adp.chat.retrieval.retrieve_context", new=AsyncMock(return_value=[])):
        async with chat_factory() as chat_session, biz_factory() as biz_session:
            async for event in orchestrator.run_turn(
                conversation_id=conv.id, history=[], user_content="hi",
                chat_session=chat_session, biz_session=biz_session, app_session=biz_session,
                kb_session=biz_session, role=PersonaRole.ENTERPRISE_ARCHITECT,
                llm_client=llm,
            ):
                events.append(event)

    done = events[-1]
    assert done["citations"][0]["verified"] is False


async def test_run_turn_sets_title_from_first_message(sessions):
    chat_factory, biz_factory = sessions

    async with chat_factory() as chat_session:
        conv = await chat_store.create_conversation("alice", chat_session)
        await chat_session.commit()

    llm = _FakeLLMClient(_text_events("Hi there."))

    with patch("adp.chat.retrieval.retrieve_context", new=AsyncMock(return_value=[])):
        async with chat_factory() as chat_session, biz_factory() as biz_session:
            async for _ in orchestrator.run_turn(
                conversation_id=conv.id, history=[],
                user_content="Which capabilities are unclassified?",
                chat_session=chat_session, biz_session=biz_session, app_session=biz_session,
                kb_session=biz_session, role=PersonaRole.ENTERPRISE_ARCHITECT,
                llm_client=llm,
            ):
                pass

    async with chat_factory() as chat_session:
        detail = await chat_store.get_conversation(conv.id, "alice", chat_session)
    assert detail is not None
    assert detail.title == "Which capabilities are unclassified?"


async def test_run_turn_yields_error_event_on_llm_failure(sessions):
    chat_factory, biz_factory = sessions

    async with chat_factory() as chat_session:
        conv = await chat_store.create_conversation("alice", chat_session)
        await chat_session.commit()

    class _FailingLLMClient:
        async def chat_stream(self, *, messages, system, tools=None, correlation_id=None):
            raise RuntimeError("LLM provider timed out")
            yield  # pragma: no cover -- unreachable, makes this an async generator

    events = []
    with patch("adp.chat.retrieval.retrieve_context", new=AsyncMock(return_value=[])):
        async with chat_factory() as chat_session, biz_factory() as biz_session:
            async for event in orchestrator.run_turn(
                conversation_id=conv.id, history=[], user_content="hi",
                chat_session=chat_session, biz_session=biz_session, app_session=biz_session,
                kb_session=biz_session, role=PersonaRole.ENTERPRISE_ARCHITECT,
                llm_client=_FailingLLMClient(),
            ):
                events.append(event)

    assert events[-1]["type"] == "error"
    assert "LLM provider timed out" in events[-1]["detail"]


def _mk_message(n: int) -> ChatMessage:
    role = ChatRole.USER if n % 2 == 0 else ChatRole.ASSISTANT
    return ChatMessage(
        id=f"M-{n}", conversation_id="C-1", role=role, content=f"message {n}",
        citations=[], created_at=datetime.now(timezone.utc),
    )


def test_windowed_history_passes_through_short_history_unchanged():
    history = [_mk_message(n) for n in range(5)]
    assert orchestrator._windowed_history(history) == history


def test_windowed_history_truncates_to_the_most_recent_messages():
    history = [_mk_message(n) for n in range(25)]
    windowed = orchestrator._windowed_history(history)
    assert len(windowed) == orchestrator._CONTEXT_WINDOW_SIZE
    assert [m.content for m in windowed] == [
        f"message {n}" for n in range(25 - orchestrator._CONTEXT_WINDOW_SIZE, 25)
    ]


async def test_run_turn_sends_only_windowed_history_to_the_llm_but_persists_all(sessions):
    """US4/research D8: a conversation far longer than the window still only
    sends the most recent slice to the model, while GET .../conversations/{id}
    (chat_store.get_conversation) continues to return the complete,
    untruncated history regardless of what was sent.

    Persists 25 real prior messages first (not synthetic ChatMessage objects
    passed straight into run_turn) so `history` here is exactly what a
    router's `get_conversation` call would have fetched -- proving the
    persisted-vs-sent distinction end to end, not just windowing in isolation."""
    chat_factory, biz_factory = sessions

    async with chat_factory() as chat_session:
        conv = await chat_store.create_conversation("alice", chat_session)
        for n in range(25):
            role = ChatRole.USER if n % 2 == 0 else ChatRole.ASSISTANT
            await chat_store.append_message(conv.id, role, f"message {n}", chat_session)
        await chat_session.commit()
        detail_before = await chat_store.get_conversation(conv.id, "alice", chat_session)
    assert detail_before is not None
    history = detail_before.messages
    assert len(history) == 25

    class _RecordingLLMClient:
        def __init__(self) -> None:
            self.seen_messages: list[dict] | None = None

        async def chat_stream(self, *, messages, system, tools=None, correlation_id=None):
            self.seen_messages = messages
            for event in _text_events("noted."):
                yield event

    llm = _RecordingLLMClient()
    with patch("adp.chat.retrieval.retrieve_context", new=AsyncMock(return_value=[])):
        async with chat_factory() as chat_session, biz_factory() as biz_session:
            async for _ in orchestrator.run_turn(
                conversation_id=conv.id, history=history, user_content="and now?",
                chat_session=chat_session, biz_session=biz_session, app_session=biz_session,
                kb_session=biz_session, role=PersonaRole.ENTERPRISE_ARCHITECT,
                llm_client=llm,
            ):
                pass

    assert llm.seen_messages is not None
    # window + the new user turn appended by _messages_for_llm
    assert len(llm.seen_messages) == orchestrator._CONTEXT_WINDOW_SIZE + 1
    assert llm.seen_messages[-1] == {"role": "user", "content": "and now?"}

    async with chat_factory() as chat_session:
        detail_after = await chat_store.get_conversation(conv.id, "alice", chat_session)
    assert detail_after is not None
    # the full prior history (25) plus this turn's user+assistant messages
    # (2) -- nothing was ever discarded from what's persisted/shown, only
    # from what was sent to the model.
    assert len(detail_after.messages) == 25 + 2
