"""948 GEO-03: the pure applicability derivation (spec FR-003/FR-004), no database.

A small world: a UN-style reference tree (Europe > DE, FR, GB, IE) and a regulatory DAG where the
EU contains DE, FR, IE and GB until 2020-01-31 (Brexit), plus a sales node APAC with JP and IE.
"""

from __future__ import annotations

from datetime import date

import pytest

from adp.compliance.applicability import (
    FrameworkFacts,
    LinkFact,
    compute_framework_applicability,
    path_up,
)
from adp.organization.geo_model import Entity, GeoGraph, Membership

BREXIT = date(2020, 1, 31)
LABELS = {
    "processes_personal_data_of": "Processes personal data of people in",
    "licensed_in": "Licensed in",
    "deployed_in": "Deployed in",
}


def _world(as_of: date) -> GeoGraph:
    places = ["DE", "FR", "GB", "IE", "JP"]
    entities = {p: Entity(p, "place", None) for p in places}
    entities |= {
        "europe": Entity("europe", "node", "ref"),
        "EU": Entity("EU", "node", "reg"),
        "APAC": Entity("APAC", "node", "sales"),
    }
    m = [Membership(f"r{p}", "ref", "europe", p) for p in ("DE", "FR", "GB", "IE")]
    m += [Membership(f"e{p}", "reg", "EU", p) for p in ("DE", "FR", "IE")]
    m += [Membership("eGB", "reg", "EU", "GB", None, BREXIT)]
    m += [Membership("sJP", "sales", "APAC", "JP"), Membership("sIE", "sales", "APAC", "IE")]
    return GeoGraph(entities, m, as_of)


def _gdpr(**over) -> FrameworkFacts:
    base = dict(
        id="gdpr",
        name="GDPR",
        status="in_force",
        in_force_from=date(2018, 5, 25),
        geography_ids=("EU",),
        triggers=frozenset({("application", "processes_personal_data_of")}),
    )
    return FrameworkFacts(**(base | over))  # type: ignore[arg-type]


def _pd(geo: str, **over) -> LinkFact:
    return LinkFact("application", "processes_personal_data_of", geo, **over)


TODAY = date(2026, 11, 20)


def _run(f, links, on=TODAY):
    return compute_framework_applicability(f, links, _world(on), on, LABELS)


class TestOutcomes:
    def test_applies_with_the_path(self) -> None:
        r = _run(_gdpr(), [_pd("DE")])
        assert r.status == "applies" and r.reason is None
        (m,) = r.matches
        assert (m.scope_id, m.how, m.path) == ("EU", "inside", ("DE", "EU"))

    def test_the_bloc_changes_on_read(self) -> None:
        # The UK left the EU on 2020-01-31: the same link gives a different answer by date.
        assert _run(_gdpr(), [_pd("GB")], date(2019, 6, 1)).status == "applies"
        r = _run(_gdpr(), [_pd("GB")])
        assert r.status == "does_not_apply"
        assert (
            r.reason
            == "None of its processes personal data of people in links are in the jurisdiction"
        )

    def test_unknown_without_jurisdiction(self) -> None:
        r = _run(_gdpr(geography_ids=()), [_pd("DE")])
        assert (r.status, r.reason) == ("unknown", "No jurisdiction recorded for this framework")
        assert _run(_gdpr(triggers=frozenset()), [_pd("DE")]).status == "unknown"

    def test_unknown_without_a_trigger_link(self) -> None:
        # Deployed in Germany says nothing about whose personal data it processes.
        r = _run(_gdpr(), [LinkFact("application", "deployed_in", "DE")])
        assert (r.status, r.reason) == (
            "unknown",
            "No processes personal data of people in links recorded",
        )

    def test_inactive_links_do_not_count(self) -> None:
        r = _run(_gdpr(), [_pd("DE", valid_to=date(2025, 1, 1))])
        assert r.status == "unknown"
        assert _run(_gdpr(), [_pd("DE", valid_from=date(2027, 1, 1))]).status == "unknown"

    @pytest.mark.parametrize(
        ("over", "on", "reason"),
        [
            ({"status": "repealed"}, TODAY, "The framework is repealed"),
            ({}, date(2018, 1, 1), "Not in force until 2018-05-25"),
            (
                {"status": "not_yet_applicable", "in_force_from": None},
                TODAY,
                "The framework is not yet applicable",
            ),
        ],
    )
    def test_lifecycle(self, over, on, reason) -> None:
        r = _run(_gdpr(**over), [_pd("DE")], on)
        assert (r.status, r.reason) == ("does_not_apply", reason)

    def test_not_yet_applicable_with_a_past_date_applies(self) -> None:
        f = _gdpr(status="not_yet_applicable", in_force_from=date(2020, 1, 1))
        assert _run(f, [_pd("DE")]).status == "applies"


class TestGeometry:
    def test_same_covers_and_shared_countries(self) -> None:
        assert _run(_gdpr(), [_pd("EU")]).matches[0].how == "same"
        national = _gdpr(geography_ids=("DE",))
        assert _run(national, [_pd("europe")]).matches[0].how == "covers"
        # APAC (sales) shares Ireland with the EU.
        assert _run(_gdpr(), [_pd("APAC")]).matches[0].how == "shares_countries"
        assert _run(_gdpr(), [_pd("JP")]).status == "does_not_apply"

    def test_every_matching_link_is_evidence(self) -> None:
        r = _run(_gdpr(geography_ids=("EU", "GB")), [_pd("DE"), _pd("GB"), _pd("JP")])
        assert sorted((m.link.geography_id, m.scope_id) for m in r.matches) == [
            ("DE", "EU"),
            ("GB", "GB"),
        ]

    def test_path_up_finds_the_shortest_chain(self) -> None:
        g = _world(TODAY)
        assert path_up(g, "IE", "EU") == ("IE", "EU")
        assert path_up(g, "JP", "EU") == ()


class TestSubjects:
    def test_trigger_is_per_subject_type(self) -> None:
        insurance = FrameworkFacts(
            "ins",
            "Insurance law",
            "in_force",
            None,
            ("DE",),
            frozenset({("legal_entity", "licensed_in")}),
        )
        own = LinkFact("application", "licensed_in", "DE")  # not a legal entity's link
        assert _run(insurance, [own]).status == "unknown"
        via = LinkFact("legal_entity", "licensed_in", "DE", via_id="gmbh", via_name="Retail GmbH")
        r = _run(insurance, [via])
        assert r.status == "applies" and r.matches[0].link.via_name == "Retail GmbH"
