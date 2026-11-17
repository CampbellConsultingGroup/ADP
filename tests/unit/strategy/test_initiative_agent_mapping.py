"""ADP-321: initiative <-> control-mapping linkage (925) covers every mapping target, including
944's agent. Replaces 944's guard test_initiative_agent_excluded.py.
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.compliance.models import MappingTargetType
from adp.strategy import initiatives as sinit
from adp.strategy import store as sstore
from adp.strategy.initiatives import StrategyInitiativeCreate


def test_every_mapping_target_has_an_initiative_link():
    assert set(sinit._LINK_TABLE_BY_TARGET_TYPE) == set(MappingTargetType)
    assert set(sinit._MIRROR_BY_TARGET_TYPE) == set(MappingTargetType)
    table, col = sinit._LINK_TABLE_BY_TARGET_TYPE[MappingTargetType.AGENT]
    assert (table.name, col) == ("initiative_control_agent_mapping", "agent_id")


@pytest.fixture()
async def session(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/initiative_agent.db")
    async with engine.begin() as conn:
        await conn.run_sync(sstore._metadata.create_all)
        await conn.execute(
            sa.text(
                "CREATE UNIQUE INDEX uq_icagm ON initiative_control_agent_mapping"
                "(initiative_id, control_id, agent_id)"
            )
        )
        await conn.execute(
            sstore._controls_mirror.insert().values(
                id="CTRL-1", code="Art. 50", title="Transparency", framework_id="FW-1"
            )
        )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def _mapping(session, status: str) -> None:
    await session.execute(
        sstore._control_agent_mapping_mirror.insert().values(
            control_id="CTRL-1", agent_id="AG-1", compliance_status=status
        )
    )
    await session.commit()


async def test_link_agent_mapping_round_trip(session):
    ini = (await sinit.create_initiative(StrategyInitiativeCreate(name="Fix"), session)).id
    with pytest.raises(sinit.ControlMappingNotFoundError):
        await sinit.link_initiative_control_mapping(
            ini, "CTRL-1", MappingTargetType.AGENT, "AG-1", session
        )
    await _mapping(session, "non_compliant")
    await sinit.link_initiative_control_mapping(
        ini, "CTRL-1", MappingTargetType.AGENT, "AG-1", session
    )
    await session.commit()

    got = await sinit.get_initiative(ini, session)
    assert got is not None
    [ref] = got.control_mappings
    assert (ref.target_type, ref.target_id, ref.compliance_status) == (
        MappingTargetType.AGENT, "AG-1", "non_compliant",
    )
    found = await sinit.list_initiatives_for_control_mapping(
        "CTRL-1", MappingTargetType.AGENT, "AG-1", session
    )
    assert [i.id for i in found.items] == [ini]

    with pytest.raises(sinit.DuplicateLinkError):
        await sinit.link_initiative_control_mapping(
            ini, "CTRL-1", MappingTargetType.AGENT, "AG-1", session
        )
    await session.rollback()
    await sinit.unlink_initiative_control_mapping(
        ini, "CTRL-1", MappingTargetType.AGENT, "AG-1", session
    )
    with pytest.raises(sinit.LinkNotFoundError):
        await sinit.unlink_initiative_control_mapping(
            ini, "CTRL-1", MappingTargetType.AGENT, "AG-1", session
        )
