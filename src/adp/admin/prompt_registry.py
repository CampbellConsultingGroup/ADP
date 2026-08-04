"""Effective system-prompt lookup for ADP's AI agents (ADP-SPEC-042).

Generalizes `adp.business.agent_review._load_system_prompt()`'s shape: check
for a saved admin override first; fall back to the agent's own built-in
constant/loader otherwise. This is the READ path only, self-contained (its
own tiny session factory, no caller-supplied session) so every existing AI
call site can adopt it with a single-line change. The admin WRITE path
(edit/confirm/restore) lives in `adp.admin.service`, which owns its own
request-scoped session and Core Table objects for the same two tables --
this module only ever reads `agent_prompt_overrides`.

Lives in `adp.admin`, NOT `adp.agents` -- unlike that package (the ADP-SPEC-039
Agent Review toolkit, mechanically enforced to have zero imports from any
single domain module so a second adapter can reuse it unmodified, see
tests/unit/agents/test_toolkit_boundary.py), this module's entire purpose is
to know about every agent, including domain-specific ones (it imports from
`adp.chat`, `adp.recommendation`, `adp.llm`, and `adp.business` below). It was
originally planned as `adp.agents.prompt_registry`; relocated during
implementation once the toolkit boundary test made that conflict concrete.

Fallback providers are deferred (imported inside the function body, not at
module load time) to avoid a circular import: each of the five other call
sites imports `get_effective_prompt` from here, so this module cannot import
their constants at its own top level.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

_metadata = sa.MetaData()

# Minimal projection of agent_prompt_overrides (migration 023) -- only the
# columns this read path needs. adp.admin.service defines the full table
# (including updated_by/updated_at) for the write path.
_overrides = sa.Table(
    "agent_prompt_overrides",
    _metadata,
    sa.Column("agent_id", sa.Text(), primary_key=True),
    sa.Column("prompt_text", sa.Text(), nullable=False),
    sa.Column("version", sa.Integer(), nullable=False),
)


@dataclass(frozen=True)
class EffectivePrompt:
    """What an agent should actually use right now."""

    text: str
    is_override: bool
    version: int


@dataclass(frozen=True)
class AgentRegistration:
    """One agent's system-prompt slot (data-model.md §2)."""

    agent_id: str
    display_name: str
    fallback_provider: Callable[[], str]


def _chat_assistant_fallback() -> str:
    from adp.chat.orchestrator import _SYSTEM_PROMPT
    return _SYSTEM_PROMPT


def _recommendation_generation_fallback() -> str:
    from adp.recommendation.prompts import GENERATION_SYSTEM_PROMPT
    return GENERATION_SYSTEM_PROMPT


def _recommendation_generation_no_kb_fallback() -> str:
    from adp.recommendation.prompts import GENERATION_SYSTEM_PROMPT_NO_KB
    return GENERATION_SYSTEM_PROMPT_NO_KB


def _recommendation_tradeoff_fallback() -> str:
    from adp.recommendation.prompts import TRADEOFF_SYSTEM_PROMPT
    return TRADEOFF_SYSTEM_PROMPT


def _intake_extraction_fallback() -> str:
    from adp.llm.client import _EXTRACTION_SYSTEM_PROMPT
    return _EXTRACTION_SYSTEM_PROMPT


def _agent_review_business_capability_fallback() -> str:
    # _load_system_prompt() is ALREADY a two-level fallback (file, then a
    # hardcoded string) -- this registration's provider IS that function,
    # not a bare constant (research.md Decision 5).
    from adp.business.agent_review import _load_system_prompt
    return _load_system_prompt()


# Order matches data-model.md §2 / the originating bead's enumeration.
AGENT_REGISTRATIONS: tuple[AgentRegistration, ...] = (
    AgentRegistration("chat_assistant", "Chat Assistant", _chat_assistant_fallback),
    AgentRegistration(
        "recommendation_generation",
        "Recommendation — Generation",
        _recommendation_generation_fallback,
    ),
    AgentRegistration(
        "recommendation_generation_no_kb",
        "Recommendation — Generation (no knowledge base)",
        _recommendation_generation_no_kb_fallback,
    ),
    AgentRegistration(
        "recommendation_tradeoff",
        "Recommendation — Trade-off Analysis",
        _recommendation_tradeoff_fallback,
    ),
    AgentRegistration("intake_extraction", "Intake Extraction", _intake_extraction_fallback),
    AgentRegistration(
        "agent_review_business_capability",
        "Agent Review — Business Capability",
        _agent_review_business_capability_fallback,
    ),
)

_REGISTRATIONS_BY_ID: dict[str, AgentRegistration] = {r.agent_id: r for r in AGENT_REGISTRATIONS}


def get_registration(agent_id: str) -> AgentRegistration | None:
    return _REGISTRATIONS_BY_ID.get(agent_id)


# ── Self-contained session factory (mirrors adp.business.store's pattern) ────
#
# Unlike adp.business.store, this factory is invoked directly from deep inside
# business logic (orchestrator.py, agent_review.py, steps.py, llm/client.py)
# with no FastAPI dependency-override seam -- every other store module's
# equivalent lazy singleton is only ever exercised in tests via a router-level
# override, never called directly, so it never has to survive multiple event
# loops. get_effective_prompt() IS called directly, so a plain module-level
# singleton would bind its asyncpg engine to whichever event loop happened to
# create it first and then break every subsequent test running under a
# different loop (pytest-asyncio's default is one loop per test function).
# Track the loop the engine was created for and recreate it if that loop is no
# longer the running one.

_engine: Any = None
_session_factory: Any = None
_engine_loop: Any = None


def _get_session_factory() -> async_sessionmaker:
    import asyncio

    global _engine, _session_factory, _engine_loop
    current_loop = asyncio.get_running_loop()
    if _session_factory is None or _engine_loop is not current_loop:
        db_url = os.environ.get(
            "ADP_DATABASE_URL", "postgresql+asyncpg://adp_user:adp_pass@127.0.0.1:5432/adp"
        )
        _engine = create_async_engine(db_url, echo=False)
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
        _engine_loop = current_loop
    return _session_factory


async def _fetch_override(agent_id: str, session: AsyncSession) -> sa.Row[Any] | None:
    result = await session.execute(
        sa.select(_overrides.c.prompt_text, _overrides.c.version).where(
            _overrides.c.agent_id == agent_id
        )
    )
    return result.first()


async def get_effective_prompt(agent_id: str) -> EffectivePrompt:
    """Return what `agent_id` should actually use right now.

    Raises KeyError for an unregistered agent_id -- callers are the fixed set
    of six registrations plus the admin list/history endpoints, never
    arbitrary user input.
    """
    registration = _REGISTRATIONS_BY_ID[agent_id]
    factory = _get_session_factory()
    async with factory() as session:
        row = await _fetch_override(agent_id, session)
    if row is not None:
        return EffectivePrompt(text=row.prompt_text, is_override=True, version=row.version)
    return EffectivePrompt(text=registration.fallback_provider(), is_override=False, version=0)
