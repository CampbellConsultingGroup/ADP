"""Unit tests: 925-strategy-compliance-linkage (COMPLY-05) -- ObjectiveControlMapping
(adp.strategy.store) and InitiativeControlMapping (adp.strategy.initiatives) against in-memory
SQLite, mirroring test_strategy_store.py's/test_initiatives_store.py's exact fixture convention.

`initiatives.py` shares `store.py`'s `_metadata` (research.md D2), so
`sstore._metadata.create_all` already creates every table this file needs, including the new
read-only compliance-schema mirrors (_controls_mirror, five control_*_mapping mirrors) and the
new join tables -- this file adds its own composite-PK unique-index DDL for the join tables
(store metadata omits PK/FK constraints; those live only in the migration) and seeds the mirror
tables directly (standing in for a real COMPLY-01/02 write, which this package never performs).
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.compliance.models import MappingTargetType
from adp.strategy import initiatives as sinit
from adp.strategy import store as sstore
from adp.strategy.initiatives import StrategyInitiativeCreate
from adp.strategy.models import StrategicObjectiveCreate, StrategicThemeCreate

_UNIQUE_DDL = [
    "CREATE UNIQUE INDEX uq_theme_name ON strategic_themes(name)",
    "CREATE UNIQUE INDEX uq_iccm "
    "ON initiative_control_capability_mapping(initiative_id, control_id, capability_id)",
    "CREATE UNIQUE INDEX uq_ocl ON objective_control_links(objective_id, control_id)",
]


@pytest.fixture()
async def session(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/strategy_control_links.db")
    async with engine.begin() as conn:
        await conn.run_sync(sstore._metadata.create_all)
        for ddl in _UNIQUE_DDL:
            await conn.execute(sa.text(ddl))
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def _mk_objective(session, name="Objective") -> str:
    theme = await sstore.create_theme(StrategicThemeCreate(name=f"Theme-{name}"), session)
    await session.commit()
    created = await sstore.create_objective(
        StrategicObjectiveCreate(
            theme_id=theme.id, owner="Owner", statement=name, fiscal_year=2026, period="Q1",
        ),
        session,
    )
    await session.commit()
    return created.id


async def _mk_initiative(session, name="Initiative") -> str:
    created = await sinit.create_initiative(StrategyInitiativeCreate(name=name), session)
    await session.commit()
    return created.id


async def _mk_control(session, control_id="CTRL-1") -> str:
    """Seeds the _controls_mirror table directly, standing in for a real COMPLY-01 write."""
    await session.execute(
        sstore._controls_mirror.insert().values(
            id=control_id, code="AC-2", title="Account Management", framework_id="FW-1"
        )
    )
    await session.commit()
    return control_id


async def _mk_capability_mapping(
    session, control_id: str, capability_id: str = "CAP-1", status: str = "non_compliant"
) -> None:
    """Seeds the _control_capability_mapping_mirror table directly, standing in for a real
    COMPLY-02 write (adp.compliance.store.upsert_capability_mapping)."""
    await session.execute(
        sstore._control_capability_mapping_mirror.insert().values(
            control_id=control_id, capability_id=capability_id, compliance_status=status,
            evidence_ref=None, assessed_at=None,
        )
    )
    await session.commit()


class TestControlExists:
    """T004 -- Foundational: control_exists() mirrors design_exists()/application_exists()."""

    async def test_control_exists_true(self, session):
        control_id = await _mk_control(session)
        assert await sstore.control_exists(control_id, session) is True

    async def test_control_exists_false(self, session):
        assert await sstore.control_exists("does-not-exist", session) is False


class TestLinkInitiativeControlMapping:
    """T005 -- US1: link_initiative_control_mapping()/unlink_initiative_control_mapping()/
    _linked_control_mappings()."""

    async def test_link_raises_when_no_control_mapping_exists(self, session):
        initiative_id = await _mk_initiative(session)
        control_id = await _mk_control(session)
        # No _control_capability_mapping_mirror row seeded for (control_id, "CAP-1") -- this
        # Control has never been assessed against this target.
        with pytest.raises(sinit.ControlMappingNotFoundError):
            await sinit.link_initiative_control_mapping(
                initiative_id, control_id, MappingTargetType.CAPABILITY, "CAP-1", session
            )

    async def test_link_then_duplicate_raises(self, session):
        initiative_id = await _mk_initiative(session)
        control_id = await _mk_control(session)
        await _mk_capability_mapping(session, control_id, "CAP-1")

        await sinit.link_initiative_control_mapping(
            initiative_id, control_id, MappingTargetType.CAPABILITY, "CAP-1", session
        )
        await session.commit()

        with pytest.raises(sinit.DuplicateLinkError):
            await sinit.link_initiative_control_mapping(
                initiative_id, control_id, MappingTargetType.CAPABILITY, "CAP-1", session
            )

    async def test_unlink_raises_when_not_linked(self, session):
        initiative_id = await _mk_initiative(session)
        control_id = await _mk_control(session)
        with pytest.raises(sinit.LinkNotFoundError):
            await sinit.unlink_initiative_control_mapping(
                initiative_id, control_id, MappingTargetType.CAPABILITY, "CAP-1", session
            )

    async def test_unlink_removes_link(self, session):
        initiative_id = await _mk_initiative(session)
        control_id = await _mk_control(session)
        await _mk_capability_mapping(session, control_id, "CAP-1")
        await sinit.link_initiative_control_mapping(
            initiative_id, control_id, MappingTargetType.CAPABILITY, "CAP-1", session
        )
        await session.commit()

        await sinit.unlink_initiative_control_mapping(
            initiative_id, control_id, MappingTargetType.CAPABILITY, "CAP-1", session
        )
        await session.commit()

        refs = await sinit._linked_control_mappings(initiative_id, session)
        assert refs == []

    async def test_linked_control_mappings_reflects_live_status(self, session):
        """FR-008 / research.md D3: the link table carries no status of its own -- updating the
        underlying mirrored row (simulating a real COMPLY-02 write) changes what
        _linked_control_mappings() returns with zero writes to the link table itself."""
        initiative_id = await _mk_initiative(session)
        control_id = await _mk_control(session)
        await _mk_capability_mapping(session, control_id, "CAP-1", status="non_compliant")
        await sinit.link_initiative_control_mapping(
            initiative_id, control_id, MappingTargetType.CAPABILITY, "CAP-1", session
        )
        await session.commit()

        refs = await sinit._linked_control_mappings(initiative_id, session)
        assert len(refs) == 1
        assert refs[0].compliance_status == "non_compliant"
        assert refs[0].target_type == MappingTargetType.CAPABILITY
        assert refs[0].target_id == "CAP-1"

        # Simulate a COMPLY-02 re-assessment -- a direct UPDATE against the mirrored physical
        # table, standing in for adp.compliance.store.upsert_capability_mapping().
        await session.execute(
            sstore._control_capability_mapping_mirror.update()
            .where(
                sstore._control_capability_mapping_mirror.c.control_id == control_id,
                sstore._control_capability_mapping_mirror.c.capability_id == "CAP-1",
            )
            .values(compliance_status="compliant")
        )
        await session.commit()

        refs = await sinit._linked_control_mappings(initiative_id, session)
        assert refs[0].compliance_status == "compliant"

    async def test_organization_target_has_no_target_id(self, session):
        initiative_id = await _mk_initiative(session)
        control_id = await _mk_control(session)
        await session.execute(
            sstore._control_organization_mapping_mirror.insert().values(
                control_id=control_id, compliance_status="partial", evidence_ref=None,
                assessed_at=None,
            )
        )
        await session.commit()

        await sinit.link_initiative_control_mapping(
            initiative_id, control_id, MappingTargetType.ORGANIZATION, None, session
        )
        await session.commit()

        refs = await sinit._linked_control_mappings(initiative_id, session)
        assert len(refs) == 1
        assert refs[0].target_type == MappingTargetType.ORGANIZATION
        assert refs[0].target_id is None


class TestListInitiativesForControlMapping:
    """T005 (cont.) -- reverse lookup used by adp.compliance.router."""

    async def test_returns_linked_initiatives(self, session):
        initiative_id = await _mk_initiative(session, "Remediate MFA gap")
        control_id = await _mk_control(session)
        await _mk_capability_mapping(session, control_id, "CAP-1")
        await sinit.link_initiative_control_mapping(
            initiative_id, control_id, MappingTargetType.CAPABILITY, "CAP-1", session
        )
        await session.commit()

        response = await sinit.list_initiatives_for_control_mapping(
            control_id, MappingTargetType.CAPABILITY, "CAP-1", session
        )
        assert response.total == 1
        assert response.items[0].id == initiative_id

    async def test_returns_empty_when_no_initiatives_linked(self, session):
        control_id = await _mk_control(session)
        await _mk_capability_mapping(session, control_id, "CAP-1")
        response = await sinit.list_initiatives_for_control_mapping(
            control_id, MappingTargetType.CAPABILITY, "CAP-1", session
        )
        assert response.total == 0


class TestLinkObjectiveControl:
    """T020 -- US2: link_objective_control()/unlink_objective_control()."""

    async def test_link_then_duplicate_raises(self, session):
        objective_id = await _mk_objective(session)
        control_id = await _mk_control(session)

        await sstore.link_objective_control(objective_id, control_id, session)
        await session.commit()

        with pytest.raises(sstore.DuplicateLinkError):
            await sstore.link_objective_control(objective_id, control_id, session)

    async def test_unlink_raises_when_not_linked(self, session):
        objective_id = await _mk_objective(session)
        control_id = await _mk_control(session)
        with pytest.raises(sstore.LinkNotFoundError):
            await sstore.unlink_objective_control(objective_id, control_id, session)

    async def test_link_then_unlink_removes_it(self, session):
        objective_id = await _mk_objective(session)
        control_id = await _mk_control(session)

        await sstore.link_objective_control(objective_id, control_id, session)
        await session.commit()
        objective = await sstore.get_objective(objective_id, session)
        assert objective is not None
        assert objective.control_ids == [control_id]

        await sstore.unlink_objective_control(objective_id, control_id, session)
        await session.commit()
        objective = await sstore.get_objective(objective_id, session)
        assert objective is not None
        assert objective.control_ids == []

    async def test_list_objectives_for_control_returns_linked(self, session):
        objective_id = await _mk_objective(session, "Regulatory readiness")
        control_id = await _mk_control(session)
        await sstore.link_objective_control(objective_id, control_id, session)
        await session.commit()

        response = await sstore.list_objectives_for_control(control_id, session)
        assert response.total == 1
        assert response.items[0].id == objective_id

    async def test_list_objectives_for_control_empty_when_none_linked(self, session):
        control_id = await _mk_control(session)
        response = await sstore.list_objectives_for_control(control_id, session)
        assert response.total == 0
