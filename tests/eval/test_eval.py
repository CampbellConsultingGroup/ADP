"""Tests for the AI-quality eval harness (adp.eval)."""

from __future__ import annotations

from pathlib import Path

from adp.eval.runner import run_grounding_case, run_judge_case, run_suite
from adp.eval.scorer import grounding_score, verdict_agrees

_EVALS_DIR = Path(__file__).resolve().parents[2] / "evals"


# ── Scorer ───────────────────────────────────────────────────────────────────

def test_grounding_score_perfect() -> None:
    gs = grounding_score({"A", "B"}, {"A", "B"})
    assert gs.precision == 1.0 and gs.recall == 1.0 and gs.f1 == 1.0


def test_grounding_score_spurious_citation_lowers_precision() -> None:
    gs = grounding_score({"A", "B", "C"}, {"A", "B"})
    assert gs.precision == 2 / 3
    assert gs.recall == 1.0


def test_grounding_score_missing_citation_lowers_recall() -> None:
    gs = grounding_score({"A"}, {"A", "B"})
    assert gs.precision == 1.0
    assert gs.recall == 0.5


def test_verdict_agrees() -> None:
    assert verdict_agrees("fail", "fail")
    assert not verdict_agrees("pass", "fail")


# ── Judge cases drive the real gate() ────────────────────────────────────────

def test_judge_case_critical_fails() -> None:
    result = run_judge_case(
        {"id": "c", "kind": "judge", "findings": [{"severity": "critical"}],
         "expected_status": "fail"}
    )
    assert result.passed
    assert result.detail["actual"] == "fail"


def test_judge_case_detects_wrong_expectation() -> None:
    # A clean design cannot fail — expecting 'fail' must be reported as a miss.
    result = run_judge_case(
        {"id": "c", "kind": "judge", "findings": [], "expected_status": "fail"}
    )
    assert not result.passed
    assert result.detail["actual"] == "pass"


# ── Grounding cases drive the real validate_citations_step ────────────────────

async def test_grounding_case_valid_citations_not_advisory() -> None:
    result = await run_grounding_case({
        "id": "g", "kind": "grounding",
        "knowledge_index": {"KB-1": "1", "KB-2": "1"},
        "options": [{"option_id": "OPT-1", "grounded_on": ["KB-1", "KB-2"],
                     "expected_advisory": False, "expected_citations": ["KB-1", "KB-2"]}],
    })
    assert result.passed
    assert result.detail["mean_precision"] == 1.0


async def test_grounding_case_unresolvable_marks_advisory() -> None:
    result = await run_grounding_case({
        "id": "g", "kind": "grounding",
        "knowledge_index": {"KB-1": "1"},
        "options": [{"option_id": "OPT-1", "grounded_on": ["KB-1", "KB-404"],
                     "expected_advisory": True}],
    })
    assert result.passed  # the step correctly flagged it advisory


# ── Full suite over the shipped golden fixtures ──────────────────────────────

async def test_shipped_suite_all_pass() -> None:
    report = await run_suite(_EVALS_DIR)
    assert report.total > 0
    assert report.passed, f"failing cases: {[r.case_id for r in report.failed]}"
    assert report.metrics["verdict_accuracy"] == 1.0
    assert report.metrics["grounding_case_pass_rate"] == 1.0
