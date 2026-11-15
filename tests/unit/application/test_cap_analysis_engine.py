"""938-capability-model-analysis (ADP-6et.2): the pure analysis engine.

Every rule in spec FR-005..FR-017 against hand-built snapshots, with a fixed as_of. No database.
"""

from __future__ import annotations

import time
from datetime import date, timedelta
from decimal import Decimal

import pytest

from adp.application import cap_analysis as ca
from adp.application.cap_analysis import AppInfo, CapabilitySnapshot, Node, RiskInfo, TechNode

AS_OF = date(2026, 11, 15)


class Builder:
    """Small fluent builder for snapshots. Ids double as names."""

    def __init__(self) -> None:
        self.business: dict[str, Node] = {}
        self.app_caps: dict[str, Node] = {}
        self.technical: dict[str, TechNode] = {}
        self.biz_to_ac: dict[str, set[str]] = {}
        self.ac_to_tc: dict[str, set[str]] = {}
        self.ac_to_apps: dict[str, set[str]] = {}
        self.apps: dict[str, AppInfo] = {}
        self.risk: dict[str, RiskInfo] = {}
        self.cost: dict[str, Decimal] = {}

    def biz(self, cid: str, level: int, parent: str | None = None) -> Builder:
        self.business[cid] = Node(cid, cid, level, parent)
        return self

    def ac(self, cid: str, level: int = 3, parent: str | None = None) -> Builder:
        self.app_caps[cid] = Node(cid, cid, level, parent)
        return self

    def tech(
        self,
        cid: str,
        level: int = 3,
        parent: str | None = None,
        status: str = "current",
        eol: date | None = None,
    ) -> Builder:
        self.technical[cid] = TechNode(cid, cid, level, parent, status, eol)
        return self

    def app(self, aid: str, health: int | None = None, lifecycle: str = "active") -> Builder:
        self.apps[aid] = AppInfo(aid, aid, lifecycle, health)
        return self

    def link_biz(self, b: str, a: str) -> Builder:
        self.biz_to_ac.setdefault(b, set()).add(a)
        return self

    def link_tech(self, a: str, t: str) -> Builder:
        self.ac_to_tc.setdefault(a, set()).add(t)
        return self

    def realize(self, a: str, app: str) -> Builder:
        self.ac_to_apps.setdefault(a, set()).add(app)
        return self

    def build(self, *, risk_visible: bool = True, cost_visible: bool = True) -> CapabilitySnapshot:
        return CapabilitySnapshot(
            business=self.business,
            app_caps=self.app_caps,
            technical=self.technical,
            biz_to_ac={k: frozenset(v) for k, v in self.biz_to_ac.items()},
            ac_to_tc={k: frozenset(v) for k, v in self.ac_to_tc.items()},
            ac_to_apps={k: frozenset(v) for k, v in self.ac_to_apps.items()},
            apps=self.apps,
            risk=self.risk if risk_visible else {},
            cost=self.cost if cost_visible else {},
            risk_visible=risk_visible,
            cost_visible=cost_visible,
        )


def pos() -> Builder:
    """The user's Store POS example (ADP-6et notes)."""
    b = (
        Builder()
        .biz("Sales", 1)
        .biz("In-Store", 2, "Sales")
        .ac("Transaction Processing", 1)
        .ac("Checkout", 2, "Transaction Processing")
        .tech("Integration", 1)
        .tech("Data Storage", 2, "Integration")
        .tech("API Services", 2, "Integration")
        .app("POS", health=2)
    )
    chains = [
        ("Process Checkout", "Basket Calculation", ["Offline Sync"], "Data Storage"),
        ("Apply Promotions", "Price Rule Evaluation", ["Caching"], "Data Storage"),
        ("Accept Payment", "Tender Authorization", ["API Gateway"], "API Services"),
    ]
    for biz, ac_, techs, tparent in chains:
        b.biz(biz, 3, "In-Store").ac(ac_, 3, "Checkout").link_biz(biz, ac_).realize(ac_, "POS")
        for t in techs:
            if t not in b.technical:
                b.tech(t, 3, tparent)
            b.link_tech(ac_, t)
    return b


def by_id(resp) -> dict:
    return {i.capability_id: i for i in resp.items}


# ── Risk band (R4) ─────────────────────────────────────────────────────────────


class TestRiskBand:
    @pytest.mark.parametrize(
        "risk",
        [
            RiskInfo("strong", "open_high", None),
            RiskInfo("strong", "critical", None),
            RiskInfo("weak", "none_known", None),
            RiskInfo("strong", "none_known", AS_OF - timedelta(days=1)),
            RiskInfo("strong", "none_known", AS_OF),
        ],
    )
    def test_high(self, risk):
        assert ca.risk_band(risk, AS_OF) == "high"

    @pytest.mark.parametrize(
        "risk",
        [
            RiskInfo("strong", "open_low", None),
            RiskInfo("adequate", "none_known", None),
            RiskInfo("strong", "none_known", AS_OF + timedelta(days=365)),
        ],
    )
    def test_medium(self, risk):
        assert ca.risk_band(risk, AS_OF) == "medium"

    def test_low(self):
        assert (
            ca.risk_band(RiskInfo("strong", "none_known", AS_OF + timedelta(days=366)), AS_OF)
            == "low"
        )

    @pytest.mark.parametrize(
        "risk",
        [
            None,
            RiskInfo(None, None, None),
            RiskInfo("unknown", "none_known", None),
            RiskInfo("strong", None, None),
        ],
    )
    def test_unknown(self, risk):
        assert ca.risk_band(risk, AS_OF) == "unknown"


# ── Roll-up (US1, FR-005..FR-010) ───────────────────────────────────────────────


class TestBusinessRollup:
    def test_pos_health_rolls_up_to_l1(self):
        r = by_id(ca.business_rollup(pos().build(), AS_OF))
        for cid in ("Process Checkout", "Apply Promotions", "Accept Payment", "In-Store", "Sales"):
            assert r[cid].health.worst == 2, cid
        assert r["In-Store"].health.spread["2"] == 3
        assert r["Sales"].health.spread["2"] == 3

    def test_l3_worst_and_spread_over_apps(self):
        b = (
            Builder()
            .biz("L3", 3)
            .ac("A1")
            .ac("A2")
            .app("a", 2)
            .app("b", 4)
            .link_biz("L3", "A1")
            .link_biz("L3", "A2")
            .realize("A1", "a")
            .realize("A2", "b")
        )
        h = by_id(ca.business_rollup(b.build(), AS_OF))["L3"].health
        assert h.worst == 2
        assert h.spread["2"] == 1 and h.spread["4"] == 1 and h.spread["no_data"] == 0

    def test_parent_spread_counts_leaves(self):
        b = (
            Builder()
            .biz("L2", 2)
            .biz("x", 3, "L2")
            .biz("y", 3, "L2")
            .biz("z", 3, "L2")
            .ac("Ax")
            .ac("Ay")
            .app("a", 2)
            .app("b", 4)
            .link_biz("x", "Ax")
            .link_biz("y", "Ay")
            .realize("Ax", "a")
            .realize("Ay", "b")
        )
        h = by_id(ca.business_rollup(b.build(), AS_OF))["L2"].health
        assert h.worst == 2
        assert (h.spread["2"], h.spread["4"], h.spread["no_data"]) == (1, 1, 1)

    def test_no_application_capability_or_no_realizer_is_no_data(self):
        b = Builder().biz("alone", 3).biz("unrealized", 3).ac("A").link_biz("unrealized", "A")
        r = by_id(ca.business_rollup(b.build(), AS_OF))
        for cid in ("alone", "unrealized"):
            assert r[cid].health.worst is None
            assert r[cid].health.spread["no_data"] == 1
            assert r[cid].risk.worst is None
            assert r[cid].cost.total_tco is None

    def test_unassessed_never_sets_worst(self):
        b = (
            Builder()
            .biz("L3", 3)
            .ac("A")
            .app("a", 4)
            .app("u", None)
            .link_biz("L3", "A")
            .realize("A", "a")
            .realize("A", "u")
        )
        h = by_id(ca.business_rollup(b.build(), AS_OF))["L3"].health
        assert h.worst == 4 and h.spread["unassessed"] == 1

    def test_only_unassessed_counts_as_unassessed_leaf_at_parent(self):
        b = (
            Builder()
            .biz("L2", 2)
            .biz("L3", 3, "L2")
            .ac("A")
            .app("u", None)
            .link_biz("L3", "A")
            .realize("A", "u")
        )
        r = by_id(ca.business_rollup(b.build(), AS_OF))
        assert r["L3"].health.worst is None
        assert r["L2"].health.spread["unassessed"] == 1 and r["L2"].health.spread["no_data"] == 0

    def test_retired_excluded_sunset_counted(self):
        b = (
            Builder()
            .biz("L3", 3)
            .ac("A")
            .app("a", 4)
            .app("old", 1, lifecycle="retired")
            .link_biz("L3", "A")
            .realize("A", "a")
            .realize("A", "old")
        )
        item = by_id(ca.business_rollup(b.build(), AS_OF))["L3"]
        assert item.health.worst == 4
        assert [a.id for a in item.excluded_retired_apps] == ["old"]
        assert [a.id for a in item.contributing_apps] == ["a"]
        b.apps["old"] = AppInfo("old", "old", "sunset", 1)
        assert by_id(ca.business_rollup(b.build(), AS_OF))["L3"].health.worst == 1

    def test_only_retired_is_no_data_with_excluded_list(self):
        b = (
            Builder()
            .biz("L3", 3)
            .ac("A")
            .app("old", 1, "retired")
            .link_biz("L3", "A")
            .realize("A", "old")
        )
        item = by_id(ca.business_rollup(b.build(), AS_OF))["L3"]
        assert item.health.worst is None and item.health.spread["no_data"] == 1
        assert [a.id for a in item.excluded_retired_apps] == ["old"]

    def test_app_counted_once_per_capability(self):
        b = (
            Builder()
            .biz("L1", 1)
            .biz("L2a", 2, "L1")
            .biz("L2b", 2, "L1")
            .biz("x", 3, "L2a")
            .biz("y", 3, "L2b")
            .ac("A1")
            .ac("A2")
            .app("a", 3)
            .link_biz("x", "A1")
            .link_biz("x", "A2")
            .link_biz("y", "A1")
            .realize("A1", "a")
            .realize("A2", "a")
        )
        b.cost["a"] = Decimal("100")
        r = by_id(ca.business_rollup(b.build(), AS_OF))
        assert r["x"].health.spread["3"] == 1
        assert r["x"].cost.total_tco == Decimal("100")
        assert r["L1"].cost.total_tco == Decimal("100")
        assert [v.id for v in r["x"].contributing_apps[0].via] == ["A1", "A2"]

    def test_l1_without_leaves_is_no_data(self):
        item = by_id(ca.business_rollup(Builder().biz("Empty", 1).build(), AS_OF))["Empty"]
        assert item.health.worst is None and item.exposure.worst is None

    def test_cost_sum_distinct_and_missing_count(self):
        b = (
            Builder()
            .biz("L2", 2)
            .biz("x", 3, "L2")
            .biz("y", 3, "L2")
            .ac("Ax")
            .ac("Ay")
            .app("a")
            .app("b")
            .app("c")
            .link_biz("x", "Ax")
            .link_biz("y", "Ay")
            .realize("Ax", "a")
            .realize("Ax", "b")
            .realize("Ay", "a")
            .realize("Ay", "c")
        )
        b.cost.update({"a": Decimal("100.50"), "b": Decimal("20")})
        r = by_id(ca.business_rollup(b.build(), AS_OF))
        assert r["x"].cost.total_tco == Decimal("120.50") and r["x"].cost.apps_without_cost == 0
        assert r["y"].cost.total_tco == Decimal("100.50") and r["y"].cost.apps_without_cost == 1
        # Parent: distinct union {a, b, c}, not x + y.
        assert r["L2"].cost.total_tco == Decimal("120.50") and r["L2"].cost.apps_without_cost == 1

    def test_risk_worst_ignores_unknown(self):
        b = (
            Builder()
            .biz("L3", 3)
            .ac("A")
            .app("a")
            .app("b")
            .app("c")
            .link_biz("L3", "A")
            .realize("A", "a")
            .realize("A", "b")
            .realize("A", "c")
        )
        b.risk.update(
            {"a": RiskInfo("adequate", "none_known", None), "b": RiskInfo(None, None, None)}
        )
        risk = by_id(ca.business_rollup(b.build(), AS_OF))["L3"].risk
        assert risk.worst == "medium"
        assert risk.spread["medium"] == 1 and risk.spread["unknown"] == 2


class TestGating:
    def test_hidden_metrics_are_none_and_flagged(self):
        resp = ca.business_rollup(pos().build(risk_visible=False, cost_visible=False), AS_OF)
        assert resp.risk_available is False and resp.cost_available is False
        assert all(i.risk is None and i.cost is None for i in resp.items)
        assert all(i.health is not None for i in resp.items)

    def test_visible_but_empty_is_worst_none_not_missing(self):
        resp = ca.business_rollup(Builder().biz("x", 3).build(), AS_OF)
        assert resp.risk_available and resp.cost_available
        item = resp.items[0]
        assert item.risk is not None and item.risk.worst is None
        assert item.cost is not None and item.cost.total_tco is None

    def test_each_gate_is_independent(self):
        resp = ca.business_rollup(pos().build(risk_visible=True, cost_visible=False), AS_OF)
        assert resp.risk_available and not resp.cost_available
        assert all(i.risk is not None and i.cost is None for i in resp.items)


# ── Effective band and exposure (US4, FR-012..FR-014) ──────────────────────────


class TestEffectiveBand:
    @pytest.mark.parametrize(
        ("status", "eol", "band"),
        [
            ("retired", None, "past_end_of_life"),
            ("current", AS_OF, "past_end_of_life"),
            ("emerging", AS_OF - timedelta(days=10), "past_end_of_life"),
            ("retiring", None, "retiring"),
            ("current", AS_OF + timedelta(days=365), "retiring"),
            ("current", AS_OF + timedelta(days=366), "current"),
            ("contained", None, "contained"),
            ("emerging", None, "emerging"),
        ],
    )
    def test_bands(self, status, eol, band):
        assert ca.effective_band(TechNode("t", "t", 3, None, status, eol), AS_OF) == band


class TestExposure:
    def test_pos_retiring_offline_sync(self):
        b = pos()
        b.technical["Offline Sync"] = TechNode(
            "Offline Sync", "Offline Sync", 3, "Data Storage", "retiring", None
        )
        r = by_id(ca.business_rollup(b.build(), AS_OF))
        assert r["Process Checkout"].exposure.worst == "retiring"
        assert r["Apply Promotions"].exposure.worst == "current"
        assert r["In-Store"].exposure.worst == "retiring"
        assert (
            r["Sales"].exposure.spread["retiring"] == 1
            and r["Sales"].exposure.spread["current"] == 2
        )

    def test_l2_technical_link_expands_to_children(self):
        b = (
            Builder()
            .biz("L3", 3)
            .ac("A")
            .tech("T2", 2)
            .tech("T3", 3, "T2", status="retired")
            .link_biz("L3", "A")
            .link_tech("A", "T2")
        )
        assert (
            by_id(ca.business_rollup(b.build(), AS_OF))["L3"].exposure.worst == "past_end_of_life"
        )

    def test_no_chain_is_no_data(self):
        item = by_id(ca.business_rollup(Builder().biz("x", 3).build(), AS_OF))["x"]
        assert item.exposure.worst is None and item.exposure.spread["no_data"] == 1


class TestTechnologyDependencies:
    def test_l3_lists_each_technical_with_band(self):
        b = pos()
        b.technical["Offline Sync"] = TechNode(
            "Offline Sync", "Offline Sync", 3, "Data Storage", "retiring", None
        )
        deps = ca.technology_dependencies(b.build(), "Process Checkout", AS_OF)
        assert deps is not None
        assert [(d.technical.id, d.effective_band, d.via_app_capability.id) for d in deps] == [
            ("Offline Sync", "retiring", "Basket Calculation")
        ]
        assert [p.name for p in deps[0].technical.path] == ["Integration", "Data Storage"]

    def test_parent_unions_leaves_with_via_business(self):
        deps = ca.technology_dependencies(pos().build(), "In-Store", AS_OF)
        assert deps is not None
        assert {d.via_business_capability.id for d in deps} == {
            "Process Checkout",
            "Apply Promotions",
            "Accept Payment",
        }

    def test_unknown_capability_is_none(self):
        assert ca.technology_dependencies(pos().build(), "nope", AS_OF) is None


# ── Impact (US3, FR-011) ─────────────────────────────────────────────────────


class TestImpact:
    def test_pos_offline_sync(self):
        res = ca.impact(pos().build(), "Offline Sync")
        assert res is not None
        assert [a.id for a in res.application_capabilities] == ["Basket Calculation"]
        assert [a.id for a in res.applications] == ["POS"]
        assert [b.id for b in res.business_capabilities] == ["Process Checkout"]
        assert [p.name for p in res.business_capabilities[0].path] == ["Sales", "In-Store"]

    def test_l2_includes_children_with_via(self):
        res = ca.impact(pos().build(), "Data Storage")
        assert res is not None
        assert {a.id for a in res.application_capabilities} == {
            "Basket Calculation",
            "Price Rule Evaluation",
        }
        via = {a.id: [t.id for t in a.via_technical] for a in res.application_capabilities}
        assert via["Basket Calculation"] == ["Offline Sync"]
        assert {c.id for c in res.covered_technical} == {"Data Storage", "Offline Sync", "Caching"}

    def test_business_listed_once_with_both_routes(self):
        b = (
            Builder()
            .biz("B", 3)
            .ac("A1")
            .ac("A2")
            .tech("T")
            .link_biz("B", "A1")
            .link_biz("B", "A2")
            .link_tech("A1", "T")
            .link_tech("A2", "T")
        )
        res = ca.impact(b.build(), "T")
        assert res is not None
        assert len(res.business_capabilities) == 1
        assert [r.id for r in res.business_capabilities[0].routes] == ["A1", "A2"]

    def test_nothing_depends(self):
        res = ca.impact(Builder().tech("T").build(), "T")
        assert res is not None
        assert (
            res.application_capabilities == []
            and res.applications == []
            and res.business_capabilities == []
        )

    def test_retired_apps_listed_and_marked(self):
        b = (
            Builder()
            .ac("A")
            .tech("T")
            .app("old", lifecycle="retired")
            .link_tech("A", "T")
            .realize("A", "old")
        )
        res = ca.impact(b.build(), "T")
        assert res is not None and res.applications[0].lifecycle_status == "retired"

    def test_unknown_is_none_and_no_gated_fields(self):
        assert ca.impact(pos().build(), "nope") is None
        fields = set(ca.ImpactResult.model_fields)
        assert not fields & {"cost", "risk", "tco"}


# ── Findings (US5, FR-015..FR-017) ────────────────────────────────────────────


class TestFindings:
    def test_overlap_two_apps(self):
        b = (
            pos()
            .app("Commerce", 4)
            .ac("Online Promo", 3, "Checkout")
            .link_biz("Apply Promotions", "Online Promo")
        )
        b.realize("Online Promo", "Commerce")
        f = ca.findings(b.build())
        assert [o.business.id for o in f.overlaps] == ["Apply Promotions"]
        apps = {a.id: [v.id for v in a.via] for a in f.overlaps[0].applications}
        assert apps == {"Commerce": ["Online Promo"], "POS": ["Price Rule Evaluation"]}

    def test_same_app_twice_is_not_overlap(self):
        b = (
            pos()
            .ac("Other", 3, "Checkout")
            .link_biz("Apply Promotions", "Other")
            .realize("Other", "POS")
        )
        assert ca.findings(b.build()).overlaps == []

    def test_retired_does_not_create_overlap(self):
        b = pos().app("Old", lifecycle="retired").ac("Other").link_biz("Apply Promotions", "Other")
        b.realize("Other", "Old")
        assert ca.findings(b.build()).overlaps == []

    def test_gaps(self):
        b = (
            pos()
            .biz("Process Returns", 3, "In-Store")
            .ac("Loyalty", 3, "Checkout")
            .ac("Unrealized", 3, "Checkout")
        )
        b.link_biz("Process Checkout", "Unrealized")
        f = ca.findings(b.build())
        assert [g.id for g in f.gaps.business_without_app_capability] == ["Process Returns"]
        assert [p.name for p in f.gaps.business_without_app_capability[0].path] == [
            "Sales",
            "In-Store",
        ]
        assert [g.id for g in f.gaps.app_capability_without_business] == ["Loyalty"]
        assert {g.id for g in f.gaps.app_capability_without_application} == {
            "Loyalty",
            "Unrealized",
        }

    def test_shared_threshold(self):
        b = Builder().ac("A").ac("B")
        for i in range(3):
            b.biz(f"x{i}", 3).link_biz(f"x{i}", "A")
        for i in range(2):
            b.link_biz(f"x{i}", "B")
        f = ca.findings(b.build())
        assert [(s.app_capability.id, s.count) for s in f.shared] == [("A", 3)]

    def test_empty_estate(self):
        b = Builder().biz("x", 3).biz("y", 3)
        f = ca.findings(b.build())
        assert {g.id for g in f.gaps.business_without_app_capability} == {"x", "y"}
        assert f.overlaps == [] and f.shared == []


# ── Scale (SC-005 headroom) ─────────────────────────────────────────────────


class TestScale:
    def test_500_500_2000_is_fast(self):
        b = Builder()
        for i in range(25):
            b.biz(f"L1-{i}", 1)
            for j in range(4):
                b.biz(f"L2-{i}-{j}", 2, f"L1-{i}")
        for k in range(400):
            b.biz(f"B{k}", 3, f"L2-{k % 25}-{k % 4}")
        for k in range(500):
            b.ac(f"A{k}").app(f"app{k % 120}", health=(k % 5) + 1).realize(f"A{k}", f"app{k % 120}")
            b.tech(f"T{k}")
        for n in range(2000):
            if n % 2:
                b.link_biz(f"B{n % 400}", f"A{n % 500}")
            else:
                b.link_tech(f"A{n % 500}", f"T{(n * 7) % 500}")
        snap = b.build()
        start = time.perf_counter()
        ca.business_rollup(snap, AS_OF)
        ca.findings(snap)
        assert time.perf_counter() - start < 2.0
