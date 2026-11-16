"""Pure engine tests for 942-regional-assessments (no database).

Capabilities (baseline maturity)      Geography
Sell (L1, 3)                          Global
  Payments (L2, none)                   Europe > Germany, France
    Accept Payment (L3, 3)              Americas > Brazil
    eSocial (L3, none)
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from adp.organization import regional_analysis as ra
from adp.organization.models import LevelRuleError, UnknownReferenceError
from adp.organization.regional_analysis import Assessment, CapNode, GeoNode, RegionalSnapshot

T = datetime(2026, 11, 16, tzinfo=timezone.utc)
CAPS = [
    CapNode("sell", "Sell", 1, None, 0, 3),
    CapNode("pay", "Payments", 2, "sell", 0, None),
    CapNode("accept", "Accept Payment", 3, "pay", 0, 3),
    CapNode("esocial", "eSocial", 3, "pay", 1, None),
]
GEOS = [
    GeoNode("g", "Global", 1, None, None),
    GeoNode("eu", "Europe", 2, "g", None),
    GeoNode("am", "Americas", 2, "g", None),
    GeoNode("de", "Germany", 3, "eu", "DE"),
    GeoNode("fr", "France", 3, "eu", "FR"),
    GeoNode("br", "Brazil", 3, "am", "BR"),
]


def snap(
    assessments: dict[tuple[str, str], tuple[int | None, str | None]] | None = None,
    scopes: dict[str, set[str]] | None = None,
) -> RegionalSnapshot:
    return RegionalSnapshot.build(
        capabilities=CAPS,
        geographies=GEOS,
        assessments=[
            Assessment(f"a-{c}-{g}", c, g, m, n, T)
            for (c, g), (m, n) in (assessments or {}).items()
        ],
        scopes={k: frozenset(v) for k, v in (scopes or {}).items()},
    )


def cells(h, cap_id: str) -> list[tuple[str, int | None, int | None]]:  # type: ignore[no-untyped-def]
    row = next(r for r in h.rows if r.capability.id == cap_id)
    return [(c.state, c.maturity_level, c.delta) for c in row.cells]


# ── US3: cells and the heat map ────────────────────────────────────────────────


class TestCells:
    def test_assessed_cell_carries_score_note_and_delta(self) -> None:
        s = snap({("accept", "eu"): (5, "Shared service in Dublin")})
        c = ra.cell(s, "accept", "eu")
        assert (c.state, c.maturity_level, c.note, c.delta) == (
            "assessed",
            5,
            "Shared service in Dublin",
            2,
        )

    def test_no_delta_without_a_baseline_or_a_score(self) -> None:
        s = snap({("esocial", "br"): (2, None), ("accept", "br"): (None, "Manual")})
        assert ra.cell(s, "esocial", "br").delta is None
        c = ra.cell(s, "accept", "br")
        assert (c.state, c.maturity_level, c.delta, c.note) == ("assessed", None, None, "Manual")

    def test_unassessed_cell(self) -> None:
        assert ra.cell(snap(), "accept", "eu").state == "not_assessed"

    def test_no_inheritance_and_no_roll_up(self) -> None:
        s = snap({("accept", "eu"): (4, None), ("pay", "de"): (2, None)})
        assert ra.cell(s, "accept", "de").state == "not_assessed"  # country doesn't inherit
        assert ra.cell(s, "pay", "eu").state == "not_assessed"  # no roll-up from children
        assert ra.cell(s, "sell", "eu").state == "not_assessed"


class TestHeatmap:
    def test_default_columns_are_the_regions_by_name(self) -> None:
        h = ra.heatmap(snap(), None)
        assert [c.name for c in h.columns] == ["Americas", "Europe"]
        assert h.max_columns == 12

    def test_rows_follow_the_tree_with_their_baseline(self) -> None:
        h = ra.heatmap(snap(), None)
        assert [(r.capability.name, r.baseline) for r in h.rows] == [
            ("Sell", 3),
            ("Payments", None),
            ("Accept Payment", 3),
            ("eSocial", None),
        ]

    def test_requested_columns_keep_their_order_and_drop_duplicates(self) -> None:
        h = ra.heatmap(snap({("accept", "br"): (2, None)}), ["br", "eu", "br", "de"])
        assert [c.id for c in h.columns] == ["br", "eu", "de"]
        assert [c.code for c in h.columns] == ["BR", None, "DE"]
        assert cells(h, "accept") == [
            ("assessed", 2, -1),
            ("not_assessed", None, None),
            ("not_assessed", None, None),
        ]

    def test_bad_columns_raise(self) -> None:
        with pytest.raises(LevelRuleError, match="baseline"):
            ra.heatmap(snap(), ["g"])
        with pytest.raises(UnknownReferenceError):
            ra.heatmap(snap(), ["nope"])
        with pytest.raises(LevelRuleError, match="12"):
            ra.columns(snap(), ["eu"] * 1 + [f"x{i}" for i in range(12)])


# ── US2: applicability ─────────────────────────────────────────────────────────


class TestApplicability:
    def test_not_region_specific_applies_everywhere(self) -> None:
        s = snap()
        assert all(ra.applicable(s, "accept", g) for g in ("eu", "am", "de", "br"))

    def test_scope_matches_by_containment_both_ways(self) -> None:
        s = snap(scopes={"esocial": {"br"}, "accept": {"am"}})
        assert [ra.applicable(s, "esocial", g) for g in ("br", "am", "eu", "de")] == [
            True,
            True,
            False,
            False,
        ]
        assert ra.applicable(s, "accept", "br") is True  # inside the Americas
        assert ra.applicable(s, "accept", "fr") is False

    def test_flagged_empty_scope_applies_nowhere_and_needs_update(self) -> None:
        s = snap(scopes={"esocial": set()})
        h = ra.heatmap(s, ["br", "eu"])
        row = next(r for r in h.rows if r.capability.id == "esocial")
        assert row.region_specific is True and row.scope_needs_update is True
        assert [c.state for c in row.cells] == ["not_applicable", "not_applicable"]

    def test_not_applicable_wins_over_an_assessment(self) -> None:
        s = snap({("esocial", "eu"): (3, None)}, scopes={"esocial": {"br"}})
        assert ra.cell(s, "esocial", "eu").state == "not_applicable"
        h = ra.heatmap(s, ["br", "eu"])
        assert cells(h, "esocial") == [
            ("not_assessed", None, None),
            ("not_applicable", None, None),
        ]


# ── US4: export block ──────────────────────────────────────────────────────────


class TestExportBlock:
    def test_block(self) -> None:
        s = snap({("esocial", "br"): (2, "Manual filing")}, scopes={"esocial": {"br"}})
        assert ra.export_block(s, "esocial") == {
            "region_specific": True,
            "scope": [{"id": "br", "name": "Brazil"}],
            "scope_needs_update": False,
            "assessments": [
                {
                    "geography": {"id": "br", "name": "Brazil", "code": "BR"},
                    "maturity_level": 2,
                    "note": "Manual filing",
                }
            ],
        }

    def test_empty_block(self) -> None:
        assert ra.export_block(snap(), "accept") == ra.EMPTY_BLOCK
        assert ra.export_block(snap(), "missing") == ra.EMPTY_BLOCK
