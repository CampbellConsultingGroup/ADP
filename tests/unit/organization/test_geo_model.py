"""946 GEO-01: the pure geography resolver (containment as of a date) and write invariants."""

from __future__ import annotations

from datetime import date

import pytest

from adp.organization.geo_model import (
    Entity,
    GeoGraph,
    Membership,
    check_membership,
    check_shape,
)

REF, REG, SALES = "ref", "reg", "sales"

ENTITIES = {
    # reference hierarchy: Global > Europe {DE, FR, IE, GB}, Asia {JP}, Africa {ZA}
    "global": Entity("global", "node", REF),
    "europe": Entity("europe", "node", REF),
    "asia": Entity("asia", "node", REF),
    "africa": Entity("africa", "node", REF),
    # regulatory DAG: EEA > EU; Eurozone
    "eu": Entity("eu", "node", REG),
    "eea": Entity("eea", "node", REG),
    "ez": Entity("ez", "node", REG),
    # sales tree: APAC
    "apac": Entity("apac", "node", SALES),
    "emptyn": Entity("emptyn", "node", SALES),
    **{c: Entity(c, "place", None) for c in ("de", "fr", "ie", "gb", "no", "jp", "za")},
}


def m(i: str, h: str, parent: str, child: str, start: date | None = None, end: date | None = None):
    return Membership(i, h, parent, child, start, end)


BREXIT = date(2020, 1, 31)
MEMBERS = [
    m("1", REF, "global", "europe"),
    m("2", REF, "global", "asia"),
    m("3", REF, "global", "africa"),
    m("4", REF, "europe", "de"),
    m("5", REF, "europe", "fr"),
    m("6", REF, "europe", "ie"),
    m("7", REF, "europe", "gb"),
    m("8", REF, "europe", "no"),
    m("9", REF, "asia", "jp"),
    m("10", REF, "africa", "za"),
    m("11", REG, "eea", "eu"),
    m("12", REG, "eea", "no"),
    m("13", REG, "eu", "de"),
    m("14", REG, "eu", "fr"),
    m("15", REG, "eu", "ie"),
    m("16", REG, "eu", "gb", None, BREXIT),
    m("17", REG, "ez", "ie"),
    m("18", REG, "ez", "de"),
    m("19", SALES, "apac", "jp"),
    m("20", SALES, "apac", "za"),
]
TODAY = date(2026, 11, 20)


def graph(as_of: date = TODAY) -> GeoGraph:
    return GeoGraph(ENTITIES, MEMBERS, as_of)


def test_places_follow_dates() -> None:
    assert graph().places("eu") == {"de", "fr", "ie"}
    assert graph(date(2019, 6, 1)).places("eu") == {"de", "fr", "ie", "gb"}
    assert graph().places("eea") == {"de", "fr", "ie", "no"}
    assert graph().places("de") == {"de"}
    assert graph().places("emptyn") == frozenset()


def test_end_date_is_exclusive() -> None:
    assert "gb" in graph(date(2020, 1, 30)).places("eu")
    assert "gb" not in graph(BREXIT).places("eu")


def test_ancestors_cross_hierarchies() -> None:
    assert graph().ancestors("ie") == {"europe", "global", "eu", "eea", "ez"}
    assert graph().ancestors("gb") == {"europe", "global"}


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        ("europe", "de", True),
        ("de", "europe", False),
        ("eea", "eu", True),  # descendant node
        ("europe", "eu", True),  # all EU countries are European
        ("eu", "europe", False),
        ("apac", "jp", True),
        ("asia", "apac", False),  # South Africa is not in Asia
        ("global", "apac", True),
        ("za", "africa", False),  # a one-country region is not inside its country
        ("africa", "za", True),
        ("emptyn", "jp", False),
        ("jp", "emptyn", False),
        ("global", "emptyn", False),  # covers no country, not a descendant
        ("apac", "apac", True),
        ("nope", "de", False),
    ],
)
def test_contains(a: str, b: str, expected: bool) -> None:
    assert graph().contains(a, b) is expected


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        ("apac", "asia", True),
        ("apac", "africa", True),
        ("apac", "europe", False),
        ("eu", "ez", True),
        ("de", "fr", False),
        ("jp", "apac", True),
        ("emptyn", "global", False),
        ("europe", "asia", False),
    ],
)
def test_overlaps(a: str, b: str, expected: bool) -> None:
    assert graph().overlaps(a, b) is expected


def test_reference_parent() -> None:
    g = graph()
    assert g.parents("de", REF) == ["europe"]
    assert g.parents("ie", REG) == ["eu", "ez"]
    assert g.parents("global", REF) == []


# ── Write invariants ──────────────────────────────────────────────────────────


def _check(candidate: Membership, shape: str = "dag", existing=MEMBERS) -> None:
    check_membership(candidate, existing, ENTITIES, shape)


def test_dag_allows_two_parents() -> None:
    _check(m("n", REG, "ez", "fr"))


def test_strict_tree_refuses_overlapping_second_parent() -> None:
    sales = [m("a", SALES, "apac", "jp")]
    ents = {**ENTITIES, "emea": Entity("emea", "node", SALES)}
    with pytest.raises(ValueError, match="already under apac"):
        check_membership(m("b", SALES, "emea", "jp"), sales, ents, "strict_tree")
    # Not overlapping in time: fine.
    dated = [m("a", SALES, "apac", "jp", None, date(2025, 1, 1))]
    check_membership(m("b", SALES, "emea", "jp", date(2025, 1, 1)), dated, ents, "strict_tree")


def test_cycle_refused() -> None:
    with pytest.raises(ValueError, match="cycle"):
        _check(m("n", REG, "eu", "eea"))
    with pytest.raises(ValueError, match="itself"):
        _check(m("n", REG, "eu", "eu"))


def test_dates_must_be_ordered() -> None:
    with pytest.raises(ValueError, match="after"):
        _check(m("n", REG, "ez", "fr", date(2025, 1, 1), date(2025, 1, 1)))


def test_same_pair_may_not_overlap_but_may_repeat_later() -> None:
    with pytest.raises(ValueError, match="already"):
        _check(m("n", REG, "eu", "de", date(2030, 1, 1)))
    _check(m("n", REG, "eu", "gb", date(2030, 1, 1)))  # rejoining after Brexit


def test_parent_and_child_must_fit_the_hierarchy() -> None:
    with pytest.raises(ValueError, match="node of this hierarchy"):
        _check(m("n", REG, "europe", "de"))  # parent in another hierarchy
    with pytest.raises(ValueError, match="node of this hierarchy"):
        _check(m("n", REG, "de", "fr"))  # parent is a place
    with pytest.raises(ValueError, match="another hierarchy"):
        _check(m("n", REG, "eu", "apac"))  # child node from another hierarchy
    with pytest.raises(ValueError, match="not found"):
        _check(m("n", REG, "eu", "zz"))


def test_updating_a_membership_ignores_itself() -> None:
    _check(m("16", REG, "eu", "gb", None, date(2021, 1, 1)))


def test_shape_change_to_strict_tree() -> None:
    reg = [x for x in MEMBERS if x.hierarchy_id == REG]
    problems = check_shape(reg, "strict_tree")
    assert problems == [
        "de has two parents at the same time",
        "ie has two parents at the same time",
    ]
    assert check_shape([x for x in MEMBERS if x.hierarchy_id == SALES], "strict_tree") == []
