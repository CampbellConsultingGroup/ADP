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
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from adp.agentic.models import (
    Agent,
    AgentAutomates,
    AgentCreate,
    AgentDetail,
    AgentNotFoundError,
    AgentSolution,
    AgentSummary,
    AgentUpdate,
    AutomatesActivity,
    AutomatesCapability,
    AutomatesKind,
    AutomatesStage,
    DuplicateLinkError,
    DuplicateSolutionAgentError,
    LevelRuleError,
    LinkNotFoundError,
    MembershipNotFoundError,
    NotAgenticSolutionError,
    OrderMismatchError,
    SolutionAgent,
    SolutionNotFoundError,
    TargetNotFoundError,
)
from adp.agentic.risk import agent_risk
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

# ── Automates links (944-agent-traceability, migration 052) ───────────────────
# Plain columns: the FKs (CASCADE on both legs) exist only in the migration, because the targets
# live on adp.business's metadata (research.md R1, 940's owning_org_unit_id precedent).


def _link_table(name: str, target_col: str) -> sa.Table:
    return sa.Table(
        name,
        _metadata,
        sa.Column("agent_id", sa.String(36), primary_key=True),
        sa.Column(target_col, sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


_agent_capability_links = _link_table("agent_capability_links", "capability_id")
_agent_stage_links = _link_table("agent_stage_links", "stage_id")
_agent_activity_links = _link_table("agent_activity_links", "activity_id")

# Narrow read-only mirrors of adp.business's tables, used to validate link targets and to
# describe them. Fixtures that also create adp.business.store's metadata must create it FIRST;
# create_all(checkfirst) then skips these mirrors (the astore/agstore order rule).
_capabilities_mirror = sa.Table(
    "business_capabilities",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("name", sa.String(255), nullable=False),
    sa.Column("level", sa.Integer(), nullable=False),
    sa.Column("parent_id", sa.String(36)),
)
_value_streams_mirror = sa.Table(
    "value_streams",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("name", sa.String(255), nullable=False),
)
_stages_mirror = sa.Table(
    "value_stream_stages",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("value_stream_id", sa.String(36), nullable=False),
    sa.Column("name", sa.String(255), nullable=False),
    sa.Column("position", sa.Integer(), nullable=False, default=0),
)
_value_chains_mirror = sa.Table(
    "value_chains",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("name", sa.String(255), nullable=False),
)
_activities_mirror = sa.Table(
    "value_chain_activities",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("value_chain_id", sa.String(36), nullable=False),
    sa.Column("name", sa.String(255), nullable=False),
    sa.Column("category", sa.Text(), nullable=False),
    sa.Column("position", sa.Integer(), nullable=False, default=0),
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
    """Every store shares adp.db's single engine (ADP-blp.15). A test may set this module's
    _session_factory to point it at its own database instead."""
    if _session_factory is not None:
        return _session_factory
    from adp.db import get_session_factory

    return get_session_factory()


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
        agentic_risk=agent_risk(
            row.autonomy_level, row.human_approval, row.data_classification_max
        ),
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
    for link_table, _target_col, _mirror in _LINKS.values():
        await session.execute(link_table.delete().where(link_table.c.agent_id == agent_id))
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


# ── Automates links (944-agent-traceability, US1) ─────────────────────────────

# kind -> (link table, target column, target mirror)
_LINKS: dict[str, tuple[sa.Table, str, sa.Table]] = {
    "capability": (_agent_capability_links, "capability_id", _capabilities_mirror),
    "stage": (_agent_stage_links, "stage_id", _stages_mirror),
    "activity": (_agent_activity_links, "activity_id", _activities_mirror),
}
_KIND_LABEL = {"capability": "Capability", "stage": "Stage", "activity": "Activity"}


async def _require_agent(agent_id: str, session: AsyncSession) -> None:
    if not await _agent_exists(agent_id, session):
        raise AgentNotFoundError(f"Agent {agent_id!r} not found")


async def _require_target(kind: str, target_id: str, session: AsyncSession) -> Any:
    _table, _col, mirror = _LINKS[kind]
    row = (await session.execute(sa.select(mirror).where(mirror.c.id == target_id))).first()
    if row is None:
        raise TargetNotFoundError(f"{_KIND_LABEL[kind]} {target_id!r} not found")
    return row


async def _capability_paths(rows: list[Any], session: AsyncSession) -> dict[str, list[str]]:
    """[L1 name, L2 name] for each capability row, from the mirror's parent ids."""
    names: dict[str, tuple[str, str | None]] = {}
    pending = {r.parent_id for r in rows if r.parent_id}
    while pending:
        result = await session.execute(
            sa.select(
                _capabilities_mirror.c.id,
                _capabilities_mirror.c.name,
                _capabilities_mirror.c.parent_id,
            ).where(_capabilities_mirror.c.id.in_(pending))
        )
        found = {r.id: (r.name, r.parent_id) for r in result}
        names.update(found)
        pending = {p for _n, p in found.values() if p and p not in names}
    paths: dict[str, list[str]] = {}
    for r in rows:
        path: list[str] = []
        parent = r.parent_id
        while parent and parent in names:
            name, parent = names[parent]
            path.insert(0, name)
        paths[r.id] = path
    return paths


async def get_automates(agent_id: str, session: AsyncSession) -> AgentAutomates:
    """Everything the agent automates, with context. Inner joins: a link whose target row is gone
    (SQLite doesn't enforce the migration's CASCADE) never surfaces."""
    await _require_agent(agent_id, session)
    links = _agent_capability_links
    caps = _capabilities_mirror
    cap_rows = list(
        await session.execute(
            sa.select(caps)
            .select_from(links.join(caps, caps.c.id == links.c.capability_id))
            .where(links.c.agent_id == agent_id)
        )
    )
    paths = await _capability_paths(cap_rows, session)
    capabilities = sorted(
        (
            AutomatesCapability(id=r.id, name=r.name, level=r.level, path=paths[r.id])
            for r in cap_rows
        ),
        key=lambda c: ([p.lower() for p in c.path], c.name.lower()),
    )

    st, vs, sl = _stages_mirror, _value_streams_mirror, _agent_stage_links
    stage_rows = await session.execute(
        sa.select(st.c.id, st.c.name, st.c.value_stream_id, vs.c.name.label("vs_name"))
        .select_from(
            sl.join(st, st.c.id == sl.c.stage_id).join(vs, vs.c.id == st.c.value_stream_id)
        )
        .where(sl.c.agent_id == agent_id)
        .order_by(vs.c.name, st.c.position, st.c.name)
    )
    stages = [
        AutomatesStage(
            id=r.id, name=r.name, value_stream_id=r.value_stream_id, value_stream_name=r.vs_name
        )
        for r in stage_rows
    ]

    act, ch, al = _activities_mirror, _value_chains_mirror, _agent_activity_links
    primary_first = sa.case((act.c.category == "primary", 0), else_=1)
    act_rows = await session.execute(
        sa.select(act.c.id, act.c.name, act.c.category, act.c.value_chain_id,
                  ch.c.name.label("ch_name"))
        .select_from(
            al.join(act, act.c.id == al.c.activity_id).join(ch, ch.c.id == act.c.value_chain_id)
        )
        .where(al.c.agent_id == agent_id)
        .order_by(ch.c.name, primary_first, act.c.position, act.c.name)
    )
    activities = [
        AutomatesActivity(
            id=r.id, name=r.name, category=r.category, value_chain_id=r.value_chain_id,
            value_chain_name=r.ch_name,
        )
        for r in act_rows
    ]
    return AgentAutomates(capabilities=capabilities, stages=stages, activities=activities)


async def add_link(
    kind: AutomatesKind, agent_id: str, target_id: str, session: AsyncSession
) -> AgentAutomates:
    await _require_agent(agent_id, session)
    target = await _require_target(kind, target_id, session)
    if kind == "capability" and target.level != 3:
        raise LevelRuleError(
            f"Agents automate business capabilities at L3 only; {target.name!r} is L{target.level}"
        )
    table, col, _mirror = _LINKS[kind]
    exists = await session.execute(
        sa.select(table.c.agent_id).where(table.c.agent_id == agent_id, table.c[col] == target_id)
    )
    if exists.first() is not None:
        raise DuplicateLinkError(
            f"Agent {agent_id!r} already automates {kind} {target_id!r}"
        )
    await session.execute(
        table.insert().values(agent_id=agent_id, created_at=_now(), **{col: target_id})
    )
    return await get_automates(agent_id, session)


async def remove_link(
    kind: AutomatesKind, agent_id: str, target_id: str, session: AsyncSession
) -> None:
    table, col, _mirror = _LINKS[kind]
    result = await session.execute(
        table.delete().where(table.c.agent_id == agent_id, table.c[col] == target_id)
    )
    if _rowcount(result) == 0:
        raise LinkNotFoundError(f"Agent {agent_id!r} does not automate {kind} {target_id!r}")


async def list_agents_for(
    kind: AutomatesKind, target_id: str, session: AsyncSession
) -> list[AgentSummary]:
    """Reverse lookup: the agents that automate a capability, stage or activity, by name."""
    await _require_target(kind, target_id, session)
    table, col, _mirror = _LINKS[kind]
    result = await session.execute(
        sa.select(_agents)
        .select_from(table.join(_agents, _agents.c.id == table.c.agent_id))
        .where(table.c[col] == target_id)
        .order_by(_agents.c.name, _agents.c.id)
    )
    return [
        AgentSummary(
            id=r.id,
            name=r.name,
            lifecycle_status=r.lifecycle_status,
            autonomy_level=r.autonomy_level,
            agentic_risk=agent_risk(r.autonomy_level, r.human_approval, r.data_classification_max),
        )
        for r in result
    ]
