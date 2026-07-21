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
from adp.auth.deps import get_current_user
from adp.auth.models import AuthenticatedUser
from adp.authz.roles import PersonaRole
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


class _ToolCallingLLMClient:
    """First chat_stream() call requests one tool; the second call replies
    with the requested text (ignoring the tool result -- used where the
    test only needs the model to have *cited* something, T025's first
    scenario)."""

    def __init__(self, tool_name: str, tool_input: dict, *reply_texts: str):
        self._tool_name = tool_name
        self._tool_input = tool_input
        self._reply_texts = reply_texts
        self._call_count = 0

    async def chat_stream(self, *, messages, system, tools=None, correlation_id=None):
        self._call_count += 1
        if self._call_count == 1:
            yield {
                "type": "tool_use", "id": "tool-1",
                "name": self._tool_name, "input": self._tool_input,
            }
            yield {
                "type": "done", "stop_reason": "tool_use",
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            }
        else:
            for text in self._reply_texts:
                yield {"type": "text_delta", "text": text}
            yield {
                "type": "done", "stop_reason": "end_turn",
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            }


class _EchoToolResultLLMClient:
    """First call requests one tool; the second call echoes the REAL tool
    result it was handed back (via the tool_result content block in
    `messages`) verbatim as its reply text -- lets a test assert on what
    adp.chat.tools.dispatch_tool actually returned, not a scripted stand-in,
    proving the real permission-gating code path ran end to end (T025's
    sensitive-category scenarios)."""

    def __init__(self, tool_name: str, tool_input: dict):
        self._tool_name = tool_name
        self._tool_input = tool_input
        self._call_count = 0

    async def chat_stream(self, *, messages, system, tools=None, correlation_id=None):
        self._call_count += 1
        if self._call_count == 1:
            yield {
                "type": "tool_use", "id": "tool-1",
                "name": self._tool_name, "input": self._tool_input,
            }
            yield {
                "type": "done", "stop_reason": "tool_use",
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            }
        else:
            tool_result_block = messages[-1]["content"][0]
            yield {"type": "text_delta", "text": tool_result_block["content"]}
            yield {
                "type": "done", "stop_reason": "end_turn",
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            }


def _user(role: PersonaRole) -> AuthenticatedUser:
    return AuthenticatedUser(sub="t", username="t", email="t@localhost", role=role, groups=[])


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
    yield client, chat_factory, biz_factory, app_factory, app
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


async def _mk_application(app_factory, app_id: str, name: str = "Order Service") -> None:
    now = datetime.now(timezone.utc)
    async with app_factory() as session:
        await session.execute(
            astore._applications.insert().values(
                id=app_id, name=name, description=None, vendor=None, primary_owner=None,
                time_classification=None, r_strategy=None, pace_layer=None, health_score=None,
                business_value=None, business_criticality=None, owning_business_unit=None,
                business_owner=None, technical_owner=None, lifecycle_status="active",
                hosting_model=None, architecture_pattern=None, tech_debt_flags=[],
                created_at=now, updated_at=now,
            )
        )
        await session.commit()


async def test_create_send_stream_and_ground_citation(app_and_stores):
    client, _, biz_factory, _, _ = app_and_stores
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
    client, _, _, _, _ = app_and_stores
    conv_id = client.post("/api/v1/chat/conversations").json()["id"]

    llm = _FakeLLMClient(_text_events("This relates to [business_capability:CAP-99-invented]."))
    with _mock_retrieval(), patch("adp.chat.router._make_chat_llm_client", return_value=llm):
        resp = client.post(
            f"/api/v1/chat/conversations/{conv_id}/messages", json={"content": "hi"}
        )
    events = _parse_sse(resp.text)
    assert events[-1]["citations"][0]["verified"] is False


async def test_llm_failure_emits_error_event_and_conversation_stays_resumable(app_and_stores):
    client, _, _, _, _ = app_and_stores
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
    client, _, _, _, _ = app_and_stores
    resp = client.post("/api/v1/chat/conversations/nope/messages", json={"content": "hi"})
    assert resp.status_code == 404


def test_send_message_rejects_blank_content(app_and_stores):
    client, _, _, _, _ = app_and_stores
    conv_id = client.post("/api/v1/chat/conversations").json()["id"]
    resp = client.post(
        f"/api/v1/chat/conversations/{conv_id}/messages", json={"content": "   "}
    )
    assert resp.status_code == 422


# ── US2: cross-domain retrieval + tool-calling (T025) ────────────────────────

async def test_application_question_retrieves_and_cites_application_data(app_and_stores):
    """A question the model answers by calling the get_application tool ends
    up citing the real application id, grounded and verified -- proving the
    tool-use round-trip (request -> dispatch -> result fed back -> reply)
    works end to end, not just the US1 no-tools path."""
    client, _, _, app_factory, _ = app_and_stores
    await _mk_application(app_factory, "APP-1", name="Order Service")

    conv_id = client.post("/api/v1/chat/conversations").json()["id"]
    llm = _ToolCallingLLMClient(
        "get_application", {"application_id": "APP-1"},
        "The Order Service application [application:APP-1] is currently active.",
    )
    with _mock_retrieval(), patch("adp.chat.router._make_chat_llm_client", return_value=llm):
        resp = client.post(
            f"/api/v1/chat/conversations/{conv_id}/messages",
            json={"content": "Tell me about the Order Service application"},
        )
    assert resp.status_code == 200, resp.text
    done = _parse_sse(resp.text)[-1]
    assert done["citations"] == [
        {"entity_type": "application", "entity_id": "APP-1", "verified": True}
    ]


@pytest.mark.parametrize(
    "tool_name", ["get_application_risk", "get_application_cost", "get_application_governance"]
)
async def test_sensitive_category_answered_when_permitted(app_and_stores, tool_name):
    """SC-004, permitted branch: ENTERPRISE_ARCHITECT holds every
    READ_APPLICATION_* permission, so the tool's real result -- not a
    scripted stand-in -- comes back permitted (found False, since no risk/
    cost/governance row was seeded; the point is the gate, not the data)."""
    client, _, _, app_factory, app = app_and_stores
    await _mk_application(app_factory, "APP-1")
    app.dependency_overrides[get_current_user] = lambda: _user(
        PersonaRole.ENTERPRISE_ARCHITECT
    )

    conv_id = client.post("/api/v1/chat/conversations").json()["id"]
    llm = _EchoToolResultLLMClient(tool_name, {"application_id": "APP-1"})
    with _mock_retrieval(), patch("adp.chat.router._make_chat_llm_client", return_value=llm):
        resp = client.post(
            f"/api/v1/chat/conversations/{conv_id}/messages", json={"content": "hi"}
        )
    assert resp.status_code == 200, resp.text
    text = "".join(e["text"] for e in _parse_sse(resp.text) if e["type"] == "text_delta")
    assert json.loads(text) == {"permitted": True, "found": False}


@pytest.mark.parametrize(
    "tool_name", ["get_application_risk", "get_application_cost", "get_application_governance"]
)
async def test_sensitive_category_declined_when_not_permitted(app_and_stores, tool_name):
    """SC-004, declined branch: REVIEWER holds USE_CHAT_ASSISTANT (can use
    the assistant at all) but none of the READ_APPLICATION_* sensitive-
    category permissions -- the tool must come back {"permitted": false},
    never an error and never a silently-empty result that could be
    mistaken for "no data exists" (research D5)."""
    client, _, _, app_factory, app = app_and_stores
    await _mk_application(app_factory, "APP-1")
    app.dependency_overrides[get_current_user] = lambda: _user(PersonaRole.REVIEWER)

    conv_id = client.post("/api/v1/chat/conversations").json()["id"]
    llm = _EchoToolResultLLMClient(tool_name, {"application_id": "APP-1"})
    with _mock_retrieval(), patch("adp.chat.router._make_chat_llm_client", return_value=llm):
        resp = client.post(
            f"/api/v1/chat/conversations/{conv_id}/messages", json={"content": "hi"}
        )
    assert resp.status_code == 200, resp.text
    text = "".join(e["text"] for e in _parse_sse(resp.text) if e["type"] == "text_delta")
    assert json.loads(text) == {"permitted": False}


# ── US3: actor-scoped conversation history (T033) ────────────────────────────

def test_own_conversations_are_listable_and_resumable(app_and_stores):
    client, _, _, _, _ = app_and_stores
    conv = client.post(
        "/api/v1/chat/conversations", headers={"X-Actor": "alice"}
    ).json()

    listing = client.get("/api/v1/chat/conversations", headers={"X-Actor": "alice"})
    assert listing.status_code == 200, listing.text
    assert [c["id"] for c in listing.json()] == [conv["id"]]

    detail = client.get(
        f"/api/v1/chat/conversations/{conv['id']}", headers={"X-Actor": "alice"}
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["id"] == conv["id"]


def test_other_actors_cannot_list_or_open_a_conversation_they_dont_own(app_and_stores):
    """SC-003: a second actor's attempt to list or open the first actor's
    conversation never reveals it exists -- listing simply omits it, and
    opening it directly is a 404 (never a 403, which would confirm the id
    is valid), the same non-distinguishing outcome for "doesn't exist" and
    "isn't yours"."""
    client, _, _, _, _ = app_and_stores
    conv = client.post(
        "/api/v1/chat/conversations", headers={"X-Actor": "alice"}
    ).json()

    other_listing = client.get("/api/v1/chat/conversations", headers={"X-Actor": "bob"})
    assert other_listing.status_code == 200, other_listing.text
    assert other_listing.json() == []

    other_detail = client.get(
        f"/api/v1/chat/conversations/{conv['id']}", headers={"X-Actor": "bob"}
    )
    assert other_detail.status_code == 404

    other_send = client.post(
        f"/api/v1/chat/conversations/{conv['id']}/messages",
        headers={"X-Actor": "bob"}, json={"content": "hi"},
    )
    assert other_send.status_code == 404


# ── US4: bounded sliding-window multi-turn context (T036) ────────────────────

class _RecordingLLMClient:
    """Records the `messages` payload of its most recent chat_stream() call
    so a test can assert on what context was actually sent to the model."""

    def __init__(self, *reply_texts: str):
        self._reply_texts = reply_texts
        self.seen_messages: list[dict] | None = None

    async def chat_stream(self, *, messages, system, tools=None, correlation_id=None):
        self.seen_messages = messages
        for text in self._reply_texts:
            yield {"type": "text_delta", "text": text}
        yield {
            "type": "done", "stop_reason": "end_turn",
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }


def test_follow_up_question_sends_prior_turn_as_context(app_and_stores):
    client, _, _, _, _ = app_and_stores
    conv_id = client.post("/api/v1/chat/conversations").json()["id"]

    first = _RecordingLLMClient("Merchandising is a level-1 capability.")
    with _mock_retrieval(), patch("adp.chat.router._make_chat_llm_client", return_value=first):
        client.post(
            f"/api/v1/chat/conversations/{conv_id}/messages",
            json={"content": "Tell me about the Merchandising capability."},
        )

    follow_up = _RecordingLLMClient("Yes, it is.")
    with _mock_retrieval(), patch(
        "adp.chat.router._make_chat_llm_client", return_value=follow_up
    ):
        resp = client.post(
            f"/api/v1/chat/conversations/{conv_id}/messages",
            json={"content": "Is it a level 1 capability?"},
        )
    assert resp.status_code == 200, resp.text

    assert follow_up.seen_messages is not None
    contents = [m["content"] for m in follow_up.seen_messages]
    assert "Tell me about the Merchandising capability." in contents
    assert "Merchandising is a level-1 capability." in contents
    assert contents[-1] == "Is it a level 1 capability?"


def test_long_conversation_replies_coherently_and_full_history_is_still_returned(app_and_stores):
    """A conversation with more messages than the sliding window still gets
    a normal reply, and GET .../conversations/{id} returns every persisted
    message regardless of what was actually sent to the model (US4 Scenario 2)."""
    client, chat_factory, _, _, _ = app_and_stores
    conv_id = client.post("/api/v1/chat/conversations").json()["id"]

    async def _seed_long_history() -> None:
        async with chat_factory() as session:
            for n in range(25):
                role = chat_store.ChatRole.USER if n % 2 == 0 else chat_store.ChatRole.ASSISTANT
                await chat_store.append_message(conv_id, role, f"message {n}", session)
            await session.commit()

    import asyncio
    asyncio.run(_seed_long_history())

    llm = _RecordingLLMClient("Still a coherent reply.")
    with _mock_retrieval(), patch("adp.chat.router._make_chat_llm_client", return_value=llm):
        resp = client.post(
            f"/api/v1/chat/conversations/{conv_id}/messages", json={"content": "and now?"}
        )
    assert resp.status_code == 200, resp.text
    assert _parse_sse(resp.text)[-1]["type"] == "done"
    assert llm.seen_messages is not None
    assert len(llm.seen_messages) < 25 + 1  # windowed, not the full history

    detail = client.get(f"/api/v1/chat/conversations/{conv_id}").json()
    assert len(detail["messages"]) == 25 + 2
