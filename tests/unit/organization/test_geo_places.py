"""949 GEO-04: places inside places, the seeded regulatory blocs, and the read views (pure)."""

from __future__ import annotations

from datetime import date, datetime, timezone

from adp.compliance.applicability import (
    FrameworkFacts,
    LinkFact,
    compute_framework_applicability,
)
from adp.organization import geodata
from adp.organization.geo_model import Entity, GeoGraph, Membership
from adp.organization.geo_views import (
    HierarchyInfo,
    footprint,
    matrix,
    placements,
    reached_places,
)
from adp.organization.models import FootprintLink, LinkGeography, PlaceRef

NOW = datetime(2026, 11, 21, tzinfo=timezone.utc)
D = date


def _graph(as_of: date = D(2026, 11, 21)) -> GeoGraph:
    entities = {
        "eu": Entity("eu", "node", "blocs"),
        "europe": Entity("europe", "node", "m49"),
        "de": Entity("de", "place"),
        "fr": Entity("fr", "place"),
        "us": Entity("us", "place"),
        "de-by": Entity("de-by", "place", parent_place="de"),
        "us-ca": Entity("us-ca", "place", parent_place="us"),
        "bavaria-only": Entity("bavaria-only", "node", "sales"),
    }
    memberships = [
        Membership("m1", "blocs", "eu", "de"),
        Membership("m2", "blocs", "eu", "fr"),
        Membership("m3", "m49", "europe", "de"),
        Membership("m4", "m49", "europe", "fr"),
        Membership("m5", "sales", "bavaria-only", "de-by"),
    ]
    return GeoGraph(entities, memberships, as_of)


def test_a_subdivision_is_inside_its_country_and_its_countrys_nodes() -> None:
    g = _graph()
    assert g.contains("de", "de-by")
    assert g.contains("eu", "de-by")
    assert not g.contains("de-by", "de")
    assert not g.contains("fr", "de-by")
    assert g.places("de") == frozenset({"de", "de-by"})
    assert "de-by" in g.places("eu")
    assert g.parent_place("de-by") == "de"
    assert g.parent_place("de") is None
    # A node holding only Bavaria overlaps Germany through the shared place, but a place never
    # contains a node.
    assert g.overlaps("bavaria-only", "de")
    assert not g.contains("de", "bavaria-only")
    assert g.contains("eu", "bavaria-only")  # every place of it is in the EU


def test_applicability_follows_a_subdivision_up_to_the_bloc() -> None:
    gdpr = FrameworkFacts(
        "gdpr", "GDPR", "in_force", D(2018, 5, 25), ("eu",),
        frozenset({("application", "deployed_in")}),
    )
    r = compute_framework_applicability(
        gdpr, [LinkFact("application", "deployed_in", "de-by")], _graph(), D(2026, 11, 21)
    )
    assert r.status == "applies"
    assert r.matches[0].how == "inside"
    assert r.matches[0].path == ("de-by", "de", "eu")
    r = compute_framework_applicability(
        gdpr, [LinkFact("application", "deployed_in", "us-ca")], _graph(), D(2026, 11, 21)
    )
    assert r.status == "does_not_apply"


# ── Seed data ────────────────────────────────────────────────────────────────


def _seeded_graph(on: date) -> GeoGraph:
    _, places, refs = geodata.seed_v2(NOW)
    seed = geodata.blocs_seed(NOW)
    rows = places + seed["nodes"] + seed["places"]
    entities = {
        r["id"]: Entity(r["id"], r["entity"], r["hierarchy_id"], r.get("parent_place_id"))
        for r in rows
    }
    mbs = [
        Membership(m["id"], m["hierarchy_id"], m["parent_id"], m["child_id"], m["valid_from"],
                   m["valid_to"])
        for m in refs + seed["memberships"]
    ]
    return GeoGraph(entities, mbs, on)


def _countries(g: GeoGraph, node: str) -> set[str]:
    """ISO alpha-2 codes of the countries in ``node`` (Lloyd's, inside GB, is a place too)."""
    codes = {p.removeprefix("geo-") for p in g.places(node)}
    return {c for c in codes if len(c) == 2}


def test_eu_membership_by_date() -> None:
    eu = "geo-bloc-eu"
    assert len(_countries(_seeded_graph(D(2026, 11, 21)), eu)) == 27
    assert len(_countries(_seeded_graph(D(2020, 1, 31)), eu)) == 28  # UK's last day
    assert "GB" not in _countries(_seeded_graph(D(2020, 2, 1)), eu)
    assert len(_countries(_seeded_graph(D(2013, 6, 30)), eu)) == 27  # before Croatia
    assert len(_countries(_seeded_graph(D(2013, 7, 1)), eu)) == 28
    assert _countries(_seeded_graph(D(1960, 1, 1)), eu) == {"BE", "DE", "FR", "IT", "LU", "NL"}
    assert len(_countries(_seeded_graph(D(1957, 12, 31)), eu)) == 0


def test_eea_membership_by_date() -> None:
    eea = "geo-bloc-eea"
    today = _countries(_seeded_graph(D(2026, 11, 21)), eea)
    assert len(today) == 30
    assert {"IS", "LI", "NO"} <= today and "CH" not in today
    assert _countries(_seeded_graph(D(2026, 11, 21)), "geo-bloc-eu") <= today
    assert len(_countries(_seeded_graph(D(1994, 1, 1)), eea)) == 17
    assert "LI" not in _countries(_seeded_graph(D(1995, 4, 30)), eea)
    # Bulgaria and Romania were in the EU before the EEA enlargement applied; Croatia likewise.
    assert "BG" not in _countries(_seeded_graph(D(2007, 7, 31)), eea)
    assert "BG" in _countries(_seeded_graph(D(2007, 8, 1)), eea)
    assert "HR" not in _countries(_seeded_graph(D(2014, 4, 11)), eea)
    assert "HR" in _countries(_seeded_graph(D(2014, 4, 12)), eea)


def test_lloyds_is_inside_the_uk_and_rest_of_world_is_inside_nothing() -> None:
    g = _seeded_graph(D(2019, 1, 1))
    assert g.contains("geo-GB", "geo-lloyds")
    assert g.contains("geo-bloc-eu", "geo-lloyds")  # while the UK was a member
    assert not _seeded_graph(D(2026, 1, 1)).contains("geo-bloc-eu", "geo-lloyds")
    assert not any(
        g.contains(n, "geo-rest-of-world") for n in ("geo-001", "geo-bloc-eu", "geo-bloc-eea")
    )


def test_subdivision_snapshot() -> None:
    expected = {"code": "US-CA", "name": "California", "type": "State"}
    assert geodata.subdivision(" us-ca ") == expected
    assert geodata.subdivision("XX-ZZ") is None
    assert geodata.subdivision_id("de-by") == "geo-DE-BY"
    assert geodata.subdivision_country("DE-BY") == "DE"
    assert len(geodata.subdivisions()) > 5000
    assert all(len(c) <= 8 for c in geodata.subdivisions())  # fits geographies.code


# ── Read views ───────────────────────────────────────────────────────────────

H = {
    "blocs": HierarchyInfo("blocs", "Regulatory blocs", "regulatory"),
    "m49": HierarchyInfo("m49", "UN M49", "reference"),
    "sales": HierarchyInfo("sales", "Sales", "sales"),
}
NAMES = {"eu": "EU", "europe": "Europe", "bavaria-only": "Bavaria territory"}
REFS = {
    "de": PlaceRef(id="de", name="Germany", code="DE", place_type="country"),
    "fr": PlaceRef(id="fr", name="France", code="FR", place_type="country"),
    "us": PlaceRef(id="us", name="United States", code="US", place_type="country"),
    "de-by": PlaceRef(id="de-by", name="Bavaria", code="DE-BY", place_type="subdivision",
                      parent_place_id="de"),
    "us-ca": PlaceRef(id="us-ca", name="California", code="US-CA", place_type="subdivision",
                      parent_place_id="us"),
}


def _link(relation: str, geo: str, via: str | None = None) -> tuple[str, FootprintLink]:
    from adp.organization.models import GeoNodeRef

    return geo, FootprintLink(
        relation=relation,
        relation_label=relation.replace("_", " ").capitalize(),
        geography=LinkGeography(id=geo, name=geo, entity="place"),
        via_legal_entity=GeoNodeRef(id=via, name=via) if via else None,
    )


def test_placements_list_each_hierarchy_reference_first() -> None:
    out = placements(_graph(), "de-by", H, NAMES)
    assert [(p.hierarchy_id, [n.name for n in p.nodes]) for p in out] == [
        ("m49", ["Europe"]),
        ("blocs", ["EU"]),
        ("sales", ["Bavaria territory"]),
    ]
    assert placements(_graph(), "de-by", H, NAMES, ["blocs"])[0].hierarchy_id == "blocs"
    assert placements(_graph(), "us", H, NAMES) == []


def test_reached_places_drop_subdivisions_their_country_covers() -> None:
    g = _graph()
    assert reached_places(g, "eu") == ["de", "fr"]  # not de-by: Germany covers it
    assert reached_places(g, "bavaria-only") == ["de-by"]
    assert reached_places(g, "us-ca") == ["us-ca"]


def test_footprint_groups_links_by_place() -> None:
    fp = footprint(
        "app-1",
        [_link("deployed_in", "de-by"), _link("serves_customers_in", "eu", via="GmbH"),
         _link("deployed_in", "empty")],
        _graph(),  # "empty" is no known geography, so it reaches no place
        REFS, H, NAMES,
    )
    by_name = {p.place.name: p for p in fp.places}
    assert sorted(by_name) == ["Bavaria", "France", "Germany"]
    assert [lk.via_legal_entity.name for lk in by_name["France"].links] == ["GmbH"]
    assert [lk.relation for lk in by_name["Bavaria"].links] == ["deployed_in"]
    assert [lk.geography.id for lk in fp.unresolved] == ["empty"]


def test_matrix_orders_subdivisions_under_their_country() -> None:
    m = matrix(_graph(), REFS, H, NAMES)
    assert [r.place.name for r in m.rows] == [
        "France", "Germany", "Bavaria", "United States", "California",
    ]
    assert [h.id for h in m.hierarchies] == ["m49", "blocs", "sales"]
    germany = next(r for r in m.rows if r.place.id == "de")
    assert {k: [n.name for n in v] for k, v in germany.cells.items()} == {
        "blocs": ["EU"], "m49": ["Europe"],
    }
