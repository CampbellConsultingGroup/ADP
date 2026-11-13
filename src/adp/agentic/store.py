"""Agent registry store -- async SQLAlchemy Core CRUD (933-agent-registry, ADP-hii).

Agents are solution-independent; solution_agents joins an agentic application to an agent with a
role and a position (normalised to 0..n-1 per solution on every write, the value-chain precedent).
The migration (043) owns PK/FK/CHECK constraints; these Table objects are DML-only. Child rows are
removed explicitly so SQLite fixtures behave like Postgres, where CASCADE is the safety net.

Cross-domain reads go through a narrow `applications` mirror so this package imports no other
domain package (research.md D2, mirroring adp.compliance.store).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, cast

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from adp.agentic.models import (
    Agent,
    AgentCreate,
    AgentDetail,
    AgentNotFoundError,
    AgentSolution,
    AgentUpdate,
    DuplicateSolutionAgentError,
    MembershipNotFoundError,
    NotAgenticSolutionError,
    OrderMismatchError,
    SolutionAgent,
    SolutionNotFoundError,
)
from adp.search import ENTITY_AGENT, build_text, index_entity, unindex_entity

_metadata = sa.MetaData()

_agents = sa.Table(
    "agents",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("name", sa.String(255), nullable=False),
    sa.Column("description", sa.Text()),
    sa.Column("owner", sa.String(255)),
    sa.Column("lifecycle_status", sa.Text(), nullable=False, default="active"),
    sa.Column("model_provider", sa.String(100)),
    sa.Column("model_id", sa.String(200)),
    sa.Column("model_version", sa.String(100)),
    sa.Column("framework", sa.String(100)),
    sa.Column("prompt_ref", sa.String(200)),
    sa.Column("autonomy_level", sa.SmallInteger(), nullable=False),
    sa.Column("human_approval", sa.Text(), nullable=False),
    sa.Column("data_classification_max", sa.Text()),
    sa.Column("a2a_card_url", sa.Text()),
    sa.Column("est_cost_per_run", sa.Numeric(12, 4, asdecimal=True)),
    sa.Column("runs_per_month", sa.Integer()),
    sa.Column("external_registry_ref", sa.String(255)),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

_solution_agents = sa.Table(
    "solution_agents",
    _metadata,
    sa.Column("solution_app_id", sa.String(36), primary_key=True),
    sa.Column("agent_id", sa.String(36), primary_key=True),
    sa.Column("role", sa.Text(), nullable=False),
    sa.Column("position", sa.Integer(), nullable=False, default=0),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

# Narrow read-only mirror of adp.application's applications table (research.md D2).
_applications_mirror = sa.Table(
    "applications",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("name", sa.String(255), nullable=False),
    sa.Column("application_type", sa.Text()),
)

_AGENT_FIELDS = (
    "name", "description", "owner", "lifecycle_status", "model_provider", "model_id",
    "model_version", "framework", "prompt_ref", "autonomy_level", "human_approval",
    "data_classification_max", "a2a_card_url", "est_cost_per_run", "runs_per_month",
    "external_registry_ref",
)
# Required columns: an explicit null in a PATCH is ignored rather than written.
_NOT_NULL_FIELDS = frozenset({"name", "lifecycle_status", "autonomy_level", "human_approval"})


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _rowcount(result: Any) -> int:
    return cast("sa.CursorResult[Any]", result).rowcount


# ── Session factory ───────────────────────────────────────────────────────────

_engine: Any = None
_session_factory: Any = None


def _get_session_factory() -> async_sessionmaker:
    global _engine, _session_factory
    if _session_factory is None:
        import os

        db_url = os.environ.get(
            "ADP_DATABASE_URL", "postgresql+asyncpg://adp_user:adp_pass@127.0.0.1:5432/adp"
        )
        _engine = create_async_engine(db_url, echo=False)
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _session_factory


def get_session() -> AsyncSession:
    return _get_session_factory()()


# ── Helpers ───────────────────────────────────────────────────────────────────


def _row_to_agent(row: Any, solution_count: int = 0) -> Agent:
    return Agent(
        id=row.id,
        name=row.name,
        description=row.description,
        owner=row.owner,
        lifecycle_status=row.lifecycle_status,
        model_provider=row.model_provider,
        model_id=row.model_id,
        model_version=row.model_version,
        framework=row.framework,
        prompt_ref=row.prompt_ref,
        autonomy_level=row.autonomy_level,
        human_approval=row.human_approval,
        data_classification_max=row.data_classification_max,
        a2a_card_url=row.a2a_card_url,
        est_cost_per_run=row.est_cost_per_run,
        runs_per_month=row.runs_per_month,
        external_registry_ref=row.external_registry_ref,
        solution_count=solution_count,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _search_text(agent: Agent) -> str:
    return build_text(
        agent.name, agent.description, agent.model_provider, agent.model_id, agent.framework
    )


def _count_subquery() -> Any:
    return (
        sa.select(
            _solution_agents.c.agent_id.label("agent_id"),
            sa.func.count().label("solution_count"),
        )
        .group_by(_solution_agents.c.agent_id)
        .subquery()
    )


async def _agent_exists(agent_id: str, session: AsyncSession) -> bool:
    result = await session.execute(sa.select(_agents.c.id).where(_agents.c.id == agent_id))
    return result.first() is not None


async def _require_solution(app_id: str, session: AsyncSession, *, agentic: bool) -> None:
    row = (
        await session.execute(
            sa.select(_applications_mirror.c.application_type).where(
                _applications_mirror.c.id == app_id
            )
        )
    ).first()
    if row is None:
        raise SolutionNotFoundError(f"Application {app_id!r} not found")
    if agentic and row.application_type != "agentic":
        raise NotAgenticSolutionError(
            f"Application {app_id!r} is not an agentic solution (application_type="
            f"{row.application_type!r}); only agentic applications can have agents"
        )


async def _member_ids(app_id: str, session: AsyncSession) -> list[str]:
    result = await session.execute(
        sa.select(_solution_agents.c.agent_id)
        .where(_solution_agents.c.solution_app_id == app_id)
        .order_by(_solution_agents.c.position, _solution_agents.c.created_at)
    )
    return [r.agent_id for r in result]


async def _write_positions(app_id: str, agent_ids: list[str], session: AsyncSession) -> None:
    for pos, agent_id in enumerate(agent_ids):
        await session.execute(
            _solution_agents.update()
            .where(
                _solution_agents.c.solution_app_id == app_id,
                _solution_agents.c.agent_id == agent_id,
            )
            .values(position=pos)
        )


async def _renormalise(app_id: str, session: AsyncSession) -> None:
    await _write_positions(app_id, await _member_ids(app_id, session), session)


# ── Agents ────────────────────────────────────────────────────────────────────


async def create_agent(body: AgentCreate, session: AsyncSession) -> Agent:
    now = _now()
    agent_id = str(uuid.uuid4())
    values = {f: getattr(body, f) for f in _AGENT_FIELDS}
    await session.execute(
        _agents.insert().values(id=agent_id, created_at=now, updated_at=now, **values)
    )
    agent = await get_agent(agent_id, session)
    assert agent is not None
    await index_entity(ENTITY_AGENT, agent_id, _search_text(agent), session)
    return agent


async def get_agent(agent_id: str, session: AsyncSession) -> AgentDetail | None:
    row = (await session.execute(sa.select(_agents).where(_agents.c.id == agent_id))).first()
    if row is None:
        return None
    result = await session.execute(
        sa.select(
            _solution_agents.c.solution_app_id,
            _solution_agents.c.role,
            _solution_agents.c.position,
            _applications_mirror.c.name,
        )
        .select_from(
            _solution_agents.join(
                _applications_mirror,
                _applications_mirror.c.id == _solution_agents.c.solution_app_id,
            )
        )
        .where(_solution_agents.c.agent_id == agent_id)
        .order_by(_applications_mirror.c.name)
    )
    solutions = [
        AgentSolution(app_id=r.solution_app_id, app_name=r.name, role=r.role, position=r.position)
        for r in result
    ]
    agent = _row_to_agent(row, solution_count=len(solutions))
    return AgentDetail(**agent.model_dump(), solutions=solutions)


async def list_agents(
    session: AsyncSession,
    *,
    autonomy_level: int | None = None,
    autonomy_min: int | None = None,
    model_provider: str | None = None,
    owner: str | None = None,
    lifecycle_status: str | None = None,
) -> list[Agent]:
    counts = _count_subquery()
    query = (
        sa.select(_agents, sa.func.coalesce(counts.c.solution_count, 0).label("solution_count"))
        .select_from(_agents.outerjoin(counts, counts.c.agent_id == _agents.c.id))
        .order_by(_agents.c.name, _agents.c.id)
    )
    if autonomy_level is not None:
        query = query.where(_agents.c.autonomy_level == autonomy_level)
    if autonomy_min is not None:
        query = query.where(_agents.c.autonomy_level >= autonomy_min)
    if model_provider:
        query = query.where(_agents.c.model_provider == model_provider)
    if owner:
        query = query.where(_agents.c.owner == owner)
    if lifecycle_status:
        query = query.where(_agents.c.lifecycle_status == lifecycle_status)
    result = await session.execute(query)
    return [_row_to_agent(r, solution_count=r.solution_count) for r in result]


async def update_agent(agent_id: str, body: AgentUpdate, session: AsyncSession) -> Agent | None:
    if not await _agent_exists(agent_id, session):
        return None
    updates: dict[str, Any] = {"updated_at": _now()}
    for field in _AGENT_FIELDS:
        if field not in body.model_fields_set:
            continue
        value = getattr(body, field)
        if value is None and field in _NOT_NULL_FIELDS:
            continue
        updates[field] = value
    await session.execute(_agents.update().where(_agents.c.id == agent_id).values(**updates))
    agent = await get_agent(agent_id, session)
    assert agent is not None
    await index_entity(ENTITY_AGENT, agent_id, _search_text(agent), session)
    return agent


async def delete_agent(agent_id: str, session: AsyncSession) -> bool:
    if not await _agent_exists(agent_id, session):
        return False
    affected = await session.execute(
        sa.select(_solution_agents.c.solution_app_id).where(
            _solution_agents.c.agent_id == agent_id
        )
    )
    app_ids = [r.solution_app_id for r in affected]
    await session.execute(_solution_agents.delete().where(_solution_agents.c.agent_id == agent_id))
    await session.execute(_agents.delete().where(_agents.c.id == agent_id))
    for app_id in app_ids:
        await _renormalise(app_id, session)
    await unindex_entity(ENTITY_AGENT, agent_id, session)
    return True


# ── Solution membership ───────────────────────────────────────────────────────


async def list_solution_agents(app_id: str, session: AsyncSession) -> list[SolutionAgent]:
    await _require_solution(app_id, session, agentic=False)
    counts = _count_subquery()
    result = await session.execute(
        sa.select(
            _agents,
            _solution_agents.c.role,
            _solution_agents.c.position,
            sa.func.coalesce(counts.c.solution_count, 0).label("solution_count"),
        )
        .select_from(
            _solution_agents.join(_agents, _agents.c.id == _solution_agents.c.agent_id).outerjoin(
                counts, counts.c.agent_id == _agents.c.id
            )
        )
        .where(_solution_agents.c.solution_app_id == app_id)
        .order_by(_solution_agents.c.position, _solution_agents.c.created_at)
    )
    return [
        SolutionAgent(
            agent=_row_to_agent(r, solution_count=r.solution_count),
            role=r.role,
            position=r.position,
        )
        for r in result
    ]


async def add_solution_agent(
    app_id: str, agent_id: str, role: str, session: AsyncSession
) -> list[SolutionAgent]:
    await _require_solution(app_id, session, agentic=True)
    if not await _agent_exists(agent_id, session):
        raise AgentNotFoundError(f"Agent {agent_id!r} not found")
    members = await _member_ids(app_id, session)
    if agent_id in members:
        raise DuplicateSolutionAgentError(
            f"Agent {agent_id!r} is already part of solution {app_id!r}"
        )
    await session.execute(
        _solution_agents.insert().values(
            solution_app_id=app_id,
            agent_id=agent_id,
            role=role,
            position=len(members),
            created_at=_now(),
        )
    )
    return await list_solution_agents(app_id, session)


async def update_solution_agent_role(
    app_id: str, agent_id: str, role: str, session: AsyncSession
) -> SolutionAgent:
    await _require_solution(app_id, session, agentic=False)
    result = await session.execute(
        _solution_agents.update()
        .where(
            _solution_agents.c.solution_app_id == app_id,
            _solution_agents.c.agent_id == agent_id,
        )
        .values(role=role)
    )
    if _rowcount(result) == 0:
        raise MembershipNotFoundError(f"Agent {agent_id!r} is not part of solution {app_id!r}")
    for member in await list_solution_agents(app_id, session):
        if member.agent.id == agent_id:
            return member
    raise MembershipNotFoundError(agent_id)  # pragma: no cover - just updated


async def reorder_solution_agents(
    app_id: str, agent_ids: list[str], session: AsyncSession
) -> list[SolutionAgent]:
    await _require_solution(app_id, session, agentic=False)
    members = await _member_ids(app_id, session)
    if len(agent_ids) != len(members) or set(agent_ids) != set(members):
        raise OrderMismatchError(
            "agent_ids must list every agent in the solution exactly once"
        )
    await _write_positions(app_id, agent_ids, session)
    return await list_solution_agents(app_id, session)


async def remove_solution_agent(app_id: str, agent_id: str, session: AsyncSession) -> None:
    await _require_solution(app_id, session, agentic=False)
    result = await session.execute(
        _solution_agents.delete().where(
            _solution_agents.c.solution_app_id == app_id,
            _solution_agents.c.agent_id == agent_id,
        )
    )
    if _rowcount(result) == 0:
        raise MembershipNotFoundError(f"Agent {agent_id!r} is not part of solution {app_id!r}")
    await _renormalise(app_id, session)
