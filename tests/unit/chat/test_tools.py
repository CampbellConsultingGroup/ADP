"""Unit tests: adp.chat.tools's read-only TOOL_REGISTRY (ADP-SPEC-041 US2).

Covers T026: a sensitive-category handler (get_application_{risk,cost,
governance}) returns {"permitted": False} for a role that lacks the matching
READ_APPLICATION_* permission -- never an error, never a silently-empty
result that could be mistaken for "no data exists" (research D5). Also
covers the non-sensitive get_capability/get_application handlers and
dispatch_tool's unknown-tool path.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.application import store as astore
from adp.authz.roles import PersonaRole
from adp.business import store as bstore
from adp.chat import tools as chat_tools


@pytest.fixture()
async def sessions(tmp_path):
    biz_engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/biz.db")
    async with biz_engine.begin() as conn:
        await conn.run_sync(bstore._metadata.create_all)
    app_engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/app.db")
    async with app_engine.begin() as conn:
        await conn.run_sync(astore._metadata.create_all)

    biz_factory = async_sessionmaker(biz_engine, expire_on_commit=False)
    app_factory = async_sessionmaker(app_engine, expire_on_commit=False)
    yield biz_factory, app_factory
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


async def test_get_capability_found_and_not_found(sessions):
    biz_factory, _ = sessions
    await _mk_capability(biz_factory, "CAP-1")

    async with biz_factory() as session:
        found = await chat_tools.get_capability(
            {"capability_id": "CAP-1"}, PersonaRole.ENTERPRISE_ARCHITECT, biz_session=session
        )
        missing = await chat_tools.get_capability(
            {"capability_id": "NOPE"}, PersonaRole.ENTERPRISE_ARCHITECT, biz_session=session
        )

    assert found["found"] is True
    assert found["capability"]["id"] == "CAP-1"
    assert missing == {"found": False}


async def test_get_application_found_and_not_found(sessions):
    _, app_factory = sessions
    await _mk_application(app_factory, "APP-1")

    async with app_factory() as session:
        found = await chat_tools.get_application(
            {"application_id": "APP-1"}, PersonaRole.ENTERPRISE_ARCHITECT, app_session=session
        )
        missing = await chat_tools.get_application(
            {"application_id": "NOPE"}, PersonaRole.ENTERPRISE_ARCHITECT, app_session=session
        )

    assert found["found"] is True
    assert found["application"]["id"] == "APP-1"
    assert missing == {"found": False}


@pytest.mark.parametrize(
    "handler",
    [chat_tools.get_application_risk, chat_tools.get_application_cost,
     chat_tools.get_application_governance],
)
async def test_sensitive_handlers_deny_unauthorized_role(sessions, handler):
    """REVIEWER holds USE_CHAT_ASSISTANT but none of the READ_APPLICATION_*
    sensitive-category permissions -- the handler must short-circuit to
    {"permitted": False} without ever touching the database."""
    _, app_factory = sessions
    async with app_factory() as session:
        result = await handler(
            {"application_id": "APP-1"}, PersonaRole.REVIEWER, app_session=session
        )
    assert result == {"permitted": False}


@pytest.mark.parametrize(
    "handler",
    [chat_tools.get_application_risk, chat_tools.get_application_cost,
     chat_tools.get_application_governance],
)
async def test_sensitive_handlers_permit_authorized_role_with_no_data(sessions, handler):
    """Distinct from the denied case: an authorized role with no risk/cost/
    governance row yet gets {"permitted": True, "found": False} -- "I have
    access but there's nothing there" is never conflated with "you can't
    see this" (research D5)."""
    _, app_factory = sessions
    await _mk_application(app_factory, "APP-1")
    async with app_factory() as session:
        result = await handler(
            {"application_id": "APP-1"}, PersonaRole.ENTERPRISE_ARCHITECT, app_session=session
        )
    assert result == {"permitted": True, "found": False}


async def test_dispatch_tool_unknown_name_returns_error_not_raise(sessions):
    biz_factory, app_factory = sessions
    async with biz_factory() as biz_session, app_factory() as app_session:
        result = await chat_tools.dispatch_tool(
            "not_a_real_tool", {}, PersonaRole.ENTERPRISE_ARCHITECT,
            sessions={"biz_session": biz_session, "app_session": app_session},
        )
    assert "error" in result


async def test_dispatch_tool_routes_to_matching_handler(sessions):
    biz_factory, app_factory = sessions
    await _mk_capability(biz_factory, "CAP-1")
    async with biz_factory() as biz_session, app_factory() as app_session:
        result = await chat_tools.dispatch_tool(
            "get_capability", {"capability_id": "CAP-1"}, PersonaRole.ENTERPRISE_ARCHITECT,
            sessions={"biz_session": biz_session, "app_session": app_session},
        )
    assert result["found"] is True


def test_anthropic_tool_specs_cover_the_whole_registry():
    specs = chat_tools.anthropic_tool_specs()
    names = {s["name"] for s in specs}
    assert names == {t.name for t in chat_tools.TOOL_REGISTRY}
    assert all({"name", "description", "input_schema"} == set(s) for s in specs)
