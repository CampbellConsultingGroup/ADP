"""943-mapping-rationale: the pure parts -- the TIME-consistency hint (US1), overlap status and
reasons (US2) and the redundant list (US3) -- over hand-built snapshots."""

from __future__ import annotations

import pytest

from adp.application.cap_analysis import consistency_hint

RATIONALES = [None, "target", "tactical", "transitional", "redundant"]
TIMES = [None, "Tolerate", "Invest", "Migrate", "Eliminate"]
EXPECTED = {
    ("target", "Eliminate"): "TIME says Eliminate",
    ("target", "Migrate"): "TIME says Migrate",
    ("redundant", "Invest"): "TIME says Invest",
}


@pytest.mark.parametrize("rationale", RATIONALES)
@pytest.mark.parametrize("time", TIMES)
def test_consistency_hint_matrix(rationale, time) -> None:
    assert consistency_hint(rationale, time) == EXPECTED.get((rationale, time))


# ── Overlaps (US2) and the redundant list (US3) ───────────────────────────────

from adp.application.cap_analysis import (  # noqa: E402
    AppInfo,
    CapabilitySnapshot,
    GeoInfo,
    Node,
    Realization,
    findings,
)

# A tiny geography tree: Global > Europe > Germany, Global > Americas > Brazil.
GEOS = {
    "global": GeoInfo(None, "Global", None),
    "eu": GeoInfo("global", "Europe", None),
    "de": GeoInfo("eu", "Germany", "DE"),
    "am": GeoInfo("global", "Americas", None),
    "br": GeoInfo("am", "Brazil", "BR"),
}


class Snap:
    """Business L3s, each realized through its own application capability by named apps."""

    def __init__(self) -> None:
        self.business: dict[str, Node] = {}
        self.app_caps: dict[str, Node] = {}
        self.biz_to_ac: dict[str, set[str]] = {}
        self.ac_to_apps: dict[str, set[str]] = {}
        self.apps: dict[str, AppInfo] = {}
        self.realizations: dict[tuple[str, str], Realization] = {}

    def app(self, aid: str, time: str | None = None, lifecycle: str = "active") -> Snap:
        self.apps[aid] = AppInfo(aid, aid, lifecycle, None, time, "Retain" if time else None)
        return self

    def cap(self, biz: str, *ac_ids: str) -> Snap:
        self.business[biz] = Node(biz, biz, 3, None)
        for a in ac_ids or (f"ac:{biz}",):
            self.app_caps.setdefault(a, Node(a, a, 3, None))
            self.biz_to_ac.setdefault(biz, set()).add(a)
        return self

    def real(self, ac: str, app: str, rationale: str | None = None, geo: str | None = None) -> Snap:
        if app not in self.apps:
            self.app(app)
        self.app_caps.setdefault(ac, Node(ac, ac, 3, None))
        self.ac_to_apps.setdefault(ac, set()).add(app)
        self.realizations[(ac, app)] = Realization(rationale, geo)
        return self

    def build(self) -> CapabilitySnapshot:
        return CapabilitySnapshot(
            business=self.business,
            app_caps=self.app_caps,
            technical={},
            biz_to_ac={k: frozenset(v) for k, v in self.biz_to_ac.items()},
            ac_to_tc={},
            ac_to_apps={k: frozenset(v) for k, v in self.ac_to_apps.items()},
            apps=self.apps,
            risk={},
            cost={},
            risk_visible=False,
            cost_visible=False,
            realizations=self.realizations,
            geographies=GEOS,
        )


def _overlap(snap: Snap, biz: str = "Promo"):
    entries = [o for o in findings(snap.build()).overlaps if o.business.name == biz]
    assert len(entries) == 1
    return entries[0]


def _promo(*mappings: tuple[str, str | None, str | None]) -> Snap:
    s = Snap().cap("Promo")
    for app, rationale, geo in mappings:
        s.real("ac:Promo", app, rationale, geo)
    return s


def _codes(o) -> dict[str, list[str]]:
    return {r.code: r.application_ids for r in o.reasons}


def test_all_unclassified_needs_attention_without_no_target() -> None:
    o = _overlap(_promo(("pos", None, None), ("ecom", None, None)))
    assert o.status == "needs_attention"
    assert _codes(o) == {"unclassified": ["ecom", "pos"]}


def test_redundant_names_the_application() -> None:
    o = _overlap(_promo(("pos", "target", None), ("ecom", "redundant", None)))
    assert o.status == "needs_attention" and _codes(o) == {"redundant": ["ecom"]}


def test_classified_without_target() -> None:
    o = _overlap(_promo(("pos", "tactical", None), ("ecom", "transitional", None)))
    assert _codes(o) == {"no_target": []}


def test_two_global_targets_compete() -> None:
    o = _overlap(_promo(("pos", "target", None), ("ecom", "target", None)))
    assert _codes(o) == {"competing_targets": ["ecom", "pos"]}


def test_regional_targets_are_explained() -> None:
    o = _overlap(_promo(("pos", "target", "eu"), ("ecom", "target", "am")))
    assert (o.status, o.reasons) == ("explained", [])


@pytest.mark.parametrize("a, b", [("eu", "de"), ("de", "eu"), ("de", "de"), (None, "br")])
def test_targets_in_overlapping_scope_compete(a, b) -> None:
    o = _overlap(_promo(("pos", "target", a), ("ecom", "target", b)))
    assert "competing_targets" in _codes(o)


def test_one_app_targeted_through_two_capabilities_is_not_competing() -> None:
    s = Snap().cap("Promo", "ac1", "ac2")
    s.real("ac1", "pos", "target").real("ac2", "pos", "target").real("ac1", "ecom", "tactical")
    o = _overlap(s)
    assert (o.status, o.reasons) == ("explained", [])
    pos = next(a for a in o.applications if a.id == "pos")
    assert [m.via.id for m in pos.mappings] == ["ac1", "ac2"]


def test_target_transitional_and_regional_tactical_are_explained() -> None:
    o = _overlap(
        _promo(("pos", "target", None), ("old", "transitional", None), ("br-app", "tactical", "br"))
    )
    assert o.status == "explained"
    m = {a.id: a.mappings[0] for a in o.applications}
    assert m["br-app"].rationale == "tactical"
    assert m["br-app"].geography is not None and m["br-app"].geography.code == "BR"
    assert [v.id for v in next(a for a in o.applications if a.id == "pos").via] == ["ac:Promo"]


def test_retired_target_does_not_explain() -> None:
    s = _promo(("pos", "target", None), ("ecom", "tactical", None), ("ret", "target", None))
    s.app("ret", lifecycle="retired")
    o = _overlap(s)
    assert o.status == "explained"  # pos is still the target
    s2 = _promo(("ecom", "tactical", None), ("x", "tactical", None), ("ret", "target", None))
    s2.app("ret", lifecycle="retired")
    assert _codes(_overlap(s2)) == {"no_target": []}


def test_dangling_geography_counts_as_everywhere() -> None:
    o = _overlap(_promo(("pos", "target", "gone"), ("ecom", "target", "am")))
    assert "competing_targets" in _codes(o)
    assert next(a for a in o.applications if a.id == "pos").mappings[0].geography is None


def test_every_reason_is_listed() -> None:
    o = _overlap(
        _promo(
            ("pos", "target", None),
            ("ecom", "target", None),
            ("x", "redundant", None),
            ("y", None, None),
        )
    )
    assert set(_codes(o)) == {"unclassified", "redundant", "competing_targets"}


def test_ordering_needs_attention_first_then_name() -> None:
    s = Snap().cap("A explained").cap("B needs").cap("C needs")
    s.real("ac:A explained", "p", "target").real("ac:A explained", "q", "tactical")
    s.real("ac:B needs", "p").real("ac:B needs", "q")
    s.real("ac:C needs", "p", "redundant").real("ac:C needs", "q", "target")
    assert [o.business.name for o in findings(s.build()).overlaps] == [
        "B needs",
        "C needs",
        "A explained",
    ]


def test_hint_on_mappings() -> None:
    s = _promo(("pos", "target", None), ("ecom", "tactical", None))
    s.app("pos", time="Eliminate")
    o = _overlap(s)
    assert (
        next(a for a in o.applications if a.id == "pos").mappings[0].hint == "TIME says Eliminate"
    )


def test_redundant_groups() -> None:
    s = Snap().cap("Promo").cap("Pay")
    s.real("ac:Promo", "pos", "target").real("ac:Promo", "ecom", "redundant")
    s.real("ac:Pay", "solo", "redundant", "de")  # a single app is no overlap, but is listed here
    s.real("ac:orphan", "lone", "redundant")  # reaches no business L3
    s.real("ac:Pay", "ret", "redundant")
    s.app("ret", lifecycle="retired")
    s.app("ecom", time="Invest")
    groups = findings(s.build()).redundant
    assert [(g.business.name if g.business else None) for g in groups] == ["Pay", "Promo", None]
    assert [e.application.id for e in groups[0].entries] == ["solo"]
    assert (
        groups[0].entries[0].geography is not None
        and groups[0].entries[0].geography.name == "Germany"
    )
    ecom = groups[1].entries[0]
    assert (ecom.application.time_classification, ecom.hint) == ("Invest", "TIME says Invest")
    assert ecom.app_capability.id == "ac:Promo"
    assert [e.application.id for e in groups[2].entries] == ["lone"]


def test_no_redundant_mappings() -> None:
    assert findings(_promo(("pos", "target", None)).build()).redundant == []
