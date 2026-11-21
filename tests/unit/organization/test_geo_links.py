"""947 GEO-02: typed geography links and the legal entity registry (store, on SQLite).

Pure rules (overlap, the relation matrix, LEI check digits), link CRUD over the three subjects,
the 940 operating-geography routes as ``operates_in`` links, 941's "today" reading, and legal
entity CRUD with its parent tree and links. Applications go straight into the organization
store's narrow ``applications`` mirror.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
import sqlalchemy as sa
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.organization import cap_mappings, geo_links, hierarchies, legal_entities
from adp.organization import store as ostore
from adp.organization.geo_links import Period, check_link, overlaps
from adp.organization.models import (
    DuplicateLinkError,
    DuplicateNameError,
    GeoHierarchyCreate,
    GeoLinkCreate,
    GeoLinkUpdate,
    GeoNodeCreate,
    HasChildrenError,
    LegalEntityCreate,
    LegalEntityUpdate,
    LinkRuleError,
    OrgNotFoundError,
    OrgUnitCreate,
    lei_is_valid,
)

NOW = datetime(2026, 11, 20, tzinfo=timezone.utc)
DE, FR, GB, EUROPE = "geo-DE", "geo-FR", "geo-GB", "geo-m49-150"
LEI = "529900T8BM49AURSDO55"
D = date


# ── Pure rules ────────────────────────────────────────────────────────────────


class TestPure:
    @pytest.mark.parametrize(
        ("a", "b", "expected"),
        [
            ((None, None), (None, None), True),
            ((D(2020, 1, 1), D(2021, 1, 1)), (D(2021, 1, 1), None), False),  # end is exclusive
            ((D(2020, 1, 1), D(2021, 1, 1)), (D(2020, 12, 31), None), True),
            ((None, D(2020, 1, 1)), (D(2020, 1, 1), D(2022, 1, 1)), False),
            ((D(2019, 1, 1), None), (None, D(2019, 1, 2)), True),
        ],
    )
    def test_overlaps(self, a, b, expected) -> None:
        assert overlaps(*a, *b) is expected
        assert overlaps(*b, *a) is expected

    def test_relation_must_fit_the_subject(self) -> None:
        with pytest.raises(LinkRuleError, match="not allowed for application"):
            check_link("application", Period("x", "licensed_in", DE, None, None), [], True)
        with pytest.raises(LinkRuleError, match="not allowed for org unit"):
            check_link("org_unit", Period("x", "deployed_in", DE, None, None), [], True)

    def test_incorporated_in_is_a_country_and_one_at_a_time(self) -> None:
        with pytest.raises(LinkRuleError, match="must be a country"):
            check_link(
                "legal_entity", Period("x", "incorporated_in", EUROPE, None, None), [], False
            )
        old = Period("a", "incorporated_in", GB, None, D(2020, 1, 1))
        check_link(
            "legal_entity", Period("b", "incorporated_in", DE, D(2020, 1, 1), None), [old], True
        )
        with pytest.raises(DuplicateLinkError, match="one incorporated in link at a time"):
            check_link(
                "legal_entity", Period("b", "incorporated_in", DE, D(2019, 6, 1), None), [old], True
            )

    def test_same_link_twice_in_a_period(self) -> None:
        held = Period("a", "licensed_in", DE, D(2020, 1, 1), D(2025, 1, 1))
        with pytest.raises(DuplicateLinkError, match="already covers"):
            check_link("legal_entity", Period("b", "licensed_in", DE, None, None), [held], True)
        # Other geographies and other periods are fine; other relations never collide.
        check_link("legal_entity", Period("b", "licensed_in", FR, None, None), [held], True)
        check_link(
            "legal_entity", Period("b", "licensed_in", DE, D(2025, 1, 1), None), [held], True
        )
        check_link("legal_entity", Period("b", "tax_resident_in", DE, None, None), [held], True)

    def test_dates(self) -> None:
        with pytest.raises(LinkRuleError, match="after the start"):
            check_link(
                "org_unit", Period("x", "operates_in", DE, D(2021, 1, 1), D(2021, 1, 1)), [], True
            )
        with pytest.raises(ValidationError, match="after the start"):
            GeoLinkCreate(
                relation="operates_in",
                geography_id=DE,
                valid_from=D(2021, 1, 2),
                valid_to=D(2021, 1, 1),
            )

    def test_lei(self) -> None:
        assert lei_is_valid(LEI)
        assert not lei_is_valid(LEI[:-1] + "6")
        assert not lei_is_valid("TOO-SHORT")
        assert LegalEntityCreate(name="X", lei=LEI.lower()).lei == LEI
        assert LegalEntityCreate(name="X", lei="  ").lei is None
        with pytest.raises(ValidationError, match="ISO 17442"):
            LegalEntityCreate(name="X", lei="529900T8BM49AURSDO56")

    def test_relation_matrix_is_served(self) -> None:
        served = geo_links.relations().subjects
        assert [r.relation for r in served["org_unit"]] == [
            "operates_in",
            "serves_customers_in",
            "has_staff_in",
        ]
        inc = next(r for r in served["legal_entity"] if r.relation == "incorporated_in")
        assert inc.place_only and inc.single_active


# ── Store ─────────────────────────────────────────────────────────────────────


@pytest.fixture()
async def session(tmp_path, monkeypatch):
    async def _noop(*args, **kwargs):
        return None

    for mod in (ostore, legal_entities):
        monkeypatch.setattr(mod, "index_entity", _noop)
        monkeypatch.setattr(mod, "unindex_entity", _noop)
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/links.db")
    async with engine.begin() as conn:
        await conn.run_sync(ostore._metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        await ostore.seed_geography(s, NOW)
        await s.execute(ostore._applications.insert().values(id="pos", name="Store POS"))
        yield s
    await engine.dispose()


def _link(relation: str, geo: str, start: date | None = None, end: date | None = None):
    return GeoLinkCreate(relation=relation, geography_id=geo, valid_from=start, valid_to=end)


class TestLinks:
    async def test_add_list_update_delete_for_every_subject(self, session) -> None:
        ou = await ostore.create_org_unit(OrgUnitCreate(name="Stores"), session)
        le = await legal_entities.create_legal_entity(
            LegalEntityCreate(name="Retail GmbH"), session
        )
        for subject, sid, relation in (
            ("application", "pos", "deployed_in"),
            ("legal_entity", le.id, "licensed_in"),
            ("org_unit", ou.id, "has_staff_in"),
        ):
            link = await geo_links.add_link(subject, sid, _link(relation, DE), session)
            assert (link.subject_type, link.relation, link.geography.code) == (
                subject,
                relation,
                "DE",
            )
            assert link.active
            listed = await geo_links.list_links(subject, sid, session)
            assert [i.id for i in listed.items] == [link.id]
            ended = await geo_links.update_link(
                subject, sid, link.id, GeoLinkUpdate(valid_to=date.today()), session
            )
            assert not ended.active
            assert (await geo_links.list_links(subject, sid, session)).items == []
            everything = await geo_links.list_links(subject, sid, session, include_inactive=True)
            assert len(everything.items) == 1
            await geo_links.delete_link(subject, sid, link.id, session)
            with pytest.raises(OrgNotFoundError):
                await geo_links.delete_link(subject, sid, link.id, session)

    async def test_as_of(self, session) -> None:
        le = await legal_entities.create_legal_entity(LegalEntityCreate(name="Old Co"), session)
        await geo_links.add_link(
            "legal_entity", le.id, _link("incorporated_in", GB, None, D(2020, 1, 31)), session
        )
        await geo_links.add_link(
            "legal_entity", le.id, _link("incorporated_in", DE, D(2020, 1, 31)), session
        )
        then = await geo_links.list_links("legal_entity", le.id, session, as_of=D(2019, 6, 1))
        now = await geo_links.list_links("legal_entity", le.id, session)
        assert [i.geography.id for i in then.items] == [GB]
        assert [i.geography.id for i in now.items] == [DE]

    async def test_rules_on_write(self, session) -> None:
        le = await legal_entities.create_legal_entity(LegalEntityCreate(name="Co"), session)
        with pytest.raises(LinkRuleError, match="must be a country"):
            await geo_links.add_link(
                "legal_entity", le.id, _link("incorporated_in", EUROPE), session
            )
        with pytest.raises(OrgNotFoundError):
            await geo_links.add_link("legal_entity", le.id, _link("licensed_in", "geo-ZZ"), session)
        with pytest.raises(OrgNotFoundError):
            await geo_links.add_link("legal_entity", "nope", _link("licensed_in", DE), session)
        a = await geo_links.add_link(
            "legal_entity", le.id, _link("licensed_in", DE, D(2020, 1, 1), D(2021, 1, 1)), session
        )
        b = await geo_links.add_link(
            "legal_entity", le.id, _link("licensed_in", DE, D(2022, 1, 1)), session
        )
        # Moving b's start back into a's period collides with a, not with itself.
        with pytest.raises(DuplicateLinkError):
            await geo_links.update_link(
                "legal_entity", le.id, b.id, GeoLinkUpdate(valid_from=D(2020, 6, 1)), session
            )
        moved = await geo_links.update_link(
            "legal_entity", le.id, b.id, GeoLinkUpdate(valid_from=D(2021, 1, 1)), session
        )
        assert moved.valid_from == D(2021, 1, 1)
        # A link belongs to its subject: another subject's id can't reach it.
        other = await legal_entities.create_legal_entity(LegalEntityCreate(name="Other"), session)
        with pytest.raises(OrgNotFoundError):
            await geo_links.delete_link("legal_entity", other.id, a.id, session)

    async def test_a_node_can_be_a_target(self, session) -> None:
        h = await hierarchies.create_hierarchy(
            GeoHierarchyCreate(name="Sales", kind="sales", shape="strict_tree"), session
        )
        apac = await hierarchies.create_node(h.id, GeoNodeCreate(name="APAC"), session)
        link = await geo_links.add_link(
            "application", "pos", _link("serves_customers_in", apac.id), session
        )
        assert (link.geography.entity, link.geography.hierarchy_name) == ("node", "Sales")
        # Deleting the node removes the link (FR-007).
        await ostore.delete_geography(apac.id, session)
        assert (await geo_links.list_links("application", "pos", session)).items == []


class TestOperatesIn:
    async def test_940_routes_are_operates_in_links(self, session) -> None:
        ou = await ostore.create_org_unit(OrgUnitCreate(name="Stores"), session)
        linked = await ostore.link_geography(ou.id, DE, session)
        assert linked.geography_ids == [DE]
        links = (await geo_links.list_links("org_unit", ou.id, session)).items
        assert [(i.relation, i.valid_from, i.valid_to) for i in links] == [
            ("operates_in", None, None)
        ]
        with pytest.raises(DuplicateLinkError):
            await ostore.link_geography(ou.id, DE, session)
        # Other relations don't count as operating geographies.
        await geo_links.add_link("org_unit", ou.id, _link("has_staff_in", FR), session)
        assert (await ostore.get_org_unit(ou.id, session)).geography_ids == [DE]
        assert [o.id for o in await ostore.org_units_for_geography(DE, session)] == [ou.id]
        assert await ostore.org_units_for_geography(FR, session) == []
        de = next(g for g in (await ostore.list_geographies(session)).items if g.id == DE)
        assert de.org_unit_count == 1
        assert await ostore.unlink_geography(ou.id, DE, session)
        assert (await ostore.get_org_unit(ou.id, session)).geography_ids == []

    async def test_only_links_active_today_count(self, session) -> None:
        ou = await ostore.create_org_unit(OrgUnitCreate(name="Stores"), session)
        tomorrow = date.today() + timedelta(days=1)
        await geo_links.add_link("org_unit", ou.id, _link("operates_in", DE, tomorrow), session)
        await geo_links.add_link(
            "org_unit", ou.id, _link("operates_in", FR, None, date.today()), session
        )
        assert (await ostore.get_org_unit(ou.id, session)).geography_ids == []
        snap = await cap_mappings.build_snapshot(session)
        assert not snap.operates_in.get(ou.id)

    async def test_deleting_an_org_unit_removes_its_links(self, session) -> None:
        ou = await ostore.create_org_unit(OrgUnitCreate(name="Stores"), session)
        await geo_links.add_link("org_unit", ou.id, _link("has_staff_in", FR), session)
        await ostore.delete_org_unit(ou.id, session)
        count = sa.select(sa.func.count()).select_from(ostore._org_unit_geo_links)
        assert (await session.execute(count)).scalar_one() == 0


# ── Legal entities ────────────────────────────────────────────────────────────


class TestLegalEntities:
    async def test_crud_and_tree(self, session) -> None:
        plc = await legal_entities.create_legal_entity(
            LegalEntityCreate(name="Retail Co plc", lei=LEI, registration_number="01234567"),
            session,
        )
        gmbh = await legal_entities.create_legal_entity(
            LegalEntityCreate(name="Retail Co GmbH", parent_id=plc.id), session
        )
        assert [p.name for p in gmbh.path] == ["Retail Co plc"]
        detail = await legal_entities.get_legal_entity(plc.id, session)
        assert (detail.lei, detail.child_count, [c.name for c in detail.children]) == (
            LEI,
            1,
            ["Retail Co GmbH"],
        )
        with pytest.raises(LinkRuleError, match="subsidiaries"):
            await legal_entities.update_legal_entity(
                plc.id, LegalEntityUpdate(parent_id=gmbh.id), session
            )
        with pytest.raises(HasChildrenError, match="owns 1 other legal entity"):
            await legal_entities.delete_legal_entity(plc.id, session)
        moved = await legal_entities.update_legal_entity(
            gmbh.id, LegalEntityUpdate(parent_id=None, description="German stores"), session
        )
        assert (moved.parent_id, moved.description) == (None, "German stores")
        await legal_entities.delete_legal_entity(plc.id, session)
        assert (await legal_entities.list_legal_entities(session)).total == 1

    async def test_unique_name_and_lei(self, session) -> None:
        await legal_entities.create_legal_entity(LegalEntityCreate(name="Retail", lei=LEI), session)
        with pytest.raises(DuplicateNameError, match="named"):
            await legal_entities.create_legal_entity(LegalEntityCreate(name="RETAIL"), session)
        with pytest.raises(DuplicateNameError, match="LEI"):
            await legal_entities.create_legal_entity(LegalEntityCreate(name="B", lei=LEI), session)
        with pytest.raises(OrgNotFoundError):
            await legal_entities.create_legal_entity(
                LegalEntityCreate(name="C", parent_id="nope"), session
            )
        with pytest.raises(ValidationError, match="cleared"):
            LegalEntityUpdate(name=None)

    async def test_links_to_org_units_and_applications(self, session) -> None:
        le = await legal_entities.create_legal_entity(LegalEntityCreate(name="Retail"), session)
        ou = await ostore.create_org_unit(OrgUnitCreate(name="Stores"), session)
        detail = await legal_entities.link_org_unit(le.id, ou.id, session)
        assert [o.name for o in detail.org_units] == ["Stores"]
        with pytest.raises(DuplicateLinkError):
            await legal_entities.link_org_unit(le.id, ou.id, session)
        with pytest.raises(OrgNotFoundError):
            await legal_entities.link_org_unit(le.id, "nope", session)
        assert [e.id for e in await legal_entities.legal_entities_for_org_unit(ou.id, session)] == [
            le.id
        ]
        assert [e.id for e in await legal_entities.link_application("pos", le.id, session)] == [
            le.id
        ]
        with pytest.raises(DuplicateLinkError):
            await legal_entities.link_application("pos", le.id, session)
        with pytest.raises(OrgNotFoundError):
            await legal_entities.link_application("nope", le.id, session)
        assert (await legal_entities.list_legal_entities(session)).items[0].application_count == 1
        assert await legal_entities.all_application_links(session) == [("pos", le.id)]
        await legal_entities.unlink_application("pos", le.id, session)
        with pytest.raises(OrgNotFoundError):
            await legal_entities.unlink_application("pos", le.id, session)
        await legal_entities.unlink_org_unit(le.id, ou.id, session)
        with pytest.raises(OrgNotFoundError):
            await legal_entities.unlink_org_unit(le.id, ou.id, session)

    async def test_delete_removes_links(self, session) -> None:
        le = await legal_entities.create_legal_entity(LegalEntityCreate(name="Retail"), session)
        ou = await ostore.create_org_unit(OrgUnitCreate(name="Stores"), session)
        await legal_entities.link_org_unit(le.id, ou.id, session)
        await legal_entities.link_application("pos", le.id, session)
        await geo_links.add_link("legal_entity", le.id, _link("licensed_in", DE), session)
        await legal_entities.delete_legal_entity(le.id, session)
        for table in (
            ostore._legal_entity_org_units,
            ostore._application_legal_entities,
            ostore._legal_entity_geo_links,
        ):
            n = sa.select(sa.func.count()).select_from(table)
            assert (await session.execute(n)).scalar_one() == 0
        with pytest.raises(OrgNotFoundError):
            await legal_entities.get_legal_entity(le.id, session)
