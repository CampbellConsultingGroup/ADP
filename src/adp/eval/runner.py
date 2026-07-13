"""Load golden cases and score them against the real product decision code."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml

from adp.eval.fakes import FakeKnowledgeRetrieval, NoOpTelemetry
from adp.eval.models import CaseResult, EvalReport
from adp.eval.scorer import grounding_score, mean, verdict_agrees
from adp.knowledge.schema import CitationRef
from adp.recommendation.models import RecommendationState, SolutionOption
from adp.recommendation.steps import validate_citations_step
from adp.validation.gate import gate
from adp.validation.models import Finding, FindingSeverity, GatingThreshold

# ── Case loading ─────────────────────────────────────────────────────────────

def load_cases(path: str | Path) -> list[dict[str, Any]]:
    """Load golden cases from a YAML file (a top-level list of case dicts)."""
    data = yaml.safe_load(Path(path).read_text()) or []
    if not isinstance(data, list):
        raise ValueError(f"{path}: expected a list of cases, got {type(data).__name__}")
    return data


def _discover(evals_dir: str | Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for yaml_file in sorted(Path(evals_dir).rglob("*.yaml")):
        cases.extend(load_cases(yaml_file))
    return cases


# ── Judge (gate) cases ───────────────────────────────────────────────────────

def run_judge_case(case: dict[str, Any]) -> CaseResult:
    """Drive the real ``gate()`` on labeled findings and compare its decision."""
    findings = [
        Finding(
            finding_id=f"FND-{i:03d}",
            operation_id=case.get("id", "eval"),
            critic_name=f.get("critic_name", "eval"),
            severity=FindingSeverity(f["severity"]),
            description=f.get("description", "eval finding"),
        )
        for i, f in enumerate(case.get("findings", []))
    ]
    thresholds = GatingThreshold(**case.get("thresholds", {}))
    actual = gate(findings, thresholds, llm_critics_ran=case.get("critics_ran", True))
    expected = case["expected_status"]
    passed = verdict_agrees(actual, expected)
    return CaseResult(
        case_id=case.get("id", "?"),
        kind="judge",
        passed=passed,
        detail={"expected": expected, "actual": actual},
    )


# ── Grounding (citation) cases ───────────────────────────────────────────────

async def run_grounding_case(case: dict[str, Any]) -> CaseResult:
    """Drive the real ``validate_citations_step`` and score citation grounding."""
    options: list[SolutionOption] = []
    for opt in case.get("options", []):
        options.append(
            SolutionOption(
                option_id=opt["option_id"],
                operation_id=case.get("id", "eval"),
                grounded_on=[
                    CitationRef(item_id=cid, item_version="1")
                    for cid in opt.get("grounded_on", [])
                ],
            )
        )

    state: RecommendationState = {
        "operation_id": case.get("id", "eval"),
        "ranked_options": options,
    }
    # The fakes are structural test-doubles for the step's collaborators.
    result_state = await validate_citations_step(
        state,
        knowledge_retrieval=cast(Any, FakeKnowledgeRetrieval(case.get("knowledge_index", {}))),
        telemetry=cast(Any, NoOpTelemetry()),
    )
    validated: list[SolutionOption] = result_state["validated_options"]
    by_id = {o.option_id: o for o in validated}

    passed = True
    per_option: list[dict[str, Any]] = []
    precisions: list[float] = []
    recalls: list[float] = []
    for spec in case.get("options", []):
        opt = by_id[spec["option_id"]]
        retained = {ref.item_id for ref in opt.grounded_on}
        advisory_ok = opt.advisory == spec.get("expected_advisory", opt.advisory)

        citations_ok = True
        gs = None
        if "expected_citations" in spec:
            expected = set(spec["expected_citations"])
            gs = grounding_score(retained, expected)
            precisions.append(gs.precision)
            recalls.append(gs.recall)
            citations_ok = retained == expected

        opt_passed = advisory_ok and citations_ok
        passed = passed and opt_passed
        per_option.append({
            "option_id": opt.option_id,
            "advisory": opt.advisory,
            "retained": sorted(retained),
            "precision": None if gs is None else gs.precision,
            "recall": None if gs is None else gs.recall,
            "passed": opt_passed,
        })

    return CaseResult(
        case_id=case.get("id", "?"),
        kind="grounding",
        passed=passed,
        detail={
            "options": per_option,
            "mean_precision": mean(precisions),
            "mean_recall": mean(recalls),
        },
    )


# ── Suite ────────────────────────────────────────────────────────────────────

async def run_suite(evals_dir: str | Path) -> EvalReport:
    """Run every golden case under ``evals_dir`` and aggregate metrics."""
    results: list[CaseResult] = []
    for case in _discover(evals_dir):
        kind = case.get("kind")
        if kind == "judge":
            results.append(run_judge_case(case))
        elif kind == "grounding":
            results.append(await run_grounding_case(case))
        else:
            raise ValueError(f"case {case.get('id', '?')}: unknown kind {kind!r}")

    judge = [r for r in results if r.kind == "judge"]
    grounding = [r for r in results if r.kind == "grounding"]
    metrics = {
        "verdict_accuracy": mean([1.0 if r.passed else 0.0 for r in judge]),
        "grounding_case_pass_rate": mean([1.0 if r.passed else 0.0 for r in grounding]),
        "mean_grounding_precision": mean(
            [r.detail["mean_precision"] for r in grounding]
        ),
        "mean_grounding_recall": mean([r.detail["mean_recall"] for r in grounding]),
    }
    return EvalReport(results=results, metrics=metrics)
