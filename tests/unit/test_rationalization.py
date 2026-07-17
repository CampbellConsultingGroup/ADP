"""Unit tests for the TIME rationalization projection (APM US1, ADP-SPEC-038)."""

from __future__ import annotations

from adp.application.rationalization import build_projection, quadrant_for


def test_quadrant_mapping_four_corners():
    assert quadrant_for(5, 5) == "invest"      # high value, high health
    assert quadrant_for(5, 1) == "migrate"     # high value, low health
    assert quadrant_for(1, 5) == "tolerate"    # low value, high health
    assert quadrant_for(1, 1) == "eliminate"   # low value, low health


def test_quadrant_threshold_is_three():
    # >= 3 counts as high on the 1–5 scale.
    assert quadrant_for(3, 3) == "invest"
    assert quadrant_for(2, 2) == "eliminate"
    assert quadrant_for(3, 2) == "migrate"
    assert quadrant_for(2, 3) == "tolerate"


def test_unassessed_returns_none():
    assert quadrant_for(None, 5) is None
    assert quadrant_for(5, None) is None
    assert quadrant_for(None, None) is None


def test_build_projection_splits_and_preserves_order():
    rows = [
        {"id": "A", "name": "Alpha", "business_value": 5, "health_score": 2},   # migrate
        {"id": "B", "name": "Beta", "business_value": None, "health_score": 4},  # unassessed
        {"id": "C", "name": "Gamma", "business_value": 2, "health_score": None},  # unassessed
        {"id": "D", "name": "Delta", "business_value": 4, "health_score": 5},    # invest
    ]
    proj = build_projection(rows)

    assert proj.total == 4
    assert [e.app_id for e in proj.assessed] == ["A", "D"]
    assert proj.assessed[0].quadrant == "migrate"
    assert proj.assessed[1].quadrant == "invest"

    assert {e.app_id for e in proj.unassessed} == {"B", "C"}
    assert all(e.quadrant is None for e in proj.unassessed)


def test_build_projection_empty():
    proj = build_projection([])
    assert proj.total == 0
    assert proj.assessed == []
    assert proj.unassessed == []
