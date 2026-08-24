"""Integration test: a confirmed prompt edit takes effect for the very next
AI operation, against a real Postgres container -- no restart, no redeploy
(FR-005, User Story 2 Scenario 4; ADP-SPEC-042).

adp.admin.service and adp.admin.prompt_registry each own a lazy,
process-global session factory keyed off ADP_DATABASE_URL (see those
modules' comments on why prompt_registry's specifically also tracks the
event loop it was created under). This test points that env var at the real
test container and resets both modules' cached engine/factory first, so
this test doesn't depend on whatever a previous test in the same process
already initialized them to.

(This file previously also had its own local, after-each-test DELETE of
agent_prompt_history/agent_prompt_overrides -- removed as redundant now
that conftest.py's directory-wide _clean_tables truncates every table
before each test runs, ADP-isj.)
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _reset_admin_module_state(db_url, monkeypatch):
    from adp.admin import prompt_registry
    from adp.admin import service as admin_service

    monkeypatch.setenv("ADP_DATABASE_URL", db_url)
    for mod in (prompt_registry, admin_service):
        monkeypatch.setattr(mod, "_engine", None)
        monkeypatch.setattr(mod, "_session_factory", None)
    monkeypatch.setattr(prompt_registry, "_engine_loop", None)


async def test_confirmed_edit_takes_effect_for_next_chat_turn(db_engine) -> None:
    from adp.admin import service as admin_service
    from adp.admin.prompt_registry import get_effective_prompt

    # Before any edit: chat_assistant is on its built-in fallback.
    before = await get_effective_prompt("chat_assistant")
    assert before.is_override is False

    # Confirm an edit via the service layer (mirrors what the confirm
    # endpoint does) using its OWN fresh session against the real container.
    factory = admin_service._get_session_factory()
    async with factory() as session:
        result = await admin_service.save_prompt(
            "chat_assistant",
            "You are ADP's chat assistant. Always cite grounding sources explicitly.",
            expected_version=0,
            actor="alice",
            confirmation_id="CONFIRM-chat_assistant-integration-1",
            session=session,
        )
        await session.commit()
    assert result.version == 1

    # The next AI operation for this agent -- a completely separate call,
    # its own fresh lookup, no shared in-process state, no restart -- must
    # see the new text immediately.
    after = await get_effective_prompt("chat_assistant")
    assert after.is_override is True
    assert after.text == "You are ADP's chat assistant. Always cite grounding sources explicitly."

    # And the real chat orchestrator call site (not just the registry
    # directly) picks it up too, proving the T020 rewire actually works
    # end-to-end against a real DB, not just the SQLite-mocked unit test.
    from unittest.mock import AsyncMock, patch

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from adp.authz.roles import PersonaRole
    from adp.business import store as bstore
    from adp.chat import orchestrator
    from adp.chat import store as chat_store

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

    try:
        with patch("adp.chat.retrieval.retrieve_context", new=AsyncMock(return_value=[])):
            async with chat_factory() as chat_session, biz_factory() as biz_session:
                async for _ in orchestrator.run_turn(
                    conversation_id=conv.id, history=[], user_content="Hi",
                    chat_session=chat_session, biz_session=biz_session,
                    app_session=biz_session, kb_session=biz_session,
                    role=PersonaRole.ENTERPRISE_ARCHITECT, llm_client=_RecordingLLMClient(),
                ):
                    pass
    finally:
        await chat_engine.dispose()
        await biz_engine.dispose()

    assert len(captured_system) == 1
    assert "Always cite grounding sources explicitly" in captured_system[0]


async def test_two_edits_by_different_actors_recorded_and_restorable(db_engine) -> None:
    """User Story 3's Independent Test setup, exercised against a real DB:
    two successive edits by different actors, then restore the first."""
    from adp.admin import service as admin_service

    factory = admin_service._get_session_factory()

    async with factory() as session:
        await admin_service.save_prompt(
            "intake_extraction", "Alice's extraction prompt.", 0, "alice",
            "CONFIRM-1", session,
        )
        await session.commit()

    async with factory() as session:
        await admin_service.save_prompt(
            "intake_extraction", "Bob's extraction prompt.", 1, "bob", "CONFIRM-2", session,
        )
        await session.commit()

    async with factory() as session:
        history = await admin_service.get_history("intake_extraction", session)
    assert len(history) == 2
    assert history[0].actor == "bob"  # newest first
    assert history[1].actor == "alice"

    alice_entry = history[1]
    async with factory() as session:
        restored = await admin_service.restore_prompt(
            "intake_extraction", alice_entry.id, expected_version=2, actor="alice",
            confirmation_id="CONFIRM-3", session=session,
        )
        await session.commit()

    assert restored.active_text == "Alice's extraction prompt."
    assert restored.version == 3

    async with factory() as session:
        final_history = await admin_service.get_history("intake_extraction", session)
    assert len(final_history) == 3
    assert final_history[0].change_type == "restore"
    assert final_history[0].new_text == "Alice's extraction prompt."
