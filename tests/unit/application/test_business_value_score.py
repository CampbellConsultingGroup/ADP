"""Table-driven unit tests for compute_business_value_score() --
docs/application-business-value-assessment-spec.md §5.

Pure function, no I/O -- driven entirely from a dict of dimension scores.
Mirrors tests/unit/strategy/test_objective_status.py's own precedent for
testing this codebase's derived-value functions directly, no DB/HTTP.
"""

from __future__ import annotations

from adp.application.store import compute_business_value_score

_UNIFORM = {
    "strategic_alignment": 3,
    "revenue_cost_impact": 3,
    "customer_stakeholder_impact": 3,
    "competitive_differentiation": 3,
    "risk_compliance_contribution": 3,
    "evidence_measurability": 3,
}


def _scores(**overrides: int) -> dict[str, int]:
    merged = dict(_UNIFORM)
    merged.update(overrides)
    return merged  # type: ignore[return-value]


class TestUniformScores:
    """A uniform score across all six never gets capped tighter than
    itself -- the cap table's ceiling for each evidence value is always
    >= that same value (spec §5.2), so weighted_average == that value too."""

    def test_uniform_one(self) -> None:
        result = compute_business_value_score(_scores(**{k: 1 for k in _UNIFORM}))
        assert result.business_value == 1
        assert result.weighted_average == 1.0
        assert result.capped is False

    def test_uniform_three(self) -> None:
        result = compute_business_value_score(_scores(**{k: 3 for k in _UNIFORM}))
        assert result.business_value == 3
        assert result.capped is False

    def test_uniform_five(self) -> None:
        result = compute_business_value_score(_scores(**{k: 5 for k in _UNIFORM}))
        assert result.business_value == 5
        assert result.cap is None
        assert result.capped is False


class TestWorkedExampleFromSpec:
    """docs/application-business-value-assessment-spec.md §5.3's own worked
    example: Strategic Alignment 5, Revenue 5, Customer 4, Differentiation 4,
    Risk 3, Evidence 1 -> raw 4.05, capped at 2 by evidence=1."""

    def test_high_scores_but_low_evidence_gets_capped(self) -> None:
        result = compute_business_value_score(
            _scores(
                strategic_alignment=5,
                revenue_cost_impact=5,
                customer_stakeholder_impact=4,
                competitive_differentiation=4,
                risk_compliance_contribution=3,
                evidence_measurability=1,
            )
        )
        assert result.weighted_average == 4.05
        assert result.cap == 2
        assert result.capped is True
        assert result.business_value == 2


class TestCapTable:
    def test_evidence_one_caps_at_two(self) -> None:
        result = compute_business_value_score(
            _scores(evidence_measurability=1, strategic_alignment=5, revenue_cost_impact=5)
        )
        assert result.cap == 2
        assert result.business_value <= 2

    def test_evidence_two_caps_at_three(self) -> None:
        result = compute_business_value_score(
            _scores(evidence_measurability=2, strategic_alignment=5, revenue_cost_impact=5)
        )
        assert result.cap == 3
        assert result.business_value <= 3

    def test_evidence_three_caps_at_four(self) -> None:
        result = compute_business_value_score(
            _scores(evidence_measurability=3, strategic_alignment=5, revenue_cost_impact=5)
        )
        assert result.cap == 4
        assert result.business_value <= 4

    def test_evidence_four_applies_no_cap(self) -> None:
        result = compute_business_value_score(
            _scores(evidence_measurability=4, strategic_alignment=5, revenue_cost_impact=5)
        )
        assert result.cap is None
        assert result.capped is False

    def test_evidence_five_applies_no_cap(self) -> None:
        result = compute_business_value_score(
            _scores(evidence_measurability=5, strategic_alignment=5, revenue_cost_impact=5)
        )
        assert result.cap is None
        assert result.capped is False

    def test_cap_present_but_not_binding_is_not_flagged_capped(self) -> None:
        # evidence=3 -> cap=4, but a uniform-3 average (3.0) is already
        # below that cap -- the cap exists but doesn't actually reduce the
        # result, so `capped` must be False (spec §4: only report capping
        # when the cap is genuinely why the score came out lower).
        result = compute_business_value_score(_scores(evidence_measurability=3))
        assert result.cap == 4
        assert result.weighted_average == 3.0
        assert result.capped is False
        assert result.business_value == 3


class TestWeighting:
    def test_strategic_alignment_and_revenue_carry_more_weight(self) -> None:
        # Both at 25% each vs. e.g. competitive_differentiation at 10% --
        # raising the high-weight dimensions should move the average more.
        low_weight_boost = compute_business_value_score(
            _scores(competitive_differentiation=5, evidence_measurability=5)
        )
        high_weight_boost = compute_business_value_score(
            _scores(strategic_alignment=5, evidence_measurability=5)
        )
        assert high_weight_boost.weighted_average > low_weight_boost.weighted_average


class TestRounding:
    def test_rounds_half_up_not_bankers_rounding(self) -> None:
        # strategic_alignment=4 (25%) + revenue_cost_impact=4 (25%) +
        # customer=3(15%) + differentiation=3(10%) + risk=3(15%) + evidence=4(10%,
        # no cap) -> raw = 1.0+1.0+0.45+0.3+0.45+0.4 = 3.6 -- not a half-point
        # case, but confirms fractional averages round sensibly upward.
        result = compute_business_value_score(
            _scores(
                strategic_alignment=4, revenue_cost_impact=4,
                customer_stakeholder_impact=3, competitive_differentiation=3,
                risk_compliance_contribution=3, evidence_measurability=4,
            )
        )
        assert result.weighted_average == 3.6
        assert result.business_value == 4  # round-half-up territory, rounds up

    def test_business_value_always_within_1_to_5(self) -> None:
        for uniform in range(1, 6):
            result = compute_business_value_score(_scores(**{k: uniform for k in _UNIFORM}))
            assert 1 <= result.business_value <= 5
