"""942-regional-assessments: the regional store on SQLite.

Assessments (US1), region-specific scope (US2) and delete cleanup. Capabilities go straight into
the organization store's narrow ``business_capabilities`` mirror, with a baseline maturity.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
import sqlalchemy as sa
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.organization import regional
from adp.organization import store as ostore
from adp.organization.geodata import geography_seed_rows
from adp.organization.models import (
    GeographyCreate,
    LevelRuleError,
    OrgNotFoundError,
    SetRegionalAssessment,
    SetRegionScope,
    UnknownReferenceError,
)

NOW = datetime(2026, 11, 16, tzinfo=timezone.utc)
EU, BR, DE, GLOBAL = "geo-m49-150", "geo-BR", "geo-DE", "geo-001"


@pytest.fixture()
async def session(tmp_path, monkeypatch):
    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr(ostore, "index_entity", _noop)
    monkeypatch.setattr(ostore, "unindex_entity", _noop)
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/regional.db")
    async with engine.begin() as conn:
        await conn.run_sync(ostore._metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        await s.execute(ostore._geographies.insert(), geography_seed_rows(NOW))
        for cid, name, level, parent, baseline in [
            ("sell", "Sell", 1, None, 3),
            ("pay", "Payments", 2, "sell", None),
            ("accept", "Accept Payment", 3, "pay", 3),
        ]:
            await s.execute(
                ostore._business_capabilities.insert().values(
                    id=cid,
                    name=name,
                    level=level,
                    parent_id=parent,
                    position=0,
                    maturity_level=baseline,
                )
            )
        yield s
    await engine.dispose()


def _set(m: int | None = None, note: str | None = None) -> SetRegionalAssessment:
    return SetRegionalAssessment(maturity_level=m, note=note)  # type: ignore[arg-type]


async def _baseline(s, cap_id: str) -> int | None:
    b = ostore._business_capabilities
    return (await s.execute(sa.select(b.c.maturity_level).where(b.c.id == cap_id))).scalar_one()


async def _count(s, table: sa.Table) -> int:
    return int((await s.execute(sa.select(sa.func.count()).select_from(table))).scalar_one())


class TestAssessments:
    async def test_record_region_and_country(self, session) -> None:
        eu, created = await regional.set_assessment("accept", EU, _set(4), session)
        assert created and eu.maturity_level == 4 and eu.geography.name == "Europe"
        br, _ = await regional.set_assessment("accept", BR, _set(2, "Manual"), session)
        assert (br.maturity_level, br.note, br.geography.code) == (2, "Manual", "BR")

    async def test_recording_again_changes_the_same_row(self, session) -> None:
        first, _ = await regional.set_assessment("accept", EU, _set(4), session)
        second, created = await regional.set_assessment("accept", EU, _set(5, "Better"), session)
        assert not created and second.id == first.id and second.maturity_level == 5
        assert second.updated_at >= first.updated_at
        assert await _count(session, ostore._capability_regional_assessments) == 1

    async def test_note_only_and_blank_note(self, session) -> None:
        a, _ = await regional.set_assessment("accept", DE, _set(None, "Varies by state"), session)
        assert a.maturity_level is None and a.note == "Varies by state"
        assert SetRegionalAssessment(maturity_level=3, note="   ").note is None

    async def test_rules(self, session) -> None:
        with pytest.raises(LevelRuleError, match="baseline"):
            await regional.set_assessment("accept", GLOBAL, _set(3), session)
        with pytest.raises(ValidationError, match="score, a note, or both"):
            SetRegionalAssessment()
        with pytest.raises(ValidationError):
            SetRegionalAssessment(maturity_level=6)  # type: ignore[arg-type]
        with pytest.raises(ValidationError):
            SetRegionalAssessment(note="x" * 1001)
        with pytest.raises(OrgNotFoundError):
            await regional.set_assessment("nope", EU, _set(3), session)
        with pytest.raises(OrgNotFoundError):
            await regional.set_assessment("accept", "geo-ZZ", _set(3), session)

    async def test_remove(self, session) -> None:
        await regional.set_assessment("accept", EU, _set(4), session)
        await regional.remove_assessment("accept", EU, session)
        assert await _count(session, ostore._capability_regional_assessments) == 0
        with pytest.raises(OrgNotFoundError):
            await regional.remove_assessment("accept", EU, session)

    async def test_list_filters_and_sorts(self, session) -> None:
        await regional.set_assessment("accept", EU, _set(4), session)
        await regional.set_assessment("accept", BR, _set(2), session)
        await regional.set_assessment("pay", DE, _set(1), session)
        listed = await regional.list_assessments(session, capability_id="accept")
        assert listed.total == 2
        assert [a.geography.name for a in listed.items] == ["Brazil", "Europe"]
        assert (await regional.list_assessments(session)).total == 3

    async def test_baseline_is_never_written(self, session) -> None:
        await regional.set_assessment("accept", EU, _set(5), session)
        await regional.set_assessment("accept", BR, _set(1), session)
        await regional.remove_assessment("accept", BR, session)
        assert await _baseline(session, "accept") == 3
        assert await _baseline(session, "pay") is None


class TestScope:
    async def test_set_replace_and_clear(self, session) -> None:
        scope = await regional.set_scope(
            "accept", SetRegionScope(region_specific=True, geography_ids=[BR, DE]), session
        )
        assert scope.region_specific and [g.name for g in scope.geographies] == [
            "Brazil",
            "Germany",
        ]
        scope = await regional.set_scope(
            "accept", SetRegionScope(region_specific=True, geography_ids=[BR]), session
        )
        assert [g.id for g in scope.geographies] == [BR]
        scope = await regional.set_scope("accept", SetRegionScope(region_specific=False), session)
        assert not scope.region_specific and scope.geographies == []
        assert await _count(session, ostore._region_specific_capabilities) == 0
        assert await _count(session, ostore._region_specific_capability_geographies) == 0

    async def test_scope_rules(self, session) -> None:
        with pytest.raises(ValidationError, match="at least one geography"):
            SetRegionScope(region_specific=True, geography_ids=[])
        with pytest.raises(ValidationError, match="only be set"):
            SetRegionScope(region_specific=False, geography_ids=[BR])
        with pytest.raises(LevelRuleError):
            await regional.set_scope(
                "accept", SetRegionScope(region_specific=True, geography_ids=[GLOBAL]), session
            )
        with pytest.raises(UnknownReferenceError):
            await regional.set_scope(
                "accept", SetRegionScope(region_specific=True, geography_ids=["geo-ZZ"]), session
            )
        with pytest.raises(OrgNotFoundError):
            await regional.get_scope("nope", session)

    async def test_unflagged_scope(self, session) -> None:
        scope = await regional.get_scope("accept", session)
        assert (scope.region_specific, scope.geographies, scope.scope_needs_update) == (
            False,
            [],
            False,
        )


class TestDeletes:
    async def test_deleting_a_geography_removes_its_rows_and_keeps_the_flag(self, session) -> None:
        geo = await ostore.create_geography(
            GeographyCreate(name="Scratchland", code="XQ", parent_id=EU), session
        )
        await regional.set_assessment("accept", geo.id, _set(2), session)
        await regional.set_scope(
            "accept", SetRegionScope(region_specific=True, geography_ids=[geo.id]), session
        )
        await ostore.delete_geography(geo.id, session)
        assert await _count(session, ostore._capability_regional_assessments) == 0
        scope = await regional.get_scope("accept", session)
        assert scope.region_specific and scope.geographies == [] and scope.scope_needs_update

    async def test_rows_for_a_missing_capability_never_surface(self, session) -> None:
        await regional.set_assessment("accept", EU, _set(4), session)
        await session.execute(
            ostore._business_capabilities.delete().where(
                ostore._business_capabilities.c.id == "accept"
            )
        )
        assert (await regional.list_assessments(session)).total == 0
        h = await regional.get_heatmap(None, session)
        assert all(r.capability.id != "accept" for r in h.rows)
