"""Table-driven unit tests for compute_status() -- ADP-d8u.5, research.md Decision 1.

Pure function, no I/O -- driven entirely from constructed target/direction/
progress-entry fixtures, no database or async session needed.

compute_status(status, target_value, direction, progress, trend_window=3):
  progress is a list[tuple[date, Decimal]] ordered ascending by date (a
  precondition, not re-sorted internally -- list_progress_entries already
  returns entries in that order, so the caller never needs to re-sort).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from adp.strategy.store import compute_status


def _d(day: int) -> date:
    return date(2026, 8, day)


class TestNoTargetOrNoProgress:
    def test_no_target_is_proposed_even_with_progress(self) -> None:
        # FR-008: not measurable -- never an error, never a guess.
        assert compute_status(None, None, None, [(_d(1), Decimal("50"))]) == "proposed"

    def test_target_but_zero_progress_entries_is_proposed(self) -> None:
        # FR-005: distinct from at-risk.
        assert compute_status(None, Decimal("100"), "increase", []) == "proposed"


class TestAchieved:
    def test_increase_direction_reached(self) -> None:
        entries = [(_d(1), Decimal("100"))]
        assert compute_status(None, Decimal("100"), "increase", entries) == "achieved"

    def test_increase_direction_passed(self) -> None:
        entries = [(_d(1), Decimal("120"))]
        assert compute_status(None, Decimal("100"), "increase", entries) == "achieved"

    def test_decrease_direction_reached(self) -> None:
        entries = [(_d(1), Decimal("10"))]
        assert compute_status(None, Decimal("10"), "decrease", entries) == "achieved"

    def test_decrease_direction_passed(self) -> None:
        entries = [(_d(1), Decimal("2"))]
        assert compute_status(None, Decimal("10"), "decrease", entries) == "achieved"

    def test_reach_direction_exact_match(self) -> None:
        assert compute_status(None, Decimal("50"), "reach", [(_d(1), Decimal("50"))]) == "achieved"

    def test_reach_direction_not_exact_is_not_achieved(self) -> None:
        assert compute_status(None, Decimal("50"), "reach", [(_d(1), Decimal("51"))]) != "achieved"


class TestAtRiskAndActive:
    def test_single_entry_not_at_target_is_active(self) -> None:
        # No prior entry to compare a trend against -- can't be "at risk" yet.
        entries = [(_d(1), Decimal("40"))]
        assert compute_status(None, Decimal("100"), "increase", entries) == "active"

    def test_two_entries_trending_toward_target_is_active(self) -> None:
        entries = [(_d(1), Decimal("40")), (_d(8), Decimal("55"))]
        assert compute_status(None, Decimal("100"), "increase", entries) == "active"

    def test_two_entries_trending_away_from_target_is_at_risk(self) -> None:
        entries = [(_d(1), Decimal("40")), (_d(8), Decimal("30"))]
        assert compute_status(None, Decimal("100"), "increase", entries) == "at_risk"

    def test_three_entries_all_trending_away_is_at_risk(self) -> None:
        entries = [(_d(1), Decimal("60")), (_d(8), Decimal("50")), (_d(15), Decimal("40"))]
        assert compute_status(None, Decimal("100"), "increase", entries) == "at_risk"

    def test_three_entries_mixed_trend_is_active_not_at_risk(self) -> None:
        # Not every consecutive pair moves away -- doesn't qualify as at_risk.
        entries = [(_d(1), Decimal("40")), (_d(8), Decimal("30")), (_d(15), Decimal("50"))]
        assert compute_status(None, Decimal("100"), "increase", entries) == "active"

    def test_trend_window_only_considers_last_n_entries(self) -> None:
        # 5 entries, only the most recent 3 count -- an early decline outside
        # the window must not itself force at_risk if the recent trend improved.
        entries = [
            (_d(1), Decimal("80")), (_d(8), Decimal("60")),  # outside the window
            (_d(15), Decimal("40")), (_d(22), Decimal("50")), (_d(29), Decimal("65")),
        ]
        assert compute_status(None, Decimal("100"), "increase", entries, trend_window=3) == "active"

    def test_decrease_direction_trend_away_is_at_risk(self) -> None:
        # For "decrease", moving away from target means the value is rising.
        entries = [(_d(1), Decimal("20")), (_d(8), Decimal("25"))]
        assert compute_status(None, Decimal("10"), "decrease", entries) == "at_risk"


class TestAbandonedShortCircuit:
    def test_abandoned_status_wins_regardless_of_progress(self) -> None:
        # FR-011 / ADP-d8u.5 US2: abandoned always short-circuits, even if the
        # progress trend would otherwise compute "achieved".
        entries = [(_d(1), Decimal("100"))]
        assert compute_status("abandoned", Decimal("100"), "increase", entries) == "abandoned"

    def test_abandoned_status_wins_with_no_target_at_all(self) -> None:
        assert compute_status("abandoned", None, None, []) == "abandoned"
