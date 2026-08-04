"""Unit tests: adp.admin.prompt_registry effective-prompt lookup (ADP-SPEC-042).

Points the module's own (normally lazy, ADP_DATABASE_URL-backed) session
factory at a throwaway SQLite DB for the duration of each test, mirroring
tests/unit/chat/test_store.py's convention.
"""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.admin import prompt_registry
from adp.admin.prompt_registry import AGENT_REGISTRATIONS, get_effective_prompt


@pytest.fixture()
async def sqlite_factory(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/prompts.db")
    async with engine.begin() as conn:
        await conn.run_sync(prompt_registry._metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(prompt_registry, "_session_factory", factory)
    # Also pin _engine_loop to THIS test's running loop -- otherwise
    # _get_session_factory()'s loop-identity check (added to keep the real
    # module safe across pytest-asyncio's per-test event loops) would decide
    # this monkeypatched factory is "stale" and silently replace it with a
    # fresh real-DB engine on the very next call.
    monkeypatch.setattr(prompt_registry, "_engine_loop", asyncio.get_running_loop())
    yield factory
    await engine.dispose()


def test_six_registrations_with_unique_ids() -> None:
    """Exactly the six agents from data-model.md §2, no duplicates."""
    ids = [r.agent_id for r in AGENT_REGISTRATIONS]
    assert len(ids) == 6
    assert len(set(ids)) == 6
    assert set(ids) == {
        "chat_assistant",
        "recommendation_generation",
        "recommendation_generation_no_kb",
        "recommendation_tradeoff",
        "intake_extraction",
        "agent_review_business_capability",
    }


@pytest.mark.parametrize("agent_id", [r.agent_id for r in AGENT_REGISTRATIONS])
async def test_falls_back_when_no_override_exists(sqlite_factory, agent_id: str) -> None:
    """With no override row, get_effective_prompt returns the agent's own
    fallback provider's current output, is_override=False, version=0."""
    registration = prompt_registry.get_registration(agent_id)
    assert registration is not None

    result = await get_effective_prompt(agent_id)

    assert result.is_override is False
    assert result.version == 0
    assert result.text == registration.fallback_provider()
    assert result.text.strip() != ""


async def test_agent_review_fallback_matches_load_system_prompt(sqlite_factory) -> None:
    """agent_review_business_capability's fallback provider IS
    _load_system_prompt itself (file-then-string), not a bare constant."""
    from adp.business.agent_review import _load_system_prompt

    result = await get_effective_prompt("agent_review_business_capability")
    assert result.text == _load_system_prompt()


async def test_override_row_takes_precedence(sqlite_factory) -> None:
    async with sqlite_factory() as session:
        await session.execute(
            prompt_registry._overrides.insert().values(
                agent_id="chat_assistant", prompt_text="Custom override text.", version=3
            )
        )
        await session.commit()

    result = await get_effective_prompt("chat_assistant")

    assert result.is_override is True
    assert result.version == 3
    assert result.text == "Custom override text."


async def test_other_agents_unaffected_by_one_overridden_agent(sqlite_factory) -> None:
    """An override on one agent_id must not leak into another's lookup."""
    async with sqlite_factory() as session:
        await session.execute(
            prompt_registry._overrides.insert().values(
                agent_id="chat_assistant", prompt_text="Custom.", version=1
            )
        )
        await session.commit()

    registration = prompt_registry.get_registration("intake_extraction")
    assert registration is not None
    result = await get_effective_prompt("intake_extraction")

    assert result.is_override is False
    assert result.version == 0
    assert result.text == registration.fallback_provider()
