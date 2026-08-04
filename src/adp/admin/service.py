"""Service layer for the Admin Agent Prompt Management API (ADP-SPEC-042).

Owns the WRITE path (confirm/restore) and its own Core Table objects for
`agent_prompt_overrides`/`agent_prompt_history` (migration 023). The READ
path used across every AI call site lives in `adp.admin.prompt_registry`,
which defines its own minimal projection of `agent_prompt_overrides` and is
deliberately NOT imported from here for writes -- this module always uses a
request-scoped session (via the router's dependency), never
prompt_registry's self-contained one.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from adp.admin import prompt_registry
from adp.admin.models import AgentPromptView, PromptChangeResult, PromptHistoryEntry

_metadata = sa.MetaData()

_overrides = sa.Table(
    "agent_prompt_overrides",
    _metadata,
    sa.Column("agent_id", sa.Text(), primary_key=True),
    sa.Column("prompt_text", sa.Text(), nullable=False),
    sa.Column("updated_by", sa.Text(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("version", sa.Integer(), nullable=False),
)

_history = sa.Table(
    "agent_prompt_history",
    _metadata,
    # SQLite only treats a column as the auto-incrementing rowid alias when
    # its declared type affinity is exactly INTEGER, not BIGINT -- Integer()
    # here (BigInteger on Postgres, matching migration 023's BIGSERIAL)
    # mirrors business/store.py's ARRAY/.with_variant(JSON, "sqlite") pattern
    # for the same "prod type breaks SQLite-backed tests" class of issue.
    sa.Column(
        "id",
        sa.Integer().with_variant(sa.BigInteger(), "postgresql"),
        primary_key=True,
        autoincrement=True,
    ),
    sa.Column("agent_id", sa.Text(), nullable=False),
    sa.Column("actor", sa.Text(), nullable=False),
    sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("change_type", sa.Text(), nullable=False),
    sa.Column("prior_text", sa.Text(), nullable=False),
    sa.Column("new_text", sa.Text(), nullable=False),
    sa.Column("confirmation_id", sa.Text(), nullable=False),
)


# ── Module-level session factory (set by deps or tests) ───────────────────────
# Always accessed via the router's FastAPI dependency (mirrors
# adp.business.store / adp.chat.store) -- tests always override the router
# dependency directly, so this lazy singleton is never invoked in a test
# context, unlike adp.admin.prompt_registry's (see that module's comment).

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


def get_session() -> AsyncSession:
    return _get_session_factory()()


def _now() -> datetime:
    return datetime.now(timezone.utc)


class PromptVersionConflict(Exception):
    """Raised when expected_version doesn't match the current row (FR-012).

    Carries the current state so the caller (router) can surface it to the
    client rather than silently overwriting -- the admin must reload and
    retry, not lose the other admin's change.
    """

    def __init__(self, current_text: str, current_version: int) -> None:
        self.current_text = current_text
        self.current_version = current_version
        super().__init__(
            f"Version conflict: expected version does not match current version {current_version}"
        )


class UnknownAgentError(Exception):
    """Raised for an agent_id not in prompt_registry.AGENT_REGISTRATIONS."""


# ── US1: list every agent's current effective prompt (read-only) ────────────

async def _get_override_row(agent_id: str, session: AsyncSession) -> sa.Row[Any] | None:
    result = await session.execute(
        sa.select(_overrides.c.prompt_text, _overrides.c.version).where(
            _overrides.c.agent_id == agent_id
        )
    )
    return result.first()


async def _current_state(agent_id: str, session: AsyncSession) -> tuple[str, int]:
    """Return (current_text, current_version) whether or not an override
    row exists yet (version=0, fallback text, if not)."""
    row = await _get_override_row(agent_id, session)
    if row is not None:
        return row.prompt_text, row.version
    registration = prompt_registry.get_registration(agent_id)
    if registration is None:
        raise UnknownAgentError(agent_id)
    return registration.fallback_provider(), 0


async def list_agents() -> list[AgentPromptView]:
    """One AgentPromptView per registration, via prompt_registry's shared
    effective-prompt lookup -- the same function every AI call site uses, so
    what this screen shows is guaranteed to match what agents actually send
    (FR-001, User Story 1's Independent Test)."""
    views: list[AgentPromptView] = []
    for registration in prompt_registry.AGENT_REGISTRATIONS:
        effective = await prompt_registry.get_effective_prompt(registration.agent_id)
        views.append(
            AgentPromptView(
                agent_id=registration.agent_id,
                display_name=registration.display_name,
                active_text=effective.text,
                is_override=effective.is_override,
                version=effective.version,
            )
        )
    return views


# ── User Story 2: edit + confirm (write path) ────────────────────────────────

async def save_prompt(
    agent_id: str,
    new_text: str,
    expected_version: int,
    actor: str,
    confirmation_id: str,
    session: AsyncSession,
) -> PromptChangeResult:
    """Confirm a manual edit (FR-003/FR-005/FR-010). Caller (the router) is
    responsible for committing the session -- both the override upsert and
    the history insert happen in the same not-yet-committed transaction, so
    they succeed or fail together (spec.md edge case)."""
    if not new_text.strip():
        raise ValueError("new_text must be non-empty (FR-004)")

    current_text, current_version = await _current_state(agent_id, session)
    if expected_version != current_version:
        raise PromptVersionConflict(current_text, current_version)

    new_version = current_version + 1
    now = _now()
    if current_version == 0:
        await session.execute(
            _overrides.insert().values(
                agent_id=agent_id, prompt_text=new_text, updated_by=actor,
                updated_at=now, version=new_version,
            )
        )
    else:
        await session.execute(
            _overrides.update()
            .where(_overrides.c.agent_id == agent_id)
            .values(prompt_text=new_text, updated_by=actor, updated_at=now, version=new_version)
        )
    await session.execute(
        _history.insert().values(
            agent_id=agent_id, actor=actor, changed_at=now, change_type="edit",
            prior_text=current_text, new_text=new_text, confirmation_id=confirmation_id,
        )
    )
    return PromptChangeResult(agent_id=agent_id, active_text=new_text, version=new_version)


# ── User Story 3: history + restore ──────────────────────────────────────────

async def get_history(agent_id: str, session: AsyncSession) -> list[PromptHistoryEntry]:
    result = await session.execute(
        sa.select(
            _history.c.id, _history.c.agent_id, _history.c.actor, _history.c.changed_at,
            _history.c.change_type, _history.c.prior_text, _history.c.new_text,
        )
        .where(_history.c.agent_id == agent_id)
        .order_by(_history.c.changed_at.desc(), _history.c.id.desc())
    )
    return [
        PromptHistoryEntry(
            id=row.id, agent_id=row.agent_id, actor=row.actor, changed_at=row.changed_at,
            change_type=row.change_type, prior_text=row.prior_text, new_text=row.new_text,
        )
        for row in result.all()
    ]


class HistoryEntryNotFoundError(Exception):
    """Raised when history_id doesn't exist or doesn't belong to agent_id."""


async def restore_prompt(
    agent_id: str,
    history_id: int,
    expected_version: int,
    actor: str,
    confirmation_id: str,
    session: AsyncSession,
) -> PromptChangeResult:
    """Restore a prior version as the new active prompt (FR-008), subject to
    the SAME confirmation/version-check gate as save_prompt (Clarification
    Session 2026-07-24: restore is not a lower-friction path). The restored
    text is copied from the chosen history row's new_text; this transition
    is itself recorded as a NEW history entry (change_type="restore"), never
    a rewrite of the past."""
    result = await session.execute(
        sa.select(_history.c.new_text).where(
            (_history.c.id == history_id) & (_history.c.agent_id == agent_id)
        )
    )
    row = result.first()
    if row is None:
        raise HistoryEntryNotFoundError(f"history_id {history_id!r} not found for {agent_id!r}")
    restored_text = row.new_text

    current_text, current_version = await _current_state(agent_id, session)
    if expected_version != current_version:
        raise PromptVersionConflict(current_text, current_version)

    new_version = current_version + 1
    now = _now()
    if current_version == 0:
        await session.execute(
            _overrides.insert().values(
                agent_id=agent_id, prompt_text=restored_text, updated_by=actor,
                updated_at=now, version=new_version,
            )
        )
    else:
        await session.execute(
            _overrides.update()
            .where(_overrides.c.agent_id == agent_id)
            .values(
                prompt_text=restored_text, updated_by=actor, updated_at=now, version=new_version
            )
        )
    await session.execute(
        _history.insert().values(
            agent_id=agent_id, actor=actor, changed_at=now, change_type="restore",
            prior_text=current_text, new_text=restored_text, confirmation_id=confirmation_id,
        )
    )
    return PromptChangeResult(agent_id=agent_id, active_text=restored_text, version=new_version)
