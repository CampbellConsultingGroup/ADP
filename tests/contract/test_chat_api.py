"""Contract tests for the AI Chat Assistant API (ADP-SPEC-041 US1).

Full-stack against the real chat/business/application stores on in-memory
SQLite (mirrors test_capability_agent_review_api.py's approach), with
retrieval mocked at the call site since adp.search's hybrid_search requires a
real pgvector-backed Postgres session SQLite cannot provide at all. Auth is
disabled in tests, so the caller is ENTERPRISE_ARCHITECT (all actions);
authz denial is covered in tests/authz/test_enforcement.py.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.application import store as astore
from adp.business import store as bstore
from adp.chat import router as crouter
from adp.chat import store as chat_store


class _FakeLLMClient:
    """Yields a fixed event sequence, ignoring the actual request content."""

    def __init__(self, events: list[dict]):
        self._events = events

    async def chat_stream(self, *, messages, system, tools=None, correlation_id=None):
        for event in self._events:
            yield event


class _FailingLLMClient:
    async def chat_stream(self, *, messages, system, tools=None, correlation_id=None):
        raise RuntimeError("LLM provider timed out")
        yield  # pragma: no cover -- unreachable, makes this an async generator


def _text_events(*texts: str, prompt_tokens=1, completion_tokens=1) -> list[dict]:
    events = [{"type": "text_delta", "text": t} for t in texts]
    events.append({
        "type": "done", "stop_reason": "end_turn",
        "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
    })
    return events


def _parse_sse(text: str) -> list[dict]:
    return [
        json.loads(line[len("data:"):].strip())
        for line in text.splitlines()
        if line.startswith("data:")
    ]


def _mock_retrieval():
    return patch("adp.chat.retrieval.retrieve_context", new=AsyncMock(return_value=[]))


@pytest.fixture()
async def app_and_stores(tmp_path):
    chat_engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/chat.db")
    async with chat_engine.begin() as conn:
        await conn.run_sync(chat_store._metadata.create_all)
    biz_engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/biz.db")
    async with biz_engine.begin() as conn:
        await conn.run_sync(bstore._metadata.create_all)
    app_engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/app.db")
    async with app_engine.begin() as conn:
        await conn.run_sync(astore._metadata.create_all)

    chat_factory = async_sessionmaker(chat_engine, expire_on_commit=False)
    biz_factory = async_sessionmaker(biz_engine, expire_on_commit=False)
    app_factory = async_sessionmaker(app_engine, expire_on_commit=False)

    from adp.api.app import create_app

    app = create_app()

    async def _override_chat_session():
        async with chat_factory() as session:
            yield session

    app.dependency_overrides[crouter._get_chat_session] = _override_chat_session
    app.dependency_overrides[crouter._get_chat_session_factory] = lambda: chat_factory
    app.dependency_overrides[crouter._get_biz_session_factory] = lambda: biz_factory
    app.dependency_overrides[crouter._get_application_session_factory] = lambda: app_factory

    client = TestClient(app, raise_server_exceptions=False)
    yield client, chat_factory, biz_factory
    await chat_engine.dispose()
    await biz_engine.dispose()
    await app_engine.dispose()


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


async def test_create_send_stream_and_ground_citation(app_and_stores):
    client, _, biz_factory = app_and_stores
    await _mk_capability(biz_factory, "CAP-1")

    create_resp = client.post("/api/v1/chat/conversations")
    assert create_resp.status_code == 201, create_resp.text
    conv_id = create_resp.json()["id"]

    llm = _FakeLLMClient(_text_events(
        "The Merchandising capability [business_capability:CAP-1] is unclassified."
    ))
    with _mock_retrieval(), patch("adp.chat.router._make_chat_llm_client", return_value=llm):
        resp = client.post(
            f"/api/v1/chat/conversations/{conv_id}/messages",
            json={"content": "Tell me about Merchandising"},
        )
    assert resp.status_code == 200, resp.text
    events = _parse_sse(resp.text)
    assert any(e["type"] == "text_delta" for e in events)
    done = events[-1]
    assert done["type"] == "done"
    assert done["citations"] == [
        {"entity_type": "business_capability", "entity_id": "CAP-1", "verified": True}
    ]

    detail = client.get(f"/api/v1/chat/conversations/{conv_id}").json()
    assert detail["title"] == "Tell me about Merchandising"
    assert len(detail["messages"]) == 2
    assert "[business_capability:CAP-1]" not in detail["messages"][-1]["content"]


async def test_unresolvable_citation_marked_unverified(app_and_stores):
    client, _, _ = app_and_stores
    conv_id = client.post("/api/v1/chat/conversations").json()["id"]

    llm = _FakeLLMClient(_text_events("This relates to [business_capability:CAP-99-invented]."))
    with _mock_retrieval(), patch("adp.chat.router._make_chat_llm_client", return_value=llm):
        resp = client.post(
            f"/api/v1/chat/conversations/{conv_id}/messages", json={"content": "hi"}
        )
    events = _parse_sse(resp.text)
    assert events[-1]["citations"][0]["verified"] is False


async def test_llm_failure_emits_error_event_and_conversation_stays_resumable(app_and_stores):
    client, _, _ = app_and_stores
    conv_id = client.post("/api/v1/chat/conversations").json()["id"]

    with _mock_retrieval(), patch(
        "adp.chat.router._make_chat_llm_client", return_value=_FailingLLMClient()
    ):
        resp = client.post(
            f"/api/v1/chat/conversations/{conv_id}/messages", json={"content": "hi"}
        )
    assert resp.status_code == 200, resp.text
    events = _parse_sse(resp.text)
    assert events[-1]["type"] == "error"
    assert "LLM provider timed out" in events[-1]["detail"]

    # The conversation remains resumable -- the user's message persisted, and
    # a follow-up send still works normally.
    detail = client.get(f"/api/v1/chat/conversations/{conv_id}").json()
    assert len(detail["messages"]) == 1
    assert detail["messages"][0]["role"] == "user"

    llm2 = _FakeLLMClient(_text_events("Hello again."))
    with _mock_retrieval(), patch("adp.chat.router._make_chat_llm_client", return_value=llm2):
        resp2 = client.post(
            f"/api/v1/chat/conversations/{conv_id}/messages", json={"content": "hi again"}
        )
    assert resp2.status_code == 200, resp2.text
    assert _parse_sse(resp2.text)[-1]["type"] == "done"


def test_send_message_to_unknown_conversation_returns_404(app_and_stores):
    client, _, _ = app_and_stores
    resp = client.post("/api/v1/chat/conversations/nope/messages", json={"content": "hi"})
    assert resp.status_code == 404


def test_send_message_rejects_blank_content(app_and_stores):
    client, _, _ = app_and_stores
    conv_id = client.post("/api/v1/chat/conversations").json()["id"]
    resp = client.post(
        f"/api/v1/chat/conversations/{conv_id}/messages", json={"content": "   "}
    )
    assert resp.status_code == 422
