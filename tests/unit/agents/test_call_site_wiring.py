"""Unit tests: each of the 5 non-Agent-Review AI call sites resolves its
system prompt via adp.admin.prompt_registry.get_effective_prompt() rather
than referencing its module-level constant directly (ADP-SPEC-042 US1).

This is what makes User Story 1's own Independent Test meaningful: the admin
screen only shows what an agent "actually sends to the LLM" if the agent's
real code path reads from the same override table the screen reads from.
Each test sets a distinctive override for one agent_id in a throwaway SQLite
DB (mirroring tests/unit/admin/test_prompt_registry.py's convention) and
confirms that exact text -- not the hardcoded constant -- reaches the
(mocked) LLM call.

Agent Review's rewire (the 6th registration) is intentionally NOT covered
here -- it is exercised end-to-end by tests/contract/test_capability_agent_review_api.py.
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.admin import prompt_registry


@pytest.fixture()
async def sqlite_factory(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/prompts.db")
    async with engine.begin() as conn:
        await conn.run_sync(prompt_registry._metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(prompt_registry, "_session_factory", factory)
    monkeypatch.setattr(prompt_registry, "_engine_loop", asyncio.get_running_loop())
    yield factory
    await engine.dispose()


async def _set_override(sqlite_factory, agent_id: str, text: str) -> None:
    async with sqlite_factory() as session:
        await session.execute(
            prompt_registry._overrides.insert().values(agent_id=agent_id, prompt_text=text, version=1)
        )
        await session.commit()


# ── chat_assistant ────────────────────────────────────────────────────────────

async def test_chat_assistant_uses_override(sqlite_factory) -> None:
    from adp.authz.roles import PersonaRole
    from adp.business import store as bstore
    from adp.chat import orchestrator
    from adp.chat import store as chat_store

    await _set_override(sqlite_factory, "chat_assistant", "CUSTOM CHAT PROMPT MARKER")

    chat_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with chat_engine.begin() as conn:
        await conn.run_sync(chat_store._metadata.create_all)
    biz_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with biz_engine.begin() as conn:
        await conn.run_sync(bstore._metadata.create_all)
    chat_factory = async_sessionmaker(chat_engine, expire_on_commit=False)
    biz_factory = async_sessionmaker(biz_engine, expire_on_commit=False)

    async with chat_factory() as chat_session:
        conv = await chat_store.create_conversation("alice", chat_session)
        await chat_session.commit()

    captured_system: list[str] = []

    class _RecordingLLMClient:
        async def chat_stream(self, *, messages, system, tools=None, correlation_id=None):
            captured_system.append(system)
            yield {
                "type": "done", "stop_reason": "end_turn",
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            }

    with patch("adp.chat.retrieval.retrieve_context", new=AsyncMock(return_value=[])):
        async with chat_factory() as chat_session, biz_factory() as biz_session:
            events = [
                e
                async for e in orchestrator.run_turn(
                    conversation_id=conv.id, history=[], user_content="Hi",
                    chat_session=chat_session, biz_session=biz_session,
                    app_session=biz_session, kb_session=biz_session,
                    role=PersonaRole.ENTERPRISE_ARCHITECT, llm_client=_RecordingLLMClient(),
                )
            ]

    assert events[-1]["type"] == "done"
    assert len(captured_system) == 1
    assert "CUSTOM CHAT PROMPT MARKER" in captured_system[0]

    await chat_engine.dispose()
    await biz_engine.dispose()


# ── recommendation_generation / recommendation_generation_no_kb ─────────────

async def test_recommendation_generation_uses_override(sqlite_factory) -> None:
    from adp.models import Requirement
    from adp.recommendation.steps import generate_step
    from tests.recommendation.test_steps import _llm_generation_response, _make_entry, _mock_telemetry

    await _set_override(
        sqlite_factory, "recommendation_generation", "CUSTOM GENERATION MARKER {option_count}"
    )

    mock_llm = MagicMock()
    mock_llm.chat = AsyncMock(return_value=_llm_generation_response(1))
    req = Requirement(id="REQ-001", title="Stateless", description="System must be stateless")
    entry = _make_entry("PAT-001")

    await generate_step(
        {
            "operation_id": "op-001", "design_id": "DESIGN-001", "requirement_ids": ["REQ-001"],
            "requirements": [req], "retrieved_knowledge": [entry], "candidate_options": [],
            "ranked_options": [], "validated_options": [], "correlation_id": "corr-001",
            "error": None, "option_count": 1, "ranking_weights": (0.4, 0.3, 0.3),
        },
        llm=mock_llm, telemetry=_mock_telemetry(), option_count=1,
    )

    system_sent = mock_llm.chat.call_args.kwargs.get("system") or mock_llm.chat.call_args.args[0]
    assert "CUSTOM GENERATION MARKER 1" in system_sent


async def test_recommendation_generation_no_kb_uses_override(sqlite_factory) -> None:
    from adp.models import Requirement
    from adp.recommendation.steps import generate_step
    from tests.recommendation.test_steps import _llm_generation_response, _mock_telemetry

    await _set_override(
        sqlite_factory, "recommendation_generation_no_kb", "CUSTOM NO-KB MARKER {option_count}"
    )

    mock_llm = MagicMock()
    mock_llm.chat = AsyncMock(return_value=_llm_generation_response(1))
    req = Requirement(id="REQ-001", title="Stateless", description="System must be stateless")

    await generate_step(
        {
            "operation_id": "op-001", "design_id": "DESIGN-001", "requirement_ids": ["REQ-001"],
            "requirements": [req], "retrieved_knowledge": [], "candidate_options": [],
            "ranked_options": [], "validated_options": [], "correlation_id": "corr-001",
            "error": None, "option_count": 1, "ranking_weights": (0.4, 0.3, 0.3),
        },
        llm=mock_llm, telemetry=_mock_telemetry(), option_count=1,
    )

    system_sent = mock_llm.chat.call_args.kwargs.get("system") or mock_llm.chat.call_args.args[0]
    assert "CUSTOM NO-KB MARKER 1" in system_sent


# ── recommendation_tradeoff ──────────────────────────────────────────────────

async def test_recommendation_tradeoff_uses_override(sqlite_factory) -> None:
    from adp.models import ElementKind
    from adp.recommendation.models import ProposedElement, SolutionOption
    from adp.recommendation.steps import analyze_tradeoffs_step
    from tests.recommendation.test_steps import _mock_telemetry

    await _set_override(sqlite_factory, "recommendation_tradeoff", "CUSTOM TRADEOFF MARKER")

    option = SolutionOption(
        option_id="OPT-1", operation_id="op-001", title="Option A", rationale="Because",
        grounded_on=[], satisfies=[],
        proposed_elements=[ProposedElement(name="Svc", kind=ElementKind.SYSTEM)],
        trade_offs=[],
    )
    mock_llm = MagicMock()
    mock_llm.chat = AsyncMock(return_value={
        "choices": [{"message": {"content": json.dumps({"trade_offs": []})}}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
    })

    await analyze_tradeoffs_step(
        {
            "operation_id": "op-001", "design_id": "DESIGN-001", "requirement_ids": [],
            "requirements": [], "retrieved_knowledge": [], "candidate_options": [option],
            "ranked_options": [], "validated_options": [], "correlation_id": "corr-001",
            "error": None, "option_count": 1, "ranking_weights": (0.4, 0.3, 0.3),
        },
        llm=mock_llm, telemetry=_mock_telemetry(),
    )

    system_sent = mock_llm.chat.call_args.args[0]
    assert system_sent == "CUSTOM TRADEOFF MARKER"


# ── intake_extraction ────────────────────────────────────────────────────────

async def test_intake_extraction_uses_override(sqlite_factory) -> None:
    from adp.llm.client import LLMClient

    await _set_override(sqlite_factory, "intake_extraction", "CUSTOM EXTRACTION MARKER")

    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"requirements": []}'}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
            request=request,
        )

    client = LLMClient(base_url="https://api.example.com", api_key="test-key", model="gpt-4o")

    _RealClient = httpx.AsyncClient

    def make_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return _RealClient(*args, **kwargs)

    with patch("adp.llm.client.httpx.AsyncClient", side_effect=make_client):
        await client.extract("Some source text.", "corr-001")

    assert len(captured) == 1
    body = json.loads(captured[0].content)
    system_messages = [m["content"] for m in body["messages"] if m["role"] == "system"]
    assert system_messages == ["CUSTOM EXTRACTION MARKER"]
