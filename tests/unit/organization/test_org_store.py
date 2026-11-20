"""940-org-units-geography: the organization store on SQLite.

Org units (US1), geography (US2), links (US3) and the review queue (US4). The geography tree is
seeded from the real data file through the same loader migration 048 uses.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
import sqlalchemy as sa
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.organization import hierarchies
from adp.organization import store as ostore
from adp.organization.geodata import geography_seed_rows
from adp.organization.models import (
    DepthError,
    DuplicateLinkError,
    DuplicateSiblingError,
    GeographyUpdate,
    GeoHierarchyCreate,
    GeoNodeCreate,
    HasChildrenError,
    InvalidCodeError,
    OrgNotFoundError,
    OrgUnitCreate,
    OrgUnitUpdate,
    ReadOnlyHierarchyError,
    ResolveCreate,
    ResolveUnmatched,
)

NOW = datetime(2026, 11, 15, tzinfo=timezone.utc)


@pytest.fixture()
async def session(tmp_path, monkeypatch):
    indexed: list[tuple[str, str, str]] = []

    async def _index(entity_type, entity_id, text, session):
        indexed.append((entity_type, entity_id, text))

    async def _unindex(entity_type, entity_id, session):
        indexed.append((entity_type, entity_id, "<removed>"))

    monkeypatch.setattr(ostore, "index_entity", _index)
    monkeypatch.setattr(ostore, "unindex_entity", _unindex)
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/org.db")
    async with engine.begin() as conn:
        await conn.run_sync(ostore._metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        await ostore.seed_geography(s, NOW)
        s.info["indexed"] = indexed
        yield s
    await engine.dispose()


async def _ou(s, name: str, parent: str | None = None):
    return await ostore.create_org_unit(OrgUnitCreate(name=name, parent_id=parent), s)


async def _app(s, app_id: str, bu: str | None, ou: str | None = None):
    await s.execute(
        ostore._applications.insert().values(
            id=app_id, name=app_id, owning_business_unit=bu, owning_org_unit_id=ou
        )
    )


async def _bu(s, app_id: str) -> str | None:
    return (
        await s.execute(
            sa.select(ostore._applications.c.owning_business_unit).where(
                ostore._applications.c.id == app_id
            )
        )
    ).scalar_one()


async def _link(s, app_id: str) -> str | None:
    return (
        await s.execute(
            sa.select(ostore._applications.c.owning_org_unit_id).where(
                ostore._applications.c.id == app_id
            )
        )
    ).scalar_one()


# ── US1 org units ─────────────────────────────────────────────────────────────


class TestOrgUnits:
    async def test_levels_and_kinds_derive_from_parent(self, session):
        rc = await _ou(session, "Retail Co")
        corp = await _ou(session, "Corporate", rc.id)
        fin = await _ou(session, "Finance", corp.id)
        assert (rc.level, rc.kind) == (1, "enterprise")
        assert (corp.level, corp.kind) == (2, "division")
        assert (fin.level, fin.kind) == (3, "function")
        assert [p.name for p in fin.path] == ["Retail Co", "Corporate"]

    async def test_fourth_level_refused(self, session):
        a = await _ou(session, "A")
        b = await _ou(session, "B", a.id)
        c = await _ou(session, "C", b.id)
        with pytest.raises(DepthError):
            await _ou(session, "D", c.id)

    async def test_unknown_parent(self, session):
        with pytest.raises(OrgNotFoundError):
            await _ou(session, "X", "nope")

    async def test_duplicate_sibling_ignoring_case_including_roots(self, session):
        rc = await _ou(session, "Retail Co")
        with pytest.raises(DuplicateSiblingError):
            await _ou(session, "retail co")
        await _ou(session, "Finance", rc.id)
        with pytest.raises(DuplicateSiblingError):
            await _ou(session, "FINANCE", rc.id)
        other = await _ou(session, "Other Co")
        await _ou(session, "Finance", other.id)  # same name under a different parent is fine

    async def test_update_renames_and_reindexes_descendants(self, session):
        rc = await _ou(session, "Retail Co")
        st = await _ou(session, "Stores", rc.id)
        session.info["indexed"].clear()
        await ostore.update_org_unit(rc.id, OrgUnitUpdate(name="Retail Group"), session)
        texts = {eid: text for _, eid, text in session.info["indexed"]}
        assert "Retail Group" in texts[st.id]

    async def test_update_rejects_parent_change(self):
        with pytest.raises(ValidationError):
            OrgUnitUpdate(parent_id="x")  # type: ignore[call-arg]

    async def test_name_cannot_be_blank(self):
        with pytest.raises(ValidationError):
            OrgUnitCreate(name="   ")

    async def test_delete_refused_with_children_and_clears_app_links(self, session):
        rc = await _ou(session, "Retail Co")
        st = await _ou(session, "Stores", rc.id)
        with pytest.raises(HasChildrenError):
            await ostore.delete_org_unit(rc.id, session)
        await _app(session, "pos", "Store Systems", st.id)
        assert await ostore.delete_org_unit(st.id, session)
        assert await _link(session, "pos") is None
        assert await _bu(session, "pos") == "Store Systems"  # FR-013: free text kept
        assert not await ostore.delete_org_unit("nope", session)

    async def test_application_count_and_detail(self, session):
        st = await _ou(session, "Stores")
        await _app(session, "pos", "x", st.id)
        await _app(session, "till", None, st.id)
        listed = (await ostore.list_org_units(session)).items
        assert listed[0].application_count == 2
        detail = await ostore.get_org_unit(st.id, session)
        assert detail is not None and [a.name for a in detail.applications] == ["pos", "till"]
        assert await ostore.org_unit_exists(st.id, session)
        assert not await ostore.org_unit_exists("nope", session)

    async def test_search_hooks(self, session):
        rc = await _ou(session, "Retail Co")
        await ostore.delete_org_unit(rc.id, session)
        kinds = [(t, eid, text) for t, eid, text in session.info["indexed"]]
        assert kinds[0][:2] == ("org_unit", rc.id)
        assert kinds[-1] == ("org_unit", rc.id, "<removed>")


# ── US2 geography ─────────────────────────────────────────────────────────────


class TestGeographies:
    async def test_seeded_tree(self, session):
        items = (await ostore.list_geographies(session)).items
        by_id = {g.id: g for g in items}
        assert len(items) == len(geography_seed_rows(NOW))
        assert by_id["geo-001"].kind == "global"
        assert sum(1 for g in items if g.kind == "region") == 5
        de = by_id["geo-DE"]
        assert (de.kind, de.code) == ("country", "DE")
        assert [p.name for p in de.path] == ["Global", "Europe"]
        assert [p.name for p in by_id["geo-TW"].path] == ["Global"]

    async def test_places_and_the_reference_hierarchy_are_read_only(self, session):
        # 946: countries are places; Global and the UN regions are nodes of the read-only
        # reference hierarchy.
        for geo_id in ("geo-DE", "geo-m49-150"):
            with pytest.raises(ReadOnlyHierarchyError):
                await ostore.update_geography(geo_id, GeographyUpdate(name="x"), session)
            with pytest.raises(ReadOnlyHierarchyError):
                await ostore.delete_geography(geo_id, session)
        assert await ostore.update_geography("nope", GeographyUpdate(name="x"), session) is None
        assert await ostore.delete_geography("nope", session) is False

    async def test_rename_a_node_checks_names_and_codes(self, session):
        h = await hierarchies.create_hierarchy(
            GeoHierarchyCreate(name="Sales", kind="sales", shape="strict_tree"), session
        )
        emea = await hierarchies.create_node(h.id, GeoNodeCreate(name="EMEA"), session)
        await hierarchies.create_node(h.id, GeoNodeCreate(name="APAC"), session)
        renamed = await ostore.update_geography(emea.id, GeographyUpdate(name="Europe+"), session)
        assert renamed is not None and renamed.name == "Europe+" and renamed.entity == "node"
        with pytest.raises(DuplicateSiblingError):
            await ostore.update_geography(emea.id, GeographyUpdate(name="apac"), session)
        with pytest.raises(InvalidCodeError):
            await ostore.update_geography(emea.id, GeographyUpdate(code="EM"), session)

    async def test_delete_node_refused_with_sub_nodes_and_clears_primary(self, session):
        h = await hierarchies.create_hierarchy(
            GeoHierarchyCreate(name="Sales", kind="sales", shape="strict_tree"), session
        )
        amer = await hierarchies.create_node(h.id, GeoNodeCreate(name="Americas"), session)
        na = await hierarchies.create_node(
            h.id, GeoNodeCreate(name="NA", parent_id=amer.id), session
        )
        with pytest.raises(HasChildrenError):
            await ostore.delete_geography(amer.id, session)
        ou = await ostore.create_org_unit(
            OrgUnitCreate(name="NA Retail", primary_geography_id=na.id), session
        )
        assert await ostore.delete_geography(na.id, session)
        refreshed = await ostore.get_org_unit(ou.id, session)
        assert refreshed is not None and refreshed.primary_geography_id is None
        assert await ostore.delete_geography(amer.id, session)

    async def test_unknown_primary_geography(self, session):
        with pytest.raises(OrgNotFoundError):
            await ostore.create_org_unit(
                OrgUnitCreate(name="X", primary_geography_id="geo-ZZ"), session
            )


# ── US3 links ─────────────────────────────────────────────────────────────────


class TestLinks:
    async def test_link_unlink_and_reverse(self, session):
        st = await _ou(session, "Stores")
        for g in ("geo-US", "geo-CA", "geo-DE"):
            await ostore.link_geography(st.id, g, session)
        with pytest.raises(DuplicateLinkError):
            await ostore.link_geography(st.id, "geo-US", session)
        detail = await ostore.get_org_unit(st.id, session)
        assert detail is not None
        assert {g.id for g in detail.geographies} == {"geo-US", "geo-CA", "geo-DE"}
        rev = await ostore.org_units_for_geography("geo-DE", session)
        assert rev is not None and [o.name for o in rev] == ["Stores"]
        assert (await ostore.get_geography("geo-DE", session)).org_unit_count == 1  # type: ignore[union-attr]
        assert await ostore.unlink_geography(st.id, "geo-DE", session)
        assert not await ostore.unlink_geography(st.id, "geo-DE", session)
        assert await ostore.org_units_for_geography("geo-ZZ", session) is None

    async def test_primary_need_not_be_linked(self, session):
        ou = await ostore.create_org_unit(
            OrgUnitCreate(name="Europe Retail", primary_geography_id="geo-m49-150"), session
        )
        assert ou.primary_geography_id == "geo-m49-150" and ou.geography_ids == []
        cleared = await ostore.update_org_unit(
            ou.id, OrgUnitUpdate(primary_geography_id=None), session
        )
        assert cleared is not None and cleared.primary_geography_id is None

    async def test_delete_either_side_removes_links(self, session):
        a = await _ou(session, "A")
        b = await _ou(session, "B")
        h = await hierarchies.create_hierarchy(
            GeoHierarchyCreate(name="Ops", kind="operational", shape="strict_tree"), session
        )
        hub = (await hierarchies.create_node(h.id, GeoNodeCreate(name="Hub"), session)).id
        await ostore.link_geography(a.id, hub, session)
        await ostore.link_geography(b.id, hub, session)
        await ostore.delete_org_unit(a.id, session)
        assert [o.name for o in await ostore.org_units_for_geography(hub, session) or []] == ["B"]
        await ostore.delete_geography(hub, session)
        assert (await ostore.get_org_unit(b.id, session)).geography_ids == []  # type: ignore[union-attr]

    async def test_link_unknown(self, session):
        st = await _ou(session, "Stores")
        with pytest.raises(OrgNotFoundError):
            await ostore.link_geography(st.id, "geo-ZZ", session)
        with pytest.raises(OrgNotFoundError):
            await ostore.link_geography("nope", "geo-US", session)


# ── US4 review queue ──────────────────────────────────────────────────────────


class TestUnmatched:
    async def _seed(self, s):
        await _app(s, "a1", "Store Systems")
        await _app(s, "a2", "Store Systems")
        await _app(s, "a3", "Store Systems")
        await _app(s, "a4", "Store systems")
        await _app(s, "a5", "   ")
        await _app(s, "a6", None)
        st = await _ou(s, "Stores")
        await _app(s, "a7", "Store Systems", st.id)  # already linked
        return st

    async def test_lists_exact_values_by_count(self, session):
        await self._seed(session)
        items = (await ostore.list_unmatched(session)).items
        assert [(u.value, u.application_count) for u in items] == [
            ("Store Systems", 3),
            ("Store systems", 1),
        ]
        assert [a.id for a in items[0].sample_applications] == ["a1", "a2", "a3"]

    async def test_resolve_to_existing_never_writes_free_text(self, session):
        st = await self._seed(session)
        before = {a: await _bu(session, a) for a in ("a1", "a2", "a3", "a4", "a7")}
        result = await ostore.resolve_unmatched(
            ResolveUnmatched(value="Store Systems", org_unit_id=st.id), session
        )
        assert result.updated_count == 3
        assert result.org_unit.application_count == 4
        assert {a: await _link(session, a) for a in ("a1", "a2", "a3")} == {
            a: st.id for a in ("a1", "a2", "a3")
        }
        assert await _link(session, "a4") is None  # different exact value
        after = {a: await _bu(session, a) for a in before}
        assert after == before  # SC-004
        assert [u.value for u in (await ostore.list_unmatched(session)).items] == ["Store systems"]

    async def test_resolve_with_create(self, session):
        await self._seed(session)
        rc = await _ou(session, "Retail Co")
        result = await ostore.resolve_unmatched(
            ResolveUnmatched(
                value="Store systems", create=ResolveCreate(name="Store Ops", parent_id=rc.id)
            ),
            session,
        )
        assert result.updated_count == 1
        assert (result.org_unit.name, result.org_unit.level) == ("Store Ops", 2)
        assert await _link(session, "a4") == result.org_unit.id

    async def test_resolve_create_error_changes_nothing(self, session):
        await self._seed(session)
        with pytest.raises(DuplicateSiblingError):
            await ostore.resolve_unmatched(
                ResolveUnmatched(value="Store systems", create=ResolveCreate(name="stores")),
                session,
            )
        assert await _link(session, "a4") is None

    async def test_resolve_unknown_org_unit(self, session):
        await self._seed(session)
        with pytest.raises(OrgNotFoundError):
            await ostore.resolve_unmatched(
                ResolveUnmatched(value="Store Systems", org_unit_id="nope"), session
            )

    def test_exactly_one_target(self):
        with pytest.raises(ValidationError):
            ResolveUnmatched(value="x")
        with pytest.raises(ValidationError):
            ResolveUnmatched(value="x", org_unit_id="a", create=ResolveCreate(name="b"))
