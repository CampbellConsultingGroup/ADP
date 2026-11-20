"""941-capability-org-mappings: the mapping store on SQLite.

Owners (US1), performers and contributors (US2), and delete cleanup (R3). The capability tree is
inserted straight into the organization store's narrow ``business_capabilities`` mirror.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.organization import cap_mappings as cm
from adp.organization import store as ostore
from adp.organization.models import (
    AddMapping,
    DuplicateLinkError,
    LevelRuleError,
    OrgNotFoundError,
    OrgUnitCreate,
    UnknownReferenceError,
)

NOW = datetime(2026, 11, 16, tzinfo=timezone.utc)


@pytest.fixture()
async def session(tmp_path, monkeypatch):
    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr(ostore, "index_entity", _noop)
    monkeypatch.setattr(ostore, "unindex_entity", _noop)
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/capmap.db")
    async with engine.begin() as conn:
        await conn.run_sync(ostore._metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        await ostore.seed_geography(s, NOW)
        for cid, name, level, parent in [
            ("sell", "Sell", 1, None),
            ("pay", "Payments", 2, "sell"),
            ("accept", "Accept Payment", 3, "pay"),
        ]:
            await s.execute(
                ostore._business_capabilities.insert().values(
                    id=cid, name=name, level=level, parent_id=parent, position=0
                )
            )
        yield s
    await engine.dispose()


async def _ou(s, name: str, parent: str | None = None) -> str:
    return (await ostore.create_org_unit(OrgUnitCreate(name=name, parent_id=parent), s)).id


async def _rows(s) -> list[tuple[str, str, str, str | None]]:
    t = ostore._capability_org_mappings
    rows = await s.execute(
        sa.select(t.c.capability_id, t.c.org_unit_id, t.c.role, t.c.geography_id).order_by(
            t.c.capability_id, t.c.role, t.c.geography_id
        )
    )
    return [tuple(r) for r in rows]


def _perf(cap: str, ou: str, geo: str | None = None, role: str = "performer") -> AddMapping:
    return AddMapping(capability_id=cap, org_unit_id=ou, role=role, geography_id=geo)  # type: ignore[arg-type]


class TestOwner:
    async def test_set_replace_and_clear(self, session) -> None:
        a, b = await _ou(session, "Supply Chain"), await _ou(session, "Logistics")
        view, previous = await cm.set_owner("pay", a, session)
        assert view.owner is not None and view.owner.id == a and previous is None
        view, previous = await cm.set_owner("pay", b, session)
        assert view.owner is not None and view.owner.id == b and previous == a
        assert [r for r in await _rows(session) if r[2] == "owner"] == [("pay", b, "owner", None)]
        view, previous = await cm.set_owner("pay", None, session)
        assert view.owner is None and previous == b
        assert await _rows(session) == []

    async def test_same_owner_again_is_a_no_op(self, session) -> None:
        a = await _ou(session, "Supply Chain")
        await cm.set_owner("sell", a, session)
        view, previous = await cm.set_owner("sell", a, session)
        assert previous == a and view.owner is not None and view.owner.id == a
        assert len(await _rows(session)) == 1

    async def test_l3_refused(self, session) -> None:
        a = await _ou(session, "Supply Chain")
        with pytest.raises(LevelRuleError, match="Owners are set at L2 or L1, not L3"):
            await cm.set_owner("accept", a, session)

    async def test_unknown_capability_and_org_unit(self, session) -> None:
        with pytest.raises(OrgNotFoundError):
            await cm.set_owner("nope", None, session)
        with pytest.raises(UnknownReferenceError):
            await cm.set_owner("pay", "no-such-unit", session)

    async def test_list_views_shows_inherited_owner(self, session) -> None:
        a = await _ou(session, "Supply Chain")
        await cm.set_owner("pay", a, session)
        views = {v.capability_id: v for v in (await cm.list_views(session)).items}
        assert views["accept"].effective_owner is not None
        assert views["accept"].owner_inherited_from is not None
        assert views["accept"].owner_inherited_from.id == "pay"

    async def test_db_allows_one_owner_only(self, session) -> None:
        a, b = await _ou(session, "A"), await _ou(session, "B")
        t = ostore._capability_org_mappings
        await session.execute(
            t.insert().values(
                id="x1", capability_id="pay", org_unit_id=a, role="owner", created_at=NOW
            )
        )
        with pytest.raises(IntegrityError):
            await session.execute(
                t.insert().values(
                    id="x2", capability_id="pay", org_unit_id=b, role="owner", created_at=NOW
                )
            )


class TestPerformers:
    async def test_add_with_and_without_geography(self, session) -> None:
        st = await _ou(session, "Stores")
        everywhere = await cm.add_mapping(_perf("accept", st), session)
        de = await cm.add_mapping(_perf("accept", st, "geo-DE"), session)
        assert everywhere.geography is None
        assert de.geography is not None and de.geography.name == "Germany"
        assert len(await _rows(session)) == 2

    async def test_exact_duplicate_refused(self, session) -> None:
        st = await _ou(session, "Stores")
        await cm.add_mapping(_perf("accept", st), session)
        with pytest.raises(DuplicateLinkError):
            await cm.add_mapping(_perf("accept", st), session)
        await cm.add_mapping(_perf("accept", st, "geo-DE"), session)
        with pytest.raises(DuplicateLinkError):
            await cm.add_mapping(_perf("accept", st, "geo-DE"), session)

    async def test_wrong_level_refused(self, session) -> None:
        st = await _ou(session, "Stores")
        for cap in ("sell", "pay"):
            for role in ("performer", "contributor"):
                with pytest.raises(
                    LevelRuleError, match="Performers and contributors are mapped at L3"
                ):
                    await cm.add_mapping(_perf(cap, st, role=role), session)

    async def test_contributor_cannot_name_a_geography(self) -> None:
        with pytest.raises(ValueError, match="Only performers"):
            _perf("accept", "x", "geo-DE", role="contributor")

    async def test_unknown_references(self, session) -> None:
        st = await _ou(session, "Stores")
        with pytest.raises(OrgNotFoundError):
            await cm.add_mapping(_perf("nope", st), session)
        with pytest.raises(UnknownReferenceError):
            await cm.add_mapping(_perf("accept", "nope"), session)
        with pytest.raises(UnknownReferenceError):
            await cm.add_mapping(_perf("accept", st, "geo-ZZ"), session)

    async def test_remove(self, session) -> None:
        st = await _ou(session, "Stores")
        added = await cm.add_mapping(_perf("accept", st, role="contributor"), session)
        removed = await cm.remove_mapping(added.id, session)
        assert removed.org_unit_id == st and removed.role == "contributor"
        assert await _rows(session) == []
        with pytest.raises(OrgNotFoundError):
            await cm.remove_mapping(added.id, session)


async def _node(session) -> str:
    """946: only nodes can be deleted (countries are read-only places)."""
    from adp.organization import hierarchies
    from adp.organization.models import GeoHierarchyCreate, GeoNodeCreate

    h = await hierarchies.create_hierarchy(
        GeoHierarchyCreate(name="Scratch", kind="custom", shape="dag"), session
    )
    return (await hierarchies.create_node(h.id, GeoNodeCreate(name="Scratchland"), session)).id


class TestDeletes:
    async def test_deleting_an_org_unit_removes_its_mappings_and_owner_falls_back(
        self, session
    ) -> None:
        rc = await _ou(session, "Retail Co")
        st = await _ou(session, "Stores", rc)
        await cm.set_owner("sell", rc, session)
        await cm.set_owner("pay", st, session)
        await cm.add_mapping(_perf("accept", st), session)
        await ostore.delete_org_unit(st, session)
        assert await _rows(session) == [("sell", rc, "owner", None)]
        views = {v.capability_id: v for v in (await cm.list_views(session)).items}
        assert views["pay"].owner is None
        assert views["pay"].effective_owner is not None and views["pay"].effective_owner.id == rc

    async def test_deleting_a_geography_clears_it(self, session) -> None:
        st = await _ou(session, "Stores")
        node = await _node(session)
        await cm.add_mapping(_perf("accept", st, node), session)
        await ostore.delete_geography(node, session)
        assert await _rows(session) == [("accept", st, "performer", None)]

    async def test_deleting_a_geography_merges_into_the_everywhere_row(self, session) -> None:
        st = await _ou(session, "Stores")
        await cm.add_mapping(_perf("accept", st), session)
        node = await _node(session)
        await cm.add_mapping(_perf("accept", st, node), session)
        await ostore.delete_geography(node, session)
        assert await _rows(session) == [("accept", st, "performer", None)]

    async def test_mappings_to_a_missing_capability_never_surface(self, session) -> None:
        st = await _ou(session, "Stores")
        await cm.add_mapping(_perf("accept", st), session)
        # SQLite enforces no FK cascade; the read side must still hide the orphan.
        await session.execute(
            ostore._business_capabilities.delete().where(
                ostore._business_capabilities.c.id == "accept"
            )
        )
        views = (await cm.list_views(session)).items
        assert all(v.capability_id != "accept" for v in views)
