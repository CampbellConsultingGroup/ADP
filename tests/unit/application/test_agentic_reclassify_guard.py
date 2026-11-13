"""933-agent-registry (Clarification Q1): an agentic application with agents cannot be
reclassified, and deleting an application removes its agent memberships (never the agents).

Uses adp.application.store's narrow solution_agents mirror on a SQLite fixture.
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.application import store as astore
from adp.application.models import (
    AgenticSolutionHasAgentsError,
    ApplicationCreate,
    ApplicationUpdate,
)


@pytest.fixture()
async def session(tmp_path, monkeypatch):
    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr(astore, "index_entity", _noop)
    monkeypatch.setattr(astore, "unindex_entity", _noop)
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/guard.db")
    async with engine.begin() as conn:
        await conn.run_sync(astore._metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def _agentic_app(session, with_agents: int = 0) -> str:
    app = await astore.create_application(
        ApplicationCreate(name="Claims", application_type="agentic"), session
    )
    for i in range(with_agents):
        await session.execute(
            astore._solution_agents.insert().values(solution_app_id=app.id, agent_id=f"ag-{i}")
        )
    return app.id


async def test_reclassify_blocked_while_agents_exist(session):
    app_id = await _agentic_app(session, with_agents=2)
    with pytest.raises(AgenticSolutionHasAgentsError) as exc:
        await astore.update_application(
            app_id, ApplicationUpdate(application_type="custom"), session
        )
    assert exc.value.agent_count == 2
    with pytest.raises(AgenticSolutionHasAgentsError):
        await astore.update_application(app_id, ApplicationUpdate(application_type=None), session)


async def test_reclassify_allowed_without_agents(session):
    app_id = await _agentic_app(session)
    updated = await astore.update_application(
        app_id, ApplicationUpdate(application_type="custom"), session
    )
    assert updated is not None and updated.application_type == "custom"


async def test_unrelated_update_and_same_type_unaffected(session):
    app_id = await _agentic_app(session, with_agents=1)
    renamed = await astore.update_application(app_id, ApplicationUpdate(name="Claims v2"), session)
    assert renamed is not None and renamed.application_type == "agentic"
    same = await astore.update_application(
        app_id, ApplicationUpdate(application_type="agentic"), session
    )
    assert same is not None


async def test_delete_application_removes_memberships_only(session):
    app_id = await _agentic_app(session, with_agents=2)
    other = await _agentic_app(session, with_agents=0)
    await session.execute(
        astore._solution_agents.insert().values(solution_app_id=other, agent_id="ag-0")
    )
    assert await astore.delete_application(app_id, session) is True
    remaining = (
        await session.execute(sa.select(astore._solution_agents.c.solution_app_id))
    ).scalars().all()
    assert remaining == [other]
