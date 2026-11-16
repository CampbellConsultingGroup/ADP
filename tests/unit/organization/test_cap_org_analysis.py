"""Pure engine tests for 941-capability-org-mappings (no database).

Built on hand-made snapshots:

    Capabilities                      Org units
    Sell (L1)                         Retail Co (1)
      Payments (L2)                     Stores (2)
        Accept Payment (L3)               Store Ops (3)
        Refund (L3)                       Store Finance (3)
      Orders (L2)                       E-commerce (2)
        Capture Order (L3)
      Loyalty (L2, leaf)
    Support (L1)
      HR (L2)
        Payroll (L3)

    Geography: Global > Europe > Germany, France; Global > Americas > Brazil
"""

from __future__ import annotations

from adp.organization import cap_org_analysis as an
from adp.organization.cap_org_analysis import CapNode, GeoNode, MappingRow, OuNode, Snapshot

CAPS = {
    "sell": CapNode("sell", "Sell", 1, None, 0),
    "pay": CapNode("pay", "Payments", 2, "sell", 0),
    "accept": CapNode("accept", "Accept Payment", 3, "pay", 0),
    "refund": CapNode("refund", "Refund", 3, "pay", 1),
    "orders": CapNode("orders", "Orders", 2, "sell", 1),
    "capture": CapNode("capture", "Capture Order", 3, "orders", 0),
    "loyalty": CapNode("loyalty", "Loyalty", 2, "sell", 2),
    "support": CapNode("support", "Support", 1, None, 1),
    "hr": CapNode("hr", "HR", 2, "support", 0),
    "payroll": CapNode("payroll", "Payroll", 3, "hr", 0),
}
OUS = {
    "rc": OuNode("rc", "Retail Co", 1, None),
    "st": OuNode("st", "Stores", 2, "rc"),
    "ops": OuNode("ops", "Store Ops", 3, "st"),
    "sfin": OuNode("sfin", "Store Finance", 3, "st"),
    "ec": OuNode("ec", "E-commerce", 2, "rc"),
}
GEOS = {
    "g": GeoNode("g", "Global", 1, None),
    "eu": GeoNode("eu", "Europe", 2, "g"),
    "am": GeoNode("am", "Americas", 2, "g"),
    "de": GeoNode("de", "Germany", 3, "eu"),
    "fr": GeoNode("fr", "France", 3, "eu"),
    "br": GeoNode("br", "Brazil", 3, "am"),
}

_n = 0


def m(cap: str, ou: str, role: str = "performer", geo: str | None = None) -> MappingRow:
    global _n
    _n += 1
    return MappingRow(f"m{_n}", cap, ou, role, geo)


def snap(*mappings: MappingRow, operates_in: dict[str, set[str]] | None = None) -> Snapshot:
    return Snapshot.build(
        capabilities=CAPS.values(),
        org_units=OUS.values(),
        geographies=GEOS.values(),
        operates_in={k: frozenset(v) for k, v in (operates_in or {}).items()},
        mappings=mappings,
    )


# ── US1: effective owner ───────────────────────────────────────────────────────


class TestEffectiveOwner:
    def test_own_owner_wins(self) -> None:
        s = snap(m("pay", "st", "owner"), m("sell", "rc", "owner"))
        assert an.effective_owner(s, "pay") == ("st", None)

    def test_l3_inherits_l2_then_l1(self) -> None:
        assert an.effective_owner(snap(m("pay", "st", "owner")), "accept") == ("st", "pay")
        assert an.effective_owner(snap(m("sell", "rc", "owner")), "accept") == ("rc", "sell")

    def test_nearest_owned_ancestor_wins(self) -> None:
        s = snap(m("sell", "rc", "owner"), m("pay", "st", "owner"))
        assert an.effective_owner(s, "accept") == ("st", "pay")
        assert an.effective_owner(s, "capture") == ("rc", "sell")

    def test_no_owner_anywhere(self) -> None:
        assert an.effective_owner(snap(), "accept") == (None, None)

    def test_views_report_own_and_inherited_owner(self) -> None:
        views = {v.capability_id: v for v in an.views(snap(m("pay", "st", "owner")))}
        assert views["pay"].owner is not None and views["pay"].owner.id == "st"
        assert views["pay"].owner_inherited_from is None
        accept = views["accept"]
        assert accept.owner is None
        assert accept.effective_owner is not None and accept.effective_owner.name == "Stores"
        assert accept.owner_inherited_from is not None and accept.owner_inherited_from.id == "pay"
        # Capabilities with nothing mapped and no effective owner are left out.
        assert "support" not in views and "payroll" not in views


# ── US2: geography note ────────────────────────────────────────────────────────


class TestGeographyNote:
    OPERATES = {"st": {"eu"}}

    def note(self, ou: str, geo: str | None) -> bool:
        return an.outside_operating_geographies(snap(operates_in=self.OPERATES), ou, geo)

    def test_same_or_inside_an_operating_geography_is_fine(self) -> None:
        assert self.note("st", "eu") is False
        assert self.note("st", "de") is False

    def test_outside_is_flagged(self) -> None:
        assert self.note("st", "br") is True
        assert self.note("st", "g") is True  # Global is above Europe, not inside it

    def test_no_operating_geographies_or_no_geography_is_never_flagged(self) -> None:
        assert self.note("ec", "br") is False
        assert self.note("st", None) is False

    def test_views_flag_performers_only(self) -> None:
        s = snap(m("accept", "st", "performer", "br"), m("accept", "st", "contributor"),
                 operates_in=self.OPERATES)
        view = next(v for v in an.views(s) if v.capability_id == "accept")
        assert [p.outside_operating_geographies for p in view.performers] == [True]
        assert view.performers[0].geography is not None
        assert view.performers[0].geography.name == "Brazil"
        assert [c.outside_operating_geographies for c in view.contributors] == [False]


# ── US3: findings ──────────────────────────────────────────────────────────────


def ids(items) -> list[str]:  # type: ignore[no-untyped-def]
    return [i.id for i in items]


class TestFindings:
    def test_no_owner_lists_l1_l2_without_an_effective_owner(self) -> None:
        f = an.findings(snap(m("sell", "rc", "owner")))
        assert ids(f.no_owner) == ["support", "hr"]  # everything under Sell inherits
        f = an.findings(snap(m("pay", "st", "owner")))
        assert ids(f.no_owner) == ["sell", "orders", "loyalty", "support", "hr"]

    def test_leaf_l2_is_listed_as_no_owner_but_never_as_an_unmapped_l3(self) -> None:
        f = an.findings(snap())
        assert "loyalty" in ids(f.no_owner)
        assert "loyalty" not in ids(f.unmapped)

    def test_one_unit_in_two_countries_is_one_performer(self) -> None:
        f = an.findings(snap(m("accept", "st", geo="de"), m("accept", "st", geo="fr")))
        assert f.shared_service == []

    def test_two_branches_are_a_candidate(self) -> None:
        f = an.findings(snap(m("accept", "st", geo="de"), m("accept", "ec")))
        [cand] = f.shared_service
        assert cand.capability.id == "accept" and cand.branches == 2
        assert [p.org_unit.name for p in cand.performers] == ["E-commerce", "Stores"]
        stores = cand.performers[1]
        assert [g.name for g in stores.geographies] == ["Germany"]
        assert [r.name for r in stores.org_unit_path] == ["Retail Co"]
        assert [r.name for r in cand.capability.path] == ["Sell", "Payments"]

    def test_a_unit_and_its_own_descendant_are_one_branch(self) -> None:
        f = an.findings(snap(m("accept", "st"), m("accept", "ops")))
        assert f.shared_service == []

    def test_sibling_functions_are_two_branches(self) -> None:
        f = an.findings(snap(m("accept", "ops"), m("accept", "sfin")))
        assert [c.branches for c in f.shared_service] == [2]

    def test_folded_units_are_reported_under_their_branch(self) -> None:
        f = an.findings(snap(m("accept", "st"), m("accept", "ops"), m("accept", "ec")))
        [cand] = f.shared_service
        assert cand.branches == 2
        folded = {p.org_unit.id: p.folded_into for p in cand.performers}
        assert folded["ops"] is not None and folded["ops"].id == "st"
        assert folded["st"] is None and folded["ec"] is None

    def test_unmapped_and_owned_no_performer(self) -> None:
        f = an.findings(snap(m("pay", "st", "owner"), m("capture", "ec")))
        assert ids(f.owned_no_performer) == ["accept", "refund"]
        assert ids(f.unmapped) == ["payroll"]

    def test_contributors_change_nothing(self) -> None:
        base = an.findings(snap())
        with_contrib = an.findings(snap(m("accept", "st", "contributor"), m("accept", "ec", "contributor")))
        assert with_contrib == base

    def test_counts(self) -> None:
        f = an.findings(snap(m("accept", "st"), m("accept", "ec")))
        assert f.counts.l1_l2_total == 6
        assert f.counts.l3_total == 4
        assert f.counts.shared_service == 1
        assert f.counts.unmapped == 3
        assert f.counts.no_owner == 6
        assert f.counts.owned_no_performer == 0


# ── US4: footprint ─────────────────────────────────────────────────────────────


class TestFootprint:
    def test_groups_l1_l2_l3_with_counts(self) -> None:
        s = snap(m("accept", "st", geo="de"), m("refund", "st"), m("capture", "st"))
        fp = an.footprint(s, "st")
        assert fp.l3_total == 3
        [sell] = fp.performs
        assert sell.capability.name == "Sell" and sell.l3_count == 3
        assert [(l2.capability.name, l2.l3_count) for l2 in sell.l2s] == [
            ("Payments", 2),
            ("Orders", 1),
        ]
        accept = sell.l2s[0].l3s[0]
        assert accept.capability.name == "Accept Payment"
        assert [(p.org_unit.name, [g.name for g in p.geographies]) for p in accept.performed_by] == [
            ("Stores", ["Germany"])
        ]

    def test_includes_descendant_units_attributed(self) -> None:
        fp = an.footprint(snap(m("payroll", "ops")), "rc")
        assert fp.includes_descendants is True
        [support] = fp.performs
        l3 = support.l2s[0].l3s[0]
        assert [p.org_unit.name for p in l3.performed_by] == ["Store Ops"]

    def test_owns_and_contributes(self) -> None:
        s = snap(m("pay", "st", "owner"), m("hr", "sfin", "owner"), m("accept", "ec", "contributor"))
        fp = an.footprint(s, "rc")
        assert [(e.capability.name, e.org_unit.name) for e in fp.owns] == [
            ("Payments", "Stores"),
            ("HR", "Store Finance"),
        ]
        assert [(e.capability.name, e.org_unit.name) for e in fp.contributes] == [
            ("Accept Payment", "E-commerce")
        ]
        assert fp.performs == [] and fp.l3_total == 0

    def test_empty_unit(self) -> None:
        fp = an.footprint(snap(m("accept", "ec")), "st")
        assert fp.performs == [] and fp.owns == [] and fp.contributes == [] and fp.l3_total == 0


# ── US5: export block ──────────────────────────────────────────────────────────


class TestExportBlock:
    def test_block_for_an_l3_with_inherited_owner(self) -> None:
        s = snap(m("pay", "st", "owner"), m("accept", "ec", geo="de"), m("accept", "rc", "contributor"))
        assert an.export_block(s, "accept") == {
            "owner": None,
            "effective_owner": {"id": "st", "name": "Stores", "inherited_from": "pay"},
            "performers": [
                {"org_unit": {"id": "ec", "name": "E-commerce"}, "geography": {"id": "de", "name": "Germany"}}
            ],
            "contributors": [{"org_unit": {"id": "rc", "name": "Retail Co"}}],
        }

    def test_block_for_an_owned_l2_and_an_unmapped_capability(self) -> None:
        s = snap(m("pay", "st", "owner"))
        assert an.export_block(s, "pay")["owner"] == {"id": "st", "name": "Stores"}
        assert an.export_block(s, "pay")["effective_owner"] == {
            "id": "st", "name": "Stores", "inherited_from": None
        }
        assert an.export_block(s, "payroll") == {
            "owner": None, "effective_owner": None, "performers": [], "contributors": []
        }
