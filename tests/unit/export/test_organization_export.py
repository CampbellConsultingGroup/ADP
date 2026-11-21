"""940-org-units-geography (research R7): org units + geography in the business export."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.export.organization import reconcile_organization
from adp.organization import store as ostore
from adp.organization.models import OrgUnitCreate

NOW = datetime(2026, 11, 15, tzinfo=timezone.utc)


@pytest.fixture()
async def session(tmp_path, monkeypatch):
    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr(ostore, "index_entity", _noop)
    monkeypatch.setattr(ostore, "unindex_entity", _noop)
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/exp.db")
    async with engine.begin() as conn:
        await conn.run_sync(ostore._metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        await ostore.seed_geography(s, NOW)
        yield s
    await engine.dispose()


async def test_writes_org_units_and_geographies_and_cleans_orphans(session, tmp_path):
    rc = await ostore.create_org_unit(OrgUnitCreate(name="Retail Co"), session)
    st = await ostore.create_org_unit(
        OrgUnitCreate(name="Stores", parent_id=rc.id, primary_geography_id="geo-m49-019"), session
    )
    await ostore.link_geography(st.id, "geo-US", session)
    await session.execute(
        ostore._applications.insert().values(
            id="pos", name="POS", owning_business_unit="x", owning_org_unit_id=st.id
        )
    )
    root = tmp_path / "out"
    await reconcile_organization(root, session, NOW)

    stores = json.loads((root / "organization" / "org-units" / f"{st.id}.json").read_text())
    assert stores["kind"] == "division" and stores["path"] == ["Retail Co"]
    assert stores["geography_ids"] == ["geo-US"]
    assert stores["primary_geography_id"] == "geo-m49-019"
    assert stores["application_ids"] == ["pos"]
    geos = json.loads((root / "organization" / "geographies.json").read_text())["geographies"]
    assert geos[0]["id"] == "geo-001"
    assert next(g for g in geos if g["id"] == "geo-DE")["code"] == "DE"

    await ostore.delete_org_unit(st.id, session)
    await reconcile_organization(root, session, NOW)
    assert not (root / "organization" / "org-units" / f"{st.id}.json").exists()
    assert (root / "organization" / "org-units" / f"{rc.id}.json").exists()


async def test_geographies_file_lists_hierarchies_with_dated_memberships(session, tmp_path):
    from datetime import date

    from adp.organization import hierarchies
    from adp.organization.models import AddMemberships, GeoHierarchyCreate, GeoNodeCreate

    h = await hierarchies.create_hierarchy(
        GeoHierarchyCreate(name="Regulatory", kind="regulatory", shape="dag"), session
    )
    eu = await hierarchies.create_node(h.id, GeoNodeCreate(name="EU"), session)
    await hierarchies.add_memberships(
        h.id,
        AddMemberships(parent_id=eu.id, child_ids=["geo-GB"], valid_to=date(2020, 1, 31)),
        session,
    )
    root = tmp_path / "out"
    await reconcile_organization(root, session, NOW)
    data = json.loads((root / "organization" / "geographies.json").read_text())
    by_id = {x["id"]: x for x in data["hierarchies"]}
    assert by_id["geoh-m49"]["kind"] == "reference" and len(by_id["geoh-m49"]["memberships"]) > 200
    reg = by_id[h.id]
    assert reg["node_ids"] == [eu.id]
    assert reg["memberships"] == [
        {"parent_id": eu.id, "child_id": "geo-GB", "valid_from": None, "valid_to": "2020-01-31"}
    ]
    eu_row = next(g for g in data["geographies"] if g["id"] == eu.id)
    assert eu_row["entity"] == "node" and eu_row["hierarchy_id"] == h.id


async def test_legal_entities_and_typed_links(session, tmp_path, monkeypatch):
    """947 GEO-02 FR-011: legal entity files, org unit geo_links, application links file."""
    from datetime import date

    from adp.organization import geo_links, legal_entities
    from adp.organization.models import GeoLinkCreate, LegalEntityCreate

    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr(legal_entities, "index_entity", _noop)
    monkeypatch.setattr(legal_entities, "unindex_entity", _noop)
    ou = await ostore.create_org_unit(OrgUnitCreate(name="Stores"), session)
    await ostore.link_geography(ou.id, "geo-DE", session)
    le = await legal_entities.create_legal_entity(LegalEntityCreate(name="Retail GmbH"), session)
    await legal_entities.link_org_unit(le.id, ou.id, session)
    await geo_links.add_link(
        "legal_entity",
        le.id,
        GeoLinkCreate(
            relation="incorporated_in", geography_id="geo-DE", valid_from=date(2001, 1, 1)
        ),
        session,
    )
    await session.execute(ostore._applications.insert().values(id="pos", name="POS"))
    await legal_entities.link_application("pos", le.id, session)
    await geo_links.add_link(
        "application", "pos", GeoLinkCreate(relation="deployed_in", geography_id="geo-IE"), session
    )
    root = tmp_path / "out"
    await reconcile_organization(root, session, NOW)

    base = root / "organization"
    entity = json.loads((base / "legal-entities" / f"{le.id}.json").read_text())
    assert entity["org_unit_ids"] == [ou.id] and entity["application_ids"] == ["pos"]
    assert entity["geo_links"] == [
        {
            "relation": "incorporated_in",
            "geography_id": "geo-DE",
            "valid_from": "2001-01-01",
            "valid_to": None,
        }
    ]
    unit = json.loads((base / "org-units" / f"{ou.id}.json").read_text())
    assert [lk["relation"] for lk in unit["geo_links"]] == ["operates_in"]
    apps = json.loads((base / "application-geo-links.json").read_text())["applications"]
    assert apps == [
        {
            "application_id": "pos",
            "legal_entity_ids": [le.id],
            "geo_links": [
                {
                    "relation": "deployed_in",
                    "geography_id": "geo-IE",
                    "valid_from": None,
                    "valid_to": None,
                }
            ],
        }
    ]
    await legal_entities.delete_legal_entity(le.id, session)
    await reconcile_organization(root, session, NOW)
    assert not (base / "legal-entities" / f"{le.id}.json").exists()
