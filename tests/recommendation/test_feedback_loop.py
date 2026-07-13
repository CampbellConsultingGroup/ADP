"""Tests for the recommendation feedback loop (ADP-SPEC-019): past accept/reject
decisions influence future generation labelling and ranking.
"""

from __future__ import annotations

from types import SimpleNamespace

from adp.eval.fakes import NoOpTelemetry
from adp.knowledge.schema import CitationRef
from adp.recommendation.models import SolutionOption
from adp.recommendation.steps import (
    HISTORY_WEIGHT,
    _decision_type,
    _knowledge_summary,
    rank_step,
)


def _entry(item_id: str, *, item_type: str | None, kind: str = "prior_solution",
           relevance: float = 0.9):
    metadata = {"item_type": item_type} if item_type else {}
    return SimpleNamespace(
        item=SimpleNamespace(kind=kind, metadata=metadata, title=item_id,
                             full_text="detail"),
        citation=SimpleNamespace(item_id=item_id, item_version="1"),
        relevance_score=relevance,
    )


def _option(option_id: str, cited: list[str]) -> SolutionOption:
    return SolutionOption(
        option_id=option_id,
        operation_id="op",
        satisfies=["REQ-1"],
        grounded_on=[CitationRef(item_id=c, item_version="1") for c in cited],
    )


# ── decision typing + prompt labelling ───────────────────────────────────────

def test_decision_type() -> None:
    def _ns(item_type):
        return SimpleNamespace(metadata={"item_type": item_type} if item_type else None)

    assert _decision_type(_ns("accepted_recommendation")) == "accepted"
    assert _decision_type(_ns("rejected_recommendation")) == "rejected"
    assert _decision_type(_ns("pattern")) is None
    assert _decision_type(_ns(None)) is None


def test_knowledge_summary_labels_decisions() -> None:
    summary = _knowledge_summary([
        _entry("KB-A", item_type="accepted_recommendation"),
        _entry("KB-R", item_type="rejected_recommendation"),
        _entry("KB-P", item_type=None, kind="pattern"),
    ])
    assert "ACCEPTED PATTERN (prefer)" in summary
    assert "REJECTED PATTERN (avoid)" in summary
    assert "[KB-P@1] pattern" in summary  # ordinary items keep their kind


# ── ranking consumes the historical signal ───────────────────────────────────

def test_rank_step_boosts_accepted_penalises_rejected() -> None:
    retrieved = [
        _entry("KB-A", item_type="accepted_recommendation"),
        _entry("KB-R", item_type="rejected_recommendation"),
    ]
    opt_accept = _option("O-accept", ["KB-A"])
    opt_reject = _option("O-reject", ["KB-R"])
    state = {
        "operation_id": "op",
        "candidate_options": [opt_reject, opt_accept],  # deliberately reverse order
        "retrieved_knowledge": retrieved,
        "requirement_ids": ["REQ-1"],
    }

    out = rank_step(state, telemetry=NoOpTelemetry())
    ranked = {o.option_id: o for o in out["ranked_options"]}

    assert ranked["O-accept"].history_score == 1.0
    assert ranked["O-reject"].history_score == -1.0
    # Identical on every other dimension, so history decides ordering.
    assert ranked["O-accept"].ranking_score > ranked["O-reject"].ranking_score
    assert ranked["O-accept"].rank == 1
    # The boost is exactly the history weight applied to the net signal.
    delta = ranked["O-accept"].ranking_score - ranked["O-reject"].ranking_score
    assert abs(delta - 2 * HISTORY_WEIGHT) < 1e-9


def test_rank_step_no_history_is_neutral() -> None:
    state = {
        "operation_id": "op",
        "candidate_options": [_option("O-1", [])],
        "retrieved_knowledge": [_entry("KB-P", item_type=None, kind="pattern")],
        "requirement_ids": ["REQ-1"],
    }
    out = rank_step(state, telemetry=NoOpTelemetry())
    assert out["ranked_options"][0].history_score == 0.0
